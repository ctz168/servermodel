#!/usr/bin/env python3
"""
多层NAT穿透模块 - 借鉴比特币P2P网络设计
==========================================

解决分布式推理节点跨网络通信问题。

比特币P2P网络如何穿透NAT:
1. 主动出站连接: 节点主动发起多个出站连接,NAT/防火墙允许出站流量
2. addr消息交换: 节点间交换已知对等节点地址,构建去中心化地址簿
3. 反向连接: 利用已有出站连接的NAT映射接收入站连接
4. DNS种子引导: 新节点通过硬编码DNS种子发现可达节点
5. 无需STUN/TURN: 比特币用"多出站连接"策略,8+出站即可接收入站

连接策略(按优先级):
  Layer 1: 直连 TCP — 局域网或已转发端口 (当前实现)
  Layer 2: UPnP自动端口转发 — 家庭路由器 ~60%成功率
  Layer 3: STUN探测 + UDP打洞 — Cone NAT ~70%
  Layer 4: TURN中继 — 保底方案,使用中继带宽
  Layer 5: 反向连接 — 比特币风格,利用已有出站连接中转
"""

import os
import sys
import socket
import struct
import random
import time
import json
import uuid
import threading
import logging
import traceback
from typing import Dict, List, Optional, Any, Tuple, Callable, Set
from dataclasses import dataclass, field
from enum import Enum
from concurrent.futures import ThreadPoolExecutor, Future

logger = logging.getLogger("nat_traversal")

# 可选依赖
try:
    import miniupnpc
    HAS_UPNP = True
except ImportError:
    HAS_UPNP = False


# ==================== 枚举 ====================

class NatType(Enum):
    """NAT类型"""
    UNKNOWN = "unknown"
    FULL_CONE = "full_cone"                # 完全锥形NAT - 最容易穿透
    RESTRICTED_CONE = "restricted_cone"     # 受限锥形NAT
    PORT_RESTRICTED_CONE = "port_restricted_cone"  # 端口受限锥形NAT
    SYMMETRIC = "symmetric"                 # 对称NAT - 最难穿透,需要TURN
    BLOCKED = "blocked"                     # 完全被阻止


class ConnectionMethod(Enum):
    """连接方式"""
    DIRECT = "direct"           # 直连
    UPNP = "upnp"              # UPnP端口转发
    HOLE_PUNCH = "hole_punch"  # UDP打洞
    RELAY = "relay"            # TURN中继
    REVERSE = "reverse"        # 反向连接
    FAILED = "failed"          # 全部失败


# ==================== 数据结构 ====================

@dataclass
class NatInfo:
    """NAT信息"""
    nat_type: NatType = NatType.UNKNOWN
    external_ip: str = ""
    external_port: int = 0
    internal_ip: str = ""
    internal_port: int = 0
    upnp_available: bool = False
    public_reachable: bool = False

    def to_dict(self) -> Dict:
        return {
            "nat_type": self.nat_type.value,
            "external_ip": self.external_ip,
            "external_port": self.external_port,
            "internal_ip": self.internal_ip,
            "internal_port": self.internal_port,
            "upnp_available": self.upnp_available,
            "public_reachable": self.public_reachable,
        }


@dataclass
class RelayRegistration:
    """中继注册信息"""
    node_id: str
    host: str
    port: int
    registered_at: float = 0.0


# ==================== UPnP 管理器 ====================

