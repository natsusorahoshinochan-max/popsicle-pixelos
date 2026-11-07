// SPDX-License-Identifier: Apache-2.0
// Export a kernel policy with the same libsepol used by the PixelOS build.
// This tool never changes the loaded policy.
#include <fcntl.h>
#include <stdio.h>
#include <unistd.h>

#include <sepol/kernel_to_cil.h>
#include <sepol/policydb/policydb.h>

int main(int argc, char **argv) {
    if (argc != 3) {
        fprintf(stderr, "Usage: %s INPUT_BINARY NEW_OUTPUT_CIL\n", argv[0]);
        return 2;
    }

    FILE *input = fopen(argv[1], "rb");
    if (input == NULL) {
        perror("open input policy");
        return 1;
    }
    policydb_t policy;
    if (policydb_init(&policy) != 0) {
        fprintf(stderr, "Cannot initialize policy database\n");
        fclose(input);
        return 1;
    }
    policy_file_t file;
    policy_file_init(&file);
    file.type = PF_USE_STDIO;
    file.fp = input;
    int status = policydb_read(&policy, &file, 0);
    if (fclose(input) != 0) status = -1;
    if (status != 0 || policy.policy_type != POLICY_KERN) {
        fprintf(stderr, "Cannot read a complete kernel policy\n");
        policydb_destroy(&policy);
        return 1;
    }

    int fd = open(argv[2], O_WRONLY | O_CREAT | O_EXCL | O_CLOEXEC, 0600);
    if (fd < 0) {
        perror("create output CIL");
        policydb_destroy(&policy);
        return 1;
    }
    FILE *output = fdopen(fd, "w");
    if (output == NULL) {
        perror("open output stream");
        close(fd);
        unlink(argv[2]);
        policydb_destroy(&policy);
        return 1;
    }
    status = sepol_kernel_policydb_to_cil(output, &policy);
    if (fclose(output) != 0) status = -1;
    unsigned int version = policy.policyvers;
    policydb_destroy(&policy);
    if (status != 0) {
        fprintf(stderr, "Cannot export complete policy CIL\n");
        unlink(argv[2]);
        return 1;
    }
    // Let the caller compile the candidate with this exact binary policy version.
    if (printf("%u\n", version) < 0) return 1;
    return 0;
}
