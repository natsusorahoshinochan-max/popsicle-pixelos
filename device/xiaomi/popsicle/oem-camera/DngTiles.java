/* SPDX-License-Identifier: Apache-2.0 */
package com.android.camera;

import java.io.IOException;
import java.io.OutputStream;
import java.nio.ByteBuffer;
import java.nio.ByteOrder;
import java.util.Arrays;
import java.util.Map;
import java.util.TreeMap;

/** OS4 RAW16 lossless-JPEG tile envelope. No image decoding or requantization. */
public final class DngTiles {
    public final int width;
    public final int height;
    private final int compressedSize;
    private final int tileWidth;
    private final int tileHeight;
    private final int[] lengths;

    public DngTiles(byte[] parameters, byte[] pixels) throws IOException {
        require(parameters != null && parameters.length == 604, "Missing OEM compression parameters");
        ByteBuffer p = ByteBuffer.wrap(parameters).order(ByteOrder.LITTLE_ENDIAN);
        int format = p.getInt();
        width = p.getInt();
        height = p.getInt();
        compressedSize = p.getInt();
        int compressed = p.getInt();
        int columns = p.getInt();
        int rows = p.getInt();
        // tagCompressWriter in the matching OS4 binary uses an 8 by 8 grid.
        require(format == 32 && compressed == 1 && columns == 8 && rows == 8,
                "Unsupported OEM RAW compression layout");
        require(width > 0 && height > 0 && (long) width * height <= 50331648
                && width % 16 == 0 && height % 8 == 0, "Invalid compressed RAW dimensions");
        require(pixels != null && compressedSize > 0 && compressedSize <= pixels.length,
                "Truncated compressed RAW payload");
        tileWidth = width / columns;
        tileHeight = height / rows;
        lengths = new int[columns * rows];
        long offset = 0;
        for (int i = 0; i < lengths.length; i++) {
            lengths[i] = p.getInt();
            require(lengths[i] >= 4 && offset + lengths[i] <= compressedSize,
                    "Invalid JPEG tile length");
            checkJpeg(pixels, (int) offset, lengths[i]);
            offset += lengths[i];
        }
        require(offset == compressedSize, "Compressed size does not match tile lengths");
    }

    private void checkJpeg(byte[] data, int start, int length) throws IOException {
        int end = start + length;
        require(u8(data[start]) == 255 && u8(data[start + 1]) == 216
                && u8(data[end - 2]) == 255 && u8(data[end - 1]) == 217,
                "JPEG tile missing SOI/EOI");
        boolean frame = false;
        for (int pos = start + 2; pos + 4 <= end;) {
            require(u8(data[pos++]) == 255, "Invalid JPEG marker");
            int marker = u8(data[pos++]);
            int count = (u8(data[pos]) << 8) | u8(data[pos + 1]);
            require(count >= 2 && pos + count <= end, "Truncated JPEG marker");
            if (marker == 0xc3) {
                require(count == 14 && u8(data[pos + 2]) == 16
                        && ((u8(data[pos + 3]) << 8) | u8(data[pos + 4])) == tileHeight
                        && ((u8(data[pos + 5]) << 8) | u8(data[pos + 6])) * 2 == tileWidth
                        && u8(data[pos + 7]) == 2
                        && u8(data[pos + 9]) == 0x11 && u8(data[pos + 12]) == 0x11,
                        "Unsupported lossless JPEG frame");
                frame = true;
            } else if (marker == 0xda) {
                require(frame, "Lossless JPEG frame missing");
                return;
            } else {
                require(marker == 0xc4 || marker == 0xdd || marker == 0xfe
                        || (marker >= 0xe0 && marker <= 0xef), "Unsupported JPEG coding marker");
            }
            pos += count;
        }
        throw new IOException("JPEG scan missing");
    }

