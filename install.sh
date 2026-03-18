#!/bin/bash
set -e

# ============================================================
# douyin-video-forge OpenClaw Skill 一键安装脚本
# ============================================================
# 用法:
#   bash install.sh            # 安装
#   bash install.sh --uninstall # 卸载
# ============================================================

# --- 颜色定义 ---
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m' # 无颜色

# --- 常量 ---
SKILL_NAME="douyin-video-forge"
SKILL_DIR="$HOME/.openclaw/skills/$SKILL_NAME"
OPENCLAW_CONFIG="$HOME/.openclaw/openclaw.json"
REQUIRED_OPENCLAW_VERSION="v2026.1.29"
REQUIRED_PYTHON_MINOR=10
SCRIPT_SOURCE_DIR="$(cd "$(dirname "$0")" && pwd)"

# --- 辅助函数 ---
info()    { echo -e "${BLUE}[信息]${NC} $1"; }
success() { echo -e "${GREEN}[成功]${NC} $1"; }
warn()    { echo -e "${YELLOW}[警告]${NC} $1"; }
error()   { echo -e "${RED}[错误]${NC} $1"; }
step()    { echo -e "\n${BOLD}${CYAN}[$1/10]${NC} ${BOLD}$2${NC}"; }

# 版本号比较: 返回 0 表示 $1 >= $2
version_gte() {
    local v1="${1#v}"
    local v2="${2#v}"
    # 将版本号转为可比较的数字序列
    printf '%s\n%s' "$v2" "$v1" | sort -t. -k1,1n -k2,2n -k3,3n | head -n1 | grep -qF "$v2"
}

# 确认提示，默认为 Y
confirm() {
    local prompt="$1 [Y/n] "
    read -r -p "$(echo -e "${YELLOW}${prompt}${NC}")" answer
    case "$answer" in
        [nN]|[nN][oO]) return 1 ;;
        *) return 0 ;;
    esac
}

# ============================================================
# 卸载逻辑
# ============================================================
if [[ "${1:-}" == "--uninstall" ]]; then
    echo -e "${BOLD}${RED}=== douyin-video-forge 卸载程序 ===${NC}\n"

    if [[ -d "$SKILL_DIR" ]]; then
        if confirm "确定要删除技能目录 $SKILL_DIR 吗？"; then
            rm -rf "$SKILL_DIR"
            success "已删除技能目录"
        fi
    else
        info "技能目录不存在，跳过"
    fi

    # 从 openclaw.json 中移除 MCP 服务器配置
    if [[ -f "$OPENCLAW_CONFIG" ]] && command -v jq &>/dev/null; then
        if jq -e ".mcpServers.\"$SKILL_NAME\"" "$OPENCLAW_CONFIG" &>/dev/null; then
            if confirm "要从 openclaw.json 中移除 MCP 服务器配置吗？"; then
                tmp=$(mktemp)
                jq "del(.mcpServers.\"$SKILL_NAME\")" "$OPENCLAW_CONFIG" > "$tmp" && mv "$tmp" "$OPENCLAW_CONFIG"
                success "已从 openclaw.json 中移除配置"
            fi
        else
            info "openclaw.json 中无相关配置，跳过"
        fi
    fi

    echo ""
    success "卸载完成！如需重新安装，请运行: bash install.sh"
    exit 0
fi

# ============================================================
# 安装开始
# ============================================================
echo -e "${BOLD}${CYAN}"
echo "╔══════════════════════════════════════════════════════╗"
echo "║     douyin-video-forge OpenClaw Skill 安装程序      ║"
echo "║                    v2.0                             ║"
echo "╚══════════════════════════════════════════════════════╝"
echo -e "${NC}"

# ----------------------------------------------------------
# 步骤 1: OpenClaw 版本检查
# ----------------------------------------------------------
step 1 "检查 OpenClaw CLI"

if ! command -v openclaw &>/dev/null; then
    error "未检测到 openclaw CLI"
    echo ""
    echo -e "  请先安装 OpenClaw CLI:"
    echo -e "  ${CYAN}curl -fsSL https://openclaw.dev/install.sh | bash${NC}"
    echo -e "  或访问 ${CYAN}https://github.com/openclaw/openclaw${NC}"
    echo ""
    exit 1
