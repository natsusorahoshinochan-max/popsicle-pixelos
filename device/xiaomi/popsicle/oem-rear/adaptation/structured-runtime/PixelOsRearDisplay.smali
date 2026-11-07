# SPDX-License-Identifier: Apache-2.0
.class public final Ln2/PixelOsRearDisplay;
.super Ljava/lang/Object;

# Single geometry read/validation path; the OEM fields remain the state owners.
.method public static refreshGeometry(Landroid/content/Context;Ln2/e;)Z
    .locals 4
    const-class v0, Landroid/hardware/display/DisplayManager;
    invoke-virtual {p0, v0}, Landroid/content/Context;->getSystemService(Ljava/lang/Class;)Ljava/lang/Object;
    move-result-object v0
    check-cast v0, Landroid/hardware/display/DisplayManager;
    if-eqz v0, :unavailable
    const/4 v1, 0x1
    invoke-virtual {v0, v1}, Landroid/hardware/display/DisplayManager;->getDisplay(I)Landroid/view/Display;
    move-result-object v0
    if-eqz v0, :unavailable
    new-instance v1, Landroid/graphics/Point;
    invoke-direct {v1}, Landroid/graphics/Point;-><init>()V
    invoke-virtual {v0, v1}, Landroid/view/Display;->getRealSize(Landroid/graphics/Point;)V
    iget v2, v1, Landroid/graphics/Point;->x:I
    iget v3, v1, Landroid/graphics/Point;->y:I
    if-lez v2, :unavailable
    if-lez v3, :unavailable
    sget-object v1, LC2/l;->k:Landroid/graphics/Point;
    invoke-virtual {v1, v2, v3}, Landroid/graphics/Point;->set(II)V
    if-eqz p1, :ratio
    iput v2, p1, Ln2/e;->c:I
    iput v3, p1, Ln2/e;->d:I
    :ratio
    int-to-float v2, v2
    int-to-float v3, v3
    div-float/2addr v2, v3
    sput v2, LC2/l;->l:F
    const/4 v0, 0x1
    return v0
    :unavailable
    const/4 v0, 0x0
    return v0
.end method
