/* SPDX-License-Identifier: Apache-2.0 */
package com.xiaomi.subscreencenter.personalization;

import android.content.ContentProvider;
import android.content.ContentValues;
import android.content.Context;
import android.database.Cursor;
import android.graphics.Bitmap;
import android.graphics.BitmapFactory;
import android.graphics.Point;
import android.media.MediaMetadataRetriever;
import android.net.Uri;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.os.ParcelFileDescriptor;
import android.os.Process;
import android.view.Display;
import java.io.*;
import java.nio.charset.StandardCharsets;
import java.util.*;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;
import org.json.JSONArray;
import org.json.JSONObject;
import java.nio.file.Files;
import java.util.concurrent.atomic.AtomicReference;
import java.util.zip.ZipEntry;
import java.util.zip.ZipOutputStream;

/** A Settings-only import boundary. SSC owns all media and its original widget configuration. */
public final class RearPersonalizationProvider extends ContentProvider {
    private static final long MAX_BYTES = 256L * 1024 * 1024;
    private final Object importLock = new Object();

    @Override public boolean onCreate() {
        // Provider creation precedes this process's panel loading and imports.
        // Only reclaim files that the last process never committed. Never use
        // a timer to delete media that a live panel may still be displaying.
        try {
            Set<String> referenced = referencedDirectories(readWidgets());
            File[] directories = mediaRoot().listFiles();
            if (directories != null) for (File directory : directories) {
                if (!referenced.contains(directory.getCanonicalPath())) delete(directory);
            }
        } catch (Exception e) {
            android.util.Log.w("RearPersonalization", "Keeping media: configuration unavailable", e);
        }
        return true;
    }

    private File mediaRoot() {
        return new File(getContext().createDeviceProtectedStorageContext().getFilesDir(),
                "rear-personalization");
    }

    private JSONArray readWidgets() throws Exception {
        File data = getContext().createDeviceProtectedStorageContext().getDataDir();
        return new JSONArray(Files.readString(new File(data,
                "oem_theme/config/widget.json").toPath(), StandardCharsets.UTF_8));
    }

    private static Set<String> referencedDirectories(JSONArray widgets) throws Exception {
        Set<String> result = new HashSet<>();
        for (int i = 0; i < widgets.length(); i++) {
            JSONObject widget = widgets.getJSONObject(i);
            String path = widget.optString("path", "");
            if (!path.isEmpty()) result.add(new File(path).getCanonicalFile().getParent());
        }
        return result;
    }

    @Override public Bundle call(String method, String arg, Bundle extras) {
        String caller = getCallingPackage();
        if (!"com.android.settings".equals(caller)
                || getContext().getPackageManager().checkSignatures(caller,
                getContext().getPackageName()) != android.content.pm.PackageManager.SIGNATURE_MATCH) {
            throw new SecurityException("Only platform Settings may configure the rear display");
        }
        try {
            if ("state".equals(method)) return state();
            if ("options".equals(method)) {
                if (extras == null) throw new IllegalArgumentException("Missing options");
                android.content.SharedPreferences.Editor editor = RearPersonalization.prefs(getContext()).edit();
                if (extras.containsKey("always_on")) {
                    if (extras.getBoolean("always_on") && !RearPersonalization.pocketAvailable())
                        throw new IllegalStateException("背屏口袋传感器不可用，无法安全启用常亮");
                    editor.putBoolean("always_on", extras.getBoolean("always_on"));
                }
                if (extras.containsKey("long_press"))
                    editor.putBoolean("long_press", extras.getBoolean("long_press"));
                if (!editor.commit()) throw new IOException("无法保存设置");
                return state();
            }
            if ("import".equals(method)) {
                synchronized (importLock) { return importMedia(extras); }
            }
            if ("reset".equals(method)) {
                synchronized (importLock) {
                    publish(null);
                    if (!RearPersonalization.prefs(getContext()).edit().remove("media").commit())
                        throw new IOException("无法保存设置");
                    return state();
                }
            }
            throw new IllegalArgumentException("Unknown operation");
        } catch (Exception e) {
            android.util.Log.e("RearPersonalization", "Operation failed", e);
            Bundle result = new Bundle();
            result.putString("error", e.getMessage() == null ? "操作失败" : e.getMessage());
            return result;
        }
    }

