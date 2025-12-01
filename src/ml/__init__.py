"""机器学习模块

包含趋势分析、投资分类和AI顾问。
"""
from .trend_analyzer import TrendAnalyzer
from .classifier import InvestmentClassifier, ItemCategoryClassifier
from .ai_advisor import AIAdvisor, ai_advisor

__all__ = [
    'TrendAnalyzer',
    'InvestmentClassifier', 
    'ItemCategoryClassifier',
    'AIAdvisor', 
    'ai_advisor'
]
