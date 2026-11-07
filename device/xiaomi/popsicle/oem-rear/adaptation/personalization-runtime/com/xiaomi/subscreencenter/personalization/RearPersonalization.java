/* SPDX-License-Identifier: Apache-2.0 */
package com.xiaomi.subscreencenter.personalization;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.content.IntentFilter;
import android.content.SharedPreferences;
import android.graphics.Point;
import android.hardware.Sensor;
import android.hardware.SensorEvent;
import android.hardware.SensorEventListener;
import android.hardware.SensorManager;
import android.hardware.display.DisplayManager;
import android.os.Handler;
import android.os.Looper;
import android.os.PowerManager;
import android.os.SystemClock;
import android.util.Log;
import android.view.Display;

/** Controls only the configured physical rear display; never the default display group. */
public final class RearPersonalization implements DisplayManager.DisplayListener, SensorEventListener {
    private static volatile RearPersonalization instance;
    private final Context context;
    private final Handler handler = new Handler(Looper.getMainLooper());
    private final DisplayManager displays;
    private final SensorManager sensors;
    private final Sensor pocket;
    private PowerManager.WakeLock wakeLock;
    private int heldDisplay = Display.INVALID_DISPLAY;
    private boolean listening;
    private boolean covered;
    private boolean sensorReady;
    private volatile String error = "";
    private final Runnable update = this::updatePower;

    private RearPersonalization(Context context) {
        this.context = context.getApplicationContext();
        displays = context.getSystemService(DisplayManager.class);
        sensors = context.getSystemService(SensorManager.class);
        pocket = sensors == null ? null : sensors.getDefaultSensor(33171227);
        displays.registerDisplayListener(this, handler);
        prefs(context).registerOnSharedPreferenceChangeListener(listener);
        context.registerReceiver(new BroadcastReceiver() {
            @Override
            public void onReceive(Context context, Intent intent) {
                refresh();
            }
        }, new IntentFilter("android.intent.action.USER_SWITCHED"), Context.RECEIVER_EXPORTED);
        handler.post(update);
    }

    private final SharedPreferences.OnSharedPreferenceChangeListener listener = (p, key) -> refresh();

    public static synchronized void start(Context context) {
        if (instance != null) return;
        try { instance = new RearPersonalization(context); }
        catch (RuntimeException e) { Log.e("RearPersonalization", "Initialization failed", e); }
    }

    static SharedPreferences prefs(Context context) {
        return context.createDeviceProtectedStorageContext()
                .getSharedPreferences("rear_personalization", Context.MODE_PRIVATE);
    }

    public static boolean allowLongPress() {
        return instance == null || prefs(instance.context).getBoolean("long_press", true);
    }

    static Display rearDisplay(Context context) throws Exception {
        Class<?> identity = Class.forName("com.android.internal.display.OemRearDisplay");
        for (Display display : context.getSystemService(DisplayManager.class).getDisplays()) {
            if (display.getDisplayId() != Display.DEFAULT_DISPLAY
                    && (Boolean) identity.getMethod("isRearDisplay",
                    android.content.res.Resources.class, Display.class)
                    .invoke(null, context.getResources(), display)) return display;
        }
        return null;
    }

    static String status() { return instance == null ? "背屏服务未就绪" : instance.error; }
    static boolean pocketAvailable() { return instance != null && instance.pocket != null; }

    private void refresh() {
        handler.removeCallbacks(update);
        handler.postDelayed(update, 150);
    }

    private void release() {
        if (wakeLock != null && wakeLock.isHeld()) wakeLock.release();
        wakeLock = null;
        heldDisplay = Display.INVALID_DISPLAY;
    }

    private void updatePower() {
        String previous = error;
        try {
            boolean enabled = prefs(context).getBoolean("always_on", false);
            int activeUser = (Integer) Class.forName("android.app.ActivityManager")
                    .getMethod("getCurrentUser").invoke(null);
            enabled &= activeUser == android.os.Process.myUid() / 100000;
            Display display = rearDisplay(context);
            if (!enabled || display == null) {
                release();
                if (listening) sensors.unregisterListener(this);
                listening = false;
                sensorReady = false;
                covered = false;
                error = display == null ? "未找到内置背屏" : "";
                return;
            }
            if (pocket == null) {
                release();
                error = "背屏口袋传感器不可用，未启用常亮";
                return;
            }
            if (!listening) {
                listening = sensors.registerListener(this, pocket, SensorManager.SENSOR_DELAY_NORMAL,
                        handler);
                if (!listening) {
                    error = "无法启用背屏口袋保护，未启用常亮";
                    release();
                    return;
                }
            }
            // Wait for an actual reading, rather than treating an unknown sensor as clear.
            if (!sensorReady) { error = "等待背屏口袋传感器"; return; }
            PowerManager power = context.getSystemService(PowerManager.class);
            int id = display.getDisplayId();
            if (covered) {
                release();
                if (display.getState() != Display.STATE_OFF) {
                    PowerManager.class.getMethod("goToSleep", int.class, long.class,
                            int.class, int.class).invoke(power, id, SystemClock.uptimeMillis(), 0, 1);
                }
                error = "口袋保护中";
                return;
            }
            if (heldDisplay != id || wakeLock == null) {
                release();
                wakeLock = (PowerManager.WakeLock) PowerManager.class.getMethod("newWakeLock",
                        int.class, String.class, int.class).invoke(power,
                        PowerManager.SCREEN_BRIGHT_WAKE_LOCK, "SSC:RearPersonalization", id);
                wakeLock.setReferenceCounted(false);
                heldDisplay = id;
            }
            if (!wakeLock.isHeld()) wakeLock.acquire();
            if (display.getState() != Display.STATE_ON) {
                PowerManager.class.getMethod("wakeUp", long.class, int.class, String.class,
                        int.class).invoke(power, SystemClock.uptimeMillis(), 2,
                        "SSC:rear-personalization", id);
            }
            error = "背屏常亮要求已生效";
        } catch (Exception e) {
            release();
            error = "背屏电源控制失败";
            Log.e("RearPersonalization", error, e);
        } finally {
            if (!previous.equals(error)) context.getContentResolver().notifyChange(
                    android.net.Uri.parse("content://com.xiaomi.subscreencenter.personalization"), null);
        }
    }

    @Override public void onSensorChanged(SensorEvent event) {
        if (event.values.length == 0 || !Float.isFinite(event.values[0])) return;
        boolean next = event.values[0] > 0;
        if (!sensorReady || next != covered) {
            sensorReady = true;
            covered = next;
            refresh();
        }
    }
    @Override public void onAccuracyChanged(Sensor sensor, int accuracy) {}
    @Override public void onDisplayAdded(int displayId) { refresh(); }
    @Override public void onDisplayRemoved(int displayId) { refresh(); }
    @Override public void onDisplayChanged(int displayId) { refresh(); }
}
