"""分类器模块

包含投资分类器和商品类型分类器。
"""
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, accuracy_score
import joblib
from pathlib import Path
from loguru import logger

from ..core.config import config, PROJECT_ROOT
from ..core.database import mongo_client


class InvestmentClassifier:
    """投资标的分类器"""
    
    def __init__(self):
        self.model = None
        self.model_path = PROJECT_ROOT / 'data' / 'models' / 'classifier.pkl'
        self.model_path.parent.mkdir(parents=True, exist_ok=True)
        
        ml_config = config.get('ml.model', {})
        self.model_type = ml_config.get('type', 'random_forest')
        self.model_params = ml_config.get('params', {})
        
        filter_config = config.get('ml.filter', {})
        self.min_buy_ratio = filter_config.get('min_buy_ratio', 1.0)
        self.min_buy_stable = filter_config.get('min_buy_stable', 1.0)
    
    def prepare_features(self, items_df: pd.DataFrame) -> tuple:
        """准备特征数据"""
        feature_columns = [
            'sell_ratio', 'buy_ratio', 'buy_stable', 
            'steam_price', 'on_sale_count'
        ]
        
        for col in feature_columns:
            if col not in items_df.columns:
                items_df[col] = 0
        
        X = items_df[feature_columns].fillna(0)
        y = ((items_df['buy_ratio'] >= self.min_buy_ratio) & 
             (items_df['buy_stable'] >= self.min_buy_stable)).astype(int)
        
        return X, y
    
    def train(self, items_df: pd.DataFrame = None):
        """训练模型"""
        if items_df is None:
            items = mongo_client.find_items(limit=10000)
            items_df = pd.DataFrame(items)
        
        if len(items_df) < 10:
            logger.warning("训练数据不足")
            return
        
        X, y = self.prepare_features(items_df)
        
        if y.sum() == 0 or (len(y) - y.sum()) == 0:
            logger.warning("训练数据不平衡")
            return
        
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42, stratify=y
        )
        
        self.model = RandomForestClassifier(**self.model_params)
        self.model.fit(X_train, y_train)
        
        y_pred = self.model.predict(X_test)
        accuracy = accuracy_score(y_test, y_pred)
        
        logger.info(f"模型准确率: {accuracy:.4f}")
        self.save_model()
    
    def predict(self, item_data: dict) -> tuple:
        """预测"""
        if self.model is None:
            self.load_model()
        
        if self.model is None:
            return self._rule_based_predict(item_data)
        
        features = [
            item_data.get('sell_ratio', 0),
            item_data.get('buy_ratio', 0),
            item_data.get('buy_stable', 0),
            item_data.get('steam_price', 0),
            item_data.get('on_sale_count', 0),
        ]
        
        X = np.array([features])
        prediction = self.model.predict(X)[0]
        probability = self.model.predict_proba(X)[0][1]
        
        is_recommended = bool(prediction)
        score = round(probability * 100, 2)
        reason = self._generate_reason(item_data, is_recommended)
        
        return is_recommended, score, reason
    
    def _rule_based_predict(self, item_data: dict) -> tuple:
        """基于规则的预测"""
        buy_ratio = item_data.get('buy_ratio', 0)
        buy_stable = item_data.get('buy_stable', 0)
        
        is_recommended = (buy_ratio >= self.min_buy_ratio and 
                         buy_stable >= self.min_buy_stable)
        score = round((buy_ratio * 0.5 + buy_stable * 0.5) * 50, 2) if is_recommended else 0
        reason = self._generate_reason(item_data, is_recommended)
        
        return is_recommended, score, reason
    
    def _generate_reason(self, item_data: dict, is_recommended: bool) -> str:
        """生成推荐理由"""
        if not is_recommended:
            return "不满足筛选条件"
        
        reasons = []
        if item_data.get('buy_ratio', 0) >= self.min_buy_ratio:
            reasons.append(f"求购竞价优秀({item_data['buy_ratio']:.2f})")
        if item_data.get('buy_stable', 0) >= self.min_buy_stable:
            reasons.append(f"求购稳定({item_data['buy_stable']:.2f})")
        
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
            logger.debug(f"模型已加载: {self.model_path}")