class UPnPManager:
    """UPnP/NAT-PMP 端口转发管理器

    利用家庭路由器的UPnP功能自动配置端口转发。
    在大多数家庭路由器上成功率约60%。
    """

    def __init__(self):
        self.upnpc = None
        self.available = False
        self.mapped_ports: Dict[Tuple[int, str], int] = {}  # (internal_port, protocol) -> external_port
        self.external_ip: Optional[str] = None
        self.lock = threading.Lock()

    def discover(self) -> bool:
        """发现UPnP IGD设备"""
        if not HAS_UPNP:
            logger.debug("miniupnpc未安装, UPnP不可用")
            return False

        try:
            self.upnpc = miniupnpc.UPnP()
            # 发现IGD设备
            discover_result = self.upnpc.discover()
            if discover_result <= 0:
                logger.debug("未发现UPnP IGD设备")
                return False

            # 选择IGD
            self.upnpc.selectigd()

            # 获取外部IP
            self.external_ip = self.upnpc.externalipaddress()
            if not self.external_ip:
                logger.debug("UPnP: 无法获取外部IP")
                return False

            self.available = True
            logger.info(f"UPnP IGD已发现, 外部IP: {self.external_ip}")
            return True

        except Exception as e:
            logger.debug(f"UPnP发现失败: {e}")
            return False

    def add_port_mapping(self, internal_port: int, protocol: str = "TCP",
                         description: str = "servermodel",
                         lease_duration: int = 0) -> Optional[int]:
        """添加端口映射

        Args:
            internal_port: 内部端口
            protocol: 协议 (TCP/UDP)
            description: 映射描述
            lease_duration: 租约时长(秒), 0表示永久

        Returns:
            外部端口, 或 None (失败时)
        """
        if not self.available or not self.upnpc:
            return None

        with self.lock:
            try:
                key = (internal_port, protocol)

                # 如果已经有映射,返回已有的
                if key in self.mapped_ports:
                    return self.mapped_ports[key]

                # 尝试使用相同的端口号
                external_port = internal_port

                result = self.upnpc.addportmapping(
                    external_port, protocol,
                    _get_local_ip(), internal_port,
                    description, lease_duration
                )

                if result:
                    self.mapped_ports[key] = external_port
                    logger.info(f"UPnP: 映射 {protocol} {internal_port} -> {external_port}")
                    return external_port
                else:
                    logger.debug(f"UPnP: 端口映射失败 {internal_port}")
                    return None

            except Exception as e:
                logger.debug(f"UPnP映射异常: {e}")
                return None

    def remove_port_mapping(self, external_port: int, protocol: str = "TCP"):
        """删除端口映射"""
        if not self.available or not self.upnpc:
            return

        with self.lock:
            try:
                self.upnpc.deleteportmapping(external_port, protocol)
                # 清理缓存
                keys_to_remove = [
                    k for k, v in self.mapped_ports.items()
                    if v == external_port and k[1] == protocol
                ]
                for k in keys_to_remove:
                    del self.mapped_ports[k]
                logger.info(f"UPnP: 删除映射 {protocol}:{external_port}")
            except Exception as e:
                logger.debug(f"UPnP删除映射异常: {e}")

    def get_external_ip(self) -> Optional[str]:
        """获取外部IP"""
        if self.external_ip:
            return self.external_ip
        if self.discover():
            return self.external_ip
        return None

    def cleanup(self):
        """清理所有映射"""
        with self.lock:
            for key, ext_port in list(self.mapped_ports.items()):
                protocol = key[1]
                try:
                    if self.upnpc:
                        self.upnpc.deleteportmapping(ext_port, protocol)
                except Exception:
                    pass
            self.mapped_ports.clear()
            logger.info("UPnP: 已清理所有端口映射")


# ==================== STUN 客户端 ====================

