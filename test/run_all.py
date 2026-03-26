#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""运行所有测试"""

import subprocess
import sys
import os

TEST_DIR = os.path.dirname(os.path.abspath(__file__))

def run_all():
    print("\n" + "="*60)
    print("  运行所有测试")
    print("="*60 + "\n")
    
    tests = [
        ("API 测试", "test_api.py"),
        ("快速测试", "quick_test.py"),
    ]
    
    results = []
    for name, script in tests:
        print(f"\n>>> {name}")
        script_path = os.path.join(TEST_DIR, script)
        result = subprocess.run([sys.executable, script_path], cwd=TEST_DIR)
        results.append((name, result.returncode == 0))
    
    print("\n" + "="*60)
    print("  测试汇总")
    print("="*60)
    for name, passed in results:
        status = "PASS" if passed else "FAIL"
        print(f"  {name}: {status}")
    
    total = len(results)
    passed = sum(1 for _, r in results if r)
    print(f"\n总计: {passed}/{total} 通过")
    
    return passed == total

if __name__ == "__main__":
    sys.exit(0 if run_all() else 1)
