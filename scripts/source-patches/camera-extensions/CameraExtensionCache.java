// SPDX-License-Identifier: Apache-2.0
import java.io.*;
import java.nio.file.*;
import java.util.zip.*;
import org.objectweb.asm.*;

/** Specialize the pinned CameraX AAR's global extension cache key before R8. */
public final class CameraExtensionCache {
    private static final String TARGET =
            "androidx/camera/camera2/pipe/compat/Camera2MetadataCache.class";
    private static byte[] patch(byte[] data) {
        ClassReader reader = new ClassReader(data);
        if (!(reader.getClassName() + ".class").equals(TARGET)) {
            throw new IllegalArgumentException("Unexpected cache class identity");
        }
        ClassWriter writer = new ClassWriter(reader, ClassWriter.COMPUTE_MAXS);
        int[] changes = new int[3];
        reader.accept(new ClassVisitor(Opcodes.ASM9, writer) {
            @Override public MethodVisitor visitMethod(int access, String name, String desc,
                    String signature, String[] exceptions) {
                MethodVisitor next = super.visitMethod(access, name, desc, signature, exceptions);
                if (!name.equals("awaitCameraExtensionMetadata-0r8Bogc") || !desc.equals(
                        "(Ljava/lang/String;I)Landroidx/camera/camera2/pipe/CameraExtensionMetadata;")) {
                    return next;
                }
                return new MethodVisitor(Opcodes.ASM9, next) {
                    private void key() {
                        super.visitVarInsn(Opcodes.ILOAD, 2);
                        super.visitMethodInsn(Opcodes.INVOKESTATIC, "java/lang/Integer", "valueOf",
                                "(I)Ljava/lang/Integer;", false);
                        super.visitMethodInsn(Opcodes.INVOKESTATIC, "android/util/Pair", "create",
                                "(Ljava/lang/Object;Ljava/lang/Object;)Landroid/util/Pair;", false);
                    }
                    @Override public void visitMethodInsn(int opcode, String owner, String method,
                            String descriptor, boolean itf) {
                        if (owner.equals("android/util/Pair") && method.equals("create")) {
                            changes[2]++;
                        }
                        if (opcode == Opcodes.INVOKEVIRTUAL
                                && owner.equals("android/util/ArrayMap") && method.equals("get")
                                && descriptor.equals("(Ljava/lang/Object;)Ljava/lang/Object;")) {
                            key();
                            changes[0]++;
                        } else if (opcode == Opcodes.INVOKEINTERFACE && owner.equals("java/util/Map") && method.equals("put")
                                && descriptor.equals(
                                        "(Ljava/lang/Object;Ljava/lang/Object;)Ljava/lang/Object;")) {
                            super.visitInsn(Opcodes.SWAP);
                            key();
                            super.visitInsn(Opcodes.SWAP);
                            changes[1]++;
                        }
                        super.visitMethodInsn(opcode, owner, method, descriptor, itf);
                    }
                };
            }
        }, 0);
        if (changes[0] != 1 || changes[1] != 1 || changes[2] != 0) {
            throw new IllegalArgumentException("Unexpected pinned cache call sites");
        }
        return writer.toByteArray();
    }
    private static byte[] rewrite(byte[] bytes, boolean aar) throws IOException {
        ByteArrayOutputStream output = new ByteArrayOutputStream();
        int changed = 0;
        try (ZipInputStream in = new ZipInputStream(new ByteArrayInputStream(bytes));
                ZipOutputStream out = new ZipOutputStream(output)) {
            ZipEntry entry;
            while ((entry = in.getNextEntry()) != null) {
                byte[] data = in.readAllBytes();
                if (entry.getName().equals(aar ? "classes.jar" : TARGET)) {
                    data = aar ? rewrite(data, false) : patch(data);
                    changed++;
                }
                ZipEntry copy = new ZipEntry(entry.getName());
                copy.setTime(0);
                out.putNextEntry(copy);
                out.write(data);
                out.closeEntry();
            }
        }
        if (changed != 1) throw new IllegalArgumentException("Missing or duplicate cache input");
        return output.toByteArray();
    }
    public static void main(String[] args) throws IOException {
        if (args.length != 2) throw new IllegalArgumentException("INPUT_AAR OUTPUT_AAR");
        Files.write(Path.of(args[1]), rewrite(Files.readAllBytes(Path.of(args[0])), true));
    }
}
