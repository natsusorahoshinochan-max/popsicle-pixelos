# Independent PixelOS ROM repair modules

These five source repairs are part of the formal ROM. Implementation and
acceptance limits are maintained in the [repair topic](../../docs/pixelos/validation.md);
current delivery status is maintained in [progress](../../docs/pixelos/progress.md). The current
ROM needs none of these modules; disable or uninstall old overrides before upgrading.

The following historical KernelSU module instructions apply only to the accepted popsicle PixelOS
Android 17 global-telephony ROM with `ro.build.date.utc=1790747209`. Install through
KernelSU with system-file mounting configured and reboot. Each module contains one repair;
disable it and reboot to return to the ROM version of those files. No script
flashes partitions, patches init_boot, restarts live services or wipes data.

| Part / module ID | ROM payload | Repair scope |
|---|---|---|
| `audio-reconfigure` / `popsicle_audio_reconfigure` | Audio adapter executable | Bluetooth offload reconfiguration or active-headset switch, with normal media and IMS audio retained |
| `ims-locked-boot` / `popsicle_ims_locked_boot` | IMS bridge APK and matching preoptimization | Ordinary incoming-call two-way audio after credential-protected cold boot before first unlock, then after unlock |
| `brightness-event-order` / `popsicle_brightness_event_order` | services.jar, profile, ART artifacts and matching fs-verity manifest | Startup automatic brightness with queued old and new light samples |
| `rear-notice-eligibility` / `popsicle_rear_notice_eligibility` | SystemUI APK and matching preoptimization | Same notification loses rear extras, including while the rear bridge is disconnected |
| `vpn-ingress-owner` / `popsicle_vpn_ingress_owner` | Connectivity APEX JAR/profile, matching system-server preoptimization and fs-verity manifest | VPN replacement/teardown keeps the current network's ingress filters |

Brightness and VPN modules must not be enabled together. They carry separate
matching BuildManifest and system-server class-loader contexts. Disable one and
reboot before installing or enabling the other. The remaining three modules can
be enabled with either candidate. Installers reject active older modules that
replace the same payload paths; disable those modules and reboot first. Do not
later re-enable a conflicting old module. Replacing framework files from another
ROM or mixing one candidate's preoptimization with another is unsupported.

The VPN module uses `post-mount.sh` to enter init's mount namespace and bind the
JAR and profile read-only into the already active `com.android.tethering` APEX.
It refuses execution after zygote or system_server starts. Both successful binds
are required; a failure attempts to undo this invocation's binds and records the
failure in `connectivity-mount.status`. It has no late `service.sh` fallback.
The existing CAPEX and APEX activation/signature checks remain unchanged.

## Historical carrier packaging

For maintenance of this fixed-baseline carrier, prepare a separate product-layout
payload directory for the requested part and package in the remote Linux container:

```sh
python3 modules/popsicle-repair-parts/build-modules.py PART PREPARED_PAYLOAD NEW_OUTPUT \
    --soong-zip ANDROID_TREE/out-pixelos-user/host/linux-x86/bin/soong_zip
```

Prepared paths begin with `system/`, `system_ext/`, or (only for Connectivity)
`apex/com.android.tethering/javalib/`. The packager copies only that part's explicit
file list. Framework candidates must already include their own normally signed
`system/etc/security/fsverity/BuildManifest.apk` and `.idsig`, plus the matching
`.fsv_meta` files. `manifest_support.py` prepares those files from the matching ROM
baseline manifest and the specific candidate's framework artifacts. No baseline
or other candidate's missing artifacts are silently substituted during packing.

Each part produces its own installation ZIP and SHA256 companion, compressed with
16 workers by `soong_zip`. ZIP is the KernelSU installation format; full ROM
deliveries continue to use `.tar.gz` with `pigz -p 16`. Packaging produces the
carrier for its recorded baseline. Device acceptance retains its recorded scope.
