"""统一爬虫运行器

整合多个爬虫脚本，提供统一的爬虫启动接口。
支持：
- 全量爬取
- 首页数据爬取
- 断点续传
"""
import requests
import time
import json
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, List
from loguru import logger

from ..core.config import config, get_env, PROJECT_ROOT
from ..core.database import mongo_client


class CrawlerRunner:
    """爬虫运行器 - 统一管理所有爬虫任务"""
    
    def __init__(self):
        self.market_crawler = EnhancedCrawler()
        self.homepage_crawler = HomepageCrawler()
    
    def run_market_crawl(self, max_pages: int = None, delay: float = 1.5):
        """运行市场数据爬取"""
        self.market_crawler.delay = delay
        self.market_crawler.crawl_all(max_pages=max_pages)
    
    def run_homepage_crawl(self):
        """运行首页数据爬取"""
        self.homepage_crawler.crawl()
    
    def run_all(self, market_pages: int = None, delay: float = 1.5):
        """运行所有爬取任务"""
        logger.info("=" * 70)
        logger.info("开始运行所有爬取任务")
        logger.info("=" * 70)
        
        # 先爬取首页数据
        logger.info("\n[1/2] 爬取首页数据...")
        self.run_homepage_crawl()
        
        # 再爬取市场数据
        logger.info("\n[2/2] 爬取市场数据...")
        self.run_market_crawl(max_pages=market_pages, delay=delay)
        
        logger.info("\n所有爬取任务完成！")


