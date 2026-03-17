# 分布式大模型推理系统


<div align="center">

**一键安装 · 跨平台支持 · 傻瓜式使用**

一个轻量级、生产级的分布式大模型推理系统，支持多节点协同推理。


</div>

---

## ✨ 一键安装

### Linux / macOS

```bash
# 一键安装
curl -fsSL https://raw.githubusercontent.com/ctz168/sm/main/install.sh | bash

# 启动服务
dllm-start

# 或
~/.distributed-llm/start.sh
```

### Windows

```powershell
# 下载并运行安装脚本
# 方法1: PowerShell
Invoke-WebRequest -Uri "https://raw.githubusercontent.com/ctz168/sm/main/install.bat" -OutFile "install.bat"
.\install.bat

# 方法2: 直接下载
# 访问 https://github.com/ctz168/sm 下载项目
# 双击运行 install.bat
```

### Docker

```bash
# 克隆项目
git clone https://github.com/ctz168/sm.git
cd sm

# 启动服务
docker-compose up -d

# 查看日志
docker-compose logs -f
```

---

## 🚀 快速使用

### 启动服务

**Linux/macOS:**
```bash
# 方式1: 使用快捷命令
dllm-start

# 方式2: 直接运行
~/.distributed-llm/start.sh

# 方式3: 指定模式
./start.sh unified        # 统一去中心化模式（推荐）
./start.sh resource_aware # 资源感知模式
./start.sh pipeline       # Pipeline模式
./start.sh decentralized  # 去中心化模式
```

**Windows:**
```cmd
# 双击桌面快捷方式 "分布式大模型推理"
# 或运行
start.bat
```

### 停止服务

```bash
# Linux/macOS
dllm-stop
# 或
~/.distributed-llm/stop.sh

# Windows
stop.bat
```

### 查看状态

```bash
# Linux/macOS
dllm-status
# 或
~/.distributed-llm/status.sh

# Windows
status.bat
```

---

## 📋 五种运行模式

### 1. 统一去中心化模式（推荐）⭐

**特点：自动发现、自动选举、统一API**

- 任意节点启动，自动检测其他节点
- 第一个节点自动成为领导节点
- Raft共识算法保证高可用
- 领导节点提供统一API入口
- 支持联合分布式推理
- 故障自动恢复

```bash
# 第一个节点（自动成为领导）
python download/node_unified.py --port 5000 --api-port 8080

# 后续节点（自动发现并加入）
python download/node_unified.py --port 5001 --seeds "localhost:5000"

# 或使用启动脚本
./scripts/start_unified.sh 3  # 启动3个节点
```

**API端点（领导节点）:**
```
POST /inference - 提交推理请求
POST /task      - 提交异步任务
GET  /status    - 获取节点状态
GET  /nodes     - 获取节点列表
GET  /stats     - 获取统计信息
```

### 2. 资源感知模式

**特点：自动检测资源，智能启停**

- 资源不足时自动停止模型
- 资源充足时自动启动模型
- 适合资源有限的环境

```bash
./start.sh 1
# 或
python download/node_resource_aware.py --model Qwen/Qwen2.5-0.5B-Instruct
```

### 3. Pipeline并行模式

**特点：多节点分片，内存最优**

- 每个节点只加载部分层
- 内存使用降低50%
- 支持运行更大的模型

```bash
# 节点1
./start.sh 2
# 输入: 节点索引=0, 总节点数=2

# 节点2
./start.sh 2
# 输入: 节点索引=1, 总节点数=2
```

### 4. 去中心化模式

**特点：无单点故障，高可用**

- Raft共识算法
- 自动领导者选举
- 故障自动转移

```bash
./start.sh 3
```

### 5. 中心化模式

**特点：有Web管理界面**

- 需要先启动Orchestrator
- 支持Web监控

```bash
./start.sh 4
```

---

## 🏗️ 统一去中心化架构

### 工作流程

```
┌─────────────────────────────────────────────────────────────┐
│                    启动流程                                   │
├─────────────────────────────────────────────────────────────┤
│  1. 节点启动，检查是否有其他节点存在                           │
│  2. 如果没有其他节点 → 自动成为领导节点                        │
│  3. 如果有其他节点 → 加入集群，参与选举                        │
│  4. 领导节点负责：资源分配、API统一入口、任务调度               │
│  5. 所有节点都可以参与推理计算                                 │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                    集群架构                                   │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│    ┌──────────────┐                                         │
│    │   客户端请求   │                                         │
│    └──────┬───────┘                                         │
│           │                                                  │
│           ▼                                                  │
│    ┌──────────────┐      ┌──────────────┐                   │
│    │   领导节点    │◄────►│   工作节点1   │                   │
│    │  (Leader)    │      │  (Worker)    │                   │
│    │  - API入口   │      │  - 模型推理   │                   │
│    │  - 任务调度  │      │  - 资源上报   │                   │
│    │  - 资源分配  │      └──────────────┘                   │
│    └──────┬───────┘                                         │
│           │                                                  │
│           ▼                                                  │
│    ┌──────────────┐      ┌──────────────┐                   │
│    │   工作节点2   │◄────►│   工作节点3   │                   │
│    │  (Worker)    │      │  (Worker)    │                   │
│    └──────────────┘      └──────────────┘                   │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### 核心组件

| 组件 | 功能 |
|------|------|
| NetworkManager | TCP通信、消息编解码 |
| NodeDiscovery | UDP广播发现、种子节点连接 |
| RaftElection | Raft选举、心跳维护 |
| ModelManager | 模型加载、推理执行 |
| TaskScheduler | 任务队列、负载均衡 |
| DistributedInferenceEngine | 分布式推理协调 |

---

## 🔧 配置文件

配置文件位置: `~/.distributed-llm/config/config.yaml`

```yaml
# 模型配置
model:
  name: "Qwen/Qwen2.5-0.5B-Instruct"
  memory_gb: 2.0

