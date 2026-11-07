// CameraService receiver only. Never load this observer in an application process.
'use strict';
if (Process.mainModule.name !== 'cameraserver') throw Error('Expected cameraserver');
const camera = Process.getModuleByName('libcamera_client.so');
const binder = Process.getModuleByName('libbinder.so');
const native = (name, result, args) => new NativeFunction(
    binder.getExportByName(name), result, args);
const dataOf = native('_ZNK7android6Parcel4dataEv', 'pointer', ['pointer']);
const sizeOf = native('_ZNK7android6Parcel8dataSizeEv', 'ulong', ['pointer']);
const self = native('_ZN7android14IPCThreadState10selfOrNullEv', 'pointer', []);
const callingUid = native('_ZNK7android14IPCThreadState13getCallingUidEv', 'uint', ['pointer']);
const callingPid = native('_ZNK7android14IPCThreadState13getCallingPidEv', 'int', ['pointer']);
const clock = new NativeFunction(Module.getGlobalExportByName('clock_gettime'), 'int', ['int', 'pointer']);
const contexts = new Map();
let sequence = 0;
let targetUid = null;
function emit(event, fields, binary = null) {
    const time = Memory.alloc(16);
    const ok = clock(7, time) === 0;
    const row = Object.assign({event, sequence: ++sequence, pid: Process.id,
        tid: Process.getCurrentThreadId(),
        boot_seconds: ok ? time.readS64().toString() : null,
        boot_nanoseconds: ok ? time.add(8).readS64().toString() : null}, fields);
    send(row, binary);
    return row.sequence;
}
function parcel(event, pointer, fields) {
    const bytes = Number(sizeOf(pointer));
    if (bytes < 0 || bytes > 1048576) throw Error('Parcel outside capture bound: ' + bytes);
    emit(event, Object.assign({bytes, encoding: 'fixed-build-binder-parcel'}, fields),
        bytes ? dataOf(pointer).readByteArray(bytes) : null);
}
rpc.exports = {
    configure(uid) {
        if (targetUid !== null || !Number.isInteger(uid) || uid < 10000) throw Error('Invalid target UID');
        targetUid = uid;
        return {uid, process: Process.mainModule.name};
    }
};
// A normal function entry, not its adjustor thunk or an instruction in its body.
const transactName = '_ZN7android8hardware7camera218BnCameraDeviceUser10onTransactEjRKNS_6ParcelEPS3_j';
Interceptor.attach(camera.getExportByName(transactName), {
    onEnter(args) {
        this.active = false;
        try {
            const ipc = self();
            if (ipc.isNull() || targetUid === null || callingUid(ipc) !== targetUid) return;
            const tid = Process.getCurrentThreadId();
            const row = {client_pid: callingPid(ipc), client_uid: targetUid,
                device_user: args[0].toString(), code: args[1].toUInt32()};
            row.call = emit('service_transaction', row);
            this.tid = tid;
            this.row = row;
            this.reply = args[3];
            this.previous = contexts.get(tid);
            contexts.set(tid, row);
            this.active = true;
            parcel('service_binder_request', args[2], row);
        } catch (error) { emit('native_error', {hook: transactName, error: String(error)}); }
    },
    onLeave(result) {
        if (!this.active) return;
        try {
            if (result.toInt32() === 0 && !this.reply.isNull()) {
                parcel('service_binder_reply', this.reply, this.row);
            }
            emit('service_transaction_return', Object.assign({status: result.toInt32()}, this.row));
        } catch (error) { emit('native_error', {hook: transactName, error: String(error)}); }
        finally {
            if (this.previous === undefined) contexts.delete(this.tid);
            else contexts.set(this.tid, this.previous);
        }
    }
});
// Copy only after the original reader successfully returns ownership to its caller.
// Scope by the enclosing camera transaction; never call the reader a second time.
const readName = '_ZN7android14CameraMetadata14readFromParcelERKNS_6ParcelEPP15camera_metadata';
Interceptor.attach(camera.getExportByName(readName), {
    onEnter(args) {
        this.row = contexts.get(Process.getCurrentThreadId());
        this.destination = args[1];
    },
    onLeave(status) {
        if (!this.row || status.toInt32() !== 0) return;
        try {
            const metadata = this.destination.readPointer();
            const bytes = metadata.isNull() ? 0 : metadata.readU32();
            if (bytes !== 0 && (bytes < 48 || bytes > 1048576)) throw Error('Metadata outside capture bound: ' + bytes);
            emit('service_metadata_read', Object.assign({bytes, encoding: 'camera_metadata_t'}, this.row),
                bytes ? metadata.readByteArray(bytes) : null);
        } catch (error) { emit('native_error', {hook: readName, error: String(error)}); }
    }
});
emit('service_native_ready', {hooks: [transactName, readName]});
