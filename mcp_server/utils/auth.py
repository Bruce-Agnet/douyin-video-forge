"""API 认证工具：TikHub Bearer Token + Kling JWT 签名。"""

import os
import time

import jwt
from fastmcp.exceptions import ToolError


def get_tikhub_base_url() -> str:
    """返回 TikHub API base URL，优先使用中国节点。"""
    return os.environ.get("TIKHUB_BASE_URL", "https://api.tikhub.io")


def get_tikhub_headers() -> dict[str, str]:
    """构建 TikHub API 请求头。缺失 Key 时抛出 ToolError。"""
    api_key = os.environ.get("TIKHUB_API_KEY")
    if not api_key:
        raise ToolError(
            "未配置 TIKHUB_API_KEY 环境变量。"
            "请在 OpenClaw 设置或 .env 中添加 TIKHUB_API_KEY。"
            "获取地址：https://tikhub.io"
        )
    return {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }


def generate_kling_jwt() -> str:
    """使用 HS256 签发 Kling API JWT，有效期 30 分钟。"""
    access_key = os.environ.get("KLING_ACCESS_KEY")
    secret_key = os.environ.get("KLING_SECRET_KEY")
    if not access_key or not secret_key:
        raise ToolError(
            "未配置 KLING_ACCESS_KEY 或 KLING_SECRET_KEY 环境变量。"
            "请在 OpenClaw 设置或 .env 中添加这两个 Key。"
            "获取地址：https://klingai.com"
        )
    now = int(time.time())
    headers = {"alg": "HS256", "typ": "JWT"}
    payload = {
        "iss": access_key,
        "exp": now + 1800,
        "nbf": now - 5,
    }
    return jwt.encode(payload, secret_key, algorithm="HS256", headers=headers)


def get_kling_headers() -> dict[str, str]:
    """构建 Kling API 请求头。"""
    token = generate_kling_jwt()
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