fi

OPENCLAW_VERSION=$(openclaw --version 2>/dev/null | grep -oE 'v[0-9]+\.[0-9]+\.[0-9]+' | head -1)
if [[ -z "$OPENCLAW_VERSION" ]]; then
    warn "无法解析 openclaw 版本号，继续安装..."
elif ! version_gte "$OPENCLAW_VERSION" "$REQUIRED_OPENCLAW_VERSION"; then
    error "OpenClaw 版本过低: $OPENCLAW_VERSION (需要 >= $REQUIRED_OPENCLAW_VERSION)"
    echo -e "  请升级: ${CYAN}openclaw update${NC}"
    exit 1
else
    success "OpenClaw 版本: $OPENCLAW_VERSION"
fi

# ----------------------------------------------------------
# 步骤 2: 复制技能到 skills 目录
# ----------------------------------------------------------
step 2 "安装技能到 skills 目录"

mkdir -p "$HOME/.openclaw/skills"

if [[ -d "$SKILL_DIR" ]]; then
    warn "技能目录已存在: $SKILL_DIR"
    if confirm "是否覆盖更新？"; then
        rm -rf "$SKILL_DIR"
        info "已清除旧版本，正在重新安装..."
    else
        info "保留现有安装，跳过复制"
    fi
fi

if [[ ! -d "$SKILL_DIR" ]]; then
    cp -R "$SCRIPT_SOURCE_DIR" "$SKILL_DIR"
    success "已安装到 $SKILL_DIR"
else
    success "使用现有安装: $SKILL_DIR"
fi

# ----------------------------------------------------------
# 步骤 3: Python 依赖安装
# ----------------------------------------------------------
step 3 "检查 Python 环境并安装依赖"

if ! command -v python3 &>/dev/null; then
    error "未检测到 python3，请先安装 Python 3.10+"
    exit 1
fi

PYTHON_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
PYTHON_MINOR=$(python3 -c "import sys; print(sys.version_info.minor)")

if [[ "$PYTHON_MINOR" -lt "$REQUIRED_PYTHON_MINOR" ]]; then
    error "Python 版本过低: $PYTHON_VERSION (需要 >= 3.10)"
    exit 1
fi
success "Python 版本: $PYTHON_VERSION"

info "正在安装 Python 依赖..."
if [[ -f "$SKILL_DIR/requirements.txt" ]]; then
    python3 -m pip install -r "$SKILL_DIR/requirements.txt" --quiet 2>&1 | tail -5
    success "Python 依赖安装完成"
else
    warn "未找到 requirements.txt，跳过依赖安装"
fi

# ----------------------------------------------------------
# 步骤 4: Docker 环境检测
# ----------------------------------------------------------
step 4 "检测 Docker 环境"

IN_DOCKER=false
if [[ -f /.dockerenv ]] || grep -qsE '(docker|containerd)' /proc/1/cgroup 2>/dev/null; then
    IN_DOCKER=true
fi

if $IN_DOCKER; then
    warn "检测到 Docker 环境，正在配置..."
    export OPENCLAW_DOCKER_APT_PACKAGES="ffmpeg"
    info "已设置 OPENCLAW_DOCKER_APT_PACKAGES=\"ffmpeg\""
    info "请确保容器具有出站网络访问权限（Kling API）"
    echo "OPENCLAW_DOCKER_APT_PACKAGES=ffmpeg" > "$SKILL_DIR/.docker_env"
    success "Docker 环境配置完成"
else
    success "非 Docker 环境，跳过容器特殊配置"
fi

# ----------------------------------------------------------
# 步骤 5: FFmpeg / yt-dlp 检查
# ----------------------------------------------------------
step 5 "检查 FFmpeg 和 yt-dlp"

if command -v ffmpeg &>/dev/null; then
    FFMPEG_VERSION=$(ffmpeg -version 2>/dev/null | head -1 | grep -oE '[0-9]+\.[0-9]+(\.[0-9]+)?' | head -1)
    success "FFmpeg 已安装 (版本: $FFMPEG_VERSION)"
