"""从API获取探员列表，然后更新数据库中的分类"""
import sys
sys.path.insert(0, '.')
import requests
import time
from utils.mongo_client import mongo_client

url = 'https://api.steamdt.com/skin/market/v3/page'
headers = {
    'Content-Type': 'application/json',
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Origin': 'https://steamdt.com',
    'Referer': 'https://steamdt.com/',
    'x-currency': 'CNY',
    'x-device': '1'
}

# 使用正确的weaponList参数筛选探员
body = {
    'dataField': 'pvNums',
    'dataRange': '',
    'sortType': 'desc',
    'nextId': '',
    'queryName': '',
    'pageSize': 200,  # 获取更多
    'timestamp': int(time.time() * 1000),
    'exteriorList': [],
    'qualityList': [],
    'rarityList': [],
    'typeList': [],
    'weaponList': [
        'Type_CustomPlayer:customplayer_counter_strike',
        'Type_CustomPlayer:customplayer_terrorist'
    ]
}

print("从API获取探员列表...")
try:
    r = requests.post(url, json=body, headers=headers, timeout=30)
    data = r.json()
    
    if 'data' in data and 'list' in data['data']:
        items = data['data']['list']
        print(f"API返回 {len(items)} 个探员:")
        
        agent_names = []
        for item in items:
            name = item.get('name', '')
            print(f"  - {name}")
            agent_names.append(name)
        
        # 更新数据库
        print(f"\n开始更新数据库中的探员分类...")
        col = mongo_client.get_collection('csgo_items')
        
        updated = 0
        for name in agent_names:
            result = col.update_many(
                {'name': name},
                {'$set': {'weapon_category': '探员'}}
            )
            if result.modified_count > 0:
                print(f"  更新: {name}")
                updated += result.modified_count
        
        print(f"\n总共更新了 {updated} 个探员物品")
        
        # 验证
        agent_count = col.count_documents({'weapon_category': '探员'})
        print(f"现在数据库中共有 {agent_count} 个探员")
    else:
        print(f"API返回异常: {data}")
        
except Exception as e:
    print(f"Error: {e}")

