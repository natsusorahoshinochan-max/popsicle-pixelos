/* SPDX-License-Identifier: Apache-2.0 */
package com.android.camera;

import android.content.Context;
import android.graphics.Bitmap;
import android.graphics.Rect;
import android.util.Size;
import android.util.Rational;
import android.graphics.BitmapFactory;
import android.hardware.camera2.CameraCharacteristics;
import android.hardware.camera2.CaptureResult;
import android.hardware.camera2.DngCreator;
import android.net.Uri;
import android.util.Log;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.File;
import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.io.OutputStream;
import java.io.FileOutputStream;
import java.io.IOException;
import java.lang.reflect.Array;
import java.nio.ByteBuffer;
import java.nio.charset.StandardCharsets;

/** OEM save boundary adaptation. Does not reinterpret unknown RAW formats. */
public final class PixelosRawSave {
    private static final String TAG = "PixelosRawSave";
    private static final ThreadLocal<Boolean> NEW_FILE = new ThreadLocal<>();
    private static final long MAX_PAYLOAD = 320L * 1024 * 1024;

    private PixelosRawSave() {}

    public static void begin(String path) {
        NEW_FILE.set(!new File(path).exists());
    }

    public static void complete() {
        NEW_FILE.remove();
    }

    @SuppressWarnings({"rawtypes", "unchecked"})
    private static Object vendor(CaptureResult result, String name) {
        for (CaptureResult.Key key : result.getKeys()) {
            if (key.getName().equals(name)) return result.get(key);
        }
        return null;
    }

    private static boolean enabled(Object value) {
        if (value == null) return false;
        if (value instanceof Boolean) return (Boolean) value;
        if (value instanceof Number) return ((Number) value).intValue() != 0;
        return Array.getLength(value) > 0 && enabled(Array.get(value, 0));
    }

    private static void set(Object metadata, CameraCharacteristics.Key<?> key, Object value)
            throws ReflectiveOperationException {
        metadata.getClass().getMethod("set", CameraCharacteristics.Key.class, Object.class)
                .invoke(metadata, key, value);
    }

    public static DngCreator create(Object request) throws Exception {
        CameraCharacteristics characteristics = (CameraCharacteristics) field(request, "N");
        CaptureResult result = (CaptureResult) field(request, "O");
        int width = (Integer) field(request, "J");
        int height = (Integer) field(request, "K");
        int rawType = (Integer) field(request, "r");
        byte[] pixels = (byte[]) field(request, "p");
        if ((rawType & 1) != 0) {
            DngTiles layout = new DngTiles((byte[]) vendor(result,
                    "com.xiaomi.dng.compressedParameters"), pixels);
            width = layout.width;
            height = layout.height;
        } else if (pixels == null || pixels.length != (long) width * height * 2) {
            throw new IOException("RAW16 payload length does not match dimensions");
        }
        Object metadata = CameraCharacteristics.class.getMethod("getNativeCopy")
                .invoke(characteristics);
        Size original = characteristics.get(CameraCharacteristics.SENSOR_INFO_PIXEL_ARRAY_SIZE);
        Rect pre = characteristics.get(CameraCharacteristics.SENSOR_INFO_PRE_CORRECTION_ACTIVE_ARRAY_SIZE);
        if (original == null || pre == null) throw new IOException("Missing sensor geometry");
        if ((width != original.getWidth() || height != original.getHeight())
                && (width != pre.width() || height != pre.height())) {
            // OS4 full-resolution final output is already remosaiced RGGB, unlike
            // the earlier Quad conversion dump. Adapt only this explicit contract.
            if ((rawType & 1) != 0 || width != original.getWidth() * 2
                    || height != original.getHeight() * 2
                    || !enabled(vendor(result, "com.xiaomi.dng.isQuadRawRemosaic"))) {
                throw new IOException("Unsupported OEM DNG geometry " + width + "x" + height);
            }
            set(metadata, CameraCharacteristics.SENSOR_INFO_PIXEL_ARRAY_SIZE, new Size(width, height));
            set(metadata, CameraCharacteristics.SENSOR_INFO_PRE_CORRECTION_ACTIVE_ARRAY_SIZE, scale(pre));
            Rect active = characteristics.get(CameraCharacteristics.SENSOR_INFO_ACTIVE_ARRAY_SIZE);
            if (active == null) throw new IOException("Missing active array");
            set(metadata, CameraCharacteristics.SENSOR_INFO_ACTIVE_ARRAY_SIZE, scale(active));
            Object capture = CaptureResult.class.getMethod("getNativeCopy").invoke(result);
            java.lang.reflect.Method update = capture.getClass().getMethod(
                    "set", CaptureResult.Key.class, Object.class);
            float[] intrinsic = result.get(CaptureResult.LENS_INTRINSIC_CALIBRATION);
            if (intrinsic != null) {
                intrinsic = intrinsic.clone();
                for (int i = 0; i < intrinsic.length; i++) intrinsic[i] *= 2;
                update.invoke(capture, CaptureResult.LENS_INTRINSIC_CALIBRATION, intrinsic);
            }
            android.graphics.Point[] hot = result.get(CaptureResult.STATISTICS_HOT_PIXEL_MAP);
            if (hot != null && hot.length != 0) {
                throw new IOException("Full-resolution hot-pixel coordinates require OEM mapping");
            }
            result = CaptureResult.class.getConstructor(capture.getClass(), int.class)
                    .newInstance(capture, result.getSequenceId());
            // DngCreator uses the effective rectangle for both crop and gain-map extent.
            // Do not globally rewrite HAL characteristics or bypass native validation.
        }
        Integer white = result.get(CaptureResult.SENSOR_DYNAMIC_WHITE_LEVEL);
        if (white != null) {
            if (white <= 0 || white > 65535) throw new IOException("Invalid RAW16 white level");
            set(metadata, CameraCharacteristics.SENSOR_INFO_WHITE_LEVEL, white);
        }
        CameraCharacteristics effective = CameraCharacteristics.class
                .getConstructor(metadata.getClass()).newInstance(metadata);
        return new DngCreator(effective, result);
    }