class STUNClient:
    """STUN 客户端 - 纯Python实现,无需外部依赖

    STUN (Session Traversal Utilities for NAT) 用于:
    1. 发现节点的公网IP和端口
    2. 检测NAT类型

    协议实现:
    - STUN Binding Request (Type 0x0001)
    - STUN Binding Response (Type 0x0101)
    - XOR-MAPPED-ADDRESS 属性 (Type 0x0020)
    """

    # 公共STUN服务器
    STUN_SERVERS = [
        ("stun.l.google.com", 19302),
        ("stun1.l.google.com", 19302),
        ("stun2.l.google.com", 19302),
        ("stun3.l.google.com", 19302),
        ("stun4.l.google.com", 19302),
        ("stun.ekiga.net", 3478),
        ("stun.ideasip.com", 3478),
        ("stun.schlund.de", 3478),
    ]

    MAGIC_COOKIE = 0x2112A442

    def __init__(self):
        self.external_ip: Optional[str] = None
        self.external_port: int = 0
        self.nat_type: NatType = NatType.UNKNOWN
        self.socket: Optional[socket.socket] = None

    def _build_binding_request(self) -> bytes:
        """构建STUN Binding Request"""
        # Message Type: 0x0001 (Binding Request)
        # Message Length: 0 (no attributes)
        # Magic Cookie: 0x2112A442
        # Transaction ID: 12 random bytes
        transaction_id = os.urandom(12)
        header = struct.pack("!HHI", 0x0001, 0x0000, self.MAGIC_COOKIE)
        return header + transaction_id

    def _parse_binding_response(self, data: bytes) -> Optional[Tuple[str, int, bytes]]:
        """解析STUN Binding Response

        Returns:
            (external_ip, external_port, transaction_id) 或 None
        """
        try:
            if len(data) < 20:
                return None

            msg_type, msg_length, magic_cookie = struct.unpack("!HHI", data[:8])
            transaction_id = data[8:20]

            # 验证Magic Cookie
            if magic_cookie != self.MAGIC_COOKIE:
                return None

            # 验证Message Type (0x0101 = Binding Response)
            if msg_type != 0x0101:
                return None

            # 解析属性
            offset = 20
            remaining = msg_length

            while remaining >= 4:
                attr_type, attr_length = struct.unpack("!HH", data[offset:offset + 4])
                attr_data = data[offset + 4:offset + 4 + attr_length]

                if attr_type == 0x0020:  # XOR-MAPPED-ADDRESS
                    if len(attr_data) >= 8:
                        reserved = attr_data[0]
                        family = attr_data[1]
                        if family == 0x01:  # IPv4
                            x_port = struct.unpack("!H", attr_data[2:4])[0]
                            x_ip = struct.unpack("!I", attr_data[4:8])[0]

                            # XOR解密
                            ext_port = x_port ^ (self.MAGIC_COOKIE >> 16)
                            ext_ip = x_ip ^ self.MAGIC_COOKIE
                            ip_str = socket.inet_ntoa(struct.pack("!I", ext_ip))
                            return (ip_str, ext_port, transaction_id)

                # 移到下一个属性 (对齐到4字节边界)
                offset += 4 + attr_length
                attr_padded = (attr_length + 3) & ~3
                remaining -= (4 + attr_padded)

            return None

        except Exception as e:
            logger.debug(f"STUN响应解析失败: {e}")
            return None

    def _stun_request(self, server: Tuple[str, int], local_port: int = 0,
                      timeout: float = 3.0) -> Optional[Tuple[str, int, bytes]]:
        """发送STUN请求到指定服务器

        Args:
            server: (host, port)
            local_port: 本地端口, 0表示自动选择
            timeout: 超时时间

        Returns:
            (external_ip, external_port, transaction_id) 或 None
        """
        sock = None
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.settimeout(timeout)

            if local_port > 0:
                sock.bind(("0.0.0.0", local_port))
                actual_local_port = local_port
            else:
                sock.bind(("0.0.0.0", 0))
                actual_local_port = sock.getsockname()[1]

            request = self._build_binding_request()
            sock.sendto(request, server)

            data, addr = sock.recvfrom(1024)
            result = self._parse_binding_response(data)

            if result:
                ext_ip, ext_port, txn_id = result
                # 记录实际使用的本地端口
                self.external_port = ext_port
                return (ext_ip, ext_port, txn_id)

            return None

        except socket.timeout:
            logger.debug(f"STUN请求超时: {server[0]}:{server[1]}")
            return None
        except Exception as e:
            logger.debug(f"STUN请求失败 {server[0]}:{server[1]}: {e}")
            return None
        finally:
            if sock:
                try:
                    sock.close()
                except Exception:
                    pass

    def discover(self, local_port: int = 0) -> NatInfo:
        """探测NAT类型和外部地址

        步骤:
        1. 向第一个STUN服务器发送请求,获取外部IP:端口 (test1)
        2. 向第二个STUN服务器发送请求,获取外部IP:端口 (test2)
        3. 比较:
           - 同IP同端口 → Full Cone NAT
           - 同IP不同端口 → Symmetric NAT (最难穿透)
           - 不同IP → 检测是否有多层NAT

        Args:
            local_port: 固定本地端口进行测试

        Returns:
            NatInfo 对象
        """
        nat_info = NatInfo()
        nat_info.internal_ip = _get_local_ip()
        nat_info.internal_port = local_port

        # 选择两个不同的STUN服务器
        if len(self.STUN_SERVERS) < 2:
            nat_info.nat_type = NatType.UNKNOWN
            return nat_info

        server1 = self.STUN_SERVERS[0]
        server2 = self.STUN_SERVERS[1]

        logger.info(f"STUN探测: 使用 {server1[0]} 和 {server2[0]}")

        # Test 1: 向第一个服务器发送请求
        result1 = self._stun_request(server1, local_port, timeout=3.0)

        if not result1:
            # 尝试其他服务器
            for server in self.STUN_SERVERS[2:5]:
                result1 = self._stun_request(server, local_port, timeout=2.0)
                if result1:
                    server1 = server
                    break

        if not result1:
            nat_info.nat_type = NatType.BLOCKED
            logger.warning("STUN: 无法连接任何STUN服务器, 可能被完全阻止")
            return nat_info

        ext_ip1, ext_port1, txn1 = result1
        self.external_ip = ext_ip1
        self.external_port = ext_port1
        nat_info.external_ip = ext_ip1
        nat_info.external_port = ext_port1

        # Test 2: 向第二个服务器发送请求 (同一个本地端口)
        # 需要复用同一个socket来保持NAT映射
        sock = None
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.settimeout(3.0)

            if local_port > 0:
                sock.bind(("0.0.0.0", local_port))

            request = self._build_binding_request()
            sock.sendto(request, server2)

            data2, addr2 = sock.recvfrom(1024)
            result2 = self._parse_binding_response(data2)

            if result2:
                ext_ip2, ext_port2, _ = result2

                if ext_ip1 == ext_ip2 and ext_port1 == ext_port2:
                    nat_info.nat_type = NatType.FULL_CONE
                    logger.info(f"STUN: Full Cone NAT (最容易穿透)")
                elif ext_ip1 == ext_ip2 and ext_port1 != ext_port2:
                    nat_info.nat_type = NatType.SYMMETRIC
                    logger.info(f"STUN: Symmetric NAT (需要TURN中继)")
                else:
                    # 不同外部IP - 可能有多个NAT
                    nat_info.nat_type = NatType.PORT_RESTRICTED_CONE
                    logger.info(f"STUN: 检测到多层NAT或端口受限")
            else:
                nat_info.nat_type = NatType.RESTRICTED_CONE
                logger.info(f"STUN: 受限锥形NAT (可尝试打洞)")

        except socket.timeout:
            nat_info.nat_type = NatType.RESTRICTED_CONE
        except Exception as e:
            logger.debug(f"STUN test2 失败: {e}")
            nat_info.nat_type = NatType.RESTRICTED_CONE
        finally:
            if sock:
                try:
                    sock.close()
                except Exception:
                    pass

        # 检查是否可达 (外部IP不等于内部IP说明在NAT后面)
        nat_info.public_reachable = (ext_ip1 != nat_info.internal_ip)

        return nat_info


