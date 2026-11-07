# PixelOS brightness curve trial

KernelSU is only the delivery mechanism for a static product RRO. The payload
overrides exactly the matching lux and nits arrays from this project's device
configuration. It changes neither display XML nor services, properties, user
settings, sensors or ODM files. No boot-time brightness controller is included.

The user accepted v0.1 on 2026-09-12. The same RRO is now selected by the device
product at device/xiaomi/popsicle/rro/BrightnessCurve. This `overlay` directory
retains the exact tested module source; future production changes belong in the
device tree. Disable the trial module before evaluating the native ROM resources.

Package the APK at system/product/overlay/PopsicleBrightnessCurve.apk, with
module.prop and the existing ../resource-overlay-customize.sh as customize.sh.
Use this PixelOS tree's aapt2/signapk and platform certificate, never another ROM's
output. The connected device must be PixelOS popsicle, SDK 37, with KernelSU and system-file mounting configured. Reboot after installation. Disable the module and reboot
to restore the previous resources; do not remove or disable the stock ODM RRO.

Build results and user acceptance are recorded in
[the PixelOS report](../../docs/pixelos/validation.md).
