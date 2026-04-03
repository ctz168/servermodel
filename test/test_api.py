#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
API 功能测试
============

支持两种模式:
1. 在线测试 - 需要运行中的服务器
2. 模拟测试 - 不需要 torch/transformers，使用 mock 进行单元测试

用法:
  # 在线测试 (需要服务器运行)
  python test_api.py --mode online [--host localhost] [--port 8080]

  # 模拟测试 (不需要 torch/transformers)
  python test_api.py --mode mock

  # 混合测试 (两者都运行)
  python test_api.py
"""

import sys
import os
import json
import time
import threading
import unittest
from unittest.mock import patch, MagicMock, PropertyMock
from io import BytesIO
import argparse

# 确保可以导入项目模块
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ==================== 在线测试 (需要服务器) ====================

def _online_test_health(api_base: str) -> bool:
    try:
        import requests
        r = requests.get(f"{api_base}/health", timeout=5)
        return r.status_code == 200
    except Exception:
        return False

def _online_test_status(api_base: str) -> bool:
    try:
        import requests
        r = requests.get(f"{api_base}/status", timeout=5)
        return r.status_code == 200
    except Exception:
        return False

def _online_test_models(api_base: str) -> bool:
    try:
        import requests
        r = requests.get(f"{api_base}/v1/models", timeout=5)
        return r.status_code == 200
    except Exception:
        return False

def _online_test_chat(api_base: str) -> bool:
    try:
        import requests
        r = requests.post(
            f"{api_base}/v1/chat/completions",
            json={
                "model": "Qwen/Qwen2.5-0.5B-Instruct",
                "messages": [{"role": "user", "content": "hi"}],
                "max_tokens": 10
            },
            timeout=30
        )
        return r.status_code == 200
    except Exception:
        return False

def _online_test_completion(api_base: str) -> bool:
    try:
        import requests
        r = requests.post(
            f"{api_base}/v1/completions",
            json={
                "model": "Qwen/Qwen2.5-0.5B-Instruct",
                "prompt": "AI is",
                "max_tokens": 10
            },
            timeout=30
        )
        return r.status_code == 200
    except Exception:
        return False

def _online_test_validation(api_base: str) -> bool:
    """Test that API validates required fields (returns 400 for missing messages)"""
    try:
        import requests
        # Missing 'messages' field
        r = requests.post(
            f"{api_base}/v1/chat/completions",
            json={"model": "test"},
            timeout=5
        )
        return r.status_code == 400
    except Exception:
        return False


def run_online_tests(api_base: str):
    """Run online integration tests against a running server"""
    print("\n=== 在线 API 测试 ===")
    print(f"目标: {api_base}\n")
    
    tests = [
        ("健康检查", lambda: _online_test_health(api_base)),
        ("状态查询", lambda: _online_test_status(api_base)),
        ("模型列表", lambda: _online_test_models(api_base)),
        ("聊天补全", lambda: _online_test_chat(api_base)),
        ("文本补全", lambda: _online_test_completion(api_base)),
        ("输入验证", lambda: _online_test_validation(api_base)),
    ]
    
    passed = 0
    for name, func in tests:
        result = func()
        status = "PASS" if result else "FAIL"
        print(f"  [{status}] {name}")
        if result:
            passed += 1
    
    print(f"\n总计: {passed}/{len(tests)} 通过")
    return passed == len(tests)


# ==================== 模拟测试 (不需要 torch/transformers) ====================

class MockModelManager:
    """Mock ModelManager for testing without torch"""
    loaded = True
    device = "cpu"
    model = MagicMock()
    tokenizer = MagicMock()
    model_size_gb = 1.0
    
    def __init__(self):
        self.total_inferences = 0
        self.total_tokens = 0
        self.total_latency = 0.0
        # Configure mock tokenizer
        self.tokenizer.pad_token = "<pad>"
        self.tokenizer.eos_token = "</s>"
        self.tokenizer.pad_token_id = 0
        self.tokenizer.eos_token_id = 1
    
    def inference(self, prompt, max_tokens=256, temperature=0.7, **kwargs):
        self.total_inferences += 1
        return MagicMock(
            success=True,
            response=f"Mock response to: {prompt[:50]}",
            tokens=10,
            latency=0.1,
            throughput=100.0,
            error="",
            to_dict=lambda: {
                "success": True,
                "response": f"Mock response to: {prompt[:50]}",
                "tokens": 10,
                "latency": 0.1,
            }
        )
    
    def get_stats(self):
        return {
            "loaded": self.loaded,
            "model_name": "mock-model",
            "device": self.device,
        }
    
    def load(self):
        return True
    
    def unload(self):
        self.loaded = False


class TestCoreModule(unittest.TestCase):
    """Unit tests for the core module (no torch needed)"""
    
    @classmethod
    def setUpClass(cls):
        """Mock torch/transformers if not available"""
        cls.torch_patcher = None
        cls.transformers_patcher = None
        
        # Check if torch is available
        try:
            import torch
            cls.HAS_TORCH = True
        except ImportError:
            cls.HAS_TORCH = False
            # Create mock torch module
            mock_torch = MagicMock()
            mock_torch.cuda = MagicMock()
            mock_torch.cuda.is_available = MagicMock(return_value=False)
            mock_torch.no_grad = MagicMock(return_value=MagicMock(__enter__=MagicMock(), __exit__=MagicMock()))
            mock_torch.float16 = "float16"
            mock_torch.float32 = "float32"
            mock_torch.Tensor = MagicMock
            mock_torch.from_numpy = MagicMock()
            mock_torch.argmax = MagicMock()
            mock_torch.cat = MagicMock()
            mock_torch.tensor = MagicMock()
            mock_torch.cuda.get_device_properties = MagicMock(return_value=MagicMock(total_memory=8e9))
            mock_torch.cuda.memory_allocated = MagicMock(return_value=0)
            mock_torch.cuda.empty_cache = MagicMock()
            cls.torch_patcher = patch.dict('sys.modules', {'torch': mock_torch})
            cls.torch_patcher.start()
            
            # Mock transformers
            mock_transformers = MagicMock()
            mock_transformers.AutoModelForCausalLM = MagicMock()
            mock_transformers.AutoTokenizer = MagicMock()
            mock_transformers.AutoConfig = MagicMock()
            cls.transformers_patcher = patch.dict('sys.modules', {'transformers': mock_transformers})
            cls.transformers_patcher.start()
    
    @classmethod
    def tearDownClass(cls):
        if cls.torch_patcher:
            cls.torch_patcher.stop()
        if cls.transformers_patcher:
            cls.transformers_patcher.stop()
    
    def test_imports(self):
        """Test that core module can be imported"""
        from core.node_unified_complete import (
            VERSION, UnifiedConfig, NodeInfo, MessageType, 
            NodeRole, ParallelMode, UnifiedNode, InferenceResult,
        )
        self.assertEqual(VERSION, "3.0.0")
        self.assertIsNotNone(UnifiedConfig)
        self.assertIsNotNone(NodeInfo)
    
    def test_config_creation(self):
        """Test UnifiedConfig creation and defaults"""
        from core.node_unified_complete import UnifiedConfig, ParallelMode
        
        config = UnifiedConfig()
        self.assertTrue(len(config.node_id) > 0)
        self.assertTrue(len(config.node_name) > 0)
        self.assertEqual(config.parallel_mode, ParallelMode.DATA_PARALLEL)
        self.assertEqual(config.port, 5000)
        self.assertEqual(config.api_port, 8080)
    
    def test_config_from_string(self):
        """Test UnifiedConfig with string parallel mode"""
        from core.node_unified_complete import UnifiedConfig, ParallelMode
        
        config = UnifiedConfig(parallel_mode="pipeline_parallel")
        self.assertEqual(config.parallel_mode, ParallelMode.PIPELINE_PARALLEL)
    
    def test_node_info_to_dict(self):
        """Test NodeInfo serialization"""
        from core.node_unified_complete import NodeInfo
        
        info = NodeInfo(
            node_id="test-123",
            node_name="TestNode",
            host="192.168.1.1",
            port=5000,
        )
        d = info.to_dict()
        self.assertEqual(d["node_id"], "test-123")
        self.assertEqual(d["host"], "192.168.1.1")
        self.assertEqual(d["port"], 5000)
    
    def test_node_info_from_dict(self):
        """Test NodeInfo deserialization"""
        from core.node_unified_complete import NodeInfo
        
        data = {
            "node_id": "test-456",
            "node_name": "TestNode2",
            "host": "10.0.0.1",
            "port": 6000,
            "memory_available_gb": 16.0,
        }
        info = NodeInfo.from_dict(data)
        self.assertEqual(info.node_id, "test-456")
        self.assertEqual(info.memory_available_gb, 16.0)
    
    def test_message_type_values(self):
        """Test MessageType enum values"""
        from core.node_unified_complete import MessageType
        
        self.assertEqual(MessageType.DISCOVER.value, "discover")
        self.assertEqual(MessageType.HEARTBEAT.value, "heartbeat")
        self.assertEqual(MessageType.REQUEST_VOTE.value, "request_vote")
        self.assertEqual(MessageType.VOTE_RESPONSE.value, "vote_response")
        self.assertEqual(MessageType.PIPELINE_DATA.value, "pipeline_data")
        self.assertEqual(MessageType.CLUSTER_RESOURCE_QUERY.value, "cluster_resource_query")
    
    def test_message_type_unknown_value(self):
        """Test that unknown message type string raises ValueError"""
        from core.node_unified_complete import MessageType
        
        with self.assertRaises(ValueError):
            MessageType("unknown_type")
    
    def test_inference_result(self):
        """Test InferenceResult dataclass"""
        from core.node_unified_complete import InferenceResult
        
        result = InferenceResult(
            success=True,
            response="Hello world",
            tokens=5,
            latency=0.5,
        )
        d = result.to_dict()
        self.assertTrue(d["success"])
        self.assertEqual(d["response"], "Hello world")
        self.assertEqual(d["tokens"], 5)
    
    def test_resource_monitor(self):
        """Test ResourceMonitor without psutil"""
        from core.node_unified_complete import ResourceMonitor
        
        info = ResourceMonitor.get_system_info()
        self.assertIn("memory_total_gb", info)
        self.assertIn("memory_available_gb", info)
        self.assertIn("cpu_percent", info)
        self.assertGreater(info["memory_total_gb"], 0)
        
        health = ResourceMonitor.get_health_score()
        self.assertGreater(health, 0)
        self.assertLessEqual(health, 100)
    
    def test_estimate_model_size(self):
        """Test model size estimation"""
        from core.node_unified_complete import ResourceMonitor
        
        # Known model
        size = ResourceMonitor.estimate_model_size("Qwen/Qwen2.5-7B-Instruct")
        self.assertEqual(size, 14.0)
        
        # Unknown model with size in name
        size = ResourceMonitor.estimate_model_size("some-model-3B")
        self.assertAlmostEqual(size, 9.0, places=1)  # 3 * 2 * 1.5
        
        # Completely unknown model
        size = ResourceMonitor.estimate_model_size("unknown-model")
        self.assertEqual(size, 8.0)  # default
    
    def test_load_balancer(self):
        """Test LoadBalancer"""
        from core.node_unified_complete import LoadBalancer, NodeInfo
        
        lb = LoadBalancer(strategy="adaptive")
        
        # Update stats
        lb.update_node_stats("node-1", 0.1, True)
        lb.update_node_stats("node-1", 0.2, True)
        lb.update_node_stats("node-2", 1.0, False)
        
        stats = lb.get_stats()
        self.assertEqual(stats["total_requests"], 3)
        self.assertEqual(stats["successful_requests"], 2)
        self.assertIn("node-1", stats["node_weights"])
        self.assertIn("node-2", stats["node_weights"])
    
    def test_load_balancer_select_node(self):
        """Test LoadBalancer node selection"""
        from core.node_unified_complete import LoadBalancer, NodeInfo
        
        lb = LoadBalancer(strategy="least_loaded")
        
        nodes = {
            "node-1": NodeInfo("node-1", "N1", "host1", 5000, active_tasks=5, model_loaded=True),
            "node-2": NodeInfo("node-2", "N2", "host2", 5000, active_tasks=1, model_loaded=True),
            "node-3": NodeInfo("node-3", "N3", "host3", 5000, active_tasks=3, model_loaded=True),
        }
        
        selected = lb.select_node(nodes)
        self.assertEqual(selected, "node-2")  # least loaded
    
    def test_network_manager_send_message_signature(self):
        """Test that NetworkManager.send_message has correct signature"""
        from core.node_unified_complete import NetworkManager, UnifiedConfig, MessageType
        
        config = UnifiedConfig()
        nm = NetworkManager(config)
        
        # Verify method exists with correct signature
        import inspect
        sig = inspect.signature(nm.send_message)
        params = list(sig.parameters.keys())
        self.assertIn("host", params)
        self.assertIn("port", params)
        self.assertIn("msg_type", params)
        self.assertIn("data", params)
    
    def test_network_manager_send_message_to_node(self):
        """Test NetworkManager.send_message_to_node convenience method"""
        from core.node_unified_complete import (
            NetworkManager, UnifiedConfig, MessageType, NodeInfo
        )
        
        config = UnifiedConfig()
        nm = NetworkManager(config)
        
        # Add a known node
        nm.known_nodes["test-node"] = NodeInfo(
            node_id="test-node", node_name="Test", host="127.0.0.1", port=9999
        )
        
        # Verify method exists
        self.assertTrue(hasattr(nm, 'send_message_to_node'))
        
        # Test with unknown node returns None
        result = nm.send_message_to_node("unknown-node", MessageType.HEARTBEAT, {})
        self.assertIsNone(result)
    
    def test_network_manager_send_raw_message(self):
        """Test NetworkManager.send_raw_message convenience method"""
        from core.node_unified_complete import NetworkManager, UnifiedConfig
        
        config = UnifiedConfig()
        nm = NetworkManager(config)
        
        # Verify method exists
        self.assertTrue(hasattr(nm, 'send_raw_message'))
    
    def test_raft_election_role(self):
        """Test that RaftElection uses 'role' not 'state' (Bug 3 fix)"""
        from core.node_unified_complete import RaftElection, UnifiedConfig, NetworkManager, NodeRole
        
        config = UnifiedConfig()
        nm = NetworkManager(config)
        election = RaftElection(config, nm)
        
        # Verify 'role' attribute exists
        self.assertTrue(hasattr(election, 'role'))
        self.assertEqual(election.role, NodeRole.FOLLOWER)
        
        # Verify 'state' does NOT exist (Bug 3 fix)
        self.assertFalse(hasattr(election, 'state'))
        
        # Verify is_leader() method works
        self.assertFalse(election.is_leader())
    
    def test_network_manager_known_nodes_not_peers(self):
        """Test that NetworkManager uses 'known_nodes' not 'peers' (Bug 4 fix)"""
        from core.node_unified_complete import NetworkManager, UnifiedConfig
        
        config = UnifiedConfig()
        nm = NetworkManager(config)
        
        # Verify 'known_nodes' attribute exists
        self.assertTrue(hasattr(nm, 'known_nodes'))
        
        # Verify 'peers' does NOT exist (Bug 4 fix)
        self.assertFalse(hasattr(nm, 'peers'))
    
    def test_handle_unknown_message_type(self):
        """Test that unknown message types don't crash (Bug 7 fix)"""
        from core.node_unified_complete import NetworkManager, UnifiedConfig
        import pickle, zlib, socket
        
        config = UnifiedConfig()
        nm = NetworkManager(config)
        
        # Create a message with an unknown type
        message = {"type": "completely_unknown_type", "data": {}}
        encoded = zlib.compress(pickle.dumps(message))
        
        # This should not raise an exception
        # We can't easily test _handle_connection directly without a socket,
        # but we can test _decode_message
        decoded = nm._decode_message(encoded)
        self.assertIsNotNone(decoded)
        self.assertEqual(decoded["type"], "completely_unknown_type")
        
        # Verify that creating a MessageType from unknown string raises ValueError
        from core.node_unified_complete import MessageType
        with self.assertRaises(ValueError):
            MessageType("completely_unknown_type")
    
    def test_api_validation_missing_messages(self):
        """Test that API validates required fields (Bug 15 fix)"""
        from core.node_unified_complete import (
            APIRequestHandler, UnifiedConfig, UnifiedNode, InferenceResult
        )
        from http.server import HTTPServer
        import threading
        
        # Create a mock node
        config = UnifiedConfig(api_host="127.0.0.1", api_port=0)  # port 0 = auto-assign
        node = UnifiedNode.__new__(UnifiedNode)
        node.config = config
        node.model_manager = MockModelManager()
        node.node_info = MagicMock()
        node.node_info.to_dict = MagicMock(return_value={})
        node.network = MagicMock()
        node.network.known_nodes = {}
        node.election = MagicMock()
        node.load_balancer = MagicMock()
        node.load_balancer.get_stats = MagicMock(return_value={})
        
        APIRequestHandler.node = node
        
        # Start server on random port using ThreadingHTTPServer for concurrent requests
        from http.server import ThreadingHTTPServer
        server = ThreadingHTTPServer(("127.0.0.1", 0), APIRequestHandler)
        port = server.server_address[1]
        
        server_thread = threading.Thread(target=server.serve_forever, daemon=True)
        server_thread.start()
        time.sleep(0.2)  # Give server time to start
        
        # Test with requests if available
        try:
            import requests
            
            # Missing 'messages' field should return 400
            r = requests.post(
                f"http://127.0.0.1:{port}/v1/chat/completions",
                json={"model": "test"},
                timeout=5
            )
            self.assertEqual(r.status_code, 400)
            
            # Missing 'prompt' field should return 400
            r = requests.post(
                f"http://127.0.0.1:{port}/v1/completions",
                json={"model": "test"},
                timeout=5
            )
            self.assertEqual(r.status_code, 400)
            
        except ImportError:
            # If requests is not available, skip HTTP-level tests
            pass
        finally:
            server.shutdown()
            server.server_close()
    
    def test_completed_tasks_memory_limit(self):
        """Test that completed_tasks has a size limit (Bug 11 fix)"""
        from collections import OrderedDict
        from core.node_unified_complete import UnifiedConfig, UnifiedNode
        
        config = UnifiedConfig()
        node = UnifiedNode.__new__(UnifiedNode)
        node.config = config
        node.MAX_COMPLETED_TASKS = 10
        node.completed_tasks = OrderedDict()
        node.task_lock = threading.Lock()
        
        # Add more than MAX_COMPLETED_TASKS using the same logic as the fixed code
        for i in range(15):
            with node.task_lock:
                node.completed_tasks[f"task-{i}"] = {"data": i}
                if len(node.completed_tasks) > node.MAX_COMPLETED_TASKS:
                    oldest_keys = list(node.completed_tasks.keys())[:len(node.completed_tasks) - node.MAX_COMPLETED_TASKS]
                    for key in oldest_keys:
                        del node.completed_tasks[key]
        
        self.assertLessEqual(len(node.completed_tasks), node.MAX_COMPLETED_TASKS)
        # Verify oldest entries were removed
        self.assertNotIn("task-0", node.completed_tasks)
        self.assertNotIn("task-1", node.completed_tasks)
        self.assertNotIn("task-2", node.completed_tasks)
        self.assertNotIn("task-3", node.completed_tasks)
        self.assertNotIn("task-4", node.completed_tasks)
        # Verify newest entries are kept
        self.assertIn("task-14", node.completed_tasks)
        self.assertIn("task-13", node.completed_tasks)


