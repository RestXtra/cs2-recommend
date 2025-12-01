"""统计模块"""
from datetime import datetime, timedelta
from typing import Dict, List
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from utils.mongo_client import mongo_client
from utils.redis_client import redis_client
from loguru import logger


class StatsCollector:
    """统计收集器"""
    
    def get_crawler_stats(self) -> Dict:
        """获取爬虫统计信息"""
        try:
            # 获取最新的统计记录
            stats_collection = mongo_client.get_collection('stats')
            latest_stats = stats_collection.find_one(
                sort=[('timestamp', -1)]
            )
            
            if not latest_stats:
                return self._empty_stats()
            
            # 获取Redis统计
            redis_stats = redis_client.get_stats()
            
            return {
                'spider_name': latest_stats.get('spider_name', 'N/A'),
                'status': latest_stats.get('status', 'unknown'),
                'items_scraped': latest_stats.get('items_scraped', 0),
                'items_dropped': latest_stats.get('items_dropped', 0),
                'response_received': latest_stats.get('response_received', 0),
                'request_failed': latest_stats.get('request_failed', 0),
                'queue_size': redis_stats.get('queue_size', 0),
                'dupefilter_count': redis_stats.get('filtered_count', 0),
                'runtime': latest_stats.get('runtime', 0),
                'last_update': latest_stats.get('timestamp', datetime.now()).isoformat(),
                'memory_usage': redis_stats.get('memory_usage', 'N/A')
            }
        except Exception as e:
            logger.error(f"获取爬虫统计失败: {e}")
            return self._empty_stats()
    
    def get_items_stats(self) -> Dict:
        """获取商品统计信息"""
        try:
            items_collection = mongo_client.get_collection('items')
            
            # 总数
            total_count = items_collection.count_documents({})
            
            # 推荐数量
            recommended_count = items_collection.count_documents({
                'is_recommended': True
            })
            
            # 今日新增
            today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            today_count = items_collection.count_documents({
                'created_at': {'$gte': today_start}
            })
            
            # 平均价格
            pipeline = [
                {'$group': {
                    '_id': None,
                    'avg_price': {'$avg': '$steam_price'},
                    'max_price': {'$max': '$steam_price'},
                    'min_price': {'$min': '$steam_price'}
                }}
            ]
            price_stats = list(items_collection.aggregate(pipeline))
            
            if price_stats:
                avg_price = price_stats[0].get('avg_price', 0)
                max_price = price_stats[0].get('max_price', 0)
                min_price = price_stats[0].get('min_price', 0)
            else:
                avg_price = max_price = min_price = 0

            # 计算平均涨幅 (buy_ratio)
            ratio_pipeline = [
                {'$match': {'buy_ratio': {'$exists': True, '$ne': None, '$gt': 0}}},
                {'$group': {
                    '_id': None,
                    'avg_buy_ratio': {'$avg': '$buy_ratio'}
                }}
            ]
            ratio_stats = list(items_collection.aggregate(ratio_pipeline))
            avg_buy_ratio = ratio_stats[0].get('avg_buy_ratio', 1) if ratio_stats else 1

            return {
                'total_count': total_count,
                'recommended_count': recommended_count,
                'today_count': today_count,
                'avg_price': round(avg_price, 2),
                'max_price': round(max_price, 2),
                'min_price': round(min_price, 2),
                'avg_buy_ratio': round(avg_buy_ratio, 4) if avg_buy_ratio else 1,
                'recommendation_rate': round(recommended_count / total_count * 100, 2) if total_count > 0 else 0
            }
        except Exception as e:
            logger.error(f"获取商品统计失败: {e}")
            return {
                'total_count': 0,
                'recommended_count': 0,
                'today_count': 0,
                'avg_price': 0,
                'max_price': 0,
                'min_price': 0,
                'recommendation_rate': 0
            }
    
    def get_history_stats(self, days: int = 7) -> List[Dict]:
        """获取历史统计数据
        
        Args:
            days: 天数
            
        Returns:
            历史统计列表
        """
        try:
            stats_collection = mongo_client.get_collection('stats')
            
            # 计算起始时间
            start_time = datetime.now() - timedelta(days=days)
            
            # 查询历史数据
            history = list(stats_collection.find(
                {'timestamp': {'$gte': start_time}},
                sort=[('timestamp', 1)]
            ))
            
            # 格式化数据
            result = []
            for record in history:
                result.append({
                    'timestamp': record.get('timestamp').isoformat(),
                    'items_scraped': record.get('items_scraped', 0),
                    'items_dropped': record.get('items_dropped', 0),
                    'runtime': record.get('runtime', 0),
                    'status': record.get('status', 'unknown')
                })
            
            return result
        except Exception as e:
            logger.error(f"获取历史统计失败: {e}")
            return []
    
    def get_top_items(self, limit: int = 10, sort_by: str = 'recommendation_score') -> List[Dict]:
        """获取Top商品
        
        Args:
            limit: 数量限制
            sort_by: 排序字段
            
        Returns:
            商品列表
        """
        try:
            items_collection = mongo_client.get_collection('items')
            
            # 查询推荐商品
            items = list(items_collection.find(
                {'is_recommended': True},
                limit=limit,
                sort=[(sort_by, -1)]
            ))
            
            # 格式化数据
            result = []
            for item in items:
                result.append({
                    'name': item.get('name', ''),
                    'image_url': item.get('image_url', ''),
                    'steam_price': item.get('steam_price', 0),
                    'buy_ratio': item.get('buy_ratio', 0),
                    'buy_stable': item.get('buy_stable', 0),
                    'recommendation_score': item.get('recommendation_score', 0),
                    'recommendation_reason': item.get('recommendation_reason', '')
                })
            
            return result
        except Exception as e:
            logger.error(f"获取Top商品失败: {e}")
            return []
    
    def _empty_stats(self) -> Dict:
        """空统计数据"""
        return {
            'spider_name': 'N/A',
            'status': 'unknown',
            'items_scraped': 0,
            'items_dropped': 0,
            'response_received': 0,
            'request_failed': 0,
            'queue_size': 0,
            'dupefilter_count': 0,
            'runtime': 0,
            'last_update': datetime.now().isoformat(),
            'memory_usage': 'N/A'
        }


# 全局统计收集器实例
stats_collector = StatsCollector()

