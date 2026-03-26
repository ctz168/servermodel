#!/bin/bash
#
# 一键安装脚本 - Linux
# 使用方法: curl -fsSL https://raw.githubusercontent.com/YOUR_REPO/main/scripts/install_remote.sh | bash
#

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# 项目配置
PROJECT_DIR="$HOME/servermodel"
GIT_REPO="${GIT_REPO:-https://github.com/YOUR_USERNAME/servermodel.git}"

print_banner() {
    echo ""
    echo -e "${GREEN}============================================================${NC}"
    echo -e "${GREEN}   统一分布式推理系统 - 一键安装${NC}"
    echo -e "${GREEN}============================================================${NC}"
    echo ""
}

print_success() { echo -e "${GREEN}[OK]${NC} $1"; }
print_error() { echo -e "${RED}[ERROR]${NC} $1"; }
print_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
print_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }

# 检查系统
check_system() {
    print_info "检查系统环境..."
    
    if [[ "$OSTYPE" != "linux-gnu"* ]]; then
        print_error "此脚本仅支持 Linux 系统"
        exit 1
    fi
    
    print_success "系统: $(uname -a)"
}

# 安装依赖
install_deps() {
    print_info "安装系统依赖..."
    
    if command -v apt-get &> /dev/null; then
        sudo apt-get update -qq
        sudo apt-get install -y -qq python3 python3-pip python3-venv git curl
    elif command -v yum &> /dev/null; then
        sudo yum install -y -q python3 python3-pip git curl
    elif command -v dnf &> /dev/null; then
        sudo dnf install -y -q python3 python3-pip git curl
    else
        print_error "不支持的包管理器"
        exit 1
    fi
    
    print_success "系统依赖安装完成"
}

# 克隆项目
clone_project() {
    print_info "克隆项目..."
    
    if [ -d "$PROJECT_DIR" ]; then
        print_warn "项目目录已存在，更新代码..."
        cd "$PROJECT_DIR"
        git pull -q
    else
        git clone -q "$GIT_REPO" "$PROJECT_DIR"
        cd "$PROJECT_DIR"
    fi
    
    print_success "项目准备完成"
}

# 创建虚拟环境
create_venv() {
    print_info "创建虚拟环境..."
    
    cd "$PROJECT_DIR"
    
    if [ ! -d "venv" ]; then
        python3 -m venv venv
    fi
    
    source venv/bin/activate
    print_success "虚拟环境已激活"
}

# 安装 Python 依赖
install_python_deps() {
    print_info "安装 Python 依赖..."
    
    pip install --upgrade pip -q
    pip install torch transformers psutil pyngrok -q \
        -i https://pypi.tuna.tsinghua.edu.cn/simple
    
    print_success "Python 依赖安装完成"
}

# 配置环境
setup_env() {
    print_info "配置环境..."
    
    # 添加环境变量到 bashrc
    if ! grep -q "HF_ENDPOINT" ~/.bashrc; then
        echo 'export HF_ENDPOINT=https://hf-mirror.com' >> ~/.bashrc
    fi
    
    export HF_ENDPOINT=https://hf-mirror.com
    
    print_success "环境配置完成"
}

# 创建启动脚本
create_start_script() {
    print_info "创建启动脚本..."
    
    cat > "$PROJECT_DIR/start.sh" << 'START_SCRIPT'
#!/bin/bash
cd "$HOME/servermodel"
source venv/bin/activate
export HF_ENDPOINT=https://hf-mirror.com

# 交互式选择
echo ""
echo "=========================================="
echo "  选择启动模式"
echo "=========================================="
echo ""
echo "  1. 单节点模式 (推荐新手)"
echo "  2. Pipeline 领导节点 (需 Ngrok)"
echo "  3. Pipeline 工作节点"
echo ""
read -p "请选择 [1/2/3]: " mode_choice

case $mode_choice in
    1)
        echo ""
        echo "选择模型:"
        echo "  1. Qwen2.5-0.5B (小模型)"
        echo "  2. Qwen2.5-1.5B (中等)"
        echo "  3. Qwen2.5-3B   (较大)"
        read -p "请选择 [1/2/3，默认1]: " model_choice
        model_choice=${model_choice:-1}
        
        models=("Qwen/Qwen2.5-0.5B-Instruct" "Qwen/Qwen2.5-1.5B-Instruct" "Qwen/Qwen2.5-3B-Instruct")
        model=${models[$((model_choice-1))]}
        
        python core/node_unified_complete.py --model "$model" --auto
        ;;
    2)
        read -p "请输入 Ngrok Token: " ngrok_token
        if [ -z "$ngrok_token" ]; then
            echo "错误: Ngrok Token 不能为空"
            exit 1
        fi
        
        echo ""
        echo "选择模型:"
        echo "  1. Qwen2.5-3B  (适合 2 节点)"
        echo "  2. Qwen2.5-7B  (推荐)"
        echo "  3. Qwen2.5-14B (需要 4 节点)"
        read -p "请选择 [1/2/3，默认2]: " model_choice
        model_choice=${model_choice:-2}
        
        models=("Qwen/Qwen2.5-3B-Instruct" "Qwen/Qwen2.5-7B-Instruct" "Qwen/Qwen2.5-14B-Instruct")
        model=${models[$((model_choice-1))]}
        
        stages=("2" "2" "4")
        stage=${stages[$((model_choice-1))]}
        
        python core/node_unified_complete.py \
            --mode pipeline_parallel \
            --stages $stage \
            --port 5000 \
            --api-port 8080 \
            --model "$model" \
            --ngrok \
            --ngrok-auth-token "$ngrok_token"
        ;;
    3)
        read -p "请输入领导节点地址 (如 0.tcp.ngrok.io:12345): " seed_addr
        if [ -z "$seed_addr" ]; then
            echo "错误: 地址不能为空"
            exit 1
        fi
        
        echo ""
        echo "选择模型 (需与领导节点一致):"
        echo "  1. Qwen2.5-3B"
        echo "  2. Qwen2.5-7B"
        echo "  3. Qwen2.5-14B"
        read -p "请选择 [1/2/3，默认2]: " model_choice
        model_choice=${model_choice:-2}
        
        models=("Qwen/Qwen2.5-3B-Instruct" "Qwen/Qwen2.5-7B-Instruct" "Qwen/Qwen2.5-14B-Instruct")
        model=${models[$((model_choice-1))]}
        
        stages=("2" "2" "4")
        stage=${stages[$((model_choice-1))]}
        
        python core/node_unified_complete.py \
            --mode pipeline_parallel \
            --stages $stage \
            --seeds "$seed_addr" \
            --model "$model"
        ;;
    *)
        echo "无效选择"
        exit 1
        ;;
esac
START_SCRIPT

    chmod +x "$PROJECT_DIR/start.sh"
    print_success "启动脚本创建完成"
}

# 完成
print_complete() {
    echo ""
    echo -e "${GREEN}============================================================${NC}"
    echo -e "${GREEN}   安装完成!${NC}"
    echo -e "${GREEN}============================================================${NC}"
    echo ""
    echo "启动服务:"
    echo "  cd ~/servermodel && ./start.sh"
    echo ""
    echo "或手动启动:"
    echo "  cd ~/servermodel && source venv/bin/activate"
    echo "  python core/node_unified_complete.py --help"
    echo ""
}

# 主函数
main() {
    print_banner
    check_system
    install_deps
    clone_project
    create_venv
    install_python_deps
    setup_env
    create_start_script
    print_complete
}

main "$@"
