# douyin-video-forge v2.0 产品需求文档

## 1. 文档信息

| 项目 | 内容 |
|------|------|
| 版本 | v2.0 |
| 日期 | 2026-03-18 |
| 状态 | 开发中 |
| 变更摘要 | TikHub API → 浏览器语义爬取，新增语音转写，零付费数据 API 依赖 |

### v1.0 → v2.0 核心变化

| 维度 | v1.0 | v2.0 |
|------|------|------|
| 数据采集 | TikHub API（付费第三方） | OpenClaw 内置浏览器（零成本） |
| 视频下载 | TikHub 下载端点 | yt-dlp（开源） |
| 语音转写 | 无 | faster-whisper 本地推理 |
| 低粉高赞筛选 | Python 代码 (`filters.py`) | SKILL.md 自然语言指令 |
| 入口门槛 | 需要 TIKHUB_API_KEY | 仅需安装 Python + FFmpeg + yt-dlp |
| MCP 工具数 | 13 个 | 9 个 |

---

## 2. 产品概述

`douyin-video-forge` 是一个 OpenClaw Skill，覆盖抖音短视频制作的完整链路：

```
热点采集（浏览器）→ 低粉高赞视频筛选（LLM）→ 竞品分析（浏览器）→ 语音转写分析 →
数据洞察 → 脚本生成 → AI 视频生成 → 多段拼接成片
```

**v2.0 核心范式：零第三方数据 API 依赖**。所有数据采集通过 OpenClaw 内置浏览器以语义爬取方式完成，LLM 直接理解页面内容并提取结构化数据。唯一的外部 API 调用仅限于 AI 视频生成（可灵 3.0，可选）。

---

## 3. 目标用户

| 角色 | 使用场景 |
|------|---------|
| 短视频运营人员 | 日常热点追踪、内容策划、脚本批量生产 |
| MCN 机构 | 多账号矩阵内容管理、竞品监控 |
| 品牌方 | 产品推广视频制作、数据驱动内容决策 |

---

## 4. 技术架构

### 新架构图

```
SKILL.md (脑) ─── 编排 ──→ OpenClaw 浏览器 (眼) → 抖音网页
    │                         │
    │                         ├── 热榜：douyin.com/hot
    │                         ├── 搜索：douyin.com/search/<keyword>
    │                         ├── 竞品：douyin.com/user/<sec_uid>
    │                         └── 评论：视频页面评论区
    │
    └── 工具调用 ──→ MCP Server (手) → 9 个工具
                      ├── media.py (新): video_download / audio_extract / audio_transcribe
                      ├── kling.py (保留): generate / img2video / frame / status
                      └── video.py (改): video_concat / env_check
```

### 目录结构

```
douyin-video-forge/
├── SKILL.md                    # Agent 编排指令（核心）
├── mcp_server/                 # MCP Server（确定性工具）
│   ├── server.py               # FastMCP 入口，flat mount 三个子 server
│   ├── tools/
│   │   ├── media.py            # 媒体处理 3 工具（下载/音频提取/语音转写）
│   │   ├── kling.py            # Kling 3.0 API 4 工具（视频生成）
│   │   └── video.py            # FFmpeg 拼接 + env_check（2 工具）
│   └── utils/
│       └── auth.py             # API 认证（Kling JWT）
├── references/                 # LLM 知识库（SKILL.md 按需引用）
│   ├── browser-navigation.md   # 抖音页面结构参考
│   ├── douyin-algorithm.md
│   ├── kling-prompt-guide.md
│   ├── seedance-prompt-guide.md
│   ├── script-templates.md
│   └── trend-analysis.md
├── examples/                   # 示例文件
├── install.sh                  # 一键安装脚本
└── requirements.txt            # Python 依赖
```

### 模型推荐

强烈推荐 **Claude Sonnet 4.6+**，数据分析和创意脚本需要强推理能力。

---

## 5. 功能需求

### 就绪标志

