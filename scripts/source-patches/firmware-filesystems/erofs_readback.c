// SPDX-License-Identifier: MIT
// Read metadata and bytes directly from EROFS. Never mount or extract the image.
#define _GNU_SOURCE
#include <errno.h>
#include <fcntl.h>
#include <inttypes.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include "erofs/config.h"
#include "erofs/dir.h"
#include "erofs/internal.h"
#include "erofs/io.h"
#include "erofs/xattr.h"

struct walk {
    struct erofs_dir_context ctx;
    const char *path;
    unsigned int depth;
    struct erofs_sb_info *other;
};

static void die(const char *message, int error)
{
    fprintf(stderr, "erofs_readback: %s (%d)\n", message, error);
    exit(EXIT_FAILURE);
}

static void *allocate(size_t size)
{
    void *p = malloc(size ? size : 1);
    if (!p) die("out of memory", errno);
    return p;
}

static void hex(const void *data, size_t size)
{
    const unsigned char *p = data;
    putchar('"');
    for (size_t i = 0; i < size; ++i) printf("%02x", p[i]);
    putchar('"');
}

static void open_image(struct erofs_sb_info *sbi, const char *path)
{
    int err = erofs_dev_open(sbi, path, O_RDONLY);
    if (err) die("open image", err);
    err = erofs_read_superblock(sbi);
    if (err) die("read superblock", err);
    // A derivative must be independently readable, with no external blob device.
    if (sbi->extra_devices) die("external device is unsupported", -EINVAL);
}

static void close_image(struct erofs_sb_info *sbi)
{
    erofs_put_super(sbi);
    erofs_dev_close(sbi);
}

static unsigned int check_raw_xattr(struct erofs_inode *inode, uint64_t position,
                                    size_t available, unsigned int *count)
{
    struct erofs_xattr_entry entry;
    if (available < sizeof(entry)) die("truncated raw xattr entry", -EIO);
    int err = erofs_dev_read(inode->sbi, 0, &entry, position, sizeof(entry));
    if (err < 0) die("read raw xattr entry", err);
    unsigned int size = erofs_xattr_entry_size(&entry);
    if (size > available) die("raw xattr exceeds inode", -EIO);
    unsigned int index = entry.e_name_index;
    if (index & EROFS_XATTR_LONG_PREFIX) {
        unsigned int prefix = index & EROFS_XATTR_LONG_PREFIX_MASK;
        if (prefix >= inode->sbi->xattr_prefix_count) die("unknown xattr prefix", -EINVAL);
        index = inode->sbi->xattr_prefixes[prefix].prefix->base_index;
        if (!index) die("hidden xattr prefix is unsupported", -EINVAL);
    }
    if (!index) {
        // The on-disk padding entry has no name and only zero-valued bytes.
        // Other index-zero entries are hidden from erofs_listxattr; refusing them
        // prevents a falsely successful rebuild that silently loses hidden EAs.
        if (entry.e_name_len) die("hidden xattr is unsupported", -EINVAL);
        unsigned int value_size = le16_to_cpu(entry.e_value_size);
        unsigned char *value = allocate(value_size);
        err = erofs_dev_read(inode->sbi, 0, value, position + sizeof(entry), value_size);
        if (err < 0) die("read raw xattr padding", err);
        for (unsigned int i = 0; i < value_size; ++i)
            if (value[i]) die("nonzero hidden xattr is unsupported", -EINVAL);
        free(value);
    } else {
        if (index > EROFS_XATTR_INDEX_SECURITY || index == EROFS_XATTR_INDEX_LUSTRE)
            die("unknown xattr namespace", -EINVAL);
        ++*count;
    }
    return size;
}

static void check_raw_xattrs(struct erofs_inode *inode, unsigned int listed)
{
    unsigned int count = 0;
    if (inode->xattr_isize) {
        unsigned int offset = sizeof(struct erofs_xattr_ibody_header) +
                              inode->xattr_shared_count * sizeof(__le32);
        if (offset > inode->xattr_isize) die("raw xattr array exceeds inode", -EIO);
        while (offset < inode->xattr_isize)
            offset += check_raw_xattr(inode, erofs_iloc(inode) + inode->inode_isize + offset,
                                      inode->xattr_isize - offset, &count);
        for (unsigned int i = 0; i < inode->xattr_shared_count; ++i)
            check_raw_xattr(inode, erofs_pos(inode->sbi, inode->sbi->xattr_blkaddr) +
                            (uint64_t)inode->xattr_shared_xattrs[i] * sizeof(__le32),
                            sizeof(struct erofs_xattr_entry) + UINT8_MAX + UINT16_MAX + 3,
                            &count);
    }
    if (count != listed) die("raw xattr inventory differs from listed names", -EIO);
}

