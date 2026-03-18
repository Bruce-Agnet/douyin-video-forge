# douyin-video-forge 开发指南

## 项目结构

```
douyin-video-forge/
├── SKILL.md                    # Agent 编排指令（核心）
├── mcp_server/                 # MCP Server（确定性工具）
│   ├── server.py               # FastMCP 入口，flat mount 三个子 server
│   ├── tools/
│   │   ├── media.py            # 媒体处理 3 工具（视频下载/音频提取/语音转写）
│   │   ├── kling.py            # Kling 3.0 API 4 工具（视频生成）
│   │   └── video.py            # FFmpeg 拼接 + env_check（2 工具）
│   └── utils/
│       └── auth.py             # API 认证（Kling JWT）
├── references/                 # LLM 知识库（SKILL.md 按需引用）
├── examples/                   # 示例文件
├── install.sh                  # 一键安装脚本
└── requirements.txt            # Python 依赖
```

## 关键设计决策

1. **浏览器语义爬取**：数据采集由 SKILL.md 编排 OpenClaw 内置浏览器完成，不写 MCP 数据采集工具
2. **Flat mount**：`mcp.mount(media_server)` 无命名空间前缀，工具名保持 `video_download` 而非 `media_video_download`
3. **Auto-poll**：`kling_generate` 和 `kling_generate_with_image` 内部自动轮询任务状态（默认 interval=10s, timeout=300s）
4. **全 async**：所有工具函数均为 `async def`，FastMCP 原生支持
5. **临时文件管理**：下载的视频和帧存入 `tempfile.mkdtemp()`，返回绝对路径
6. **语音转写单例**：faster-whisper 模型 lazy import + 全局单例缓存，避免重复加载
7. **三层降级链**：语音转写 → 抖音AI章节要点（浏览器）→ 跳过
8. **错误全中文**：所有 `ToolError` 消息使用中文，面向非技术运营人员

## 开发命令

```bash
# 验证模块导入
cd douyin-video-forge
python3 -c "from mcp_server.tools.media import media_server; print('Media OK')"
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
- 工具的 docstring 即为 LLM 可见的工具说明，需简洁准确

## 依赖

- `fastmcp>=2.0.0`：MCP Server 框架
- `httpx>=0.27.0`：异步 HTTP（Kling API 请求）
- `pyjwt>=2.8.0`：Kling API JWT 签名
- `yt-dlp>=2024.0.0`：抖音视频下载（subprocess 调用）
- `faster-whisper>=1.0.0`：本地语音转写（lazy import，可选）
- `ffmpeg`：系统级依赖，音视频处理