| 标志 | 含义 | 检查项 | 阻塞? |
|------|------|--------|-------|
| `data_ready` | 数据采集+脚本生成 | Python 3.10+ / FFmpeg / yt-dlp | **是**，进入 Phase 0 的前提 |
| `video_ready` | AI 视频生成 | Kling API Key + 连通性 | 否，仅 Phase 5-6 需要 |
| `voice_ready` | 语音转写 | faster-whisper 可导入 | 否，降级跳过 |

**`data_ready` 不再需要任何 API Key** — 安装门槛大幅降低。

### Phase 0：需求录入

与 v1.0 相同。展示需求模板，支持自填或引导式填写。

### Phase 1：内容策略框架

与 v1.0 相同。为整个项目建立创作决策边界。

### Phase 2：每日数据采集（v2.0 重写）

| 步骤 | 方式 | 操作 |
|------|------|------|
| 1 热榜 | 浏览器 | 导航 douyin.com/hot → LLM 读取 Top 50 热点 |
| 2 关键词搜索 | 浏览器 | 导航 douyin.com/search/\<keyword\>?type=video → LLM 在脑内应用低粉高赞筛选 |
| 3 行业趋势 | web_search | 与 v1.0 相同 |
| 4 头部视频深度分析 | 浏览器+MCP | 选视频 → video_download → 帧分析 + audio_extract → audio_transcribe → 分析脚本结构 |
| 5 评论阅读 | 浏览器 | 在视频页面滚动到评论区，直接阅读真实评论 |
| 6 竞品分析（可选） | 浏览器 | 导航竞品主页 → 读 profile + 近期作品 → 下载 1-2 个爆款做深度分析 |
| 7 语音转写降级链 | MCP+浏览器 | ① faster-whisper → ② 浏览器读抖音AI章节要点 → ③ 跳过，仅用视觉分析 |

#### 低粉高赞筛选（自然语言版）

筛选标准（在 SKILL.md 中以自然语言描述）：
- 作者粉丝数 ≤ max_followers（默认 5 万）
- 点赞量相对于作者体量偏高（互动率高）
- 若符合条件不足 5 个：放宽粉丝上限 50%，降低互动率要求 25%
- 若仍不足：记录"关键词X结果有限"，继续

### Phase 3：数据分析 + 方向推荐

在 v1.0 基础上新增第 7 维度：

1. 热点匹配
2. 爆款切入角度
3. 评论洞察
4. 视频类型推荐
5. 竞品差异化
6. 内容形态适配性
7. **竞品脚本结构分析**（新）— 基于语音转写分析钩子类型、节奏、用词、情绪曲线

### Phase 4：脚本生成

与 v1.0 基本相同，三种输出格式（口播文案 / 可灵版 / Seedance 版）。

### Phase 4→5 门控检查

检查 `video_ready` 标志（替代旧的 `phase2_ready`）。

### Phase 5：视频生成

与 v1.0 相同（可灵 3.0 API）。

### Phase 6：视频拼接

与 v1.0 相同（FFmpeg concat + BGM）。

---

## 6. MCP 工具清单

共 9 个工具，分三个模块：

### media.py — 媒体处理（3 个，新增）

| 工具 | 功能 | 参数 |
|------|------|------|
| `video_download` | yt-dlp 下载抖音视频 + 可选帧提取 | `url`, `extract_frames=False`, `frame_interval=2.0` |
| `audio_extract` | FFmpeg 提取音频（16kHz mono WAV） | `video_path`, `output_format="wav"` |
| `audio_transcribe` | faster-whisper 本地语音转写 | `audio_path`, `language="zh"`, `model_size="medium"` |

### kling.py — 视频生成（4 个，保留）

| 工具 | 功能 |
|------|------|
| `kling_generate` | 文生视频（自动轮询） |
| `kling_generate_with_image` | 图生视频（首末帧衔接） |
| `kling_extract_frame` | 提取视频帧 |
| `kling_check_status` | 查询任务状态 |

### video.py — 视频处理 + 系统（2 个，改）

