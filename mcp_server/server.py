"""DouyinVideoForge MCP Server 入口：flat mount 三个子 server。"""

from fastmcp import FastMCP

from mcp_server.tools.media import media_server
from mcp_server.tools.kling import kling_server
from mcp_server.tools.video import video_server

mcp = FastMCP("DouyinVideoForge")

# Flat mount — 保持工具名称扁平（如 video_download 而非 media_video_download）
mcp.mount(media_server)
mcp.mount(kling_server)
mcp.mount(video_server)

if __name__ == "__main__":
    mcp.run()
