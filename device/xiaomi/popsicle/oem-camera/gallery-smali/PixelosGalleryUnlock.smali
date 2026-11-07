# SPDX-License-Identifier: Apache-2.0
.class public final Lcom/android/camera/PixelosGalleryUnlock;
.super Landroid/app/KeyguardManager$KeyguardDismissCallback;
.field private final camera:Lcom/android/camera/Camera;
.field private final capture:Z
.field private final rear:Z

.method public constructor <init>(Lcom/android/camera/Camera;ZZ)V
    .locals 0
    invoke-direct {p0}, Landroid/app/KeyguardManager$KeyguardDismissCallback;-><init>()V
    iput-object p1, p0, Lcom/android/camera/PixelosGalleryUnlock;->camera:Lcom/android/camera/Camera;
    iput-boolean p2, p0, Lcom/android/camera/PixelosGalleryUnlock;->capture:Z
    iput-boolean p3, p0, Lcom/android/camera/PixelosGalleryUnlock;->rear:Z
    return-void
.end method

.method public onDismissSucceeded()V
    .locals 3
    iget-object v0, p0, Lcom/android/camera/PixelosGalleryUnlock;->camera:Lcom/android/camera/Camera;
    invoke-virtual {v0}, Landroid/app/Activity;->isFinishing()Z
    move-result v1
    if-nez v1, :done
    invoke-virtual {v0}, Landroid/app/Activity;->isDestroyed()Z
    move-result v1
    if-nez v1, :done
    const-string v1, "keyguard"
    invoke-virtual {v0, v1}, Landroid/content/Context;->getSystemService(Ljava/lang/String;)Ljava/lang/Object;
    move-result-object v1
    check-cast v1, Landroid/app/KeyguardManager;
    invoke-virtual {v1}, Landroid/app/KeyguardManager;->isKeyguardLocked()Z
    move-result v1
    if-nez v1, :done
    iget-boolean v1, p0, Lcom/android/camera/PixelosGalleryUnlock;->capture:Z
    iget-boolean v2, p0, Lcom/android/camera/PixelosGalleryUnlock;->rear:Z
    invoke-virtual {v0, v1, v2}, Lcom/android/camera/Camera;->pixelosGotoGallery(ZZ)V
    :done
    return-void
.end method
