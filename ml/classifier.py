"""机器学习分类器"""
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, accuracy_score
import joblib
from pathlib import Path
from loguru import logger
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))
from utils.mongo_client import mongo_client
from utils.config import config


class InvestmentClassifier:
    """投资标的分类器"""
    
    def __init__(self):
        self.model = None
        self.model_path = Path(__file__).parent / 'models' / 'classifier.pkl'
        self.model_path.parent.mkdir(parents=True, exist_ok=True)
        
        # ML配置
        ml_config = config.get('ml.model', {})
        self.model_type = ml_config.get('type', 'random_forest')
        self.model_params = ml_config.get('params', {})
        
        # 筛选配置
        filter_config = config.get('ml.filter', {})
        self.min_buy_ratio = filter_config.get('min_buy_ratio', 1.0)
        self.min_buy_stable = filter_config.get('min_buy_stable', 1.0)
    
    def prepare_features(self, items_df: pd.DataFrame) -> tuple:
        """准备特征数据
        
        Args:
            items_df: 商品数据DataFrame
            
        Returns:
            (X, y) 特征和标签
        """
        # 选择特征列
        feature_columns = [
            'sell_ratio',      # 寄售竞价
            'buy_ratio',       # 求购竞价
            'buy_stable',      # 求购稳定
            'steam_price',     # Steam价格
            'on_sale_count',   # 在售数量
        ]
        
        # 确保所有特征列存在
        for col in feature_columns:
            if col not in items_df.columns:
                items_df[col] = 0
        
        X = items_df[feature_columns].fillna(0)
        
        # 创建标签：求购竞价 > 1.0 且 求购稳定 > 1.0
        y = ((items_df['buy_ratio'] >= self.min_buy_ratio) & 
             (items_df['buy_stable'] >= self.min_buy_stable)).astype(int)
        
        return X, y
    
    def train(self, items_df: pd.DataFrame = None):
        """训练模型
        
        Args:
            items_df: 商品数据DataFrame，如果为None则从数据库加载
        """
        if items_df is None:
            # 从MongoDB加载数据
            items = mongo_client.find_items(limit=10000)
            items_df = pd.DataFrame(items)
        
        if len(items_df) < 10:
            logger.warning("训练数据不足，至少需要10条数据")
            return
        
        # 准备数据
        X, y = self.prepare_features(items_df)
        
        # 检查正负样本
        positive_count = y.sum()
        negative_count = len(y) - positive_count
        
        logger.info(f"训练数据: 总数={len(y)}, 正样本={positive_count}, 负样本={negative_count}")
        
        if positive_count == 0 or negative_count == 0:
            logger.warning("训练数据不平衡，无法训练模型")
            return
        
        # 分割训练集和测试集
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42, stratify=y
        )
        
        # 创建模型
        if self.model_type == 'random_forest':
            self.model = RandomForestClassifier(**self.model_params)
        else:
            logger.error(f"不支持的模型类型: {self.model_type}")
            return
        
        # 训练
        logger.info("开始训练模型...")
        self.model.fit(X_train, y_train)
        
        # 评估
        y_pred = self.model.predict(X_test)
        accuracy = accuracy_score(y_test, y_pred)
        
        logger.info(f"模型准确率: {accuracy:.4f}")
        logger.info(f"\n分类报告:\n{classification_report(y_test, y_pred)}")
        
        # 特征重要性
        feature_importance = pd.DataFrame({
            'feature': X.columns,
            'importance': self.model.feature_importances_
        }).sort_values('importance', ascending=False)
        
        logger.info(f"\n特征重要性:\n{feature_importance}")
        
        # 保存模型
        self.save_model()
    
    def predict(self, item_data: dict) -> tuple:
        """预测单个商品
        
        Args:
            item_data: 商品数据字典
            
        Returns:
            (is_recommended, score, reason) 是否推荐、分数、理由
        """
        if self.model is None:
            self.load_model()
        
        if self.model is None:
            # 如果没有模型，使用规则判断
            return self._rule_based_predict(item_data)
        
        # 准备特征
        features = [
            item_data.get('sell_ratio', 0),
            item_data.get('buy_ratio', 0),
            item_data.get('buy_stable', 0),
            item_data.get('steam_price', 0),
            item_data.get('on_sale_count', 0),
        ]
        
        X = np.array([features])
        
        # 预测
        prediction = self.model.predict(X)[0]
        probability = self.model.predict_proba(X)[0][1]
        
        is_recommended = bool(prediction)
        score = round(probability * 100, 2)
        
        # 生成理由
        reason = self._generate_reason(item_data, is_recommended)
        
        return is_recommended, score, reason
    
    def _rule_based_predict(self, item_data: dict) -> tuple:
        """基于规则的预测（无模型时使用）"""
        buy_ratio = item_data.get('buy_ratio', 0)
        buy_stable = item_data.get('buy_stable', 0)
        
        is_recommended = (buy_ratio >= self.min_buy_ratio and 
                         buy_stable >= self.min_buy_stable)
        
        if is_recommended:
            score = round((buy_ratio * 0.5 + buy_stable * 0.5) * 50, 2)
        else:
            score = 0
        
        reason = self._generate_reason(item_data, is_recommended)
        
        return is_recommended, score, reason
    
    def _generate_reason(self, item_data: dict, is_recommended: bool) -> str:
        """生成推荐理由"""
        if not is_recommended:
            return "不满足筛选条件"
        
        reasons = []
        
        buy_ratio = item_data.get('buy_ratio', 0)
        buy_stable = item_data.get('buy_stable', 0)
        
        if buy_ratio >= self.min_buy_ratio:
            reasons.append(f"求购竞价优秀({buy_ratio:.2f})")
        
        if buy_stable >= self.min_buy_stable:
            reasons.append(f"求购稳定({buy_stable:.2f})")
        
        return ', '.join(reasons) if reasons else "符合投资条件"
    
    def save_model(self):
        """保存模型"""
        if self.model:
            joblib.dump(self.model, self.model_path)
            logger.info(f"模型已保存: {self.model_path}")
    
    def load_model(self):
        """加载模型"""
        if self.model_path.exists():
            self.model = joblib.load(self.model_path)
            logger.info(f"模型已加载: {self.model_path}")
        else:
            logger.warning(f"模型文件不存在: {self.model_path}")


