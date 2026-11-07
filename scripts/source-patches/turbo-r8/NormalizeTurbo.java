// SPDX-License-Identifier: Apache-2.0
import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.*;
import java.util.jar.*;
import org.objectweb.asm.*;
import org.objectweb.asm.commons.ClassRemapper;
import org.objectweb.asm.commons.Remapper;
import org.objectweb.asm.tree.*;
import org.objectweb.asm.tree.analysis.*;

/** Rebuild frames against real Android classes; never load or execute input classes. */
public final class NormalizeTurbo {
    private final Map<String, ClassReader> types = new HashMap<>();
    private final SortedMap<String, byte[]> program = new TreeMap<>();
    private int verifiedMethods;
    private final Map<String, String> originalNames = new HashMap<>();

    private void names(Path originalTypes) throws IOException {
        for (String name : Files.readAllLines(originalTypes)) {
            if (name.isBlank()) throw new IllegalArgumentException("Empty DEX type");
            String previous = originalNames.putIfAbsent(name.replace('-', '_'), name);
            if (previous != null) throw new IllegalArgumentException("Ambiguous type: " + name);
        }
    }

    private void read(Path jar, boolean input) throws IOException {
        try (JarFile z = new JarFile(jar.toFile())) {
            for (JarEntry e : Collections.list(z.entries())) {
                if (!e.getName().endsWith(".class")) continue;
                byte[] data = z.getInputStream(e).readAllBytes();
                ClassReader r = new ClassReader(data);
                if (!e.getName().equals(r.getClassName() + ".class")) {
                    throw new IllegalArgumentException("Class entry mismatch: " + e.getName());
                }
                if (input) {
                    if (!originalNames.containsKey(r.getClassName().replace('-', '_'))) {
                        throw new IllegalArgumentException("Unexpected converted type: " + r.getClassName());
                    }
                    ClassWriter restored = new ClassWriter(0);
                    r.accept(new ClassRemapper(restored, new Remapper() {
                        @Override public String map(String name) {
                            return originalNames.getOrDefault(name, name);
                        }
                    }), 0);
                    data = restored.toByteArray();
                    r = new ClassReader(data);
                }
                if (input && program.putIfAbsent(r.getClassName(), data) != null) {
                    throw new IllegalArgumentException("Duplicate input: " + r.getClassName());
                }
                types.putIfAbsent(r.getClassName(), r);
            }
        }
    }

    private ClassReader type(String name) {
        ClassReader r = types.get(name);
        if (r == null) throw new IllegalArgumentException("Unresolved hierarchy: " + name);
        return r;
    }

    private boolean assignable(String target, String source) {
        if (target.equals(source)) return true;
        if (source.equals("null")) return true;
        if (source.startsWith("[")) {
            if (Set.of("java/lang/Object", "java/lang/Cloneable", "java/io/Serializable")
                    .contains(target)) return true;
            if (!target.startsWith("[")) return false;
            String a = target.substring(1), b = source.substring(1);
            if (a.length() == 1 || b.length() == 1) return a.equals(b);
            return assignable(internal(a), internal(b));
        }
        if (target.startsWith("[")) return false;
        type(target);
        ClassReader r = type(source);
        if (target.equals("java/lang/Object")) return true;
        if (r.getSuperName() != null && assignable(target, r.getSuperName())) return true;
        for (String itf : r.getInterfaces()) if (assignable(target, itf)) return true;
        return false;
    }

    private static String internal(String descriptor) {
        return descriptor.startsWith("[") ? descriptor
                : descriptor.substring(1, descriptor.length() - 1);
    }

    private String common(String a, String b) {
        if (assignable(a, b)) return a;
        if (assignable(b, a)) return b;
        if (a.startsWith("[") && b.startsWith("[")) {
            String ac = a.substring(1), bc = b.substring(1);
            if (ac.length() != 1 && bc.length() != 1) {
                String c = common(internal(ac), internal(bc));
                return c.startsWith("[") ? "[" + c : "[L" + c + ";";
            }
            return "java/lang/Object";
        }
        if (a.startsWith("[") || b.startsWith("[")) return "java/lang/Object";
        if ((type(a).getAccess() & Opcodes.ACC_INTERFACE) != 0
                || (type(b).getAccess() & Opcodes.ACC_INTERFACE) != 0) {
            return "java/lang/Object";
        }
        do { a = type(a).getSuperName(); } while (a != null && !assignable(a, b));
        if (a == null) throw new IllegalArgumentException("No common ancestor");
        return a;
    }

