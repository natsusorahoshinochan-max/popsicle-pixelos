/* SPDX-License-Identifier: Apache-2.0 */

/** Read the native display snapshot independently of DisplayManager's cached state. */
public final class ArrInfo {
    public static void main(String[] args) throws Exception {
        if (args.length != 1) {
            throw new IllegalArgumentException("Expected physical display ID");
        }
        Class<?> surfaceControl = Class.forName("android.view.SurfaceControl");
        Object info = surfaceControl.getMethod("getDynamicDisplayInfo", long.class)
                .invoke(null, Long.parseLong(args[0]));
        if (info == null) {
            throw new IllegalStateException("Display snapshot unavailable");
        }
        for (String field : new String[]{"activeDisplayModeId", "hasArrSupport",
                "renderFrameRate"}) {
            System.out.println(field + "=" + info.getClass().getField(field).get(info));
        }
    }
}
