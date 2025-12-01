"""初始化数据库脚本"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.mongo_client import mongo_client
from utils.redis_client import redis_client
from monitor.logger import logger


def init_mongodb():
    """初始化MongoDB"""
    logger.info("初始化MongoDB...")
    
    try:
        # 测试连接
        mongo_client.db.command('ping')
        logger.info("MongoDB连接成功")
        
        # 创建集合（如果不存在）
        collections = ['market_items', 'crawler_stats', 'crawler_logs']
        existing_collections = mongo_client.db.list_collection_names()
        
        for collection in collections:
            if collection not in existing_collections:
                mongo_client.db.create_collection(collection)
                logger.info(f"创建集合: {collection}")
            else:
                logger.info(f"集合已存在: {collection}")
        
        logger.info("MongoDB初始化完成")
        
    except Exception as e:
        logger.error(f"MongoDB初始化失败: {e}")
        raise


def init_redis():
    """初始化Redis"""
    logger.info("初始化Redis...")
    
    try:
        # 测试连接
        redis_client.client.ping()
        logger.info("Redis连接成功")
        
        # 清空队列和去重过滤器
        redis_client.clear_queue()
        redis_client.clear_dupefilter()
        
        logger.info("Redis初始化完成")
        
    except Exception as e:
        logger.error(f"Redis初始化失败: {e}")
        raise


def init_directories():
    """初始化目录结构"""
    logger.info("初始化目录结构...")
    
    base_dir = Path(__file__).parent.parent
    
    directories = [
        base_dir / 'data' / 'images' / 'items',
        base_dir / 'data' / 'images' / 'trends',
        base_dir / 'logs',
        base_dir / 'ml' / 'models',
    ]
    
    for directory in directories:
        directory.mkdir(parents=True, exist_ok=True)
        logger.info(f"创建目录: {directory}")
    
    logger.info("目录结构初始化完成")


def main():
    """主函数"""
    logger.info("=" * 50)
    logger.info("开始初始化数据库和目录")
    logger.info("=" * 50)
    
    try:
        # 初始化目录
        init_directories()
        
        # 初始化MongoDB
        init_mongodb()
        
        # 初始化Redis
        init_redis()
        
        logger.info("=" * 50)
        logger.info("初始化完成！")
        logger.info("=" * 50)
        
    except Exception as e:
        logger.error(f"初始化失败: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()

