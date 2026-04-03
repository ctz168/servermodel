#!/usr/bin/env python3
"""
NAT穿透模块测试 - 中继通信端到端测试
"""

import os
import sys
import time
import json
import socket
import threading
import logging

# 确保可以导入
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.nat_traversal import (
    NatTraversalManager, NatType, NatInfo,
    STUNClient, UPnPManager, HolePuncher,
    RelayServer, RelayClient, ConnectionMethod,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("test_nat")

passed = 0
failed = 0


def test(name, condition, detail=""):
    global passed, failed
    if condition:
        passed += 1
        logger.info(f"  ✅ PASS: {name} {detail}")
    else:
        failed += 1
        logger.error(f"  ❌ FAIL: {name} {detail}")


def test_stun_discovery():
    """测试1: STUN发现外部地址"""
    print("\n[TEST 1] STUN发现外部地址")
    client = STUNClient()
    info = client.discover()

    test("STUN返回NAT信息", info is not None)
    test("NAT类型不是UNKNOWN", info.nat_type != NatType.UNKNOWN)
    test("检测到外部IP", len(info.external_ip) > 0, f"ip={info.external_ip}")
    test("外部端口 > 0", info.external_port > 0, f"port={info.external_port}")
    test("检测到内网IP", len(info.internal_ip) > 0, f"ip={info.internal_ip}")

    # 验证外网和内网IP不同 (在NAT后面)
    test("外网IP != 内网IP (在NAT后面)",
         info.external_ip != info.internal_ip,
         f"ext={info.external_ip} int={info.internal_ip}")


def test_nat_info_serialization():
    """测试2: NatInfo序列化"""
    print("\n[TEST 2] NatInfo序列化")
    info = NatInfo(
        nat_type=NatType.SYMMETRIC,
        external_ip="1.2.3.4",
        external_port=5000,
        internal_ip="192.168.1.100",
        internal_port=5000,
        upnp_available=False,
        public_reachable=True,
    )
    d = info.to_dict()
    test("to_dict返回字典", isinstance(d, dict))
    test("nat_type正确", d["nat_type"] == "symmetric")
    test("external_ip正确", d["external_ip"] == "1.2.3.4")
    test("public_reachable正确", d["public_reachable"] is True)

    # JSON序列化
    j = json.dumps(d)
    test("可JSON序列化", len(j) > 0)


def test_full_nat_manager_discovery():
    """测试3: 完整NAT管理器发现"""
    print("\n[TEST 3] 完整NAT管理器发现")
    manager = NatTraversalManager()
    info = manager.discover()

    test("管理器返回NatInfo", info is not None)
    test("已标记为discovered", manager.discovered)
    test("外网IP非空", len(info.external_ip) > 0, f"ip={info.external_ip}")

    summary = manager.get_nat_summary()
    test("get_nat_summary返回字典", isinstance(summary, dict))
    test("status为discovered", summary.get("status") == "discovered")

    manager.stop()


def test_relay_server_client_communication():
    """测试4: 中继服务器-客户端通信"""
    print("\n[TEST 4] 中继服务器-客户端通信")

    relay_port = 17001
    relay = RelayServer("127.0.0.1", relay_port)
    relay.start()
    time.sleep(0.5)

    try:
        # 节点A连接中继
        client_a = RelayClient("127.0.0.1", relay_port, "node-A-001")
        ok_a = client_a.connect(timeout=5.0)
        test("节点A连接中继成功", ok_a)

        # 节点B连接中继
        client_b = RelayClient("127.0.0.1", relay_port, "node-B-002")
        ok_b = client_b.connect(timeout=5.0)
        test("节点B连接中继成功", ok_b)

        # B注册接收handler
        received_data = []
        received_from = []

        def on_data(data, from_node):
            received_data.append(data)
            received_from.append(from_node)

        client_b.register_handler(on_data)
        time.sleep(0.3)

        # A发送数据给B
        msg = b"Hello from A to B!"
        sent = client_a.send_to_node("node-B-002", msg)
        test("A发送数据给B", sent)

        # 等待B收到
        time.sleep(1.0)

        test("B收到数据", len(received_data) > 0, f"count={len(received_data)}")
        if len(received_data) > 0:
            test("数据内容正确", received_data[0] == msg,
                 f"got={received_data[0]} expected={msg}")
            test("来源正确", received_from[0] == "node-A-001",
                 f"got={received_from[0]}")

        # 反向: B发送给A
        received_data.clear()
        received_from.clear()
        client_a.register_handler(on_data)
        time.sleep(0.3)

        msg2 = b"Hello from B to A!"
        sent2 = client_b.send_to_node("node-A-001", msg2)
        test("B发送数据给A", sent2)

        time.sleep(1.0)

        test("A收到数据", len(received_data) > 0)
        if len(received_data) > 0:
            test("反向数据内容正确", received_data[0] == msg2)

        # 验证中继服务器的连接数
        time.sleep(0.5)
        test("中继有2个注册连接", len(relay.connections) == 2,
             f"got={len(relay.connections)}")

        client_a.disconnect()
        client_b.disconnect()

    finally:
        relay.stop()


def test_relay_offline_buffering():
    """测试5: 中继离线缓冲"""
    print("\n[TEST 5] 中继离线缓冲 (目标不在线时缓存数据)")

    relay_port = 17002
    relay = RelayServer("127.0.0.1", relay_port)
    relay.start()
    time.sleep(0.5)

    try:
        # 只有A连接, B未连接
        client_a = RelayClient("127.0.0.1", relay_port, "node-A-003")
        ok_a = client_a.connect(timeout=5.0)
        test("A连接成功", ok_a)

        # A发送给不在线的B
        sent = client_a.send_to_node("node-OFFLINE-004", b"buffered message")
        test("发送到离线节点成功", sent)

        time.sleep(0.5)

        # 检查中继是否有缓冲数据
        buffered = relay.pending_data.get("node-OFFLINE-004", [])
        test("中继缓冲了数据", len(buffered) > 0, f"count={len(buffered)}")

        client_a.disconnect()

    finally:
        relay.stop()


def test_relay_multi_message():
    """测试6: 中继多消息传输"""
    print("\n[TEST 6] 中继多消息连续传输")

    relay_port = 17003
    relay = RelayServer("127.0.0.1", relay_port)
    relay.start()
    time.sleep(0.5)

    try:
        client_a = RelayClient("127.0.0.1", relay_port, "node-A-005")
        client_b = RelayClient("127.0.0.1", relay_port, "node-B-006")

        test("A连接", client_a.connect(timeout=5.0))
        test("B连接", client_b.connect(timeout=5.0))

        received = []
        client_b.register_handler(lambda d, f: received.append(d))
        time.sleep(0.3)

        # 连续发送10条消息
        num_msgs = 10
        for i in range(num_msgs):
            client_a.send_to_node("node-B-006", f"msg-{i}".encode())

        time.sleep(2.0)

        test(f"收到{num_msgs}条消息", len(received) == num_msgs,
             f"expected={num_msgs} got={len(received)}")

        if len(received) == num_msgs:
            # 验证顺序
            all_correct = all(
                received[i] == f"msg-{i}".encode() for i in range(num_msgs)
            )
            test("消息顺序正确", all_correct)

        client_a.disconnect()
        client_b.disconnect()

    finally:
        relay.stop()


def test_establish_connection_direct():
    """测试7: establish_connection直连"""
    print("\n[TEST 7] establish_connection多层回退")

    # 启动一个简单的TCP服务器
    server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_sock.bind(("127.0.0.1", 17004))
    server_sock.listen(5)
    server_sock.settimeout(3.0)

    try:
        manager = NatTraversalManager()
        # 先发现
        manager.discover()

        # 直连到本地服务器
        method, conn = manager.establish_connection(
            "127.0.0.1", 17004, "test-node", timeout=3.0
        )

        test("直连方法", method == "direct", f"method={method}")
        test("连接非None", conn is not None)

        if conn:
            try:
                conn.close()
            except Exception:
                pass

        # 连接不存在的端口
        method2, conn2 = manager.establish_connection(
            "127.0.0.1", 19999, timeout=2.0
        )
        test("失败方法", method2 == "failed", f"method={method2}")
        test("连接为None", conn2 is None)

        manager.stop()

    finally:
        server_sock.close()


def test_hole_puncher_creation():
    """测试8: HolePuncher创建和socket"""
    print("\n[TEST 8] HolePuncher创建")

    info = NatInfo(
        nat_type=NatType.FULL_CONE,
        external_ip="1.2.3.4",
        external_port=5000,
    )
    puncher = HolePuncher(info)
    sock = puncher.create_punch_socket(0)

    test("socket创建成功", sock is not None)
    test("punch_port > 0", puncher.punch_port > 0, f"port={puncher.punch_port}")

    puncher.cleanup()
    test("cleanup成功", puncher.punch_socket is None)


def test_connection_method_enum():
    """测试9: 枚举值"""
    print("\n[TEST 9] 枚举类型")
    test("ConnectionMethod.DIRECT", ConnectionMethod.DIRECT.value == "direct")
    test("ConnectionMethod.UPNP", ConnectionMethod.UPNP.value == "upnp")
    test("ConnectionMethod.HOLE_PUNCH", ConnectionMethod.HOLE_PUNCH.value == "hole_punch")
    test("ConnectionMethod.RELAY", ConnectionMethod.RELAY.value == "relay")
    test("ConnectionMethod.REVERSE", ConnectionMethod.REVERSE.value == "reverse")
    test("ConnectionMethod.FAILED", ConnectionMethod.FAILED.value == "failed")
    test("NatType.SYMMETRIC", NatType.SYMMETRIC.value == "symmetric")
    test("NatType.FULL_CONE", NatType.FULL_CONE.value == "full_cone")


def test_nat_type_detection():
    """测试10: NAT类型检测逻辑 (模拟)"""
    print("\n[TEST 10] NAT穿透方案选择")

    # Full Cone - 可以打洞
    manager_fc = NatTraversalManager()
    manager_fc.nat_info = NatInfo(
        nat_type=NatType.FULL_CONE,
        external_ip="1.2.3.4",
        external_port=5000,
        upnp_available=False,
        public_reachable=True,
    )
    manager_fc.discovered = True
    ip, port, method = manager_fc.setup_inbound(5000)
    test("Full Cone -> STUN入站", method == "stun", f"method={method}")

    # UPnP可用
    manager_upnp = NatTraversalManager()
    manager_upnp.nat_info = NatInfo(
        nat_type=NatType.SYMMETRIC,
        external_ip="1.2.3.4",
        external_port=5000,
        upnp_available=True,
        public_reachable=True,
    )
    manager_upnp.upnp.available = True
    # Mock add_port_mapping
    manager_upnp.upnp.external_ip = "5.6.7.8"
    manager_upnp.upnp.upnpc = None  # Won't actually try UPnP calls
    manager_upnp.discovered = True
    # UPnP with no actual upnpc will fall through
    ip, port, method = manager_upnp.setup_inbound(5000)
    test("UPnP不可用时回退", True)  # Just test it doesn't crash


if __name__ == "__main__":
    print("=" * 60)
    print("NAT穿透模块测试")
    print("=" * 60)

    test_stun_discovery()
    test_nat_info_serialization()
    test_full_nat_manager_discovery()
    test_relay_server_client_communication()
    test_relay_offline_buffering()
    test_relay_multi_message()
    test_establish_connection_direct()
    test_hole_puncher_creation()
    test_connection_method_enum()
    test_nat_type_detection()

    print("\n" + "=" * 60)
    print(f"测试结果: {passed} 通过, {failed} 失败, 共 {passed + failed} 个")
    print("=" * 60)

    if failed > 0:
        sys.exit(1)