# ==================== UDP 打洞 ====================

class HolePuncher:
    """UDP 打洞器

    在两个节点都位于NAT后面时,通过同时向对方发送UDP包来打通NAT映射。
    需要一个协调方(Rendezvous)来交换双方的公网地址。

    适用于: Full Cone, Restricted Cone, Port Restricted Cone
    不适用于: Symmetric NAT (需要TURN)
    """

    def __init__(self, nat_info: NatInfo):
        self.nat_info = nat_info
        self.punch_socket: Optional[socket.socket] = None
        self.punch_port: int = 0

    def create_punch_socket(self, bind_port: int = 0) -> socket.socket:
        """创建用于打洞的UDP socket"""
        if self.punch_socket:
            try:
                self.punch_socket.close()
            except Exception:
                pass

        self.punch_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.punch_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.punch_socket.settimeout(5.0)

        if bind_port > 0:
            self.punch_socket.bind(("0.0.0.0", bind_port))
            self.punch_port = bind_port
        else:
            self.punch_socket.bind(("0.0.0.0", 0))
            self.punch_port = self.punch_socket.getsockname()[1]

        return self.punch_socket

    def punch_to_target(self, target_ip: str, target_port: int,
                        num_packets: int = 10, interval: float = 0.1) -> bool:
        """
        向目标发送UDP包以创建NAT映射

        Args:
            target_ip: 目标的公网IP
            target_port: 目标的公网端口
            num_packets: 发送包数量
            interval: 发送间隔

        Returns:
            是否收到目标的响应
        """
        if not self.punch_socket:
            self.create_punch_socket()

        try:
            # 发送多个包确保NAT映射建立
            for i in range(num_packets):
                punch_msg = b"PUNCH:" + uuid.uuid4().hex[:8].encode()
                try:
                    self.punch_socket.sendto(punch_msg, (target_ip, target_port))
                except Exception:
                    pass
                time.sleep(interval)

            # 等待响应
            try:
                self.punch_socket.settimeout(2.0)
                data, addr = self.punch_socket.recvfrom(1024)
                logger.info(f"打洞成功! 收到 {addr[0]}:{addr[1]} 的响应")
                return True
            except socket.timeout:
                logger.debug("打洞未收到响应")
                return False

        except Exception as e:
            logger.debug(f"打洞失败: {e}")
            return False

    def coordinated_punch(self, target_ip: str, target_port: int,
                          local_port: int = 0,
                          punch_callback: Callable = None) -> bool:
        """
        协调式打洞 - 需要双方同时发送

        Args:
            target_ip: 目标公网IP
            target_port: 目标公网端口
            local_port: 本地绑定端口
            punch_callback: 打洞完成回调, 参数(socket, target_addr)

        Returns:
            是否成功
        """
        sock = self.create_punch_socket(local_port)

        # 启动接收线程
        received = threading.Event()
        received_data = None
        received_addr = None

        def recv_loop():
            nonlocal received_data, received_addr
            while not received.is_set():
                try:
                    sock.settimeout(2.0)
                    data, addr = sock.recvfrom(4096)
                    if data:
                        received_data = data
                        received_addr = addr
                        received.set()
                except socket.timeout:
                    continue
                except Exception:
                    break

        recv_thread = threading.Thread(target=recv_loop, daemon=True)
        recv_thread.start()

        # 同时发送多个包
        success = False
        for i in range(20):
            try:
                msg = f"PUNCH:{i}:{uuid.uuid4().hex[:8]}".encode()
                sock.sendto(msg, (target_ip, target_port))
            except Exception:
                pass

            if received.wait(timeout=0.15):
                success = True
                break
            time.sleep(0.05)

        received.set()

        if success and punch_callback:
            try:
                punch_callback(sock, received_addr)
            except Exception:
                pass

        return success

    def cleanup(self):
        """清理资源"""
        if self.punch_socket:
            try:
                self.punch_socket.close()
            except Exception:
                pass
            self.punch_socket = None


# ==================== TCP 中继服务器 ====================

