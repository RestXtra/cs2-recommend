# -*- coding: utf-8 -*-
"""检查数据库中所有武器类型"""

from utils.mongo_client import mongo_client

db = mongo_client.db
coll = db.csgo_items

# 查询手套
print("===== 手套类型 =====")
glove_types = list(coll.aggregate([
    {'$match': {'weapon_type': {'$regex': '手套'}}},
    {'$group': {'_id': '$weapon_type', 'count': {'$sum': 1}}},
    {'$sort': {'count': -1}}
]))
for t in glove_types:
    print(f"'{t['_id']}': {t['count']}")

# 查询PP野牛
print("\n===== PP-野牛 =====")
pp_types = list(coll.aggregate([
    {'$match': {'weapon_type': {'$regex': 'PP|野牛'}}},
    {'$group': {'_id': '$weapon_type', 'count': {'$sum': 1}}},
    {'$sort': {'count': -1}}
]))
for t in pp_types:
    print(f"'{t['_id']}': {t['count']}")
