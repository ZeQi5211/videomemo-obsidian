"""Obsidian 同步路由：配置读取/保存、路径测试、单篇笔记同步。

同步链路：前端把当前笔记 task_id + 版本 + 视频 URL 传给后端，
后端取笔记 markdown → Obsidian 兼容归一化 → 写入用户配置的 vault 文件夹。
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel

from app.services.obsidian_syncer import (
    ObsidianConfigManager,
    sync_note_to_obsidian,
    validate_folder_path,
)
from app.utils.logger import get_logger
from app.utils.response import ResponseWrapper as R

logger = get_logger(__name__)

router = APIRouter()

_config_manager = ObsidianConfigManager()


class ObsidianConfigRequest(BaseModel):
    folder_path: Optional[str] = None
    auto_open: Optional[bool] = None


class ObsidianSyncRequest(BaseModel):
    task_id: str
    version_id: Optional[str] = None
    source_url: Optional[str] = None


@router.get("/obsidian_config")
def get_obsidian_config():
    return R.success(data=_config_manager.get())


@router.post("/obsidian_config")
def update_obsidian_config(data: ObsidianConfigRequest):
    cfg = _config_manager.set(folder_path=data.folder_path, auto_open=data.auto_open)
    return R.success(data=cfg, msg="Obsidian 同步配置已保存")


@router.post("/obsidian_test")
def test_obsidian_path(data: ObsidianConfigRequest):
    folder_path = (data.folder_path or _config_manager.get_folder_path()).strip()
    ok, msg = validate_folder_path(folder_path)
    if ok:
        return R.success(data={"ok": True, "folder_path": folder_path}, msg=msg)
    return R.error(msg=msg, code=400)


@router.post("/obsidian_sync")
def obsidian_sync(data: ObsidianSyncRequest):
    try:
        info = sync_note_to_obsidian(
            task_id=data.task_id,
            version_id=data.version_id,
            source_url=data.source_url or "",
        )
        return R.success(data=info, msg=f"已同步到 Obsidian：{info['filename']}")
    except ValueError as e:
        return R.error(msg=str(e), code=400)
    except RuntimeError as e:
        return R.error(msg=str(e), code=500)
    except Exception as e:
        logger.error(f"Obsidian 同步异常 (task_id={data.task_id}): {e}", exc_info=True)
        return R.error(msg=f"同步失败：{e}", code=500)
