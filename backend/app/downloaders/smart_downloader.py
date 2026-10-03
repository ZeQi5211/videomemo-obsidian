"""双引擎智能下载器：融合 VideoDownloader（yt-dlp + lux）的下载能力。

按站点自动路由下载引擎：
- lux（国内站：B站 / 抖音 / 小红书 / 微博）→ 优先 lux.exe 下载视频
- yt-dlp（YouTube / X / Instagram / TikTok 等）→ yt-dlp.exe，无则用 Python yt-dlp 包
  （音频提取统一走 yt-dlp 并转 mp3）

输出统一命名到 data/data：
- 音频：{video_id}.mp3
- 视频：{video_id}.mp4（或 lux 输出的源扩展名）
与转写、笔记生成、中间产物资产管理完全兼容。

字幕/元信息委托给原平台下载器（如 B 站官方字幕 player API）。
"""
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional

import yt_dlp

from app.downloaders.base import Downloader
from app.enmus.note_enums import DownloadQuality
from app.models.audio_model import AudioDownloadResult
from app.services.engine_config_manager import EngineConfigManager
from app.utils.path_helper import get_data_dir
from app.utils.url_parser import extract_video_id

# 站点 → 引擎路由（与 VideoDownloader 保持一致）
LUX_DOMAINS = ["bilibili.com", "b23.tv", "douyin.com", "xiaohongshu.com",
               "xhslink.com", "weibo.com", "weibo.cn"]
YT_DLP_DOMAINS = ["youtube.com", "youtu.be", "twitter.com", "x.com",
                  "instagram.com", "tiktok.com"]

# 清晰度映射（yt-dlp: -f 表达式）。注意：lux 没有 -q 质量档位，
# 也不按高度筛选流，只能选流 ID/序号；默认不传 -f 即下载最佳质量流。
YTDLP_QUALITY_FMT = {
    "audio": "bestaudio/best",
    "best": "bestvideo+bestaudio/best",
    "1080p": "bv*[height<=1080]+ba/b[height<=1080]/best",
    "720p": "bv*[height<=720]+ba/b[height<=720]/best",
    "480p": "bv*[height<=480]+ba/b[height<=480]/best",
    "360p": "bv*[height<=360]+ba/b[height<=360]/best",
}

_VIDEO_EXTS = {".mp4", ".mkv", ".webm", ".mov", ".flv", ".avi", ".ts"}


def _proxy_for_ytdlp() -> Optional[str]:
    try:
        from app.services.proxy_config_manager import ProxyConfigManager
        return ProxyConfigManager().get_proxy_url() or None
    except Exception:
        return None


