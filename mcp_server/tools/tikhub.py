"""TikHub API 工具模块：7 个数据采集工具。"""

from __future__ import annotations

import asyncio
import os
import re
import ssl
import tempfile
import time
from typing import Any

import certifi
import httpx
from fastmcp import FastMCP
from fastmcp.exceptions import ToolError

from mcp_server.utils.auth import get_tikhub_base_url, get_tikhub_headers
from mcp_server.utils.filters import search_with_stepdown

tikhub_server = FastMCP("TikHub")

_TIMEOUT = httpx.Timeout(30.0, connect=15.0)
# Cloudflare 会拦截默认 httpx User-Agent (error 1010)，需使用浏览器 UA
_USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
# SSL：显式加载 certifi 证书（macOS Python 的系统证书库可能为空）
_SSL_CONTEXT = ssl.create_default_context(cafile=certifi.where())

# A2: 全局请求节流，避免连续调用触发抖音频率限制
_LAST_REQUEST_TIME = 0.0
_MIN_REQUEST_INTERVAL = 1.0  # 最小间隔 1 秒


async def _do_request(
    client: httpx.AsyncClient,
    method: str,
    url: str,
    headers: dict[str, str],
    params: dict[str, Any] | None,
    json: dict[str, Any] | None,
) -> httpx.Response:
    """发送请求并处理 HTTP 状态码错误。"""
    resp = await client.request(method, url, headers=headers, params=params, json=json)

    if resp.status_code == 401:
        raise ToolError("TikHub API 认证失败，请检查 TIKHUB_API_KEY 是否正确。")
    if resp.status_code == 403:
        raise ToolError("TikHub API 权限不足，请检查 TIKHUB_API_KEY 的权限范围。")
    if resp.status_code == 429:
        retry_after = resp.headers.get("retry-after", "未知")
        raise ToolError(f"TikHub API 请求频率超限，请在 {retry_after} 秒后重试。")
    if resp.status_code == 400:
        try:
            detail = resp.json().get("detail", {})
            msg = detail.get("message_zh", detail.get("message", "参数错误"))
        except Exception:
            msg = "请求参数错误"
        raise ToolError(f"TikHub API 请求失败: {msg}")
    if resp.status_code >= 500:
        raise ToolError(f"TikHub API 服务器错误 ({resp.status_code})，请稍后重试。")

    resp.raise_for_status()
    return resp


async def _tikhub_request(
    method: str,
    path: str,
    params: dict[str, Any] | None = None,
    json: dict[str, Any] | None = None,
) -> Any:
    """TikHub API 通用请求：处理认证、错误、连接重试。

    连接策略：先直连（trust_env=False），失败后通过系统代理重试（trust_env=True）。
    运营环境（大陆无代理）直连 api.tikhub.dev 即可成功；
    开发环境（有代理工具）直连可能失败，回退走系统代理。

    TikHub 响应结构：{ code, data: { ... 实际数据 ... }, message, ... }
    本函数自动解包外层 wrapper，返回 data 字段内容。
    """
    global _LAST_REQUEST_TIME

    # A2: 全局请求节流
    now = time.monotonic()
    wait = _MIN_REQUEST_INTERVAL - (now - _LAST_REQUEST_TIME)
    if wait > 0:
        await asyncio.sleep(wait)
    _LAST_REQUEST_TIME = time.monotonic()

    url = f"{get_tikhub_base_url()}{path}"
    headers = get_tikhub_headers()
    headers["User-Agent"] = _USER_AGENT

    # 第一次：直连（适用于大陆运营环境无代理直连 api.tikhub.dev）
    try:
        async with httpx.AsyncClient(
            timeout=_TIMEOUT, verify=_SSL_CONTEXT, trust_env=False,
        ) as client:
            try:
                resp = await _do_request(client, method, url, headers, params, json)
            except ToolError as e:
                # A1: TikHub 间歇性 400 重试一次（2 秒后）
                if "请求失败" in str(e):
                    await asyncio.sleep(2)
                    _LAST_REQUEST_TIME = time.monotonic()
                    resp = await _do_request(client, method, url, headers, params, json)
                else:
                    raise
            try:
                data = resp.json()
            except ValueError:
                raise ToolError(f"TikHub API 返回了非 JSON 响应（状态码 {resp.status_code}），请稍后重试。")
            return data.get("data", data)
    except (httpx.TimeoutException, httpx.ConnectError):
        pass  # 直连失败，尝试系统代理

    # 第二次：走系统代理（适用于开发环境有 Clash/V2Ray 等代理工具）
    try:
        async with httpx.AsyncClient(
            timeout=_TIMEOUT, verify=_SSL_CONTEXT, trust_env=True,
        ) as client:
            try:
                resp = await _do_request(client, method, url, headers, params, json)
            except ToolError as e:
                # A1: TikHub 间歇性 400 重试一次（2 秒后）
                if "请求失败" in str(e):
                    await asyncio.sleep(2)
                    _LAST_REQUEST_TIME = time.monotonic()
                    resp = await _do_request(client, method, url, headers, params, json)
                else:
                    raise
            try:
                data = resp.json()
            except ValueError:
                raise ToolError(f"TikHub API 返回了非 JSON 响应（状态码 {resp.status_code}），请稍后重试。")
            return data.get("data", data)
    except httpx.TimeoutException:
        raise ToolError("TikHub API 请求超时，请检查网络连接或稍后重试。")
    except httpx.ConnectError:
        raise ToolError("无法连接 TikHub API，请检查网络连接。")


