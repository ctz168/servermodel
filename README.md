# 统一分布式推理系统

> 🚀 **一键启动，开箱即用** - 无需复杂配置，打开即可运行大模型推理服务

## 📋 目录

- [快速开始](#-快速开始)
- [一键安装](#-一键安装)
- [使用方法](#-使用方法)
- [API 接口](#-api-接口)
- [多节点集群](#-多节点集群)
- [常见问题](#-常见问题)

---

## 🚀 快速开始

### 方式一：一键启动（推荐）

**Windows 用户：**
```bash
# 双击运行
start.bat
```

**Linux/Mac 用户：**
```bash
# 添加执行权限并运行
chmod +x start.sh && ./start.sh
```

### 方式二：手动启动

```bash
# 1. 安装依赖
pip install torch transformers psutil

# 2. 启动服务
python download/node_unified_complete.py

# 3. 打开浏览器访问
# http://localhost:8080
```

---

## 📦 一键安装

### Windows

```batch
:: 运行安装脚本
install.bat
```

### Linux/Mac

```bash
# 运行安装脚本
chmod +x install.sh && ./install.sh
```

### 手动安装

```bash
# 创建虚拟环境（可选）
python -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate   # Windows

# 安装依赖
pip install -r requirements.txt
```

---

## 🎯 使用方法

### 1. 最简单启动

```bash
python download/node_unified_complete.py
```

启动后访问：
- **API 地址**: http://localhost:8080
- **健康检查**: http://localhost:8080/health
- **状态查看**: http://localhost:8080/status

### 2. 自动模式选择

```bash
python download/node_unified_complete.py --auto
```

系统会自动检测你的硬件配置，选择最佳运行模式。

### 3. 指定模型

```bash
# 小模型（适合低配电脑）
python download/node_unified_complete.py --model "Qwen/Qwen2.5-0.5B-Instruct"

# 中等模型（适合 8GB+ 显存）
python download/node_unified_complete.py --model "Qwen/Qwen2.5-1.5B-Instruct"

# 大模型（适合 16GB+ 显存）
python download/node_unified_complete.py --model "Qwen/Qwen2.5-7B-Instruct"
```

### 4. 指定端口

```bash
python download/node_unified_complete.py --port 6000 --api-port 9000
```

---

## 🔌 API 接口

### OpenAI 兼容接口

系统完全兼容 OpenAI API 格式，可以直接替换 OpenAI 的 base_url 使用。

#### 聊天补全

```bash
curl -X POST http://localhost:8080/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "Qwen/Qwen2.5-0.5B-Instruct",
    "messages": [
      {"role": "user", "content": "你好，请介绍一下自己"}
    ]
  }'
```

#### 文本补全

```bash
curl -X POST http://localhost:8080/v1/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "Qwen/Qwen2.5-0.5B-Instruct",
    "prompt": "人工智能是"
  }'
```

### Python 调用

```python
import requests

# 聊天补全
response = requests.post(
    "http://localhost:8080/v1/chat/completions",
    json={
        "model": "Qwen/Qwen2.5-0.5B-Instruct",
        "messages": [
            {"role": "user", "content": "你好"}
        ]
    }
)

print(response.json())
```

### 使用 OpenAI SDK

```python
from openai import OpenAI

# 只需修改 base_url
client = OpenAI(
    base_url="http://localhost:8080/v1",
    api_key="not-needed"  # 本地部署不需要 API Key
)

response = client.chat.completions.create(
    model="Qwen/Qwen2.5-0.5B-Instruct",
    messages=[
        {"role": "user", "content": "你好"}
    ]
)

print(response.choices[0].message.content)
```

---

## 🖥️ 多节点集群

### 快速启动集群

**节点 1（领导节点）：**
```bash
python download/node_unified_complete.py --port 5000 --api-port 8080
```

**节点 2（工作节点）：**
```bash
python download/node_unified_complete.py --port 5001 --api-port 8081 --seeds "localhost:5000"
```

**节点 3（工作节点）：**
```bash
python download/node_unified_complete.py --port 5002 --api-port 8082 --seeds "localhost:5000"
```

### 使用启动脚本

```bash
# 启动 3 节点集群
./scripts/start_cluster.sh 3
```

---

## ⚙️ 配置选项

### 命令行参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `--port` | 5000 | 节点通信端口 |
| `--api-port` | 8080 | API 服务端口 |
| `--model` | Qwen/Qwen2.5-0.5B-Instruct | 模型名称 |
| `--mode` | data_parallel | 并行模式 |
| `--auto` | False | 自动选择模式 |
| `--seeds` | "" | 种子节点列表 |

### 并行模式

| 模式 | 说明 | 适用场景 |
|------|------|---------|
| `data_parallel` | 数据并行 | 内存充足，追求低延迟 |
| `pipeline_parallel` | Pipeline 并行 | 大模型，中等带宽 |
| `tensor_parallel` | Tensor 并行 | 大模型，高带宽网络 |
| `hybrid` | 混合并行 | 大规模集群 |

---

## 🔧 常见问题

### Q1: 端口被占用怎么办？

```bash
# 更换端口
python download/node_unified_complete.py --port 6000 --api-port 9000
```

### Q2: 内存不足怎么办？

```bash
# 使用更小的模型
python download/node_unified_complete.py --model "Qwen/Qwen2.5-0.5B-Instruct"

# 或者使用 CPU 模式（自动降级）
# 系统会自动检测并使用 CPU
```

### Q3: 模型下载失败？

```bash
# 使用国内镜像
export HF_ENDPOINT=https://hf-mirror.com
python download/node_unified_complete.py
```

### Q4: 如何查看日志？

```bash
# 启动时会自动打印日志到控制台
# 也可以重定向到文件
python download/node_unified_complete.py 2>&1 | tee server.log
```

### Q5: 如何停止服务？

```bash
# 按 Ctrl+C 停止
# 或者使用停止脚本
./scripts/stop.sh
```

---

## 📊 性能参考

### 硬件要求

| 模型大小 | 最低内存 | 推荐内存 | GPU 显存 |
|---------|---------|---------|---------|
| 0.5B | 4GB | 8GB | 2GB+ |
| 1.5B | 8GB | 16GB | 4GB+ |
| 7B | 16GB | 32GB | 8GB+ |
| 14B | 32GB | 64GB | 16GB+ |

### 推理速度参考

| 硬件 | 模型 | 速度 (tokens/s) |
|------|------|----------------|
| RTX 4090 | 7B | ~80 |
| RTX 3080 | 7B | ~40 |
| CPU (8核) | 0.5B | ~10 |

---

## 📁 项目结构

```
servermodel-glm/
├── download/
│   └── node_unified_complete.py   # 主程序（单文件，开箱即用）
├── scripts/
│   ├── start.sh                   # Linux/Mac 启动脚本
│   ├── start.bat                  # Windows 启动脚本
│   ├── stop.sh                    # 停止脚本
│   └── start_cluster.sh           # 集群启动脚本
├── docs/
│   ├── STARTUP_FLOW.md            # 启动流程详解
│   ├── MODE_UNIFICATION_PLAN.md   # 模式统一方案
│   └── BUCKET_EFFECT_ANALYSIS.md  # 木桶效应分析
├── requirements.txt               # Python 依赖
├── install.sh                     # Linux/Mac 安装脚本
├── install.bat                    # Windows 安装脚本
├── start.sh                       # 一键启动（Linux/Mac）
├── start.bat                      # 一键启动（Windows）
└── README.md                      # 本文档
```

---

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

---

## 📄 许可证

MIT License

---

## 🙏 致谢

- [HuggingFace Transformers](https://huggingface.co/transformers/)
- [Qwen Team](https://github.com/QwenLM/Qwen)
- [PyTorch](https://pytorch.org/)