class SmartDownloader(Downloader):
    """yt-dlp + lux 双引擎下载器（下载模式：engine）。

    engine_choice 决定走哪条引擎通道：
    - ytdlp（默认）：音频/视频都走 yt-dlp（exe 优先，内置 Python 包兜底）
    - lux：音频/视频都走 lux.exe（未安装直接报错，不自动切换）
    """

    def __init__(self, platform: str = "", video_quality: str = "audio",
                 engine_choice: str = "ytdlp"):
        super().__init__()
        self.platform = platform or ""
        self.video_quality = video_quality or "audio"
        self.engine_choice = engine_choice or "ytdlp"
        self._inner = None

    # ---------------- 引擎与路由 ----------------
    def _engine_path(self, name: str) -> Optional[str]:
        d = EngineConfigManager().get_engine_dir()
        if not d:
            return None
        p = Path(d) / name
        return str(p) if p.is_file() else None

    def _use_lux(self, url: str) -> bool:
        return any(dom in url for dom in LUX_DOMAINS)

    def _video_id_from_info(self, info: dict, url: str) -> str:
        vid = info.get("id") or extract_video_id(url, self.platform)
        return str(vid) if vid else f"video_{int(time.time())}"

    def _platform_from_info(self, info: dict) -> str:
        if self.platform:
            return self.platform
        key = (info.get("extractor_key") or "").lower()
        if "bilibili" in key:
            return "bilibili"
        if "youtube" in key:
            return "youtube"
        if "douyin" in key or "tiktok" in key:
            return "douyin"
        return key or "smart"

    # ---------------- 元信息探测 ----------------
    def _probe_metadata(self, url: str) -> dict:
        """用 yt-dlp 探测标题/封面/时长/id；失败返回空 dict。"""
        opts = {
            "skip_download": True,
            "noplaylist": True,
            "quiet": True,
            "no_warnings": True,
            "nocheckcertificate": True,
        }
        proxy = _proxy_for_ytdlp()
        if proxy:
            opts["proxy"] = proxy
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                return ydl.extract_info(url, download=False) or {}
        except Exception:
            return {}

    def _make_result(self, info: dict, file_path: str, url: str) -> AudioDownloadResult:
        video_id = self._video_id_from_info(info, url)
        platform = self._platform_from_info(info)
        return AudioDownloadResult(
            file_path=file_path,
            title=info.get("title") or video_id,
            duration=info.get("duration", 0),
            cover_url=info.get("thumbnail") or "",
            platform=platform,
            video_id=video_id,
            raw_info={
                "tags": info.get("tags") or [],
                # 作者信息：yt-dlp 探测元信息里有 uploader/channel，保留给「作者/」标签用
                "uploader": info.get("uploader") or "",
                "uploader_id": info.get("uploader_id") or "",
                "channel": info.get("channel") or "",
                "channel_id": info.get("channel_id") or "",
                "title": info.get("title") or "",
                "thumbnail": info.get("thumbnail") or "",
                "duration": info.get("duration") or 0,
            },
            video_path=None,
        )

    # ---------------- 下载实现 ----------------
    def _download_audio(self, url: str, out_dir: str, video_id: str,
                        info: Optional[dict] = None) -> str:
        """下载音频并转 mp3，返回路径。按 engine_choice 走对应引擎通道。"""
        target = os.path.join(out_dir, f"{video_id}.mp3")
        if os.path.exists(target):
            return target
        if self.engine_choice == "lux":
            lux = self._engine_path("lux.exe")
            if not lux:
                raise RuntimeError("lux 引擎未安装，无法使用 lux 通道下载音频，请先安装 lux")
            path = self._audio_via_lux(url, lux, out_dir, video_id)
            # lux 无字幕能力，用 yt-dlp 单独补拉官方字幕（失败不影响下载）
            self._try_download_subtitles(url, out_dir, video_id, info or {})
            return path
        # ytdlp 通道
        exe = self._engine_path("yt-dlp.exe")
        if exe:
            return self._audio_via_ytdlp_exe(url, exe, out_dir, video_id, info)
        return self._audio_via_ytdlp_python(url, out_dir, video_id, info)

    _AUDIO_EXTS = {".m4a", ".mp3", ".aac", ".webm", ".opus", ".wav", ".flac"}

    def _audio_via_lux(self, url: str, lux: str, out_dir: str, video_id: str) -> str:
        """lux 下载视频（默认最佳流），再用 ffmpeg 提取音频转 mp3。

        为什么不用 lux 的 --audio-only：
          - 旧代码传 `-a`（lux 不支持的参数）直接报 flag 错误；
          - --audio-only 只对存在独立音频流的站点有效，部分 B 站视频只有
            音视频合流，会报 "No audio stream found"。
        统一走「lux 下载 + ffmpeg 抽音转 mp3」对两种视频都成立。
        """
        cmd = [lux, "-o", out_dir, url]
        before = {p.name for p in Path(out_dir).iterdir() if p.is_file()}
        self._run(cmd)
        newest = None
        for p in Path(out_dir).iterdir():
            if p.is_file() and p.name not in before and p.suffix.lower() in (self._AUDIO_EXTS | _VIDEO_EXTS):
                if newest is None or p.stat().st_mtime > newest.stat().st_mtime:
                    newest = p
        if newest is None:
            raise RuntimeError("lux 下载完成但未找到输出文件")
        if newest.suffix.lower() in self._AUDIO_EXTS and newest.suffix.lower() == ".mp3":
            target = newest.with_name(f"{video_id}.mp3")
            if target != newest:
                newest.replace(target)
            return str(target)
        target = os.path.join(out_dir, f"{video_id}.mp3")
        self._run(["ffmpeg", "-y", "-i", str(newest),
                   "-codec:a", "libmp3lame", "-qscale:a", "5", target])
        newest.unlink(missing_ok=True)
        return target

    def _base_ytdlp_args(self, url: str, out_dir: str, video_id: str) -> list:
        args = ["--newline", "--no-warnings", "--noplaylist",
                "-o", os.path.join(out_dir, "%(id)s.%(ext)s")]
        proxy = _proxy_for_ytdlp()
        if proxy:
            args += ["--proxy", proxy]
        return args

    # ---------------- 字幕（原版 VideoDownloader 拉字幕逻辑） ----------------
    @staticmethod
    def _pick_sub_langs(info: dict) -> tuple:
        """完全照搬原版 VideoDownloader：人工字幕全要；
        只有自动字幕时优先原语言（*-orig），再退到视频语言、再 en/zh，最后取第一个。"""
        manual = [k for k in (info.get("subtitles") or {}) if k != "live_chat"]
        if manual:
            return manual, False
        auto = info.get("automatic_captions") or {}
        if not auto:
            return [], False
        orig = [k for k in auto if k.endswith("-orig")]
        if orig:
            return orig[:1], True
        lang = info.get("language")
        if lang and lang in auto:
            return [lang], True
        for k in auto:
            if k.startswith(("en", "zh")):
                return [k], True
        return [next(iter(auto))], True

    def _subtitle_exe_args(self, info: dict) -> list:
        """yt-dlp.exe 字幕参数（原版同款），无可用字幕返回 []。"""
        langs, is_auto = self._pick_sub_langs(info or {})
        if not langs:
            return []
        args = ["--write-auto-subs" if is_auto else "--write-subs",
                "--sub-langs", ",".join(langs),
                "--sub-format", "vtt/srt/best",
                "--convert-subs", "srt"]
        return args

    def _subtitle_python_opts(self, info: dict) -> dict:
        """Python yt-dlp 库的字幕参数，无可用字幕返回 {}。"""
        langs, is_auto = self._pick_sub_langs(info or {})
        if not langs:
            return {}
        opts = {
            "writesubtitles": not is_auto,
            "writeautomaticsub": is_auto,
            "subtitleslangs": langs,
            "postprocessors": [{"key": "FFmpegSubtitlesConvertor", "format": "srt"}],
        }
        return opts

    def _try_download_subtitles(self, url: str, out_dir: str, video_id: str, info: dict):
        """lux 通道的补充：lux 本身不支持字幕，用 yt-dlp 单独拉官方字幕并转 srt。
        失败仅记日志，绝不影响主下载流程。"""
        try:
            langs, is_auto = self._pick_sub_langs(info or {})
            if not langs:
                self._log(f"未检测到可用字幕: {url}")
                return
            opts = {
                "skip_download": True,
                "noplaylist": True,
                "quiet": True,
                "no_warnings": True,
                "outtmpl": os.path.join(out_dir, "%(id)s.%(ext)s"),
                "writesubtitles": not is_auto,
                "writeautomaticsub": is_auto,
                "subtitleslangs": langs,
                "postprocessors": [{"key": "FFmpegSubtitlesConvertor", "format": "srt"}],
            }
            proxy = _proxy_for_ytdlp()
            if proxy:
                opts["proxy"] = proxy
            with yt_dlp.YoutubeDL(opts) as ydl:
                ydl.extract_info(url, download=True)
            self._log(f"已下载字幕 {','.join(langs)}{'（自动字幕）' if is_auto else '（官方字幕）'}: {url}")
        except Exception as e:
            self._log(f"补充下载字幕失败（不影响主下载）: {e}")

    def _audio_via_ytdlp_exe(self, url: str, exe: str, out_dir: str, video_id: str,
                             info: Optional[dict] = None) -> str:
        cmd = [exe, "-x", "--audio-format", "mp3", "--audio-quality", "5"]
        cmd += self._subtitle_exe_args(info or {})
        cmd += self._base_ytdlp_args(url, out_dir, video_id)
        cmd.append(url)
        self._run(cmd)
        target = os.path.join(out_dir, f"{video_id}.mp3")
        if not os.path.exists(target):
            raise RuntimeError(f"yt-dlp 音频下载完成但未找到文件: {target}")
        return target

    def _audio_via_ytdlp_python(self, url: str, out_dir: str, video_id: str,
                                 info: Optional[dict] = None) -> str:
        opts = {
            "format": "bestaudio/best",
            "outtmpl": os.path.join(out_dir, "%(id)s.%(ext)s"),
            "noplaylist": True,
            "quiet": True,
            "no_warnings": True,
            "postprocessors": [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "5",
            }],
        }
        opts.update(self._subtitle_python_opts(info or {}))
        proxy = _proxy_for_ytdlp()
        if proxy:
            opts["proxy"] = proxy
        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.extract_info(url, download=True)
        target = os.path.join(out_dir, f"{video_id}.mp3")
        if not os.path.exists(target):
            raise RuntimeError(f"yt-dlp 音频下载完成但未找到文件: {target}")
        return target

    def _download_video(self, url: str, out_dir: str, video_id: str,
                        info: Optional[dict] = None) -> str:
        """下载视频。按 engine_choice 走对应引擎通道；通道引擎缺失直接报错。"""
        # 已存在（mp4 或任意视频扩展名）直接复用
        for p in Path(out_dir).glob(f"{video_id}.*"):
            if p.is_file() and p.suffix.lower() in _VIDEO_EXTS:
                return str(p)

        if self.engine_choice == "lux":
            lux = self._engine_path("lux.exe")
            if not lux:
                raise RuntimeError("lux 引擎未安装，无法使用 lux 通道下载视频，请先安装 lux")
            path = self._video_via_lux(url, lux, out_dir, video_id)
            # lux 无字幕能力，用 yt-dlp 单独补拉官方字幕（失败不影响下载）
            self._try_download_subtitles(url, out_dir, video_id, info or {})
            return path

        exe = self._engine_path("yt-dlp.exe")
        if exe:
            return self._video_via_ytdlp_exe(url, exe, out_dir, video_id, info)
        return self._video_via_ytdlp_python(url, out_dir, video_id, info)

    def _video_via_lux(self, url: str, lux: str, out_dir: str, video_id: str) -> str:
        # lux 没有 -q 质量档位（旧代码传 -q 导致 "flag provided but not defined: -q"），
        # 也不支持按高度筛选；不传 -f 时 lux 默认下载最佳质量流。
        cmd = [lux, "-o", out_dir, url]
        # 记录下载前目录快照，用于识别 lux 新生成的文件
        before = {p.name for p in Path(out_dir).iterdir() if p.is_file()}
        self._run(cmd)
        newest = None
        for p in Path(out_dir).iterdir():
            if p.is_file() and p.name not in before and p.suffix.lower() in _VIDEO_EXTS:
                if newest is None or p.stat().st_mtime > newest.stat().st_mtime:
                    newest = p
        if newest is None:
            raise RuntimeError("lux 下载完成但未找到输出文件")
        target = newest.with_name(f"{video_id}{newest.suffix.lower()}")
        if target != newest:
            newest.replace(target)
        return str(target)

    def _video_via_ytdlp_exe(self, url: str, exe: str, out_dir: str, video_id: str,
                             info: Optional[dict] = None) -> str:
        fmt = YTDLP_QUALITY_FMT.get(self.video_quality, YTDLP_QUALITY_FMT["best"])
        cmd = [exe, "-f", fmt, "--merge-output-format", "mp4", "--fragment-retries", "3", "--continue"]
        cmd += self._subtitle_exe_args(info or {})
        cmd += self._base_ytdlp_args(url, out_dir, video_id)
        cmd.append(url)
        self._run(cmd)
        target = os.path.join(out_dir, f"{video_id}.mp4")
        if not os.path.exists(target):
            raise RuntimeError(f"yt-dlp 视频下载完成但未找到文件: {target}")
        return target

    def _video_via_ytdlp_python(self, url: str, out_dir: str, video_id: str,
                                info: Optional[dict] = None) -> str:
        fmt = YTDLP_QUALITY_FMT.get(self.video_quality, YTDLP_QUALITY_FMT["best"])
        opts = {
            "format": fmt,
            "outtmpl": os.path.join(out_dir, "%(id)s.%(ext)s"),
            "noplaylist": True,
            "quiet": True,
            "no_warnings": True,
            "merge_output_format": "mp4",
            "fragment_retries": 3,
            "continuedl": True,
        }
        opts.update(self._subtitle_python_opts(info or {}))
        proxy = _proxy_for_ytdlp()
        if proxy:
            opts["proxy"] = proxy
        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.extract_info(url, download=True)
        target = os.path.join(out_dir, f"{video_id}.mp4")
        if not os.path.exists(target):
            # 兜底：找任意 {video_id}.* 视频文件
            for p in Path(out_dir).glob(f"{video_id}.*"):
                if p.is_file() and p.suffix.lower() in _VIDEO_EXTS:
                    return str(p)
            raise RuntimeError(f"yt-dlp 视频下载完成但未找到文件: {target}")
        return target

    def _run(self, cmd: list, timeout: int = 3600):
        kwargs = {}
        if sys.platform == "win32":
            kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
        proc = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            **kwargs,
        )
        if proc.returncode != 0:
            tail = (proc.stdout or "")[-800:]
            raise RuntimeError(f"引擎退出码 {proc.returncode}: {tail}")

    def _log(self, msg: str):
        try:
            from app.utils.logger import get_logger
            get_logger(__name__).info(f"[SmartDownloader] {msg}")
        except Exception:
            pass

    # ---------------- Downloader 接口 ----------------
    def download(
        self,
        video_url: str,
        output_dir: Optional[str] = None,
        quality: DownloadQuality = "fast",
        need_video: Optional[bool] = False,
        skip_download: bool = False,
    ) -> AudioDownloadResult:
        if output_dir is None:
            output_dir = get_data_dir()
        os.makedirs(output_dir, exist_ok=True)

        info = self._probe_metadata(video_url)
        if skip_download:
            return self._make_result(info, "", video_url)

        video_id = self._video_id_from_info(info, video_url)
        audio_path = self._download_audio(video_url, output_dir, video_id, info)
        result = self._make_result(info, audio_path, video_url)
        result.video_path = None
        return result

    def download_video(self, video_url: str, output_dir: Optional[str] = None) -> str:
        if output_dir is None:
            output_dir = get_data_dir()
        os.makedirs(output_dir, exist_ok=True)

        info = self._probe_metadata(video_url)
        video_id = self._video_id_from_info(info, video_url)
        return self._download_video(video_url, output_dir, video_id, info)

    def download_subtitles(self, video_url: str, output_dir: Optional[str] = None,
                           langs: list = None):
        """优先委托原平台下载器（如 B 站官方字幕 player API）。"""
        if self.platform:
            try:
                from app.services.constant import SUPPORT_PLATFORM_MAP
                inner = SUPPORT_PLATFORM_MAP.get(self.platform)
                if inner and hasattr(inner, "download_subtitles"):
                    result = inner.download_subtitles(video_url, output_dir, langs)
                    if result:
                        return result
            except Exception as e:
                self._log(f"委托平台字幕失败: {e}")
        return None
