#!/usr/bin/env python3
"""
Ngrok 集成模块 - 为分布式推理系统提供内网穿透支持

使用场景：
1. 节点在不同网络环境下需要互联
2. 需要从外网访问本地推理服务
3. 开发测试环境快速部署

安装依赖：
pip install pyngrok
"""

import os
import json
import time
import subprocess
import requests
from typing import Optional, Dict, Any
from dataclasses import dataclass
from threading import Thread


@dataclass
class NgrokTunnel:
    """Ngrok 隧道信息"""
    name: str
    public_url: str
    local_port: int
    proto: str
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "public_url": self.public_url,
            "local_port": self.local_port,
            "proto": self.proto
        }


class NgrokManager:
    """Ngrok 管理器"""
    
    def __init__(self, auth_token: Optional[str] = None):
        """
        初始化 Ngrok 管理器
        
        Args:
            auth_token: Ngrok 认证令牌（可选，免费版不需要）
        """
        self.auth_token = auth_token
        self.tunnels: Dict[int, NgrokTunnel] = {}
        self._process = None
        self._api_url = "http://127.0.0.1:4040"
        
    def start_ngrok(self) -> bool:
        """启动 Ngrok 进程"""
        try:
            # 检查是否已安装 ngrok
            result = subprocess.run(["ngrok", "version"], capture_output=True)
            if result.returncode != 0:
                print("❌ Ngrok 未安装，请先安装: https://ngrok.com/download")
                return False
            
            # 启动 ngrok
            cmd = ["ngrok", "start", "--none"]
            if self.auth_token:
                cmd.extend(["--authtoken", self.auth_token])
            
            self._process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            
            # 等待 ngrok 启动
            time.sleep(2)
            
            # 检查是否启动成功
            if self._is_running():
                print("✅ Ngrok 已启动")
                return True
            else:
                print("❌ Ngrok 启动失败")
                return False
                
        except FileNotFoundError:
            print("❌ Ngrok 未安装，请先安装: https://ngrok.com/download")
            return False
        except Exception as e:
            print(f"❌ 启动 Ngrok 失败: {e}")
            return False
    
    def _is_running(self) -> bool:
        """检查 Ngrok 是否运行"""
        try:
            response = requests.get(f"{self._api_url}/api/tunnels", timeout=2)
            return response.status_code == 200
        except:
            return False
    
    def create_tunnel(
        self, 
        local_port: int, 
        name: Optional[str] = None,
        proto: str = "http"
    ) -> Optional[NgrokTunnel]:
        """
        创建隧道
        
        Args:
            local_port: 本地端口
            name: 隧道名称
            proto: 协议类型 (http, tcp)
            
        Returns:
            NgrokTunnel 或 None
        """
        if not self._is_running():
            if not self.start_ngrok():
                return None
        
        tunnel_name = name or f"tunnel-{local_port}"
        
        try:
            # 创建隧道
            payload = {
                "name": tunnel_name,
                "addr": str(local_port),
                "proto": proto
            }
            
            response = requests.post(
                f"{self._api_url}/api/tunnels",
                json=payload,
                timeout=10
            )
            
            if response.status_code == 201:
                data = response.json()
                tunnel = NgrokTunnel(
                    name=tunnel_name,
                    public_url=data["public_url"],
                    local_port=local_port,
                    proto=proto
                )
                self.tunnels[local_port] = tunnel
                print(f"✅ 隧道创建成功: {tunnel.public_url} -> localhost:{local_port}")
                return tunnel
            else:
                print(f"❌ 创建隧道失败: {response.text}")
                return None
                
        except Exception as e:
            print(f"❌ 创建隧道异常: {e}")
            return None
    
    def create_tcp_tunnel(self, local_port: int, name: Optional[str] = None) -> Optional[NgrokTunnel]:
        """创建 TCP 隧道（适合分布式节点通信）"""
        return self.create_tunnel(local_port, name, proto="tcp")
    
    def list_tunnels(self) -> Dict[int, NgrokTunnel]:
        """列出所有隧道"""
        return self.tunnels
    
    def close_tunnel(self, local_port: int) -> bool:
        """关闭指定隧道"""
        if local_port not in self.tunnels:
            return True
        
        tunnel = self.tunnels[local_port]
        
        try:
            response = requests.delete(
                f"{self._api_url}/api/tunnels/{tunnel.name}",
                timeout=5
            )
            
            if response.status_code == 204:
                del self.tunnels[local_port]
                print(f"✅ 隧道已关闭: {tunnel.public_url}")
                return True
            else:
                print(f"❌ 关闭隧道失败: {response.text}")
                return False
                
        except Exception as e:
            print(f"❌ 关闭隧道异常: {e}")
            return False
    
    def stop_ngrok(self):
        """停止 Ngrok"""
        if self._process:
            self._process.terminate()
            self._process.wait()
            self._process = None
            self.tunnels.clear()
            print("✅ Ngrok 已停止")
    
    def get_public_url(self, local_port: int) -> Optional[str]:
        """获取指定端口的公网 URL"""
        tunnel = self.tunnels.get(local_port)
        return tunnel.public_url if tunnel else None
    
    def save_config(self, filepath: str):
        """保存隧道配置"""
        config = {
            "tunnels": {str(k): v.to_dict() for k, v in self.tunnels.items()},
            "api_url": self._api_url
        }
        with open(filepath, 'w') as f:
            json.dump(config, f, indent=2)
    
    def load_config(self, filepath: str):
        """加载隧道配置"""
        if not os.path.exists(filepath):
            return
        
        with open(filepath, 'r') as f:
            config = json.load(f)
        
        # 重新创建隧道
        for port_str, tunnel_data in config.get("tunnels", {}).items():
            port = int(port_str)
            self.create_tunnel(port, tunnel_data["name"], tunnel_data["proto"])


