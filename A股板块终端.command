#!/bin/zsh

# 获取脚本所在目录
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}════════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}          A股行业板块扫描与投资决策终端${NC}"
echo -e "${GREEN}════════════════════════════════════════════════════════════${NC}"
echo ""

# 检查端口是否已被占用
if lsof -nP -iTCP:8765 -sTCP:LISTEN >/dev/null 2>&1; then
    echo -e "${YELLOW}✓ 服务器已在运行中${NC}"
    echo -e "${GREEN}正在打开浏览器...${NC}"
    open "http://127.0.0.1:8765/"
    exit 0
fi

# 检查 Python
if ! command -v python3 &>/dev/null; then
    echo -e "${RED}✗ 未找到 Python3，请先安装 Python 3.10+${NC}"
    read -p "按回车键退出..."
    exit 1
fi

# 检查配置文件
if [ ! -f "config.local.json" ]; then
    echo -e "${YELLOW}⚠ 未找到 config.local.json${NC}"
    echo -e "${YELLOW}  请先复制 config.local.example.json 并配置${NC}"
    read -p "按回车键退出..."
    exit 1
fi

echo -e "${GREEN}正在启动服务器...${NC}"
echo -e "${YELLOW}访问地址: http://127.0.0.1:8765/${NC}"
echo ""
echo -e "${GREEN}可用页面:${NC}"
echo -e "  • 板块扫描: http://127.0.0.1:8765/"
echo -e "  • 决策看板: http://127.0.0.1:8765/decision"
echo -e "  • 缠论分析: http://127.0.0.1:8765/chanlun"
echo -e "  • 大盘复盘: http://127.0.0.1:8765/review"
echo ""
echo -e "${YELLOW}按 Ctrl+C 停止服务器${NC}"
echo -e "${GREEN}════════════════════════════════════════════════════════════${NC}"
echo ""

# 延迟打开浏览器
(sleep 2; open "http://127.0.0.1:8765/") &

# 启动服务器
python3 server.py --host 127.0.0.1 --port 8765