# ---------------------------------------------------------------------------
# 热榜端点映射
# ---------------------------------------------------------------------------
# (endpoint, method, default_params)
_HOT_LIST_ENDPOINTS: dict[str, tuple[str, str, dict[str, Any]]] = {
    "hot_total": (
        "/api/v1/douyin/billboard/fetch_hot_total_list",
        "GET",
        {"page": 1, "page_size": 20, "type": "snapshot"},
    ),
    "hot_search": (
        "/api/v1/douyin/app/v3/fetch_hot_search_list",
        "GET",
        {},
    ),
    "hot_topic": (
        "/api/v1/douyin/billboard/fetch_hot_total_topic_list",
        "POST",
        {},
    ),
    "hot_word": (
        "/api/v1/douyin/billboard/fetch_hot_total_hot_word_list",
        "POST",
        {},
    ),
}

_SORT_TYPE_MAP = {
    "relevance": "0",
    "likes": "1",
    "time": "2",
}

_PUBLISH_TIME_MAP = {
    "1d": "1",
    "7d": "7",
    "180d": "180",
}


@tikhub_server.tool()
async def tikhub_hot_list(list_type: str) -> Any:
    """获取抖音热榜数据。

    Args:
        list_type: 列表类型 - hot_total(总热榜) / hot_search(热搜) / hot_topic(热门话题) / hot_word(热词)
    """
    entry = _HOT_LIST_ENDPOINTS.get(list_type)
    if not entry:
        raise ToolError(
            f"不支持的列表类型: {list_type}。"
            f"可选值: {', '.join(_HOT_LIST_ENDPOINTS.keys())}"
        )
    endpoint, http_method, default_params = entry
    if http_method == "POST":
        return await _tikhub_request("POST", endpoint, json=default_params or None)
    return await _tikhub_request("GET", endpoint, params=default_params or None)


@tikhub_server.tool()
async def tikhub_search(
    keyword: str,
    max_followers: int = 50000,
    min_like_ratio: float = 0.05,
    min_results: int = 5,
    sort_type: str = "relevance",
    publish_time: str = "7d",
) -> dict[str, Any]:
    """搜索抖音视频并自动筛选出低粉高赞视频（含阶梯降级）。

    Args:
        keyword: 搜索关键词
        max_followers: 粉丝量上限（默认5万）
        min_like_ratio: 最低互动率，互动率=(点赞+收藏+转发)÷播放量（默认0.05即5%）
        min_results: 最少返回结果数，不足则触发阶梯降级（默认5）
        sort_type: 排序方式 - relevance(综合) / likes(点赞) / time(最新)
        publish_time: 发布时间范围 - 1d / 7d / 180d
    """

    async def fetch_fn(
        keyword: str, sort_type: str, publish_time: str
    ) -> list[dict[str, Any]]:
        params: dict[str, Any] = {
            "keyword": keyword,
            "page": 1,
        }
        st = _SORT_TYPE_MAP.get(sort_type, sort_type)
        pt = _PUBLISH_TIME_MAP.get(publish_time, publish_time)
        if st != "0":
            params["sort_type"] = f"_{st}"
        if pt != "0":
            params["publish_time"] = f"_{pt}"

        data = await _tikhub_request(
            "GET",
            "/api/v1/douyin/web/fetch_video_search_result_v2",
            params=params,
        )
        # v2 响应: data.business_data[].data.aweme_info
        if isinstance(data, dict):
            raw_items = data.get("business_data", [])
            videos = []
            for item in raw_items:
                inner = item.get("data", {})
                aweme = inner.get("aweme_info", {})
                if aweme:
                    videos.append(aweme)
            return videos
        return data if isinstance(data, list) else []

    return await search_with_stepdown(
        fetch_fn=fetch_fn,
        keyword=keyword,
        max_followers=max_followers,
        min_like_ratio=min_like_ratio,
        min_results=min_results,
        sort_type=sort_type,
        publish_time=publish_time,
    )


