"""下载引擎配置管理：lux / yt-dlp.exe 所在目录（融合 VideoDownloader 的下载引擎）。

持久化在数据库 app_config 表（key="download_engine"）。未手动配置时自动探测
VideoDownloader（从 SmartSub 提取的独立下载模块）的 bin 目录，有引擎直接复用。
"""
from pathlib import Path
from typing import Any, Dict

from app.db.app_config_dao import load_value, set_value

# VideoDownloader 默认安装位置（本机目录，引擎即在此处）
_DEFAULT_VD_DIR = Path(r"C:\Users\wzq\Doubao\chats\2026-09-30\new-chat-1\VideoDownloader")
_ENGINE_BIN_DIR = "bin"


class EngineConfigManager:
    """管理下载引擎目录配置，提供就绪状态检测。"""

    _KEY = "download_engine"

    def __init__(self, filepath: str = "config/download_engine.json"):
        self._legacy_path = filepath

    def _read(self) -> dict:
        return load_value(self._KEY, self._legacy_path, {}) or {}

    def _write(self, data: dict):
        set_value(self._KEY, data)

    def default_dir(self) -> str:
        """VideoDownloader 的 bin 目录（仅当存在时返回）。"""
        d = _DEFAULT_VD_DIR / _ENGINE_BIN_DIR
        return str(d) if d.is_dir() else ""

    def get_engine_dir(self) -> str:
        """返回引擎目录；未配置或目录不存在时自动探测默认目录。"""
        data = self._read()
        cfg = (data.get("engine_dir") or "").strip()
        if cfg and Path(cfg).is_dir():
            return cfg
        return self.default_dir()

    def set_engine_dir(self, path: str) -> Dict[str, Any]:
        """保存引擎目录并返回最新检测状态。"""
        data = self._read()
        data["engine_dir"] = (path or "").strip()
        self._write(data)
        return self.detect()

    def detect(self) -> Dict[str, Any]:
        """引擎就绪状态：lux.exe / yt-dlp.exe 是否可用。"""
        engine_dir = self.get_engine_dir()

        def has(name: str) -> bool:
            return bool(engine_dir and (Path(engine_dir) / name).is_file())

        return {
            "engine_dir": engine_dir,
            "default_dir": self.default_dir(),
            "lux_installed": has("lux.exe"),
            "ytdlp_exe_installed": has("yt-dlp.exe"),
            # VideoMemo 自带 Python yt-dlp 包，永远可作兜底
            "ytdlp_python": True,
            # yt-dlp 整体就绪：exe 或内置 Python 包任一可用（内置包恒可用，故恒为 True）
            "ytdlp_ready": True,
        }