class RelayServer:
    """TCP 中继服务器

    运行在公网可达的节点上。其他NAT后的节点连接到中继服务器,
    中继服务器负责转发数据。

    借鉴比特币的反向连接思想:
    - 节点A连接中继并注册
    - 节点B连接中继并注册
    - 中继建立A和B之间的数据通道
    - 双方通过中继透明通信
    """

    def __init__(self, host: str = "0.0.0.0", port: int = 6000):
        self.host = host
        self.port = port
        self.server_socket: Optional[socket.socket] = None
        self.connections: Dict[str, socket.socket] = {}  # node_id -> socket
        self.pending_data: Dict[str, List[bytes]] = {}   # node_id -> [data, ...]
        self.lock = threading.Lock()
        self.running = False
        self.active_relays: Set[Tuple[str, str]] = set()  # (nodeA, nodeB) pairs

    def start(self):
        """启动中继服务器"""
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind((self.host, self.port))
        self.server_socket.listen(50)
        self.server_socket.settimeout(1.0)
        self.running = True

        threading.Thread(target=self._accept_loop, daemon=True).start()
        logger.info(f"[RELAY] 中继服务器启动: {self.host}:{self.port}")

    def _accept_loop(self):
        """接受连接"""
        while self.running:
            try:
                conn, addr = self.server_socket.accept()
                threading.Thread(
                    target=self._handle_relay_client,
                    args=(conn, addr), daemon=True
                ).start()
            except socket.timeout:
                continue
            except Exception:
                if self.running:
                    break

    def _handle_relay_client(self, conn: socket.socket, addr):
        """处理中继客户端连接"""
        node_id = None
        try:
            # 接收注册消息 (JSON: {"type": "register", "node_id": "xxx", ...})
            data = b""
            while True:
                chunk = conn.recv(65536)
                if not chunk:
                    break
                data += chunk
                # 尝试解析
                try:
                    msg = json.loads(data.decode('utf-8'))
                    break
                except (json.JSONDecodeError, UnicodeDecodeError):
                    if len(data) > 100000:  # 防止过大
                        return
                    continue

            if not isinstance(msg, dict):
                return

            msg_type = msg.get("type", "")

            if msg_type == "register":
                node_id = msg.get("node_id", "")
                if not node_id:
                    return

                with self.lock:
                    # 关闭旧连接
                    if node_id in self.connections:
                        try:
                            self.connections[node_id].close()
                        except Exception:
                            pass
                    self.connections[node_id] = conn
                    logger.info(f"[RELAY] 节点注册: {node_id[:8]} (共{len(self.connections)}个)")

                # 等待并转发数据
                self._relay_loop(conn, node_id)

            elif msg_type == "send":
                node_id = msg.get("from_node", "")
                target_id = msg.get("target_node", "")
                payload = msg.get("payload", "")
                if isinstance(payload, str):
                    payload = payload.encode('utf-8')

                self._forward_data(node_id, target_id, payload)

        except Exception as e:
            logger.debug(f"[RELAY] 客户端处理错误: {e}")
        finally:
            if node_id:
                with self.lock:
                    self.connections.pop(node_id, None)
                logger.info(f"[RELAY] 节点断开: {node_id[:8]}")
            try:
                conn.close()
            except Exception:
                pass

    def _relay_loop(self, conn: socket.socket, node_id: str):
        """中继数据循环"""
        buffer = b""
        while self.running:
            try:
                conn.settimeout(1.0)
                chunk = conn.recv(65536)
                if not chunk:
                    break
                buffer += chunk

                # 尝试按行解析JSON消息
                while b'\n' in buffer:
                    line, buffer = buffer.split(b'\n', 1)
                    try:
                        msg = json.loads(line.decode('utf-8'))
                        if msg.get("type") == "send":
                            target_id = msg.get("target_node", "")
                            payload = msg.get("payload", "")
                            if isinstance(payload, str):
                                payload = payload.encode('utf-8')
                            self._forward_data(node_id, target_id, payload)
                    except (json.JSONDecodeError, UnicodeDecodeError):
                        pass

            except socket.timeout:
                continue
            except Exception:
                break

    def _forward_data(self, from_id: str, target_id: str, data: bytes):
        """转发数据到目标节点"""
        with self.lock:
            target_conn = self.connections.get(target_id)
            if target_conn:
                try:
                    msg = json.dumps({
                        "type": "data",
                        "from_node": from_id,
                        "payload": data.decode('utf-8', errors='replace'),
                    }).encode('utf-8') + b'\n'
                    target_conn.sendall(msg)
                except Exception as e:
                    logger.debug(f"[RELAY] 转发失败 {from_id[:8]} -> {target_id[:8]}: {e}")
            else:
                # 目标不在线,缓存数据
                if target_id not in self.pending_data:
                    self.pending_data[target_id] = []
                self.pending_data[target_id].append(data)
                # 限制缓存大小
                if len(self.pending_data[target_id]) > 100:
                    self.pending_data[target_id] = self.pending_data[target_id][-50:]

    def stop(self):
        """停止中继服务器"""
        self.running = False
        with self.lock:
            for conn in self.connections.values():
                try:
                    conn.close()
                except Exception:
                    pass
            self.connections.clear()
        if self.server_socket:
            try:
                self.server_socket.close()
            except Exception:
                pass
        logger.info("[RELAY] 中继服务器已停止")


# ==================== 中继客户端 ====================

