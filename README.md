# douyin-video-forge

抖音短视频全链路自动化制作 — OpenClaw Skill

## 项目简介

`douyin-video-forge` 是一个 OpenClaw Skill，覆盖抖音短视频制作的完整链路：

```
热点数据采集 → 低粉高赞视频筛选 → 竞品分析 → 数据洞察 → 双版本脚本生成 → AI 视频生成 → 多段拼接成片
```

运营人员只需通过 OpenClaw 聊天界面用自然语言描述需求，Skill 会自动完成从趋势采集到成品视频的全部流程。支持 Cron 多日计划，每日基于最新热点数据自动生成内容。

### 一期 / 二期范围

| 阶段 | 内容 | 所需 API |
|------|------|----------|
| **一期**（当前可用） | Phase 0-4：需求录入 → 策略 → 数据采集 → 分析 → 脚本生成 | 仅 TikHub |
| **二期**（待可灵 Key） | Phase 5-6：AI 视频生成 → 拼接成片 | TikHub + 可灵 |

一期即可完成完整的数据驱动脚本生产流程，运营可直接使用脚本在 Seedance 等平台手动生成视频。

---

## 功能特性

- **自动采集抖音热榜/热搜/热词** — 实时获取抖音四大热榜数据（总热榜、热搜、热门话题、热词）
- **低粉高赞视频智能筛选（阶梯降级）** — 自动过滤低粉高赞视频，结果不足时逐级放宽条件，最多降级至 50%
- **竞品分析与粉丝画像** — 分析竞品账号内容表现、爆款率，获取粉丝年龄/性别/地域/活跃时段
- **双版本脚本生成（可灵 + Seedance）** — 同时输出可灵 API 可直接调用的脚本和 Seedance 手动输入的脚本
- **可灵 3.0 API 自动视频生成** — 文生视频 + 图生视频，首末帧衔接确保段落连贯
- **FFmpeg 多段拼接 + BGM** — 自动拼接多段视频并叠加背景音乐
- **Cron 多日计划自动化** — Skill 自动创建定时任务，每日结合最新热点生成内容
- **灵活排期（周末多发、工作日少发）** — 支持自定义每日发布数量和时间段

---

## 环境要求

| 依赖 | 最低版本 | 说明 |
|------|---------|------|
| OpenClaw | >= v2026.1.29 | 安全补丁 |
| Python | >= 3.10 | MCP Server 运行时 |
| FFmpeg | 任意版本 | 视频拼接与帧提取 |
| Node.js | >= 22 | OpenClaw 自身要求 |

---

## 快速安装

```bash
bash install.sh
```

安装脚本会自动完成以下步骤：

1. 检查 OpenClaw 版本（>= v2026.1.29）
2. 克隆仓库至 `~/.openclaw/skills/douyin-video-forge/`
3. 安装 Python 依赖（`pip install -r requirements.txt`）
4. 检测 Docker 环境并自动配置
5. 写入 MCP Server 配置至 `openclaw.json`
6. 交互式引导配置 API Key
7. 启动 MCP Server 验证连通性

---

## 手动安装

```bash
# 1. 克隆仓库
git clone <repo-url> ~/.openclaw/skills/douyin-video-forge
cd ~/.openclaw/skills/douyin-video-forge

# 2. 安装 Python 依赖（fastmcp, httpx, pyjwt）
pip install -r requirements.txt

# 3. 确认 FFmpeg 已安装（macOS: brew install ffmpeg / Ubuntu: apt-get install ffmpeg）
ffmpeg -version

# 4. 配置环境变量（添加到 ~/.zshrc 或 ~/.bashrc）
export TIKHUB_API_KEY="your-tikhub-api-key"
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
        "TIKHUB_API_KEY": "${TIKHUB_API_KEY}",
        "KLING_ACCESS_KEY": "${KLING_ACCESS_KEY}",
        "KLING_SECRET_KEY": "${KLING_SECRET_KEY}"
      }
    }
  }
}
```

