# Ngrok 集成指南

## 为什么不用 Ngrok？

### 原因分析

| 场景 | 是否使用 Ngrok | 原因 |
|------|---------------|------|
| **本地开发测试** | ✅ 推荐 | 快速暴露服务，无需配置 |
| **分布式推理系统** | ❌ 不推荐 | 延迟高、带宽限制 |
| **MCP Server** | ❌ 不需要 | 使用 stdio 通信 |
| **生产环境** | ❌ 不推荐 | 稳定性、安全性问题 |

### Ngrok 优缺点

**优点：**
- ✅ 快速暴露本地服务到公网
- ✅ 无需配置路由器/防火墙
- ✅ 自动 HTTPS 支持
- ✅ 适合开发测试

**缺点：**
- ❌ 免费版带宽限制
- ❌ 延迟较高（不适合实时推理）
- ❌ URL 不固定（免费版每次变化）
- ❌ 不适合生产环境

---

## 何时应该使用 Ngrok？

### 1. 开发测试环境
```bash
# 快速暴露本地服务
ngrok http 8080
```

### 2. 节点在不同网络环境
```bash
# 节点 A 在公司网络
ngrok tcp 5000
# 输出: tcp://0.tcp.ngrok.io:12345

# 节点 B 在家庭网络
python node.py --seeds "0.tcp.ngrok.io:12345"
```

### 3. 临时演示/分享
```bash
# 暴露 Web UI
ngrok http 3002
```

---

## 集成方案

已创建 `ngrok_integration.py` 模块，提供：

### 功能特性
- 自动启动/停止 Ngrok
- 创建 HTTP/TCP 隧道
- 分布式节点适配器
- 配置持久化

### 使用示例

```python
from ngrok_integration import NgrokManager, NgrokNodeAdapter

# 方式1: 基本使用
manager = NgrokManager()
tunnel = manager.create_tunnel(8080, proto="http")
print(f"公网地址: {tunnel.public_url}")

# 方式2: 分布式节点
adapter = NgrokNodeAdapter(node_port=5000, api_port=8080)
urls = adapter.start()
print(f"节点地址: {urls['node_url']}")
print(f"API地址: {urls['api_url']}")
```

### 命令行使用

```bash
# 安装依赖
pip install pyngrok

# 运行示例
python ngrok_integration.py
```

---

## 替代方案对比

| 方案 | 延迟 | 带宽 | 稳定性 | 成本 |
|------|------|------|--------|------|
| **Ngrok** | 高 | 限制 | 中 | 免费/付费 |
| **FRP** | 低 | 无限制 | 高 | 自建 |
| **Cloudflare Tunnel** | 中 | 无限制 | 高 | 免费 |
| **公网 IP** | 最低 | 无限制 | 最高 | 运营商 |

### 推荐

1. **开发测试**: Ngrok（快速便捷）
2. **生产环境**: 公网 IP + 云服务器
3. **企业内网**: FRP / Cloudflare Tunnel
