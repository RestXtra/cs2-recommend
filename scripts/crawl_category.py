# -*- coding: utf-8 -*-
"""分类爬取脚本 - 根据选择的类别专门抓取对应商品"""
import sys
from pathlib import Path
import requests
import time
import json
from datetime import datetime

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from utils.mongo_client import MongoDBClient
from utils.config import get_env
from loguru import logger

# API配置
API_URL = "https://api.steamdt.com/skin/market/v3/page"

# 分类配置 - queryName 搜索关键词
CATEGORY_CONFIG = {
    '全部': {
        'query': '',
        'description': '所有商品'
    },
    # ========== 匕首类 ==========
    '匕首': {
        'query': '★',  # 搜索带星号的商品（匕首+手套）
        'description': '所有匕首和手套'
    },
    '蝴蝶刀': {
        'query': '蝴蝶刀',
        'description': '蝴蝶刀'
    },
    '爪子刀': {
        'query': '爪子刀',
        'description': '爪子刀'
    },
    'M9刺刀': {
        'query': 'M9 刺刀',
        'description': 'M9 刺刀'
    },
    '刺刀': {
        'query': '刺刀',
        'description': '所有刺刀（包含M9刺刀）'
    },
    '折叠刀': {
        'query': '折叠刀',
        'description': '折叠刀'
    },
    '暗影双匕': {
        'query': '暗影双匕',
        'description': '暗影双匕'
    },
    '熊刀': {
        'query': '熊刀',
        'description': '熊刀'
    },
    '骷髅匕首': {
        'query': '骷髅匕首',
        'description': '骷髅匕首'
    },
    # ========== 手套类 ==========
    '手套': {
        'query': '手套',
        'description': '所有手套'
    },
    '运动手套': {
        'query': '运动手套',
        'description': '运动手套'
    },
    '专业手套': {
        'query': '专业手套',
        'description': '专业手套'
    },
    '摩托手套': {
        'query': '摩托手套',
        'description': '摩托手套'
    },
    '驾驶手套': {
        'query': '驾驶手套',
        'description': '驾驶手套'
    },
    # ========== 步枪类 ==========
    '步枪': {
        'queries': ['AK-47', 'M4A4', 'M4A1', 'AWP', 'AUG', 'SG 553', 'SCAR-20', 'G3SG1', 'SSG 08', '法玛斯', '加利尔'],
        'description': '所有步枪'
    },
    'AK-47': {
        'query': 'AK-47',
        'description': 'AK-47'
    },
    'AWP': {
        'query': 'AWP',
        'description': 'AWP'
    },
    'M4A4': {
        'query': 'M4A4',
        'description': 'M4A4'
    },
    'M4A1消音版': {
        'query': 'M4A1',
        'description': 'M4A1消音版'
    },
    # ========== 手枪类 ==========
    '手枪': {
        'queries': ['沙漠之鹰', 'USP', '格洛克', 'P250', 'P2000', 'Tec-9', 'FN57', 'CZ75', 'R8', '双持贝瑞塔'],
        'description': '所有手枪'
    },
    '沙漠之鹰': {
        'query': '沙漠之鹰',
        'description': '沙漠之鹰'
    },
    'USP消音版': {
        'query': 'USP',
        'description': 'USP消音版'
    },
    '格洛克': {
        'query': '格洛克',
        'description': '格洛克18型'
    },
    # ========== 冲锋枪类 ==========
    '冲锋枪': {
        'queries': ['MP9', 'MAC-10', 'P90', 'UMP-45', 'MP7', 'PP-野牛', 'MP5-SD'],
        'description': '所有冲锋枪'
    },
    'P90': {
        'query': 'P90',
        'description': 'P90'
    },
    'MAC-10': {
        'query': 'MAC-10',
        'description': 'MAC-10'
    },
    # ========== 其他类型 ==========
    '印花': {
        'query': '印花',
        'description': '印花'
    },
    '武器箱': {
        'query': '武器箱',
        'description': '武器箱'
    },
    '探员': {
        'query': '探员',
        'description': '探员'
    },
    '霰弹枪': {
        'queries': ['MAG-7', 'XM1014', '新星', '截短霰弹枪'],
        'description': '所有霰弹枪'
    },
    '机枪': {
        'queries': ['M249', '内格夫'],
        'description': '所有机枪'
    }
}


