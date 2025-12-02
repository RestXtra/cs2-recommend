"""FastAPI主应用"""
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse, FileResponse, HTMLResponse
from typing import Optional
import sys
from pathlib import Path
import uvicorn

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from api.models import (
    TaskCreate, TaskResponse, ItemQuery, ItemResponse, 
    ItemListResponse, StatsResponse, ConfigUpdate, Response
)
from utils.config import config
from utils.redis_client import redis_client
from utils.mongo_client import mongo_client
from monitor.stats import stats_collector
from monitor.logger import logger
import json
from datetime import datetime
import subprocess
import threading

# 爬虫服务类
class CrawlerService:
    def __init__(self):
        self.process = None
        self.log_queue = []
        self.is_running = False
        self.lock = threading.Lock()

    def start(self, delay=1.5, pages=0):
        with self.lock:
            if self.is_running:
                return False, "爬虫已经在运行中"
            
            try:
                cmd = [
                    sys.executable,
                    str(Path(__file__).parent.parent / "scripts" / "crawl_all_enhanced.py"),
                    "--delay", str(delay),
                    "--continue"
                ]
                if pages > 0:
                    cmd.extend(["--pages", str(pages)])
                
                self.process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                    cwd=str(Path(__file__).parent.parent)
                )
                self.is_running = True
                
                # 启动日志读取线程
                threading.Thread(target=self._read_logs, daemon=True).start()
                return True, "爬虫已启动"
            except Exception as e:
                self.is_running = False
                return False, f"启动失败: {str(e)}"

    def stop(self):
        with self.lock:
            if not self.is_running or not self.process:
                return False, "爬虫未运行"
            
            try:
                self.process.terminate()
                # 不在这里wait，避免阻塞API
                threading.Thread(target=self._wait_stop, args=(self.process,), daemon=True).start()
                self.is_running = False
                self.process = None
                return True, "正在停止爬虫..."
            except Exception as e:
                return False, f"停止失败: {str(e)}"

    def _wait_stop(self, process):
        try:
            process.wait(timeout=5)
        except:
            try:
                process.kill()
            except:
                pass

    def _read_logs(self):
        if not self.process:
            return
            
        try:
            for line in self.process.stdout:
                line = line.strip()
                if line:
                    timestamp = datetime.now().strftime('%H:%M:%S')
                    # 过滤掉一些无用的日志前缀
                    if " | " in line:
                        parts = line.split(" | ", 2)
                        if len(parts) >= 3:
                            line = parts[2]
                    
                    self.log_queue.append(f"[{timestamp}] {line}")
                    if len(self.log_queue) > 500:  # 保留最近500行
                        self.log_queue.pop(0)
        except Exception as e:
            self.log_queue.append(f"日志读取错误: {e}")
        finally:
            with self.lock:
                self.is_running = False
                self.process = None
            self.log_queue.append(f"[{datetime.now().strftime('%H:%M:%S')}] 爬虫运行结束")

    def get_logs(self):
        return self.log_queue

    def get_status(self):
        return {
            "is_running": self.is_running,
            "pid": self.process.pid if self.process else None
        }

crawler_service = CrawlerService()

# 创建FastAPI应用
app = FastAPI(
    title="CS2市场爬虫管理系统",
    description="分布式爬虫系统管理API",
    version="1.0.0"
)

# 配置CORS
cors_origins = config.get('api_server.cors_origins', ['*'])
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 挂载静态文件
images_dir = Path(__file__).parent.parent / 'data' / 'images'
if images_dir.exists():
    app.mount("/images", StaticFiles(directory=str(images_dir)), name="images")


@app.get("/api/health")
async def health_check():
    """健康检查"""
    health_status = {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "services": {}
    }

    # 检查Redis
    try:
        redis_client.client.ping()
        health_status["services"]["redis"] = "ok"
    except Exception as e:
        health_status["services"]["redis"] = f"error: {str(e)}"
        health_status["status"] = "unhealthy"

    # 检查MongoDB
    try:
        mongo_client.db.command('ping')
        health_status["services"]["mongodb"] = "ok"
    except Exception as e:
        health_status["services"]["mongodb"] = f"error: {str(e)}"
        health_status["status"] = "unhealthy"

    return health_status