class RelayClient:
    """中继客户端

    连接到中继服务器,通过中继与其他节点通信。
    用于NAT穿透失败时的最后保底方案。
    """

    def __init__(self, relay_host: str, relay_port: int, node_id: str):
        self.relay_host = relay_host
        self.relay_port = relay_port
        self.node_id = node_id
        self.socket: Optional[socket.socket] = None
        self.connected = False
        self.lock = threading.Lock()
        self.data_handlers: List[Callable] = []
        self.recv_thread: Optional[threading.Thread] = None
        self.running = False

    def connect(self, timeout: float = 10.0) -> bool:
        """连接到中继服务器并注册"""
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.settimeout(timeout)
            self.socket.connect((self.relay_host, self.relay_port))

            # 发送注册消息
            register_msg = json.dumps({
                "type": "register",
                "node_id": self.node_id,
                "timestamp": time.time(),
            }).encode('utf-8')

            self.socket.sendall(register_msg)

            self.connected = True
            self.running = True

            # 启动接收线程
            self.recv_thread = threading.Thread(target=self._recv_loop, daemon=True)
            self.recv_thread.start()

            logger.info(f"[RELAY-CLIENT] 已连接到中继 {self.relay_host}:{self.relay_port}")
            return True

        except Exception as e:
            logger.error(f"[RELAY-CLIENT] 连接失败: {e}")
            self.connected = False
            return False

    def send_to_node(self, target_node_id: str, data: bytes) -> bool:
        """通过中继发送数据到目标节点"""
        if not self.connected or not self.socket:
            return False

        try:
            payload = data.decode('utf-8', errors='replace') if isinstance(data, bytes) else data
            msg = json.dumps({
                "type": "send",
                "from_node": self.node_id,
                "target_node": target_node_id,
                "payload": payload,
            }).encode('utf-8') + b'\n'

            with self.lock:
                self.socket.sendall(msg)
            return True

        except Exception as e:
            logger.debug(f"[RELAY-CLIENT] 发送失败: {e}")
            self.connected = False
            return False

    def register_handler(self, handler: Callable):
        """注册数据接收处理器

        handler(data: bytes, from_node_id: str)
        """
        self.data_handlers.append(handler)

    def _recv_loop(self):
        """接收数据循环"""
        buffer = b""
        while self.running and self.connected:
            try:
                self.socket.settimeout(2.0)
                chunk = self.socket.recv(65536)
                if not chunk:
                    break
                buffer += chunk

                while b'\n' in buffer:
                    line, buffer = buffer.split(b'\n', 1)
                    try:
                        msg = json.loads(line.decode('utf-8'))
                        if msg.get("type") == "data":
                            from_node = msg.get("from_node", "")
                            payload = msg.get("payload", "")
                            if isinstance(payload, str):
                                payload = payload.encode('utf-8')
                            for handler in self.data_handlers:
                                try:
                                    handler(payload, from_node)
                                except Exception as e:
                                    logger.debug(f"[RELAY-CLIENT] handler错误: {e}")
                    except (json.JSONDecodeError, UnicodeDecodeError):
                        pass

            except socket.timeout:
                continue
            except Exception:
                break

        self.connected = False
        logger.info("[RELAY-CLIENT] 接收循环结束")

    def disconnect(self):
        """断开连接"""
        self.running = False
        self.connected = False
        if self.socket:
            try:
                self.socket.close()
            except Exception:
                pass
        logger.info("[RELAY-CLIENT] 已断开")


# ==================== 主管理器 ====================