class ItemCategoryClassifier:
    """商品类型分类器 - 根据名称自动识别类型"""

    CATEGORIES = {
        'knife': {'name': '匕首', 'keywords': [
            '蝴蝶刀', '爪子刀', 'M9 刺刀', '魅影匕首', '刺刀', '折叠刀', '短剑',
            '流浪者匕首', '熊刀', '海豹短刀', '猎杀者匕首', '弯刀', '暗影双匕',
            '★', 'Knife', 'Bayonet', 'Karambit', 'Butterfly', 'Kukri'
        ]},
        'glove': {'name': '手套', 'keywords': [
            '运动手套', '专业手套', '摩托手套', '驾驶手套', '裹手',
            '手套', 'Gloves'
        ]},
        'rifle': {'name': '步枪', 'keywords': [
            'AK-47', 'AWP', 'M4A1', 'M4A4', '加利尔', '法玛斯',
            'SSG 08', 'AUG', 'SG 553', 'SCAR-20', 'G3SG1'
        ]},
        'pistol': {'name': '手枪', 'keywords': [
            '沙漠之鹰', 'USP', '格洛克', 'Tec-9', 'FN57', 'P250',
            '双持贝瑞塔', 'CZ75', 'R8', 'P2000', 'Desert Eagle'
        ]},
        'smg': {'name': '微冲', 'keywords': ['MP9', 'MAC-10', 'P90', 'UMP-45', 'MP7', 'PP-野牛', 'MP5-SD']},
        'shotgun': {'name': '霰弹枪', 'keywords': ['MAG-7', 'XM1014', '截短霰弹枪', '新星']},
        'machinegun': {'name': '机枪', 'keywords': ['内格夫', 'M249', 'Negev']},
        'sticker': {'name': '印花', 'keywords': ['印花', 'Sticker']},
        'graffiti': {'name': '涂鸦', 'keywords': ['涂鸦', 'Graffiti']},
        'agent': {'name': '探员', 'keywords': ['探员', 'Agent']},
        'charm': {'name': '挂件', 'keywords': ['挂件', 'Charm']},
        'music_kit': {'name': '音乐盒', 'keywords': ['音乐盒', 'Music Kit']},
        'case': {'name': '武器箱', 'keywords': ['武器箱', 'Case', '箱子']},
        'patch': {'name': '布章', 'keywords': ['布章', 'Patch']},
        'other': {'name': '其他', 'keywords': []}
    }

    def __init__(self):
        self.collection = mongo_client.get_collection('items')

    def classify_item(self, item_name: str) -> tuple:
        """根据名称分类"""
        if not item_name:
            return 'other', '其他'

        item_name_lower = item_name.lower()
        weapon_part = item_name.split('|')[0].strip() if '|' in item_name else item_name
        weapon_part_lower = weapon_part.lower()

        priority_order = ['knife', 'glove', 'rifle', 'pistol', 'smg', 'shotgun',
                         'machinegun', 'sticker', 'graffiti', 'agent', 'charm',
                         'music_kit', 'case', 'patch']

        for category_id in priority_order:
            category = self.CATEGORIES[category_id]
            for keyword in category['keywords']:
                keyword_lower = keyword.lower()
                
                if category_id in ['rifle', 'pistol', 'smg', 'shotgun', 'machinegun']:
                    if keyword_lower == weapon_part_lower or weapon_part_lower.startswith(keyword_lower):
                        return category_id, category['name']
                else:
                    if keyword_lower in item_name_lower:
                        return category_id, category['name']

        return 'other', '其他'

    def classify_all_items(self, update_db: bool = True) -> dict:
        """分类所有商品"""
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

        logger.info("分类完成")
        return stats


# 全局实例
classifier = InvestmentClassifier()
item_classifier = ItemCategoryClassifier()
