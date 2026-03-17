#!/bin/bash
#
# 分布式大模型推理系统 - 停止脚本
#

set -e

# 配置
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
PID_DIR="$PROJECT_DIR/pids"

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m'

echo -e "${RED}正在停止服务...${NC}"

# 停止所有节点进程
for pid_file in "$PID_DIR"/*.pid; do
    if [ -f "$pid_file" ]; then
        pid=$(cat "$pid_file")
        if [ -n "$pid" ]; then
            echo "停止进程 $pid..."
            kill $pid 2>/dev/null
            rm -f "$pid_file"
        fi
    fi
done

echo -e "${GREEN}服务已停止${NC}"
