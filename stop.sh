#!/bin/bash
#
# 停止服务
#

# 颜色定义
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo ""
echo -e "${YELLOW}停止服务...${NC}"

# 查找并停止所有 node_unified_complete.py 进程
pkill -f "node_unified_complete.py" 2>/dev/null && {
    echo -e "${GREEN}✓${NC} 服务已停止"
} || {
    echo -e "${YELLOW}没有运行中的服务${NC}"
}

echo ""