class NgrokNodeAdapter:
    """
    Ngrok 节点适配器 - 为分布式节点提供内网穿透
    """
    
    def __init__(self, node_port: int, api_port: Optional[int] = None):
        """
        初始化适配器
        
        Args:
            node_port: 节点通信端口
            api_port: API 服务端口（可选）
        """
        self.node_port = node_port
        self.api_port = api_port
        self.ngrok = NgrokManager()
        self.node_tunnel: Optional[NgrokTunnel] = None
        self.api_tunnel: Optional[NgrokTunnel] = None
    
    def start(self) -> Dict[str, str]:
        """
        启动内网穿透
        
        Returns:
            公网地址映射
        """
        urls = {}
        
        # 创建节点通信隧道
        self.node_tunnel = self.ngrok.create_tcp_tunnel(
            self.node_port, 
            name=f"node-{self.node_port}"
        )
        if self.node_tunnel:
            urls["node_url"] = self.node_tunnel.public_url
        
        # 创建 API 隧道
        if self.api_port:
            self.api_tunnel = self.ngrok.create_tunnel(
                self.api_port,
                name=f"api-{self.api_port}",
                proto="http"
            )
            if self.api_tunnel:
                urls["api_url"] = self.api_tunnel.public_url
        
        return urls
    
    def stop(self):
        """停止内网穿透"""
        if self.node_tunnel:
            self.ngrok.close_tunnel(self.node_port)
        if self.api_tunnel:
            self.ngrok.close_tunnel(self.api_port)
        self.ngrok.stop_ngrok()
    
    def get_node_address(self) -> Optional[str]:
        """获取节点公网地址"""
        return self.node_tunnel.public_url if self.node_tunnel else None
    
    def get_api_address(self) -> Optional[str]:
        """获取 API 公网地址"""
        return self.api_tunnel.public_url if self.api_tunnel else None


# 使用示例
if __name__ == "__main__":
    print("=" * 60)
    print("Ngrok 内网穿透示例")
    print("=" * 60)
    
    # 示例1: 基本使用
    print("\n【示例1】创建 HTTP 隧道:")
    manager = NgrokManager()
    
    # 创建 HTTP 隧道（适合 Web 服务）
    tunnel = manager.create_tunnel(8080, name="web-service")
    if tunnel:
        print(f"公网地址: {tunnel.public_url}")
        print(f"本地端口: {tunnel.local_port}")
    
    # 示例2: 分布式节点使用
    print("\n【示例2】分布式节点内网穿透:")
    adapter = NgrokNodeAdapter(node_port=5000, api_port=8080)
    urls = adapter.start()
    
    if urls:
        print("节点公网地址:", urls.get("node_url"))
        print("API 公网地址:", urls.get("api_url"))
        
        # 其他节点可以通过这个地址连接
        print("\n其他节点连接命令:")
        print(f"python node_unified_production.py --port 5001 --seeds \"{urls.get('node_url')}\"")
    
    # 清理
    print("\n按 Ctrl+C 停止...")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n正在停止...")
        adapter.stop()
        manager.stop_ngrok()
