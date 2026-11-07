#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Package a newly exported PixelOS release with the current three-platform installer."""
import argparse
import errno
import hashlib
import os
from pathlib import Path
import re
import shutil
import subprocess


PACKAGE_NAME = "PixelOS-popsicle-20260930-global-telephony-fix_by_Kanoe"
README = r"""# PixelOS 安装

先备份数据并解锁 Bootloader。首次安装请先完整线刷官方 A16 OS3.0.318.0。

1. 完整解压安装包。
2. 手机进入 Fastboot 模式，通过 USB 连接电脑。
3. 在解压目录打开终端，运行对应命令。

**Windows（PowerShell）**
```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\flash-fastboot_Windows.ps1
```

**macOS**
```sh
bash ./flash-fastboot_macOS.sh
```

**Linux**
```sh
bash ./flash-fastboot_Linux.sh
```

按提示选择清空或保留数据，输入 `yes` 开始安装，完成后手机自动重启。
清空数据会删除内部存储；跨 ROM 安装不保证保留数据可用。
"""


def digest(path):
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def link_or_copy(source, target):
    try:
        os.link(source, target)
    except OSError as error:
        if error.errno != errno.EXDEV:
            raise
        shutil.copy2(source, target)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--flat-package", required=True, type=Path,
                        help="This build's release/generated/fastboot directory")
    parser.add_argument("--tools-dir", "--tools-template", dest="tools_dir", required=True, type=Path,
                        help="Prepared host tools directory from prepare-platform-tools.py")
    parser.add_argument("--name", default=PACKAGE_NAME,
                        help="Package basename; defaults to the historical package name")
    parser.add_argument("--output", required=True, type=Path,
                        help="Parent directory for the named package and tar.gz archive")
    args = parser.parse_args()
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", args.name):
        parser.error("--name must be a basename of 1-128 ASCII letters, digits, dots, underscores or hyphens")
    source = args.flat_package.resolve()
    package = args.output.absolute() / args.name
    archive = package.with_name(package.name + ".tar.gz")
    if package.exists() or archive.exists():
        parser.error("package/archive already exists; choose a new output directory")
    source_sums = dict((name, checksum) for checksum, name in (
        line.split("  ", 1) for line in (source / "SHA256SUMS").read_text().splitlines()))
    rows = [line.split("\t") for line in
            (source / "flash-manifest.tsv").read_text().splitlines()]
    (package / "images").mkdir(parents=True)
    (package / "metadata").mkdir()
    (package / "logs").mkdir()
    checksums = {}
    for row in rows:
        filename = row[1]
        row[1] = "images/" + filename
        link_or_copy(source / filename, package / row[1])
        checksums[row[1]] = source_sums[filename]
    (package / "metadata/flash-manifest.tsv").write_text(
        "".join("\t".join(row) + "\n" for row in rows))
    shutil.copytree(args.tools_dir, package / "tools")
    shutil.copytree(Path(__file__).resolve().parent / "installer", package,
                    dirs_exist_ok=True)
    (package / "README.md").write_text(README)
    for path in sorted(package.rglob("*")):
        if path.is_file():
            name = path.relative_to(package).as_posix()
            if name not in checksums:
                checksums[name] = digest(path)
    (package / "metadata/SHA256SUMS").write_text("".join(
        f"{checksums[name]}  {name}\n" for name in sorted(checksums)))
    subprocess.run(["tar", "--use-compress-program=pigz -p 16",
                    "-cf", str(archive), "-C", str(package.parent),
                    "--", package.name], check=True)
    archive.with_name(archive.name + ".sha256").write_text(
        f"{digest(archive)}  {archive.name}\n")
    print(archive)


if __name__ == "__main__":
    main()