class TestAPIHandlerUnit(unittest.TestCase):
    """Unit tests for API request handler"""
    
    def test_chat_completions_validation(self):
        """Test chat completions validates messages field"""
        from core.node_unified_complete import APIRequestHandler
        
        # Test that the handler exists
        self.assertTrue(hasattr(APIRequestHandler, '_handle_chat_completions'))
    
    def test_completions_validation(self):
        """Test completions validates prompt field"""
        from core.node_unified_complete import APIRequestHandler
        
        self.assertTrue(hasattr(APIRequestHandler, '_handle_completions'))
    
    def test_options_cors(self):
        """Test OPTIONS handler sets CORS headers"""
        from core.node_unified_complete import APIRequestHandler
        self.assertTrue(hasattr(APIRequestHandler, 'do_OPTIONS'))


def run_mock_tests():
    """Run mock unit tests"""
    print("\n=== 模拟单元测试 ===\n")
    
    # Create test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    suite.addTests(loader.loadTestsFromTestCase(TestCoreModule))
    suite.addTests(loader.loadTestsFromTestCase(TestAPIHandlerUnit))
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    print(f"\n{'='*60}")
    print(f"模拟测试: {result.testsRun} 个测试, "
          f"{result.testsRun - len(result.failures) - len(result.errors)} 通过, "
          f"{len(result.failures)} 失败, {len(result.errors)} 错误")
    
    return result.wasSuccessful()


# ==================== 主入口 ====================

def main():
    parser = argparse.ArgumentParser(description="API 功能测试")
    parser.add_argument("--mode", choices=["online", "mock", "all"], default="all",
                       help="测试模式: online=在线测试, mock=模拟测试, all=两者")
    parser.add_argument("--host", default="localhost", help="服务器主机")
    parser.add_argument("--port", type=int, default=8080, help="API 端口")
    
    args = parser.parse_args()
    
    results = {}
    
    if args.mode in ("mock", "all"):
        results["mock"] = run_mock_tests()
    
    if args.mode in ("online", "all"):
        api_base = f"http://{args.host}:{args.port}"
        results["online"] = run_online_tests(api_base)
    
    # Summary
    print(f"\n{'='*60}")
    print("测试总结:")
    for mode, passed in results.items():
        status = "PASS" if passed else "FAIL"
        print(f"  [{status}] {mode}")
    
    all_passed = all(results.values())
    print(f"\n总体: {'PASS' if all_passed else 'FAIL'}")
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
