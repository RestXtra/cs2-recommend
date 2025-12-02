# -*- coding: utf-8 -*-
"""测试 SteamDT API 分类筛选参数"""
import requests
import time
import json
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from utils.config import get_env

API_URL = "https://api.steamdt.com/skin/market/v3/page"

def get_headers():
    access_token = get_env('STEAMDT_ACCESS_TOKEN', '56c6dbe5-e5c7-434c-98d9-6d32e465422d')
    device_id = get_env('STEAMDT_DEVICE_ID', 'a7c322ee-206f-4430-9178-9e1f6f87a70a')
    
    return {
        "accept": "application/json",
        "accept-language": "zh-CN,zh;q=0.9",
        "access-token": access_token,
        "content-type": "application/json",
        "language": "zh_CN",
        "origin": "https://steamdt.com",
        "referer": "https://steamdt.com/",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "x-currency": "CNY",
        "x-device-id": device_id
    }

def test_api_with_filter(filter_params, description):
    """测试带筛选参数的API"""
    print(f"\n{'='*60}")
    print(f"测试: {description}")
    print(f"参数: {json.dumps(filter_params, ensure_ascii=False, indent=2)}")
    
    timestamp = int(time.time() * 1000)
    
    # 基础请求参数
    payload = {
        "dataField": "pvNums",
        "dataRange": "",
        "sortType": "desc",
        "nextId": "",
        "queryName": "",
        "pageSize": 10,
        "timestamp": timestamp
    }
    
    # 合并筛选参数
    payload.update(filter_params)
    
    try:
        response = requests.post(API_URL, headers=get_headers(), json=payload, timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            if data.get('success') and data.get('data', {}).get('list'):
                items = data['data']['list']
                total = data['data'].get('total', 0)
                print(f"✓ 成功! 总数: {total}, 返回: {len(items)} 个")
                
                # 显示前3个商品名称
                for i, item in enumerate(items[:3]):
                    print(f"  {i+1}. {item.get('name', 'N/A')}")
                return True
            else:
                print(f"✗ API返回错误或空数据")
                print(f"  响应: {json.dumps(data, ensure_ascii=False)[:200]}")
                return False
        else:
            print(f"✗ HTTP错误: {response.status_code}")
            return False
    except Exception as e:
        print(f"✗ 请求失败: {e}")
        return False

def main():
    print("=" * 60)
    print("SteamDT API 分类筛选测试")
    print("=" * 60)
    
    # 测试各类武器的搜索
    test_cases = [
        # 匕首类
        ("", "全部商品"),
        ("刺刀", "刺刀（应包含M9刺刀和普通刺刀）"),
        ("M9 刺刀", "M9 刺刀"),
        ("蝴蝶刀", "蝴蝶刀"),
        ("爪子刀", "爪子刀"),
        ("★", "带★的（匕首+手套）"),
        
        # 手套类
        ("运动手套", "运动手套"),
        ("手套", "所有手套"),
        
        # 步枪类
        ("AK-47", "AK-47"),
        ("AWP", "AWP"),
        ("M4A1", "M4A1（包含消音版）"),
        
        # 手枪类
        ("沙漠之鹰", "沙漠之鹰"),
        ("格洛克", "格洛克"),
        ("USP", "USP"),
        
        # 其他
        ("印花", "印花"),
        ("武器箱", "武器箱"),
        ("探员", "探员"),
    ]
    
    for query, desc in test_cases:
        test_api_with_filter({"queryName": query}, f"queryName='{query}' ({desc})")
        time.sleep(0.8)
    
    print("\n" + "=" * 60)
    print("测试完成!")
    print("=" * 60)

if __name__ == "__main__":
    main()
