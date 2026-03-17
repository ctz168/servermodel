#!/bin/bash
#
# 分布式大模型推理系统 - 统一启动脚本
#
# 使用方法:
#   ./start_unified_production.sh [节点数量]
#
# 示例:
#   ./start_unified_production.sh 1    # 启动单个节点
#   ./start_unified_production.sh 3    # 启动3个节点集群
#

set -e

# 配置
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
NODE_SCRIPT="$PROJECT_DIR/download/node_unified_production.py"
LOG_DIR="$PROJECT_DIR/logs"
PID_DIR="$PROJECT_DIR/pids"

# 默认配置
DEFAULT_MODEL="Qwen/Qwen2.5-0.5B-Instruct"
DEFAULT_PORT=5000
DEFAULT_API_PORT=8080
DEFAULT_WORKERS=2

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 创建必要目录
mkdir -p "$LOG_DIR" "$PID_DIR"

# 打印帮助
print_help() {
    echo "分布式大模型推理系统 - 统一启动脚本"
    echo ""
    echo "使用方法:"
    echo "  $0 [选项] [节点数量]"
    echo ""
    echo "选项:"
    echo "  -m, --model MODEL       模型名称 (默认: $DEFAULT_MODEL)"
    echo "  -p, --port PORT         第一个节点端口 (默认: $DEFAULT_PORT)"
    echo "  -a, --api-port PORT     第一个API端口 (默认: $DEFAULT_API_PORT)"
    echo "  -w, --workers NUM       每节点工作线程数 (默认: $DEFAULT_WORKERS)"
    echo "  -h, --help              显示帮助信息"
    echo ""
    echo "示例:"
    echo "  $0                      # 启动单个节点"
    echo "  $0 3                    # 启动3个节点集群"
    echo "  $0 -m Qwen/Qwen2.5-1.5B-Instruct 2  # 使用1.5B模型启动2个节点"
}

# 解析参数
NUM_NODES=1
MODEL="$DEFAULT_MODEL"
BASE_PORT="$DEFAULT_PORT"
BASE_API_PORT="$DEFAULT_API_PORT"
WORKERS="$DEFAULT_WORKERS"

while [[ $# -gt 0 ]]; do
    case $1 in
        -m|--model)
            MODEL="$2"
            shift 2
            ;;
        -p|--port)
            BASE_PORT="$2"
            shift 2
            ;;
        -a|--api-port)
            BASE_API_PORT="$2"
            shift 2
            ;;
        -w|--workers)
            WORKERS="$2"
            shift 2
            ;;
        -h|--help)
            print_help
            exit 0
            ;;
        *)
            if [[ $1 =~ ^[0-9]+$ ]]; then
                NUM_NODES=$1
            else
                echo -e "${RED}未知参数: $1${NC}"
                print_help
                exit 1
            fi
            shift
            ;;
    esac
done

# 检查Python
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}错误: 未找到Python3${NC}"
    exit 1
fi

# 检查节点脚本
if [ ! -f "$NODE_SCRIPT" ]; then
    echo -e "${RED}错误: 未找到节点脚本: $NODE_SCRIPT${NC}"
    exit 1
fi

# 打印启动信息
echo ""
echo -e "${BLUE}============================================${NC}"
echo -e "${BLUE}  分布式大模型推理系统 - 统一生产级版本${NC}"
echo -e "${BLUE}============================================${NC}"
echo -e "  模型: ${GREEN}$MODEL${NC}"
echo -e "  节点数: ${GREEN}$NUM_NODES${NC}"
echo -e "  基础端口: ${GREEN}$BASE_PORT${NC}"
echo -e "  基础API端口: ${GREEN}$BASE_API_PORT${NC}"
echo -e "  工作线程: ${GREEN}$WORKERS${NC}"
echo -e "${BLUE}============================================${NC}"
echo ""

# 启动节点
start_node() {
    local index=$1
    local port=$((BASE_PORT + index))
    local api_port=$((BASE_API_PORT + index))
    local log_file="$LOG_DIR/node_${index}.log"
    local pid_file="$PID_DIR/node_${index}.pid"
    
    # 构建种子节点列表
    local seeds=""
    if [ $index -gt 0 ]; then
        seeds="--seeds localhost:$BASE_PORT"
    fi
    
    echo -e "${YELLOW}启动节点 $index...${NC}"
    echo -e "  端口: $port"
    echo -e "  API端口: $api_port"
    echo -e "  日志: $log_file"
    
    # 启动节点
    nohup python3 "$NODE_SCRIPT" \
        --port "$port" \
        --api-port "$api_port" \
        --model "$MODEL" \
        --workers "$WORKERS" \
        --name "Node-$index" \
        $seeds \
        > "$log_file" 2>&1 &
    
    local pid=$!
    echo $pid > "$pid_file"
    
    echo -e "  PID: ${GREEN}$pid${NC}"
    
    # 等待节点启动
    sleep 2
}

# 启动所有节点
for ((i=0; i<NUM_NODES; i++)); do
    start_node $i
done

echo ""
echo -e "${GREEN}============================================${NC}"
echo -e "${GREEN}  启动完成!${NC}"
echo -e "${GREEN}============================================${NC}"
echo ""
echo "API端点:"
for ((i=0; i<NUM_NODES; i++)); do
    api_port=$((BASE_API_PORT + i))
    echo -e "  节点 $i: ${BLUE}http://localhost:$api_port${NC}"
done
echo ""
echo "测试命令:"
echo "  curl http://localhost:$BASE_API_PORT/health"
echo "  curl http://localhost:$BASE_API_PORT/status"
echo "  curl -X POST http://localhost:$BASE_API_PORT/inference -H 'Content-Type: application/json' -d '{\"prompt\": \"你好\"}'"
echo ""
echo "停止服务:"
echo "  ./stop_unified_production.sh"
echo ""