@tikhub_server.tool()
async def tikhub_video_stats(video_ids: list[str]) -> Any:
    """批量获取视频统计数据（播放、点赞、评论、转发、收藏）。

    Args:
        video_ids: 视频 ID 列表（每次最多10个）
    """
    if len(video_ids) > 10:
        raise ToolError("每次最多查询 10 个视频，请分批调用。")

    return await _tikhub_request(
        "GET",
        "/api/v1/douyin/app/v3/fetch_multi_video_statistics",
        params={"aweme_ids": ",".join(video_ids)},
    )


@tikhub_server.tool()
async def tikhub_video_comments(video_id: str) -> Any:
    """获取视频评论词云数据（高频词 + 情感倾向）。

    Args:
        video_id: 视频 ID
    """
    return await _tikhub_request(
        "GET",
        "/api/v1/douyin/billboard/fetch_hot_comment_word_list",
        params={"aweme_id": video_id},
    )


# 缓存 unique_id → sec_uid 的映射，避免重复搜索触发 Douyin 频率限制
_UNIQUE_ID_CACHE: dict[str, str] = {}


# 从抖音主页链接中提取 sec_uid 的正则
# 支持格式：
#   https://www.douyin.com/user/MS4wLjABAAAA...
#   https://www.douyin.com/user/MS4wLjABAAAA...?vid=123
#   https://v.douyin.com/user/MS4wLjABAAAA...
_DOUYIN_URL_PATTERN = re.compile(
    r"(?:https?://)?(?:www\.|v\.)?douyin\.com/user/(MS4wLj[A-Za-z0-9_-]+)"
)


def _extract_from_url(text: str) -> str | None:
    """从抖音主页链接中提取 sec_uid，无匹配返回 None。"""
    m = _DOUYIN_URL_PATTERN.search(text)
    return m.group(1) if m else None


def _resolve_account_id(account_id: str) -> tuple[str, dict[str, str]]:
    """根据 account_id 格式判断端点和参数。

    支持的输入格式（按优先级）：
    1. 抖音主页链接 → 自动提取 sec_uid
    2. sec_user_id (MS4wLj...) → handler_user_profile
    3. 纯数字 → 先尝试 uid，失败后降级为 unique_id 搜索
    4. 其他文本 → 作为 unique_id（抖音号）搜索

    Returns:
        (endpoint_path, query_params)  endpoint 为空表示需要走搜索流程
    """
    account_id = account_id.strip()

    # 1. 尝试从链接中提取 sec_uid
    sec_uid = _extract_from_url(account_id)
    if sec_uid:
        return "/api/v1/douyin/web/handler_user_profile", {"sec_user_id": sec_uid}

    # 2. 直接传入 sec_uid
    if account_id.startswith("MS4wLj"):
        return "/api/v1/douyin/web/handler_user_profile", {"sec_user_id": account_id}

    # 3. 纯数字 → 先尝试 uid
    if account_id.isdigit():
        return "/api/v1/douyin/web/handler_user_profile_v3", {"uid": account_id}

    # 4. 其他 → unique_id（抖音号）
    return "", {"unique_id": account_id}


def _extract_sec_uid(profile_data: Any) -> str | None:
    """从 profile 响应中提取 sec_uid，兼容多种响应结构。"""
    if not isinstance(profile_data, dict):
        return None
    user = profile_data.get("user", profile_data)
    return user.get("sec_uid") or user.get("sec_user_id")