def get_headers():
    """获取请求头"""
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


class CategoryCrawler:
    """分类爬取器"""
    
    def __init__(self, delay=1.0, page_size=100):
        self.delay = delay
        self.page_size = page_size
        self.mongo_client = MongoDBClient()
        self.collection = self.mongo_client.get_collection('items')
        self.headers = get_headers()
        
        # 统计
        self.total_crawled = 0
        self.total_saved = 0
        self.error_count = 0
        self.start_time = None
    
    def is_recommended_by_trend(self, trend_list):
        """基于价格走势图的推荐算法"""
        if not trend_list or len(trend_list) < 5:
            return False
        try:
            prices = [float(item[1]) for item in trend_list if len(item) >= 2]
            if not prices:
                return False
            current_price = prices[-1]
            higher_count = sum(1 for p in prices if p > current_price)
            higher_ratio = higher_count / len(prices)
            return higher_ratio >= 0.85
        except Exception:
            return False
    
    def parse_item(self, item_data):
        """解析商品数据"""
        try:
            steam_price = buff_price = youpin_price = c5_price = 0
            
            for price_info in item_data.get('sellingPriceList', []):
                platform = price_info.get('platform', '')
                price = float(price_info.get('price', 0) or 0)
                if platform == 'steam':
                    steam_price = price
                elif platform == 'buff':
                    buff_price = price
                elif platform == 'youpin':
                    youpin_price = price
                elif platform == 'c5':
                    c5_price = price
            
            suspension = item_data.get('suspension', {})
            sell_ratio = float(suspension.get('consignmentBest', 0) or 0)
            buy_ratio = float(suspension.get('purchaseBest', 0) or 0)
            buy_stable = float(suspension.get('purchaseStable', 0) or 0)
            
            return {
                'item_id': str(item_data.get('id', '')),
                'name': item_data.get('name', ''),
                'short_name': item_data.get('shortName', ''),
                'image_url': item_data.get('imageUrl', ''),
                'quality': item_data.get('qualityName', ''),
                'rarity': item_data.get('rarityName', ''),
                'exterior': item_data.get('exteriorName', ''),
                'steam_price': steam_price,
                'buff_price': buff_price,
                'youpin_price': youpin_price,
                'csgame_price': c5_price,
                'sell_ratio': sell_ratio,
                'buy_ratio': buy_ratio,
                'buy_stable': buy_stable,
                'is_recommended': self.is_recommended_by_trend(item_data.get('trendList', [])),
                'is_favorited': False,
                'trend_list': item_data.get('trendList', []),
                'sell_num': item_data.get('sellNum', 0),
                'updated_at': datetime.now()
            }
        except Exception as e:
            logger.error(f"解析商品失败: {e}")
            return None
    
    def crawl_page(self, query_name, next_id='', retry_count=0):
        """抓取一页数据（带智能重试）"""
        max_retries = 3
        
        try:
            timestamp = int(time.time() * 1000)
            payload = {
                "dataField": "pvNums",
                "dataRange": "",
                "sortType": "desc",
                "nextId": next_id,
                "queryName": query_name,
                "pageSize": self.page_size,
                "timestamp": timestamp
            }
            
            response = requests.post(API_URL, headers=self.headers, json=payload, timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                
                # 检查是否被限速 (errorCode 102)
                if not data.get('success'):
                    error_code = data.get('errorCode')
                    error_msg = data.get('errorMsg', '未知错误')
                    
                    if error_code == 102 or '速度太快' in error_msg:
                        if retry_count < max_retries:
                            # 指数退避：2^retry * 5 秒
                            wait_time = (2 ** retry_count) * 5
                            logger.warning(f"被限速，等待 {wait_time} 秒后重试 ({retry_count + 1}/{max_retries})...")
                            time.sleep(wait_time)
                            return self.crawl_page(query_name, next_id, retry_count + 1)
                        else:
                            logger.error(f"重试 {max_retries} 次后仍被限速，跳过此页")
                            self.error_count += 1
                            return None, None, 0
                    else:
                        logger.error(f"API错误: {error_code} - {error_msg}")
                        return None, None, 0
                
                if data.get('data', {}).get('list'):
                    items_data = data['data']['list']
                    new_next_id = data['data'].get('nextId', '')
                    total = data['data'].get('total', 0)
                    return items_data, new_next_id, total
                else:
                    return None, None, 0
            else:
                logger.error(f"请求失败: {response.status_code}")
                return None, None, 0
        except Exception as e:
            logger.error(f"抓取失败: {e}")
            self.error_count += 1
            return None, None, 0
    
    def save_items(self, items):
        """批量保存商品"""
        if not items:
            return 0
        saved = 0
        for item in items:
            try:
                self.collection.update_one(
                    {'item_id': item['item_id']},
                    {'$set': item},
                    upsert=True
                )
                saved += 1
            except Exception as e:
                logger.error(f"保存失败 {item.get('name')}: {e}")
        return saved
    
    def crawl_by_query(self, query_name, max_pages=None):
        """按搜索关键词抓取"""
        logger.info(f"开始抓取: queryName='{query_name}'")
        
        next_id = ''
        page_count = 0
        local_crawled = 0
        
        while True:
            if max_pages and page_count >= max_pages:
                break
            
            items_data, next_id, total = self.crawl_page(query_name, next_id)
            
            if items_data is None:
                if page_count == 0:
                    logger.warning(f"'{query_name}' 无数据或请求失败")
                break
            
            page_count += 1
            
            if not items_data:
                break
            
            items = [self.parse_item(d) for d in items_data if self.parse_item(d)]
            saved = self.save_items(items)
            
            local_crawled += len(items)
            self.total_crawled += len(items)
            self.total_saved += saved
            
            logger.info(f"  第 {page_count} 页: 获取 {len(items)} 个, 保存 {saved} 个 | 该类别总数: {total}")
            
            if not next_id:
                break
            
            time.sleep(self.delay)
        
        return local_crawled
    
    def crawl_category(self, category, max_pages=None):
        """抓取指定分类"""
        if category not in CATEGORY_CONFIG:
            logger.error(f"未知分类: {category}")
            return 0
        
        config = CATEGORY_CONFIG[category]
        
        self.start_time = time.time()
        self.total_crawled = 0
        self.total_saved = 0
        
        logger.info("=" * 60)
        logger.info(f"开始分类抓取: {category} - {config.get('description', '')}")
        logger.info("=" * 60)
        
        # 如果有多个搜索关键词（如步枪包含多种武器）
        if 'queries' in config:
            for query in config['queries']:
                self.crawl_by_query(query, max_pages)
                time.sleep(self.delay)
        else:
            self.crawl_by_query(config.get('query', ''), max_pages)
        
        elapsed = time.time() - self.start_time
        
        logger.info("=" * 60)
        logger.info(f"分类 [{category}] 抓取完成!")
        logger.info(f"  处理商品: {self.total_crawled}")
        logger.info(f"  保存/更新: {self.total_saved}")
        logger.info(f"  错误次数: {self.error_count}")
        logger.info(f"  耗时: {elapsed:.1f} 秒")
        logger.info("=" * 60)
        
        return self.total_crawled
    
    def crawl_categories(self, categories, max_pages=None):
        """抓取多个分类"""
        total = 0
        for cat in categories:
            total += self.crawl_category(cat, max_pages)
        return total


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='分类爬取器')
    parser.add_argument('--category', '-c', type=str, default='全部',
                       help=f'分类名称，可选: {", ".join(CATEGORY_CONFIG.keys())}')
    parser.add_argument('--pages', '-p', type=int, default=None,
                       help='每个搜索关键词最大页数（不指定则全部）')
    parser.add_argument('--delay', '-d', type=float, default=2.5,
                       help='请求延迟（秒），建议2.5以上避免限速')
    parser.add_argument('--list', '-l', action='store_true',
                       help='列出所有可用分类')
    
    args = parser.parse_args()
    
    if args.list:
        print("可用分类:")
        for name, config in CATEGORY_CONFIG.items():
            print(f"  {name}: {config.get('description', '')}")
        return
    
    crawler = CategoryCrawler(delay=args.delay)
    crawler.crawl_category(args.category, args.pages)


if __name__ == "__main__":
    main()
