/* SPDX-License-Identifier: Apache-2.0 */
import com.googlecode.d2j.dex.writer.DexFileWriter;
import com.googlecode.d2j.reader.DexFileReader;
import com.googlecode.d2j.visitors.DexClassVisitor;
import com.googlecode.d2j.visitors.DexFileVisitor;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.HashSet;
import java.util.Set;

/** Copies only the two original SDK classes, retaining their method bodies and annotations. */
public final class ExtractMiSight {
    public static void main(String[] args) throws Exception {
        Set<String> wanted = Set.of("Lcom/miui/misight/MiEvent;", "Lcom/miui/misight/MiSight;");
        Set<String> found = new HashSet<>();
        DexFileWriter writer = new DexFileWriter();
        new DexFileReader(Path.of(args[0])).accept(new DexFileVisitor(writer) {
            @Override
            public DexClassVisitor visit(int access, String name, String parent, String[] interfaces) {
                if (!wanted.contains(name)) return null;
                if (!found.add(name)) throw new IllegalStateException("Duplicate class: " + name);
                return super.visit(access, name, parent, interfaces);
            }
        });
        if (!found.equals(wanted)) throw new IllegalStateException("Missing SDK classes: " + found);
        byte[] dex = writer.toByteArray();
        if (!new HashSet<>(new DexFileReader(dex).getClassNames()).equals(wanted)) {
            throw new IllegalStateException("Unexpected output classes");
        }
        Files.write(Path.of(args[1]), dex);
        System.out.println("Copied original MiEvent and MiSight: " + dex.length + " bytes");
    }
}
