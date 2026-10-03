# app/routers/assets.py
"""
中间产物资产管理接口。

结构（以「项目 = 视频」为一级，项目内按类型细分）：
- 项目来源：video_tasks 表（video_id + task_id 映射）+ data/data 下未被表覆盖的音视频文件
- 项目内分类：
    audio              音频       data/data/{video_id}.mp3 等
    video              视频       data/data/{video_id}.mp4 等
    covers             封面       static/covers/*.jpg（从 {task_id}_audio.json 的 cover_url 解析）
    screenshots        原片截图   static/screenshots/*.jpg（从 {task_id}_markdown.md 解析）
    frames             抽帧       data/output_frames/*.jpg（按生成时间归属到最近一次视频理解的项目）
    grids              网格图     data/grid_output/*.jpg（同上）
    video_transcripts  视频级转写缓存  note_results/video_transcripts/{platform}_{video_id}_*.json
    transcripts        任务级转写/元信息缓存  note_results/{task_id}_transcript.json / _audio.json
    notes              笔记缓存   note_results/{task_id}_markdown.md
- 共享区（shared）：无法归属到任何项目的孤儿文件

安全：删除/打开只接受服务端按白名单解析出的路径，拒绝任意路径与穿越。
"""
import json
import hashlib
import os
import re
import sqlite3
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.utils.path_helper import get_data_dir, get_runtime_dir
from app.utils.response import ResponseWrapper as R

router = APIRouter()

# ------------------ 目录 ------------------
_note_output_dir = os.getenv("NOTE_OUTPUT_DIR", "note_results")
NOTE_OUTPUT_DIR = Path(_note_output_dir) if os.path.isabs(_note_output_dir) else Path(_note_output_dir)

_env_out_dir = os.getenv("OUT_DIR")
SCREENSHOTS_DIR = (
    Path(_env_out_dir)
    if _env_out_dir and os.path.isabs(_env_out_dir)
    else Path(get_runtime_dir("static")) / "screenshots"
)
COVERS_DIR = Path(get_runtime_dir("static")) / "covers"

DATA_ROOT = Path(get_data_dir()).parent          # backend/data
MEDIA_DIR = Path(get_data_dir())                 # backend/data/data（音视频）
FRAMES_DIR = DATA_ROOT / "output_frames"
GRIDS_DIR = DATA_ROOT / "grid_output"
VIDEO_TRANSCRIPTS_DIR = NOTE_OUTPUT_DIR / "video_transcripts"
DB_PATH = DATA_ROOT.parent / "video_memo.db"     # backend/video_memo.db

# 允许操作的所有根目录（白名单）
_ALLOWED_ROOTS = [
    MEDIA_DIR.resolve(),
    SCREENSHOTS_DIR.resolve(),
    COVERS_DIR.resolve(),
    FRAMES_DIR.resolve(),
    GRIDS_DIR.resolve(),
    NOTE_OUTPUT_DIR.resolve(),
    VIDEO_TRANSCRIPTS_DIR.resolve(),
]

_TEXT_EXTS = {".json", ".md", ".txt", ".srt", ".vtt"}
_IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp"}
_AUDIO_EXTS = {".mp3", ".m4a", ".wav", ".aac", ".ogg", ".flac", ".opus"}
_VIDEO_EXTS = {".mp4", ".mkv", ".webm", ".mov", ".flv", ".avi", ".ts"}

_SCREENSHOT_RE = re.compile(r"/static/screenshots/([A-Za-z0-9_\-\.]+\.(?:jpg|jpeg|png))")

CATEGORY_LABELS = {
    "audio": ("音频", "Audio"),
    "video": ("视频", "Video"),
    "covers": ("封面", "Covers"),
    "screenshots": ("原片截图", "Screenshots"),
    "frames": ("抽帧", "Frames"),
    "grids": ("网格图", "Grids"),
    "video_transcripts": ("视频级转写缓存", "Video transcripts"),
    "transcripts": ("转写/元信息缓存", "Transcripts"),
    "notes": ("笔记缓存", "Notes"),
}
CATEGORY_DIRS = {
    "audio": MEDIA_DIR,
    "video": MEDIA_DIR,
    "covers": COVERS_DIR,
    "screenshots": SCREENSHOTS_DIR,
    "frames": FRAMES_DIR,
    "grids": GRIDS_DIR,
    "video_transcripts": VIDEO_TRANSCRIPTS_DIR,
    "transcripts": NOTE_OUTPUT_DIR,
    "notes": NOTE_OUTPUT_DIR,
}


