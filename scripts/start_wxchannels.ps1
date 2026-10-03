# 微信视频号下载服务（wx_channels_download v260907）一键启动
# 与「启动VideoMemo.bat」同款体验：双击即起，首次运行会弹 UAC 安装证书。
$ErrorActionPreference = "Stop"

$exe = "I:\70_applist\wx_channels_download\bin\wx_video_download.exe"
$web = "http://127.0.0.1:2022"

if (-not (Test-Path $exe)) {
    Write-Host "未找到 $exe" -ForegroundColor Red
    Write-Host "请先解压官方 v260907 构建包到 I:\70_applist\wx_channels_download\bin\"
    Read-Host "按回车退出"
    exit 1
}

# 已在运行则直接打开管理页面
try {
    $resp = Invoke-WebRequest -Uri "$web/api/status" -TimeoutSec 2 -UseBasicParsing
    if ($resp.StatusCode -eq 200) {
        Write-Host "微信视频号下载服务已在运行，打开管理页面…" -ForegroundColor Green
        Start-Process $web
        exit 0
    }
} catch {
    # 未运行，继续启动
}

Write-Host "正在启动微信视频号下载服务…" -ForegroundColor Green
Write-Host "首次运行会弹出 UAC 窗口，请点「是」以安装证书并设置系统代理。" -ForegroundColor Yellow
Start-Process -FilePath $exe -WorkingDirectory (Split-Path $exe)

Start-Sleep -Seconds 3
try {
    $resp = Invoke-WebRequest -Uri "$web/api/status" -TimeoutSec 3 -UseBasicParsing
    if ($resp.StatusCode -eq 200) {
        Write-Host "服务已就绪：$web" -ForegroundColor Green
        Start-Process $web
    }
} catch {
    Write-Host "服务启动中，稍后请打开：$web" -ForegroundColor Cyan
}
