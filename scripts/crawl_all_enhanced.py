"""增强版爬虫 - 支持全部抓取、断点续传、智能延迟"""
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

# 进度文件
PROGRESS_FILE = project_root / 'data' / 'crawl_progress.json'
PROGRESS_FILE.parent.mkdir(exist_ok=True)

# API配置
API_URL = "https://api.steamdt.com/skin/market/v3/page"

def get_headers():
    """获取请求头（从环境变量读取敏感信息）"""
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


class EnhancedCrawler:
    def __init__(self, delay=1.5, page_size=100):
        self.delay = delay  # 请求延迟（秒）
        self.page_size = page_size
        self.mongo_client = MongoDBClient()
        self.collection = self.mongo_client.get_collection('items')
        self.headers = get_headers()  # 动态获取请求头
        
        # 统计信息
        self.total_crawled = 0
        self.total_saved = 0
        self.current_page = 0
        self.error_count = 0
        self.start_time = None
        
        # 加载进度
        self.next_id = ""
        self.load_progress()
    
    def load_progress(self):
        """加载爬取进度 - 每次启动从第1页开始（数据可覆盖更新）"""
        # 每次启动都从第1页开始抓取，因为upsert可以更新已有数据
        logger.info("从第1页开始抓取（覆盖更新模式）")
        self.next_id = ""
        self.current_page = 0
        self.total_crawled = 0
    
    def save_progress(self):
        """保存爬取进度"""
        try:
            progress = {
                'next_id': self.next_id,
                'current_page': self.current_page,
                'total_crawled': self.total_crawled,
                'last_update': datetime.now().isoformat()
            }
            with open(PROGRESS_FILE, 'w', encoding='utf-8') as f:
                json.dump(progress, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"保存进度失败: {e}")
    
    def is_recommended_by_trend(self, trend_list):
        """
        基于价格走势图的机器学习推荐算法

        推荐规则：
        - 如果最后一个价格点比85%的历史价格点都要小，则推荐
        - 即：当前价格低于85%的历史价格，说明处于历史低位

        Args:
            trend_list: 价格走势列表 [[timestamp, price], ...]

        Returns:
            bool: 是否推荐
        """
        if not trend_list or len(trend_list) < 5:
            # 数据点太少，无法判断，不推荐
            return False

        try:
            # 提取所有价格
            prices = [float(item[1]) for item in trend_list if len(item) >= 2]

            if not prices:
                return False

            # 获取最后一个价格（当前价格）
            current_price = prices[-1]

            # 计算有多少个价格点比当前价格高
            higher_count = sum(1 for p in prices if p > current_price)

            # 计算比例
            higher_ratio = higher_count / len(prices)

            # 如果85%的价格点都比当前价格高，说明当前价格处于历史低位，推荐购买
            is_recommended = higher_ratio >= 0.85

            return is_recommended

        except Exception as e:
            logger.error(f"计算推荐失败: {e}")
            return False

    def parse_item(self, item_data):
        """解析单个商品数据"""
        try:
            # 提取价格
            steam_price = 0
            buff_price = 0
            youpin_price = 0
            c5_price = 0
            
            selling_prices = item_data.get('sellingPriceList', [])
            for price_info in selling_prices:
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
            
            # 提取比例
            suspension = item_data.get('suspension', {})
            sell_ratio = float(suspension.get('consignmentBest', 0) or 0)
            buy_ratio = float(suspension.get('purchaseBest', 0) or 0)
            buy_stable = float(suspension.get('purchaseStable', 0) or 0)

            # 判断是否推荐 - 基于价格走势图的机器学习算法
            is_recommended = self.is_recommended_by_trend(item_data.get('trendList', []))
            
            # 构建商品数据
            item = {
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
                'is_recommended': is_recommended,
                'is_favorited': False,
                'trend_list': item_data.get('trendList', []),
                'sell_num': item_data.get('sellNum', 0),
                'updated_at': datetime.now()
            }
            
            return item
        except Exception as e:
            logger.error(f"解析商品失败: {e}")
            return None
    
    def crawl_page(self):
        """抓取一页数据"""
        try:
            timestamp = int(time.time() * 1000)
            payload = {
                "dataField": "pvNums",
                "dataRange": "",
                "sortType": "desc",
                "nextId": self.next_id,
                "queryName": "",
                "pageSize": self.page_size,
                "timestamp": timestamp
            }
            
            response = requests.post(API_URL, headers=self.headers, json=payload, timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                
                if data.get('success') and data.get('data', {}).get('list'):
                    items_data = data['data']['list']
                    self.next_id = data['data'].get('nextId', '')
                    total = data['data'].get('total', 0)
                    
                    return items_data, self.next_id, total
                else:
                    logger.error(f"API返回错误: {data}")
                    return None, None, 0
            else:
                logger.error(f"请求失败: {response.status_code}")
                return None, None, 0
                
        except Exception as e:
            logger.error(f"抓取页面失败: {e}")
            self.error_count += 1
            return None, None, 0

    def save_items(self, items):
        """批量保存商品到数据库"""
        if not items:
            return 0

        saved_count = 0
        for item in items:
            try:
                # 使用upsert更新或插入
                self.collection.update_one(
                    {'item_id': item['item_id']},
                    {'$set': item},
                    upsert=True
                )
                saved_count += 1
            except Exception as e:
                logger.error(f"保存商品失败 {item.get('name', '')}: {e}")

        return saved_count

    def crawl_all(self, max_pages=None):
        """抓取所有数据"""
        self.start_time = time.time()
        logger.info("=" * 70)
        logger.info("开始抓取所有数据...")
        logger.info(f"延迟: {self.delay}秒, 每页: {self.page_size}个")
        logger.info("=" * 70)

        page_count = 0
        total_items = 0
        retry_count = 0
        max_retries = 3  # 最大重试次数

        while True:
            # 检查是否达到最大页数
            if max_pages and page_count >= max_pages:
                logger.info(f"已达到最大页数限制: {max_pages}")
                break

            logger.info(f"\n抓取第 {self.current_page + 1} 页...")

            # 抓取数据
            items_data, next_id, total = self.crawl_page()

            if items_data is None:
                retry_count += 1
                logger.warning(f"抓取失败，第 {retry_count}/{max_retries} 次重试...")

                if retry_count >= max_retries:
                    logger.error(f"重试 {max_retries} 次后仍然失败，跳过此页")
                    retry_count = 0
                    page_count += 1
                    self.current_page += 1
                    # 重置next_id，尝试下一页
                    if self.next_id:
                        # 如果有next_id，说明不是第一页，可以继续
                        continue
                    else:
                        # 如果是第一页就失败，可能是网络问题
                        logger.error("无法获取数据，请检查网络连接")
                        break

                time.sleep(self.delay * 2)  # 失败时延迟加倍
                continue

            # 重置重试计数
            retry_count = 0
            page_count += 1
            self.current_page += 1

            if not items_data:
                logger.info("没有更多数据，抓取完成！")
                break

            # 解析商品
            items = []
            for item_data in items_data:
                item = self.parse_item(item_data)
                if item:
                    items.append(item)

            # 保存到数据库
            saved = self.save_items(items)
            self.total_crawled += len(items)
            self.total_saved += saved

            logger.info(f"✓ 获取到 {len(items)} 个商品，已保存/更新 {saved} 个")
            logger.info(f"  本次已处理: {self.total_crawled} 个 | SteamDT总商品数: {total}")

            # 保存进度
            self.save_progress()

            # 检查是否还有下一页
            if not next_id:
                logger.info("已抓取所有数据！")
                break

            # 智能延迟
            time.sleep(self.delay)

        # 统计
        elapsed = time.time() - self.start_time
        recommended = self.collection.count_documents({'is_recommended': True})

        db_total = self.collection.count_documents({})

        logger.info("\n" + "=" * 70)
        logger.info("数据抓取完成!")
        logger.info("=" * 70)
        logger.info(f"本次抓取页数: {page_count}")
        logger.info(f"本次处理商品: {self.total_crawled}")
        logger.info(f"本次保存/更新: {self.total_saved}")
        logger.info(f"数据库总商品: {db_total}")
        logger.info(f"推荐商品数: {recommended}")
        logger.info(f"推荐率: {recommended/db_total*100:.1f}%" if db_total > 0 else "推荐率: 0%")
        logger.info(f"错误次数: {self.error_count}")
        logger.info(f"耗时: {elapsed/60:.1f} 分钟")
        logger.info("=" * 70)

    def reset_progress(self):
        """重置进度"""
        self.next_id = ""
        self.current_page = 0
        self.total_crawled = 0
        if PROGRESS_FILE.exists():
            PROGRESS_FILE.unlink()
        logger.info("进度已重置")


def main():
    import argparse

    parser = argparse.ArgumentParser(description='增强版爬虫')
    parser.add_argument('--pages', type=int, default=None, help='最大页数（不指定则抓取全部）')
    parser.add_argument('--delay', type=float, default=1.5, help='请求延迟（秒）')
    parser.add_argument('--page-size', type=int, default=100, help='每页商品数')
    parser.add_argument('--reset', action='store_true', help='重置进度')
    parser.add_argument('--continue', dest='continue_crawl', action='store_true', help='继续上次抓取')

    args = parser.parse_args()

    crawler = EnhancedCrawler(delay=args.delay, page_size=args.page_size)

    if args.reset:
        crawler.reset_progress()

    crawler.crawl_all(max_pages=args.pages)


if __name__ == "__main__":
    main()


