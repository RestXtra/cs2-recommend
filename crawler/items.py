"""Scrapy数据模型定义"""
import scrapy
from scrapy import Item, Field


class MarketItem(scrapy.Item):
    """市场商品数据模型"""
    
    # 基本信息
    item_id = Field()           # 商品ID
    name = Field()              # 商品名称
    weapon_type = Field()       # 武器类型（如：格洛克18型、M4A4等）
    skin_name = Field()         # 皮肤名称
    exterior = Field()          # 外观（崭新出厂、略有磨损等）
    rarity = Field()            # 稀有度
    category = Field()          # 类别（普通、StatTrak等）
    
    # 图片
    image_url = Field()         # 商品图片URL
    image_path = Field()        # 本地图片路径
    
    # 价格信息
    steam_price = Field()       # Steam市场价格
    buff_price = Field()        # BUFF价格
    youpin_price = Field()      # 悠悠有品价格
    csgame_price = Field()      # CSGAME价格
    
    # 挂刀比例
    sell_ratio = Field()        # 寄售竞价
    buy_ratio = Field()         # 求购竞价
    buy_stable = Field()        # 求购稳定
    
    # 在售数量
    on_sale_count = Field()     # 在售数量
    
    # 走势图数据
    trend_data = Field()        # 价格走势数据（JSON格式）
    trend_image_url = Field()   # 走势图图片URL
    trend_image_path = Field()  # 走势图本地路径
    
    # 机器学习标注
    is_recommended = Field()    # 是否推荐（基于ML筛选）
    recommendation_score = Field()  # 推荐分数
    recommendation_reason = Field() # 推荐理由
    
    # 元数据
    crawled_at = Field()        # 爬取时间
    source_url = Field()        # 来源URL
    content_hash = Field()      # 内容哈希（用于去重）
    
    # 额外信息
    extra_info = Field()        # 其他额外信息（JSON格式）


class CrawlerStats(scrapy.Item):
    """爬虫统计数据模型"""
    
    timestamp = Field()         # 时间戳
    spider_name = Field()       # 爬虫名称
    items_scraped = Field()     # 已爬取数量
    items_dropped = Field()     # 丢弃数量
    response_received = Field() # 接收响应数量
    request_failed = Field()    # 失败请求数量
    queue_size = Field()        # 队列大小
    dupefilter_count = Field()  # 去重数量
    runtime = Field()           # 运行时间
    status = Field()            # 状态

