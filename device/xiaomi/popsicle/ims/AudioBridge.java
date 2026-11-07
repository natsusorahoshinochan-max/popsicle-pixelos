// SPDX-License-Identifier: Apache-2.0
package org.lineageos.popsicle.imsaudio;

import android.content.Context;
import android.os.HandlerThread;
import android.os.Looper;
import android.os.UserHandle;
import android.util.Log;

import dalvik.system.PathClassLoader;

/** Owns only the official QCRIL audio controller and its modem callbacks. */
public final class AudioBridge {
    private static Object sAgent;
    private static HandlerThread sControllerThread;

    private AudioBridge() {}

    static synchronized void start(Context context) {
        if (UserHandle.myUserId() != UserHandle.USER_SYSTEM || sAgent != null) {
            return;
        }
        final PathClassLoader loader = new PathClassLoader(
                "/system_ext/framework/popsicle-qti-audio-controller.jar:"
                        + "/system_ext/framework/qti-telephony-utils.jar",
                AudioBridge.class.getClassLoader());
        try {
            final Class<?> controller = Class.forName(
                    "com.qti.phone.audiocontroller.AudioControllerAgent", true, loader);
            final Object agent = controller.getMethod("getInstance", Context.class)
                    .invoke(null, context.getApplicationContext());
            if (sControllerThread == null) {
                sControllerThread = new HandlerThread("PopsicleImsAudio");
                sControllerThread.start();
            }
            controller.getMethod("init", Looper.class)
                    .invoke(agent, sControllerThread.getLooper());
            sAgent = agent;
            Log.i("PopsicleImsAudio", "Official audio controller initialization requested");
        } catch (ReflectiveOperationException e) {
            throw new IllegalStateException("Cannot initialize official IMS audio controller", e);
        }
    }
}