| 工具 | 功能 | 变更 |
|------|------|------|
| `video_concat` | FFmpeg 多段拼接 + BGM | 不变 |
| `env_check` | 环境检查 | 重构：返回 data_ready / video_ready / voice_ready 三个标志 |

---

## 7. 浏览器策略

### MVP（v2.0 当前）

- 意图导向指令：写"找到搜索框输入关键词"而非 CSS 选择器
- 步骤间 3-5 秒间隔，防触发反爬
- 每步以"你应该看到..."结尾，LLM 自验证
- 降级链：页面不可用时的备选方案

### V2（规划中）

- Camoufox 反检测浏览器
- 指纹随机化
- 代理轮转

### V3（远期）

- 多账号会话管理
- Cookie 池
- 验证码自动识别

---

## 8. 数据源规格

### 浏览器数据采集

| 数据 | URL 模式 | 采集方式 |
|------|---------|---------|
| 热榜 Top 50 | `douyin.com/hot` | 页面直读 |
| 视频搜索 | `douyin.com/search/<keyword>?type=video` | 页面直读 + 滚动加载 |
| 用户主页 | `douyin.com/user/<sec_uid>` | 页面直读 profile + 作品列表 |
| 视频评论 | 视频详情页评论区 | 滚动加载评论 |

### 精度说明

浏览器采集的数据精度低于 API（如播放量可能为"xx万"而非精确数字）。这是可接受的 tradeoff：**可靠性 > 精度**。语音转写能力补偿了深度分析的需求。

---

## 9. 视频生成规格

与 v1.0 相同，使用可灵 3.0 API：

| 参数 | 值 |
|------|-----|
| 模型 | kling-v3 |
| 分辨率 | 1080×1920（pro 模式） |
| 段落时长 | 10-15 秒 |
| 首末帧衔接 | kling_extract_frame → kling_generate_with_image |
| 角色一致性 | kling_elements（2-50 张参考图） |

---

## 10. 安装部署

### 依赖

| 依赖 | 类型 | 说明 |
|------|------|------|
| Python >= 3.10 | 运行时 | MCP Server |
| FFmpeg | 系统级 | 音视频处理 |
| yt-dlp | pip | 视频下载 |
| faster-whisper | pip（可选） | 语音转写，首次运行下载 ~1.5GB 模型 |
| OpenClaw >= v2026.1.29 | 平台 | Agent 运行环境 |

### 环境变量

| 变量 | 必需 | 说明 |
|------|------|------|
| KLING_ACCESS_KEY | 否（仅视频生成） | 可灵 API |
| KLING_SECRET_KEY | 否（仅视频生成） | 可灵 API |

**v2.0 不再需要 TIKHUB_API_KEY**。

### 安装步骤

```bash
bash install.sh
```

安装脚本自动完成：检查 OpenClaw → 复制 Skill → 安装 Python 依赖 → 检查 FFmpeg/yt-dlp → 配置 MCP Server → 可选配置 Kling Key → 验证。

---

## 11. SKILL.md 元数据

```yaml
metadata:
  openclaw:
    requires:
      bins:
        - python3
        - ffmpeg
        - yt-dlp
      env: []
      optionalEnv:
        - KLING_ACCESS_KEY
        - KLING_SECRET_KEY
    emoji: "🎬"
```

---

## 12. 风险矩阵

| 风险 | 概率 | 影响 | 缓解 |
|------|------|------|------|
| 抖音反爬阻断浏览器 | 高 | 数据采集中断 | 步骤间 3-5s 等待 + CAPTCHA 降级 + V2 Camoufox |
| 页面结构变化导致指令失效 | 中 | 采集失败 | 意图导向指令 + LLM 实时适应 + references/ 独立更新 |
| yt-dlp 抖音提取器失效 | 中 | 视频下载失败 | 活跃维护 + pip install --upgrade yt-dlp + 浏览器截图降级 |
| whisper 首次下载 1.5GB | 确定 | 首次等待 | env_check 提前提示 + install.sh 可选预下载 |
| 浏览器数据精度低于 API | 确定 | 分析精度下降 | 可接受 tradeoff + 语音转写补偿深度分析 |

