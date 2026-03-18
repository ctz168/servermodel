#!/bin/bash
#
# 统一分布式推理系统 - 一键启动脚本
#
# 使用方法:
#   chmod +x start.sh && ./start.sh
#

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 打印带颜色的消息
print_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 打印横幅
print_banner() {
    echo ""
    echo -e "${GREEN}============================================================${NC}"
    echo -e "${GREEN}   统一分布式推理系统 - 一键启动${NC}"
    echo -e "${GREEN}============================================================${NC}"
    echo ""
}

# 检查 Python
check_python() {
    print_info "检查 Python 环境..."
    
    if command -v python3 &> /dev/null; then
        PYTHON_CMD=python3
    elif command -v python &> /dev/null; then
        PYTHON_CMD=python
    else
        print_error "未找到 Python，请先安装 Python 3.8+"
        print_info "安装方法: https://www.python.org/downloads/"
        exit 1
    fi
    
    PYTHON_VERSION=$($PYTHON_CMD --version 2>&1 | awk '{print $2}')
    print_success "Python 版本: $PYTHON_VERSION"
}

# 检查 pip
check_pip() {
    print_info "检查 pip..."
    
    if $PYTHON_CMD -m pip --version &> /dev/null; then
        print_success "pip 已安装"
    else
        print_warning "pip 未安装，正在安装..."
        $PYTHON_CMD -m ensurepip --upgrade
    fi
}

# 安装依赖
install_dependencies() {
    print_info "检查依赖..."
    
    # 检查是否需要安装依赖
    NEED_INSTALL=0
    
    # 检查 torch
    if ! $PYTHON_CMD -c "import torch" 2>/dev/null; then
        print_warning "torch 未安装"
        NEED_INSTALL=1
    fi
    
    # 检查 transformers
    if ! $PYTHON_CMD -c "import transformers" 2>/dev/null; then
        print_warning "transformers 未安装"
        NEED_INSTALL=1
    fi
    
    # 检查 psutil
    if ! $PYTHON_CMD -c "import psutil" 2>/dev/null; then
        print_warning "psutil 未安装"
        NEED_INSTALL=1
    fi
    
    if [ $NEED_INSTALL -eq 1 ]; then
        print_info "正在安装依赖..."
        
        # 使用国内镜像加速
        $PYTHON_CMD -m pip install --upgrade pip -q
        $PYTHON_CMD -m pip install torch transformers psutil -q \
            -i https://pypi.tuna.tsinghua.edu.cn/simple
        
        print_success "依赖安装完成"
    else
        print_success "所有依赖已安装"
    fi
}

# 检查 GPU
check_gpu() {
    print_info "检查 GPU..."
    
    if $PYTHON_CMD -c "import torch; assert torch.cuda.is_available()" 2>/dev/null; then
        GPU_NAME=$($PYTHON_CMD -c "import torch; print(torch.cuda.get_device_name(0))" 2>/dev/null)
        GPU_MEMORY=$($PYTHON_CMD -c "import torch; print(torch.cuda.get_device_properties(0).total_memory / 1024**3)" 2>/dev/null)
        print_success "检测到 GPU: $GPU_NAME (${GPU_MEMORY%.*}GB)"
        DEVICE="cuda"
    else
        print_warning "未检测到 GPU，将使用 CPU 模式"
        print_info "提示: CPU 模式速度较慢，建议使用 GPU"
        DEVICE="cpu"
    fi
}

# 选择模型
select_model() {
    print_info "选择模型..."
    
    # 根据设备选择合适的模型
    if [ "$DEVICE" = "cuda" ]; then
        # 有 GPU，根据显存选择模型
        GPU_MEMORY=$($PYTHON_CMD -c "import torch; print(torch.cuda.get_device_properties(0).total_memory / 1024**3)" 2>/dev/null)
        GPU_MEMORY_INT=${GPU_MEMORY%.*}
        
        if [ "$GPU_MEMORY_INT" -ge 20 ]; then
            MODEL="Qwen/Qwen2.5-7B-Instruct"
            print_success "选择模型: $MODEL (大模型，适合 ${GPU_MEMORY_INT}GB 显存)"
        elif [ "$GPU_MEMORY_INT" -ge 10 ]; then
            MODEL="Qwen/Qwen2.5-1.5B-Instruct"
            print_success "选择模型: $MODEL (中等模型，适合 ${GPU_MEMORY_INT}GB 显存)"
        else
            MODEL="Qwen/Qwen2.5-0.5B-Instruct"
            print_success "选择模型: $MODEL (小模型，适合 ${GPU_MEMORY_INT}GB 显存)"
        fi
    else
        # 无 GPU，使用小模型
        MODEL="Qwen/Qwen2.5-0.5B-Instruct"
        print_success "选择模型: $MODEL (小模型，适合 CPU)"
    fi
}

# 设置环境变量
setup_env() {
    print_info "设置环境变量..."
    
    # 使用国内镜像加速模型下载
    export HF_ENDPOINT=https://hf-mirror.com
    
    print_success "环境变量设置完成"
}

# 启动服务
start_service() {
    print_info "启动服务..."
    
    # 获取脚本所在目录
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    
    # 主程序路径
    MAIN_SCRIPT="$SCRIPT_DIR/download/node_unified_complete.py"
    
    # 检查主程序是否存在
    if [ ! -f "$MAIN_SCRIPT" ]; then
        print_error "主程序不存在: $MAIN_SCRIPT"
        exit 1
    fi
    
    # 设置端口
    PORT=${PORT:-5000}
    API_PORT=${API_PORT:-8080}
    
    echo ""
    echo -e "${GREEN}============================================================${NC}"
    echo -e "${GREEN}   服务启动中...${NC}"
    echo -e "${GREEN}============================================================${NC}"
    echo ""
    echo -e "  模型:     ${YELLOW}$MODEL${NC}"
    echo -e "  通信端口: ${YELLOW}$PORT${NC}"
    echo -e "  API 端口: ${YELLOW}$API_PORT${NC}"
    echo -e "  设备:     ${YELLOW}$DEVICE${NC}"
    echo ""
    echo -e "  API 地址: ${BLUE}http://localhost:$API_PORT${NC}"
    echo -e "  健康检查: ${BLUE}http://localhost:$API_PORT/health${NC}"
    echo ""
    echo -e "${GREEN}============================================================${NC}"
    echo -e "  按 ${YELLOW}Ctrl+C${NC} 停止服务"
    echo -e "${GREEN}============================================================${NC}"
    echo ""
    
    # 启动主程序
    $PYTHON_CMD "$MAIN_SCRIPT" \
        --port $PORT \
        --api-port $API_PORT \
        --model "$MODEL" \
        --auto
}

# 主函数
main() {
    print_banner
    check_python
    check_pip
    install_dependencies
    check_gpu
    select_model
    setup_env
    start_service
}

# 运行主函数
main "$@"
