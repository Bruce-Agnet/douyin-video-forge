# douyin-video-forge

抖音短视频全链路自动化制作 — OpenClaw Skill

## 项目简介

`douyin-video-forge` 是一个 OpenClaw Skill，覆盖抖音短视频制作的完整链路：

```
热点数据采集（浏览器）→ 低粉高赞视频筛选 → 竞品分析 → 语音转写分析 →
数据洞察 → 双版本脚本生成 → AI 视频生成 → 多段拼接成片
```

运营人员只需通过 OpenClaw 聊天界面用自然语言描述需求，Skill 会自动完成从趋势采集到成品视频的全部流程。

### v2.0 核心变化

**零第三方数据 API 依赖** — 所有数据采集通过 OpenClaw 内置浏览器完成，无需付费 API Key 即可使用全部数据采集功能。

| 阶段 | 内容 | 所需依赖 |
|------|------|----------|
| **数据采集+脚本生成** | Phase 0-4：需求 → 策略 → 浏览器采集 → 分析 → 脚本 | Python + FFmpeg + yt-dlp（全免费） |
| **AI 视频生成**（可选） | Phase 5-6：可灵 API 生成 → 拼接成片 | 可灵 API Key |

---

## 功能特性

- **浏览器自动采集抖音热榜/搜索** — 直接浏览 douyin.com，零 API 成本
- **低粉高赞视频智能筛选** — LLM 自然语言指令实现阶梯降级筛选
- **竞品分析** — 浏览器访问竞品主页，分析内容表现
- **语音转写深度分析** — faster-whisper 本地转写，分析脚本结构、钩子、节奏
- **双版本脚本生成（可灵 + Seedance）** — 同时输出可灵 API 可直接调用的脚本和 Seedance 手动输入的脚本
- **可灵 3.0 API 自动视频生成** — 文生视频 + 图生视频，首末帧衔接确保段落连贯
- **FFmpeg 多段拼接 + BGM** — 自动拼接多段视频并叠加背景音乐
- **Cron 多日计划自动化** — 每日结合最新热点生成内容

---

## 环境要求

| 依赖 | 最低版本 | 说明 |
|------|---------|------|
| OpenClaw | >= v2026.1.29 | 安全补丁 |
| Python | >= 3.10 | MCP Server 运行时 |
| FFmpeg | 任意版本 | 音视频处理 |
| yt-dlp | 任意版本 | 抖音视频下载 |
| faster-whisper | >= 1.0.0 | 可选，语音转写 |

---

## 快速安装

```bash
bash install.sh
```

安装脚本会自动完成：

1. 检查 OpenClaw 版本（>= v2026.1.29）
2. 复制 Skill 至 `~/.openclaw/skills/douyin-video-forge/`
3. 安装 Python 依赖（fastmcp, httpx, pyjwt, yt-dlp, faster-whisper）
4. 检查 FFmpeg 和 yt-dlp
5. 写入 MCP Server 配置至 `openclaw.json`
6. 可选配置 Kling API Key
7. 验证安装

---

## 手动安装

```bash
# 1. 克隆仓库
git clone <repo-url> ~/.openclaw/skills/douyin-video-forge
cd ~/.openclaw/skills/douyin-video-forge

# 2. 安装 Python 依赖
pip install -r requirements.txt

# 3. 确认系统依赖
ffmpeg -version
yt-dlp --version

# 4. （可选）配置可灵 API Key
export KLING_ACCESS_KEY="your-kling-access-key"
export KLING_SECRET_KEY="your-kling-secret-key"
```

**5. 注册 MCP Server** — 在 `openclaw.json` 的 `mcpServers` 中添加：

```json
{
  "mcpServers": {
    "douyin-video-forge": {
      "command": "python3",
      "args": ["-m", "mcp_server.server"],
      "cwd": "~/.openclaw/skills/douyin-video-forge",
      "env": {
        "KLING_ACCESS_KEY": "${KLING_ACCESS_KEY}",
        "KLING_SECRET_KEY": "${KLING_SECRET_KEY}"
      }
    }
  }
}
```

**6. 验证安装** — 在 OpenClaw 中输入「帮我检查一下 douyin-video-forge 的环境配置」，Skill 会调用 `env_check` 检查所有依赖。

---

## 使用方法

安装完成后，直接在 OpenClaw 中用自然语言对话即可。

### 示例提示语

