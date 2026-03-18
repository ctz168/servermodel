#!/usr/bin/env python3
"""
快速测试脚本 - 测试 API 是否正常工作

使用方法:
    python test_api.py
"""

import requests
import json
import time
import sys

# API 地址
API_URL = "http://localhost:8080"

def print_header(title):
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)

def print_result(success, message):
    if success:
        print(f"✅ {message}")
    else:
        print(f"❌ {message}")

def test_health():
    """测试健康检查"""
    print_header("测试 1: 健康检查")
    try:
        response = requests.get(f"{API_URL}/health", timeout=5)
        data = response.json()
        
        if data.get("status") == "healthy":
            print_result(True, f"服务状态: {data['status']}")
            print_result(True, f"健康分数: {data.get('health_score', 0):.1f}")
            print_result(True, f"模型已加载: {data.get('model_loaded', False)}")
            return True
        else:
            print_result(False, f"服务状态异常: {data}")
            return False
    except Exception as e:
        print_result(False, f"请求失败: {e}")
        return False

def test_status():
    """测试状态接口"""
    print_header("测试 2: 状态接口")
    try:
        response = requests.get(f"{API_URL}/status", timeout=5)
        data = response.json()
        
        print_result(True, f"节点 ID: {data.get('node', {}).get('node_id', 'N/A')[:8]}")
        print_result(True, f"节点名称: {data.get('node', {}).get('node_name', 'N/A')}")
        print_result(True, f"角色: {data.get('election', {}).get('role', 'N/A')}")
        print_result(True, f"模型: {data.get('model', {}).get('model_name', 'N/A')}")
        print_result(True, f"设备: {data.get('model', {}).get('device', 'N/A')}")
        return True
    except Exception as e:
        print_result(False, f"请求失败: {e}")
        return False

def test_models():
    """测试模型列表"""
    print_header("测试 3: 模型列表")
    try:
        response = requests.get(f"{API_URL}/v1/models", timeout=5)
        data = response.json()
        
        models = data.get("models", [])
        print_result(True, f"可用模型数量: {len(models)}")
        for model in models:
            print(f"   - {model.get('id', 'N/A')}")
        return True
    except Exception as e:
        print_result(False, f"请求失败: {e}")
        return False

def test_chat():
    """测试聊天补全"""
    print_header("测试 4: 聊天补全")
    try:
        print("发送请求: '你好，请介绍一下自己'")
        
        start_time = time.time()
        response = requests.post(
            f"{API_URL}/v1/chat/completions",
            json={
                "model": "Qwen/Qwen2.5-0.5B-Instruct",
                "messages": [
                    {"role": "user", "content": "你好，请用一句话介绍自己"}
                ],
                "max_tokens": 50,
                "temperature": 0.7
            },
            timeout=60
        )
        latency = time.time() - start_time
        
        data = response.json()
        
        if "choices" in data and len(data["choices"]) > 0:
            content = data["choices"][0]["message"]["content"]
            tokens = data.get("usage", {}).get("completion_tokens", 0)
            
            print_result(True, f"响应: {content}")
            print_result(True, f"Token 数: {tokens}")
            print_result(True, f"延迟: {latency:.2f}s")
            print_result(True, f"吞吐量: {tokens/latency:.1f} tokens/s")
            return True
        else:
            print_result(False, f"响应格式错误: {data}")
            return False
    except Exception as e:
        print_result(False, f"请求失败: {e}")
        return False

def test_completion():
    """测试文本补全"""
    print_header("测试 5: 文本补全")
    try:
        print("发送请求: '人工智能是'")
        
        start_time = time.time()
        response = requests.post(
            f"{API_URL}/v1/completions",
            json={
                "model": "Qwen/Qwen2.5-0.5B-Instruct",
                "prompt": "人工智能是",
                "max_tokens": 30,
                "temperature": 0.7
            },
            timeout=60
        )
        latency = time.time() - start_time
        
        data = response.json()
        
        if "choices" in data and len(data["choices"]) > 0:
            content = data["choices"][0]["text"]
            tokens = data.get("usage", {}).get("completion_tokens", 0)
            
            print_result(True, f"响应: 人工智能是{content}")
            print_result(True, f"Token 数: {tokens}")
            print_result(True, f"延迟: {latency:.2f}s")
            return True
        else:
            print_result(False, f"响应格式错误: {data}")
            return False
    except Exception as e:
        print_result(False, f"请求失败: {e}")
        return False

def main():
    print("\n" + "=" * 60)
    print("  统一分布式推理系统 - API 测试")
    print("=" * 60)
    print(f"\nAPI 地址: {API_URL}")
    
    results = []
    
    # 运行测试
    results.append(("健康检查", test_health()))
    results.append(("状态接口", test_status()))
    results.append(("模型列表", test_models()))
    results.append(("聊天补全", test_chat()))
    results.append(("文本补全", test_completion()))
    
    # 汇总结果
    print_header("测试结果汇总")
    
    passed = sum(1 for _, r in results if r)
    total = len(results)
    
    for name, result in results:
        print_result(result, name)
    
    print(f"\n通过: {passed}/{total}")
    
    if passed == total:
        print("\n🎉 所有测试通过!")
        return 0
    else:
        print("\n⚠️ 部分测试失败")
        return 1

if __name__ == "__main__":
    sys.exit(main())
