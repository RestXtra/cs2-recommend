"""价格趋势分析器

使用机器学习方法分析商品价格走势，提供预测和推荐评分。
"""
import numpy as np
from typing import Dict, List
from sklearn.linear_model import LinearRegression, Ridge
from sklearn.preprocessing import PolynomialFeatures
import warnings
import time

warnings.filterwarnings('ignore')

from ..core.database import mongo_client


class TrendAnalyzer:
    """价格趋势分析器"""

    def __init__(self):
        self._market_data_cache = None
        self._market_data_timestamp = 0

    def _get_market_data(self) -> Dict:
        """获取大盘数据（5分钟缓存）"""
        current_time = time.time()
        
        if self._market_data_cache and (current_time - self._market_data_timestamp) < 300:
            return self._market_data_cache

        try:
            collection = mongo_client.get_collection('homepage_data')
            latest = collection.find_one(sort=[('crawl_time', -1)])
            
            if not latest:
                return {}

            summary = latest.get('summary', {})
            chart_day = latest.get('chart_data_day', [])
            chart_hour = latest.get('chart_data_hour', [])

            market_analysis = {
                'index': summary.get('index', 0),
                'rise_fall_rate': summary.get('riseFallRate', 0),
            }

            # 7日趋势
            if chart_day:
                sorted_day = sorted(chart_day, key=lambda x: x['time'])
                recent_7d = sorted_day[-7:] if len(sorted_day) >= 7 else sorted_day
                if len(recent_7d) >= 2:
                    prices = [d['close'] for d in recent_7d]
                    market_analysis['market_7d_change'] = (prices[-1] - prices[0]) / prices[0] if prices[0] > 0 else 0
                    market_analysis['market_7d_trend'] = 'up' if prices[-1] > prices[0] else 'down'

            # 24小时波动
            if chart_hour:
                sorted_hour = sorted(chart_hour, key=lambda x: x['time'])
                recent_24h = sorted_hour[-24:] if len(sorted_hour) >= 24 else sorted_hour
                if len(recent_24h) >= 2:
                    prices = [d['close'] for d in recent_24h]
                    market_analysis['market_24h_volatility'] = np.std(prices) / np.mean(prices) if np.mean(prices) > 0 else 0

            self._market_data_cache = market_analysis
            self._market_data_timestamp = current_time
            return market_analysis

        except Exception:
            return {}

    def analyze(self, item: Dict) -> Dict:
        """分析商品趋势"""
        trend_data = item.get('trend_list', [])
        prices = self._extract_prices(trend_data)

        if len(prices) < 3:
            return self._default_analysis(item)

        market_data = self._get_market_data()
        
        basic_stats = self._calculate_basic_stats(prices)
        trend_analysis = self._analyze_trend(prices)
        volatility = self._calculate_volatility(prices)
        prediction = self._predict_price(prices)
        market_correlation = self._analyze_market_correlation(market_data)
        score = self._calculate_score(item, trend_analysis, volatility, prediction, market_data)

        return {
            **basic_stats,
            **trend_analysis,
            'volatility': volatility,
            **prediction,
            **market_correlation,
            'recommendation_score': score,
            'data_points': len(prices)
        }

    def _extract_prices(self, trend_data: List) -> np.ndarray:
        """提取价格数据"""
        if not trend_data:
            return np.array([])

        prices = []
        for point in trend_data:
            if isinstance(point, (list, tuple)) and len(point) >= 2:
                price = float(point[1]) if point[1] else 0
            elif isinstance(point, dict):
                price = point.get('price', 0)
            else:
                continue
            if price > 0:
                prices.append(price)

        return np.array(prices)

    def _calculate_basic_stats(self, prices: np.ndarray) -> Dict:
        """计算基础统计"""
        return {
            'price_mean': float(np.mean(prices)),
            'price_std': float(np.std(prices)),
            'price_min': float(np.min(prices)),
            'price_max': float(np.max(prices)),
            'price_current': float(prices[-1]),
            'price_change_30d': float((prices[-1] - prices[0]) / prices[0]) if prices[0] > 0 else 0
        }

    def _analyze_trend(self, prices: np.ndarray) -> Dict:
        """趋势分析"""
        n = len(prices)
        X = np.arange(n).reshape(-1, 1)
        
        model = LinearRegression()
        model.fit(X, prices)
        
        slope = model.coef_[0]
        r_squared = model.score(X, prices)
        
        if slope > 0.01 * np.mean(prices):
            direction = "上涨"
        elif slope < -0.01 * np.mean(prices):
            direction = "下跌"
        else:
            direction = "横盘"
        
        strength = abs(slope) / np.mean(prices) * r_squared
        
        momentum = 0
        if n >= 7:
            recent_avg = np.mean(prices[-7:])
            earlier_avg = np.mean(prices[:-7]) if n > 7 else prices[0]
            momentum = (recent_avg - earlier_avg) / earlier_avg if earlier_avg > 0 else 0
        
        return {
            'trend_direction': direction,
            'trend_slope': float(slope),
            'trend_strength': float(min(strength * 100, 100)),
            'trend_r_squared': float(r_squared),
            'momentum': float(momentum)
        }

    def _calculate_volatility(self, prices: np.ndarray) -> float:
        """计算波动性"""
        if len(prices) < 2:
            return 0.0
        returns = np.diff(prices) / prices[:-1]
        return float(np.std(returns))

    def _predict_price(self, prices: np.ndarray) -> Dict:
        """预测价格"""
        n = len(prices)
        X = np.arange(n).reshape(-1, 1)
        
        poly = PolynomialFeatures(degree=2)
        X_poly = poly.fit_transform(X)
        
        model = Ridge(alpha=1.0)
        model.fit(X_poly, prices)
        
        future_X = poly.transform([[n + 7]])
        predicted_price = max(model.predict(future_X)[0], 0)
        
        r_squared = model.score(X_poly, prices)
        data_confidence = min(n / 30, 1.0)
        confidence = r_squared * data_confidence
        
        return {
            'predicted_price': float(predicted_price),
            'prediction_days': 7,
            'confidence': float(confidence)
        }

    def _analyze_market_correlation(self, market_data: Dict) -> Dict:
        """分析市场相关性"""
        result = {
            'market_index': market_data.get('index', 0),
            'market_trend': market_data.get('market_7d_trend', 'unknown'),
            'market_7d_change': market_data.get('market_7d_change', 0),
            'market_24h_volatility': market_data.get('market_24h_volatility', 0),
            'market_sentiment': 'neutral'
        }

        rise_fall_rate = market_data.get('rise_fall_rate', 0)
        if rise_fall_rate > 1:
            result['market_sentiment'] = 'bullish'
        elif rise_fall_rate < -1:
            result['market_sentiment'] = 'bearish'

        return result

    def _calculate_score(self, item: Dict, trend: Dict, volatility: float, 
                         prediction: Dict, market_data: Dict = None) -> float:
        """计算推荐评分 (0-100)"""
        score = 50
        market_data = market_data or {}

        # 趋势加分
        if trend['trend_direction'] == "上涨":
            score += min(trend['trend_strength'], 20)
        elif trend['trend_direction'] == "下跌":
            score -= min(trend['trend_strength'], 20)

        # 动量加分
        score += trend['momentum'] * 10

        # 低波动加分
        if volatility < 0.05:
            score += 10
        elif volatility > 0.15:
            score -= 10

        # 求购比例加分
        buy_ratio = item.get('buy_ratio', 0)
        if buy_ratio > 1.0:
            score += min((buy_ratio - 1) * 20, 15)

        # 预测上涨加分
        current = item.get('steam_price', 0) or item.get('buff_price', 0)
        if current > 0 and prediction['predicted_price'] > current:
            upside = (prediction['predicted_price'] - current) / current
            score += min(upside * 50, 15) * prediction['confidence']

        # 大盘因素
        market_7d_change = market_data.get('market_7d_change', 0)
        
        if market_7d_change > 0 and trend['trend_direction'] == "上涨":
            score += 5
        elif market_7d_change < 0 and trend['trend_direction'] == "下跌":
            score -= 5

        if market_7d_change < -0.02 and trend['trend_direction'] == "上涨":
            score += 10  # 抗跌性加分

        return float(max(0, min(100, score)))

    def _default_analysis(self, item: Dict) -> Dict:
        """数据不足时的默认分析"""
        price = item.get('steam_price', 0) or item.get('buff_price', 0)
        market_data = self._get_market_data()

        return {
            'price_mean': price,
            'price_std': 0,
            'price_min': price,
            'price_max': price,
            'price_current': price,
            'price_change_30d': 0,
            'trend_direction': '未知',
            'trend_slope': 0,
            'trend_strength': 0,
            'trend_r_squared': 0,
            'momentum': 0,
            'volatility': 0,
            'predicted_price': price,
            'prediction_days': 7,
            'confidence': 0,
            'market_index': market_data.get('index', 0),
            'market_trend': market_data.get('market_7d_trend', 'unknown'),
            'market_7d_change': market_data.get('market_7d_change', 0),
            'market_24h_volatility': market_data.get('market_24h_volatility', 0),
            'market_sentiment': 'neutral',
            'recommendation_score': 50,
            'data_points': 0
        }