```
# 新项目启动
我们接了一个新客户「花漾肌密」，做玻尿酸精华液推广视频。
目标人群20-35岁女性，3月15日到22日发布20个视频，周一至五每天2个，周末每天3个。

# 日常热点
帮我看看今天抖音上有什么和护肤相关的热点。

# 竞品分析
帮我分析一下润百颜这个账号的内容表现。

# 脚本生成
基于今天的热点数据，帮我生成3个45秒的种草类短视频脚本。
```

### 工作流概览

```
1. 需求录入 → 运营填写/口述项目需求
2. 内容策略 → Skill 生成品牌定位与内容方向（一次性）
3. 每日循环 →
   ├── 浏览器采集（热榜 + 搜索 + 竞品）
   ├── 视频下载 + 语音转写
   ├── 数据分析（热点匹配 + 脚本结构分析 + 方向推荐）
   ├── 脚本生成（口播文案 / 可灵版 / Seedance 版）
   ├── 视频生成（可灵 API，可选）
   └── 视频拼接（FFmpeg + BGM）
4. 成品输出 → MP4 1080x1920 竖屏视频
```

---

## MCP 工具参考

Skill 提供 9 个 MCP 工具：

| # | 工具名称 | 类别 | 功能说明 |
|---|----------|------|----------|
| 1 | `video_download` | 媒体 | yt-dlp 下载抖音视频 + 可选帧提取 |
| 2 | `audio_extract` | 媒体 | FFmpeg 提取音频（16kHz mono WAV） |
| 3 | `audio_transcribe` | 媒体 | faster-whisper 本地语音转写 |
| 4 | `kling_generate` | 生成 | 文生视频，提交可灵 3.0 任务并自动等待完成 |
| 5 | `kling_generate_with_image` | 生成 | 图生视频，以首帧图片 + prompt 生成（段落衔接） |
| 6 | `kling_extract_frame` | 处理 | 提取视频帧（默认最后一帧，用于段落间衔接） |
| 7 | `kling_check_status` | 查询 | 查询可灵视频生成任务状态 |
| 8 | `video_concat` | 处理 | FFmpeg 多段视频拼接 + BGM 叠加 |
| 9 | `env_check` | 系统 | 检查环境配置（返回 data_ready / video_ready / voice_ready） |

---

## 成本估算

### v2.0 成本结构

| 场景 | 数据采集 | 可灵 API | 合计 |
|------|---------|----------|------|
| 仅脚本（不生成视频） | **$0**（浏览器免费） | $0 | **$0** |
| 每日 2 个 45s 视频 | $0 | ~$227-454/月 | ~$227-454/月 |
| 每日 3 个 45s 视频 | $0 | ~$340-680/月 | ~$340-680/月 |

> v2.0 完全消除了 TikHub API 的月费（v1.0 约 $1.50/月）。仅输出脚本时总成本为零。

---

## API Key 获取指南

| Key | 获取地址 | 说明 |
|-----|---------|------|
| `KLING_ACCESS_KEY` | [klingai.com](https://klingai.com) | 在「API 管理」中创建，用于视频生成（可选） |
| `KLING_SECRET_KEY` | [klingai.com](https://klingai.com) | 与 Access Key 配对使用 |

> API Key 仅存储在环境变量中，不会写入代码或进入聊天记录。

---

## 常见问题 (FAQ)

**Q: 需要配置 API Key 才能使用吗？**
不需要。数据采集和脚本生成（Phase 0-4）完全通过浏览器完成，无需任何 API Key。可灵 Key 仅 AI 视频自动生成（Phase 5-6）才需要。

**Q: 搜索结果太少怎么办？**
LLM 在浏览器采集时会自动应用低粉高赞筛选，结果不足时自动放宽条件。

**Q: 语音转写需要 GPU 吗？**
faster-whisper 默认使用 CPU（int8 量化），无需 GPU。有 GPU 时自动使用（device="auto"）。首次运行会下载 ~1.5GB 的 medium 模型。

**Q: 推荐使用什么 LLM 模型？**
强烈推荐 **Claude Sonnet 4.6+**，数据分析和创意脚本需要强推理能力。

**Q: 视频段落之间如何保持连贯？**
使用「首末帧衔接」：提取段落 1 最后一帧作为段落 2 首帧输入。配合 `kling_elements` 参数保持角色一致性。

**Q: Cron 任务如何管理？**
Skill 根据发布计划自动创建 Cron 任务，无需手动配置。

---

## 卸载

```bash
bash install.sh --uninstall
```

此命令会移除 MCP Server 配置和 Skill 目录。环境变量需手动移除。