static void emit_inode(struct erofs_inode *inode, const char *path)
{
    printf("{\"path_hex\":");
    hex(path, strlen(path));
    printf(",\"nid\":%" PRIu64 ",\"mode\":%u,\"uid\":%u,\"gid\":%u,"
           "\"size\":%" PRIu64 ",\"mtime\":%" PRIu64 ",\"mtime_nsec\":%u,"
           "\"nlink\":%u,\"rdev\":%u,\"xattrs\":[",
           (uint64_t)inode->nid, inode->i_mode, inode->i_uid, inode->i_gid,
           (uint64_t)inode->i_size, (uint64_t)inode->i_mtime, inode->i_mtime_nsec,
           inode->i_nlink, S_ISCHR(inode->i_mode) || S_ISBLK(inode->i_mode) ?
           inode->u.i_rdev : 0);
    int size = erofs_listxattr(inode, NULL, 0);
    if (size < 0) die("list xattr size", size);
    char *names = allocate(size);
    if (erofs_listxattr(inode, names, size) != size) die("list xattrs", -EIO);
    unsigned int listed = 0;
    for (int offset = 0; offset < size;) {
        char *name = names + offset;
        size_t length = strnlen(name, size - offset);
        if (!length || length == (size_t)(size - offset)) die("xattr name", -EIO);
        int value_size = erofs_getxattr(inode, name, NULL, 0);
        if (value_size < 0) die("get xattr size", value_size);
        char *value = allocate(value_size);
        if (erofs_getxattr(inode, name, value, value_size) != value_size)
            die("get xattr", -EIO);
        if (offset) putchar(',');
        putchar('['); hex(name, length); putchar(','); hex(value, value_size); putchar(']');
        free(value);
        offset += length + 1;
        ++listed;
    }
    check_raw_xattrs(inode, listed);
    free(names);
    puts("]}");
}

static void compare_content(struct erofs_inode *inode, struct erofs_sb_info *other,
                            const char *path)
{
    struct erofs_inode candidate = { .sbi = other };
    int err = erofs_ilookup(path[0] ? path : "/", &candidate);
    if (err) die(path, err);
    if (candidate.i_mode != inode->i_mode || candidate.i_size != inode->i_size)
        die(path, -EINVAL);
    unsigned char a[65536], b[65536];
    for (uint64_t pos = 0; pos < inode->i_size;) {
        size_t count = inode->i_size - pos > sizeof(a) ? sizeof(a) : inode->i_size - pos;
        if ((err = erofs_pread(inode, (char *)a, count, pos)) ||
            (err = erofs_pread(&candidate, (char *)b, count, pos))) die("read inode data", err);
        if (memcmp(a, b, count)) die(path, -EILSEQ);
        pos += count;
    }
    free(candidate.xattr_shared_xattrs);
}

// The Python contract verifies the complete managed fstab and its four exact
// suffix changes. This narrow data-only command still compares every other file.
static bool managed_fstab_update;
static bool managed_policy_update;
static bool managed_notice_update;

static void visit(struct erofs_inode *inode, const char *path, unsigned int depth,
                  struct erofs_sb_info *other);

static int visit_child(struct erofs_dir_context *ctx)
{
    struct walk *walk = (struct walk *)ctx;
    if (ctx->dot_dotdot) return 0;
    if (!ctx->de_namelen || memchr(ctx->dname, '/', ctx->de_namelen) ||
        memchr(ctx->dname, '\0', ctx->de_namelen)) die("invalid directory name", -EIO);
    char *path;
    if (asprintf(&path, "%s%s%.*s", walk->path, walk->path[0] ? "/" : "",
                 ctx->de_namelen, ctx->dname) < 0) die("path allocation", errno);
    struct erofs_inode child = { .sbi = ctx->dir->sbi, .nid = ctx->de_nid };
    int err = erofs_read_inode_from_disk(&child);
    if (err) die(path, err);
    visit(&child, path, walk->depth + 1, walk->other);
    free(child.xattr_shared_xattrs);
    free(path);
    return 0;
}

