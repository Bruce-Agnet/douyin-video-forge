"""Kling 3.0 API 工具模块：4 个视频生成工具。"""

from __future__ import annotations

import asyncio
import os
import subprocess
import tempfile
from typing import Any

import httpx
from fastmcp import FastMCP
from fastmcp.exceptions import ToolError

from mcp_server.utils.auth import get_kling_headers

kling_server = FastMCP("Kling")

_BASE_URL = "https://api.klingai.com"
_TIMEOUT = httpx.Timeout(30.0, connect=10.0)


async def _kling_request(
    method: str,
    path: str,
    json: dict[str, Any] | None = None,
) -> Any:
    """Kling API 通用请求。"""
    url = f"{_BASE_URL}{path}"
    headers = get_kling_headers()

    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        try:
            resp = await client.request(method, url, headers=headers, json=json)
        except httpx.ConnectError:
            raise ToolError("无法连接 Kling API，请检查网络连接或代理设置。")

        if resp.status_code == 401:
            raise ToolError("Kling API 认证失败，请检查 KLING_ACCESS_KEY 和 KLING_SECRET_KEY。")
        if resp.status_code == 403:
            raise ToolError("Kling API 权限不足，请检查 API Key 的权限。")
        if resp.status_code == 429:
            retry_after = resp.headers.get("retry-after", "未知")
            raise ToolError(f"Kling API 请求频率超限，请在 {retry_after} 秒后重试。")

        resp.raise_for_status()
        data = resp.json()
        return data.get("data", data)


async def _poll_task(
    task_id: str,
    interval: int = 10,
    timeout: int = 300,
) -> dict[str, Any]:
    """轮询 Kling 任务直到完成或超时。"""
    elapsed = 0
    while elapsed < timeout:
        data = await _kling_request("GET", f"/v1/videos/{task_id}")
        status = data.get("status", "")
        if status == "completed":
            return data
        if status == "failed":
            error_msg = data.get("error", {}).get("message", "未知错误")
            raise ToolError(f"Kling 视频生成失败: {error_msg}")
        await asyncio.sleep(interval)
        elapsed += interval

    raise ToolError(f"Kling 任务 {task_id} 超时（{timeout}秒），请使用 kling_check_status 手动查询。")


async def _download_if_url(path_or_url: str) -> str:
    """如果是 URL 则下载到临时文件，否则原样返回路径。"""
    if path_or_url.startswith(("http://", "https://")):
        tmpdir = tempfile.mkdtemp(prefix="kling_")
        local_path = os.path.join(tmpdir, "downloaded.mp4")
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(120.0), follow_redirects=True
        ) as client:
            resp = await client.get(path_or_url)
            resp.raise_for_status()
            with open(local_path, "wb") as f:
                f.write(resp.content)
        return local_path
    return path_or_url


@kling_server.tool()
async def kling_generate(
    prompt: str,
    duration: int = 10,
    aspect_ratio: str = "9:16",
    mode: str = "pro",
    motion_has_audio: bool = True,
    kling_elements: list[str] | None = None,
) -> dict[str, Any]:
    """文生视频：提交可灵 3.0 视频生成任务并自动等待完成。

    Args:
        prompt: 视频生成 prompt（中文描述画面、动作、情绪等）
        duration: 时长（秒），10 或 15
        aspect_ratio: 画面比例，默认 9:16（竖屏）
        mode: 生成模式，pro = 1080×1920
        motion_has_audio: 是否包含原生中文音频（默认 True）
        kling_elements: 角色一致性参考图片 URL 列表（2-50张）
    """
    body: dict[str, Any] = {
        "model": "kling-v3",
        "prompt": prompt,
        "duration": duration,
        "aspect_ratio": aspect_ratio,
        "mode": mode,
        "motion_has_audio": motion_has_audio,
    }
    if kling_elements:
        body["kling_elements"] = kling_elements

    data = await _kling_request("POST", "/v1/videos/text2video", json=body)
    task_id = data.get("task_id", "")
    if not task_id:
        raise ToolError("Kling API 未返回 task_id，请检查请求参数。")

    result = await _poll_task(task_id)
    return {
        "task_id": task_id,
        "status": "completed",
        "video_url": result.get("video_url", ""),
        "duration": duration,
    }