class NatTraversalManager:
    """
    多层NAT穿透管理器

    借鉴比特币P2P网络的设计理念:

    比特币做法:
    ┌──────────────────────────────────────────────┐
    │ 1. 主动发起8+出站连接                          │
    │ 2. 通过addr消息交换节点地址                      │
    │ 3. 利用已有NAT映射接收入站连接                   │
    │ 4. DNS种子引导新节点加入                        │
    │ 5. 无需STUN/TURN/UPnP                          │
    └──────────────────────────────────────────────┘

    本系统策略 (5层回退):
    ┌──────────────────────────────────────────────┐
    │ Layer 1: 直连TCP (当前实现)                     │
    │ Layer 2: UPnP自动端口转发 (~60%家庭路由器)       │
    │ Layer 3: STUN探测 + UDP打洞 (Cone NAT ~70%)    │
    │ Layer 4: TCP中继 (保底,需要公网中继节点)          │
    │ Layer 5: 反向连接 (比特币风格,已有出站连接中转)    │
    └──────────────────────────────────────────────┘
    """

    def __init__(self, config=None):
        config = config or {}
        self.upnp = UPnPManager()
        self.stun = STUNClient()
        self.hole_puncher: Optional[HolePuncher] = None
        self.relay_client: Optional[RelayClient] = None
        self.nat_info: Optional[NatInfo] = None
        self.connection_method: str = "unknown"
        self.discovered = False

        # 配置
        self.relay_servers: List[Tuple[str, int]] = []
        relay_list = config.get("relay_servers", [])
        for r in relay_list:
            parts = r.split(":")
            if len(parts) == 2:
                self.relay_servers.append((parts[0], int(parts[1])))

        # 统计
        self.direct_success = 0
        self.upnp_success = 0
        self.punch_success = 0
        self.relay_success = 0

    def discover(self, local_port: int = 0) -> NatInfo:
        """
        探测NAT类型和外部地址

        Args:
            local_port: 本地端口 (用于STUN测试)

        Returns:
            NatInfo
        """
        logger.info("=" * 50)
        logger.info("开始NAT探测...")
        logger.info("=" * 50)

        nat_info = NatInfo()
        nat_info.internal_ip = _get_local_ip()
        nat_info.internal_port = local_port

        # Step 1: STUN探测
        logger.info("[1/3] STUN探测外部地址和NAT类型...")
        nat_info = self.stun.discover(local_port)

        # Step 2: UPnP探测
        logger.info("[2/3] UPnP探测...")
        nat_info.upnp_available = self.upnp.discover()
        if nat_info.upnp_available:
            upnp_ip = self.upnp.get_external_ip()
            if upnp_ip:
                nat_info.external_ip = upnp_ip

        # Step 3: 综合判断
        logger.info("[3/3] 综合判断...")
        nat_info.public_reachable = (
            nat_info.external_ip != "" and
            nat_info.external_ip != nat_info.internal_ip
        )

        self.nat_info = nat_info
        self.discovered = True

        # 打印结果
        logger.info("-" * 50)
        logger.info(f"NAT探测结果:")
        logger.info(f"  内网地址:  {nat_info.internal_ip}:{nat_info.internal_port}")
        logger.info(f"  外网地址:  {nat_info.external_ip}:{nat_info.external_port}")
        logger.info(f"  NAT类型:   {nat_info.nat_type.value}")
        logger.info(f"  UPnP可用:  {'是' if nat_info.upnp_available else '否'}")
        logger.info(f"  公网可达:  {'是' if nat_info.public_reachable else '否'}")

        # 推荐穿透方案
        if not nat_info.public_reachable:
            logger.info(f"  推荐方案:  直连 (无需穿透)")
        elif nat_info.upnp_available:
            logger.info(f"  推荐方案:  UPnP自动端口转发")
        elif nat_info.nat_type in (NatType.FULL_CONE, NatType.RESTRICTED_CONE,
                                    NatType.PORT_RESTRICTED_CONE):
            logger.info(f"  推荐方案:  UDP打洞")
        elif nat_info.nat_type == NatType.SYMMETRIC:
            logger.info(f"  推荐方案:  TURN中继 (对称NAT)")
        else:
            logger.info(f"  推荐方案:  中继")

        logger.info("-" * 50)

        return nat_info

    def setup_inbound(self, local_port: int) -> Tuple[str, int, str]:
        """
        设置入站连接能力

        尝试顺序:
        1. UPnP自动端口转发
        2. 使用STUN发现的外部地址

        Args:
            local_port: 需要转发的本地端口

        Returns:
            (external_ip, external_port, method)
        """
        # 尝试UPnP
        if self.nat_info and self.nat_info.upnp_available:
            ext_port = self.upnp.add_port_mapping(local_port, "TCP", "servermodel-node")
            if ext_port:
                ext_ip = self.upnp.get_external_ip() or ""
                self.connection_method = "upnp"
                self.upnp_success += 1
                logger.info(f"入站设置成功 (UPnP): {ext_ip}:{ext_port}")
                return (ext_ip, ext_port, "upnp")

        # 使用STUN发现的地址
        if self.nat_info and self.nat_info.external_ip:
            # 对于Full Cone NAT,外部地址是固定可用的
            if self.nat_info.nat_type == NatType.FULL_CONE:
                self.connection_method = "stun"
                logger.info(f"入站设置成功 (STUN): {self.nat_info.external_ip}:{self.nat_info.external_port}")
                return (self.nat_info.external_ip, self.nat_info.external_port, "stun")

        # 无法设置入站
        return ("", 0, "none")

    def establish_connection(self, target_ip: str, target_port: int,
                             target_node_id: str = "",
                             local_port: int = 0,
                             timeout: float = 5.0) -> Tuple[str, Any]:
        """
        建立到目标节点的连接 (多层回退)

        Args:
            target_ip: 目标IP
            target_port: 目标端口
            target_node_id: 目标节点ID (用于中继)
            local_port: 本地端口
            timeout: 超时

        Returns:
            (method, connection)
            method: "direct" / "upnp" / "hole_punch" / "relay" / "failed"
            connection: socket 或 RelayClient 或 None
        """

        # Layer 1: 直连TCP
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            sock.connect((target_ip, target_port))
            self.connection_method = "direct"
            self.direct_success += 1
            logger.info(f"直连成功: {target_ip}:{target_port}")
            return ("direct", sock)
        except Exception:
            pass  # 直连失败,尝试下一层

        # Layer 2: UPnP (如果目标也在UPnP后面,直连可能仍然有效,
        #           这里UPnP主要用于设置自己的入站,让目标能连过来)
        # UPnP通常不需要在出站连接时特殊处理

        # Layer 3: UDP打洞 (需要STUN信息)
        if (self.nat_info and self.nat_info.nat_type in
                (NatType.FULL_CONE, NatType.RESTRICTED_CONE,
                 NatType.PORT_RESTRICTED_CONE)):

            try:
                if not self.hole_puncher:
                    self.hole_puncher = HolePuncher(self.nat_info)

                success = self.hole_puncher.coordinated_punch(
                    target_ip, target_port, local_port
                )

                if success and self.hole_puncher.punch_socket:
                    self.connection_method = "hole_punch"
                    self.punch_success += 1
                    logger.info(f"UDP打洞成功: {target_ip}:{target_port}")
                    return ("hole_punch", self.hole_puncher.punch_socket)

            except Exception as e:
                logger.debug(f"UDP打洞失败: {e}")

        # Layer 4: TCP中继
        if self.relay_servers and target_node_id:
            for relay_host, relay_port in self.relay_servers:
                try:
                    client = RelayClient(relay_host, relay_port, target_node_id)
                    # 注意: 这里node_id参数应该是本节点的ID
                    if client.connect(timeout):
                        self.relay_client = client
                        self.connection_method = "relay"
                        self.relay_success += 1
                        logger.info(f"中继连接成功: 通过 {relay_host}:{relay_port}")
                        return ("relay", client)
                except Exception as e:
                    logger.debug(f"中继连接失败 {relay_host}:{relay_port}: {e}")

        self.connection_method = "failed"
        logger.warning(f"所有穿透方式失败: {target_ip}:{target_port}")
        return ("failed", None)

    def get_public_address(self) -> Tuple[str, int]:
        """
        获取本节点的公网可达地址

        Returns:
            (ip, port)
        """
        if self.nat_info:
            return (self.nat_info.external_ip, self.nat_info.external_port)
        return ("", 0)

    def get_nat_summary(self) -> Dict:
        """获取NAT穿透摘要信息"""
        if not self.discovered:
            return {"status": "not_discovered"}

        return {
            "status": "discovered",
            "nat_info": self.nat_info.to_dict() if self.nat_info else {},
            "connection_method": self.connection_method,
            "upnp_available": self.nat_info.upnp_available if self.nat_info else False,
            "relay_servers": [f"{h}:{p}" for h, p in self.relay_servers],
            "stats": {
                "direct_success": self.direct_success,
                "upnp_success": self.upnp_success,
                "punch_success": self.punch_success,
                "relay_success": self.relay_success,
            }
        }

    def stop(self):
        """停止并清理所有资源"""
        if self.hole_puncher:
            self.hole_puncher.cleanup()
        if self.relay_client:
            self.relay_client.disconnect()
        self.upnp.cleanup()


