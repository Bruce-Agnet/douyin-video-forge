"""允许 python3 -m mcp_server 启动 MCP Server。"""

from mcp_server.server import mcp

if __name__ == "__main__":
    mcp.run()
