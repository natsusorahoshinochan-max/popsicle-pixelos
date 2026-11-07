// SPDX-License-Identifier: Apache-2.0
// Frida 17 observation only; current A17 CHI ELF VA offsets, validated prologues.
// Host must verify only the three documented device-config bytes differ from stock.
'use strict';
const module = Process.getModuleByName('com.qti.chi.override.so');
const lastTransition = new Map();
let reported = 0;
let failures = 0;
let outerReports = 0;
let outerFailures = 0;
const virtualTargets = new Set();
let virtualReports = 0;
function bytes(address, size) {
    try {
        return Array.from(new Uint8Array(address.readByteArray(size)),
            value => value.toString(16).padStart(2, '0')).join('');
    } catch (error) { return String(error); }
}
function attach(offset, instruction, callbacks) {
    const address = module.base.add(offset);
    if (address.readU32() !== instruction) throw new Error('Wrong prologue at ' + address);
    return Interceptor.attach(address, callbacks);
}
attach(0x4a39a0, 0xd503233f, {
    onEnter(args) {
        const target = args[0].readPointer().add(0x20).readPointer();
        const key = target.toString();
        if (!virtualTargets.has(key)) {
            virtualTargets.add(key);
            const owner = Process.getModuleByAddress(target);
            send({event: 'virtual_target', address: key, module: owner.path,
                offset: target.sub(owner.base).toString()});
            Interceptor.attach(target, {
                onEnter(callArgs) {
                    this.input = bytes(callArgs[1], 32);
                    this.converted = callArgs[2];
                    this.output = callArgs[3];
                },
                onLeave(value) {
                    if (virtualReports < 3 || (value.toInt32() !== 0 && virtualReports < 15)) {
                        virtualReports++;
                        send({event: 'virtual_recommended', target: key, resultRegister: value.toInt32(),
                            request: this.input, converted: bytes(this.converted, 64),
                            masterField44c: bytes(this.converted.add(0x44c), 4),
                            output: bytes(this.output, 32)});
                    }
                }
            });
        }
        this.request = args[1];
        this.converted = args[4];
        this.input = bytes(args[1], 40);
    },
    onLeave(retval) {
        if (outerReports < 3 || (retval.toInt32() !== 0 && outerFailures < 8)) {
            outerReports++;
            if (retval.toInt32() !== 0) outerFailures++;
            send({event: 'get_recommended', thread: this.threadId,
                resultRegister: retval.toInt32(), request: this.input,
                converted: bytes(this.converted, 64)});
        }
    }
});
attach(0x69e940, 0xd503233f, {
    onEnter(args) {
        this.outputs = [args[3], args[4], args[5], args[6]];
        this.record = {thread: this.threadId, map: bytes(args[0], 32),
            request: bytes(args[1], 64), newFrame: args[2].toInt32()};
    },
    onLeave(retval) {
        this.record.resultRegister = retval.toString(); // Return type not inferred.
        this.record.outputs = this.outputs.map((p, index) => bytes(p, index === 3 ? 24 : 4));
        lastTransition.set(this.threadId, this.record);
    }
});
attach(0x4a8e60, 0xd503233f, {
    onEnter(args) {
        this.converted = args[2];
        this.output = args[3];
        this.record = {event: 'recommended', thread: this.threadId,
            request: bytes(args[1], 32), convertedBefore: bytes(args[2], 40)};
    },
    onLeave(retval) {
        const result = retval.toInt32();
        if (reported < 3 || (result !== 0 && failures < 10)) {
            reported++;
            if (result !== 0) failures++;
            this.record.resultRegister = result;
            this.record.convertedAfter = bytes(this.converted, 40);
            this.record.output = bytes(this.output, 40);
            this.record.transition = lastTransition.get(this.threadId) || null;
            send(this.record);
        }
    }
});
send({event: 'ready', module: module.path, base: module.base.toString()});
