// Observation only; fixed official A17 ELF identities guarded before hooking.
'use strict';
let sequence = 0;
const installed = new Set();
const clock = new NativeFunction(Module.getGlobalExportByName('clock_gettime'), 'int', ['int', 'pointer']);
function emit(event, data, binary = null) {
    const t = Memory.alloc(16);
    const ok = clock(7, t) === 0;
    send(Object.assign({event, sequence: ++sequence, pid: Process.id, tid: Process.getCurrentThreadId(),
        boot_seconds: ok ? t.readS64().toString() : null,
        boot_nanoseconds: ok ? t.add(8).readS64().toString() : null}, data), binary);
}
const binder = Process.getModuleByName('libbinder_ndk.so');
const position = new NativeFunction(binder.getExportByName('AParcel_getDataPosition'), 'int', ['pointer']);
const marshal = new NativeFunction(binder.getExportByName('AParcel_marshal'), 'int', ['pointer', 'pointer', 'ulong', 'ulong']);
Process.attachModuleObserver({onAdded(m) {
    if (installed.has(m.path)) return;
    try {
        if (/^android\.hardware\.camera\.device-V[123]-ndk\.so$/.test(m.name)) {
            const name = '_ZN4aidl7android8hardware6camera6device19StreamConfiguration14readFromParcelEPK7AParcel';
            const address = m.findExportByName(name);
            if (address) {
                Interceptor.attach(address, {
                    onEnter(args) { this.parcel = args[1]; this.start = position(args[1]); this.object = args[0].toString(); },
                    onLeave(status) {
                        try {
                            const end = position(this.parcel);
                            const size = end - this.start;
                            if (status.toInt32() !== 0 || size < 4 || size > 1048576) {
                                emit('native_error', {hook: name, status: status.toInt32(), size}); return;
                            }
                            const buffer = Memory.alloc(size);
                            const copied = marshal(this.parcel, buffer, this.start, size);
                            if (copied !== 0) { emit('native_error', {hook: name, marshal_status: copied}); return; }
                            emit('aidl_stream_configuration', {module: m.path, object: this.object,
                                encoding: 'fixed-build-aidl-parcel', bytes: size}, buffer.readByteArray(size));
                        } catch (e) { emit('native_error', {hook: name, error: String(e)}); }
                    }
                });
                installed.add(m.path);
                emit('native_hook_ready', {module: m.path, hook: 'aidl_stream_configuration'});
            }
        }
        if (['libmicamera_hal_core.so', 'libmicamera_adapter.so', 'libmicamera_aidl_device.so', 'libmicamera_aidl_device_adaptor.so'].includes(m.name)) {
            for (const symbol of m.enumerateExports()) {
                if (!/Session(16configureStreams|18configureStreamsV2)/.test(symbol.name)) continue;
                Interceptor.attach(symbol.address, {onEnter(args) {
                    emit('configure_dispatch', {module: m.path, symbol: symbol.name,
                        session_object: args[0].toString(), configuration_object: args[1].toString()});
                }});
            }
        }
        if (m.name === 'libmicamera_adapter.so') {
            const p = m.getExportByName('_ZN7adapter12convertToHALERKN5micam6StreamEP13camera_stream');
            if (!p.equals(m.base.add(0x404e8))) throw Error('Unexpected stream converter offset');
            Interceptor.attach(p, {onEnter(args) {
                try { emit('stream_convert', {physical_id: args[0].add(0x2c).readS32(),
                    caller_module: Process.findModuleByAddress(this.returnAddress)?.name,
                    caller_offset: (() => { const c = Process.findModuleByAddress(this.returnAddress); return c ? this.returnAddress.sub(c.base).toString() : null; })()}); }
                catch (e) { emit('native_error', {error: String(e)}); }
            }});
            installed.add(m.path);
            emit('native_hook_ready', {module: m.path, hook: 'stream_converter'});
        }
        if (m.name === 'libqti_vndfwk_detect.so') {
            const address = m.getExportByName('isRunningWithVendorEnhancedFramework');
            Interceptor.attach(address, {
                onEnter() {
                    const caller = Process.findModuleByAddress(this.returnAddress);
                    this.caller = caller ? caller.name : null;
                    this.offset = caller ? this.returnAddress.sub(caller.base).toString() : null;
                },
                onLeave(result) {
                    emit('shared_framework_result', {result: result.toInt32(), caller: this.caller, caller_offset: this.offset});
                }
            });
            installed.add(m.path);
            emit('native_hook_ready', {module: m.path, hook: 'shared_framework_detector'});
        }
        if (m.name === 'com.qti.chi.override.so') {
            const p = m.getExportByName('_ZN15ExtensionModule18GetDevicesSettingsEv');
            if (!p.equals(m.base.add(0x4e7d20))) throw Error('Unexpected XML selector offset');
            Interceptor.attach(p, {onEnter() { emit('xml_selector_enter', {}); }, onLeave() { emit('xml_selector_leave', {}); }});
            installed.add(m.path);
            emit('native_hook_ready', {module: m.path, hook: 'xml_selector'});
        }
    } catch (e) { emit('native_error', {module: m.path, error: String(e)}); }
}});
for (const name of ['open', 'openat', 'fopen']) {
    const address = Module.findGlobalExportByName(name);
    if (!address) continue;
    Interceptor.attach(address, {
        onEnter(args) {
            this.path = null;
            try {
                const path = args[name === 'openat' ? 1 : 0].readUtf8String();
                if (path && /(?:popsicle|kaanapali|camera.*config|devicesettings).*\.xml$/i.test(path)) this.path = path;
            } catch (_) {}
        },
        onLeave(result) {
            if (this.path !== null) emit('camera_xml_open', {api: name, path: this.path, result: result.toString()});
        }
    });
}
emit('native_ready', {installed: Array.from(installed)});
