// Observe native metadata serialization and its actual Binder transaction; no ART hooks.
'use strict';
const camera = Process.getModuleByName('libcamera_client.so');
const meta = Process.getModuleByName('libcamera_metadata.so');
const binder = Process.getModuleByName('libbinder.so');
const sizeOf = new NativeFunction(meta.getExportByName('get_camera_metadata_size'), 'ulong', ['pointer']);
const parcelData = new NativeFunction(binder.getExportByName('_ZNK7android6Parcel4dataEv'), 'pointer', ['pointer']);
const parcelSize = new NativeFunction(binder.getExportByName('_ZNK7android6Parcel8dataSizeEv'), 'ulong', ['pointer']);
const clock = new NativeFunction(Module.getGlobalExportByName('clock_gettime'), 'int', ['int', 'pointer']);
let sequence = 0;
const pending = new Map();
function envelope(event, data) {
    const t = Memory.alloc(16);
    const ok = clock(7, t) === 0;
    return Object.assign({event, sequence: ++sequence, pid: Process.id, tid: Process.getCurrentThreadId(),
        boot_seconds: ok ? t.readS64().toString() : null,
        boot_nanoseconds: ok ? t.add(8).readS64().toString() : null}, data);
}
const write = camera.getExportByName('_ZN7android14CameraMetadata13writeToParcelERNS_6ParcelEPK15camera_metadata');
Interceptor.attach(write, {
    onEnter(args) {
        try {
            const key = args[0].toString();
            const bytes = args[1].isNull() ? 0 : Number(sizeOf(args[1]));
            if (bytes < 0 || bytes > 1048576) throw Error('Metadata size out of capture bounds: ' + bytes);
            const event = envelope('client_metadata_write', {parcel: key, bytes, encoding: 'camera_metadata_t'});
            send(event, bytes ? args[1].readByteArray(bytes) : null);
            // Parcel identity, not nearest timestamp, joins outgoing metadata to transact().
            let list = pending.get(key);
            if (!list) { list = []; pending.set(key, list); }
            list.push(event.sequence);
            if (pending.size > 128 || list.length > 128) {
                send(envelope('native_error', {error: 'Unmatched Parcel observation limit'}));
                pending.clear();
            }
        } catch (e) { send(envelope('native_error', {error: String(e)})); }
    }
});
const transact = binder.getExportByName('_ZN7android14IPCThreadState8transactEijRKNS_6ParcelEPS1_j');
Interceptor.attach(transact, {
    onEnter(args) {
        const key = args[3].toString();
        const list = pending.get(key);
        this.observed = false;
        if (list) {
            this.observed = true;
            this.call = ++sequence;
            pending.delete(key);
            this.reply = args[4];
            try {
                const bytes = Number(parcelSize(args[3]));
                if (bytes < 0 || bytes > 1048576) throw Error('Binder request exceeds capture bound');
                send(envelope('client_binder_request', {call: this.call, parcel: key, code: args[2].toUInt32(), bytes, encoding: 'fixed-build-binder-parcel'}), bytes ? parcelData(args[3]).readByteArray(bytes) : null);
            } catch (e) { send(envelope('native_error', {error: String(e)})); }
            send(envelope('client_metadata_transact', {call: this.call, parcel: key,
                handle: args[1].toInt32(), code: args[2].toUInt32(), metadata_sequences: list}));
        }
    },
    onLeave(result) {
        if (this.observed) {
            try {
                if (result.toInt32() === 0 && !this.reply.isNull()) {
                    const bytes = Number(parcelSize(this.reply));
                    if (bytes < 0 || bytes > 1048576) throw Error('Binder reply exceeds capture bound');
                    send(envelope('client_binder_reply', {call: this.call, bytes, encoding: 'fixed-build-binder-parcel'}), bytes ? parcelData(this.reply).readByteArray(bytes) : null);
                }
            } catch (e) { send(envelope('native_error', {error: String(e)})); }
            send(envelope('client_metadata_transact_return', {call: this.call, status: result.toInt32()}));
        }
    }
});
send(envelope('client_native_ready', {}));