# 全局分类器实例
classifier = InvestmentClassifier()


class ItemCategoryClassifier:
    """商品类型分类器 - 根据商品名称自动识别类型"""

    # 类别定义
    CATEGORIES = {
        'knife': {
            'name': '匕首',
            'keywords': [
                '蝴蝶刀', '爪子刀', 'M9 刺刀', '魅影匕首', '刺刀', '折叠刀', '短剑',
                '锯齿爪刀', '流浪者匕首', '熊刀', '海豹短刀', '猎杀者匕首', '系绳匕首',
                '求生匕首', '弯刀', '暗影双匕', '鲍伊猎刀', '穿肠刀', '折刀', '腐蚀匕刀',
                '刺刀', '匕首', '猎刀', '短刀', '爪刀', '骨刀', '廓尔喀刀', '猎杀者',
                '★', 'Knife', 'Bayonet', 'Karambit', 'Butterfly', 'Talon', 'Stiletto',
                'Ursus', 'Navaja', 'Huntsman', 'Bowie', 'Falchion', 'Shadow Daggers',
                'Gut Knife', 'Flip Knife', 'Paracord', 'Survival', 'Nomad', 'Skeleton',
                'Classic Knife', 'Kukri'
            ]
        },
        'glove': {
            'name': '手套',
            'keywords': [
                '运动手套', '专业手套', '摩托手套', '驾驶手套', '裹手', '狂牙手套',
                '九头蛇手套', '血猎手套', '手套', 'Gloves', 'Sport Gloves',
                'Specialist Gloves', 'Moto Gloves', 'Driver Gloves', 'Hand Wraps',
                'Broken Fang Gloves', 'Hydra Gloves', 'Bloodhound Gloves'
            ]
        },
        'rifle': {
            'name': '步枪',
            'keywords': [
                'AK-47', 'AWP', 'M4A1 消音型', 'M4A1消音版', 'M4A4', '加利尔 AR', '法玛斯',
                'SSG 08', 'AUG', 'SG 553', 'SCAR-20', 'G3SG1', 'M4A1-S',
                'Galil AR', 'FAMAS', 'Scout', '加利尔AR'
            ]
        },
        'pistol': {
            'name': '手枪',
            'keywords': [
                '沙漠之鹰', 'USP 消音版', 'USP消音版', '格洛克 18 型', '格洛克18型',
                'Tec-9', 'FN57', 'P250', '双持贝瑞塔', 'CZ75 自动手枪', 'CZ75自动手枪',
                'R8 左轮手枪', 'R8左轮手枪', 'P2000', 'Desert Eagle',
                'USP-S', 'Glock-18', 'Five-SeveN', 'Dual Berettas', 'CZ75-Auto',
                'R8 Revolver', '手枪'
            ]
        },
        'smg': {
            'name': '微型冲锋枪',
            'keywords': [
                'MP9', 'MAC-10', 'P90', 'UMP-45', 'MP7', 'PP-野牛', 'MP5-SD',
                'PP-Bizon', '冲锋枪'
            ]
        },
        'shotgun': {
            'name': '霰弹枪',
            'keywords': [
                'MAG-7', 'XM1014', '截短霰弹枪', '新星', 'Nova', 'Sawed-Off', '霰弹枪'
            ]
        },
        'machinegun': {
            'name': '机枪',
            'keywords': [
                '内格夫', 'M249', 'Negev', '机枪'
            ]
        },
        'sticker': {
            'name': '印花',
            'keywords': [
                '印花', 'Sticker', '贴纸'
            ]
        },
        'graffiti': {
            'name': '涂鸦',
            'keywords': [
                '涂鸦', 'Graffiti', '封装的涂鸦'
            ]
        },
        'agent': {
            'name': '探员',
            'keywords': [
                '探员', 'Agent', '特工'
            ]
        },
        'charm': {
            'name': '挂件',
            'keywords': [
                '挂件', 'Charm', '吊坠'
            ]
        },
        'music_kit': {
            'name': '音乐盒',
            'keywords': [
                '音乐盒', 'Music Kit', 'StatTrak™ 音乐盒'
            ]
        },
        'case': {
            'name': '武器箱',
            'keywords': [
                '武器箱', 'Case', '箱子', '收藏品'
            ]
        },
        'patch': {
            'name': '布章',
            'keywords': [
                '布章', 'Patch', '徽章'
            ]
        },
        'other': {
            'name': '其他',
            'keywords': []
        }
    }

    def __init__(self):
        self.collection = mongo_client.get_collection('items')

    def classify_item(self, item_name: str) -> tuple:
        """根据商品名称分类

        Args:
            item_name: 商品名称

        Returns:
            (category_id, category_name) 类别ID和名称
        """
        if not item_name:
            return 'other', '其他'

        item_name_lower = item_name.lower()

        # 提取武器名称（| 之前的部分）
        weapon_part = item_name.split('|')[0].strip() if '|' in item_name else item_name
        weapon_part_lower = weapon_part.lower()

        # 按优先级检查类别（匕首和手套优先，因为它们价值最高）
        priority_order = ['knife', 'glove', 'rifle', 'pistol', 'smg', 'shotgun',
                         'machinegun', 'sticker', 'graffiti', 'agent', 'charm',
                         'music_kit', 'case', 'patch']

        for category_id in priority_order:
            category = self.CATEGORIES[category_id]
            for keyword in category['keywords']:
                keyword_lower = keyword.lower()

                # 对于武器类型（rifle, pistol, smg, shotgun, machinegun），
                # 检查武器名称部分是否匹配
                if category_id in ['rifle', 'pistol', 'smg', 'shotgun', 'machinegun']:
                    # 精确匹配武器名称部分
                    if keyword_lower == weapon_part_lower or keyword == weapon_part:
                        return category_id, category['name']
                    # 或者武器名称以关键词开头
                    if weapon_part_lower.startswith(keyword_lower) or weapon_part.startswith(keyword):
                        return category_id, category['name']
                else:
                    # 其他类型使用包含匹配
                    if keyword_lower in item_name_lower or keyword in item_name:
                        return category_id, category['name']

        return 'other', '其他'

    def classify_all_items(self, update_db: bool = True) -> dict:
        """分类所有商品

        Args:
            update_db: 是否更新数据库

        Returns:
            分类统计结果
        """
        stats = {cat_id: 0 for cat_id in self.CATEGORIES}

        items = list(self.collection.find({}, {'_id': 1, 'name': 1}))
        logger.info(f"开始分类 {len(items)} 个商品...")

        for item in items:
            item_name = item.get('name', '')
            category_id, category_name = self.classify_item(item_name)
            stats[category_id] += 1

            if update_db:
                self.collection.update_one(
                    {'_id': item['_id']},
                    {'$set': {
                        'weapon_category': category_id,
                        'weapon_category_name': category_name
                    }}
                )

        # 打印统计
        logger.info("=== 商品分类统计 ===")
        for cat_id, count in sorted(stats.items(), key=lambda x: -x[1]):
            if count > 0:
                cat_name = self.CATEGORIES[cat_id]['name']
                logger.info(f"  {cat_name}: {count}")

        return stats

    def get_items_by_category(self, category_id: str, limit: int = 100) -> list:
        """获取指定类别的商品

        Args:
            category_id: 类别ID
            limit: 返回数量限制

        Returns:
            商品列表
        """
        return list(self.collection.find(
            {'weapon_category': category_id},
            limit=limit
        ))


# 全局商品分类器实例
item_classifier = ItemCategoryClassifier()