async def _resolve_unique_id(unique_id: str) -> dict[str, Any]:
    """通过用户搜索查找 unique_id/抖音号 对应的账号，返回 sec_uid + 完整 profile。

    使用 fetch_user_search_result_v2（用户搜索）而非 fetch_video_search_result_v2（视频搜索），
    前者按用户名/抖音号搜索，命中率远高于视频内容搜索。

    流程：用户搜索 → 取第一个候选的 sec_uid → handler_user_profile 获取完整 profile。
    用户搜索结果精度高，通常第一条即为目标账号，不再逐个验证以减少 API 调用。
    结果会缓存 unique_id→sec_uid 映射，避免重复搜索。
    """
    # 检查缓存
    cached_sec = _UNIQUE_ID_CACHE.get(unique_id.lower())
    if cached_sec:
        return await _tikhub_request(
            "GET",
            "/api/v1/douyin/web/handler_user_profile",
            params={"sec_user_id": cached_sec},
        )

    data = await _tikhub_request(
        "GET",
        "/api/v1/douyin/web/fetch_user_search_result_v2",
        params={"keyword": unique_id, "page": 1},
    )

    # 解包：data → data.data.user_list
    # 注意：Douyin 频率限制时 data.data 可能是字符串 "用户未登录"
    if not isinstance(data, dict):
        raise ToolError(f"搜索 {unique_id} 无结果，请确认抖音号是否正确。")
    inner = data.get("data", data)
    # A3: "用户未登录"等字符串响应通常是抖音频率限制，等 3 秒后重试一次
    if isinstance(inner, str):
        await asyncio.sleep(3)
        data = await _tikhub_request(
            "GET",
            "/api/v1/douyin/web/fetch_user_search_result_v2",
            params={"keyword": unique_id, "page": 1},
        )
        if not isinstance(data, dict):
            raise ToolError(f"搜索 {unique_id} 无结果，请确认抖音号是否正确。")
        inner = data.get("data", data)
        if isinstance(inner, str):
            raise ToolError(f"抖音搜索暂时不可用（{inner}），请稍后重试。")
    if isinstance(inner, dict):
        user_list = inner.get("user_list", [])
    else:
        user_list = []

    if not user_list:
        raise ToolError(f"未找到抖音号「{unique_id}」对应的账号。")

    # 取第一个有效候选的 sec_uid，获取完整 profile
    for candidate in user_list[:3]:
        sec_uid = candidate.get("user_id", "")  # user_id 实为 sec_uid
        if not sec_uid or not sec_uid.startswith("MS4wLj"):
            continue
        # 缓存映射
        _UNIQUE_ID_CACHE[unique_id.lower()] = sec_uid
        return await _tikhub_request(
            "GET",
            "/api/v1/douyin/web/handler_user_profile",
            params={"sec_user_id": sec_uid},
        )

    raise ToolError(
        f"未找到抖音号「{unique_id}」的有效账号。"
        f"请尝试提供 sec_uid（以 MS4wLj 开头的长字符串，可从抖音分享链接中获取）。"
    )


async def _get_profile(account_id: str) -> dict[str, Any]:
    """统一获取账号 profile，自动处理 uid / sec_uid / unique_id 三种格式。

    纯数字 ID 可能是 uid 也可能是抖音号（unique_id），
    优先尝试 uid 端点，失败后降级为 unique_id 搜索。
    """
    endpoint, params = _resolve_account_id(account_id)

    if not endpoint:
        # unique_id → 通过搜索解析
        return await _resolve_unique_id(params["unique_id"])

    try:
        profile = await _tikhub_request("GET", endpoint, params=params)
    except ToolError:
        # 纯数字 ID 作为 uid 查询失败 → 降级为 unique_id 搜索
        if account_id.isdigit():
            return await _resolve_unique_id(account_id)
        raise

    # 检查 Douyin 内部错误（如 "Service Unavailable", "UserId不合法"）
    if isinstance(profile, dict):
        inner_status = profile.get("status_code")
        status_msg = profile.get("status_msg", "")
        if inner_status and inner_status != 0:
            # 纯数字 ID uid 查询失败 → 降级为 unique_id 搜索
            if account_id.isdigit():
                return await _resolve_unique_id(account_id)
            inner_data = profile.get("data", {})
            msg = inner_data.get("message", status_msg) if isinstance(inner_data, dict) else status_msg
            if msg:
                raise ToolError(f"抖音返回错误: {msg}（账号: {account_id}）。请稍后重试或换用 sec_uid 格式。")

    return profile


@tikhub_server.tool()
async def tikhub_account_analysis(account_id: str) -> dict[str, Any]:
    """获取竞品账号基础信息（粉丝数、获赞数、简介等），供 LLM 综合分析。

    Args:
        account_id: 抖音账号标识 — 支持主页链接、sec_uid（MS4wLj...）、抖音号或 uid
    """
    profile = await _get_profile(account_id)
    result: dict[str, Any] = {"profile": profile}

    # 获取近期作品
    sec_uid = _extract_sec_uid(profile)
    if sec_uid:
        try:
            posts = await _tikhub_request(
                "GET",
                "/api/v1/douyin/web/fetch_user_post_videos",
                params={"sec_user_id": sec_uid, "count": 20, "cursor": 0},
            )
            result["recent_posts"] = posts
        except ToolError as e:
            result["recent_posts_note"] = f"获取作品列表失败: {e}"

    return result


