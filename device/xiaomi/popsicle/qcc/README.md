# QCC native HAL inputs

This device-side template installs the matching OEM QCC AIDL service and its
three private shared libraries into `system_ext`. The complete OEM files remain
in the designated private area. `Android.bp.in` is source-controlled; the
preparation tool copies it into the private bundle as `Android.bp`.

Use the companion source build guide and input preparation command at
`scripts/build-support/source-release.md`. The maintained tool is
`scripts/firmware-analysis/prepare_qcc_hal.py`; pass `--firmware-root` for the
unpacked OS4.0.0.23.XPBCNXM filesystems, `--template-dir` for this directory,
and `--output ANDROID_TREE/vendor/xiaomi/popsicle-private/prebuilt/qcc-hal`.
The tool requires four ELF64 AArch64 inputs, preserves their complete bytes, and changes
only the unique `interface aidl` line in the official rc to
`vendor.qti.qccsyshal_aidl.IQccsyshal/default`. It retains the OEM rc's copyright,
comments, directories, ownership, operation modes, and stop conditions. Missing
or repeated interface lines fail before output creation. An existing bundle is
accepted only when it contains the same files and bytes; changed output is not
overwritten.

The product already selects `popsicle_qccsyshal_aidl_service`. Preparation
installs the complete private bundle before the build. Source preparation does
not establish runtime acceptance; current project status is maintained in
[PixelOS progress](../../../../docs/pixelos/progress.md).
The existing device framework manifest provides the AIDL declaration. It must
remain paired with the actual installed service; the template does not add a
duplicate manifest fragment.

| Module | Installed path below `system_ext` |
| --- | --- |
| `popsicle_qccsyshal_aidl_service` | `bin/qccsyshal_aidl-service` and `etc/init/qccsyshal_aidl-service.rc` |
| `popsicle_qccsyshal_aidl_ndk` | `lib64/vendor.qti.qccsyshal_aidl-V1-ndk.so` |
| `popsicle_qccsyshal_aidl_impl` | `lib64/vendor.qti.qccsyshal_aidl-halimpl.so` |
| `popsicle_qcc_file_agent_sys` | `lib64/libqcc_file_agent_sys.so` |

Every direct `DT_NEEDED` entry is represented by `shared_libs` or
`system_shared_libs`. The union of platform providers is
`android.hardware.common-V2-ndk`, `android.hardware.common.fmq-V1-ndk`, `libbase`,
`libbinder`, `libbinder_ndk`, `libc++`, `libc`, `libcutils`, `libdl`, `libfmq`,
`liblog`, `libm`, `libutils`, and `libz`. No platform libraries are copied into
this private bundle. The four modules keep ELF checks enabled and undefined
symbols disallowed. The device's preserved kernel supports only 4 KiB pages;
`PRODUCT_MAX_PAGE_SIZE_SUPPORTED := 4096` expresses that kernel contract while
`PRODUCT_CHECK_PREBUILT_MAX_PAGE_SIZE := true` keeps segment checks active.

The fixed Qualcomm policy already supplies the service domain, executable,
Binder service, socket and data labels. The system linker namespace includes
`system_ext`; the vendor client crosses Binder rather than loading these private
system libraries. No new namespace exposure or permissive SELinux rule is added.

Preparation validates the complete ELF bytes and the exact single-line rc
change, rejecting missing/repeated interfaces and foreign output. Native
contract checks use `check_elf_file.py`, the modules' direct providers and
`host_init_verifier`; the 4 KiB positive and 16 KiB negative controls have
separate scope from product integration. Product integration concerns the
actual installed modules, rc, manifest, selected ELF providers (including bionic
APEX) and strict combined policy. These results do not establish runtime mode
selection, service registration, vendor client calls, ownership/labels or
death/restart and reboot behavior.

This package installs the native HAL service and its three shared libraries.
QCC application
signing/permissions, its JNI and file-agent socket endpoint, the conditional
Mink dependency, and Sigma/WFD are separate from this native provider contract.
A registered HAL does
not establish file-delivery or complete QCC acceptance. Existing native-download
and `hwservicemanager.ready` stop conditions must be observed as mode decisions,
not removed to force the service to stay running.