---

## 13. 安全合规

- API Key 仅存储在环境变量中，绝不硬编码或进入聊天记录
- 浏览器访问遵循抖音 robots.txt 和使用条款
- 不存储用户个人信息，仅处理公开内容数据
- 视频下载仅用于内容分析，不进行二次分发
- 语音转写完全在本地执行，音频数据不上传到任何外部服务

---

## 14. 开发计划

### Phase A：代码基础

| # | 文件 | 操作 |
|---|------|------|
| A1 | `mcp_server/tools/media.py` | 新建 3 工具 |
| A2 | `mcp_server/server.py` | 去掉 tikhub_server，加 media_server |
| A3 | `mcp_server/tools/video.py` | env_check 重构 |
| A4 | `mcp_server/utils/auth.py` | 删除 TikHub 认证 |
| A5 | `requirements.txt` | 更新依赖 |

### Phase B：SKILL.md 重写（第二轮，需实测）

| # | 内容 |
|---|------|
| B1-B5 | SKILL.md 元数据 + 环境检查 + Phase 2 重写 + Phase 3 扩展 + 错误处理 |

### Phase C：清理

| # | 文件 | 操作 |
|---|------|------|
| C1 | `mcp_server/tools/tikhub.py` | 删除 |
| C2 | `mcp_server/utils/filters.py` | 删除 |

### Phase D：文档

| # | 文件 | 操作 |
|---|------|------|
| D1 | `PRD.md` | 完整重写 v2.0 |
| D2 | `references/browser-navigation.md` | 新建（第二轮） |
| D3 | `install.sh` | 更新 |
| D4 | `CLAUDE.md` | 更新 |
| D5 | `README.md` | 更新 |

---

## 15. 迁移指南

### v1.0 → v2.0 升级步骤

1. **更新代码**：`git pull` 获取最新代码
2. **安装新依赖**：`pip install -r requirements.txt`（新增 yt-dlp、faster-whisper）
3. **删除旧环境变量**：TIKHUB_API_KEY 不再需要，可从环境变量和 openclaw.json 中移除
4. **更新 MCP 配置**：重新运行 `bash install.sh` 更新 openclaw.json
5. **验证**：运行 `env_check` 确认三个就绪标志

### 破坏性变更

- 删除 7 个 TikHub 工具（tikhub_hot_list 等）
- 删除 filters.py（低粉高赞筛选迁至 SKILL.md 自然语言指令）
- env_check 返回值变更：phase1_ready / phase2_ready → data_ready / video_ready / voice_ready

---

## 附录

### A. yt-dlp 命令参考

```bash
# 下载抖音视频（最佳画质）
yt-dlp -f best "https://www.douyin.com/video/xxx"

# 下载并提取音频
yt-dlp -x --audio-format wav "https://www.douyin.com/video/xxx"

# 更新 yt-dlp
pip install --upgrade yt-dlp
```

### B. faster-whisper 模型对照

| 模型 | 大小 | 中文准确率 | 推荐场景 |
|------|------|-----------|---------|
| tiny | ~75MB | ~80% | 快速测试 |
| base | ~150MB | ~85% | 开发调试 |
| small | ~500MB | ~90% | 日常使用 |
| medium | ~1.5GB | ~95% | **推荐**（精度/速度平衡） |
| large-v3 | ~3GB | ~97% | 最高精度 |

### C. 可灵 3.0 API

参见 v1.0 附录，无变化。

### D. FFmpeg 常用命令

```bash
# 提取音频（16kHz mono WAV）
ffmpeg -i video.mp4 -vn -acodec pcm_s16le -ar 16000 -ac 1 audio.wav

# 每 2 秒提取一帧
ffmpeg -i video.mp4 -vf "fps=0.5" -q:v 2 frame_%03d.jpg

# 拼接视频
ffmpeg -f concat -safe 0 -i filelist.txt -c copy output.mp4
```