class EnhancedCrawler:
    """增强版市场爬虫 - 支持全量抓取、断点续传"""
    
    # 进度文件路径
    PROGRESS_FILE = PROJECT_ROOT / 'data' / 'crawl_progress.json'
    
    # API 配置
    API_URL = "https://api.steamdt.com/skin/market/v3/page"
    
    def __init__(self, delay: float = 1.5, page_size: int = 100):
        self.delay = delay
        self.page_size = page_size
        self.collection = mongo_client.get_collection('items')
        
        # 统计信息
        self.total_crawled = 0
        self.total_saved = 0
        self.current_page = 0
        self.error_count = 0
        self.start_time = None
        self.next_id = ""
        
        # 确保数据目录存在
        self.PROGRESS_FILE.parent.mkdir(exist_ok=True)
    
    @property
    def headers(self) -> Dict:
        """获取请求头（从配置读取）"""
        # 优先使用环境变量
        access_token = get_env('STEAMDT_ACCESS_TOKEN') or config.get(
            'spider.api.headers.access-token', 
            '56c6dbe5-e5c7-434c-98d9-6d32e465422d'
        )
        device_id = get_env('STEAMDT_DEVICE_ID') or config.get(
            'spider.api.headers.x-device-id',
            'a7c322ee-206f-4430-9178-9e1f6f87a70a'
        )
        
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
    
    def save_progress(self):
        """保存爬取进度"""
        try:
            progress = {
                'next_id': self.next_id,
                'current_page': self.current_page,
                'total_crawled': self.total_crawled,
                'last_update': datetime.now().isoformat()
            }
            with open(self.PROGRESS_FILE, 'w', encoding='utf-8') as f:
                json.dump(progress, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"保存进度失败: {e}")
    
    def is_recommended_by_trend(self, trend_list: List) -> bool:
        """基于价格走势的推荐算法
        
        规则：如果当前价格低于85%的历史价格，则推荐（处于历史低位）
        """
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
        except Exception as e:
            logger.error(f"计算推荐失败: {e}")
            return False
    
    def parse_item(self, item_data: Dict) -> Optional[Dict]:
        """解析单个商品数据"""
        try:
            # 提取价格
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
            
            # 提取比例
            suspension = item_data.get('suspension', {})
            sell_ratio = float(suspension.get('consignmentBest', 0) or 0)
            buy_ratio = float(suspension.get('purchaseBest', 0) or 0)
            buy_stable = float(suspension.get('purchaseStable', 0) or 0)
            
            # 判断是否推荐
            is_recommended = self.is_recommended_by_trend(item_data.get('trendList', []))
            
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
                'is_recommended': is_recommended,
                'is_favorited': False,
                'trend_list': item_data.get('trendList', []),
                'sell_num': item_data.get('sellNum', 0),
                'updated_at': datetime.now()
            }
        except Exception as e:
            logger.error(f"解析商品失败: {e}")
            return None
    
    def crawl_page(self) -> tuple:
        """抓取一页数据"""
        try:
            payload = {
                "dataField": "pvNums",
                "dataRange": "",
                "sortType": "desc",
                "nextId": self.next_id,
                "queryName": "",
                "pageSize": self.page_size,
                "timestamp": int(time.time() * 1000)
            }
            
            response = requests.post(
                self.API_URL, 
                headers=self.headers, 
                json=payload, 
                timeout=30
            )
            
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
    
    def save_items(self, items: List[Dict]) -> int:
        """批量保存商品到数据库"""
        if not items:
            return 0
        
        saved_count = 0
        for item in items:
            try:
                self.collection.update_one(
                    {'item_id': item['item_id']},
                    {'$set': item},
                    upsert=True
                )
                saved_count += 1
            except Exception as e:
                logger.error(f"保存商品失败 {item.get('name', '')}: {e}")
        
        return saved_count
    
    def crawl_all(self, max_pages: int = None):
        """抓取所有数据"""
        self.start_time = time.time()
        self.next_id = ""
        self.current_page = 0
        self.total_crawled = 0
        
        logger.info("=" * 70)
        logger.info("开始抓取市场数据...")
        logger.info(f"延迟: {self.delay}秒, 每页: {self.page_size}个")
        logger.info("=" * 70)
        
        page_count = 0
        retry_count = 0
        max_retries = 3
        
        while True:
            if max_pages and page_count >= max_pages:
                logger.info(f"已达到最大页数限制: {max_pages}")
                break
            
            logger.info(f"\n抓取第 {self.current_page + 1} 页...")
            
            items_data, next_id, total = self.crawl_page()
            
            if items_data is None:
                retry_count += 1
                logger.warning(f"抓取失败，第 {retry_count}/{max_retries} 次重试...")
                
                if retry_count >= max_retries:
                    logger.error(f"重试 {max_retries} 次后仍然失败，跳过此页")
                    retry_count = 0
                    page_count += 1
                    self.current_page += 1
                    if not self.next_id:
                        logger.error("无法获取数据，请检查网络连接")
                        break
                    continue
                
                time.sleep(self.delay * 2)
                continue
            
            retry_count = 0
            page_count += 1
            self.current_page += 1
            
            if not items_data:
                logger.info("没有更多数据，抓取完成！")
                break
            
            # 解析并保存
            items = [self.parse_item(d) for d in items_data]
            items = [i for i in items if i]
            
            saved = self.save_items(items)
            self.total_crawled += len(items)
            self.total_saved += saved
            
            logger.info(f"✓ 获取到 {len(items)} 个商品，已保存/更新 {saved} 个")
            logger.info(f"  本次已处理: {self.total_crawled} 个 | 总商品数: {total}")
            
            self.save_progress()
            
            if not next_id:
                logger.info("已抓取所有数据！")
                break
            
            time.sleep(self.delay)
        
        # 输出统计
        elapsed = time.time() - self.start_time
        db_total = self.collection.count_documents({})
        recommended = self.collection.count_documents({'is_recommended': True})
        
        logger.info("\n" + "=" * 70)
        logger.info("数据抓取完成!")
        logger.info("=" * 70)
        logger.info(f"本次抓取页数: {page_count}")
        logger.info(f"本次处理商品: {self.total_crawled}")
        logger.info(f"数据库总商品: {db_total}")
        logger.info(f"推荐商品数: {recommended}")
        logger.info(f"耗时: {elapsed/60:.1f} 分钟")
        logger.info("=" * 70)


