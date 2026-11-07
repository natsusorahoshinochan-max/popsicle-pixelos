// SPDX-License-Identifier: Apache-2.0
package org.lineageos.popsicle.imsaudio;

import android.app.Application;
import android.os.SystemProperties;

/** A persistent system process is restarted by ActivityManager after process death. */
public final class ImsAudioApplication extends Application {
    @Override
    public void onCreate() {
        super.onCreate();
        if (SystemProperties.getBoolean("sys.boot_completed", false)) {
            AudioBridge.start(this);
        }
    }
}
