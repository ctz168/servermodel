#!/bin/bash
#
# 启动多节点集群
#
# 使用方法:
#   ./scripts/start_cluster.sh [节点数量]
#
# 示例:
#   ./scripts/start_cluster.sh 3   # 启动 3 个节点
#

set -e

# 颜色定义
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# 节点数量
NUM_NODES=${1:-3}

# 基础端口
BASE_PORT=5000
BASE_API_PORT=8080

# 获取脚本所在目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
MAIN_SCRIPT="$PROJECT_DIR/core/node_unified_complete.py"

echo ""
echo -e "${GREEN}============================================================${NC}"
echo -e "${GREEN}   启动 $NUM_NODES 节点集群${NC}"
echo -e "${GREEN}============================================================${NC}"
echo ""

# 检查主程序
if [ ! -f "$MAIN_SCRIPT" ]; then
    echo -e "${RED}错误: 主程序不存在${NC}"
    exit 1
fi

# 设置环境变量
export HF_ENDPOINT=https://hf-mirror.com

# 创建日志目录
mkdir -p "$PROJECT_DIR/logs"

# 启动节点
for i in $(seq 1 $NUM_NODES); do
    PORT=$((BASE_PORT + i - 1))
    API_PORT=$((BASE_API_PORT + i - 1))
    
    if [ $i -eq 1 ]; then
        # 第一个节点是领导节点
        echo -e "${GREEN}启动节点 $i (领导节点)${NC}"
        echo -e "  通信端口: $PORT"
        echo -e "  API 端口: $API_PORT"
        
        python "$MAIN_SCRIPT" \
            --port $PORT \
            --api-port $API_PORT \
            --model "Qwen/Qwen2.5-0.5B-Instruct" \
            > "$PROJECT_DIR/logs/node_$i.log" 2>&1 &
    else
        # 后续节点是工作节点
        SEED="localhost:$BASE_PORT"
        
        echo -e "${YELLOW}启动节点 $i (工作节点)${NC}"
        echo -e "  通信端口: $PORT"
        echo -e "  API 端口: $API_PORT"
        echo -e "  种子节点: $SEED"
        
        python "$MAIN_SCRIPT" \
            --port $PORT \
            --api-port $API_PORT \
            --seeds "$SEED" \
            --model "Qwen/Qwen2.5-0.5B-Instruct" \
            > "$PROJECT_DIR/logs/node_$i.log" 2>&1 &
    fi
    
    # 保存进程 ID
    echo $! > "$PROJECT_DIR/logs/node_$i.pid"
    
    echo ""
    
    # 等待一下再启动下一个节点
    sleep 2
done

echo -e "${GREEN}============================================================${NC}"
echo -e "${GREEN}   集群启动完成!${NC}"
echo -e "${GREEN}============================================================${NC}"
echo ""
echo "节点状态:"
echo "  领导节点: http://localhost:$BASE_API_PORT"
echo ""

for i in $(seq 2 $NUM_NODES); do
    API_PORT=$((BASE_API_PORT + i - 1))
    echo "  工作节点 $i: http://localhost:$API_PORT"
done

echo ""
echo "查看日志:"
echo "  tail -f $PROJECT_DIR/logs/node_1.log"
echo ""
echo "停止集群:"
echo "  ./scripts/stop_cluster.sh"
echo ""
