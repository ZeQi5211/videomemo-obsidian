"""微信视频号下载服务 API：状态 / 启停 / 下载目录文件列表。

供前端「下载方式 → 微信视频号下载」一格使用，对接 wx_channels_download（wx_video_download）。
"""
from fastapi import APIRouter
from pydantic import BaseModel

from app.services.wxchannels_manager import manager
from app.utils.response import ResponseWrapper as R

router = APIRouter()


class WxDownloadReq(BaseModel):
    url: str


@router.get("/wxchannels/status")
def wxchannels_status():
    try:
        return R.success(data=manager.status())
    except Exception as e:
        return R.error(msg=str(e))


@router.post("/wxchannels/start")
def wxchannels_start():
    try:
        return R.success(data=manager.start())
    except Exception as e:
        return R.error(msg=str(e))


@router.post("/wxchannels/stop")
def wxchannels_stop():
    try:
        return R.success(data=manager.stop())
    except Exception as e:
        return R.error(msg=str(e))


@router.get("/wxchannels/downloads")
def wxchannels_downloads(limit: int = 30):
    try:
        return R.success(data=manager.list_downloads(limit))
    except Exception as e:
        return R.error(msg=str(e))


@router.post("/wxchannels/download")
def wxchannels_download(req: WxDownloadReq):
    """粘贴视频号分享链接 → 自动解析并下载为 MP4（需微信通道在线）。"""
    try:
        return R.success(data=manager.download_from_share(req.url))
    except Exception as e:
        return R.error(msg=str(e))