    private Bundle state() throws Exception {
        Bundle result = new Bundle();
        android.content.SharedPreferences prefs = RearPersonalization.prefs(getContext());
        result.putBoolean("always_on", prefs.getBoolean("always_on", false));
        result.putBoolean("long_press", prefs.getBoolean("long_press", true));
        result.putString("media", prefs.getString("media", "系统原有内容"));
        result.putString("status", RearPersonalization.status());
        result.putBoolean("pocket", RearPersonalization.pocketAvailable());
        Display display = RearPersonalization.rearDisplay(getContext());
        if (display == null) throw new IllegalStateException("未找到内置背屏");
        Point size = new Point();
        display.getRealSize(size);
        result.putInt("width", size.x);
        result.putInt("height", size.y);
        return result;
    }

    private Bundle importMedia(Bundle extras) throws Exception {
        if (extras == null) throw new IllegalArgumentException("未选择素材");
        boolean video = extras.getBoolean("video");
        ParcelFileDescriptor descriptor = extras.getParcelable("file", ParcelFileDescriptor.class);
        if (descriptor == null) throw new IllegalArgumentException("无法读取素材");
        File root = mediaRoot();
        File directory = new File(root, UUID.randomUUID().toString());
        if (!directory.mkdirs()) throw new IOException("无法创建素材目录");
        boolean published = false;
        try {
            File media = new File(directory, video ? "video.mp4" : "image.png");
            try (InputStream input = new ParcelFileDescriptor.AutoCloseInputStream(descriptor);
                    FileOutputStream output = new FileOutputStream(media)) {
                byte[] buffer = new byte[65536];
                long total = 0;
                int length;
                while ((length = input.read(buffer)) != -1) {
                    total += length;
                    if (total > MAX_BYTES) throw new IOException("素材不能超过 256 MiB");
                    output.write(buffer, 0, length);
                }
                if (total == 0) throw new IOException("素材为空");
                output.getFD().sync();
            }
            File preview = new File(directory, "preview.png");
            if (video) {
                try (MediaMetadataRetriever retriever = new MediaMetadataRetriever()) {
                    retriever.setDataSource(media.getAbsolutePath());
                    String width = retriever.extractMetadata(MediaMetadataRetriever.METADATA_KEY_VIDEO_WIDTH);
                    String height = retriever.extractMetadata(MediaMetadataRetriever.METADATA_KEY_VIDEO_HEIGHT);
                    if (width == null || height == null || Integer.parseInt(width) > 4096
                            || Integer.parseInt(height) > 4096) throw new IOException("不支持该视频尺寸");
                    Bitmap frame = retriever.getScaledFrameAtTime(0,
                            MediaMetadataRetriever.OPTION_CLOSEST_SYNC, 512, 512);
                    if (frame == null) throw new IOException("无法解码此视频");
                    try (FileOutputStream output = new FileOutputStream(preview)) {
                        if (!frame.compress(Bitmap.CompressFormat.PNG, 100, output))
                            throw new IOException("无法生成预览");
                    } finally { frame.recycle(); }
                }
            } else {
                BitmapFactory.Options options = new BitmapFactory.Options();
                options.inJustDecodeBounds = true;
                BitmapFactory.decodeFile(media.getAbsolutePath(), options);
                if (options.outWidth <= 0 || options.outHeight <= 0
                        || (long) options.outWidth * options.outHeight > 16000000)
                    throw new IOException("无法读取图片或图片过大");
                try (InputStream input = new FileInputStream(media);
                        OutputStream output = new FileOutputStream(preview)) { input.transferTo(output); }
            }
            File archive = new File(directory, "wallpaper.mrc");
            String body = video
                    ? "<Video name=\"personalVideo\" w=\"#view_width\" h=\"#view_height\" loop=\"1\" scaleMode=\"2\" path=\""
                        + media.getAbsolutePath() + "\"/>"
                        + "<ExternalCommands><Trigger action=\"init,resume\"><VideoCommand target=\"personalVideo\" command=\"setVolume\" volume=\"0\"/><VideoCommand target=\"personalVideo\" command=\"play\"/></Trigger><Trigger action=\"pause\"><VideoCommand target=\"personalVideo\" command=\"pause\"/></Trigger></ExternalCommands>"
                    : "<Image src=\"image.png\" w=\"#view_width\" h=\"#view_height\"/>";
            String xml = "<Widget frameRate=\"0\" scaleByDensity=\"false\" screenWidth=\"1080\" version=\"2\">" + body + "</Widget>";
            try (ZipOutputStream zip = new ZipOutputStream(new FileOutputStream(archive))) {
                zip.putNextEntry(new ZipEntry("manifest.xml"));
                zip.write(xml.getBytes(StandardCharsets.UTF_8));
                zip.closeEntry();
                if (!video) {
                    zip.putNextEntry(new ZipEntry("image.png"));
                    try (InputStream input = new FileInputStream(media)) { input.transferTo(zip); }
                    zip.closeEntry();
                }
            }
            // Once handed to the OEM asynchronous queues, preserve these files
            // even if confirmation fails; the queued operation can still run.
            published = true;
            publish(archive);
            if (!RearPersonalization.prefs(getContext()).edit().putString("media",
                    video ? "自选视频（静音循环）" : "自选图片").commit())
                throw new IOException("背屏配置已提交，但素材说明保存失败");
            return state();
        } finally {
            if (!published) delete(directory);
        }
    }

