"""配置管理模块"""
import yaml
import os
from pathlib import Path
from typing import Any, Dict, Optional
from dotenv import load_dotenv

# 加载 .env 文件
load_dotenv(Path(__file__).parent.parent / '.env')


def get_env(key: str, default: str = None) -> Optional[str]:
    """获取环境变量"""
    return os.getenv(key, default)


class Config:
    """配置管理类"""
    
    _instance = None
    _config = None
    
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
            # 默认配置文件路径
            base_dir = Path(__file__).parent.parent
            config_path = base_dir / 'config' / 'settings.yaml'
        
        with open(config_path, 'r', encoding='utf-8') as f:
            self._config = yaml.safe_load(f)
    
    def get(self, key: str, default: Any = None) -> Any:
        """获取配置项
        
        Args:
            key: 配置键，支持点号分隔的多级键，如 'mongodb.host'
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
    
    @property
    def mongodb(self) -> Dict:
        """MongoDB配置"""
        return self.get('mongodb', {})
    
    @property
    def redis(self) -> Dict:
        """Redis配置"""
        return self.get('redis', {})
    
    @property
    def spider(self) -> Dict:
        """爬虫配置"""
        return self.get('spider', {})
    
    @property
    def ml(self) -> Dict:
        """机器学习配置"""
        return self.get('ml', {})
    
    @property
    def monitor(self) -> Dict:
        """监控配置"""
        return self.get('monitor', {})
    
    @property
    def api_server(self) -> Dict:
        """API服务配置"""
        return self.get('api_server', {})


# 全局配置实例
config = Config()