# 资源配置
resources:
  min_memory_gb: 2.0
  min_cpu_percent: 10.0

# 网络配置
network:
  host: "0.0.0.0"
  port: 7000

# 模式选择
mode: "unified"  # unified, resource_aware, pipeline, decentralized
```

---

## 📡 API使用

服务启动后，可以通过HTTP API访问：

### 健康检查

```bash
curl http://localhost:8080/health
# {"status": "healthy"}
```

### 查看状态

```bash
curl http://localhost:8080/status
```

### 推理请求

```bash
curl -X POST http://localhost:8080/inference \
  -H "Content-Type: application/json" \
  -d '{"prompt": "你好", "max_tokens": 50}'
```

### Python调用

```python
import requests

response = requests.post(
    "http://localhost:8080/inference",
    json={"prompt": "你好", "max_tokens": 50}
)
print(response.json())
```

### 异步任务

```python
import requests
import time

# 提交任务
response = requests.post(
    "http://localhost:8080/task",
    json={"prompt": "写一首诗", "params": {"max_tokens": 100}}
)
task_id = response.json()["task_id"]

# 轮询结果
while True:
    status = requests.get(f"http://localhost:8080/status").json()
    # 检查任务状态...
    time.sleep(0.5)
```

---

## 🖥️ 开机自启

### Linux (systemd)

```bash
sudo cp /tmp/distributed-llm.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable distributed-llm
sudo systemctl start distributed-llm
```

### macOS (launchd)

```bash
cp /tmp/com.distributed.llm.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.distributed.llm.plist
```

### Windows

以管理员身份运行:
```cmd
%USERPROFILE%\.distributed-llm\install-service.bat
```

---

## 📁 安装目录结构

```
~/.distributed-llm/
├── sm/                    # 项目代码
│   ├── download/          # 节点服务
│   │   ├── node_unified.py           # 统一去中心化节点
│   │   ├── distributed_inference.py  # 分布式推理模块
│   │   ├── node_resource_aware.py    # 资源感知节点
│   │   ├── node_pipeline_shard.py    # Pipeline分片节点
│   │   ├── node_decentralized.py     # 去中心化节点
│   │   └── node_service_production.py # 生产级节点
│   └── ...
├── venv/                  # Python虚拟环境
├── config/                # 配置文件
│   └── config.yaml
├── start.sh               # 启动脚本
├── stop.sh                # 停止脚本
└── status.sh              # 状态脚本
```

---

## 🐳 Docker命令

```bash
# 构建镜像
docker build -t distributed-llm .

# 运行容器
docker run -d -p 7000:7000 --name llm distributed-llm

# 使用docker-compose
docker-compose up -d        # 启动
docker-compose logs -f      # 日志
docker-compose down         # 停止
docker-compose restart      # 重启
```

---

## ❓ 常见问题

### 1. 端口被占用

```bash
# 查看端口占用
lsof -i :7000        # Linux/macOS
netstat -ano | findstr :7000  # Windows

# 修改端口
# 编辑 config/config.yaml 中的 network.port
```

### 2. 内存不足

```bash
# 使用更小的模型
# 编辑 config/config.yaml
model:
  name: "Qwen/Qwen2.5-0.5B-Instruct"
```

### 3. 模型下载慢

```bash
# 使用镜像
export HF_ENDPOINT=https://hf-mirror.com
```

### 4. Python版本不兼容

```bash
# 需要 Python 3.8+
python3 --version
```

### 5. 领导节点选举失败

```bash
# 检查网络连接
ping <其他节点IP>

# 检查防火墙
sudo ufw allow 5000/tcp  # 节点通信端口
sudo ufw allow 9000/udp  # 发现端口
sudo ufw allow 8080/tcp  # API端口
```

---

## 📊 性能指标

| 模型 | 内存 | 延迟 | 吞吐量 |
|------|------|------|--------|
| Qwen2.5-0.5B | 1.8GB | 1.2s | 17 t/s |
| Qwen2.5-1.5B | 3.5GB | 2.5s | 20 t/s |
| Qwen2.5-7B | 14GB | 8s | 22 t/s |

---

## 🔄 版本更新

### GLM分支更新

本分支（glm）包含以下增强功能：

1. **统一去中心化模式** - 整合所有模式为单一统一模式
2. **自动节点发现** - UDP广播 + 种子节点双重发现机制
3. **Raft选举完善** - 完整的领导者选举和心跳维护
4. **联合分布式推理** - 支持模型分片和Pipeline并行
5. **统一API入口** - 领导节点提供统一的REST API

---

## 📜 许可证

MIT License

---

## 🙏 致谢

- [Qwen](https://github.com/QwenLM/Qwen) - 模型支持
- [Raft](https://raft.github.io/) - 共识算法