    private static Rect scale(Rect rect) {
        return new Rect(rect.left * 2, rect.top * 2, rect.right * 2, rect.bottom * 2);
    }

    public static void writeCompressed(Object request, DngCreator creator, OutputStream output)
            throws Exception {
        CaptureResult result = (CaptureResult) field(request, "O");
        byte[] pixels = (byte[]) field(request, "p");
        DngTiles layout = new DngTiles((byte[]) vendor(result,
                "com.xiaomi.dng.compressedParameters"), pixels);
        // Keep all platform-generated calibration, EXIF, orientation and thumbnail
        // tags, then adapt compressed storage and the OEM per-frame white-balance pair.
        try (Template template = new Template(); InputStream zeros = new InputStream() {
            @Override public int read() { return 0; }
            @Override public int read(byte[] data, int offset, int count) {
                java.util.Arrays.fill(data, offset, offset + count, (byte) 0);
                return count;
            }
        }) {
            creator.writeInputStream(template, new Size(layout.width, layout.height), zeros, 0);
            layout.write(template.bytes(), template.size(), pixels,
                    (byte[]) vendor(result, "com.xiaomi.dng.awbFrameParams"), output);
        }
    }

    private static final class Template extends ByteArrayOutputStream {
        byte[] bytes() { return buf; }
    }

    public static void thumbnail(DngCreator creator, ByteBuffer jpeg) {
        if (jpeg == null) return;
        Bitmap bitmap = null;
        Bitmap scaled = null;
        try {
            ByteBuffer input = jpeg.duplicate();
            input.clear();
            byte[] data = new byte[input.remaining()];
            input.get(data);
            BitmapFactory.Options options = new BitmapFactory.Options();
            options.inJustDecodeBounds = true;
            BitmapFactory.decodeByteArray(data, 0, data.length, options);
            if (options.outWidth <= 0 || options.outHeight <= 0) {
                throw new IOException("OEM preview is not a decodable image");
            }
            options.inJustDecodeBounds = false;
            options.inSampleSize = 1;
            while (Math.max(options.outWidth, options.outHeight) / options.inSampleSize > 512) {
                options.inSampleSize *= 2;
            }
            bitmap = BitmapFactory.decodeByteArray(data, 0, data.length, options);
            if (bitmap == null) throw new IOException("Cannot decode OEM preview");
            int longest = Math.max(bitmap.getWidth(), bitmap.getHeight());
            if (longest > DngCreator.MAX_THUMBNAIL_DIMENSION) {
                double scale = (double) DngCreator.MAX_THUMBNAIL_DIMENSION / longest;
                scaled = Bitmap.createScaledBitmap(bitmap,
                        Math.max(1, (int) Math.round(bitmap.getWidth() * scale)),
                        Math.max(1, (int) Math.round(bitmap.getHeight() * scale)), true);
            }
            creator.setThumbnail(scaled == null ? bitmap : scaled);
        } catch (IOException | RuntimeException e) {
            // Preview was already optional in the original app. Report the real
            // failure without turning it into a main-image success or suppressing
            // any exception from the main DNG writer.
            Log.w(TAG, "Cannot attach optional DNG preview", e);
        } finally {
            if (scaled != null && scaled != bitmap) scaled.recycle();
            if (bitmap != null) bitmap.recycle();
        }
    }

