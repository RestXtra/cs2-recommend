"""统一配置管理模块

整合 YAML 配置文件和环境变量，提供统一的配置访问接口。
敏感信息（API密钥等）通过环境变量或 .env 文件配置。
"""
import os
import yaml
from pathlib import Path
from typing import Any, Dict, Optional
from dotenv import load_dotenv

# 项目根目录
PROJECT_ROOT = Path(__file__).parent.parent.parent

# 加载 .env 文件
load_dotenv(PROJECT_ROOT / '.env')


def get_env(key: str, default: str = None) -> Optional[str]:
    """获取环境变量
    
    Args:
        key: 环境变量名
        default: 默认值
        
    Returns:
        环境变量值
    """
    return os.getenv(key, default)


class Config:
    """配置管理类（单例模式）"""
    
    _instance = None
    _config: Dict = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if self._config is None:
            self.load_config()
    
    def load_config(self, config_path: str = None):
        """加载配置文件"""
        if config_path is None:
            config_path = PROJECT_ROOT / 'config' / 'settings.yaml'
        
        with open(config_path, 'r', encoding='utf-8') as f:
            self._config = yaml.safe_load(f)
        
        # 注入环境变量配置
        self._inject_env_config()
    
    def _inject_env_config(self):
        """从环境变量注入敏感配置"""
        # SiliconFlow AI API
        if get_env('SILICONFLOW_API_KEY'):
            self.set('ai.siliconflow.api_key', get_env('SILICONFLOW_API_KEY'))
        
        # SteamDT API
        if get_env('STEAMDT_ACCESS_TOKEN'):
            self.set('spider.api.headers.access-token', get_env('STEAMDT_ACCESS_TOKEN'))
        if get_env('STEAMDT_DEVICE_ID'):
            self.set('spider.api.headers.x-device-id', get_env('STEAMDT_DEVICE_ID'))
        
        # Redis 密码
        if get_env('REDIS_PASSWORD'):
            self.set('redis.password', get_env('REDIS_PASSWORD'))
    
    def get(self, key: str, default: Any = None) -> Any:
        """获取配置项（支持点号分隔的多级键）
        
        Args:
            key: 配置键，如 'mongodb.host'
            default: 默认值
            
        Returns:
            配置值
        """
        keys = key.split('.')
        value = self._config
        
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
                if value is None:
                    return default
            else:
                return default
        
        return value
    
    def set(self, key: str, value: Any):
        """设置配置项
        
        Args:
            key: 配置键
            value: 配置值
        """
        keys = key.split('.')
        config = self._config
        
        for k in keys[:-1]:
            if k not in config:
                config[k] = {}
            config = config[k]
        
        config[keys[-1]] = value
    
    def get_all(self) -> Dict:
        """获取所有配置"""
        return self._config.copy()
    
    # 便捷属性
    @property
    def mongodb(self) -> Dict:
        return self.get('mongodb', {})
    
    @property
    def redis(self) -> Dict:
        return self.get('redis', {})
    
    @property
    def spider(self) -> Dict:
        return self.get('spider', {})
    
    @property
    def ml(self) -> Dict:
        return self.get('ml', {})
    
    @property
    def monitor(self) -> Dict:
        return self.get('monitor', {})
    
    @property
    def api_server(self) -> Dict:
        return self.get('api_server', {})
    
    @property
    def project_root(self) -> Path:
        return PROJECT_ROOT


# 全局配置实例
config = Config()
