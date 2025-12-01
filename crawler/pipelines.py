"""Scrapy数据管道"""
import hashlib
import json
from datetime import datetime
from pathlib import Path
import requests
from loguru import logger
import sys

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))
from utils.mongo_client import mongo_client
from utils.config import config


class DataCleanPipeline:
    """数据清洗管道"""
    
    def process_item(self, item, spider):
        """清洗数据"""
        # 清理字符串字段
        for field in ['name', 'weapon_type', 'skin_name', 'exterior']:
            if field in item and item[field]:
                item[field] = str(item[field]).strip()
        
        # 确保数值字段为数字
        for field in ['steam_price', 'buff_price', 'sell_ratio', 'buy_ratio', 'buy_stable']:
            if field in item and item[field]:
                try:
                    item[field] = float(item[field])
                except (ValueError, TypeError):
                    item[field] = 0.0
        
        # 确保整数字段
        for field in ['on_sale_count']:
            if field in item and item[field]:
                try:
                    item[field] = int(item[field])
                except (ValueError, TypeError):
                    item[field] = 0
        
        return item


class ImageDownloadPipeline:
    """图片下载管道"""
    
    def __init__(self):
        self.images_dir = Path(config.get('IMAGES_STORE', 'data/images'))
        self.images_dir.mkdir(parents=True, exist_ok=True)
    
    def process_item(self, item, spider):
        """下载图片"""
        # 下载商品图片
        if 'image_url' in item and item['image_url']:
            image_path = self.download_image(item['image_url'], 'items')
            if image_path:
                item['image_path'] = str(image_path)
        
        # 下载走势图
        if 'trend_image_url' in item and item['trend_image_url']:
            trend_path = self.download_image(item['trend_image_url'], 'trends')
            if trend_path:
                item['trend_image_path'] = str(trend_path)
        
        return item
    
    def download_image(self, url: str, category: str) -> Path:
        """下载单张图片"""
        try:
            # 生成文件名
            url_hash = hashlib.md5(url.encode()).hexdigest()
            ext = url.split('.')[-1].split('?')[0] or 'jpg'
            filename = f"{url_hash}.{ext}"
            
            # 创建分类目录
            category_dir = self.images_dir / category
            category_dir.mkdir(exist_ok=True)
            
            filepath = category_dir / filename
            
            # 如果文件已存在，跳过下载
            if filepath.exists():
                return filepath
            
            # 下载图片
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            
            with open(filepath, 'wb') as f:
                f.write(response.content)
            
            logger.debug(f"图片下载成功: {filepath}")
            return filepath
            
        except Exception as e:
            logger.error(f"图片下载失败: {url}, 错误: {e}")
            return None


class DeduplicationPipeline:
    """去重管道"""
    
    def __init__(self):
        self.dedup_config = config.get('pipeline.deduplication', {})
        self.enabled = self.dedup_config.get('enabled', True)
        self.method = self.dedup_config.get('method', 'content_hash')
        self.seen_hashes = set()
    
    def process_item(self, item, spider):
        """去重处理"""
        if not self.enabled:
            return item
        
        # 计算哈希
        if self.method == 'content_hash':
            # 基于内容的哈希
            fields = self.dedup_config.get('fields', ['name', 'exterior'])
            content = '_'.join([str(item.get(f, '')) for f in fields])
            item_hash = hashlib.md5(content.encode()).hexdigest()
        else:
            # 基于URL的哈希
            item_hash = item.get('content_hash', '')
        
        # 检查是否已存在
        if item_hash in self.seen_hashes:
            logger.debug(f"重复商品已过滤: {item.get('name')}")
            raise DropItem(f"重复商品: {item_hash}")
        
        self.seen_hashes.add(item_hash)
        item['content_hash'] = item_hash
        
        return item


class MLFilterPipeline:
    """机器学习筛选管道"""
    
    def __init__(self):
        self.ml_config = config.get('ml.filter', {})
        self.min_buy_ratio = self.ml_config.get('min_buy_ratio', 1.0)
        self.min_buy_stable = self.ml_config.get('min_buy_stable', 1.0)
    
    def process_item(self, item, spider):
        """ML筛选"""
        buy_ratio = float(item.get('buy_ratio', 0))
        buy_stable = float(item.get('buy_stable', 0))
        
        # 判断是否推荐
        is_recommended = (buy_ratio >= self.min_buy_ratio and 
                         buy_stable >= self.min_buy_stable)
        
        item['is_recommended'] = is_recommended
        
        if is_recommended:
            # 计算推荐分数（简单加权）
            score = (buy_ratio * 0.5 + buy_stable * 0.5)
            item['recommendation_score'] = round(score, 2)
            
            # 生成推荐理由
            reasons = []
            if buy_ratio >= self.min_buy_ratio:
                reasons.append(f"求购竞价优秀({buy_ratio:.2f})")
            if buy_stable >= self.min_buy_stable:
                reasons.append(f"求购稳定({buy_stable:.2f})")
            
            item['recommendation_reason'] = ', '.join(reasons)
            
            logger.info(f"发现优质标的: {item.get('name')} - 分数: {score:.2f}")
        else:
            item['recommendation_score'] = 0
            item['recommendation_reason'] = ''
        
        return item


class MongoDBPipeline:
    """MongoDB存储管道"""
    
    def __init__(self):
        self.incremental_config = config.get('pipeline.incremental', {})
        self.incremental_enabled = self.incremental_config.get('enabled', True)
        self.update_fields = self.incremental_config.get('update_fields', [])
    
    def process_item(self, item, spider):
        """存储到MongoDB"""
        try:
            item_dict = dict(item)
            
            if self.incremental_enabled:
                # 增量更新模式
                existing = mongo_client.get_collection('items').find_one(
                    {'item_id': item_dict.get('item_id')}
                )
                
                if existing:
                    # 更新指定字段
                    update_data = {field: item_dict.get(field) 
                                  for field in self.update_fields 
                                  if field in item_dict}
                    update_data['updated_at'] = datetime.now()
                    
                    mongo_client.update_item(item_dict.get('item_id'), update_data)
                    logger.debug(f"更新商品: {item_dict.get('name')}")
                else:
                    # 新增
                    mongo_client.insert_item(item_dict)
                    logger.debug(f"新增商品: {item_dict.get('name')}")
            else:
                # 直接插入或更新
                mongo_client.upsert_item(item_dict)
            
            return item
            
        except Exception as e:
            logger.error(f"MongoDB存储失败: {e}")
            raise


class StatsPipeline:
    """统计管道"""
    
    def __init__(self):
        self.stats = {
            'total': 0,
            'recommended': 0,
            'start_time': datetime.now()
        }
    
    def process_item(self, item, spider):
        """统计"""
        self.stats['total'] += 1
        
        if item.get('is_recommended'):
            self.stats['recommended'] += 1
        
        # 每100个商品输出一次统计
        if self.stats['total'] % 100 == 0:
            elapsed = (datetime.now() - self.stats['start_time']).total_seconds()
            rate = self.stats['total'] / elapsed if elapsed > 0 else 0
            
            logger.info(
                f"统计 - 总数: {self.stats['total']}, "
                f"推荐: {self.stats['recommended']}, "
                f"速率: {rate:.2f} items/s"
            )
        
        return item


from scrapy.exceptions import DropItem

