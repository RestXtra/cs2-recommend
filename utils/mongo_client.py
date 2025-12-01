"""MongoDB客户端模块"""
from pymongo import MongoClient, ASCENDING, DESCENDING
from pymongo.collection import Collection
from typing import Dict, List, Optional, Any
from datetime import datetime
from loguru import logger
from .config import config


class MongoDBClient:
    """MongoDB客户端类"""
    
    _instance = None
    _client = None
    _db = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if self._client is None:
            self.connect()
    
    def connect(self):
        """连接MongoDB"""
        mongo_config = config.mongodb
        try:
            connection_string = f"mongodb://{mongo_config.get('host', 'localhost')}:{mongo_config.get('port', 27017)}/"
            self._client = MongoClient(connection_string)
            self._db = self._client[mongo_config.get('database', 'csgo_market')]
            
            # 测试连接
            self._client.server_info()
            logger.info(f"MongoDB连接成功: {mongo_config.get('database')}")
            
            # 创建索引
            self._create_indexes()
        except Exception as e:
            logger.error(f"MongoDB连接失败: {e}")
            raise
    
    def _create_indexes(self):
        """创建索引"""
        try:
            # 商品集合索引
            items_collection = self.get_collection('items')
            items_collection.create_index([('item_id', ASCENDING)], unique=True)
            items_collection.create_index([('name', ASCENDING)])
            items_collection.create_index([('buy_ratio', DESCENDING)])
            items_collection.create_index([('buy_stable', DESCENDING)])
            items_collection.create_index([('is_recommended', DESCENDING)])
            items_collection.create_index([('updated_at', DESCENDING)])
            
            # 统计集合索引
            stats_collection = self.get_collection('stats')
            stats_collection.create_index([('timestamp', DESCENDING)])
            
            logger.info("MongoDB索引创建成功")
        except Exception as e:
            logger.warning(f"创建索引时出现警告: {e}")
    
    @property
    def db(self):
        """获取数据库实例"""
        return self._db
    
    def get_collection(self, collection_name: str) -> Collection:
        """获取集合
        
        Args:
            collection_name: 集合名称
            
        Returns:
            集合对象
        """
        collections_config = config.get('mongodb.collections', {})
        actual_name = collections_config.get(collection_name, collection_name)
        return self._db[actual_name]
    
    def insert_item(self, item: Dict) -> str:
        """插入商品数据
        
        Args:
            item: 商品数据
            
        Returns:
            插入的文档ID
        """
        collection = self.get_collection('items')
        item['created_at'] = datetime.now()
        item['updated_at'] = datetime.now()
        result = collection.insert_one(item)
        return str(result.inserted_id)
    
    def update_item(self, item_id: str, update_data: Dict) -> bool:
        """更新商品数据
        
        Args:
            item_id: 商品ID
            update_data: 更新数据
            
        Returns:
            是否更新成功
        """
        collection = self.get_collection('items')
        update_data['updated_at'] = datetime.now()
        result = collection.update_one(
            {'item_id': item_id},
            {'$set': update_data}
        )
        return result.modified_count > 0
    
    def upsert_item(self, item: Dict) -> bool:
        """插入或更新商品数据
        
        Args:
            item: 商品数据
            
        Returns:
            是否成功
        """
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
    
    def find_items(self, query: Dict = None, limit: int = 100, skip: int = 0, sort: List = None) -> List[Dict]:
        """查询商品
        
        Args:
            query: 查询条件
            limit: 限制数量
            skip: 跳过数量
            sort: 排序条件
            
        Returns:
            商品列表
        """
        collection = self.get_collection('items')
        query = query or {}
        cursor = collection.find(query).skip(skip).limit(limit)
        
        if sort:
            cursor = cursor.sort(sort)
        
        return list(cursor)
    
    def count_items(self, query: Dict = None) -> int:
        """统计商品数量
        
        Args:
            query: 查询条件
            
        Returns:
            数量
        """
        collection = self.get_collection('items')
        return collection.count_documents(query or {})
    
    def close(self):
        """关闭连接"""
        if self._client:
            self._client.close()
            logger.info("MongoDB连接已关闭")


# 全局MongoDB客户端实例
mongo_client = MongoDBClient()

