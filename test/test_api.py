#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""API 功能测试"""

import requests
import sys

API_BASE = "http://localhost:8080"

def test_health():
    try:
        r = requests.get(f"{API_BASE}/health", timeout=5)
        return r.status_code == 200
    except:
        return False

def test_status():
    try:
        r = requests.get(f"{API_BASE}/status", timeout=5)
        return r.status_code == 200
    except:
        return False

def test_models():
    try:
        r = requests.get(f"{API_BASE}/v1/models", timeout=5)
        return r.status_code == 200
    except:
        return False

def test_chat():
    try:
        r = requests.post(
            f"{API_BASE}/v1/chat/completions",
            json={
                "model": "Qwen/Qwen2.5-0.5B-Instruct",
                "messages": [{"role": "user", "content": "hi"}],
                "max_tokens": 10
            },
            timeout=30
        )
        return r.status_code == 200
    except:
        return False

def test_completion():
    try:
        r = requests.post(
            f"{API_BASE}/v1/completions",
            json={
                "model": "Qwen/Qwen2.5-0.5B-Instruct",
                "prompt": "AI is",
                "max_tokens": 10
            },
            timeout=30
        )
        return r.status_code == 200
    except:
        return False

def main():
    print("\n=== API 功能测试 ===\n")
    
    tests = [
        ("健康检查", test_health),
        ("状态查询", test_status),
        ("模型列表", test_models),
        ("聊天补全", test_chat),
        ("文本补全", test_completion),
    ]
    
    passed = 0
    for name, func in tests:
        result = func()
        status = "PASS" if result else "FAIL"
        print(f"[{status}] {name}")
        if result:
            passed += 1
    
    print(f"\n总计: {passed}/{len(tests)} 通过")
    return passed == len(tests)

if __name__ == "__main__":
    sys.exit(0 if main() else 1)