    /** Relocate the main IFD and thumbnail strips, retaining all other template tags. */
    public void write(byte[] template, int size, byte[] pixels, byte[] awbFrameParams,
            OutputStream out) throws IOException {
        byte[] balance = whiteBalanceTags(awbFrameParams);
        require(size >= 8 && template[0] == 'I' && template[1] == 'I', "Expected platform LE TIFF");
        ByteBuffer source = ByteBuffer.wrap(template, 0, size).order(ByteOrder.LITTLE_ENDIAN);
        require(source.getShort(2) == 42, "Invalid TIFF header");
        int ifd = source.getInt(4);
        TreeMap<Integer, byte[]> entries = entries(source, ifd);
        require(scalar(source, entries.get(256)) == width
                && scalar(source, entries.get(257)) == height
                && scalar(source, entries.get(258)) == 16
                && scalar(source, entries.get(262)) == 32803
                && scalar(source, entries.get(277)) == 1,
                "Template is not matching RAW16 CFA");
        int[] oldOffsets = values(source, entries.get(273));
        require(oldOffsets.length > 0, "Template has no RAW strips");
        int prefixSize = Arrays.stream(oldOffsets).min().getAsInt();
        require(prefixSize >= 8 && prefixSize <= size, "Invalid TIFF metadata extent");
        byte[] prefix = Arrays.copyOf(template, prefixSize);
        ByteBuffer header = ByteBuffer.wrap(prefix).order(ByteOrder.LITTLE_ENDIAN);
        entries.remove(273);
        entries.remove(278);
        entries.remove(279);
        entries.put(259, entry(259, 3, 1, 7));
        entries.put(322, entry(322, 4, 1, tileWidth));
        entries.put(323, entry(323, 4, 1, tileHeight));
        entries.put(324, entry(324, 4, lengths.length, 0));
        entries.put(325, entry(325, 4, lengths.length, 0));
        entries.put(50727, entry(50727, 5, 3, 0)); // AnalogBalance
        if (awbFrameParams != null) entries.put(50728, entry(50728, 5, 3, 0));
        int newIfd = (prefixSize + 3) & ~3;
        int tableSize = 2 + entries.size() * 12 + 4;
        int arrays = (newIfd + tableSize + 3) & ~3;
        int balanceOffset = arrays + lengths.length * 8;
        int payloadStart = balanceOffset + balance.length;
        entries.put(50727, entry(50727, 5, 3, balanceOffset));
        if (awbFrameParams != null) entries.put(50728, entry(50728, 5, 3, balanceOffset + 24));
        entries.put(324, entry(324, 4, lengths.length, arrays));
        entries.put(325, entry(325, 4, lengths.length, arrays + lengths.length * 4));
        header.putInt(4, newIfd);
        int[] previews = entries.containsKey(330) ? values(source, entries.get(330)) : new int[0];
        require(previews.length <= 1, "Unexpected platform thumbnail graph");
        int[] previewOffsets = new int[0];
        int[] previewLengths = new int[0];
        if (previews.length == 1) {
            TreeMap<Integer, byte[]> thumbnail = entries(source, previews[0]);
            previewOffsets = values(source, thumbnail.get(273));
            previewLengths = values(source, thumbnail.get(279));
            require(previewOffsets.length == previewLengths.length, "Invalid thumbnail strips");
            int position = payloadStart + compressedSize;
            int location = valueLocation(source, previews[0], 273);
            require(location >= 0 && (long) location + previewOffsets.length * 4 <= prefix.length,
                    "Thumbnail offset table outside header");
            for (int i = 0; i < previewOffsets.length; i++) {
                require(previewOffsets[i] >= 0 && previewLengths[i] >= 0
                        && (long) previewOffsets[i] + previewLengths[i] <= size,
                        "Thumbnail strip outside template");
                header.putInt(location + 4 * i, position);
                position += previewLengths[i];
            }
        }
        ByteBuffer extra = ByteBuffer.allocate(payloadStart - prefixSize).order(ByteOrder.LITTLE_ENDIAN);
        extra.position(newIfd - prefixSize);
        extra.putShort((short) entries.size());
        for (Map.Entry<Integer, byte[]> tag : entries.entrySet()) extra.put(tag.getValue());
        // The platform thumbnail is a SubIFD, not a next-IFD link.
        require(source.getInt(ifd + 2 + Short.toUnsignedInt(source.getShort(ifd)) * 12) == 0,
                "Unexpected next IFD");
        extra.putInt(0);
        extra.position(arrays - prefixSize);
        int offset = payloadStart;
        for (int length : lengths) { extra.putInt(offset); offset += length; }
        for (int length : lengths) extra.putInt(length);
        extra.put(balance);
        out.write(prefix);
        out.write(extra.array());
        out.write(pixels, 0, compressedSize);
        for (int i = 0; i < previewOffsets.length; i++) {
            out.write(template, previewOffsets[i], previewLengths[i]);
        }
    }

