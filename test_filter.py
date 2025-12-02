# -*- coding: utf-8 -*-
"""测试武器类型筛选修复"""

from utils.mongo_client import mongo_client
from ml.classifier import item_classifier

# 使用 get_collection 获取正确映射的集合
collection = mongo_client.get_collection('items')

def test_query(weapon_types):
    """模拟 API 筛选逻辑"""
    weapon_type_values = []
    for wt in weapon_types:
        if wt in item_classifier.WEAPON_TYPE_MAP:
            weapon_type_values.extend(item_classifier.WEAPON_TYPE_MAP[wt])
        else:
            weapon_type_values.append(wt)
    
    result = collection.count_documents({'weapon_type': {'$in': weapon_type_values}})
    print(f'{weapon_types} -> {weapon_type_values} => {result} items')

print("===== 测试武器类型筛选修复 =====")

print("\n1. 匕首类测试")
test_query(['刺刀'])
test_query(['M9 刺刀'])
test_query(['蝴蝶刀'])
test_query(['爪子刀'])
test_query(['骷髅匕首'])
test_query(['折叠刀'])
test_query(['短剑'])
test_query(['锯齿爪刀'])
test_query(['流浪者匕首'])
test_query(['熊刀'])
test_query(['海豹短刀'])
test_query(['猎杀者匕首'])
test_query(['系绳匕首'])
test_query(['求生匕首'])
test_query(['弯刀'])
test_query(['暗影双匕'])
test_query(['鲍伊猎刀'])
test_query(['穿肠刀'])
test_query(['折刀'])
test_query(['廓尔喀刀'])

print("\n2. 手套类测试")
test_query(['运动手套'])
test_query(['专业手套'])
test_query(['摩托手套'])
test_query(['驾驶手套'])
test_query(['裹手'])
test_query(['狂牙手套'])
test_query(['九头蛇手套'])
test_query(['血猎手套'])

print("\n3. 步枪类测试")
test_query(['AK-47'])
test_query(['AWP'])
test_query(['M4A1 消音型'])
test_query(['M4A4'])
test_query(['加利尔 AR'])
test_query(['法玛斯'])
test_query(['SSG 08'])
test_query(['AUG'])
test_query(['SG 553'])
test_query(['SCAR-20'])
test_query(['G3SG1'])

print("\n4. 手枪类测试")
test_query(['沙漠之鹰'])
test_query(['USP 消音版'])
test_query(['格洛克 18 型'])
test_query(['Tec-9'])
test_query(['FN57'])
test_query(['P250'])
test_query(['双持贝瑞塔'])
test_query(['CZ75 自动手枪'])
test_query(['R8 左轮手枪'])
test_query(['P2000'])

print("\n5. 微型冲锋枪类测试")
test_query(['MP9'])
test_query(['MAC-10'])
test_query(['P90'])
test_query(['UMP-45'])
test_query(['MP7'])
test_query(['PP-野牛'])
test_query(['MP5-SD'])

print("\n6. 霰弹枪类测试")
test_query(['MAG-7'])
test_query(['XM1014'])
test_query(['截短霰弹枪'])
test_query(['新星'])

print("\n7. 机枪类测试")
test_query(['内格夫'])
test_query(['M249'])

print("\n===== 测试完成 =====")
print("\n如果上面所有结果都大于0，说明筛选修复成功！")
