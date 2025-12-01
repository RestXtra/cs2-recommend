"""Scrapy扩展"""
from scrapy import signals
from datetime import datetime
from loguru import logger
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from utils.mongo_client import mongo_client
from utils.redis_client import redis_client


class StatsCollectorExtension:
    """统计收集扩展"""
    
    def __init__(self, stats):
        self.stats = stats
        self.start_time = None
        self.items_scraped = 0
        self.items_dropped = 0
    
    @classmethod
    def from_crawler(cls, crawler):
        ext = cls(crawler.stats)
        
        crawler.signals.connect(ext.spider_opened, signal=signals.spider_opened)
        crawler.signals.connect(ext.spider_closed, signal=signals.spider_closed)
        crawler.signals.connect(ext.item_scraped, signal=signals.item_scraped)
        crawler.signals.connect(ext.item_dropped, signal=signals.item_dropped)
        
        return ext
    
    def spider_opened(self, spider):
        """爬虫开启"""
        self.start_time = datetime.now()
        logger.info(f"爬虫启动: {spider.name}")
    
    def spider_closed(self, spider, reason):
        """爬虫关闭"""
        end_time = datetime.now()
        runtime = (end_time - self.start_time).total_seconds()
        
        # 获取Redis统计
        redis_stats = redis_client.get_stats()
        
        # 保存统计到MongoDB
        stats_data = {
            'timestamp': end_time,
            'spider_name': spider.name,
            'items_scraped': self.items_scraped,
            'items_dropped': self.items_dropped,
            'response_received': self.stats.get_value('response_received_count', 0),
            'request_failed': self.stats.get_value('retry/count', 0),
            'queue_size': redis_stats.get('queue_size', 0),
            'dupefilter_count': redis_stats.get('filtered_count', 0),
            'runtime': runtime,
            'status': reason
        }
        
        try:
            mongo_client.get_collection('stats').insert_one(stats_data)
            logger.info(f"统计数据已保存: {stats_data}")
        except Exception as e:
            logger.error(f"保存统计数据失败: {e}")
        
        logger.info(
            f"爬虫关闭: {spider.name}, "
            f"原因: {reason}, "
            f"运行时间: {runtime:.2f}s, "
            f"爬取: {self.items_scraped}, "
            f"丢弃: {self.items_dropped}"
        )
    
    def item_scraped(self, item, spider):
        """商品爬取"""
        self.items_scraped += 1
    
    def item_dropped(self, item, spider, exception):
        """商品丢弃"""
        self.items_dropped += 1