# ------------------ 工具 ------------------
def _safe_size(size: int) -> str:
    try:
        size = float(size)
    except (TypeError, ValueError):
        return "-"
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024 or unit == "TB":
            return f"{size:.1f} {unit}" if unit != "B" else f"{int(size)} B"
        size /= 1024
    return f"{size:.1f} TB"


def _scan_dir(directory: Path, exts: Optional[set] = None) -> List[dict]:
    """扫描目录，返回 [{name, size, mtime, mtime_ts, ext, url}]，按修改时间倒序。"""
    files: List[dict] = []
    if not directory.exists():
        return files
    try:
        entries = list(directory.iterdir())
    except OSError:
        return files
    for entry in entries:
        if not entry.is_file():
            continue
        name = entry.name
        ext = entry.suffix.lower()
        if exts and ext not in exts:
            continue
        try:
            stat = entry.stat()
            size = stat.st_size
            mtime_ts = stat.st_mtime
            mtime = datetime.fromtimestamp(mtime_ts).strftime("%Y-%m-%d %H:%M:%S")
        except OSError:
            size, mtime, mtime_ts = 0, "", 0
        files.append({
            "name": name,
            "size": size,
            "size_text": _safe_size(size),
            "mtime": mtime,
            "mtime_ts": mtime_ts,
            "ext": ext,
            "url": None,
        })
    files.sort(key=lambda f: f["mtime"], reverse=True)
    return files


def _decorate(files: List[dict], url_prefix: str, kind: str, category: str,
              content_param: bool = False) -> List[dict]:
    for f in files:
        f["kind"] = kind
        f["category"] = category
        f.pop("mtime_ts", None)
        if content_param:
            f["url"] = f"/api/assets/content?file={f['name']}"
        else:
            f["url"] = f"{url_prefix}/{f['name']}"
    return files


def _load_json(path: Path) -> Optional[dict]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _find_screenshots_in_db(task_id: str) -> List[str]:
    """从数据库 notes 表正文解析原片截图文件名（正文已含替换后的图片 URL）。"""
    try:
        conn = sqlite3.connect(str(DB_PATH))
        cur = conn.cursor()
        cur.execute("SELECT content FROM notes WHERE task_id=?", (task_id,))
        row = cur.fetchone()
        conn.close()
        if not row or not row[0]:
            return []
        return list(dict.fromkeys(_SCREENSHOT_RE.findall(str(row[0]))))
    except Exception:
        return []


def _find_covers_in_audio_json(audio_path: Path) -> List[str]:
    """从 audio 元信息缓存的原始 cover_url 推算本地封面文件名（md5(URL)[:20]）。"""
    data = _load_json(audio_path)
    if not data:
        return []
    url = str(data.get("cover_url") or "")
    if not url.startswith(("http://", "https://")):
        return []
    digest = hashlib.md5(url.encode("utf-8")).hexdigest()[:20]
    if COVERS_DIR.exists():
        try:
            for f in COVERS_DIR.iterdir():
                if f.is_file() and f.name.startswith(digest):
                    return [f.name]
        except OSError:
            return []
    return []


def _video_tasks() -> List[tuple]:
    """返回 [(video_id, platform, task_id, created_at)]。"""
    rows: List[tuple] = []
    try:
        conn = sqlite3.connect(str(DB_PATH))
        cur = conn.cursor()
        cur.execute("SELECT video_id, platform, task_id, created_at FROM video_tasks ORDER BY created_at")
        rows = [(r[0], r[1] or "", r[2] or "", r[3] or "") for r in cur.fetchall()]
        conn.close()
    except Exception:
        pass
    return rows