else
    warn "未检测到 FFmpeg，视频处理功能需要 FFmpeg"
    OS_TYPE="$(uname -s)"
    case "$OS_TYPE" in
        Darwin) echo -e "  安装: ${CYAN}brew install ffmpeg${NC}" ;;
        Linux)  echo -e "  安装: ${CYAN}sudo apt install -y ffmpeg${NC}" ;;
        *)      echo -e "  请手动安装: ${CYAN}https://ffmpeg.org/download.html${NC}" ;;
    esac
    warn "你可以稍后安装 FFmpeg，安装将继续..."
fi

if command -v yt-dlp &>/dev/null; then
    YTDLP_VERSION=$(yt-dlp --version 2>/dev/null)
    success "yt-dlp 已安装 (版本: $YTDLP_VERSION)"
else
    warn "未检测到 yt-dlp，正在尝试安装..."
    if python3 -m pip install yt-dlp --quiet 2>/dev/null; then
        success "yt-dlp 安装成功"
    else
        warn "yt-dlp 安装失败，请手动运行: pip install yt-dlp"
    fi
fi

# 可选：检查 faster-whisper
info "检查 faster-whisper（可选，用于语音转写）..."
if python3 -c "import faster_whisper" 2>/dev/null; then
    success "faster-whisper 已安装"
else
    info "faster-whisper 未安装（语音转写不可用）"
    echo -e "  安装: ${CYAN}pip install faster-whisper${NC}"
    echo -e "  注意：首次转写时会自动下载 ~1.5GB 模型"
fi

# ----------------------------------------------------------
# 步骤 6: MCP Server 配置
# ----------------------------------------------------------
step 6 "配置 MCP 服务器"

# 检查 jq 是否可用
if ! command -v jq &>/dev/null; then
    error "未检测到 jq，JSON 配置需要 jq 工具"
    OS_TYPE="$(uname -s)"
    case "$OS_TYPE" in
        Darwin) echo -e "  安装: ${CYAN}brew install jq${NC}" ;;
        Linux)  echo -e "  安装: ${CYAN}sudo apt install -y jq${NC}" ;;
    esac
    exit 1
fi

# 确保配置文件存在且格式正确
mkdir -p "$(dirname "$OPENCLAW_CONFIG")"
if [[ ! -f "$OPENCLAW_CONFIG" ]]; then
    echo '{}' > "$OPENCLAW_CONFIG"
    info "已创建 openclaw.json 配置文件"
fi

# 验证 JSON 格式
if ! jq empty "$OPENCLAW_CONFIG" 2>/dev/null; then
    error "openclaw.json 格式错误，请检查文件: $OPENCLAW_CONFIG"
    exit 1
fi

# 确保 mcpServers 字段存在
tmp=$(mktemp)
jq '.mcpServers //= {}' "$OPENCLAW_CONFIG" > "$tmp" && mv "$tmp" "$OPENCLAW_CONFIG"

# 写入 MCP 服务器基础配置
tmp=$(mktemp)
jq --arg name "$SKILL_NAME" \
   --arg cmd "python3" \
   --arg dir "$SKILL_DIR" \
   '.mcpServers[$name] = {
        "command": $cmd,
        "args": ["-m", "mcp_server.server"],
        "cwd": $dir,
        "env": (.mcpServers[$name].env // {})
    }' "$OPENCLAW_CONFIG" > "$tmp" && mv "$tmp" "$OPENCLAW_CONFIG"

success "MCP 服务器配置已写入 $OPENCLAW_CONFIG"

# ----------------------------------------------------------
# 步骤 7: 交互式 API Key 设置
# ----------------------------------------------------------
step 7 "配置 API 密钥"

echo ""
info "Kling AI API 密钥（可选 — 用于 AI 视频生成）"
echo -e "  获取地址: ${CYAN}https://klingai.com${NC}"
echo -e "  留空可稍后手动配置，数据采集和脚本生成无需 API Key"
echo ""

read -r -p "$(echo -e "  ${YELLOW}KLING_ACCESS_KEY: ${NC}")" KLING_ACCESS_KEY
read -r -p "$(echo -e "  ${YELLOW}KLING_SECRET_KEY: ${NC}")" KLING_SECRET_KEY
echo ""

if [[ -z "$KLING_ACCESS_KEY" || -z "$KLING_SECRET_KEY" ]]; then
    info "未配置 Kling API 密钥 — 数据采集和脚本生成仍可正常使用"
