"""微信视频号下载服务管理（对接 ltaoo/wx_channels_download）。

wx_channels_download（二进制名 wx_video_download）是一个 Go 编写的微信视频号下载器：
- 启动后自动安装根证书（首次，需管理员权限 → 弹出 UAC）、设置系统代理，
  并在微信 PC 客户端视频号页面注入「下载」按钮；
- API 服务（自带 Web 前端）：http://127.0.0.1:2022
- 代理服务：127.0.0.1:2023
- 下载目录：由该服务 config.yaml 的 download.dir 决定（默认 %UserDownloads%）

本模块只负责「进程 + 状态 + 下载目录」管理，供前端「微信视频号下载」一格使用。
路径均可用环境变量覆盖（写入 backend/.env 即可）：
    WXCHANNELS_BIN            二进制路径
    WXCHANNELS_API            API 地址（默认 http://127.0.0.1:2022）
    WXCHANNELS_DOWNLOAD_DIR   下载目录
"""
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional

import httpx

from app.utils.logger import get_logger

logger = get_logger(__name__)

_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_DEFAULT_BIN = r"I:\70_applist\wx_channels_download\bin\wx_video_download.exe"
_DEFAULT_API = "http://127.0.0.1:2022"
_DEFAULT_DOWNLOAD_DIR = os.path.join(_BACKEND_DIR, "data", "wxchannels")


