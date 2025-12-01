"""Scrapy中间件"""
from scrapy import signals
from scrapy.http import HtmlResponse
from scrapy.downloadermiddlewares.retry import RetryMiddleware as BaseRetryMiddleware
from loguru import logger
import sys
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))
from utils.config import config


class CustomHeadersMiddleware:
    """自定义请求头中间件"""
    
    def __init__(self):
        self.headers = config.get('spider.api.headers', {})
    
    @classmethod
    def from_crawler(cls, crawler):
        middleware = cls()
        crawler.signals.connect(middleware.spider_opened, signal=signals.spider_opened)
        return middleware
    
    def process_request(self, request, spider):
        """处理请求，添加自定义请求头"""
        # 添加API请求头
        for key, value in self.headers.items():
            # 转换为HTTP头格式
            header_key = key.replace('_', '-').title()
            if header_key not in request.headers:
                request.headers[header_key] = str(value)
        
        # 添加时间戳
        if 'timestamp' not in request.url:
            import time
            timestamp = int(time.time() * 1000)
            if '?' in request.url:
                request._url = f"{request.url}&timestamp={timestamp}"
            else:
                request._url = f"{request.url}?timestamp={timestamp}"
        
        return None
    
    def spider_opened(self, spider):
        logger.info(f'Spider opened: {spider.name}')


class RetryMiddleware(BaseRetryMiddleware):
    """重试中间件"""
    
    def process_response(self, request, response, spider):
        """处理响应"""
        if response.status in self.retry_http_codes:
            reason = f'HTTP {response.status}'
            logger.warning(f'重试请求: {request.url}, 原因: {reason}')
            return self._retry(request, reason, spider) or response
        return response
    
    def process_exception(self, request, exception, spider):
        """处理异常"""
        logger.error(f'请求异常: {request.url}, 异常: {exception}')
        return self._retry(request, exception, spider)


class SeleniumMiddleware:
    """Selenium中间件（用于动态页面）"""
    
    def __init__(self):
        self.driver = None
    
    @classmethod
    def from_crawler(cls, crawler):
        middleware = cls()
        crawler.signals.connect(middleware.spider_opened, signal=signals.spider_opened)
        crawler.signals.connect(middleware.spider_closed, signal=signals.spider_closed)
        return middleware
    
    def spider_opened(self, spider):
        """爬虫开启时初始化Selenium"""
        if hasattr(spider, 'use_selenium') and spider.use_selenium:
            from selenium import webdriver
            from selenium.webdriver.chrome.service import Service
            from selenium.webdriver.chrome.options import Options
            
            chrome_options = Options()
            
            # 从配置读取
            chromedriver_config = config.get('chromedriver', {})
            if chromedriver_config.get('headless', True):
                chrome_options.add_argument('--headless')
            
            window_size = chromedriver_config.get('window_size', [1920, 1080])
            chrome_options.add_argument(f'--window-size={window_size[0]},{window_size[1]}')
            chrome_options.add_argument('--no-sandbox')
            chrome_options.add_argument('--disable-dev-shm-usage')
            chrome_options.add_argument('--disable-gpu')
            
            # 禁用自动化检测
            chrome_options.add_experimental_option('excludeSwitches', ['enable-automation'])
            chrome_options.add_experimental_option('useAutomationExtension', False)
            
            driver_path = chromedriver_config.get('path')
            if driver_path:
                service = Service(executable_path=driver_path)
                self.driver = webdriver.Chrome(service=service, options=chrome_options)
            else:
                self.driver = webdriver.Chrome(options=chrome_options)
            
            logger.info('Selenium WebDriver已初始化')
    
    def spider_closed(self, spider):
        """爬虫关闭时清理Selenium"""
        if self.driver:
            self.driver.quit()
            logger.info('Selenium WebDriver已关闭')
    
    def process_request(self, request, spider):
        """处理请求"""
        if hasattr(spider, 'use_selenium') and spider.use_selenium:
            if self.driver:
                try:
                    self.driver.get(request.url)
                    # 等待页面加载
                    import time
                    time.sleep(2)
                    
                    body = self.driver.page_source
                    return HtmlResponse(
                        url=request.url,
                        body=body.encode('utf-8'),
                        encoding='utf-8',
                        request=request
                    )
                except Exception as e:
                    logger.error(f'Selenium处理请求失败: {e}')
                    return None
        return None


class ProxyMiddleware:
    """代理中间件"""
    
    def __init__(self):
        self.proxy_pool = []
        self.current_proxy_index = 0
    
    @classmethod
    def from_crawler(cls, crawler):
        return cls()
    
    def process_request(self, request, spider):
        """添加代理"""
        if self.proxy_pool:
            proxy = self.proxy_pool[self.current_proxy_index]
            request.meta['proxy'] = proxy
            self.current_proxy_index = (self.current_proxy_index + 1) % len(self.proxy_pool)
        return None

