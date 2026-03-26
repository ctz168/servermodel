# 4节点集群部署指南

## 资源清单

| 节点 | 系统 | 内存 | 角色 |
|------|------|------|------|
| 云主机1 | Linux Debian | 8GB | Pipeline组A - 阶段0 (领导) |
| 云主机2 | Linux Debian | 8GB | Pipeline组B - 阶段0 (领导) |
| 本地Windows1 | Windows | 16GB | Pipeline组A - 阶段1 |
| 本地Windows2 | Windows | 16GB | Pipeline组B - 阶段1 |

**总内存**: 48GB  
**可运行模型**: Qwen2.5-7B-Instruct

---

## 集群拓扑

```
Pipeline组A (运行 7B 模型):
  云主机1 (8GB) ──→ 本地Windows1 (16GB)
  加载前半层        加载后半层

Pipeline组B (运行 7B 模型):
  云主机2 (8GB) ──→ 本地Windows2 (16GB)
  加载前半层        加载后半层
```

---

## 第一步: 云主机准备 (Linux Debian)

### 1.1 安装依赖

```bash
# 更新系统
sudo apt update && sudo apt upgrade -y

# 安装 Python 3
sudo apt install -y python3 python3-pip python3-venv

# 创建项目目录
mkdir -p ~/servermodel
cd ~/servermodel

# 创建虚拟环境
python3 -m venv venv
source venv/bin/activate

# 安装依赖
pip install torch transformers psutil pyngrok -i https://pypi.tuna.tsinghua.edu.cn/simple
```

### 1.2 上传代码

方式一: 使用 git
```bash
git clone <your-repo-url> .
```

方式二: 使用 scp (从本地上传)
```bash
# 在本地 Windows 上执行
scp -r c:/Users/Administrator/Desktop/servermodel/* user@云主机IP:~/servermodel/
```

### 1.3 配置环境变量

```bash
# 使用国内镜像加速模型下载
echo 'export HF_ENDPOINT=https://hf-mirror.com' >> ~/.bashrc
source ~/.bashrc
```

### 1.4 开放防火墙端口

```bash
# 开放端口
sudo ufw allow 5000/tcp  # 节点通信
sudo ufw allow 8080/tcp  # API 服务
sudo ufw reload
```

---

## 第二步: 本地 Windows 准备

### 2.1 安装依赖

```powershell
# 进入项目目录
cd c:\Users\Administrator\Desktop\servermodel

# 创建虚拟环境
python -m venv venv
.\venv\Scripts\activate

# 安装依赖
pip install torch transformers psutil pyngrok -i https://pypi.tuna.tsinghua.edu.cn/simple
```

### 2.2 配置环境变量

```powershell
# 设置模型镜像
$env:HF_ENDPOINT = "https://hf-mirror.com"
```

---

## 第三步: 获取 Ngrok Token (公网连接)

1. 访问 https://dashboard.ngrok.com/get-started/your-authtoken
2. 注册/登录后获取 authtoken
3. 记录 token，后面会用到

---

## 第四步: 启动集群

### 4.1 启动云主机1 (Pipeline组A - 领导节点)

```bash
cd ~/servermodel
source venv/bin/activate

python core/node_unified_complete.py \
    --mode pipeline_parallel \
    --stages 2 \
    --port 5000 \
    --api-port 8080 \
    --model "Qwen/Qwen2.5-7B-Instruct" \
    --ngrok \
    --ngrok-auth-token YOUR_NGROK_TOKEN
```

**记录输出的公网地址**，例如:
```
[Ngrok] 节点通信地址: tcp://0.tcp.ngrok.io:12345
```

### 4.2 启动云主机2 (Pipeline组B - 领导节点)

```bash
cd ~/servermodel
source venv/bin/activate

python core/node_unified_complete.py \
    --mode pipeline_parallel \
    --stages 2 \
    --port 5000 \
    --api-port 8080 \
    --model "Qwen/Qwen2.5-7B-Instruct" \
    --ngrok \
    --ngrok-auth-token YOUR_NGROK_TOKEN
```

**记录输出的公网地址**，例如:
```
[Ngrok] 节点通信地址: tcp://0.tcp.ngrok.io:67890
```

### 4.3 启动本地Windows1 (Pipeline组A - 阶段1)

```powershell
cd c:\Users\Administrator\Desktop\servermodel
.\venv\Scripts\activate

python core/node_unified_complete.py `
    --mode pipeline_parallel `
    --stages 2 `
    --seeds "0.tcp.ngrok.io:12345" `
    --model "Qwen/Qwen2.5-7B-Instruct"
```

