# 统一分布式推理系统

> 🚀 **一键部署，开箱即用** - 跨平台分布式大模型推理系统，支持 Pipeline 并行，可运行比单机更大的模型

## 特性

- ✅ **单文件部署** - 核心代码仅一个 Python 文件，无需复杂配置
- ✅ **跨平台支持** - Windows / Linux / macOS 全平台兼容
- ✅ **Pipeline 并行** - 多节点协作，运行比单机更大的模型
- ✅ **OpenAI 兼容** - 完全兼容 OpenAI API 格式，无缝迁移
- ✅ **公网穿透** - 内置 Ngrok 支持，轻松组建公网集群
- ✅ **自动检测** - 自动识别硬件配置，选择最优模式

---

## 📋 目录

- [快速开始](#-快速开始)
- [一键部署](#-一键部署)
- [集群部署](#-集群部署)
- [API 接口](#-api-接口)
- [配置说明](#-配置说明)
- [项目结构](#-项目结构)
- [常见问题](#-常见问题)

---

## 🚀 快速开始

### 本地快速启动

**Windows:**
```batch
# 双击运行
start.bat
```

**Linux/Mac:**
```bash
# 一键安装并启动
curl -fsSL https://raw.githubusercontent.com/YOUR_REPO/main/scripts/install_remote.sh | bash
cd ~/servermodel && ./start.sh
```

### 手动启动

```bash
# 安装依赖
pip install torch transformers psutil

# 启动服务
python core/node_unified_complete.py

# 访问 API
# http://localhost:8080
```

---

## 📦 一键部署

### Linux 服务器 (推荐)

```bash
# 一键安装
curl -fsSL https://raw.githubusercontent.com/ctz168/servermodel/main/scripts/install_remote.sh | bash

# 启动服务 (交互式选择模式)
cd ~/servermodel && ./start.sh
```

### Docker 部署

```bash
# 构建镜像
docker build -t distributed-llm .

# 运行容器
docker run -d -p 8080:8080 distributed-llm
```

### Docker Compose 集群

```bash
# 启动 3 节点集群
docker-compose up -d
```

---

## 🖥️ 集群部署

### 典型场景：4 节点混合并行

**资源清单：**
| 节点 | 系统 | 内存 | 角色 |
|------|------|------|------|
| 云主机1 | Linux | 8GB | Pipeline A 领导 |
| 云主机2 | Linux | 8GB | Pipeline B 领导 |
| 本地Win1 | Windows | 16GB | Pipeline A 工作 |
| 本地Win2 | Windows | 16GB | Pipeline B 工作 |

**拓扑结构：**
```
Pipeline A: 云主机1(8GB) → 本地Win1(16GB)  [运行 7B 模型]
Pipeline B: 云主机2(8GB) → 本地Win2(16GB)  [运行 7B 模型]
```

**部署步骤：**

1. **云主机1 (领导节点)**
```bash
curl -fsSL https://raw.githubusercontent.com/YOUR_REPO/main/scripts/install_remote.sh | bash
cd ~/servermodel && ./start.sh
# 选择: 2. Pipeline 领导节点
# 输入 Ngrok Token
# 记录输出的公网地址，如: tcp://0.tcp.ngrok.io:12345
```

2. **云主机2 (领导节点)**
```bash
curl -fsSL https://raw.githubusercontent.com/YOUR_REPO/main/scripts/install_remote.sh | bash
cd ~/servermodel && ./start.sh
# 选择: 2. Pipeline 领导节点
# 记录公网地址
```

3. **本地 Windows (工作节点)**
```powershell
.\start.bat
# 选择: 3. Pipeline 工作节点
# 输入对应的云主机 Ngrok 地址
```

### 模型容量参考

| 方案 | 模型大小 | 最小节点内存 | 推荐节点数 |
|------|----------|--------------|------------|
| 单节点 | 0.5B-3B | 4-8GB | 1 |
| 2节点 Pipeline | 3B-7B | 8GB | 2 |
| 4节点 Pipeline | 14B | 8GB | 4 |
| 混合并行 (2x2) | 7B | 8GB | 4 |

---

## 🔌 API 接口

### OpenAI 兼容接口

系统完全兼容 OpenAI API，可直接替换 `base_url`。

**聊天补全：**
```bash
curl -X POST http://localhost:8080/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "Qwen/Qwen2.5-7B-Instruct",
    "messages": [{"role": "user", "content": "你好"}]
  }'
```

**文本补全：**
```bash
curl -X POST http://localhost:8080/v1/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "Qwen/Qwen2.5-7B-Instruct",
    "prompt": "人工智能是"
  }'
```

### Python 调用

```python
from openai import OpenAI

client = OpenAI(
    base_url="http://localhost:8080/v1",
    api_key="not-needed"
)

response = client.chat.completions.create(
    model="Qwen/Qwen2.5-7B-Instruct",
    messages=[{"role": "user", "content": "你好"}]
)
print(response.choices[0].message.content)
```

### 接口列表

| 接口 | 方法 | 说明 |
|------|------|------|
| `/health` | GET | 健康检查 |
| `/status` | GET | 节点状态 |
| `/v1/models` | GET | 模型列表 |
| `/v1/chat/completions` | POST | 聊天补全 |
| `/v1/completions` | POST | 文本补全 |

---

## ⚙️ 配置说明

### 命令行参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `--port` | 5000 | 节点通信端口 |
| `--api-port` | 8080 | API 服务端口 |
| `--model` | Qwen2.5-0.5B-Instruct | 模型名称 |
| `--mode` | data_parallel | 并行模式 |
| `--stages` | 2 | Pipeline 阶段数 |
| `--seeds` | - | 种子节点地址 |
| `--ngrok` | - | 启用 Ngrok 穿透 |
| `--ngrok-auth-token` | - | Ngrok Token |
| `--auto` | - | 自动选择模式 |

### 配置文件 (config.json)

```json
{
  "node": {
    "port": 5000,
    "api_port": 8080
  },
  "model": {
    "name": "Qwen/Qwen2.5-7B-Instruct",
    "device": "auto"
  },
  "cluster": {
    "seeds": ["192.168.1.100:5000"],
    "wait_for_cluster": true
  }
}
```

### 并行模式

| 模式 | 说明 | 适用场景 |
|------|------|----------|
| `data_parallel` | 数据并行 | 内存充足，高吞吐 |
| `pipeline_parallel` | Pipeline 并行 | 大模型，跨节点 |
| `hybrid` | 混合并行 | 大规模集群 |

---

## 📁 项目结构

```
servermodel/
├── core/
│   └── node_unified_complete.py    # 核心程序 (单文件)
├── scripts/
│   ├── install_remote.sh           # Linux 一键安装
│   ├── install.sh                  # 本地安装
│   ├── start.sh                    # Linux 启动
│   ├── stop.sh                     # Linux 停止
│   ├── start_cluster.sh            # 集群启动
│   └── stop_cluster.sh             # 集群停止
├── test/
│   ├── test_api.py                 # API 测试
│   ├── quick_test.py               # 快速测试
│   ├── check_hardware.py           # 硬件检测
│   ├── cluster_plan.py             # 集群规划
│   └── generate_commands.py        # 命令生成器
├── ui/
│   └── index.html                  # Web UI
├── config.json                     # 配置文件
├── requirements.txt                # Python 依赖
├── Dockerfile                      # Docker 镜像
├── docker-compose.yml              # Docker Compose
├── install.bat                     # Windows 安装
├── start.bat                       # Windows 启动
├── stop.bat                        # Windows 停止
├── DEPLOY_GUIDE.md                 # 部署指南
└── README.md                       # 本文档
```

---

## 🔧 常见问题

### Q: 如何选择模型？

根据可用内存选择：

| 内存 | 推荐模型 |
|------|----------|
| 4-8GB | Qwen2.5-0.5B / 1.5B |
| 8-16GB | Qwen2.5-3B |
| 16-32GB | Qwen2.5-7B |
| 32GB+ | Qwen2.5-14B |

### Q: 如何在公网组建集群？

1. 领导节点使用 `--ngrok --ngrok-auth-token YOUR_TOKEN`
2. 记录输出的公网地址
3. 工作节点使用 `--seeds "公网地址"` 连接

### Q: 内存不足怎么办？

```bash
# 使用 FP16 精度
python core/node_unified_complete.py --precision fp16

# 或使用 Pipeline 并行分散到多节点
python core/node_unified_complete.py --mode pipeline_parallel --stages 2
```

### Q: 模型下载慢？

```bash
# 使用国内镜像
export HF_ENDPOINT=https://hf-mirror.com
python core/node_unified_complete.py
```

### Q: 如何查看硬件配置？

```bash
python test/check_hardware.py
```

### Q: 如何生成启动命令？

```bash
python test/generate_commands.py
```

---

## 📊 性能参考

### 硬件要求

| 模型 | CPU 内存 | GPU 显存 | 推理速度 |
|------|----------|----------|----------|
| 0.5B | 4GB | 2GB | ~50 tokens/s |
| 1.5B | 8GB | 4GB | ~30 tokens/s |
| 3B | 16GB | 8GB | ~20 tokens/s |
| 7B | 32GB | 16GB | ~10 tokens/s |
| 14B | 64GB | 32GB | ~5 tokens/s |

*注: CPU 模式速度约为 GPU 的 1/10

---

## 🧪 测试

```bash
# 快速测试
python test/quick_test.py

# 完整测试
python test/test_api.py

# 运行所有测试
python test/run_all.py
```

---

## 🛠️ 开发

### 环境准备

```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
# .\venv\Scripts\activate  # Windows

pip install -r requirements.txt
```

### 运行测试

```bash
python test/test_api.py
```

---

## 📄 许可证

MIT License

---

## 🙏 致谢

- [HuggingFace Transformers](https://huggingface.co/transformers/)
- [Qwen Team](https://github.com/QwenLM/Qwen)
- [PyTorch](https://pytorch.org/)
- [Ngrok](https://ngrok.com/)

---

## 📞 支持

- 问题反馈: [GitHub Issues](https://github.com/YOUR_REPO/issues)
- 文档: [DEPLOY_GUIDE.md](./DEPLOY_GUIDE.md)
