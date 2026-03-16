# douyin-video-forge 开发指南

## 项目结构

```
douyin-video-forge/
├── SKILL.md                    # Agent 编排指令（核心）
├── mcp_server/                 # MCP Server（确定性工具）
│   ├── server.py               # FastMCP 入口，flat mount 三个子 server
│   ├── tools/
│   │   ├── tikhub.py           # TikHub API 7 工具（数据采集+下载）
│   │   ├── kling.py            # Kling 3.0 API 4 工具（视频生成）
│   │   └── video.py            # FFmpeg 拼接 + env_check（2 工具）
│   └── utils/
│       ├── auth.py             # API 认证（TikHub Bearer + Kling JWT）
│       └── filters.py          # 低粉高赞阶梯降级筛选
├── references/                 # LLM 知识库（SKILL.md 按需引用）
├── examples/                   # 示例文件
├── install.sh                  # 一键安装脚本
└── requirements.txt            # Python 依赖
```

## 关键设计决策

1. **Flat mount**：`mcp.mount(tikhub_server)` 无命名空间前缀，工具名保持 `tikhub_search` 而非 `tikhub_tikhub_search`
2. **Auto-poll**：`kling_generate` 和 `kling_generate_with_image` 内部自动轮询任务状态，避免 LLM 循环调用浪费 token（默认 interval=10s, timeout=300s）
3. **全 async**：所有工具函数均为 `async def`，FastMCP 原生支持
4. **临时文件管理**：下载的视频和帧存入 `tempfile.mkdtemp()`，返回绝对路径
5. **视觉分析分离**：`tikhub_download_video` 只负责下载+提取帧，视觉分析由 LLM 多模态能力完成
6. **错误全中文**：所有 `ToolError` 消息使用中文，面向非技术运营人员

## 开发命令

```bash
# 验证模块导入
cd douyin-video-forge
python3 -c "from mcp_server.tools.tikhub import tikhub_server; print('TikHub OK')"
python3 -c "from mcp_server.tools.kling import kling_server; print('Kling OK')"
python3 -c "from mcp_server.tools.video import video_server; print('Video OK')"
python3 -c "from mcp_server.server import mcp; print('Server OK')"

# 启动 MCP Server
python3 -m mcp_server.server
# 或
fastmcp run mcp_server:mcp
```

## 代码约定

- 所有用户可见文本使用中文
- API Key 只从环境变量读取，绝不硬编码
- 缺失环境变量时抛出 `ToolError` 并给出获取地址提示
- HTTP 错误按状态码分类处理：401/403（认证）、429（限流含 retry-after）、5xx（服务端）
- 工具的 docstring 即为 LLM 可见的工具说明，需简洁准确

## 依赖

- `certifi>=2024.2.2`：SSL 证书包（macOS Python 系统证书加载不稳定，需显式指定）
- `fastmcp>=2.0.0`：MCP Server 框架
- `httpx>=0.27.0`：异步 HTTP（替代 requests）
- `pyjwt>=2.8.0`：Kling API JWT 签名
- `ffmpeg`：系统级依赖，视频处理（帧提取使用 FFmpeg，不需要 Pillow）
