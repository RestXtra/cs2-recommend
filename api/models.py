"""API数据模型"""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class TaskCreate(BaseModel):
    """创建任务请求"""
    name: str = Field(..., description="任务名称")
    urls: List[str] = Field(..., description="URL列表")
    description: Optional[str] = Field(None, description="任务描述")


class TaskResponse(BaseModel):
    """任务响应"""
    task_id: str
    name: str
    status: str
    created_at: str
    message: str


class ItemQuery(BaseModel):
    """商品查询请求"""
    page: int = Field(1, ge=1, description="页码")
    page_size: int = Field(20, ge=1, le=100, description="每页数量")
    is_recommended: Optional[bool] = Field(None, description="是否推荐")
    is_favorited: Optional[bool] = Field(None, description="是否收藏")
    price_min: Optional[float] = Field(None, description="最低价格")
    price_max: Optional[float] = Field(None, description="最高价格")
    sell_ratio_min: Optional[float] = Field(None, description="最低在售比例")
    sell_ratio_max: Optional[float] = Field(None, description="最高在售比例")
    buy_ratio_min: Optional[float] = Field(None, description="最低求购比例")
    buy_ratio_max: Optional[float] = Field(None, description="最高求购比例")
    weapon_type: Optional[List[str]] = Field(None, description="武器类型(支持多选)")
    exterior: Optional[List[str]] = Field(None, description="外观(支持多选)")
    quality: Optional[List[str]] = Field(None, description="品质(支持多选)")
    rarity: Optional[List[str]] = Field(None, description="稀有度(支持多选)")
    category: Optional[List[str]] = Field(None, description="类别(武器分类，支持多选)")
    sticker: Optional[List[str]] = Field(None, description="印花类型(支持多选)")
    case_type: Optional[List[str]] = Field(None, description="箱子类型(支持多选)")
    keyword: Optional[str] = Field(None, description="关键词搜索")
    sort_by: Optional[str] = Field("updated_at", description="排序字段")
    order: Optional[str] = Field("desc", description="排序方向")


class ItemResponse(BaseModel):
    """商品响应"""
    item_id: str
    name: str
    image_url: Optional[str]
    steam_price: float
    buff_price: float
    youpin_price: float
    csgame_price: float
    buy_ratio: float
    buy_stable: float
    sell_ratio: float
    is_recommended: bool
    is_favorited: bool
    recommendation_score: float
    recommendation_reason: Optional[str]
    trend_list: Optional[List]
    updated_at: str


class ItemListResponse(BaseModel):
    """商品列表响应"""
    total: int
    page: int
    page_size: int
    items: List[ItemResponse]


class StatsResponse(BaseModel):
    """统计响应"""
    crawler_stats: dict
    items_stats: dict
    top_items: List[dict]


class ConfigUpdate(BaseModel):
    """配置更新请求"""
    key: str = Field(..., description="配置键")
    value: str = Field(..., description="配置值")


class Response(BaseModel):
    """通用响应"""
    code: int = Field(0, description="状态码，0表示成功")
    message: str = Field("success", description="消息")
    data: Optional[dict] = Field(None, description="数据")