@tikhub_server.tool()
async def tikhub_fan_portrait(account_id: str) -> dict[str, Any]:
    """获取账号基础信息和粉丝列表数据，供 LLM 分析粉丝特征。

    注意：抖音粉丝列表接口需要登录态，无登录态时仅返回 profile 数据，
    LLM 可结合行业特征和账号定位推断粉丝群体特征。

    Args:
        account_id: 抖音账号标识 — 支持主页链接、sec_uid（MS4wLj...）、抖音号或 uid
    """
    profile = await _get_profile(account_id)
    result: dict[str, Any] = {"profile": profile}

    sec_uid = _extract_sec_uid(profile)
    if sec_uid:
        try:
            fans_data = await _tikhub_request(
                "GET",
                "/api/v1/douyin/web/fetch_user_fans_list",
                params={"sec_user_id": sec_uid, "count": 50},
            )
            # 检查抖音是否要求登录
            if isinstance(fans_data, dict) and fans_data.get("status_code") == 8:
                result["fans_note"] = "抖音粉丝列表需要登录态，请基于 profile 信息推断粉丝特征"
            else:
                result["fans"] = fans_data
        except ToolError as e:
            result["fans_note"] = f"获取粉丝列表失败: {e}"

    return result


@tikhub_server.tool()
async def tikhub_download_video(
    video_id: str = "",
    video_url: str = "",
    extract_frames: bool = False,
) -> dict[str, Any]:
    """下载抖音视频并可选提取关键帧（用于 LLM 多模态视觉分析）。

    Args:
        video_id: 视频 ID（与 video_url 二选一）
        video_url: 视频直链 URL（与 video_id 二选一）
        extract_frames: 是否提取关键帧（默认 False）
    """
    if not video_id and not video_url:
        raise ToolError("请提供 video_id 或 video_url 之一。")

    # 如果只有 video_id，先获取视频详情取得下载 URL
    if not video_url:
        data = await _tikhub_request(
            "GET",
            "/api/v1/douyin/app/v3/fetch_one_video",
            params={"aweme_id": video_id},
        )
        if isinstance(data, dict):
            video_info = data.get("aweme_detail", data)
            video_obj = video_info.get("video", {})
            play_addr = video_obj.get("play_addr", {})
            url_list = play_addr.get("url_list", [])
            if url_list:
                video_url = url_list[0]
        if not video_url:
            raise ToolError(f"无法获取视频 {video_id} 的下载地址。")

    # 下载视频到临时文件
    tmpdir = tempfile.mkdtemp(prefix="douyin_video_")
    video_path = os.path.join(tmpdir, f"{video_id or 'video'}.mp4")

    dl_kwargs: dict[str, Any] = {
        "timeout": httpx.Timeout(120.0),
        "follow_redirects": True,
        "verify": _SSL_CONTEXT,
    }
    try:
        async with httpx.AsyncClient(trust_env=False, **dl_kwargs) as client:
            resp = await client.get(video_url)
            resp.raise_for_status()
    except (httpx.ConnectError, httpx.TimeoutException):
        try:
            async with httpx.AsyncClient(trust_env=True, **dl_kwargs) as client:
                resp = await client.get(video_url)
                resp.raise_for_status()
        except (httpx.ConnectError, httpx.TimeoutException):
            raise ToolError("下载视频失败，请检查网络连接。")

    with open(video_path, "wb") as f:
        f.write(resp.content)

    result: dict[str, Any] = {"video_path": video_path}

    # 可选：提取关键帧
    if extract_frames:
        import subprocess

        frames_dir = os.path.join(tmpdir, "frames")
        os.makedirs(frames_dir, exist_ok=True)

        # 使用 ffmpeg 每 2 秒提取一帧
        cmd = [
            "ffmpeg", "-i", video_path,
            "-vf", "fps=0.5",
            "-q:v", "2",
            os.path.join(frames_dir, "frame_%03d.jpg"),
            "-y",
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.returncode != 0:
            raise ToolError(f"提取关键帧失败: {proc.stderr}")

        frame_files = sorted(
            os.path.join(frames_dir, f)
            for f in os.listdir(frames_dir)
            if f.endswith(".jpg")
        )
        result["frames"] = frame_files

    return result
