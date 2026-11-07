.method public final b5(ZZ)V
    .locals 0
    invoke-static {p0, p1, p2}, Lcom/android/camera/PixelosGallery;->open(Lcom/android/camera/Camera;ZZ)V
    return-void
.end method

.method private pixelosLaunchGallery(Landroid/content/Intent;Z)Z
    .locals 3
    :try_start
    if-nez p2, :rear
    invoke-virtual {p0, p1}, Landroid/content/Context;->startActivity(Landroid/content/Intent;)V
    goto :started
    :rear
    sget-object v0, Lcom/android/camera/guide/a;->i:Lcom/android/camera/guide/a$b;
    invoke-virtual {v0}, Lcom/android/camera/guide/a$b;->a()Lcom/android/camera/guide/a;
    invoke-static {p1}, Lcom/android/camera/guide/a;->pixelosStartGallery(Landroid/content/Intent;)Z
    move-result v0
    if-eqz v0, :not_started
    :started
    sget-object v0, LOh/c;->f:LOh/c;
    invoke-virtual {p0, v0}, Lcom/android/camera/a;->G2(LOh/c;)V
    :try_end
    .catch Ljava/lang/RuntimeException; {:try_start .. :try_end} :failed
    const/4 v0, 0x1
    return v0
    :failed
    move-exception v0
    const-string v1, "PixelosGallery"
    const-string v2, "No accessible gallery activity"
    invoke-static {v1, v2, v0}, Landroid/util/Log;->w(Ljava/lang/String;Ljava/lang/String;Ljava/lang/Throwable;)I
    sget-object v0, LOh/c;->b:LOh/c;
    invoke-virtual {p0, v0}, Lcom/android/camera/a;->G2(LOh/c;)V
    :not_started
    const/4 v0, 0x0
    return v0
.end method