class HomepageCrawler:
    """首页数据爬虫"""
    
    def __init__(self):
        self.collection = mongo_client.get_collection('homepage_data')
    
    @property
    def headers(self) -> Dict:
        return {
            "accept": "application/json",
            "content-type": "application/json",
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "origin": "https://steamdt.com",
            "referer": "https://steamdt.com/"
        }
    
    def get_summary(self) -> Optional[Dict]:
        """获取板块概要数据"""
        timestamp = int(time.time() * 1000)
        url = f"https://api.steamdt.com/user/item/block/v1/summary?timestamp={timestamp}"
        payload = {
            "type": "BROAD",
            "level": 0,
            "platform": "ALL",
            "typeVal": "",
            "timestamp": str(timestamp)
        }
        
        try:
            response = requests.post(url, headers=self.headers, json=payload, timeout=10)
            if response.status_code == 200:
                data = response.json()
                if data.get('success'):
                    return data.get('data')
            return None
        except Exception as e:
            logger.error(f"获取概要数据异常: {e}")
            return None
    
    def get_kline_data(self, kline_type: int = 1) -> List[Dict]:
        """获取K线数据"""
        all_data = []
        max_time = None
        timestamp = int(time.time() * 1000)
        page = 0
        
        while True:
            page += 1
            
            if max_time:
                url = f"https://api.steamdt.com/user/statistics/v1/kline?timestamp={timestamp}&type={kline_type}&maxTime={max_time}"
            else:
                url = f"https://api.steamdt.com/user/statistics/v1/kline?timestamp={timestamp}&type={kline_type}&maxTime"
            
            try:
                response = requests.get(url, headers=self.headers, timeout=10)
                if response.status_code == 200:
                    data = response.json()
                    if data.get('success'):
                        raw_data = data.get('data', [])
                        if not raw_data:
                            break
                        
                        kline_data = self._convert_kline(raw_data)
                        
                        if all_data and kline_data[0]['time'] >= all_data[-1]['time']:
                            break
                        
                        all_data.extend(kline_data)
                        max_time = int(raw_data[0][0])
                        
                        logger.debug(f"  第 {page} 页: {len(raw_data)} 个数据点")
                    else:
                        break
                else:
                    break
            except Exception as e:
                logger.error(f"请求异常: {e}")
                break
            
            time.sleep(0.5)
        
        unique_data = {item['time']: item for item in all_data}
        return sorted(unique_data.values(), key=lambda x: x['time'])
    
    def _convert_kline(self, raw_data: List) -> List[Dict]:
        """转换K线数据格式"""
        kline_data = []
        for item in raw_data:
            if len(item) < 5:
                continue
            kline_data.append({
                'time': int(item[0]),
                'open': float(item[1]),
                'high': float(item[2]),
                'low': float(item[3]),
                'close': float(item[4])
            })
        return kline_data
    
    def crawl(self):
        """爬取首页所有数据"""
        logger.info("=" * 70)
        logger.info("开始爬取首页数据")
        logger.info("=" * 70)
        
        # 获取概要
        logger.info("\n获取板块概要...")
        summary = self.get_summary()
        if summary:
            logger.info(f"✓ 大盘指数: {summary.get('index')}")
        
        # 获取K线数据
        logger.info("\n获取K线数据...")
        chart_data_hour = self.get_kline_data(kline_type=1)
        logger.info(f"✓ 时K数据: {len(chart_data_hour)} 个")
        
        chart_data_day = self.get_kline_data(kline_type=2)
        logger.info(f"✓ 日K数据: {len(chart_data_day)} 个")
        
        # 保存到数据库
        doc = {
            'crawl_time': time.time(),
            'summary': summary,
            'chart_data_hour': chart_data_hour,
            'chart_data_day': chart_data_day
        }
        
        result = self.collection.insert_one(doc)
        logger.info(f"\n✓ 已保存，ID: {result.inserted_id}")
        logger.info("=" * 70)