def _json_body_bytes(resp) -> dict:
    """把 R.success 的 JSONResponse 转 dict。"""
    return json.loads(resp.body.decode("utf-8"))


# ------------------ 构建列表 ------------------
def _build_assets():
    vrows = _video_tasks()
    task_ids_all: Dict[str, str] = {}
    for _vid, _pf, tid, _ct in vrows:
        if tid:
            task_ids_all[tid] = _vid

    project_order: List[str] = []
    project_meta: Dict[str, dict] = {}
    for video_id, platform, task_id, created_at in vrows:
        if video_id not in project_meta:
            project_order.append(video_id)
            project_meta[video_id] = {"platform": platform, "created_at": created_at, "task_ids": []}
        if task_id:
            project_meta[video_id]["task_ids"].append(task_id)

    media_files = _scan_dir(MEDIA_DIR, exts=_AUDIO_EXTS | _VIDEO_EXTS)
    for f in media_files:
        vid = Path(f["name"]).stem
        if vid not in project_meta:
            project_order.append(vid)
            project_meta[vid] = {"platform": "", "created_at": f["mtime"], "task_ids": []}

    # 抽帧 / 网格图归属：修改时间最接近且差值 < 10 分钟的项目
    frame_files = _scan_dir(FRAMES_DIR, exts=_IMAGE_EXTS)
    grid_files = _scan_dir(GRIDS_DIR, exts=_IMAGE_EXTS)

    def _match_owner(imgs: List[dict]) -> Optional[str]:
        if not imgs:
            return None
        latest_ts = max(f["mtime_ts"] for f in imgs)
        best, best_diff = None, 600
        for vid in project_order:
            for mf in media_files:
                if Path(mf["name"]).stem == vid:
                    diff = abs(mf["mtime_ts"] - latest_ts)
                    if diff < best_diff:
                        best, best_diff = vid, diff
                    break
        return best

    frames_owner = _match_owner(frame_files)
    grids_owner = _match_owner(grid_files)

    screenshots_dir_files = {f["name"]: f for f in _scan_dir(SCREENSHOTS_DIR, exts=_IMAGE_EXTS)}
    covers_dir_files = {f["name"]: f for f in _scan_dir(COVERS_DIR, exts=_IMAGE_EXTS)}
    note_json_md = _scan_dir(NOTE_OUTPUT_DIR, exts={".json", ".md"})
    video_transcript_files = _scan_dir(VIDEO_TRANSCRIPTS_DIR, exts={".json"})

    projects: List[dict] = []
    for vid in project_order:
        meta = project_meta[vid]
        task_ids = meta["task_ids"]
        categories: List[dict] = []

        audio = [f for f in media_files if Path(f["name"]).stem == vid and f["ext"] in _AUDIO_EXTS]
        video = [f for f in media_files if Path(f["name"]).stem == vid and f["ext"] in _VIDEO_EXTS]
        if audio:
            categories.append({"id": "audio", "kind": "media",
                               "files": _decorate(audio, "/media/data", "audio", "audio")})
        if video:
            categories.append({"id": "video", "kind": "media",
                               "files": _decorate(video, "/media/data", "video", "video")})

        cover_names: List[str] = []
        screenshot_names: List[str] = []
        tc_paths: List[Path] = []
        note_paths: List[Path] = []
        for task_id in task_ids:
            audio_info_path = NOTE_OUTPUT_DIR / f"{task_id}_audio.json"
            md_path = NOTE_OUTPUT_DIR / f"{task_id}_markdown.md"
            t_path = NOTE_OUTPUT_DIR / f"{task_id}_transcript.json"
            if audio_info_path.exists():
                cover_names += _find_covers_in_audio_json(audio_info_path)
                tc_paths.append(audio_info_path)
            if md_path.exists():
                note_paths.append(md_path)
            if t_path.exists():
                tc_paths.append(t_path)
            # 截图 URL 保存在数据库 notes 表正文（markdown 缓存里只有 *Screenshot-[mm:ss]* 标记）
            screenshot_names += _find_screenshots_in_db(task_id)

        covers = [covers_dir_files[n] for n in dict.fromkeys(cover_names) if n in covers_dir_files]
        if covers:
            categories.append({"id": "covers", "kind": "image",
                               "files": _decorate(covers, "/static/covers", "image", "covers")})

        screenshots = [screenshots_dir_files[n] for n in dict.fromkeys(screenshot_names)
                       if n in screenshots_dir_files]
        if screenshots:
            categories.append({"id": "screenshots", "kind": "image",
                               "files": _decorate(screenshots, "/static/screenshots", "image", "screenshots")})

        if frames_owner == vid:
            categories.append({"id": "frames", "kind": "image",
                               "files": _decorate(frame_files, "/media/output_frames", "image", "frames")})
        if grids_owner == vid:
            categories.append({"id": "grids", "kind": "image",
                               "files": _decorate(grid_files, "/media/grid_output", "image", "grids")})

        vt = [f for f in video_transcript_files if f"_{vid}_" in f["name"]]
        if vt:
            categories.append({"id": "video_transcripts", "kind": "text",
                               "files": _decorate(vt, "", "text", "video_transcripts", content_param=True)})

        tc_names = {p.name for p in tc_paths}
        tc_files = [f for f in note_json_md if f["name"] in tc_names]
        if tc_files:
            categories.append({"id": "transcripts", "kind": "text",
                               "files": _decorate(tc_files, "", "text", "transcripts", content_param=True)})

        note_names = {p.name for p in note_paths}
        note_files = [f for f in note_json_md if f["name"] in note_names]
        if note_files:
            categories.append({"id": "notes", "kind": "text",
                               "files": _decorate(note_files, "", "text", "notes", content_param=True)})

        title = None
        for tid in task_ids:
            data = _load_json(NOTE_OUTPUT_DIR / f"{tid}_audio.json")
            if data and data.get("title"):
                title = str(data["title"])
                break
        project_name = title[:40] if title else vid

        projects.append({
            "id": vid,
            "name": project_name,
            "video_id": vid,
            "platform": meta["platform"],
            "created_at": meta["created_at"],
            "files_total": sum(len(c["files"]) for c in categories),
            "categories": categories,
        })

    # ---------------- 共享区 ----------------
    used_screenshots = set()
    used_covers = set()
    used_vt = set()
    used_task_files = set()
    for p in projects:
        for c in p["categories"]:
            if c["id"] == "screenshots":
                used_screenshots.update(f["name"] for f in c["files"])
            elif c["id"] == "covers":
                used_covers.update(f["name"] for f in c["files"])
            elif c["id"] == "video_transcripts":
                used_vt.update(f["name"] for f in c["files"])
            elif c["id"] in ("transcripts", "notes"):
                used_task_files.update(f["name"] for f in c["files"])

    orphan_screenshots = [f for f in screenshots_dir_files.values() if f["name"] not in used_screenshots]
    orphan_covers = [f for f in covers_dir_files.values() if f["name"] not in used_covers]
    orphan_video_transcripts = [f for f in video_transcript_files if f["name"] not in used_vt]
    orphan_task_files = [
        f for f in note_json_md
        if f["name"] not in used_task_files
        and (f["name"].endswith("_transcript.json") or f["name"].endswith("_audio.json")
             or f["name"].endswith("_markdown.md"))
        and not any(f["name"].startswith(tid) for tid in task_ids_all)
    ]
    orphan_frames = frame_files if frames_owner is None else []
    orphan_grids = grid_files if grids_owner is None else []

    shared = []
    if orphan_frames:
        shared.append({"id": "frames", "kind": "image",
                       "files": _decorate(orphan_frames, "/media/output_frames", "image", "frames")})
    if orphan_grids:
        shared.append({"id": "grids", "kind": "image",
                       "files": _decorate(orphan_grids, "/media/grid_output", "image", "grids")})
    if orphan_screenshots:
        shared.append({"id": "screenshots", "kind": "image",
                       "files": _decorate(orphan_screenshots, "/static/screenshots", "image", "screenshots")})
    if orphan_covers:
        shared.append({"id": "covers", "kind": "image",
                       "files": _decorate(orphan_covers, "/static/covers", "image", "covers")})
    if orphan_video_transcripts:
        shared.append({"id": "video_transcripts", "kind": "text",
                       "files": _decorate(orphan_video_transcripts, "", "text", "video_transcripts",
                                          content_param=True)})
    if orphan_task_files:
        shared.append({"id": "transcripts", "kind": "text",
                       "files": _decorate(orphan_task_files, "", "text", "transcripts", content_param=True)})

    stats = {"projects": len(projects), "shared": sum(len(c["files"]) for c in shared)}
    for p in projects:
        for c in p["categories"]:
            stats[c["id"]] = stats.get(c["id"], 0) + len(c["files"])
    for c in shared:
        stats[c["id"]] = stats.get(c["id"], 0) + len(c["files"])

    return R.success(data={"projects": projects, "shared": shared, "stats": stats})


