"""
重新计算所有商品的推荐状态
基于价格走势图的机器学习算法
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.mongo_client import MongoDBClient
from loguru import logger

def is_recommended_by_trend(trend_list):
    """
    基于价格走势图的机器学习推荐算法

    推荐规则：
    - 如果最后一个价格点比85%的历史价格点都要小，则推荐
    - 即：当前价格低于85%的历史价格，说明处于历史低位

    Args:
        trend_list: 价格走势列表 [[timestamp, price], ...]

    Returns:
        bool: 是否推荐
    """
    if not trend_list or len(trend_list) < 5:
        # 数据点太少，无法判断，不推荐
        return False

    try:
        # 提取所有价格
        prices = [float(item[1]) for item in trend_list if len(item) >= 2]

        if not prices:
            return False

        # 获取最后一个价格（当前价格）
        current_price = prices[-1]

        # 计算有多少个价格点比当前价格高
        higher_count = sum(1 for p in prices if p > current_price)

        # 计算比例
        higher_ratio = higher_count / len(prices)

        # 如果85%的价格点都比当前价格高，说明当前价格处于历史低位，推荐购买
        is_recommended = higher_ratio >= 0.85

        return is_recommended

    except Exception as e:
        logger.error(f"计算推荐失败: {e}")
        return False

def main():
    """重新计算所有商品的推荐状态"""
    logger.info("开始重新计算推荐状态...")
    
    client = MongoDBClient()
    collection = client.db['csgo_items']
    
    # 统计
    total = collection.count_documents({})
    updated = 0
    recommended_count = 0
    
    logger.info(f"总商品数: {total}")
    
    # 批量处理
    batch_size = 1000
    for skip in range(0, total, batch_size):
        items = collection.find({}).skip(skip).limit(batch_size)
        
        for item in items:
            trend_list = item.get('trend_list', [])
            is_recommended = is_recommended_by_trend(trend_list)
            
            # 更新数据库
            collection.update_one(
                {'_id': item['_id']},
                {'$set': {'is_recommended': is_recommended}}
            )
            
            updated += 1
            if is_recommended:
                recommended_count += 1
            
            # 每100个显示一次进度
            if updated % 100 == 0:
                logger.info(f"已处理: {updated}/{total} ({updated/total*100:.1f}%)")
    
    logger.info("\n" + "=" * 70)
    logger.info("重新计算完成!")
    logger.info("=" * 70)
    logger.info(f"总商品数: {total}")
    logger.info(f"已更新: {updated}")
    logger.info(f"推荐商品数: {recommended_count}")
    logger.info(f"推荐率: {recommended_count/total*100:.1f}%")
    logger.info("=" * 70)

if __name__ == '__main__':
    main()

