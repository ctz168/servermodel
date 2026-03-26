#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""快速测试"""

import requests
import sys

API_BASE = "http://localhost:8080"

def quick_test():
    print("快速测试...\n")
    
    # 健康检查
    try:
        r = requests.get(f"{API_BASE}/health", timeout=5)
        print(f"[1] 健康检查: {'OK' if r.status_code == 200 else 'FAIL'}")
    except Exception as e:
        print(f"[1] 健康检查: FAIL - {e}")
        return False
    
    # 聊天测试
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
        if r.status_code == 200:
            content = r.json()['choices'][0]['message']['content']
            print(f"[2] 聊天补全: OK - {content[:30]}...")
        else:
            print(f"[2] 聊天补全: FAIL - HTTP {r.status_code}")
            return False
    except Exception as e:
        print(f"[2] 聊天补全: FAIL - {e}")
        return False
    
    print("\n测试通过!")
    return True

if __name__ == "__main__":
    sys.exit(0 if quick_test() else 1)