# ------------------ 删除 / 打开 ------------------
def _resolve_category_dir(category: str) -> Path:
    d = CATEGORY_DIRS.get(category)
    if not d:
        raise HTTPException(status_code=400, detail=f"未知分类: {category}")
    return d


def _safe_path(path: Path) -> Path:
    try:
        resolved = path.resolve()
    except OSError:
        raise HTTPException(status_code=400, detail="非法路径")
    for root in _ALLOWED_ROOTS:
        if resolved == root or resolved.is_relative_to(root):
            return resolved
    raise HTTPException(status_code=400, detail="不允许访问该路径")


def _project_category_files(project_id: str, category: str) -> List[dict]:
    """从最新列表解析项目内某分类的文件。"""
    data = _json_body_bytes(_build_assets())["data"]
    for p in data["projects"]:
        if p["id"] == project_id:
            for c in p["categories"]:
                if c["id"] == category:
                    return c["files"]
            return []
    return []


def _shared_category_files(category: str) -> List[dict]:
    data = _json_body_bytes(_build_assets())["data"]
    for c in data["shared"]:
        if c["id"] == category:
            return c["files"]
    return []


class DeleteRequest(BaseModel):
    scope: str                      # project | category | file
    project_id: Optional[str] = None
    category: Optional[str] = None
    file: Optional[str] = None


