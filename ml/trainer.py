"""模型训练脚本"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from ml.classifier import classifier
from utils.mongo_client import mongo_client
from loguru import logger
import pandas as pd


def train_model():
    """训练模型"""
    logger.info("开始训练机器学习模型...")
    
    # 从数据库加载数据
    logger.info("从MongoDB加载数据...")
    items = mongo_client.find_items(limit=10000)
    
    if not items:
        logger.error("没有找到训练数据，请先运行爬虫")
        return
    
    logger.info(f"加载了 {len(items)} 条数据")
    
    # 转换为DataFrame
    items_df = pd.DataFrame(items)
    
    # 训练模型
    classifier.train(items_df)
    
    logger.info("模型训练完成！")


if __name__ == '__main__':
    train_model()

