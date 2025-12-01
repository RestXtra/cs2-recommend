"""CS2市场爬虫"""
import json
import hashlib
from datetime import datetime
from typing import Dict, Any
import scrapy
from scrapy_redis.spiders import RedisSpider
from loguru import logger
import sys
from pathlib import Path
import time

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from crawler.items import MarketItem
from utils.config import config, get_env


def get_api_headers():
    """获取 API 请求头（从环境变量读取敏感信息）"""
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


class CSGOMarketSpider(RedisSpider):
    """CS2市场爬虫"""

    name = 'csgo_market'

    # Redis键配置
    redis_key = config.get('redis.queue_key', 'csgo:start_urls')

    # 自定义配置
    custom_settings = {
        'CONCURRENT_REQUESTS': 1,
        'DOWNLOAD_DELAY': 1.5,
        'DOWNLOAD_TIMEOUT': 30,
        'RETRY_TIMES': 3,
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.api_config = config.get('spider.api', {})
        self.base_url = self.api_config.get('base_url', 'https://api.steamdt.com')
        self.endpoints = self.api_config.get('endpoints', {})
        self.api_headers = get_api_headers()  # 使用函数获取请求头

        # 统计
        self.items_count = 0
        self.errors_count = 0
        self.pages_crawled = 0
    
    def make_request_from_data(self, data):
        """从Redis队列数据创建请求"""
        # data可能是URL字符串或JSON字符串
        if isinstance(data, bytes):
            data = data.decode('utf-8')

        try:
            # 尝试解析为JSON
            request_data = json.loads(data)
            url = request_data.get('url', 'https://api.steamdt.com/skin/market/v3/page')
            next_id = request_data.get('next_id', '')

            # 构建steamdt.com API请求
            body = {
                "dataField": "pvNums",
                "dataRange": "",
                "sortType": "desc",
                "nextId": next_id,
                "queryName": "",
                "pageSize": 100,
                "timestamp": int(time.time() * 1000)
            }

            return scrapy.Request(
                url=url,
                method='POST',
                body=json.dumps(body),
                headers=self.api_headers,
                callback=self.parse,
                dont_filter=True
            )
        except json.JSONDecodeError:
            # 如果不是JSON，创建初始请求
            return self.create_next_page_request('')
    
    def parse(self, response):
        """解析响应"""
        try:
            data = json.loads(response.text)

            # 检查响应状态 - steamdt.com API使用success字段
            if not data.get('success'):
                logger.error(f"API返回错误: {data}")
                self.errors_count += 1
                return

            # 解析商品列表
            items_data = data.get('data', {}).get('list', [])
            next_id = data.get('data', {}).get('nextId', '')
            total = data.get('data', {}).get('total', 0)

            self.pages_crawled += 1
            logger.info(f"第{self.pages_crawled}页: 获取到 {len(items_data)} 个商品，总计 {total} 个")

            for item_data in items_data:
                item = self.parse_item(item_data, response)
                if item:
                    self.items_count += 1
                    yield item

            # 使用nextId进行分页
            if next_id:
                # 生成下一页请求
                yield self.create_next_page_request(next_id)
            else:
                logger.info(f"爬取完成！总共 {self.items_count} 个商品，错误 {self.errors_count} 个")

        except json.JSONDecodeError as e:
            logger.error(f"JSON解析失败: {e}")
            self.errors_count += 1
        except Exception as e:
            logger.error(f"解析响应失败: {e}")
            self.errors_count += 1
    
    def parse_item(self, item_data: Dict, response) -> MarketItem:
        """解析单个商品数据 - steamdt.com格式"""
        try:
            item = MarketItem()

            # 基本信息
            item['item_id'] = str(item_data.get('id', ''))
            item['name'] = item_data.get('name', '')

            # 直接使用API返回的exteriorName字段
            # 对于印花、箱子等没有外观的商品，exteriorName可能是"普通"或空
            exterior_name = item_data.get('exteriorName', '')

            # 解析武器类型和皮肤名称
            name_parts = item['name'].split('|')
            if len(name_parts) >= 2:
                # 有|符号，说明是武器皮肤
                item['weapon_type'] = name_parts[0].strip()
                skin_and_exterior = name_parts[1].strip()
                # 进一步分割外观
                skin_parts = skin_and_exterior.split('(')
                item['skin_name'] = skin_parts[0].strip()
                if len(skin_parts) > 1:
                    # 从名称中提取的外观（括号内）
                    item['exterior'] = skin_parts[1].replace(')', '').strip()
                else:
                    # 没有括号，使用API的exteriorName
                    item['exterior'] = exterior_name
            else:
                # 没有|符号，可能是印花、箱子等
                item['weapon_type'] = item['name']
                item['skin_name'] = ''
                # 使用API的exteriorName，如果是"普通"就设为空
                item['exterior'] = '' if exterior_name == '普通' else exterior_name

            # 品质和稀有度
            item['rarity'] = item_data.get('rarityName', '')
            item['category'] = item_data.get('qualityName', '')

            # 图片
            item['image_url'] = item_data.get('imageUrl', '')

            # 价格信息 - 从sellingPriceList提取
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

            item['steam_price'] = steam_price
            item['buff_price'] = buff_price
            item['youpin_price'] = youpin_price
            item['csgame_price'] = c5_price

            # 挂刀比例 - 从suspension提取
            suspension = item_data.get('suspension', {})
            item['sell_ratio'] = float(suspension.get('consignmentBest', 0) or 0)
            item['buy_ratio'] = float(suspension.get('purchaseBest', 0) or 0)
            item['buy_stable'] = float(suspension.get('purchaseStable', 0) or 0)

            # 在售数量
            item['on_sale_count'] = item_data.get('sellNum', 0)

            # 走势图 - trendList
            trend_list = item_data.get('trendList', [])
            item['trend_data'] = json.dumps(trend_list)
            item['trend_image_url'] = ''

            # 元数据
            item['crawled_at'] = datetime.now().isoformat()
            item['source_url'] = response.url

            # 计算内容哈希（使用get避免KeyError）
            content_str = f"{item.get('name', '')}_{item.get('exterior', '')}_{item.get('steam_price', 0)}"
            item['content_hash'] = hashlib.md5(content_str.encode()).hexdigest()

            # 额外信息
            item['extra_info'] = json.dumps({
                'short_name': item_data.get('shortName', ''),
                'exterior_name': item_data.get('exteriorName', ''),
            })

            return item

        except Exception as e:
            logger.error(f"解析商品数据失败: {e}, 数据: {item_data}")
            return None
    
    def create_next_page_request(self, next_id: str):
        """创建下一页请求 - 使用nextId"""
        url = "https://api.steamdt.com/skin/market/v3/page"

        # 构建POST请求体
        body = {
            "dataField": "pvNums",
            "dataRange": "",
            "sortType": "desc",
            "nextId": next_id,
            "queryName": "",
            "pageSize": 100,
            "timestamp": int(time.time() * 1000)
        }

        return scrapy.Request(
            url=url,
            method='POST',
            body=json.dumps(body),
            headers=self.api_headers,
            callback=self.parse,
            dont_filter=True
        )