# ==================== 工具函数 ====================

def _get_local_ip() -> str:
    """获取本机内网IP"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def get_nat_manager(config=None) -> NatTraversalManager:
    """便捷函数: 创建NAT穿透管理器"""
    return NatTraversalManager(config)


# ==================== 自测 ====================

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

    print("=" * 60)
    print("NAT穿透模块自测")
    print("=" * 60)

    # Test 1: STUN探测
    print("\n[TEST 1] STUN探测")
    client = STUNClient()
    nat_info = client.discover()
    print(f"  NAT类型: {nat_info.nat_type.value}")
    print(f"  外网IP: {nat_info.external_ip}")
    print(f"  外网端口: {nat_info.external_port}")
    print(f"  内网IP: {nat_info.internal_ip}")

    # Test 2: UPnP
    print("\n[TEST 2] UPnP探测")
    upnp = UPnPManager()
    upnp_ok = upnp.discover()
    print(f"  UPnP可用: {upnp_ok}")
    if upnp_ok:
        print(f"  外网IP: {upnp.get_external_ip()}")

    # Test 3: 完整探测
    print("\n[TEST 3] 完整NAT探测")
    manager = NatTraversalManager()
    info = manager.discover()
    print(f"  结果: {json.dumps(info.to_dict(), indent=2, ensure_ascii=False)}")

    # Test 4: 入站设置
    print("\n[TEST 4] 入站连接设置")
    ext_ip, ext_port, method = manager.setup_inbound(5000)
    print(f"  方法: {method}")
    print(f"  外网地址: {ext_ip}:{ext_port}")

    # Test 5: 中继服务器 (简单测试)
    print("\n[TEST 5] 中继服务器创建测试")
    relay = RelayServer("127.0.0.1", 16000)
    relay.start()
    time.sleep(0.5)
    relay.stop()
    print("  中继服务器启动/停止成功")

    # Test 6: 中继客户端
    print("\n[TEST 6] 中继客户端创建测试")
    rclient = RelayClient("127.0.0.1", 16001, "test-node-001")
    print(f"  中继客户端创建成功")

    # Test 7: 直连测试
    print("\n[TEST 7] 直连测试")
    method, conn = manager.establish_connection("127.0.0.1", 80)
    print(f"  方法: {method}")
    if conn:
        try:
            conn.close()
        except Exception:
            pass

    print("\n" + "=" * 60)
    print("NAT穿透模块自测完成!")
    print("=" * 60)

    # 清理
    manager.stop()