    private static byte[] whiteBalanceTags(byte[] awbFrameParams) throws IOException {
        // Matching OS4 DngCreator: awbFrameParams contains three LE doubles.
        // The algorithm has already applied these gains to the mosaic. Record
        // them as AnalogBalance and use a unit AsShotNeutral, not another AWB.
        // If the tag is absent, OEM fallback is unit balance + original neutral.
        ByteBuffer tags = ByteBuffer.allocate(awbFrameParams == null ? 24 : 48)
                .order(ByteOrder.LITTLE_ENDIAN);
        ByteBuffer gains = null;
        if (awbFrameParams != null) {
            require(awbFrameParams.length == 24, "Invalid OEM AWB parameter length");
            gains = ByteBuffer.wrap(awbFrameParams).order(ByteOrder.LITTLE_ENDIAN);
        }
        for (int i = 0; i < 3; i++) {
            if (gains == null) {
                tags.putInt(1).putInt(1);
                continue;
            }
            double gain = gains.getDouble();
            double scaled = gain * 100000000.0;
            require(Double.isFinite(scaled) && scaled >= 1 && scaled < 4294967296.0,
                    "Invalid OEM AWB gain");
            long numerator = (long) scaled;
            long denominator = 100000000L;
            long a = numerator, b = denominator;
            while (b != 0) { long remainder = a % b; a = b; b = remainder; }
            tags.putInt((int) (numerator / a)).putInt((int) (denominator / a));
        }
        if (gains != null) {
            for (int i = 0; i < 3; i++) tags.putInt(1).putInt(1);
        }
        return tags.array();
    }

    private static TreeMap<Integer, byte[]> entries(ByteBuffer b, int offset) throws IOException {
        require(offset >= 8 && offset + 2 <= b.limit(), "Invalid IFD offset");
        int count = Short.toUnsignedInt(b.getShort(offset));
        require((long) offset + 2 + count * 12L + 4 <= b.limit(), "Truncated IFD");
        TreeMap<Integer, byte[]> result = new TreeMap<>();
        for (int i = 0; i < count; i++) {
            byte[] entry = new byte[12];
            b.duplicate().position(offset + 2 + i * 12).get(entry);
            int tag = u8(entry[0]) | (u8(entry[1]) << 8);
            require(result.put(tag, entry) == null, "Duplicate TIFF tag");
        }
        return result;
    }

    private static byte[] entry(int tag, int type, int count, int value) {
        return ByteBuffer.allocate(12).order(ByteOrder.LITTLE_ENDIAN)
                .putShort((short) tag).putShort((short) type).putInt(count).putInt(value).array();
    }

    private static int scalar(ByteBuffer b, byte[] entry) throws IOException {
        int[] values = values(b, entry);
        require(values.length == 1, "Expected scalar TIFF value");
        return values[0];
    }

    private static int[] values(ByteBuffer source, byte[] entry) throws IOException {
        require(entry != null, "Required TIFF tag missing");
        ByteBuffer e = ByteBuffer.wrap(entry).order(ByteOrder.LITTLE_ENDIAN);
        int type = Short.toUnsignedInt(e.getShort(2));
        int count = e.getInt(4);
        require((type == 3 || type == 4) && count > 0 && count <= 65536, "Invalid TIFF integer array");
        int bytes = type == 3 ? 2 : 4;
        ByteBuffer b = count * bytes <= 4 ? e : source;
        int start = b == e ? 8 : e.getInt(8);
        require(start >= 0 && (long) start + count * bytes <= b.limit(), "TIFF value out of bounds");
        int[] result = new int[count];
        for (int i = 0; i < count; i++) {
            result[i] = type == 3 ? Short.toUnsignedInt(b.getShort(start + i * 2)) : b.getInt(start + i * 4);
        }
        return result;
    }

    private static int valueLocation(ByteBuffer b, int ifd, int tag) throws IOException {
        int count = Short.toUnsignedInt(b.getShort(ifd));
        for (int i = 0; i < count; i++) {
            int pos = ifd + 2 + i * 12;
            if (Short.toUnsignedInt(b.getShort(pos)) == tag) {
                require(b.getShort(pos + 2) == 4, "Expected LONG offset tag");
                return b.getInt(pos + 4) == 1 ? pos + 8 : b.getInt(pos + 8);
            }
        }
        throw new IOException("Missing strip offset tag");
    }

    private static int u8(byte value) { return value & 255; }
    private static void require(boolean condition, String message) throws IOException {
        if (!condition) throw new IOException(message);
    }
}
