// SPDX-License-Identifier: Apache-2.0
#include <aidl/android/media/audio/BnHalAdapterVendorExtension.h>
#include <aidl/qti/audio/core/VString.h>
#include <android/binder_manager.h>
#include <android/binder_process.h>
#include <android/log.h>

#include <sstream>
#include <optional>
#include <string>
#include <utility>
#include <vector>

using aidl::android::hardware::audio::core::VendorParameter;
using aidl::android::media::audio::BnHalAdapterVendorExtension;
using aidl::qti::audio::core::VString;

// The QTI primary HAL consumes string-valued VendorParameters. Preserve the
// original keys and values, leaving call-state validation to the real HAL.
class AudioAdapter final : public BnHalAdapterVendorExtension {
    static bool primary(const ParameterScope& scope) {
        return scope.instanceName == "default";
    }
    static ndk::ScopedAStatus invalid() {
        return ndk::ScopedAStatus::fromExceptionCode(EX_ILLEGAL_ARGUMENT);
    }
    static ndk::ScopedAStatus parseBluetoothReconfigureOffload(
            const std::string& rawValue, std::vector<VendorParameter>* result) {
        result->clear();
        // The notification needs no additional vendor parameters. Successful
        // parsing lets the framework invoke the real Bluetooth HAL operation.
        return rawValue == "true" ? ndk::ScopedAStatus::ok() : invalid();
    }

    ndk::ScopedAStatus parseVendorParameterIds(const ParameterScope& scope,
            const std::string& keys, std::vector<std::string>* result) override {
        result->clear();
        if (!primary(scope)) return ndk::ScopedAStatus::ok();
        std::istringstream input(keys);
        std::string key;
        while (std::getline(input, key, ';')) {
            if (key.empty() || key.find('=') != std::string::npos) return invalid();
            result->push_back(key);
        }
        return ndk::ScopedAStatus::ok();
    }

    ndk::ScopedAStatus parseVendorParameters(const ParameterScope& scope,
            const std::string& values, std::vector<VendorParameter>* sync,
            std::vector<VendorParameter>* async) override {
        sync->clear();
        async->clear();
        if (!primary(scope)) return ndk::ScopedAStatus::ok();
        std::istringstream input(values);
        std::string pair;
        while (std::getline(input, pair, ';')) {
            const auto split = pair.find('=');
            if (split == std::string::npos || split == 0) return invalid();
            VendorParameter parameter;
            parameter.id = pair.substr(0, split);
            VString value;
            value.value = pair.substr(split + 1);
            if (parameter.ext.setParcelable(value) != STATUS_OK) return invalid();
            sync->push_back(std::move(parameter));
        }
        return ndk::ScopedAStatus::ok();
    }

    ndk::ScopedAStatus processVendorParameters(const ParameterScope& scope,
            const std::vector<VendorParameter>& parameters, std::string* result) override {
        result->clear();
        if (!primary(scope)) return ndk::ScopedAStatus::ok();
        for (const auto& parameter : parameters) {
            std::optional<VString> value;
            if (parameter.ext.getParcelable(&value) != STATUS_OK || !value) return invalid();
            if (!result->empty()) *result += ';';
            *result += parameter.id + '=' + value->value;
        }
        return ndk::ScopedAStatus::ok();
    }

    ndk::ScopedAStatus parseBluetoothA2dpReconfigureOffload(
            const std::string& rawValue, std::vector<VendorParameter>* result) override {
        return parseBluetoothReconfigureOffload(rawValue, result);
    }
    ndk::ScopedAStatus parseBluetoothLeReconfigureOffload(
            const std::string& rawValue, std::vector<VendorParameter>* result) override {
        return parseBluetoothReconfigureOffload(rawValue, result);
    }
};

int main() {
    ABinderProcess_setThreadPoolMaxThreadCount(4);
    auto adapter = ndk::SharedRefBase::make<AudioAdapter>();
    const std::string name = std::string(AudioAdapter::descriptor) + "/default";
    const auto result = AServiceManager_addService(adapter->asBinder().get(), name.c_str());
    if (result != STATUS_OK) return 1;
    __android_log_print(ANDROID_LOG_INFO, "PopsicleAudioAdapter", "Registered");
    ABinderProcess_joinThreadPool();
    return 1;
}