    private final class Verifier extends SimpleVerifier {
        Verifier() { super(Opcodes.ASM9, null, null, null, false); }
        @Override protected boolean isInterface(Type t) {
            return t.getSort() != Type.ARRAY
                    && (type(t.getInternalName()).getAccess() & Opcodes.ACC_INTERFACE) != 0;
        }
        @Override protected Type getSuperClass(Type t) {
            String s = t.getSort() == Type.ARRAY ? "java/lang/Object"
                    : type(t.getInternalName()).getSuperName();
            return s == null ? null : Type.getObjectType(s);
        }
        @Override protected boolean isAssignableFrom(Type a, Type b) {
            if (a.equals(b)) return true;
            if (a.getSort() < Type.ARRAY || b.getSort() < Type.ARRAY) return false;
            return assignable(a.getInternalName(), b.getInternalName());
        }
        // Same interface-merge semantics as ASM SimpleVerifier, using class headers
        // instead of loading Android classes into the host JVM.
        @Override protected boolean isSubTypeOf(BasicValue value, BasicValue expected) {
            Type a = value.getType(), b = expected.getType();
            if (a == null || b == null) return a == b;
            if (a.equals(b)) return true;
            if (b.getSort() != Type.ARRAY && b.getSort() != Type.OBJECT) return false;
            if (a.equals(Type.getObjectType("null"))) return true;
            int ad = 0, bd = 0;
            if (a.getSort() == Type.ARRAY) {
                ad = a.getDimensions();
                a = a.getElementType();
                if (a.getSort() != Type.OBJECT) {
                    ad--;
                    a = Type.getObjectType("java/lang/Object");
                }
            }
            if (b.getSort() == Type.ARRAY) {
                bd = b.getDimensions();
                b = b.getElementType();
                if (b.getSort() != Type.OBJECT) return false;
            }
            if (ad < bd || a.getSort() != Type.OBJECT) return false;
            if (ad > bd) a = Type.getObjectType("java/lang/Object");
            if (isAssignableFrom(b, a)) return true;
            return isInterface(b) && isAssignableFrom(Type.getObjectType("java/lang/Object"), a);
        }
    }

    private void verify(byte[] data, boolean computeMaxs) throws AnalyzerException {
        ClassNode n = new ClassNode();
        new ClassReader(data).accept(n, 0);
        for (MethodNode m : n.methods) {
            if ((m.access & (Opcodes.ACC_ABSTRACT | Opcodes.ACC_NATIVE)) == 0) {
                try {
                    Analyzer<BasicValue> analyzer = new Analyzer<>(new Verifier());
                    if (computeMaxs) analyzer.analyzeAndComputeMaxs(n.name, m);
                    else analyzer.analyze(n.name, m);
                }
                catch (AnalyzerException e) {
                    throw new AnalyzerException(e.node, n.name + "." + m.name + m.desc, e);
                }
                verifiedMethods++;
            }
            for (AbstractInsnNode i : m.instructions) {
                if (i instanceof LdcInsnNode ldc && ldc.cst instanceof String s
                        && (s.contains("d2j fail") || s.contains("Error processing method"))) {
                    throw new IllegalArgumentException("Converter error body: " + n.name);
                }
            }
        }
    }

    private static byte[] instructions(byte[] data) {
        ClassWriter w = new ClassWriter(0);
        new ClassReader(data).accept(new ClassVisitor(Opcodes.ASM9, w) {
            @Override public MethodVisitor visitMethod(int access, String name,
                    String descriptor, String signature, String[] exceptions) {
                return new MethodVisitor(Opcodes.ASM9,
                        super.visitMethod(access, name, descriptor, signature, exceptions)) {
                    @Override public void visitMaxs(int stack, int locals) { super.visitMaxs(0, 0); }
                };
            }
        }, ClassReader.SKIP_FRAMES | ClassReader.SKIP_DEBUG);
        return w.toByteArray();
    }

    private void write(Path output) throws Exception {
        SortedMap<String, byte[]> result = new TreeMap<>();
        for (var e : program.entrySet()) {
            ClassReader r = new ClassReader(e.getValue());
            if (r.readUnsignedShort(6) < Opcodes.V1_8) {
                throw new IllegalArgumentException("Input below Java 8: " + e.getKey());
            }
            // Resolve every symbolic class reference, not just frame merge points.
            r.accept(new ClassRemapper(new ClassNode(),
                    new Remapper() {
                        @Override public String map(String name) { type(name); return name; }
                    }), ClassReader.SKIP_DEBUG | ClassReader.SKIP_FRAMES);
            // dex2jar also underestimates max_stack in exception handlers. Recompute
            // that metadata before dataflow verification; instructions are unchanged.
            verify(e.getValue(), true);
            ClassWriter w = new ClassWriter(ClassWriter.COMPUTE_FRAMES | ClassWriter.COMPUTE_MAXS) {
                @Override protected String getCommonSuperClass(String a, String b) {
                    return common(a, b);
                }
            };
            r.accept(w, ClassReader.SKIP_FRAMES);
            byte[] normalized = w.toByteArray();
            verify(normalized, false);
            if (!Arrays.equals(instructions(e.getValue()), instructions(normalized))) {
                throw new IllegalArgumentException("Frame computation changed instructions: " + e.getKey());
            }
            result.put(e.getKey(), normalized);
        }
        try (JarOutputStream out = new JarOutputStream(Files.newOutputStream(output))) {
            for (var e : result.entrySet()) {
                JarEntry entry = new JarEntry(e.getKey() + ".class");
                entry.setTime(0);
                out.putNextEntry(entry);
                out.write(e.getValue());
                out.closeEntry();
            }
        }
        System.out.println("PASS classes=" + result.size()
                + " methods_verified_before_and_after=" + verifiedMethods);
    }

    public static void main(String[] args) throws Exception {
        if (args.length < 4) throw new IllegalArgumentException("INPUT OUTPUT ORIGINAL_TYPES CLASSPATH_JAR...");
        NormalizeTurbo tool = new NormalizeTurbo();
        tool.names(Path.of(args[2]));
        tool.read(Path.of(args[0]), true);
        if (!tool.program.keySet().equals(new HashSet<>(tool.originalNames.values()))) {
            throw new IllegalArgumentException("Converted definitions differ from original DEX");
        }
        for (int i = 3; i < args.length; i++) tool.read(Path.of(args[i]), false);
        tool.write(Path.of(args[1]));
    }
}