@kling_server.tool()
async def kling_generate_with_image(
    prompt: str,
    image: str,
    duration: int = 10,
    aspect_ratio: str = "9:16",
    mode: str = "pro",
    motion_has_audio: bool = True,
    kling_elements: list[str] | None = None,
) -> dict[str, Any]:
    """图生视频：以首帧图片 + prompt 生成视频（用于段落间首末帧衔接）。

    Args:
        prompt: 视频生成 prompt
        image: 首帧图片 URL
        duration: 时长（秒），10 或 15
        aspect_ratio: 画面比例，默认 9:16
        mode: 生成模式
        motion_has_audio: 是否包含原生中文音频
        kling_elements: 角色一致性参考图片 URL 列表
    """
    body: dict[str, Any] = {
        "model": "kling-v3",
        "prompt": prompt,
        "image": image,
        "duration": duration,
        "aspect_ratio": aspect_ratio,
        "mode": mode,
        "motion_has_audio": motion_has_audio,
    }
    if kling_elements:
        body["kling_elements"] = kling_elements

    data = await _kling_request("POST", "/v1/videos/image2video", json=body)
    task_id = data.get("task_id", "")
    if not task_id:
        raise ToolError("Kling API 未返回 task_id，请检查请求参数。")

    result = await _poll_task(task_id)
    return {
        "task_id": task_id,
        "status": "completed",
        "video_url": result.get("video_url", ""),
        "duration": duration,
    }


@kling_server.tool()
async def kling_extract_frame(
    video_path: str,
    position: str = "last",
) -> dict[str, str]:
    """提取视频帧（默认提取最后一帧，用于段落间衔接）。

    Args:
        video_path: 视频文件路径或 URL
        position: 提取位置 - last(最后一帧) 或具体时间如 "00:00:05"
    """
    local_path = await _download_if_url(video_path)

    if not os.path.isfile(local_path):
        raise ToolError(f"视频文件不存在: {local_path}")

    tmpdir = tempfile.mkdtemp(prefix="kling_frame_")
    output_path = os.path.join(tmpdir, "frame.png")

    if position == "last":
        # 提取最后一帧：先获取时长，然后 seek 到末尾
        probe_cmd = [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "csv=p=0",
            local_path,
        ]
        probe = subprocess.run(probe_cmd, capture_output=True, text=True)
        if probe.returncode != 0:
            raise ToolError(f"无法读取视频信息: {probe.stderr}")

        duration = float(probe.stdout.strip())
        seek_time = max(0, duration - 0.1)

        cmd = [
            "ffmpeg", "-ss", str(seek_time),
            "-i", local_path,
            "-frames:v", "1",
            "-q:v", "2",
            output_path,
            "-y",
        ]
    else:
        cmd = [
            "ffmpeg", "-ss", position,
            "-i", local_path,
            "-frames:v", "1",
            "-q:v", "2",
            output_path,
            "-y",
        ]

    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise ToolError(f"提取视频帧失败: {proc.stderr}")

    return {"frame_path": output_path}


@kling_server.tool()
async def kling_check_status(task_id: str) -> dict[str, Any]:
    """查询可灵视频生成任务状态。

    Args:
        task_id: 任务 ID
    """
    data = await _kling_request("GET", f"/v1/videos/{task_id}")
    status = data.get("status", "unknown")
    result: dict[str, Any] = {
        "task_id": task_id,
        "status": status,
    }
    if status == "completed":
        result["video_url"] = data.get("video_url", "")
    elif status == "failed":
        result["error"] = data.get("error", {}).get("message", "未知错误")
    return result
