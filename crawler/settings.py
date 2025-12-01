"""Scrapy配置文件"""
import sys
from pathlib import Path

# 添加项目根目录到Python路径
BASE_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(BASE_DIR))

from utils.config import config

# Scrapy基础配置
BOT_NAME = 'csgo_spider'
SPIDER_MODULES = ['crawler.spiders']
NEWSPIDER_MODULE = 'crawler.spiders'

# 遵守robots.txt规则
ROBOTSTXT_OBEY = False

# 并发配置
CONCURRENT_REQUESTS = config.get('spider.concurrent_requests', 16)
CONCURRENT_REQUESTS_PER_DOMAIN = 16
DOWNLOAD_DELAY = config.get('spider.download_delay', 0.5)

# 超时配置
DOWNLOAD_TIMEOUT = config.get('spider.timeout', 30)

# 重试配置
RETRY_ENABLED = True
RETRY_TIMES = config.get('spider.retry_times', 3)
RETRY_HTTP_CODES = [500, 502, 503, 504, 408, 429]

# Cookie配置
COOKIES_ENABLED = True

# Telnet配置
TELNETCONSOLE_ENABLED = False

# User-Agent配置
USER_AGENT = config.get('spider.api.headers.user-agent', 
                        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')

# 默认请求头
DEFAULT_REQUEST_HEADERS = {
    'Accept': 'application/json',
    'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
    'Accept-Encoding': 'gzip, deflate, br',
}

# ============= Scrapy-Redis配置 =============
# 使用Scrapy-Redis的调度器
SCHEDULER = "scrapy_redis.scheduler.Scheduler"

# 使用Scrapy-Redis的去重过滤器
DUPEFILTER_CLASS = "scrapy_redis.dupefilter.RFPDupeFilter"

# 启用持久化（不清空Redis队列）
SCHEDULER_PERSIST = True

# 队列类型（优先级队列）
SCHEDULER_QUEUE_CLASS = 'scrapy_redis.queue.PriorityQueue'

# Redis连接配置
redis_config = config.redis
REDIS_HOST = redis_config.get('host', 'localhost')
REDIS_PORT = redis_config.get('port', 6379)
REDIS_DB = redis_config.get('db', 0)
REDIS_PARAMS = {
    'password': redis_config.get('password'),
    # Scrapy-Redis使用pickle序列化，不能decode_responses
    'decode_responses': False
}

# Redis键配置
REDIS_START_URLS_KEY = redis_config.get('queue_key', 'csgo:start_urls')
REDIS_ITEMS_KEY = redis_config.get('items_key', 'csgo:items')

# ============= 中间件配置 =============
DOWNLOADER_MIDDLEWARES = {
    'crawler.middlewares.CustomHeadersMiddleware': 543,
    'crawler.middlewares.RetryMiddleware': 550,
    'scrapy.downloadermiddlewares.useragent.UserAgentMiddleware': None,
    'scrapy.downloadermiddlewares.retry.RetryMiddleware': None,
}

SPIDER_MIDDLEWARES = {
    # scrapy-redis没有spidermiddleware，注释掉
    # 'scrapy_redis.spidermiddleware.RediSpiderMiddleware': 100,
}

# ============= Pipeline配置 =============
ITEM_PIPELINES = {
    'crawler.pipelines.DataCleanPipeline': 100,
    'crawler.pipelines.ImageDownloadPipeline': 200,
    'crawler.pipelines.DeduplicationPipeline': 300,
    'crawler.pipelines.MLFilterPipeline': 400,
    'crawler.pipelines.MongoDBPipeline': 500,
    'crawler.pipelines.StatsPipeline': 600,
}

# 图片下载配置
IMAGES_STORE = str(BASE_DIR / 'data' / 'images')
IMAGES_URLS_FIELD = 'image_url'
IMAGES_RESULT_FIELD = 'image_path'

# ============= 日志配置 =============
LOG_LEVEL = config.get('monitor.logging.level', 'INFO')
LOG_FORMAT = '%(asctime)s [%(name)s] %(levelname)s: %(message)s'
LOG_DATEFORMAT = '%Y-%m-%d %H:%M:%S'

# 禁用默认日志，使用loguru
LOG_ENABLED = True

# ============= 扩展配置 =============
EXTENSIONS = {
    'scrapy.extensions.telnet.TelnetConsole': None,
    'crawler.extensions.StatsCollectorExtension': 100,
}

# ============= AutoThrottle配置 =============
AUTOTHROTTLE_ENABLED = True
AUTOTHROTTLE_START_DELAY = 1
AUTOTHROTTLE_MAX_DELAY = 10
AUTOTHROTTLE_TARGET_CONCURRENCY = 2.0
AUTOTHROTTLE_DEBUG = False

# ============= HTTP缓存配置 =============
HTTPCACHE_ENABLED = False
HTTPCACHE_EXPIRATION_SECS = 3600
HTTPCACHE_DIR = 'httpcache'
HTTPCACHE_IGNORE_HTTP_CODES = [500, 502, 503, 504, 408, 429]

# ============= Feed导出配置 =============
FEED_EXPORT_ENCODING = 'utf-8'

# ============= DNS配置 =============
DNSCACHE_ENABLED = True
DNSCACHE_SIZE = 10000

# ============= 其他配置 =============
REACTOR_THREADPOOL_MAXSIZE = 20
REDIRECT_ENABLED = True
REDIRECT_MAX_TIMES = 3

