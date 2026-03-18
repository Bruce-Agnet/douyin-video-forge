"""视频处理 + 环境检查模块：2 个工具。"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from typing import Any

import httpx
from fastmcp import FastMCP
from fastmcp.exceptions import ToolError

video_server = FastMCP("Video")


@video_server.tool()
async def video_concat(
    video_paths: list[str],
    output_path: str,
    bgm_path: str = "",
    bgm_volume: float = 0.3,
) -> dict[str, str]:
    """使用 FFmpeg 拼接多段视频并可选叠加 BGM。

    Args:
        video_paths: 视频文件路径列表（按顺序拼接）
        output_path: 输出文件路径
        bgm_path: BGM 音频文件路径（可选）
        bgm_volume: BGM 音量 0.0-1.0（默认0.3）
    """
    if not video_paths:
        raise ToolError("视频路径列表不能为空。")

    for p in video_paths:
        if not os.path.isfile(p):
            raise ToolError(f"视频文件不存在: {p}")

    if bgm_path and not os.path.isfile(bgm_path):
        raise ToolError(f"BGM 文件不存在: {bgm_path}")

    # 确保输出目录存在
    output_dir = os.path.dirname(output_path)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)

    # 创建 concat 文件列表
    tmpdir = tempfile.mkdtemp(prefix="video_concat_")
    filelist_path = os.path.join(tmpdir, "filelist.txt")
    with open(filelist_path, "w") as f:
        for vp in video_paths:
            f.write(f"file '{vp}'\n")

    if bgm_path:
        # 拼接 + BGM 叠加
        vol = max(0.0, min(1.0, bgm_volume))
        cmd = [
            "ffmpeg",
            "-f", "concat", "-safe", "0", "-i", filelist_path,
            "-i", bgm_path,
            "-filter_complex",
            f"[0:a][1:a]amix=inputs=2:duration=first:dropout_transition=2,"
            f"volume={vol}[a]",
            "-map", "0:v", "-map", "[a]",
            "-c:v", "copy",
            output_path,
            "-y",
        ]
    else:
        # 纯拼接
        cmd = [
            "ffmpeg",
            "-f", "concat", "-safe", "0", "-i", filelist_path,
            "-c", "copy",
            output_path,
            "-y",
        ]

    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise ToolError(f"FFmpeg 拼接失败: {proc.stderr}")

    return {"output_path": output_path}


@video_server.tool()
async def env_check() -> dict[str, Any]:
    """检查运行环境配置状态，返回三个就绪标志。

    - data_ready: 数据采集+脚本生成（Python 3.10+ / FFmpeg / yt-dlp）— 不需要任何 API Key
    - video_ready: AI 视频生成（Kling API Key + 连通性）
    - voice_ready: 语音转写（faster-whisper 可导入）
    """
    result: dict[str, Any] = {}

    # Python 版本
    result["python_version"] = sys.version
    python_ok = sys.version_info >= (3, 10)

    # FFmpeg 可用性
    ffmpeg_path = shutil.which("ffmpeg")
    if ffmpeg_path:
        proc = subprocess.run(["ffmpeg", "-version"], capture_output=True, text=True)
        version_line = proc.stdout.split("\n")[0] if proc.stdout else "未知版本"
        result["ffmpeg"] = {"available": True, "version": version_line}
    else:
        result["ffmpeg"] = {"available": False, "message": "未找到 ffmpeg，请安装后重试"}

    # yt-dlp 可用性
    ytdlp_path = shutil.which("yt-dlp")
    if ytdlp_path:
        proc = subprocess.run(["yt-dlp", "--version"], capture_output=True, text=True)
        result["yt_dlp"] = {"available": True, "version": proc.stdout.strip()}
    else:
        result["yt_dlp"] = {"available": False, "message": "未找到 yt-dlp，请运行: pip install yt-dlp"}

    # faster-whisper 可用性
    try:
        import faster_whisper  # noqa: F401
        result["faster_whisper"] = {"available": True}
    except ImportError:
        result["faster_whisper"] = {
            "available": False,
            "message": "未安装 faster-whisper，语音转写不可用。安装: pip install faster-whisper",
        }

    # Kling API Key 配置状态
    kling_access_configured = bool(os.environ.get("KLING_ACCESS_KEY"))
    kling_secret_configured = bool(os.environ.get("KLING_SECRET_KEY"))
    kling_configured = kling_access_configured and kling_secret_configured

    result["api_keys"] = {
        "KLING_ACCESS_KEY": {
            "status": "已配置" if kling_access_configured else "未配置",
            "required": False,
            "note": "" if kling_access_configured else "仅视频生成需要",
        },
        "KLING_SECRET_KEY": {
            "status": "已配置" if kling_secret_configured else "未配置",
            "required": False,
            "note": "" if kling_secret_configured else "仅视频生成需要",
        },
    }

    # 网络连通性 — 仅检查 Kling（数据采集由浏览器完成，无需 API 连通性检查）
    connectivity: dict[str, Any] = {}
    if kling_configured:
        async with httpx.AsyncClient(timeout=httpx.Timeout(10.0)) as client:
            try:
                resp = await client.get("https://api.klingai.com")
                connectivity["kling"] = {
                    "reachable": True,
                    "status_code": resp.status_code,
                }
            except Exception as e:
                connectivity["kling"] = {"reachable": False, "error": str(e)}
    else:
        connectivity["kling"] = {"reachable": False, "skipped": True, "message": "跳过 — 未配置密钥"}

    result["connectivity"] = connectivity

    # 三个就绪标志
    result["data_ready"] = python_ok and bool(ffmpeg_path) and bool(ytdlp_path)
    result["video_ready"] = kling_configured and connectivity.get("kling", {}).get("reachable", False)
    result["voice_ready"] = result["faster_whisper"]["available"]

    # 故障排除指引
    issues = []
    if not python_ok:
        issues.append("Python 版本需 >= 3.10")
    if not ffmpeg_path:
        issues.append("缺少 FFmpeg: brew install ffmpeg (macOS) / apt install ffmpeg (Linux)")
    if not ytdlp_path:
        issues.append("缺少 yt-dlp: pip install yt-dlp")
    if not result["voice_ready"]:
        issues.append("语音转写不可用（可选）: pip install faster-whisper")
    if issues:
        result["troubleshooting"] = issues

    return result
