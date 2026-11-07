# SPDX-License-Identifier: Apache-2.0
.class public final Lcom/android/camera/PixelosGallery;
.super Ljava/lang/Object;

.method public static open(Lcom/android/camera/Camera;ZZ)V
    .locals 3
    invoke-virtual {p0}, Landroid/app/Activity;->isFinishing()Z
    move-result v0
    if-nez v0, :done
    invoke-virtual {p0}, Landroid/app/Activity;->isDestroyed()Z
    move-result v0
    if-nez v0, :done
    :try_start
    const-string v0, "keyguard"
    invoke-virtual {p0, v0}, Landroid/content/Context;->getSystemService(Ljava/lang/String;)Ljava/lang/Object;
    move-result-object v0
    check-cast v0, Landroid/app/KeyguardManager;
    invoke-virtual {v0}, Landroid/app/KeyguardManager;->isKeyguardLocked()Z
    move-result v1
    if-eqz v1, :unlocked
    new-instance v1, Lcom/android/camera/PixelosGalleryUnlock;
    invoke-direct {v1, p0, p1, p2}, Lcom/android/camera/PixelosGalleryUnlock;-><init>(Lcom/android/camera/Camera;ZZ)V
    invoke-virtual {v0, p0, v1}, Landroid/app/KeyguardManager;->requestDismissKeyguard(Landroid/app/Activity;Landroid/app/KeyguardManager$KeyguardDismissCallback;)V
    goto :done
    :unlocked
    invoke-virtual {p0, p1, p2}, Lcom/android/camera/Camera;->pixelosGotoGallery(ZZ)V
    :try_end
    .catch Ljava/lang/RuntimeException; {:try_start .. :try_end} :failed
    goto :done
    :failed
    move-exception v0
    const-string v1, "PixelosGallery"
    const-string v2, "Gallery entry failed"
    invoke-static {v1, v2, v0}, Landroid/util/Log;->w(Ljava/lang/String;Ljava/lang/String;Ljava/lang/Throwable;)I
    :done
    return-void
.end method

.method public static view(Landroid/content/Context;Landroid/net/Uri;Z)Landroid/content/Intent;
    .locals 3
    invoke-virtual {p0}, Landroid/content/Context;->getContentResolver()Landroid/content/ContentResolver;
    move-result-object v0
    invoke-virtual {v0, p1}, Landroid/content/ContentResolver;->getType(Landroid/net/Uri;)Ljava/lang/String;
    move-result-object v0
    if-nez v0, :typed
    const-string v0, "image/*"
    if-eqz p2, :typed
    const-string v0, "video/*"
    :typed
    new-instance v1, Landroid/content/Intent;
    const-string v2, "android.intent.action.VIEW"
    invoke-direct {v1, v2}, Landroid/content/Intent;-><init>(Ljava/lang/String;)V
    invoke-virtual {v1, p1, v0}, Landroid/content/Intent;->setDataAndType(Landroid/net/Uri;Ljava/lang/String;)Landroid/content/Intent;
    const/4 v0, 0x1
    invoke-virtual {v1, v0}, Landroid/content/Intent;->addFlags(I)Landroid/content/Intent;
    const-string v0, "Camera photo"
    invoke-static {v0, p1}, Landroid/content/ClipData;->newRawUri(Ljava/lang/CharSequence;Landroid/net/Uri;)Landroid/content/ClipData;
    move-result-object v0
    invoke-virtual {v1, v0}, Landroid/content/Intent;->setClipData(Landroid/content/ClipData;)V
    return-object v1
.end method

.method public static album()Landroid/content/Intent;
    .locals 2
    const-string v0, "android.intent.action.MAIN"
    const-string v1, "android.intent.category.APP_GALLERY"
    invoke-static {v0, v1}, Landroid/content/Intent;->makeMainSelectorActivity(Ljava/lang/String;Ljava/lang/String;)Landroid/content/Intent;
    move-result-object v0
    return-object v0
.end method
