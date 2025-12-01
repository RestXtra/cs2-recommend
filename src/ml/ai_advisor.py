"""AI 投资顾问

结合机器学习和大语言模型分析商品投资价值。
使用硅基流动 API 调用 DeepSeek 模型。
"""
import httpx
from typing import Dict, List
from loguru import logger

from ..core.config import config, get_env
from ..core.database import mongo_client
from .trend_analyzer import TrendAnalyzer


class AIAdvisor:
    """AI 投资顾问"""
    
    # API 配置
    API_URL = "https://api.siliconflow.cn/v1/chat/completions"
    MODEL = "deepseek-ai/DeepSeek-R1-0528-Qwen3-8B"
    
    def __init__(self):
        self.trend_analyzer = TrendAnalyzer()
    
    @property
    def api_key(self) -> str:
        """获取 API 密钥（优先从环境变量读取）"""
        key = get_env('SILICONFLOW_API_KEY')
        if not key:
            key = config.get('ai.siliconflow.api_key', '')
        if not key:
            logger.warning("未配置 SILICONFLOW_API_KEY，AI 分析功能将不可用")
        return key
    
    async def analyze_item(self, item_id: str) -> Dict:
        """分析单个商品"""
        items = mongo_client.find_items({'item_id': item_id}, limit=1)
        if not items:
            return {'error': '商品不存在'}
        
        item = items[0]
        ml_analysis = self.trend_analyzer.analyze(item)
        prompt = self._build_prompt(item, ml_analysis)
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
        """构建 AI 分析提示词"""
        trend_desc = self._describe_trend(item.get('trend_list', []))
        
        return f"""你是一个专业的CS2饰品投资顾问。请根据以下商品数据进行分析，给出投资建议。

## 商品信息
- 名称：{item.get('name', '未知')}
- 武器类型：{item.get('weapon_type', '未知')}
- 品质：{item.get('quality', '未知')}
- 稀有度：{item.get('rarity', '未知')}

## 当前价格（人民币）
- Steam市场价：¥{item.get('steam_price', 0):.2f}
- BUFF价格：¥{item.get('buff_price', 0):.2f}

## 市场指标
- 在售数量：{item.get('sell_num', 0)}
- 求购比例：{item.get('buy_ratio', 0):.2%}
- 求购稳定度：{item.get('buy_stable', 0):.2f}

## 机器学习分析结果
- 趋势方向：{ml_analysis.get('trend_direction', '未知')}
- 趋势强度：{ml_analysis.get('trend_strength', 0):.2f}
- 预测下周价格：¥{ml_analysis.get('predicted_price', 0):.2f}
- 置信度：{ml_analysis.get('confidence', 0):.0%}
- ML推荐评分：{ml_analysis.get('recommendation_score', 0):.0f}/100

## 近30天价格走势
{trend_desc}

请给出：
1. **市场分析**：当前价格合理性
2. **投资建议**：买入/持有/卖出
3. **风险提示**：主要风险因素
4. **目标价位**：短期(1周)和中期(1月)

请用简洁专业的语言回答。"""

    def _describe_trend(self, trend_data: List) -> str:
        """描述价格走势"""
        if not trend_data or len(trend_data) < 2:
            return "暂无足够的历史数据"

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
        change_pct = (end_price - start_price) / start_price * 100 if start_price > 0 else 0
        
        return f"""- 起始价格：¥{start_price:.2f}
- 当前价格：¥{end_price:.2f}
- 30天涨跌幅：{change_pct:+.1f}%
- 数据点数量：{len(prices)}"""

    async def _call_llm(self, prompt: str) -> str:
        """调用大模型 API"""
        if not self.api_key:
            return "AI 分析不可用：未配置 API 密钥"
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": self.MODEL,
            "messages": [
                {"role": "system", "content": "你是专业的CS2饰品投资分析师。"},
                {"role": "user", "content": prompt}
            ],
            "max_tokens": 2048,
            "temperature": 0.7,
            "enable_thinking": False
        }
        
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(self.API_URL, headers=headers, json=payload)
                response.raise_for_status()
                result = response.json()
                return result['choices'][0]['message']['content']
        except Exception as e:
            logger.error(f"调用 AI API 失败: {e}")
            return f"AI 分析暂时不可用: {str(e)}"


# 全局实例
ai_advisor = AIAdvisor()