### 4.4 启动本地Windows2 (Pipeline组B - 阶段1)

```powershell
cd c:\Users\Administrator\Desktop\servermodel
.\venv\Scripts\activate

python core/node_unified_complete.py `
    --mode pipeline_parallel `
    --stages 2 `
    --seeds "0.tcp.ngrok.io:67890" `
    --model "Qwen/Qwen2.5-7B-Instruct"
```

---

## 第五步: 验证集群

### 5.1 检查节点状态

```bash
# 云主机1
curl http://localhost:8080/status

# 云主机2
curl http://localhost:8080/status
```

### 5.2 测试推理

```bash
curl -X POST http://云主机1公网IP:8080/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "Qwen/Qwen2.5-7B-Instruct",
    "messages": [{"role": "user", "content": "你好"}]
  }'
```

---

## 备选方案: 4节点单 Pipeline (更大模型)

如果需要运行 **14B 模型**:

```
云主机1 → 云主机2 → 本地Win1 → 本地Win2
(阶段0)   (阶段1)    (阶段2)     (阶段3)
```

### 启动命令

**云主机1 (阶段0)**:
```bash
python core/node_unified_complete.py \
    --mode pipeline_parallel \
    --stages 4 \
    --stage-id 0 \
    --model "Qwen/Qwen2.5-14B-Instruct" \
    --ngrok --ngrok-auth-token YOUR_TOKEN
```

**云主机2 (阶段1)**:
```bash
python core/node_unified_complete.py \
    --mode pipeline_parallel \
    --stages 4 \
    --stage-id 1 \
    --seeds "云主机1地址:5000" \
    --model "Qwen/Qwen2.5-14B-Instruct" \
    --ngrok --ngrok-auth-token YOUR_TOKEN
```

**本地Windows1 (阶段2)**:
```powershell
python core/node_unified_complete.py `
    --mode pipeline_parallel `
    --stages 4 `
    --stage-id 2 `
    --seeds "云主机2地址:5000" `
    --model "Qwen/Qwen2.5-14B-Instruct"
```

**本地Windows2 (阶段3)**:
```powershell
python core/node_unified_complete.py `
    --mode pipeline_parallel `
    --stages 4 `
    --stage-id 3 `
    --seeds "本地Windows1地址:5000" `
    --model "Qwen/Qwen2.5-14B-Instruct"
```

> ⚠️ 注意: 4节点 Pipeline 延迟较高，不推荐在公网环境使用

---

## 性能对比

| 方案 | 模型大小 | 节点跳数 | 吞吐量 | 推荐度 |
|------|----------|----------|--------|--------|
| 数据并行 | 3B | 0 | 高 | ⭐⭐⭐ |
| 混合并行 (2x2) | 7B | 2 | 中 | ⭐⭐⭐⭐⭐ |
| 单 Pipeline (4) | 14B | 4 | 低 | ⭐⭐ |

---

## 常见问题

### Q: 内存不足怎么办?
```bash
# 使用 fp16 精度
python core/node_unified_complete.py --precision fp16 ...

# 或使用更小的模型
python core/node_unified_complete.py --model "Qwen/Qwen2.5-3B-Instruct" ...
```

### Q: 网络连接超时?
```bash
# 检查防火墙
sudo ufw status

# 检查端口监听
netstat -tlnp | grep 5000
```

### Q: 模型下载慢?
```bash
# 使用镜像
export HF_ENDPOINT=https://hf-mirror.com
```

---

## 快速启动脚本

### Linux (云主机)

创建 `start_leader.sh`:
```bash
#!/bin/bash
cd ~/servermodel
source venv/bin/activate
export HF_ENDPOINT=https://hf-mirror.com

python core/node_unified_complete.py \
    --mode pipeline_parallel \
    --stages 2 \
    --port 5000 \
    --api-port 8080 \
    --model "Qwen/Qwen2.5-7B-Instruct" \
    --ngrok \
    --ngrok-auth-token YOUR_TOKEN
```

### Windows (本地)

创建 `start_worker.bat`:
```batch
@echo off
cd c:\Users\Administrator\Desktop\servermodel
call venv\Scripts\activate
set HF_ENDPOINT=https://hf-mirror.com

python core/node_unified_complete.py ^
    --mode pipeline_parallel ^
    --stages 2 ^
    --seeds "YOUR_NGROK_ADDRESS:5000" ^
    --model "Qwen/Qwen2.5-7B-Instruct"
```
