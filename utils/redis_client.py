"""Redis客户端模块"""
import redis
from typing import List, Optional
from loguru import logger
from .config import config


class RedisClient:
    """Redis客户端类"""
    
    _instance = None
    _client = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if self._client is None:
            self.connect()
    
    def connect(self):
        """连接Redis"""
        redis_config = config.redis
        try:
            self._client = redis.Redis(
                host=redis_config.get('host', 'localhost'),
                port=redis_config.get('port', 6379),
                db=redis_config.get('db', 0),
                password=redis_config.get('password'),
                decode_responses=True
            )
            # 测试连接
            self._client.ping()
            logger.info(f"Redis连接成功: {redis_config.get('host')}:{redis_config.get('port')}")
        except Exception as e:
            logger.error(f"Redis连接失败: {e}")
            raise
    
    @property
    def client(self):
        """获取Redis客户端"""
        return self._client
    
    def push_start_url(self, url: str):
        """添加起始URL到队列
        
        Args:
            url: URL地址
        """
        queue_key = config.get('redis.queue_key', 'csgo:start_urls')
        self._client.lpush(queue_key, url)
        logger.info(f"添加URL到队列: {url}")
    
    def push_start_urls(self, urls: List[str]):
        """批量添加起始URL
        
        Args:
            urls: URL列表
        """
        queue_key = config.get('redis.queue_key', 'csgo:start_urls')
        if urls:
            self._client.lpush(queue_key, *urls)
            logger.info(f"批量添加{len(urls)}个URL到队列")
    
    def get_queue_size(self) -> int:
        """获取队列大小"""
        queue_key = config.get('redis.queue_key', 'csgo:start_urls')
        return self._client.llen(queue_key)
    
    def clear_queue(self):
        """清空队列"""
        queue_key = config.get('redis.queue_key', 'csgo:start_urls')
        self._client.delete(queue_key)
        logger.info("队列已清空")
    
    def clear_dupefilter(self):
        """清空去重过滤器"""
        dupefilter_key = config.get('redis.dupefilter_key', 'csgo:dupefilter')
        # 删除所有匹配的键
        keys = self._client.keys(f"{dupefilter_key}:*")
        if keys:
            self._client.delete(*keys)
        self._client.delete(dupefilter_key)
        logger.info("去重过滤器已清空")
    
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
        """设置键值
        
        Args:
            key: 键
            value: 值
            expire: 过期时间（秒）
        """
        self._client.set(key, value, ex=expire)
    
    def get_value(self, key: str) -> Optional[str]:
        """获取键值
        
        Args:
            key: 键
            
        Returns:
            值
        """
        return self._client.get(key)
    
    def delete_key(self, key: str):
        """删除键
        
        Args:
            key: 键
        """
        self._client.delete(key)
    
    def close(self):
        """关闭连接"""
        if self._client:
            self._client.close()
            logger.info("Redis连接已关闭")


# 全局Redis客户端实例
redis_client = RedisClient()

