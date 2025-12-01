"""核心模块 - 配置、数据库、日志"""
from .config import config, get_env
from .database import mongo_client, redis_client
from .logger import logger, setup_logger

__all__ = [
    'config', 'get_env',
    'mongo_client', 'redis_client', 
    'logger', 'setup_logger'
]
