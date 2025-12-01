"""数据库客户端模块

整合 MongoDB 和 Redis 客户端，提供统一的数据库访问接口。
"""
import redis
from pymongo import MongoClient, ASCENDING, DESCENDING
from pymongo.collection import Collection
from typing import Dict, List, Optional, Any
from datetime import datetime
from loguru import logger

from .config import config


class MongoDBClient:
    """MongoDB 客户端类（单例模式）"""
    
    _instance = None
    _client: MongoClient = None
    _db = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if self._client is None:
            self.connect()
    
    def connect(self):
        """连接 MongoDB"""
        mongo_config = config.mongodb
        try:
            connection_string = f"mongodb://{mongo_config.get('host', 'localhost')}:{mongo_config.get('port', 27017)}/"
            self._client = MongoClient(connection_string)
            self._db = self._client[mongo_config.get('database', 'csgo_market')]
            
            # 测试连接
            self._client.server_info()
            logger.info(f"MongoDB 连接成功: {mongo_config.get('database')}")
            
            # 创建索引
            self._create_indexes()
        except Exception as e:
            logger.error(f"MongoDB 连接失败: {e}")
            raise
    
    def _create_indexes(self):
        """创建索引"""
        try:
            items_collection = self.get_collection('items')
            items_collection.create_index([('item_id', ASCENDING)], unique=True)
            items_collection.create_index([('name', ASCENDING)])
            items_collection.create_index([('buy_ratio', DESCENDING)])
            items_collection.create_index([('is_recommended', DESCENDING)])
            items_collection.create_index([('updated_at', DESCENDING)])
            
            stats_collection = self.get_collection('stats')
            stats_collection.create_index([('timestamp', DESCENDING)])
            
            logger.debug("MongoDB 索引创建成功")
        except Exception as e:
            logger.warning(f"创建索引时出现警告: {e}")
    
    @property
    def db(self):
        """获取数据库实例"""
        return self._db
    
    def get_collection(self, collection_name: str) -> Collection:
        """获取集合"""
        collections_config = config.get('mongodb.collections', {})
        actual_name = collections_config.get(collection_name, collection_name)
        return self._db[actual_name]
    
    def insert_item(self, item: Dict) -> str:
        """插入商品数据"""
        collection = self.get_collection('items')
        item['created_at'] = datetime.now()
        item['updated_at'] = datetime.now()
        result = collection.insert_one(item)
        return str(result.inserted_id)
    
    def update_item(self, item_id: str, update_data: Dict) -> bool:
        """更新商品数据"""
        collection = self.get_collection('items')
        update_data['updated_at'] = datetime.now()
        result = collection.update_one(
            {'item_id': item_id},
            {'$set': update_data}
        )
        return result.modified_count > 0
    
    def upsert_item(self, item: Dict) -> bool:
        """插入或更新商品数据"""
        collection = self.get_collection('items')
        item['updated_at'] = datetime.now()
        
        result = collection.update_one(
            {'item_id': item.get('item_id')},
            {
                '$set': item,
                '$setOnInsert': {'created_at': datetime.now()}
            },
            upsert=True
        )
        return result.acknowledged
    
    def find_items(self, query: Dict = None, limit: int = 100, 
                   skip: int = 0, sort: List = None) -> List[Dict]:
        """查询商品"""
        collection = self.get_collection('items')
        query = query or {}
        cursor = collection.find(query).skip(skip).limit(limit)
        
        if sort:
            cursor = cursor.sort(sort)
        
        return list(cursor)
    
    def count_items(self, query: Dict = None) -> int:
        """统计商品数量"""
        collection = self.get_collection('items')
        return collection.count_documents(query or {})
    
    def close(self):
        """关闭连接"""
        if self._client:
            self._client.close()
            logger.info("MongoDB 连接已关闭")


class RedisClient:
    """Redis 客户端类（单例模式）"""
    
    _instance = None
    _client: redis.Redis = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if self._client is None:
            self.connect()
    
    def connect(self):
        """连接 Redis"""
        redis_config = config.redis
        try:
            self._client = redis.Redis(
                host=redis_config.get('host', 'localhost'),
                port=redis_config.get('port', 6379),
                db=redis_config.get('db', 0),
                password=redis_config.get('password'),
                decode_responses=True
            )
            self._client.ping()
            logger.info(f"Redis 连接成功: {redis_config.get('host')}:{redis_config.get('port')}")
        except Exception as e:
            logger.error(f"Redis 连接失败: {e}")
            raise
    
    @property
    def client(self) -> redis.Redis:
        """获取 Redis 客户端"""
        return self._client
    
    def push_start_url(self, url: str):
        """添加起始 URL 到队列"""
        queue_key = config.get('redis.queue_key', 'csgo:start_urls')
        self._client.lpush(queue_key, url)
    
    def push_start_urls(self, urls: List[str]):
        """批量添加起始 URL"""
        queue_key = config.get('redis.queue_key', 'csgo:start_urls')
        if urls:
            self._client.lpush(queue_key, *urls)
    
    def get_queue_size(self) -> int:
        """获取队列大小"""
        queue_key = config.get('redis.queue_key', 'csgo:start_urls')
        return self._client.llen(queue_key)
    
    def clear_queue(self):
        """清空队列"""
        queue_key = config.get('redis.queue_key', 'csgo:start_urls')
        self._client.delete(queue_key)
    
    def clear_dupefilter(self):
        """清空去重过滤器"""
        dupefilter_key = config.get('redis.dupefilter_key', 'csgo:dupefilter')
        keys = self._client.keys(f"{dupefilter_key}:*")
        if keys:
            self._client.delete(*keys)
        self._client.delete(dupefilter_key)
    
    def get_stats(self) -> dict:
        """获取统计信息"""
        queue_key = config.get('redis.queue_key', 'csgo:start_urls')
        dupefilter_key = config.get('redis.dupefilter_key', 'csgo:dupefilter')
        
        return {
            'queue_size': self._client.llen(queue_key),
            'filtered_count': self._client.scard(dupefilter_key),
            'memory_usage': self._client.info('memory').get('used_memory_human', 'N/A')
        }
    
    def set_value(self, key: str, value: str, expire: Optional[int] = None):
        """设置键值"""
        self._client.set(key, value, ex=expire)
    
    def get_value(self, key: str) -> Optional[str]:
        """获取键值"""
        return self._client.get(key)
    
    def close(self):
        """关闭连接"""
        if self._client:
            self._client.close()
            logger.info("Redis 连接已关闭")


# 全局客户端实例
mongo_client = MongoDBClient()
redis_client = RedisClient()
