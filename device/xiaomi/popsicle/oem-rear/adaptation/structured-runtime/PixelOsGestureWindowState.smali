# SPDX-License-Identifier: Apache-2.0
.class public final Ln2/PixelOsGestureWindowState;
.super Ljava/lang/Object;
.implements Ljava/lang/Runnable;
.field private final manager:Ln2/e;
.field private final view:Landroid/view/View;
.field private final back:Z

.method public constructor <init>(Ln2/e;Landroid/view/View;Z)V
    .locals 0
    invoke-direct {p0}, Ljava/lang/Object;-><init>()V
    iput-object p1, p0, Ln2/PixelOsGestureWindowState;->manager:Ln2/e;
    iput-object p2, p0, Ln2/PixelOsGestureWindowState;->view:Landroid/view/View;
    iput-boolean p3, p0, Ln2/PixelOsGestureWindowState;->back:Z
    return-void
.end method

# View.post preserves the existing main-thread attachment timing. Recalculate
# current policy instead of saving a hidden value or falsifying the OEM cache.
.method public run()V
    .locals 4
    iget-object v0, p0, Ln2/PixelOsGestureWindowState;->manager:Ln2/e;
    iget-object v1, p0, Ln2/PixelOsGestureWindowState;->view:Landroid/view/View;
    invoke-virtual {v1}, Landroid/view/View;->isAttachedToWindow()Z
    move-result v2
    if-eqz v2, :done
    iget-boolean v2, p0, Ln2/PixelOsGestureWindowState;->back:Z
    const/4 v3, 0x1
    if-eqz v2, :home
    iget-object v2, v0, Ln2/e;->m:Ln2/h;
    if-ne v1, v2, :done
    invoke-virtual {v0, v3}, Ln2/e;->applyPixelOsBackState(Z)V
    return-void
    :home
    iget-object v2, v0, Ln2/e;->p:Landroid/view/View;
    if-ne v1, v2, :done
    invoke-virtual {v0, v3}, Ln2/e;->applyPixelOsHomeState(Z)V
    :done
    return-void
.end method
