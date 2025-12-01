"""爬取 SteamDT 首页数据"""
import sys
from pathlib import Path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import requests
import time
import json
from datetime import datetime
from loguru import logger
from utils.mongo_client import MongoDBClient

class HomepageCrawler:
    """首页数据爬虫"""
    
    def __init__(self):
        self.headers = {
            "accept": "application/json",
            "content-type": "application/json",
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "origin": "https://steamdt.com",
            "referer": "https://steamdt.com/"
        }
        self.mongo_client = MongoDBClient()
        self.collection = self.mongo_client.get_collection('homepage_data')
    
    def get_summary(self):
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
            logger.error(f"获取概要数据失败: {response.status_code}")
            return None
        except Exception as e:
            logger.error(f"获取概要数据异常: {e}")
            return None
    
    def get_next_level(self):
        """获取下级板块数据（各类别指数）"""
        timestamp = int(time.time() * 1000)
        url = f"https://api.steamdt.com/user/item/block/v1/next-level?timestamp={timestamp}"
        payload = {
            "type": "BROAD",
            "level": 0,
            "platform": "ALL",
            "typeVal": "",
            "typeDay": "1",
            "timestamp": str(timestamp)
        }
        
        try:
            response = requests.post(url, headers=self.headers, json=payload, timeout=10)
            if response.status_code == 200:
                data = response.json()
                if data.get('success'):
                    return data.get('data')
            logger.error(f"获取下级板块数据失败: {response.status_code}")
            return None
        except Exception as e:
            logger.error(f"获取下级板块数据异常: {e}")
            return None
    
    def get_hot_relation(self):
        """获取热门关联数据"""
        timestamp = int(time.time() * 1000)
        url = f"https://api.steamdt.com/user/item/block/v1/relation?timestamp={timestamp}"
        payload = {
            "type": "HOT",
            "level": 0,
            "platform": "ALL",
            "typeDay": "1",
            "timestamp": str(timestamp)
        }
        
        try:
            response = requests.post(url, headers=self.headers, json=payload, timeout=10)
            if response.status_code == 200:
                data = response.json()
                if data.get('success'):
                    return data.get('data')
            logger.error(f"获取热门关联数据失败: {response.status_code}")
            return None
        except Exception as e:
            logger.error(f"获取热门关联数据异常: {e}")
            return None
    
    def get_chart_data_v1(self, kline_type=1, max_pages=None):
        """使用 v1 API 获取K线数据（支持分页，尽可能多地抓取）

        Args:
            kline_type: 1=时K, 2=日K
            max_pages: 最多加载几页数据，None=无限制，直到没有更多数据

        Returns:
            转换后的K线数据列表，格式: [{time, open, high, low, close}, ...]
        """
        all_data = []
        max_time = None
        timestamp = int(time.time() * 1000)
        page = 0

        while True:
            page += 1

            # 如果设置了最大页数限制
            if max_pages and page > max_pages:
                logger.info(f"    已达到最大页数限制: {max_pages}")
                break

            # 构建 URL
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
                        if not raw_data or len(raw_data) == 0:
                            logger.info(f"    第 {page} 页: 没有更多数据")
                            break  # 没有更多数据

                        # 转换为K线格式
                        kline_data = self._convert_v1_to_kline(raw_data)

                        # 检查是否有重复数据（说明已经到底了）
                        if all_data and kline_data[0]['time'] >= all_data[-1]['time']:
                            logger.info(f"    第 {page} 页: 数据重复，已到达最早数据")
                            break

                        all_data.extend(kline_data)

                        # 获取最早的时间戳作为下一页的 maxTime
                        max_time = int(raw_data[0][0])

                        logger.info(f"    第 {page} 页: {len(raw_data)} 个数据点 (最早: {datetime.fromtimestamp(max_time).strftime('%Y-%m-%d %H:%M')})")
                    else:
                        logger.error(f"API 返回失败: {data.get('message', 'unknown')}")
                        break
                else:
                    logger.error(f"HTTP 错误: {response.status_code}")
                    break
            except Exception as e:
                logger.error(f"请求异常: {e}")
                break

            # 避免请求过快
            time.sleep(0.5)

        # 去重并排序
        unique_data = {item['time']: item for item in all_data}
        result = sorted(unique_data.values(), key=lambda x: x['time'])

        return result

    def _convert_to_kline(self, raw_data):
        """将原始数据转换为K线格式

        Args:
            raw_data: [[timestamp, price], ...] 格式的原始数据

        Returns:
            [{time, open, high, low, close}, ...] 格式的K线数据
        """
        if not raw_data or len(raw_data) == 0:
            return []

        kline_data = []
        for i, item in enumerate(raw_data):
            if len(item) < 2:
                continue

            timestamp = int(item[0])
            price = float(item[1])

            # 简化处理：使用当前价格作为开高低收
            # 如果需要更真实的K线，可以从相邻数据点计算
            prev_price = float(raw_data[i-1][1]) if i > 0 else price
            next_price = float(raw_data[i+1][1]) if i < len(raw_data) - 1 else price

            kline_data.append({
                'time': timestamp,
                'open': prev_price,
                'high': max(prev_price, price, next_price),
                'low': min(prev_price, price, next_price),
                'close': price
            })

        return kline_data

    def _convert_v1_to_kline(self, raw_data):
        """将 v1 API 数据转换为K线格式

        Args:
            raw_data: [[时间戳, 开, 高, 低, 收, 量, 额], ...] 格式的原始数据

        Returns:
            [{time, open, high, low, close}, ...] 格式的K线数据
        """
        if not raw_data:
            return []

        kline_data = []
        for item in raw_data:
            if len(item) < 5:
                continue

            # v1 格式: [时间戳, 开, 高, 低, 收, 量, 额]
            timestamp = int(item[0])
            open_price = float(item[1])
            high_price = float(item[2])
            low_price = float(item[3])
            close_price = float(item[4])

            kline_data.append({
                'time': timestamp,
                'open': open_price,
                'high': high_price,
                'low': low_price,
                'close': close_price
            })

        return kline_data

    def crawl(self):
        """爬取首页所有数据"""
        logger.info("=" * 70)
        logger.info("开始爬取 SteamDT 首页数据")
        logger.info("=" * 70)
        
        # 1. 获取概要数据
        logger.info("\n1. 获取板块概要...")
        summary = self.get_summary()
        if summary:
            logger.info(f"✓ 大盘指数: {summary.get('index')}")
            logger.info(f"✓ 涨跌幅: {summary.get('riseFallRate')}%")
            logger.info(f"✓ 上涨: {summary.get('upNum')}, 持平: {summary.get('flatNum')}, 下跌: {summary.get('downNum')}")
        
        # 2. 获取各类别数据
        logger.info("\n2. 获取各类别指数...")
        categories = self.get_next_level()
        if categories:
            logger.info(f"✓ 获取到 {len(categories)} 个类别")
            for cat in categories[:5]:
                logger.info(f"  - {cat.get('name')}: {cat.get('index')} ({cat.get('riseFallRate')}%)")
        
        # 3. 获取热门数据
        logger.info("\n3. 获取热门板块...")
        hot_data = self.get_hot_relation()
        if hot_data:
            logger.info(f"✓ 获取到 {len(hot_data)} 个热门板块")
        
        # 4. 获取图表数据（使用 v1 API，尽可能多地抓取）
        logger.info("\n4. 获取历史图表数据（v1 API）...")

        # 时K数据（type=1，无限制分页，直到没有更多数据）
        logger.info("  - 获取时K数据（尽可能多）...")
        chart_data_hour = self.get_chart_data_v1(kline_type=1, max_pages=None)
        if chart_data_hour:
            first_time = datetime.fromtimestamp(chart_data_hour[0]['time'])
            last_time = datetime.fromtimestamp(chart_data_hour[-1]['time'])
            logger.info(f"    ✓ 总共获取到 {len(chart_data_hour)} 个时K数据点")
            logger.info(f"    ✓ 时间范围: {first_time} ~ {last_time}")

        # 日K数据（type=2，无限制分页，直到没有更多数据）
        logger.info("  - 获取日K数据（尽可能多）...")
        chart_data_day = self.get_chart_data_v1(kline_type=2, max_pages=None)
        if chart_data_day:
            first_time = datetime.fromtimestamp(chart_data_day[0]['time'])
            last_time = datetime.fromtimestamp(chart_data_day[-1]['time'])
            logger.info(f"    ✓ 总共获取到 {len(chart_data_day)} 个日K数据点")
            logger.info(f"    ✓ 时间范围: {first_time} ~ {last_time}")

        # 5. 保存到数据库
        logger.info("\n5. 保存到数据库...")
        doc = {
            'crawl_time': time.time(),
            'summary': summary,
            'categories': categories,
            'hot_data': hot_data,
            'chart_data_hour': chart_data_hour,    # 时K
            'chart_data_day': chart_data_day       # 日K
        }

        result = self.collection.insert_one(doc)
        logger.info(f"✓ 已保存，ID: {result.inserted_id}")
        
        logger.info("\n" + "=" * 70)
        logger.info("首页数据爬取完成！")
        logger.info("=" * 70)

def main():
    crawler = HomepageCrawler()
    crawler.crawl()

if __name__ == "__main__":
    main()

