"""增量更新首页数据（只抓取最新数据，不抓取历史）"""
import sys
from pathlib import Path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import requests
import time
from datetime import datetime
from loguru import logger
from utils.mongo_client import MongoDBClient

class IncrementalHomepageUpdater:
    """首页数据增量更新器"""

    def __init__(self):
        self.headers = {
            "accept": "application/json",
            "content-type": "application/json",
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36 Edg/142.0.0.0",
            "x-app-version": "1.0.0",
            "x-currency": "CNY",
            "x-device": "1",
            "origin": "https://steamdt.com",
            "referer": "https://steamdt.com/",
        }
        self.mongo_client = MongoDBClient()
        self.collection = self.mongo_client.get_collection('homepage_data')
    
    def _request_with_retry(self, method, url, max_retries=3, **kwargs):
        """带重试的请求"""
        kwargs.setdefault('timeout', 20)
        kwargs.setdefault('headers', self.headers)

        for attempt in range(max_retries):
            try:
                if method == 'GET':
                    response = requests.get(url, **kwargs)
                else:
                    response = requests.post(url, **kwargs)
                return response
            except Exception as e:
                if attempt < max_retries - 1:
                    logger.warning(f"请求失败 (尝试 {attempt + 1}/{max_retries}): {e}")
                    time.sleep(2)
                else:
                    raise
        return None

    def get_summary(self):
        """获取板块概要"""
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
            response = self._request_with_retry('POST', url, json=payload)
            if response and response.status_code == 200:
                data = response.json()
                if data.get('success'):
                    return data.get('data')
            return None
        except Exception as e:
            logger.error(f"获取概要数据异常: {e}")
            return None
    
    def get_categories(self):
        """获取各类别指数"""
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
            response = self._request_with_retry('POST', url, json=payload)
            if response and response.status_code == 200:
                data = response.json()
                if data.get('success'):
                    return data.get('data', [])
            return []
        except Exception as e:
            logger.error(f"获取类别数据异常: {e}")
            return []

    def get_hot_data(self):
        """获取热门板块"""
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
            response = self._request_with_retry('POST', url, json=payload)
            if response and response.status_code == 200:
                data = response.json()
                if data.get('success'):
                    return data.get('data', [])
            return []
        except Exception as e:
            logger.error(f"获取热门数据异常: {e}")
            return []
    
    def get_kline_from_last_time(self, kline_type=1, last_time=None):
        """从上次抓取的最后时间开始获取K线数据

        逻辑说明：
        - API的maxTime参数用于获取比maxTime更早的数据（向前翻页）
        - 我们需要获取最新数据，所以不使用maxTime，获取第一页（最新数据）
        - 然后过滤出比last_time新的数据

        Args:
            kline_type: 1=时K, 2=日K
            last_time: 数据库中最后一条记录的时间戳（已减一年的）

        Returns:
            新的K线数据点列表
        """
        ONE_YEAR = 31536000  # 一年的秒数

        if last_time:
            logger.info(f"数据库最后记录: {datetime.fromtimestamp(last_time)}")

        try:
            timestamp = int(time.time() * 1000)
            # 不使用maxTime，获取最新的第一页数据
            url = f"https://api.steamdt.com/user/statistics/v1/kline?timestamp={timestamp}&type={kline_type}&maxTime"

            response = self._request_with_retry('GET', url)
            if not response or response.status_code != 200:
                logger.warning(f"API返回状态码: {response.status_code if response else 'None'}")
                return []

            data = response.json()
            if not data.get('success'):
                logger.warning("API返回失败")
                return []

            raw_data = data.get('data', [])
            if not raw_data:
                logger.info("API返回无数据")
                return []

            # 转换数据，过滤出比last_time新的
            new_data = []
            for item in raw_data:
                if len(item) >= 5:
                    # API返回的时间戳减一年
                    item_time = int(item[0]) - ONE_YEAR

                    # 只要比last_time新的数据
                    if last_time and item_time <= last_time:
                        continue

                    new_data.append({
                        'time': item_time,
                        'open': float(item[1]),
                        'high': float(item[2]),
                        'low': float(item[3]),
                        'close': float(item[4])
                    })

            if new_data:
                logger.info(f"获取 {len(new_data)} 个新数据点 (API返回 {len(raw_data)} 个)")
            else:
                logger.info(f"无新数据 (API返回 {len(raw_data)} 个，都已存在)")

            # 排序后返回
            new_data.sort(key=lambda x: x['time'])
            return new_data

        except Exception as e:
            logger.error(f"获取K线数据失败: {e}")
            return []
    
    def update(self):
        """增量更新数据"""
        logger.info("=" * 50)
        logger.info("开始增量更新首页数据...")

        # 1. 获取最新的概要、类别、热门数据
        summary = self.get_summary()
        categories = self.get_categories()
        hot_data = self.get_hot_data()

        if not summary:
            logger.error("获取概要数据失败")
            return False

        logger.info(f"✓ 大盘指数: {summary.get('index', 0)}, 涨跌幅: {summary.get('riseFallRate', 0)}%")

        # 2. 获取数据库中现有的K线数据
        latest_doc = self.collection.find_one(sort=[('crawl_time', -1)])

        if not latest_doc:
            logger.warning("数据库中没有历史数据，请先运行 crawl_homepage.py")
            return False

        chart_data_hour = latest_doc.get('chart_data_hour', [])
        chart_data_day = latest_doc.get('chart_data_day', [])

        # 3. 找到数据库中最后一条K线的时间
        last_hour_time = None
        last_day_time = None

        if chart_data_hour:
            sorted_hour = sorted(chart_data_hour, key=lambda x: x['time'])
            last_hour_time = sorted_hour[-1]['time']
            logger.info(f"时K最后记录: {datetime.fromtimestamp(last_hour_time)}")

        if chart_data_day:
            sorted_day = sorted(chart_data_day, key=lambda x: x['time'])
            last_day_time = sorted_day[-1]['time']
            logger.info(f"日K最后记录: {datetime.fromtimestamp(last_day_time)}")

        # 4. 从最后时间开始抓取新数据
        new_hour_points = self.get_kline_from_last_time(kline_type=1, last_time=last_hour_time)
        new_day_points = self.get_kline_from_last_time(kline_type=2, last_time=last_day_time)

        # 5. 合并新数据（去重）
        hour_added = 0
        if new_hour_points:
            existing_times = {item['time'] for item in chart_data_hour}
            for point in new_hour_points:
                if point['time'] not in existing_times:
                    chart_data_hour.append(point)
                    hour_added += 1
            chart_data_hour.sort(key=lambda x: x['time'])
        logger.info(f"✓ 时K数据更新: 新增 {hour_added} 个点，总计 {len(chart_data_hour)} 个点")

        day_added = 0
        if new_day_points:
            existing_times = {item['time'] for item in chart_data_day}
            for point in new_day_points:
                if point['time'] not in existing_times:
                    chart_data_day.append(point)
                    day_added += 1
            chart_data_day.sort(key=lambda x: x['time'])
        logger.info(f"✓ 日K数据更新: 新增 {day_added} 个点，总计 {len(chart_data_day)} 个点")

        # 6. 检查数据连续性
        self._check_data_continuity(chart_data_hour, "时K")
        self._check_data_continuity(chart_data_day, "日K", gap_threshold=86400*2)  # 日K允许2天间隙

        # 7. 保存更新后的数据
        doc = {
            'crawl_time': time.time(),
            'summary': summary,
            'categories': categories,
            'hot_data': hot_data,
            'chart_data_hour': chart_data_hour,
            'chart_data_day': chart_data_day
        }

        self.collection.insert_one(doc)
        logger.info("✓ 数据更新完成")
        logger.info("=" * 50)
        return True

    def _check_data_continuity(self, data, name, gap_threshold=7200):
        """检查数据连续性

        Args:
            data: K线数据列表
            name: 数据名称（用于日志）
            gap_threshold: 间隙阈值（秒），默认2小时
        """
        if len(data) < 2:
            return

        sorted_data = sorted(data, key=lambda x: x['time'])
        gaps = []

        prev_time = sorted_data[0]['time']
        for item in sorted_data[1:]:
            diff = item['time'] - prev_time
            if diff > gap_threshold:
                gaps.append({
                    'from': datetime.fromtimestamp(prev_time),
                    'to': datetime.fromtimestamp(item['time']),
                    'hours': diff / 3600
                })
            prev_time = item['time']

        if gaps:
            logger.warning(f"⚠ {name}数据发现 {len(gaps)} 个间隙:")
            for gap in gaps[-3:]:  # 只显示最近3个
                logger.warning(f"   {gap['from']} -> {gap['to']} ({gap['hours']:.1f}小时)")
        else:
            logger.info(f"✓ {name}数据连续性检查通过")

if __name__ == '__main__':
    updater = IncrementalHomepageUpdater()
    updater.update()

