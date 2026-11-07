/* SPDX-License-Identifier: Apache-2.0 */
import java.nio.ByteBuffer;
import java.nio.ByteOrder;
import java.nio.file.Files;
import java.nio.file.Path;
import java.security.MessageDigest;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.zip.Adler32;

import org.jf.dexlib2.Opcode;
import org.jf.dexlib2.dexbacked.DexBackedDexFile;
import org.jf.dexlib2.dexbacked.instruction.DexBackedInstruction;
import org.jf.dexlib2.iface.instruction.Instruction;
import org.jf.dexlib2.iface.instruction.OffsetInstruction;
import org.jf.dexlib2.iface.instruction.OneRegisterInstruction;
import org.jf.dexlib2.iface.instruction.ReferenceInstruction;
import org.jf.dexlib2.iface.reference.MethodReference;

/** Select the OEM descriptor discovery path in the fixed camera capability constructor. */
class CameraVendorDiscovery {
    private static boolean calls(Instruction instruction, String owner, String name) {
        return instruction instanceof ReferenceInstruction
                && ((ReferenceInstruction) instruction).getReference() instanceof MethodReference
                && ((MethodReference) ((ReferenceInstruction) instruction).getReference())
                        .getDefiningClass().equals(owner)
                && ((MethodReference) ((ReferenceInstruction) instruction).getReference())
                        .getName().equals(name);
    }

    public static void main(String[] args) throws Exception {
        if (args.length != 2) throw new IllegalArgumentException("INPUT_DEX OUTPUT_DEX");
        byte[] source = Files.readAllBytes(Path.of(args[0]));
        DexBackedDexFile dex = new DexBackedDexFile(null, source);
        int patchOffset = -1;
        for (var cls : dex.getClasses()) {
            if (!cls.getType().equals("Lj9/e;")) continue;
            for (var method : cls.getMethods()) {
                if (!method.getName().equals("<init>")
                        || !method.getParameterTypes().toString().equals(
                                "[Landroid/hardware/camera2/CameraCharacteristics;, I]")) continue;
                var instructions = new ArrayList<Instruction>();
                method.getImplementation().getInstructions().forEach(instructions::add);
                for (int i = 0; i + 3 < instructions.size(); i++) {
                    Instruction call = instructions.get(i);
                    if (!calls(call, "LCc/h;", "m")) continue;
                    Instruction result = instructions.get(i + 1);
                    Instruction branch = instructions.get(i + 2);
                    Instruction next = instructions.get(i + 3);
                    if (call.getOpcode() != Opcode.INVOKE_STATIC
                            || result.getOpcode() != Opcode.MOVE_RESULT
                            || branch.getOpcode() != Opcode.IF_EQZ
                            || ((OneRegisterInstruction) result).getRegisterA()
                                != ((OneRegisterInstruction) branch).getRegisterA()
                            || !calls(next, "LDp/b;", "c")) {
                        throw new IllegalArgumentException("Unexpected discovery branch");
                    }
                    int offset = ((DexBackedInstruction) branch).instructionStart;
                    int destination = offset + 2 * ((OffsetInstruction) branch).getCodeOffset();
                    Instruction target = instructions.stream().filter(insn ->
                            ((DexBackedInstruction) insn).instructionStart == destination)
                            .findFirst().orElseThrow();
                    boolean hasDescriptorRead = instructions.subList(i + 3,
                            instructions.indexOf(target)).stream().anyMatch(insn -> calls(insn,
                                    "Landroid/hardware/camera2/impl/CameraMetadataNative;",
                                    "getAllVendorKeys"));
                    if (!calls(target, "Landroid/hardware/camera2/CameraCharacteristics;",
                            "getAvailableCaptureRequestKeys") || !hasDescriptorRead
                            || patchOffset != -1) {
                        throw new IllegalArgumentException("Unexpected discovery consumer");
                    }
                    patchOffset = offset;
                }
            }
        }
        if (patchOffset < 0) throw new IllegalArgumentException("Original constructor not found");
        byte[] output = source.clone();
        // Two NOPs retain all code offsets and enter the existing descriptor enumeration.
        // Q0, w0, metadata values, session checks and all other consumers stay byte-identical.
        Arrays.fill(output, patchOffset, patchOffset + 4, (byte) 0);
        // These are required DEX header fields, not a separate artifact hash audit.
        byte[] signature = MessageDigest.getInstance("SHA-1").digest(
                Arrays.copyOfRange(output, 32, output.length));
        System.arraycopy(signature, 0, output, 12, signature.length);
        Adler32 checksum = new Adler32();
        checksum.update(output, 12, output.length - 12);
        ByteBuffer.wrap(output).order(ByteOrder.LITTLE_ENDIAN).putInt(8, (int) checksum.getValue());
        Files.write(Path.of(args[1]), output);
        System.out.println("Patched one discovery branch at DEX byte " + patchOffset);
    }
}
