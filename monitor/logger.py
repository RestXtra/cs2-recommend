"""日志系统"""
import sys
from pathlib import Path
from loguru import logger

sys.path.insert(0, str(Path(__file__).parent.parent))
from utils.config import config


def setup_logger():
    """配置日志系统"""
    # 移除默认处理器
    logger.remove()
    
    # 获取日志配置
    log_config = config.get('monitor.logging', {})
    
    log_level = log_config.get('level', 'INFO')
    log_format = log_config.get('format', 
        "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan> - "
        "<level>{message}</level>"
    )
    rotation = log_config.get('rotation', '100 MB')
    retention = log_config.get('retention', '30 days')
    log_dir = Path(log_config.get('log_dir', 'logs'))
    
    # 创建日志目录
    log_dir.mkdir(parents=True, exist_ok=True)
    
    # 添加控制台处理器
    logger.add(
        sys.stdout,
        format=log_format,
        level=log_level,
        colorize=True
    )
    
    # 添加文件处理器 - 所有日志
    logger.add(
        log_dir / "all_{time:YYYY-MM-DD}.log",
        format=log_format,
        level=log_level,
        rotation=rotation,
        retention=retention,
        encoding='utf-8'
    )
    
    # 添加文件处理器 - 错误日志
    logger.add(
        log_dir / "error_{time:YYYY-MM-DD}.log",
        format=log_format,
        level='ERROR',
        rotation=rotation,
        retention=retention,
        encoding='utf-8'
    )
    
    logger.info("日志系统已初始化")


# 初始化日志
setup_logger()

