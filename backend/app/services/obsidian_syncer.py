"""Obsidian 同步服务：配置管理、路径校验、笔记归一化与写盘。

设计要点：
- 配置（目标文件夹路径）存在 app_config 表（key="obsidian"），由每个使用者在设置页填写自己的 vault 路径。
- 同步时对笔记做 Obsidian 兼容归一化：保证 YAML frontmatter 位于文件第 1 行，
  来源链接行（无论来自旧数据还是新数据）统一放在 frontmatter 之后。
- 文件名：视频标题清理非法字符 + 截断；重名自动追加 -1/-2 序号，绝不覆盖已有文件。
"""
from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Optional

from app.db.app_config_dao import load_value, set_value
from app.utils.logger import get_logger
from app.utils.note_helper import (
    prepend_source_link,
    normalize_frontmatter_tags,
    extract_author_from_raw_info,
    inject_auto_tags,
)

logger = get_logger(__name__)

_FILENAME_MAX = 100
_HISTORY_MAX = 10


class ObsidianConfigManager:
    """Obsidian 同步配置，持久化在 app_config 表（key="obsidian"）。"""

    _KEY = "obsidian"

    @staticmethod
    def _clean_history(raw) -> list[str]:
        return [
            p.strip()
            for p in (raw or [])
            if isinstance(p, str) and p.strip()
        ]

    def get(self) -> dict:
        cfg = load_value(self._KEY, default=None) or {}
        return {
            "folder_path": str(cfg.get("folder_path") or "").strip(),
            "auto_open": bool(cfg.get("auto_open", False)),
            "history": self._clean_history(cfg.get("history")),
        }

    def get_folder_path(self) -> str:
        return self.get()["folder_path"]

    def set(self, folder_path: Optional[str] = None, auto_open: Optional[bool] = None) -> dict:
        cfg = load_value(self._KEY, default=None) or {}
        if folder_path is not None:
            cfg["folder_path"] = str(folder_path or "").strip()
        if auto_open is not None:
            cfg["auto_open"] = bool(auto_open)
        # 历史路径：非空才记录，同路径去重置顶，最多保留 _HISTORY_MAX 条
        fp = str(cfg.get("folder_path") or "").strip()
        if fp:
            history = [p for p in self._clean_history(cfg.get("history")) if p != fp]
            cfg["history"] = [fp, *history][:_HISTORY_MAX]
        set_value(self._KEY, cfg)
        return self.get()


def validate_folder_path(folder_path: str) -> tuple[bool, str]:
    """校验目标文件夹：必填、绝对路径、存在、是目录、可写。返回 (ok, message)。"""
    path = (folder_path or "").strip()
    if not path:
        return False, "未填写 Obsidian 文件夹路径"
    p = Path(path)
    if not p.is_absolute():
        return False, "必须填写绝对路径（例如 D:\\ObsidianVault\\视频解析知识库）"
    if not p.exists():
        return False, f"目录不存在：{path}"
    if not p.is_dir():
        return False, f"路径不是文件夹：{path}"
    if not os.access(p, os.W_OK):
        return False, "目录不可写，请检查权限（例如是否被 OneDrive 占用）"
    return True, "路径有效"


def safe_filename(title: str, fallback: str) -> str:
    """清理 Windows/Obsidian 非法文件名，超长截断。返回不带扩展名的文件名。"""
    cleaned = re.sub(r'[\\/:*?"<>|\r\n\t]', '', title or '').strip()
    if not cleaned:
        cleaned = re.sub(r'[\\/:*?"<>|\r\n\t]', '', fallback or '') or 'note'
    return cleaned[:_FILENAME_MAX]


def write_md_unique(folder: Path, stem: str, content: str) -> Path:
    """写入 .md 文件；重名自动追加 -1/-2 序号。返回最终路径。"""
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    candidate = folder / f"{stem}.md"
    i = 1
    while candidate.exists():
        candidate = folder / f"{stem}-{i}.md"
        i += 1
    candidate.write_text(content, encoding="utf-8", newline="\n")
    return candidate


def ensure_obsidian_frontmatter(markdown: str, source_url: str = "") -> str:
    """Obsidian 兼容归一化：
    1. 移除任意位置的「来源链接」行（旧数据可能挤占 frontmatter 第一行）；
    2. frontmatter tags 行标点兜底（中文逗号/顿号 → 英文逗号，防层级标签失效）；
    3. 重新调用 prepend_source_link：若正文以 frontmatter 开头，来源链接插到
       闭合 --- 之后；否则插到最前面。保证 frontmatter 位于文件第 1 行。
    """
    lines = (markdown or "").splitlines()
    kept = [
        line
        for line in lines
        if not line.strip().startswith(("> 来源链接：", "来源链接："))
    ]
    # 去掉前导空行：来源链接行被移除后可能把空行顶到文件开头，会再次挤占 frontmatter 第一行
    body = "\n".join(kept).lstrip("\n")
    body = normalize_frontmatter_tags(body)
    return prepend_source_link(body, source_url)


def sync_note_to_obsidian(
    task_id: str,
    version_id: Optional[str] = None,
    source_url: str = "",
    folder_path: Optional[str] = None,
) -> dict:
    """把一篇已生成笔记写入 Obsidian 文件夹，返回同步信息。

    任何失败抛 ValueError（参数/校验类）或 RuntimeError（IO 类），由路由层转成错误响应。
    """
    target_folder = (folder_path or ObsidianConfigManager().get_folder_path()).strip()
    ok, msg = validate_folder_path(target_folder)
    if not ok:
        raise ValueError(msg)

    from app.routers.note import _pick_markdown_version
    from app.db.note_dao import load_note

    data = load_note(task_id)
    if data is None:
        raise ValueError(f"笔记不存在或尚未生成完成：{task_id}")

    content = _pick_markdown_version(data.get("markdown"), version_id)
    if not (content or "").strip():
        raise ValueError("笔记内容为空，无法同步")

    audio_meta = data.get("audio_meta") or {}
    raw_info = audio_meta.get("raw_info") or {}
    title = (
        audio_meta.get("title")
        or raw_info.get("title")
        or f"VideoMemo 笔记 {task_id[:8]}"
    )

    normalized = ensure_obsidian_frontmatter(content, source_url)
    # 同步兜底：老笔记可能缺「平台/」「作者/」标签，补注入（取不到作者则只加平台）
    platform = audio_meta.get("platform") or raw_info.get("platform") or ""
    author = extract_author_from_raw_info(raw_info, platform)
    normalized = inject_auto_tags(normalized, platform=platform, author=author)
    stem = safe_filename(title, task_id[:8])
    try:
        target = write_md_unique(Path(target_folder), stem, normalized)
    except OSError as e:
        logger.error(f"Obsidian 同步写入失败 (task_id={task_id}): {e}", exc_info=True)
        raise RuntimeError(f"写入文件失败：{e}") from e

    info = {
        "file_path": str(target),
        "filename": target.name,
        "folder_path": target_folder,
        "title": title,
    }
    logger.info(f"Obsidian 同步成功 (task_id={task_id}) -> {target}")
    return info