static void visit(struct erofs_inode *inode, const char *path, unsigned int depth,
                  struct erofs_sb_info *other)
{
    // Fail instead of following corrupt directory cycles indefinitely.
    if (depth > 256) die("directory nesting exceeds 256", -ELOOP);
    if (other) {
        if ((S_ISREG(inode->i_mode) || S_ISLNK(inode->i_mode)) &&
            !(managed_fstab_update && !strcmp(path, "etc/fstab.qcom")) &&
            !(managed_notice_update && !strcmp(path, "etc/NOTICE.xml.gz")) &&
            !(managed_policy_update && (!strcmp(path, "etc/selinux/vendor_sepolicy.cil") ||
                                        !strcmp(path, "etc/selinux/plat_pub_versioned.cil"))))
            compare_content(inode, other, path);
    } else {
        emit_inode(inode, path);
    }
    if (S_ISDIR(inode->i_mode)) {
        struct walk walk = { .ctx = { .dir = inode, .cb = visit_child },
                             .path = path, .depth = depth, .other = other };
        int err = erofs_iterate_dir(&walk.ctx, true);
        if (err) die("iterate directory", err);
    }
}

int main(int argc, char **argv)
{
    const bool compare = argc >= 2 &&
            (!strcmp(argv[1], "compare-data") ||
             !strcmp(argv[1], "compare-data-fstab-update") ||
             !strcmp(argv[1], "compare-data-policy-update") ||
             !strcmp(argv[1], "compare-data-managed-update"));
    // Python verifies the merged NOTICE against both complete source documents.
    // No other path or unknown command can select this narrowly scoped mode.
    if (compare && argc == 5 && !strcmp(argv[4], "--notice")) {
        managed_notice_update = true;
        --argc;
    }
    if (argc < 3 || ((strcmp(argv[1], "inventory") || argc != 3) &&
                    (strcmp(argv[1], "super") || argc != 3) &&
                    (strcmp(argv[1], "compare-data") || argc != 4) &&
                    (strcmp(argv[1], "compare-data-fstab-update") || argc != 4) &&
                    (strcmp(argv[1], "compare-data-policy-update") || argc != 4) &&
                    (strcmp(argv[1], "compare-data-managed-update") || argc != 4) &&
                    (strcmp(argv[1], "cat") || argc != 4))) {
        fprintf(stderr, "usage: %s inventory IMAGE | super IMAGE | compare-data OLD NEW | cat IMAGE PATH\n",
                argv[0]);
        return EXIT_FAILURE;
    }
    erofs_init_configure();
    cfg.c_dbg_lvl = -1;
    struct erofs_sb_info source = {0}, other = {0};
    open_image(&source, argv[2]);
    struct erofs_inode root = { .sbi = &source, .nid = source.root_nid };
    int err = erofs_read_inode_from_disk(&root);
    if (err) die("read root inode", err);
    if (!strcmp(argv[1], "super")) {
        printf("{\"block_size\":%u,\"blocks\":%" PRIu64 ",\"build_time\":%" PRIu64 ","
               "\"feature_compat\":%u,\"feature_incompat\":%u,\"uuid\":",
               erofs_blksiz(&source), source.primarydevice_blocks,
               (uint64_t)source.build_time,
               source.feature_compat, source.feature_incompat);
        hex(source.uuid, sizeof(source.uuid));
        printf(",\"volume_hex\":"); hex(source.volume_name, sizeof(source.volume_name));
        puts("}");
    } else if (!strcmp(argv[1], "cat")) {
        struct erofs_inode inode = { .sbi = &source };
        err = erofs_ilookup(argv[3], &inode);
        if (err) die("lookup file", err);
        if (!S_ISREG(inode.i_mode) && !S_ISLNK(inode.i_mode)) die("not a file", -EINVAL);
        unsigned char buffer[65536];
        for (uint64_t pos = 0; pos < inode.i_size;) {
            size_t count = inode.i_size - pos > sizeof(buffer) ? sizeof(buffer) : inode.i_size - pos;
            if ((err = erofs_pread(&inode, (char *)buffer, count, pos))) die("read file", err);
            if (fwrite(buffer, 1, count, stdout) != count) die("write data", errno);
            pos += count;
        }
        free(inode.xattr_shared_xattrs);
    } else if (!strcmp(argv[1], "compare-data") ||
               !strcmp(argv[1], "compare-data-fstab-update") ||
               !strcmp(argv[1], "compare-data-policy-update") ||
               !strcmp(argv[1], "compare-data-managed-update")) {
        managed_fstab_update = !strcmp(argv[1], "compare-data-fstab-update") ||
                               !strcmp(argv[1], "compare-data-managed-update");
        managed_policy_update = !strcmp(argv[1], "compare-data-policy-update") ||
                                !strcmp(argv[1], "compare-data-managed-update");
        open_image(&other, argv[3]);
        visit(&root, "", 0, &other);
        close_image(&other);
    } else {
        visit(&root, "", 0, NULL);
    }
    free(root.xattr_shared_xattrs);
    close_image(&source);
    erofs_exit_configure();
    if (fflush(stdout) || ferror(stdout)) die("write output", errno);
    return EXIT_SUCCESS;
}
