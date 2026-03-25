#!/bin/bash
#
# 统一分布式推理系统 - 安装脚本
#
# 使用方法:
#   chmod +x install.sh && ./install.sh
#

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# 打印横幅
echo ""
echo -e "${GREEN}============================================================${NC}"
echo -e "${GREEN}   统一分布式推理系统 - 安装程序${NC}"
echo -e "${GREEN}============================================================${NC}"
echo ""

# 检查 Python
echo -e "${BLUE}[1/5]${NC} 检查 Python 环境..."

if command -v python3 &> /dev/null; then
    PYTHON_CMD=python3
elif command -v python &> /dev/null; then
    PYTHON_CMD=python
else
    echo -e "${RED}错误: 未找到 Python${NC}"
    echo "请先安装 Python 3.8+: https://www.python.org/downloads/"
    exit 1
fi

PYTHON_VERSION=$($PYTHON_CMD --version 2>&1 | awk '{print $2}')
echo -e "${GREEN}✓${NC} Python 版本: $PYTHON_VERSION"

# 创建虚拟环境（可选）
echo -e "${BLUE}[2/5]${NC} 创建虚拟环境..."

read -p "是否创建虚拟环境? (推荐) [Y/n]: " CREATE_VENV

if [[ "$CREATE_VENV" =~ ^[Yy]$ ]] || [[ -z "$CREATE_VENV" ]]; then
    if [ ! -d "venv" ]; then
        $PYTHON_CMD -m venv venv
        echo -e "${GREEN}✓${NC} 虚拟环境已创建"
    else
        echo -e "${GREEN}✓${NC} 虚拟环境已存在"
    fi
    
    # 激活虚拟环境
    source venv/bin/activate
    PYTHON_CMD=python
    echo -e "${GREEN}✓${NC} 虚拟环境已激活"
else
    echo -e "${YELLOW}跳过虚拟环境创建${NC}"
fi

# 升级 pip
echo -e "${BLUE}[3/5]${NC} 升级 pip..."
$PYTHON_CMD -m pip install --upgrade pip -q
echo -e "${GREEN}✓${NC} pip 已升级"

# 安装依赖
echo -e "${BLUE}[4/5]${NC} 安装依赖..."

# 使用国内镜像
PIP_INDEX="https://pypi.tuna.tsinghua.edu.cn/simple"

echo "选择安装模式:"
echo "  1. CPU 版本 (适合无 GPU)"
echo "  2. GPU 版本 (适合 NVIDIA GPU)"
echo "  3. 完整版本 (包含所有依赖)"
read -p "请选择 [1/2/3]: " INSTALL_MODE

case $INSTALL_MODE in
    1)
        echo "安装 CPU 版本..."
        $PYTHON_CMD -m pip install torch --index-url https://download.pytorch.org/whl/cpu -q
        $PYTHON_CMD -m pip install transformers psutil -q -i $PIP_INDEX
        ;;
    2)
        echo "安装 GPU 版本..."
        $PYTHON_CMD -m pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121 -q
        $PYTHON_CMD -m pip install transformers psutil -q -i $PIP_INDEX
        ;;
    *)
        echo "安装完整版本..."
        $PYTHON_CMD -m pip install torch torchvision torchaudio transformers psutil accelerate -q -i $PIP_INDEX
        ;;
esac

echo -e "${GREEN}✓${NC} 依赖安装完成"

# 验证安装
echo -e "${BLUE}[5/5]${NC} 验证安装..."

$PYTHON_CMD -c "import torch; print(f'PyTorch: {torch.__version__}')" && echo -e "${GREEN}✓${NC} PyTorch"
$PYTHON_CMD -c "import transformers; print(f'Transformers: {transformers.__version__}')" && echo -e "${GREEN}✓${NC} Transformers"
$PYTHON_CMD -c "import psutil; print(f'psutil: {psutil.__version__}')" && echo -e "${GREEN}✓${NC} psutil"

# 检查 GPU
if $PYTHON_CMD -c "import torch; assert torch.cuda.is_available()" 2>/dev/null; then
    GPU_NAME=$($PYTHON_CMD -c "import torch; print(torch.cuda.get_device_name(0))")
    echo -e "${GREEN}✓${NC} GPU 可用: $GPU_NAME"
else
    echo -e "${YELLOW}!${NC} GPU 不可用，将使用 CPU 模式"
fi

# 完成
echo ""
echo -e "${GREEN}============================================================${NC}"
echo -e "${GREEN}   安装完成!${NC}"
echo -e "${GREEN}============================================================${NC}"
echo ""
echo "启动服务:"
echo "  ./start.sh"
echo ""
echo "或手动启动:"
echo "  python core/node_unified_complete.py"
echo ""