**6. 验证安装** — 在 OpenClaw 中输入「帮我检查一下 douyin-video-forge 的环境配置」，Skill 会调用 `env_check` 检查所有依赖和连通性。

---

## Docker 安装指南

> `install.sh` 会自动检测 Docker 环境并完成下述配置，通常无需手动操作。

**FFmpeg 安装** — 设置环境变量让容器启动时自动安装：

```bash
OPENCLAW_DOCKER_APT_PACKAGES="ffmpeg"
```

**网络出站** — 确保容器可访问 `api.tikhub.io`（国际）/ `api.tikhub.dev`（中国）/ `api.klingai.com`。

**环境变量注入** — 在 `openclaw.json` 中通过 `docker.env` 注入 API Key：

```json
{
  "agents": {
    "defaults": {
      "sandbox": {
        "docker": {
          "env": {
            "TIKHUB_API_KEY": "your-tikhub-api-key",
            "KLING_ACCESS_KEY": "your-kling-access-key",
            "KLING_SECRET_KEY": "your-kling-secret-key"
          }
        }
      }
    }
  }
}
```

---

## API Key 获取指南

| Key | 获取地址 | 说明 |
|-----|---------|------|
| `TIKHUB_API_KEY` | [tikhub.io](https://tikhub.io) | 注册后在控制台创建，用于数据采集（热榜、搜索、统计、竞品分析） |
| `KLING_ACCESS_KEY` | [klingai.com](https://klingai.com) | 在「API 管理」中创建，用于视频生成 |
| `KLING_SECRET_KEY` | [klingai.com](https://klingai.com) | 与 Access Key 配对使用，Skill 自动签发 JWT |

> API Key 仅存储在环境变量中，不会写入代码或进入聊天记录。

---

## 使用方法

安装完成后，直接在 OpenClaw 中用自然语言对话即可。Skill 会根据对话内容自动激活。

### 示例提示语

```
# 新项目启动
我们接了一个新客户「花漾肌密」，做玻尿酸精华液推广视频。
目标人群20-35岁女性，3月15日到22日发布20个视频，周一至五每天2个，周末每天3个。

# 日常热点
帮我看看今天抖音上有什么和护肤相关的热点，适合我们这个项目的。

# 竞品分析
帮我分析一下 @润百颜官方旗舰店 这个账号的内容表现和粉丝画像。

# 脚本生成
基于今天的热点数据，帮我生成3个45秒的种草类短视频脚本。
```

### 工作流概览

```
1. 需求录入 → 运营填写/口述项目需求
2. 内容策略 → Skill 生成品牌定位与内容方向（一次性）
3. 每日循环 → Cron 自动触发：
   ├── 数据采集（热榜 + 低粉高赞视频）
   ├── 数据分析（热点匹配 + 方向推荐）
   ├── 脚本生成（可灵版 + Seedance 版）
   ├── 视频生成（可灵 API 分段生成）
   └── 视频拼接（FFmpeg + BGM）
4. 成品输出 → MP4 1080x1920 竖屏视频
```

---

## MCP 工具参考

Skill 提供 13 个 MCP 工具：

| # | 工具名称 | 类别 | 功能说明 |
|---|----------|------|----------|
| 1 | `tikhub_hot_list` | 采集 | 获取抖音热榜/热搜/热门话题/热词 |
| 2 | `tikhub_search` | 采集 | 关键词搜索 + 低粉高赞自动筛选（含阶梯降级） |
| 3 | `tikhub_video_stats` | 采集 | 批量获取视频统计数据（播放、点赞、评论、转发、收藏） |
| 4 | `tikhub_video_comments` | 采集 | 获取视频评论词云（高频词 + 情感倾向） |
| 5 | `tikhub_account_analysis` | 采集 | 竞品账号基础信息 + 近期作品（支持 sec_uid/uid/抖音号） |
| 6 | `tikhub_fan_portrait` | 采集 | 粉丝数据分析（基础套餐返回 profile，高级套餐含粉丝列表） |
| 7 | `tikhub_download_video` | 采集 | 下载视频 + 可选关键帧提取（用于多模态分析） |
| 8 | `kling_generate` | 生成 | 文生视频，提交可灵 3.0 任务并自动等待完成 |
| 9 | `kling_generate_with_image` | 生成 | 图生视频，以首帧图片 + prompt 生成（段落衔接） |
| 10 | `kling_extract_frame` | 处理 | 提取视频帧（默认最后一帧，用于段落间衔接） |
| 11 | `kling_check_status` | 查询 | 查询可灵视频生成任务状态 |
| 12 | `video_concat` | 处理 | FFmpeg 多段视频拼接 + BGM 叠加 |
| 13 | `env_check` | 系统 | 检查环境配置（Python、FFmpeg、API Key、网络连通性） |

---

## 成本估算

### TikHub API

| 项目 | 费用 |
|------|------|
| 单次请求 | ~$0.001 |
| 典型每日用量（热榜 + 搜索 + 统计 + 评论） | ~$0.05 |
| 每月（按 30 天计） | ~$1.50 |

### 可灵 3.0 API

| 项目 | 费用 |
|------|------|
| 每秒视频 | ~$0.084 - $0.168（取决于模式） |
| 单个 45s 视频（3-4 段 x 10-15s） | ~$3.78 - $7.56 |
| 单个 10s 段落 | ~$0.84 - $1.68 |

### 月度估算（典型用量）

| 场景 | 视频数 | TikHub | 可灵 API | 合计 |
|------|--------|--------|----------|------|
| 轻度使用（仅脚本，不生成视频） | — | ~$1.50 | $0 | ~$1.50 |
| 中度使用（每日 2 个 45s 视频） | 60 个/月 | ~$1.50 | ~$227 - $454 | ~$229 - $456 |
| 高强度使用（每日 3 个 45s 视频） | 90 个/月 | ~$1.50 | ~$340 - $680 | ~$342 - $682 |

> 仅输出脚本（用于 Seedance 手动生成或其他用途）时，只需 TikHub 费用，无可灵 API 费用。

---

## 常见问题 (FAQ)

**Q: 必须配置所有 API Key 才能使用吗？**
不需要。一期功能（热点采集 + 数据分析 + 脚本生成）仅需 `TIKHUB_API_KEY`。可灵相关 Key 仅二期（AI 视频自动生成）才需要。`env_check` 会返回 `phase1_ready` / `phase2_ready` 标志，明确告知当前可用范围。

**Q: 搜索结果太少怎么办？**
`tikhub_search` 内置阶梯降级：结果不足时自动放宽条件（提高粉丝上限、降低互动率），最多降级至 50%。也可手动调整 `max_followers` 和 `min_like_ratio`。

**Q: 推荐使用什么 LLM 模型？**
强烈推荐 **Claude Sonnet 4.6+**，数据分析和创意脚本需要强推理能力。MiniMax M2.5 可正常调用工具，但脚本质量偏低。

**Q: 视频段落之间如何保持连贯？**
使用「首末帧衔接」：提取段落 1 最后一帧作为段落 2 首帧输入。配合 `kling_elements` 参数（2-50 张参考图）保持角色一致性。

**Q: 可以在中国大陆网络环境中使用吗？**
可以。设置 `TIKHUB_BASE_URL=https://api.tikhub.dev` 切换 TikHub 中国节点。可灵 API 为国内服务，直连即可。

**Q: Cron 任务如何管理？**
Skill 根据发布计划自动创建 Cron 任务（`~/.openclaw/cron/jobs.json`），无需手动配置。每日自动采集最新热点，确保内容紧跟当日趋势。

---

## 卸载

```bash
bash install.sh --uninstall
```

此命令会移除 `openclaw.json` 中的 MCP Server 配置、删除 `~/.openclaw/skills/douyin-video-forge/` 目录并清理 Cron 任务。环境变量需手动从 shell 配置文件中移除。