    public static void failed(Object request, String path, Uri uri, Throwable failure) {
        Log.e(TAG, "DNG save failed: " + path, failure);
        try {
            Context context = (Context) request.getClass().getField("a").get(request);
            try {
                boolean retain = (Boolean) Class.forName("android.os.SystemProperties")
                        .getMethod("getBoolean", String.class, boolean.class)
                        .invoke(null, "debug.popsicle.dng.capture", false);
                if (retain) captureFailure(context, request, failure);
            } catch (Exception e) {
                Log.w(TAG, "Cannot retain failed DNG input", e);
            }
            // A URI here was inserted for this save attempt. Existing path-only
            // files are not deleted, even if an OEM name collision truncated one.
            if (uri != null && Boolean.TRUE.equals(NEW_FILE.get())) {
                int removed = context.getContentResolver().delete(uri, null, null);
                if (removed != 1) Log.w(TAG, "Failed DNG row delete count=" + removed);
            } else if (uri == null && Boolean.TRUE.equals(NEW_FILE.get())) {
                File file = new File(path);
                if (file.exists() && !file.delete()) Log.w(TAG, "Cannot remove " + path);
            }
        } catch (Exception e) {
            Log.e(TAG, "Cannot clean up failed DNG", e);
        } finally {
            NEW_FILE.remove();
        }
    }

    private static Object field(Object request, String name) throws Exception {
        return request.getClass().getField(name).get(request);
    }

    private static Object jsonValue(Object value) throws Exception {
        if (value == null) return JSONObject.NULL;
        if (value.getClass().isArray()) {
            JSONArray array = new JSONArray();
            for (int i = 0; i < Array.getLength(value); i++) {
                array.put(jsonValue(Array.get(value, i)));
            }
            return array;
        }
        if (value instanceof Rational) return value.toString();
        if (value instanceof Number || value instanceof Boolean || value instanceof String) {
            return value;
        }
        return value.toString();
    }

    private static boolean needed(String name) {
        return name.startsWith("android.sensor.") || name.startsWith("android.scaler.")
                || name.startsWith("android.lens.") || name.startsWith("android.colorCorrection.")
                || name.startsWith("android.statistics.") || name.startsWith("android.request.")
                || name.equals("android.control.postRawSensitivityBoost")
                || name.toLowerCase(java.util.Locale.ROOT).contains("dng")
                || name.toLowerCase(java.util.Locale.ROOT).contains("remosaic")
                || name.contains("SuperResolutionStreamConfigurations");
    }

    @SuppressWarnings({"rawtypes", "unchecked"})
    private static synchronized void captureFailure(Context context, Object request,
            Throwable failure) throws Exception {
        byte[] pixels = (byte[]) field(request, "p");
        int width = (Integer) field(request, "J");
        int height = (Integer) field(request, "K");
        int rawType = (Integer) field(request, "r");
        String slot = (rawType & 3) != 0 ? "oem" : ((long) width * height > 16000000
                ? "full-resolution" : "standard");
        File directory = new File(context.getFilesDir(), "pixelos-dng-failures/" + slot);
        if (!directory.isDirectory() && !directory.mkdirs()) {
            throw new IOException("Cannot create DNG failure directory");
        }
        JSONObject report = new JSONObject();
        report.put("timeMillis", System.currentTimeMillis());
        report.put("rawType", rawType);
        report.put("width", width);
        report.put("height", height);
        report.put("bytes", pixels == null ? -1 : pixels.length);
        report.put("exception", Log.getStackTraceString(failure));
        CameraCharacteristics characteristics = (CameraCharacteristics) field(request, "N");
        CaptureResult result = (CaptureResult) field(request, "O");
        JSONObject staticMetadata = new JSONObject();
        for (CameraCharacteristics.Key key : characteristics.getKeys()) {
            if (needed(key.getName())) staticMetadata.put(key.getName(),
                    jsonValue(characteristics.get(key)));
        }
        JSONObject captureMetadata = new JSONObject();
        for (CaptureResult.Key key : result.getKeys()) {
            if (needed(key.getName())) captureMetadata.put(key.getName(), jsonValue(result.get(key)));
        }
        report.put("characteristics", staticMetadata);
        report.put("captureResult", captureMetadata);
        // One overwritten pair per branch, app-private; no background collection.
        // Remove the previous pair first so it can never be confused with this report.
        File payload = new File(directory, "payload.bin");
        File metadata = new File(directory, "metadata.json");
        if (payload.exists() && !payload.delete()) throw new IOException("Cannot retire payload");
        if (metadata.exists() && !metadata.delete()) throw new IOException("Cannot retire metadata");
        boolean retained = pixels != null && pixels.length <= MAX_PAYLOAD
                && directory.getUsableSpace() > pixels.length + 512L * 1024 * 1024;
        if (retained) write(payload, pixels);
        report.put("payloadRetained", retained);
        write(metadata, report.toString(2).getBytes(StandardCharsets.UTF_8));
        Log.i(TAG, "Failed DNG input retained at " + directory);
    }

    private static void write(File destination, byte[] data) throws IOException {
        File temporary = new File(destination.getParentFile(), destination.getName() + ".tmp");
        try {
            try (FileOutputStream output = new FileOutputStream(temporary)) {
                output.write(data);
            }
            if (!temporary.renameTo(destination)) throw new IOException("Cannot publish diagnostic");
        } finally {
            if (temporary.exists() && !temporary.delete()) Log.w(TAG, "Cannot remove " + temporary);
        }
    }
}
