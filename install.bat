@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

REM 统一分布式推理系统 - 安装脚本 (Windows)
REM 使用方法: 双击运行 install.bat

REM 颜色定义
for /f %%i in ('echo prompt $E^| cmd') do set "ESC=%%i"
set "RED=!ESC![91m"
set "GREEN=!ESC![92m"
set "YELLOW=!ESC![93m"
set "BLUE=!ESC![94m"
set "NC=!ESC![0m"

REM 打印横幅
echo.
echo ============================================================
echo    统一分布式推理系统 - 安装程序
echo ============================================================
echo.

REM 检查 Python
echo [1/5] 检查 Python 环境...

where python >nul 2>&1
if %errorlevel% neq 0 (
    echo [错误] 未找到 Python
    echo 请先安装 Python 3.8+: https://www.python.org/downloads/
    echo 安装时请勾选 "Add Python to PATH"
    pause
    exit /b 1
)

for /f "tokens=2" %%i in ('python --version 2^>^&1') do set PYTHON_VERSION=%%i
echo [成功] Python 版本: %PYTHON_VERSION%

REM 创建虚拟环境
echo [2/5] 创建虚拟环境...

set /p CREATE_VENV="是否创建虚拟环境? (推荐) [Y/n]: "

if /i "%CREATE_VENV%"=="n" (
    echo [跳过] 不创建虚拟环境
) else (
    if not exist "venv" (
        python -m venv venv
        echo [成功] 虚拟环境已创建
    ) else (
        echo [成功] 虚拟环境已存在
    )
    
    REM 激活虚拟环境
    call venv\Scripts\activate.bat
    echo [成功] 虚拟环境已激活
)

REM 升级 pip
echo [3/5] 升级 pip...
python -m pip install --upgrade pip -q
echo [成功] pip 已升级

REM 安装依赖
echo [4/5] 安装依赖...

echo 选择安装模式:
echo   1. CPU 版本 (适合无 GPU)
echo   2. GPU 版本 (适合 NVIDIA GPU)
echo   3. 完整版本 (包含所有依赖)
set /p INSTALL_MODE="请选择 [1/2/3]: "

set PIP_INDEX=https://pypi.tuna.tsinghua.edu.cn/simple

if "%INSTALL_MODE%"=="1" (
    echo 安装 CPU 版本...
    python -m pip install torch --index-url https://download.pytorch.org/whl/cpu -q
    python -m pip install transformers psutil -q -i %PIP_INDEX%
) else if "%INSTALL_MODE%"=="2" (
    echo 安装 GPU 版本...
    python -m pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121 -q
    python -m pip install transformers psutil -q -i %PIP_INDEX%
) else (
    echo 安装完整版本...
    python -m pip install torch torchvision torchaudio transformers psutil accelerate -q -i %PIP_INDEX%
)

echo [成功] 依赖安装完成

REM 验证安装
echo [5/5] 验证安装...

python -c "import torch; print(f'PyTorch: {torch.__version__}')" && echo [成功] PyTorch
python -c "import transformers; print(f'Transformers: {transformers.__version__}')" && echo [成功] Transformers
python -c "import psutil; print(f'psutil: {psutil.__version__}')" && echo [成功] psutil

REM 检查 GPU
python -c "import torch; assert torch.cuda.is_available()" >nul 2>&1
if %errorlevel% equ 0 (
    for /f "delims=" %%i in ('python -c "import torch; print(torch.cuda.get_device_name(0))"') do set GPU_NAME=%%i
    echo [成功] GPU 可用: !GPU_NAME!
) else (
    echo [警告] GPU 不可用，将使用 CPU 模式
)

REM 完成
echo.
echo ============================================================
echo    安装完成!
echo ============================================================
echo.
echo 启动服务:
echo   start.bat
echo.
echo 或手动启动:
echo   python download\node_unified_complete.py
echo.

pause