fi

# ----------------------------------------------------------
# 步骤 8: 写入 API Key 到 openclaw.json
# ----------------------------------------------------------
step 8 "保存 API 密钥到配置文件"

# 构建 env 对象
ENV_JSON="{}"
if [[ -n "$KLING_ACCESS_KEY" ]]; then
    ENV_JSON=$(echo "$ENV_JSON" | jq --arg k "$KLING_ACCESS_KEY" '. + {"KLING_ACCESS_KEY": $k}')
fi
if [[ -n "$KLING_SECRET_KEY" ]]; then
    ENV_JSON=$(echo "$ENV_JSON" | jq --arg k "$KLING_SECRET_KEY" '. + {"KLING_SECRET_KEY": $k}')
fi

# Docker 环境额外变量
if $IN_DOCKER; then
    ENV_JSON=$(echo "$ENV_JSON" | jq '. + {"OPENCLAW_DOCKER_APT_PACKAGES": "ffmpeg"}')
fi

# 更新 env 字段
tmp=$(mktemp)
jq --arg name "$SKILL_NAME" \
   --argjson env "$ENV_JSON" \
   '.mcpServers[$name].env = (.mcpServers[$name].env // {} | . * $env)' \
   "$OPENCLAW_CONFIG" > "$tmp" && mv "$tmp" "$OPENCLAW_CONFIG"

KLING_STATUS="${RED}未配置${NC}"
[[ -n "$KLING_ACCESS_KEY" && -n "$KLING_SECRET_KEY" ]] && KLING_STATUS="${GREEN}已配置${NC}"

success "配置已保存"

# ----------------------------------------------------------
# 步骤 9: 启动验证
# ----------------------------------------------------------
step 9 "验证安装"

info "正在进行快速启动检查..."

# 测试 Python 模块是否可以导入
VERIFY_OK=true
if (cd "$SKILL_DIR" && python3 -c "import mcp_server" 2>/dev/null); then
    success "MCP 服务器模块导入成功"
else
    if [[ -f "$SKILL_DIR/mcp_server/server.py" ]]; then
        success "MCP 服务器入口文件存在"
    else
        warn "MCP 服务器模块导入失败，请检查安装是否完整"
        VERIFY_OK=false
    fi
fi

# 快速启动测试（超时 5 秒）
if $VERIFY_OK; then
    info "正在尝试启动 MCP 服务器（5 秒超时测试）..."
    if timeout 5 bash -c "cd '$SKILL_DIR' && python3 -c 'from mcp_server.server import mcp; print(\"OK\")'" 2>/dev/null; then
        success "MCP 服务器启动验证通过"
    else
        EXIT_CODE=$?
        if [[ $EXIT_CODE -eq 124 ]]; then
            success "MCP 服务器可以正常启动"
        else
            warn "启动测试未通过（退出码: $EXIT_CODE），服务器可能需要额外配置"
        fi
    fi
fi

# ----------------------------------------------------------
# 步骤 10: 安装完成
# ----------------------------------------------------------
step 10 "安装完成"

echo ""
echo -e "${BOLD}${GREEN}╔══════════════════════════════════════════════════════╗${NC}"
echo -e "${BOLD}${GREEN}║         安装成功！(v2.0)                            ║${NC}"
echo -e "${BOLD}${GREEN}╚══════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "  ${BOLD}安装路径:${NC}       $SKILL_DIR"
echo -e "  ${BOLD}配置文件:${NC}       $OPENCLAW_CONFIG"
echo -e "  ${BOLD}Kling AI API:${NC}   $KLING_STATUS"
echo -e "  ${BOLD}数据采集:${NC}       ${GREEN}浏览器模式（无需 API Key）${NC}"
echo ""
echo -e "${BOLD}${CYAN}快速开始:${NC}"
echo -e "  在 OpenClaw 中输入 ${GREEN}'帮我制作抖音短视频'${NC} 即可开始"
echo ""
echo -e "${BOLD}更多信息:${NC}"
echo -e "  查看 README: ${CYAN}$SKILL_DIR/README.md${NC}"
echo -e "  卸载命令:     ${CYAN}bash $SCRIPT_SOURCE_DIR/install.sh --uninstall${NC}"
echo ""