@router.post("/assets/delete")
def delete_asset(req: DeleteRequest):
    """按 scope 删除：project 整个项目 / category 整个分类（项目内或共享区）/ file 单个文件。"""
    if req.scope not in ("project", "category", "file"):
        raise HTTPException(status_code=400, detail="scope 必须是 project/category/file")
    if req.file and os.path.basename(req.file) != req.file:
        raise HTTPException(status_code=400, detail="非法的文件名")

    targets: List[Path] = []

    if req.scope == "file":
        if not req.category or not req.file:
            raise HTTPException(status_code=400, detail="缺少 category/file")
        d = _resolve_category_dir(req.category)
        targets.append(_safe_path(d / req.file))

    elif req.scope == "category":
        if not req.category:
            raise HTTPException(status_code=400, detail="缺少 category")
        d = _resolve_category_dir(req.category)
        if req.project_id:
            files = _project_category_files(req.project_id, req.category)
            if not files:
                raise HTTPException(status_code=404, detail="项目或分类不存在")
            targets = [_safe_path(d / f["name"]) for f in files]
        else:
            # 共享区分类：只删 shared 列表里的孤儿文件，绝不整目录扫
            files = _shared_category_files(req.category)
            if not files:
                raise HTTPException(status_code=404, detail="共享区分类不存在或为空")
            targets = [_safe_path(d / f["name"]) for f in files]

    elif req.scope == "project":
        if not req.project_id:
            raise HTTPException(status_code=400, detail="缺少 project_id")
        data = _json_body_bytes(_build_assets())["data"]
        for p in data["projects"]:
            if p["id"] == req.project_id:
                for c in p["categories"]:
                    d = _resolve_category_dir(c["id"])
                    targets.extend(_safe_path(d / f["name"]) for f in c["files"])
                break
        if not targets:
            raise HTTPException(status_code=404, detail="项目不存在或没有可删除的文件")

    removed = 0
    errors: List[str] = []
    for t in targets:
        try:
            if t.exists() and t.is_file():
                t.unlink()
                removed += 1
        except OSError as exc:
            errors.append(f"{t.name}: {exc}")

    msg = f"已删除 {removed} 个文件" + (f"，失败 {len(errors)} 个" if errors else "")
    return R.success(data={"removed": removed, "errors": errors}, msg=msg)


