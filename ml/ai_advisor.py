"""AI投资顾问 - 结合机器学习和大语言模型分析商品"""
import httpx
import numpy as np
import pandas as pd
from typing import Optional, Dict, List, Tuple
from loguru import logger
from pathlib import Path
import sys
import json

sys.path.insert(0, str(Path(__file__).parent.parent))
from utils.mongo_client import mongo_client
from utils.config import get_env
from ml.trend_analyzer import TrendAnalyzer

# 硅基流动API配置（从环境变量读取）
SILICONFLOW_API_URL = "https://api.siliconflow.cn/v1/chat/completions"
SILICONFLOW_MODEL = "deepseek-ai/DeepSeek-R1-0528-Qwen3-8B"


class AIAdvisor:
    """AI投资顾问"""
    
    def __init__(self):
        self.trend_analyzer = TrendAnalyzer()
        # 从环境变量读取 API 密钥
        self.api_key = get_env('SILICONFLOW_API_KEY', '')
        self.api_url = SILICONFLOW_API_URL
        self.model = SILICONFLOW_MODEL
        
        if not self.api_key:
            from loguru import logger
            logger.warning("未配置 SILICONFLOW_API_KEY，AI 分析功能将不可用")
    
    async def analyze_item(self, item_id: str) -> Dict:
        """分析单个商品
        
        Args:
            item_id: 商品ID
            
        Returns:
            包含ML分析和AI建议的字典
        """
        # 1. 从数据库获取商品数据
        items = mongo_client.find_items({'item_id': item_id}, limit=1)
        if not items:
            return {'error': '商品不存在'}
        item = items[0]
        
        # 2. 机器学习分析
        ml_analysis = self.trend_analyzer.analyze(item)
        
        # 3. 构建AI提示词
        prompt = self._build_prompt(item, ml_analysis)
        
        # 4. 调用大模型获取建议
        ai_response = await self._call_llm(prompt)
        
        return {
            'item_id': item_id,
            'item_name': item.get('name', ''),
            'ml_analysis': ml_analysis,
            'ai_advice': ai_response,
            'current_prices': {
                'steam': item.get('steam_price', 0),
                'buff': item.get('buff_price', 0),
                'youpin': item.get('youpin_price', 0),
                'c5': item.get('c5_price', 0)
            }
        }
    
    def _build_prompt(self, item: Dict, ml_analysis: Dict) -> str:
        """构建AI分析提示词"""
        trend_data = item.get('trend_list', [])
        trend_desc = self._describe_trend(trend_data)
        
        prompt = f"""你是一个专业的CS2饰品投资顾问。请根据以下商品数据进行分析，给出投资建议。

## 商品信息
- 名称：{item.get('name', '未知')}
- 武器类型：{item.get('weapon_type', '未知')}
- 品质：{item.get('quality', '未知')}
- 稀有度：{item.get('rarity', '未知')}
- 外观：{item.get('exterior', '未知')}

## 当前价格（人民币）
- Steam市场价：¥{item.get('steam_price', 0):.2f}
- BUFF价格：¥{item.get('buff_price', 0):.2f}
- 悠悠有品价格：¥{item.get('youpin_price', 0):.2f}
- C5价格：¥{item.get('c5_price', 0):.2f}

## 市场指标
- 在售数量：{item.get('sell_num', 0)}
- 求购比例：{item.get('buy_ratio', 0):.2%}
- 求购稳定度：{item.get('buy_stable', 0):.2f}
- 寄售比例：{item.get('sell_ratio', 0):.2%}

## 机器学习分析结果
- 趋势方向：{ml_analysis.get('trend_direction', '未知')}
- 趋势强度：{ml_analysis.get('trend_strength', 0):.2f}
- 波动性：{ml_analysis.get('volatility', 0):.2%}
- 预测下周价格：¥{ml_analysis.get('predicted_price', 0):.2f}
- 置信度：{ml_analysis.get('confidence', 0):.0%}
- ML推荐评分：{ml_analysis.get('recommendation_score', 0):.0f}/100

## 大盘行情（CS2饰品市场整体）
- 大盘指数：{ml_analysis.get('market_index', 0):.2f}
- 7日涨跌幅：{ml_analysis.get('market_7d_change', 0):.2%}
- 大盘趋势：{self._format_market_trend(ml_analysis.get('market_trend', 'unknown'))}
- 24小时波动率：{ml_analysis.get('market_24h_volatility', 0):.2%}
- 市场情绪：{self._format_market_sentiment(ml_analysis.get('market_sentiment', 'neutral'))}

## 近30天价格走势
{trend_desc}

请给出：
1. **市场分析**：结合大盘行情分析当前市场状态和价格合理性
2. **投资建议**：是否建议买入/持有/卖出，需考虑大盘趋势
3. **加仓策略**：如果建议买入，给出分批建仓的具体策略
4. **风险提示**：主要风险因素，包括大盘风险
5. **目标价位**：短期(1周)和中期(1月)目标价

注意：请综合考虑大盘走势对该商品的影响，给出专业的分析意见。请用简洁专业的语言回答，直接给出结论和建议。"""
        
        return prompt

    def _format_market_trend(self, trend: str) -> str:
        """格式化大盘趋势"""
        if trend == 'up':
            return '上涨'
        elif trend == 'down':
            return '下跌'
        return '横盘震荡'

    def _format_market_sentiment(self, sentiment: str) -> str:
        """格式化市场情绪"""
        if sentiment == 'bullish':
            return '牛市（乐观）'
        elif sentiment == 'bearish':
            return '熊市（悲观）'
        return '中性震荡'

    def _describe_trend(self, trend_data: List) -> str:
        """描述价格走势"""
        if not trend_data or len(trend_data) < 2:
            return "暂无足够的历史数据"

        # 支持两种格式：[timestamp, price] 或 {price: xx}
        prices = []
        for t in trend_data:
            if isinstance(t, (list, tuple)) and len(t) >= 2:
                price = float(t[1]) if t[1] else 0
            elif isinstance(t, dict):
                price = t.get('price', 0)
            else:
                continue
            if price > 0:
                prices.append(price)

        if len(prices) < 2:
            return "暂无有效的价格数据"
        
        start_price = prices[0]
        end_price = prices[-1]
        max_price = max(prices)
        min_price = min(prices)
        change_pct = (end_price - start_price) / start_price * 100 if start_price > 0 else 0
        
        return f"""- 起始价格：¥{start_price:.2f}
- 当前价格：¥{end_price:.2f}
- 最高价格：¥{max_price:.2f}
- 最低价格：¥{min_price:.2f}
- 30天涨跌幅：{change_pct:+.1f}%
- 数据点数量：{len(prices)}"""

    async def _call_llm(self, prompt: str) -> str:
        """调用硅基流动API"""
        if not self.api_key:
            return "AI 分析不可用：未配置 SILICONFLOW_API_KEY 环境变量"
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": "你是专业的CS2饰品投资分析师，擅长分析市场趋势和给出投资建议。"},
                {"role": "user", "content": prompt}
            ],
            "max_tokens": 2048,
            "temperature": 0.7,
            "enable_thinking": False
        }
        
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(self.api_url, headers=headers, json=payload)
                response.raise_for_status()
                result = response.json()
                return result['choices'][0]['message']['content']
        except Exception as e:
            logger.error(f"调用AI API失败: {e}")
            return f"AI分析暂时不可用: {str(e)}"


# 全局实例
ai_advisor = AIAdvisor()