@app.post("/api/tasks/create", response_model=Response)
async def create_task(task: TaskCreate):
    """创建爬取任务"""
    try:
        # 将URL添加到Redis队列
        if task.urls:
            # 构建请求数据
            for url in task.urls:
                request_data = {
                    "url": url,
                    "meta": {
                        "task_name": task.name,
                        "task_description": task.description
                    }
                }
                redis_client.push_start_url(json.dumps(request_data))
            
            logger.info(f"任务创建成功: {task.name}, URL数量: {len(task.urls)}")
            
            return Response(
                code=0,
                message="任务创建成功",
                data={
                    "task_id": f"task_{int(datetime.now().timestamp())}",
                    "name": task.name,
                    "url_count": len(task.urls),
                    "status": "queued"
                }
            )
        else:
            raise HTTPException(status_code=400, detail="URL列表不能为空")
    
    except Exception as e:
        logger.error(f"创建任务失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/tasks/queue")
async def get_queue_info():
    """获取队列信息"""
    try:
        stats = redis_client.get_stats()
        return Response(
            code=0,
            message="success",
            data=stats
        )
    except Exception as e:
        logger.error(f"获取队列信息失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/tasks/queue")
async def clear_queue():
    """清空队列"""
    try:
        redis_client.clear_queue()
        redis_client.clear_dupefilter()
        
        logger.info("队列已清空")
        
        return Response(
            code=0,
            message="队列已清空",
            data={}
        )
    except Exception as e:
        logger.error(f"清空队列失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# GET 版本的商品查询接口（供前端使用）
@app.get("/api/items/query", response_model=Response)
async def query_items_get(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    keyword: Optional[str] = None,
    recommend_only: bool = False,
    min_price: Optional[float] = None,
    max_price: Optional[float] = None
):
    """GET方式查询商品"""
    try:
        filter_query = {}
        
        if recommend_only:
            filter_query['is_recommended'] = True
        
        if min_price is not None or max_price is not None:
            filter_query['steam_price'] = {}
            if min_price is not None:
                filter_query['steam_price']['$gte'] = min_price
            if max_price is not None:
                filter_query['steam_price']['$lte'] = max_price
        
        if keyword:
            filter_query['name'] = {'$regex': keyword, '$options': 'i'}
        
        skip = (page - 1) * page_size
        sort = [('recommendation_score', -1)]
        
        items = mongo_client.find_items(
            query=filter_query,
            limit=page_size,
            skip=skip,
            sort=sort
        )
        
        total = mongo_client.count_items(filter_query)
        
        items_data = []
        for item in items:
            items_data.append({
                'item_id': item.get('item_id', ''),
                'name': item.get('name', ''),
                'image_url': item.get('image_url', ''),
                'steam_price': item.get('steam_price', 0),
                'buff_price': item.get('buff_price', 0),
                'steam_buff_ratio': round(item.get('sell_ratio', 0), 2),
                'exterior': item.get('exterior', ''),
                'is_recommended': item.get('is_recommended', False),
                'steam_url': f"https://steamcommunity.com/market/listings/730/{item.get('name', '')}",
                'buff_url': f"https://buff.163.com/goods/{item.get('item_id', '')}"
            })
        
        return Response(
            code=0,
            message="success",
            data={
                'total': total,
                'page': page,
                'page_size': page_size,
                'items': items_data
            }
        )
    except Exception as e:
        logger.error(f"查询商品失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/items/query", response_model=Response)
async def query_items(query: ItemQuery):
    """查询商品"""
    try:
        # 构建查询条件
        filter_query = {}

        if query.is_recommended is not None:
            filter_query['is_recommended'] = query.is_recommended

        if query.is_favorited is not None:
            filter_query['is_favorited'] = query.is_favorited

        # 价格筛选
        if query.price_min is not None or query.price_max is not None:
            filter_query['steam_price'] = {}
            if query.price_min is not None:
                filter_query['steam_price']['$gte'] = query.price_min
            if query.price_max is not None:
                filter_query['steam_price']['$lte'] = query.price_max

        # 在售比例筛选
        if query.sell_ratio_min is not None or query.sell_ratio_max is not None:
            filter_query['sell_ratio'] = {}
            if query.sell_ratio_min is not None:
                filter_query['sell_ratio']['$gte'] = query.sell_ratio_min
            if query.sell_ratio_max is not None:
                filter_query['sell_ratio']['$lte'] = query.sell_ratio_max

        # 求购比例筛选
        if query.buy_ratio_min is not None or query.buy_ratio_max is not None:
            filter_query['buy_ratio'] = {}
            if query.buy_ratio_min is not None:
                filter_query['buy_ratio']['$gte'] = query.buy_ratio_min
            if query.buy_ratio_max is not None:
                filter_query['buy_ratio']['$lte'] = query.buy_ratio_max

        # 武器类型筛选（支持多选数组）
        if query.weapon_type and len(query.weapon_type) > 0:
            # 特殊处理：探员、印花、武器箱等非武器类型，查询weapon_category而不是weapon_type
            special_categories = ['探员', '印花', '武器箱', '音乐盒', '布章', '涂鸦', '挂件']
            weapon_conditions = []
            category_conditions = []

            for wt in query.weapon_type:
                if wt in special_categories:
                    category_conditions.append(wt)
                else:
                    weapon_conditions.append({'weapon_type': {'$regex': wt, '$options': 'i'}})

            if category_conditions:
                weapon_conditions.append({'weapon_category': {'$in': category_conditions}})

            if len(weapon_conditions) == 1:
                filter_query.update(weapon_conditions[0])
            elif len(weapon_conditions) > 1:
                if '$or' not in filter_query:
                    filter_query['$or'] = []
                filter_query['$or'].extend(weapon_conditions)

        # 类别筛选（weapon_category，支持多选）
        if query.category and len(query.category) > 0:
            filter_query['weapon_category'] = {'$in': query.category}

        # 外观筛选（支持多选）
        if query.exterior and len(query.exterior) > 0:
            filter_query['exterior'] = {'$in': query.exterior}

        # 品质筛选（支持多选）
        if query.quality and len(query.quality) > 0:
            filter_query['quality'] = {'$in': query.quality}

        # 稀有度筛选（支持多选）
        if query.rarity and len(query.rarity) > 0:
            filter_query['rarity'] = {'$in': query.rarity}

        # 箱子类型筛选（支持多选）
        if query.case_type and len(query.case_type) > 0:
            case_regex = '|'.join(query.case_type)
            filter_query['name'] = {'$regex': case_regex, '$options': 'i'}

        # 印花类型筛选（支持多选）
        if query.sticker and len(query.sticker) > 0:
            sticker_regex = '|'.join(query.sticker)
            if 'name' in filter_query:
                filter_query['$and'] = [
                    {'name': filter_query['name']},
                    {'name': {'$regex': sticker_regex, '$options': 'i'}}
                ]
                del filter_query['name']
            else:
                filter_query['name'] = {'$regex': sticker_regex, '$options': 'i'}

        # 关键词搜索
        if query.keyword:
            if 'name' in filter_query:
                filter_query['$and'] = filter_query.get('$and', [])
                filter_query['$and'].append({'name': {'$regex': query.keyword, '$options': 'i'}})
            elif '$and' in filter_query:
                filter_query['$and'].append({'name': {'$regex': query.keyword, '$options': 'i'}})
            else:
                filter_query['name'] = {'$regex': query.keyword, '$options': 'i'}
        
        # 计算分页
        skip = (query.page - 1) * query.page_size
        
        # 排序
        sort_order = -1 if query.order == 'desc' else 1
        sort = [(query.sort_by, sort_order)]
        
        # 查询数据
        items = mongo_client.find_items(
            query=filter_query,
            limit=query.page_size,
            skip=skip,
            sort=sort
        )
        
        # 统计总数
        total = mongo_client.count_items(filter_query)
        
        # 格式化响应
        items_data = []
        for item in items:
            # 解析趋势数据
            trend_list = []
            # 优先使用trend_list字段（数组），如果没有则尝试解析trend_data字段（字符串）
            if item.get('trend_list'):
                trend_list = item.get('trend_list', [])
            elif item.get('trend_data'):
                try:
                    import json as json_lib
                    trend_list = json_lib.loads(item.get('trend_data', '[]'))
                except:
                    trend_list = []

            items_data.append({
                'item_id': item.get('item_id', ''),
                'name': item.get('name', ''),
                'image_url': item.get('image_url', ''),
                'steam_price': item.get('steam_price', 0),
                'buff_price': item.get('buff_price', 0),
                'youpin_price': item.get('youpin_price', 0),
                'c5_price': item.get('c5_price', 0),
                'buy_ratio': item.get('buy_ratio', 0),
                'buy_stable': item.get('buy_stable', 0),
                'sell_ratio': item.get('sell_ratio', 0),
                'sell_num': item.get('sell_num', 0),
                'is_recommended': item.get('is_recommended', False),
                'is_favorited': item.get('is_favorited', False),
                'recommendation_score': item.get('recommendation_score', 0),
                'recommendation_reason': item.get('recommendation_reason', ''),
                'trend_list': trend_list,
                'weapon_type': item.get('weapon_type', ''),
                'exterior': item.get('exterior', ''),
                'quality': item.get('quality', ''),
                'rarity': item.get('rarity', ''),
                'updated_at': item.get('updated_at', datetime.now()).isoformat() if hasattr(item.get('updated_at'), 'isoformat') else str(item.get('updated_at', ''))
            })
        
        return Response(
            code=0,
            message="success",
            data={
                'total': total,
                'page': query.page,
                'page_size': query.page_size,
                'items': items_data
            }
        )
    
    except Exception as e:
        logger.error(f"查询商品失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/stats", response_model=Response)
async def get_stats():
    """获取统计信息"""
    try:
        # 调试：直接查询MongoDB
        collection = mongo_client.get_collection('items')
        direct_count = collection.count_documents({})
        logger.info(f"直接查询MongoDB: {direct_count} 个商品")

        crawler_stats = stats_collector.get_crawler_stats()
        items_stats = stats_collector.get_items_stats()
        top_items = stats_collector.get_top_items(limit=10)

        logger.info(f"stats_collector返回: {items_stats['total_count']} 个商品")

        return Response(
            code=0,
            message="success",
            data={
                'crawler_stats': crawler_stats,
                'items_stats': items_stats,
                'top_items': top_items
            }
        )
    except Exception as e:
        logger.error(f"获取统计信息失败: {e}")
        import traceback
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/stats/history")
async def get_history_stats(days: int = Query(7, ge=1, le=30)):
    """获取历史统计"""
    try:
        history = stats_collector.get_history_stats(days=days)

        return Response(
            code=0,
            message="success",
            data={'history': history}
        )
    except Exception as e:
        logger.error(f"获取历史统计失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/stats/homepage")
async def get_homepage_stats():
    """获取首页大盘统计数据"""
    try:
        collection = mongo_client.get_collection('items')
        
        # 统计数据
        total = collection.count_documents({})
        recommended = collection.count_documents({'is_recommended': True})
        
        # 计算涨跌统计（基于 sell_ratio）
        up_count = collection.count_documents({'sell_ratio': {'$gt': 0.8}})
        down_count = collection.count_documents({'sell_ratio': {'$lt': 0.7}})
        flat_count = total - up_count - down_count
        
        # 模拟指数（可以基于实际数据计算）
        index_value = 1000 + (recommended * 0.1)
        
        return {
            "code": 0,
            "message": "success",
            "data": {
                "summary": {
                    "index_value": round(index_value, 2),
                    "rise_fall_diff": round((recommended - total * 0.3) * 0.01, 2),
                    "rise_fall_rate": round((recommended / max(total, 1)) * 100, 2),
                    "volume": total,
                    "up_count": up_count,
                    "flat_count": flat_count,
                    "down_count": down_count,
                    "update_time": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                }
            }
        }
    except Exception as e:
        logger.error(f"获取首页统计失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/items/{item_id}")
async def get_item_detail(item_id: str):
    """获取商品详情"""
    try:
        item = mongo_client.get_collection('items').find_one({'item_id': item_id})

        if not item:
            raise HTTPException(status_code=404, detail="商品不存在")

        # 移除MongoDB的_id字段
        if '_id' in item:
            del item['_id']

        # 格式化日期
        for field in ['created_at', 'updated_at', 'crawled_at']:
            if field in item and hasattr(item[field], 'isoformat'):
                item[field] = item[field].isoformat()

        return Response(
            code=0,
            message="success",
            data=item
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取商品详情失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/config")
async def get_config():
    """获取配置"""
    return config

# 爬虫控制API
@app.post("/api/crawler/start")
async def start_crawler(delay: float = 1.5, pages: int = 0):
    """启动爬虫"""
    success, message = crawler_service.start(delay, pages)
    return {"success": success, "message": message}

@app.post("/api/crawler/stop")
async def stop_crawler():
    """停止爬虫"""
    success, message = crawler_service.stop()
    return {"success": success, "message": message}

@app.get("/api/crawler/status")
async def get_crawler_status():
    """获取爬虫状态"""
    return crawler_service.get_status()

@app.get("/api/crawler/logs")
async def get_crawler_logs():
    """获取爬虫日志"""
    return {"logs": crawler_service.get_logs()}


@app.post("/api/config/update")
async def update_config(config_update: ConfigUpdate):
    """更新配置"""
    try:
        # 只允许更新特定配置
        allowed_keys = [
            'spider.concurrent_requests',
            'spider.download_delay',
            'ml.filter.min_buy_ratio',
            'ml.filter.min_buy_stable',
            'monitor.logging.level'
        ]

        if config_update.key not in allowed_keys:
            raise HTTPException(status_code=400, detail="不允许修改此配置项")

        # 更新配置
        config.set(config_update.key, config_update.value)

        logger.info(f"配置已更新: {config_update.key} = {config_update.value}")

        return Response(
            code=0,
            message="配置更新成功",
            data={
                'key': config_update.key,
                'value': config_update.value
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"更新配置失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/items/{item_id}/favorite")
async def toggle_favorite(item_id: str):
    """切换收藏状态"""
    try:
        collection = mongo_client.get_collection('items')
        item = collection.find_one({'item_id': item_id})

        if not item:
            raise HTTPException(status_code=404, detail="商品不存在")

        # 切换收藏状态
        new_status = not item.get('is_favorited', False)
        collection.update_one(
            {'item_id': item_id},
            {'$set': {'is_favorited': new_status}}
        )

        logger.info(f"商品收藏状态已更新: {item_id} -> {new_status}")

        return Response(
            code=0,
            message="success",
            data={'is_favorited': new_status}
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"切换收藏失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# AI分析接口
@app.post("/api/items/analyze")
async def analyze_item(item_id: str = Query(..., description="商品ID")):
    """AI分析商品投资价值"""
    try:
        from ml.ai_advisor import ai_advisor

        result = await ai_advisor.analyze_item(item_id)

        if 'error' in result:
            return Response(code=404, message=result['error'], data=None)

        return Response(
            code=0,
            message="success",
            data=result
        )
    except Exception as e:
        logger.error(f"AI分析失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ML趋势分析接口（不调用大模型，仅机器学习分析）
@app.post("/api/items/ml-analyze")
async def ml_analyze_item(item_id: str = Query(..., description="商品ID")):
    """机器学习分析商品趋势"""
    try:
        from ml.trend_analyzer import TrendAnalyzer

        items = mongo_client.find_items({'item_id': item_id}, limit=1)
        if not items:
            return Response(code=404, message="商品不存在", data=None)
        item = items[0]

        analyzer = TrendAnalyzer()
        analysis = analyzer.analyze(item)

        return Response(
            code=0,
            message="success",
            data={
                'item_id': item_id,
                'item_name': item.get('name', ''),
                'analysis': analysis
            }
        )
    except Exception as e:
        logger.error(f"ML分析失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# LSTM价格预测接口
@app.post("/api/items/predict")
async def predict_item_price(item_id: str = Query(..., description="商品ID"),
                              days: int = Query(7, description="预测天数")):
    """LSTM深度学习价格预测"""
    try:
        from ml.lstm_predictor import predict_item_price as lstm_predict

        result = lstm_predict(item_id, days)

        if not result.get('success'):
            return Response(code=404, message=result.get('error', '预测失败'), data=None)

        return Response(
            code=0,
            message="success",
            data=result
        )
    except Exception as e:
        logger.error(f"LSTM价格预测失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# LSTM模型训练接口
@app.post("/api/items/train-model")
async def train_prediction_model(item_id: str = Query(..., description="商品ID"),
                                   epochs: int = Query(50, description="训练轮数")):
    """训练LSTM价格预测模型"""
    try:
        from ml.lstm_predictor import train_model_for_item

        result = train_model_for_item(item_id, epochs)

        if not result.get('success'):
            return Response(code=400, message=result.get('error', '训练失败'), data=None)

        return Response(
            code=0,
            message="模型训练完成",
            data=result
        )
    except Exception as e:
        logger.error(f"模型训练失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/homepage/latest")
async def get_homepage_latest():
    """获取最新的首页数据"""
    try:
        # 从 homepage_data 集合获取最新数据
        collection = mongo_client.get_collection('homepage_data')
        latest = collection.find_one(sort=[('crawl_time', -1)])

        if not latest:
            return JSONResponse(
                status_code=404,
                content={
                    "code": 404,
                    "message": "暂无首页数据，请先运行 python scripts/crawl_homepage.py",
                    "data": None
                }
            )

        # 移除 MongoDB 的 _id 字段
        latest.pop('_id', None)

        return {
            "code": 0,
            "message": "success",
            "data": latest
        }
    except Exception as e:
        logger.error(f"获取首页数据失败: {e}")
        return JSONResponse(
            status_code=500,
            content={
                "code": 500,
                "message": f"获取首页数据失败: {str(e)}",
                "data": None
            }
        )


@app.get("/api/categories")
async def get_categories():
    """获取商品类别列表及统计"""
    try:
        from ml.classifier import item_classifier

        collection = mongo_client.get_collection('items')

        # 统计每个类别的商品数量
        categories = []
        for cat_id, cat_info in item_classifier.CATEGORIES.items():
            count = collection.count_documents({'weapon_category': cat_id})
            if count > 0:
                categories.append({
                    'id': cat_id,
                    'name': cat_info['name'],
                    'count': count
                })

        # 按数量排序
        categories.sort(key=lambda x: -x['count'])

        return {
            "code": 0,
            "message": "success",
            "data": categories
        }
    except Exception as e:
        logger.error(f"获取类别列表失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/items/reclassify")
async def reclassify_items():
    """重新分类所有商品"""
    try:
        from ml.classifier import item_classifier

        stats = item_classifier.classify_all_items(update_db=True)

        return {
            "code": 0,
            "message": "分类完成",
            "data": stats
        }
    except Exception as e:
        logger.error(f"重新分类失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============ 静态文件服务 ============
# 注意：这些路由必须放在所有 API 路由之后

web_dir = Path(__file__).parent.parent / 'web'

@app.get("/", response_class=HTMLResponse)
async def serve_index():
    """服务首页"""
    index_file = web_dir / 'index.html'
    if index_file.exists():
        return FileResponse(index_file)
    return HTMLResponse("<h1>Welcome to CS2 Market API</h1><p>Visit <a href='/docs'>/docs</a> for API documentation.</p>")

# 挂载静态资源到 /static 路径（CSS, JS 等）
if web_dir.exists():
    app.mount("/static", StaticFiles(directory=str(web_dir)), name="static")


if __name__ == "__main__":
    # 获取API服务配置
    api_config = config.api_server

    uvicorn.run(
        "main:app",
        host=api_config.get('host', '0.0.0.0'),
        port=api_config.get('port', 8008),
        reload=api_config.get('reload', True),
        log_level="info"
    )