class WxChannelsManager:
    """微信视频号下载服务（wx_video_download）进程与文件管理。"""

    def __init__(self):
        self.bin = os.getenv("WXCHANNELS_BIN", _DEFAULT_BIN)
        self.api = os.getenv("WXCHANNELS_API", _DEFAULT_API).rstrip("/")
        self.download_dir = os.getenv("WXCHANNELS_DOWNLOAD_DIR", _DEFAULT_DOWNLOAD_DIR)

    # ---------------- 基础 ----------------
    def binary_exists(self) -> bool:
        return os.path.isfile(self.bin)

    # ---------------- 状态 ----------------
    def _http_status(self) -> Optional[dict]:
        """GET /api/status；服务未启动/不可达时返回 None。"""
        try:
            r = httpx.get(f"{self.api}/api/status", timeout=2.0)
            r.raise_for_status()
            data = (r.json() or {}).get("data") or {}
            api = data.get("api") or {}
            proxy = data.get("proxy") or {}
            return {
                "api_addr": api.get("addr", ""),
                "api_listening": bool(api.get("listening")),
                "proxy_addr": proxy.get("addr", ""),
                "proxy_listening": bool(proxy.get("listening")),
                "version": str(data.get("version") or ""),
            }
        except Exception as e:
            logger.warning(f"wx_channels API 不可达: {e}")
            return None

    def _process_pid(self) -> Optional[int]:
        """按进程名查 wx_video_download.exe 的 PID。"""
        try:
            flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
            out = subprocess.run(
                ["tasklist", "/FI", "IMAGENAME eq wx_video_download.exe", "/FO", "CSV", "/NH"],
                capture_output=True, text=True, timeout=10, creationflags=flags,
            ).stdout
            for line in out.splitlines():
                parts = [p.strip().strip('"') for p in line.strip().split('","')]
                if parts and "wx_video_download" in parts[0]:
                    try:
                        return int(parts[1])
                    except (ValueError, IndexError):
                        continue
        except Exception as e:
            logger.warning(f"tasklist 查询失败: {e}")
        return None

    def status(self) -> dict:
        http = self._http_status()
        pid = self._process_pid()
        api_listening = bool(http and http["api_listening"])
        return {
            "binary": self.bin,
            "binary_exists": self.binary_exists(),
            "pid": pid,
            "running": bool(pid is not None) or api_listening,
            "api_addr": (http or {}).get("api_addr") or "",
            "api_listening": api_listening,
            "proxy_addr": (http or {}).get("proxy_addr", ""),
            "proxy_listening": bool(http and http["proxy_listening"]),
            "version": (http or {}).get("version", ""),
            "download_dir": self.download_dir,
            "download_dir_exists": os.path.isdir(self.download_dir),
        }

    # ---------------- 启停 ----------------
    def start(self) -> dict:
        if not self.binary_exists():
            raise FileNotFoundError(
                f"未找到 wx_video_download.exe：{self.bin}\n"
                f"请先下载官方 v260907 构建包并解压到 bin 目录，"
                f"或在 backend/.env 中配置 WXCHANNELS_BIN"
            )
        st = self.status()
        if st["running"]:
            logger.info("wx_channels 服务已在运行，无需重复启动")
            return st

        # 独立控制台启动：用户能看到「代理服务启动成功」提示并可 Ctrl+C 退出；
        # 首次运行（装根证书）会由程序自身弹出 UAC，需用户点「是」。
        flags = subprocess.CREATE_NEW_CONSOLE if sys.platform == "win32" else 0
        cwd = os.path.dirname(self.bin) or None
        proc = subprocess.Popen([self.bin], cwd=cwd, creationflags=flags)
        logger.info(f"wx_channels 服务已拉起 pid={proc.pid}，等待 API 就绪（首次需确认 UAC）…")

        # 最多等 10 秒（首次装证书 + 提权较慢）
        for _ in range(20):
            time.sleep(0.5)
            st = self.status()
            if st["api_listening"]:
                return st
        return self.status()

    def stop(self) -> dict:
        # 1) 优雅停掉代理服务（其 Stop 会先清除指向本服务的系统代理，避免断网残留）
        if self._http_status():
            try:
                httpx.post(f"{self.api}/api/service/stop", json={"name": "proxy"}, timeout=2.0)
            except Exception as e:
                logger.warning(f"调用 wx API 停止代理失败（继续强停进程）: {e}")
        # 2) 结束进程
        pid = self._process_pid()
        if pid is not None:
            try:
                flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
                subprocess.run(
                    ["taskkill", "/PID", str(pid), "/F"],
                    capture_output=True, text=True, timeout=10, creationflags=flags,
                )
            except Exception as e:
                logger.warning(f"taskkill 失败: {e}")
        time.sleep(0.6)
        return self.status()

    # ---------------- 下载目录 ----------------
    _MEDIA_EXTS = {
        ".mp4", ".mkv", ".webm", ".mov", ".flv", ".avi", ".ts",
        ".m4a", ".mp3", ".aac", ".wav", ".flac", ".opus",
    }

    def list_downloads(self, limit: int = 30) -> list:
        """列出下载目录里最近的媒体文件（按修改时间倒序）。"""
        d = Path(self.download_dir)
        if not d.is_dir():
            return []
        items = []
        for p in d.iterdir():
            if p.is_file() and p.suffix.lower() in self._MEDIA_EXTS:
                try:
                    st = p.stat()
                except OSError:
                    continue
                items.append({
                    "path": str(p),
                    "name": p.name,
                    "size": st.st_size,
                    "mtime": st.st_mtime,
                    "ext": p.suffix.lower(),
                })
        items.sort(key=lambda x: x["mtime"], reverse=True)
        return items[: max(1, min(int(limit), 200))]

    # ---------------- 分享链接一键下载 ----------------
    def download_from_share(self, share_url: str) -> dict:
        """从视频号分享链接直接下载为可播放 MP4。

        链路：微信通道解析(parse_sph) → 拿带票据直链 + 解密 key → wx 服务 /play 代理下载并解密。
        前置条件：wx 服务已启动（api_listening）且微信通道已连接
        （微信中打开过任意视频号页面，通道建立后保持在线即可）。
        """
        st = self.status()
        if not st["api_listening"]:
            raise RuntimeError("wx_channels 服务未启动，请先点「启动服务」（首次会弹 UAC 确认证书）")

        # 1) 通道检查
        try:
            r = httpx.get(f"{self.api}/api/channels/status", timeout=5.0)
            r.raise_for_status()
            available = bool(((r.json() or {}).get("data") or {}).get("available"))
        except Exception as e:
            raise RuntimeError(f"无法连接 wx_channels API：{e}")
        if not available:
            raise RuntimeError(
                "微信通道未连接：请在微信里打开一次视频号页面（分享链接→点击进入），"
                "并保持微信在线。通道建立后即可直接粘贴链接下载。"
            )

        # 2) 解析分享链接（走微信通道）
        try:
            r = httpx.get(
                f"{self.api}/api/channels/parse_sph",
                params={"url": share_url.strip()},
                timeout=60.0,
            )
            r.raise_for_status()
            payload = (r.json() or {}).get("data") or {}
            err_code = payload.get("errCode")
            if err_code not in (None, 0):
                raise RuntimeError(f"解析失败：{payload.get('errMsg') or '未知错误'}")
            inner = payload.get("data") or {}
            obj = inner.get("object") or {}
        except RuntimeError:
            raise
        except Exception as e:
            raise RuntimeError(f"调用解析接口失败：{e}")

        if not obj:
            raise RuntimeError("解析结果为空，链接可能已失效，请重新获取分享链接")

        object_desc = obj.get("objectDesc") or {}
        title = (
            (object_desc.get("flowCardDesc") or {}).get("description")
            or object_desc.get("description")
            or obj.get("description")
            or "微信视频号"
        )
        author = obj.get("nickname") or ""
        media_list = object_desc.get("media") or []
        media = media_list[0] if media_list else {}
        media_url = media.get("url") or ""
        url_token = media.get("urlToken") or ""
        decode_key = str(media.get("decodeKey") or "")
        if not media_url:
            raise RuntimeError("未能在解析结果中找到视频直链（该内容可能不支持下载）")

        # urlToken 形如 "&token=...&basedata=..."，直接拼在直链后面
        full_url = media_url + url_token

        # 3) 经 wx 服务 /play 代理下载并解密为 MP4
        os.makedirs(self.download_dir, exist_ok=True)
        safe_title = _sanitize_filename(title) or "weixin-channel"
        safe_author = _sanitize_filename(author)
        name = f"{safe_title}" + (f"-{safe_author}" if safe_author else "") + ".mp4"
        out = os.path.join(self.download_dir, name)
        logger.info(f"wx_channels 分享链接下载开始: {name}")
        try:
            with httpx.stream(
                "GET",
                f"{self.api}/play",
                params={"url": full_url, "key": decode_key},
                timeout=300.0,
                follow_redirects=True,
            ) as resp:
                resp.raise_for_status()
                total = 0
                with open(out, "wb") as f:
                    for chunk in resp.iter_bytes(chunk_size=1 << 20):
                        f.write(chunk)
                        total += len(chunk)
        except Exception as e:
            raise RuntimeError(f"下载失败：{e}")
        if total == 0:
            raise RuntimeError("下载内容为空（票据可能已过期），请重新尝试")

        logger.info(f"wx_channels 分享链接下载完成: {name} ({total} bytes)")
        return {"file": out, "name": name, "size": total, "title": title, "author": author}


def _sanitize_filename(s: str) -> str:
    """去掉 Windows 文件名非法字符，并截断到合理长度。"""
    s = re.sub(r'[\\/:*?"<>|\x00-\x1f]', "", str(s)).strip()
    return s[:80]


manager = WxChannelsManager()
