"""媒体处理工具模块：视频下载、音频提取、语音转写（3 个工具）。"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from typing import Any

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError

media_server = FastMCP("Media")

# whisper 模型单例缓存
_whisper_model = None
_whisper_model_size = None


@media_server.tool()
async def video_download(
    url: str,
    extract_frames: bool = False,
    frame_interval: float = 2.0,
) -> dict[str, Any]:
    """使用 yt-dlp 下载抖音视频，可选提取关键帧用于多模态分析。

    Args:
        url: 抖音视频链接（支持 douyin.com/video/xxx、v.douyin.com 短链、分享链接）
        extract_frames: 是否提取关键帧（默认 False）
        frame_interval: 帧提取间隔秒数（默认 2.0）
    """
    if not shutil.which("yt-dlp"):
        raise ToolError("未安装 yt-dlp，请运行: pip install yt-dlp")

    tmpdir = tempfile.mkdtemp(prefix="media_download_")
    output_template = os.path.join(tmpdir, "%(id)s.%(ext)s")

    cmd = [
        "yt-dlp",
        "--no-warnings",
        "-f", "best",
        "-o", output_template,
        "--no-playlist",
        url,
    ]

    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    except subprocess.TimeoutExpired:
        raise ToolError("视频下载超时（120秒），请检查链接或网络。")

    if proc.returncode != 0:
        raise ToolError(f"yt-dlp 下载失败: {proc.stderr.strip()}")

    # 查找下载的视频文件
    video_files = [
        f for f in os.listdir(tmpdir)
        if f.endswith((".mp4", ".webm", ".mkv", ".flv"))
    ]
    if not video_files:
        raise ToolError("下载完成但未找到视频文件。")

    video_path = os.path.join(tmpdir, video_files[0])
    duration = _get_duration(video_path)

    result: dict[str, Any] = {
        "video_path": video_path,
        "duration": duration,
    }

    if extract_frames:
        result["frames"] = _extract_frames(video_path, tmpdir, frame_interval)

    return result


@media_server.tool()
async def audio_extract(
    video_path: str,
    output_format: str = "wav",
) -> dict[str, Any]:
    """从视频中提取音频（16kHz mono WAV，适合 whisper 转写）。

    Args:
        video_path: 视频文件路径
        output_format: 输出格式（默认 wav）
    """
    if not os.path.isfile(video_path):
        raise ToolError(f"视频文件不存在: {video_path}")

    tmpdir = tempfile.mkdtemp(prefix="media_audio_")
    audio_path = os.path.join(tmpdir, f"audio.{output_format}")

    cmd = [
        "ffmpeg",
        "-i", video_path,
        "-vn",
        "-acodec", "pcm_s16le",
        "-ar", "16000",
        "-ac", "1",
        audio_path,
        "-y",
    ]

    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        stderr = proc.stderr.strip()
        if "does not contain any stream" in stderr or "no audio" in stderr.lower():
            raise ToolError("视频没有音频轨道。")
        raise ToolError(f"音频提取失败: {stderr}")

    duration = _get_duration(audio_path)

    return {
        "audio_path": audio_path,
        "duration": duration,
    }


@media_server.tool()
async def audio_transcribe(
    audio_path: str,
    language: str = "zh",
    model_size: str = "medium",
) -> dict[str, Any]:
    """使用 faster-whisper 本地转写音频为文字。

    首次调用会自动下载模型（~1.5GB），后续使用缓存。

    Args:
        audio_path: 音频文件路径（推荐 16kHz mono WAV）
        language: 语言代码（默认 zh）
        model_size: 模型大小 - tiny/base/small/medium/large-v3（默认 medium）
    """
    if not os.path.isfile(audio_path):
        raise ToolError(f"音频文件不存在: {audio_path}")

    try:
        from faster_whisper import WhisperModel
    except ImportError:
        raise ToolError("未安装 faster-whisper，请运行: pip install faster-whisper")

    global _whisper_model, _whisper_model_size
    if _whisper_model is None or _whisper_model_size != model_size:
        _whisper_model = WhisperModel(
            model_size, device="auto", compute_type="int8",
        )
        _whisper_model_size = model_size

    segments_iter, info = _whisper_model.transcribe(
        audio_path,
        language=language,
        vad_filter=True,
    )

    segments = []
    full_text_parts = []
    for seg in segments_iter:
        segments.append({
            "start": round(seg.start, 2),
            "end": round(seg.end, 2),
            "text": seg.text.strip(),
        })
        full_text_parts.append(seg.text.strip())

    return {
        "text": "".join(full_text_parts),
        "segments": segments,
        "language": info.language,
        "duration": round(info.duration, 2),
    }


def _get_duration(file_path: str) -> float:
    """使用 ffprobe 获取媒体文件时长。"""
    cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "csv=p=0",
        file_path,
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        return 0.0
    try:
        return round(float(proc.stdout.strip()), 2)
    except ValueError:
        return 0.0


def _extract_frames(
    video_path: str, tmpdir: str, interval: float,
) -> list[str]:
    """使用 FFmpeg 按间隔提取视频帧。"""
    frames_dir = os.path.join(tmpdir, "frames")
    os.makedirs(frames_dir, exist_ok=True)

    fps = 1.0 / interval if interval > 0 else 0.5
    cmd = [
        "ffmpeg", "-i", video_path,
        "-vf", f"fps={fps}",
        "-q:v", "2",
        os.path.join(frames_dir, "frame_%03d.jpg"),
        "-y",
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        return []

    return sorted(
        os.path.join(frames_dir, f)
        for f in os.listdir(frames_dir)
        if f.endswith(".jpg")
    )
