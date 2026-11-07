#!/system/bin/sh
# Read-only target/output sampling. Run for a bounded period; do not change settings.
samples=${1:-600}
case "$samples" in ''|*[!0-9]*) exit 2;; esac
[ "$samples" -le 3000 ] || exit 2
i=0
while [ "$i" -lt "$samples" ]; do
    printf 'SAMPLE %s time=' "$i"
    date +%s.%N
    printf 'elapsed '
    cat /proc/uptime
    dumpsys display | awk '
        /^Display Power Controller:/ {inside=1; id=-1}
        inside && /^  mDisplayId=/ && id == -1 {id=$0; print id}
        inside && /mPowerRequest=|mScreenState=|mScreenBrightness=|mAmbientLux=|mScreenAutoBrightness=|mTemporaryAutoBrightnessAdjustment=|mAppliedTemporaryAutoBrightnessAdjustment=|mStartupBrightnessPending=|mScreenBrightnessRampAnimator.isAnimating/ {print}
    '
    i=$((i + 1))
    sleep 0.2
done
