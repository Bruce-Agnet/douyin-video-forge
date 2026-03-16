"""视频筛选逻辑：低粉高赞阶梯降级搜索。"""

from __future__ import annotations

from typing import Any


def calculate_engagement_ratio(video: dict[str, Any]) -> float:
    """计算互动率 = (点赞+收藏+转发) ÷ 播放量 × 100%。

    注意：抖音 web 搜索 API 的 play_count 可能为 0，
    此时使用 digg_count 作为替代指标（互动率 = 1.0 视为通过）。
    需要后续调用 tikhub_video_stats 获取真实播放量。
    """
    stats = video.get("statistics", video)
    play_count = stats.get("play_count", 0)
    like = stats.get("digg_count", 0) or stats.get("like_count", 0)
    collect = stats.get("collect_count", 0)
    share = stats.get("share_count", 0)
    if play_count == 0:
        # play_count 不可用时，有互动数据即视为通过
        return 1.0 if (like + collect + share) > 0 else 0.0
    return (like + collect + share) / play_count


def filter_videos(
    videos: list[dict[str, Any]],
    max_followers: int,
    min_like_ratio: float,
) -> list[dict[str, Any]]:
    """按粉丝量上限和最低互动率筛选视频。"""
    results = []
    for v in videos:
        author = v.get("author", {})
        follower_count = author.get("follower_count", 0)
        if follower_count > max_followers:
            continue
        ratio = calculate_engagement_ratio(v)
        if ratio < min_like_ratio:
            continue
        v["_engagement_ratio"] = round(ratio, 4)
        results.append(v)
    return results


async def search_with_stepdown(
    fetch_fn,
    keyword: str,
    max_followers: int = 50000,
    min_like_ratio: float = 0.05,
    min_results: int = 5,
    sort_type: str = "relevance",
    publish_time: str = "7d",
) -> dict[str, Any]:
    """
    低粉高赞视频搜索，含自动阶梯降级。
    若符合条件的视频不足 min_results，自动放宽筛选条件。
    最多降级至原始条件的 50%。
    """
    degradation = 1.0
    results: list[dict[str, Any]] = []
    current_max_followers = max_followers
    current_min_ratio = min_like_ratio

    while len(results) < min_results and degradation >= 0.5:
        current_max_followers = int(max_followers / degradation)
        current_min_ratio = min_like_ratio * degradation

        raw_videos = await fetch_fn(
            keyword=keyword,
            sort_type=sort_type,
            publish_time=publish_time,
        )
        results = filter_videos(raw_videos, current_max_followers, current_min_ratio)

        if len(results) < min_results:
            degradation -= 0.25

    return {
        "videos": results,
        "degradation_applied": degradation < 1.0,
        "final_thresholds": {
            "max_followers": current_max_followers,
            "min_like_ratio": round(current_min_ratio, 4),
        },
    }