    private static void delete(File directory) {
        File[] children = directory.listFiles();
        if (children != null) for (File file : children) file.delete();
        directory.delete();
    }

    private void publish(File archive) throws Exception {
        AtomicReference<Exception> error = new AtomicReference<>();
        CountDownLatch done = new CountDownLatch(1);
        new Handler(Looper.getMainLooper()).post(() -> {
            try {
                Object persistence = Class.forName("k2.L").getField("a").get(null);
                List<?> original = (List<?>) persistence.getClass().getMethod("e", boolean.class)
                        .invoke(persistence, false);
                Class<?> widget = Class.forName("x2.a");
                ArrayList<Object> items = new ArrayList<>();
                int selectedId = archive == null ? -1 : archive.getAbsolutePath().hashCode();
                if (archive != null) {
                    Bundle attributes = new Bundle();
                    attributes.putString("snapshotPath", new File(archive.getParentFile(), "preview.png").getAbsolutePath());
                    attributes.putBoolean("pixelos_personalization", true);
                    attributes.putString("title", "自选壁纸");
                    attributes.putString("resName", "自选壁纸");
                    items.add(widget.getConstructor(int.class, int.class, int.class, Bundle.class,
                            boolean.class, String.class, String.class, android.content.ComponentName.class,
                            Bundle.class, Bundle.class, boolean.class, boolean.class, int.class)
                            .newInstance(selectedId, 0, 1, attributes, false, archive.getAbsolutePath(),
                                    null, null, null, null, false, false, -1));
                }
                for (Object item : original) {
                    Bundle attributes = (Bundle) widget.getField("d").get(item);
                    if (attributes == null || !attributes.getBoolean("pixelos_personalization")) items.add(item);
                }
                if (items.isEmpty()) {
                    items.addAll((List<?>) persistence.getClass().getMethod("e", boolean.class)
                            .invoke(persistence, true));
                }
                Object manager = Class.forName("E2.z").getField("a").get(null);
                manager.getClass().getMethod("K", List.class, int.class, int.class)
                        .invoke(manager, items, 1, archive == null ? -1 : 0);
                // K posts both the panel update and the configuration write.
                // Queue confirmation behind the original persistence task. This
                // confirms disk state, not rendering or first-frame success.
                Handler persistenceHandler = (Handler) persistence.getClass().getField("a")
                        .get(persistence);
                if (!persistenceHandler.post(() -> {
                    try {
                        JSONArray widgets = readWidgets();
                        boolean found = false;
                        for (int i = 0; i < widgets.length(); i++) {
                            JSONObject item = widgets.getJSONObject(i);
                            JSONObject attributes = item.optJSONObject("extra");
                            if (archive == null) {
                                if (attributes != null && attributes.optBoolean("pixelos_personalization"))
                                    throw new IOException("系统原有内容尚未保存，旧素材已保留");
                            } else if (archive.getAbsolutePath().equals(item.optString("path"))) {
                                found = true;
                            }
                        }
                        if (archive != null && !found)
                            throw new IOException("背屏配置保存未确认，素材已保留");
                    } catch (Exception failure) { error.set(failure); }
                    finally { done.countDown(); }
                })) throw new IOException("背屏配置保存队列不可用");
            } catch (Exception failure) { error.set(failure); done.countDown(); }
        });
        // A timeout is not cancellation: the queued work may still commit, so
        // importMedia keeps the handed-off files until the next process startup.
        try {
            if (!done.await(30, TimeUnit.SECONDS))
                throw new IOException("背屏配置处理超时，素材已保留，请稍后检查");
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            throw new IOException("背屏配置等待中断，素材已保留", e);
        }
        if (error.get() != null) throw error.get();
    }

    @Override public Cursor query(Uri uri, String[] projection, String selection,
            String[] args, String order) { throw new UnsupportedOperationException(); }
    @Override public String getType(Uri uri) { return null; }
    @Override public Uri insert(Uri uri, ContentValues values) { throw new UnsupportedOperationException(); }
    @Override public int delete(Uri uri, String selection, String[] args) { throw new UnsupportedOperationException(); }
    @Override public int update(Uri uri, ContentValues values, String selection, String[] args) { throw new UnsupportedOperationException(); }
}