class OpenRequest(BaseModel):
    scope: str                      # project | category | file
    project_id: Optional[str] = None
    category: Optional[str] = None
    file: Optional[str] = None


def _open_in_explorer(path: Path, select_file: bool = False):
    system = sys.platform
    try:
        if system == "win32":
            if select_file and path.is_file():
                subprocess.Popen(["explorer", "/select,", str(path)])
            else:
                os.startfile(str(path))  # type: ignore[attr-defined]
        elif system == "darwin":
            if select_file and path.is_file():
                subprocess.Popen(["open", "-R", str(path)])
            else:
                subprocess.Popen(["open", str(path)])
        else:
            subprocess.Popen(["xdg-open", str(path)])
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"打开文件管理器失败: {exc}")


@router.post("/assets/open")
def open_asset(req: OpenRequest):
    """在文件管理器中打开：project 打开视频所在目录 / category 打开分类目录 / file 选中单个文件。"""
    if req.file and os.path.basename(req.file) != req.file:
        raise HTTPException(status_code=400, detail="非法的文件名")

    if req.scope == "project":
        if not req.project_id:
            raise HTTPException(status_code=400, detail="缺少 project_id")
        d = _safe_path(MEDIA_DIR)
        target = None
        for ext in ("mp4", "mkv", "webm", "mov", "flv", "avi", "mp3", "m4a", "wav"):
            cand = d / f"{req.project_id}.{ext}"
            if cand.exists():
                target = cand
                break
        if target:
            _open_in_explorer(target, select_file=True)
        else:
            _open_in_explorer(d, select_file=False)
        return R.success(msg="已打开所在位置")

    if req.scope == "category":
        if not req.category:
            raise HTTPException(status_code=400, detail="缺少 category")
        d = _resolve_category_dir(req.category)
        _open_in_explorer(_safe_path(d), select_file=False)
        return R.success(msg="已打开所在位置")

    if req.scope == "file":
        if not req.category or not req.file:
            raise HTTPException(status_code=400, detail="缺少 category/file")
        d = _resolve_category_dir(req.category)
        target = _safe_path(d / req.file)
        if not target.exists():
            raise HTTPException(status_code=404, detail="文件不存在")
        _open_in_explorer(target, select_file=True)
        return R.success(msg="已打开所在位置")

    raise HTTPException(status_code=400, detail="scope 必须是 project/category/file")


# ------------------ 列表 & 内容 ------------------
@router.get("/assets/list")
def list_assets():
    return _build_assets()


@router.get("/assets/content")
def get_asset_content(file: str):
    """读取 note_results 下的文本类文件内容（仅白名单扩展名，防路径穿越）。"""
    if not file or os.path.basename(file) != file:
        raise HTTPException(status_code=400, detail="非法的文件名")

    target = (NOTE_OUTPUT_DIR / file).resolve()
    base = NOTE_OUTPUT_DIR.resolve()
    if not target.is_relative_to(base):
        raise HTTPException(status_code=400, detail="不允许访问该路径")

    if target.suffix.lower() not in _TEXT_EXTS:
        raise HTTPException(status_code=400, detail="不支持的文件类型")

    if not target.exists() or not target.is_file():
        raise HTTPException(status_code=404, detail="文件不存在")

    try:
        content = target.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        raise HTTPException(status_code=500, detail=f"读取失败: {exc}")

    return R.success(data={"name": file, "content": content})
