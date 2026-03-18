#!/bin/bash
#
# 停止集群
#

# 颜色定义
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# 获取脚本所在目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
LOGS_DIR="$PROJECT_DIR/logs"

echo ""
echo -e "${YELLOW}停止集群...${NC}"

# 查找并停止所有节点进程
if [ -d "$LOGS_DIR" ]; then
    for pid_file in "$LOGS_DIR"/*.pid; do
        if [ -f "$pid_file" ]; then
            PID=$(cat "$pid_file")
            if kill -0 "$PID" 2>/dev/null; then
                kill "$PID"
                echo -e "${GREEN}✓${NC} 停止进程 $PID"
            fi
            rm "$pid_file"
        fi
    done
fi

# 额外清理：查找并停止所有 node_unified_complete.py 进程
pkill -f "node_unified_complete.py" 2>/dev/null || true

echo ""
echo -e "${GREEN}集群已停止${NC}"
echo ""
