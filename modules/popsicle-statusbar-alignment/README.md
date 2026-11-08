# PixelOS status bar alignment trial v0.1

Historical KernelSU test module for PixelOS Android 17 popsicle, system build date
1790225821. The resource fix is integrated into the production device tree and
complete ROM; the user confirmed successful on-device testing of that ROM on
2026-09-24. The current ROM does not require this trial module. See the
[repair and validation record](../../docs/pixelos/validation.md).

The module replaces `/product/overlay/PopsicleStatusbarSystemUI.apk` through
KernelSU with system-file mounting configured. It retains the package, platform signing
certificate, corners and landscape split-shade resources. Main-display status
bar top padding changes from 38px to 0px; the unused bottom-padding resource is
removed. Cutout, status bar window heights, framework and SystemUI code are unchanged.
The source belongs to this project and has no runtime external imports.

To reproduce the archived trial on the remote Linux host with its matching baseline:
`bash modules/popsicle-statusbar-alignment/build.sh ANDROID_TREE OUTPUT_DIRECTORY`.
The builder refuses a different baseline APK and verifies signing. It does not
modify active Android source or production device-tree resources. The published
v0.1 ZIP remains unchanged as historical evidence.

On the matching old baseline, installation through KernelSU takes effect after a
manual reboot. Disabling or uninstalling and rebooting restores that baseline.
Chrome's landscape cutout-side black area is expected and preserved. Individual
font/display scales, rotation directions, lockscreen and expanded-shade layouts
await separate checks.
