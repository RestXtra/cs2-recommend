# 快速启动指南

## 🚀 一键启动所有服务

```bash
python scripts/start_all.py
```

这个命令会自动完成以下操作：

1. ✅ 检查 Redis 和 MongoDB 服务
2. ✅ 抓取首页大盘数据（时K + 日K）
3. ✅ 启动 API 服务（端口 8008）
4. ✅ 启动 Web 服务（端口 3000）
5. ✅ 启动监控窗口
6. ✅ 启动爬虫
7. ✅ 自动打开浏览器

## 📡 服务端口

| 服务 | 端口 | 地址 |
|------|------|------|
| API 服务 | 8008 | http://localhost:8008 |
| Web 服务 | 3000 | http://localhost:3000 |
| 首页大盘 | 3000 | http://localhost:3000/homepage.html |
| 饰品市场 | 3000 | http://localhost:3000/index.html |

## 🎯 首页大盘功能

访问 http://localhost:3000/homepage.html 可以看到：

### 1. 专业K线图
- **时K** 和 **日K** 两种模式切换
- 鼠标滚轮缩放
- 鼠标拖动查看历史
- 十字光标显示详细数据

### 2. 实时数据
- 时间、开高低收、涨幅、成交量

### 3. 涨跌统计
- 上涨/持平/下跌商品数

### 4. 各类别指数
- 匕首、步枪、手套等各类别指数和涨跌幅

### 5. 热门板块
- 热门板块指数和涨跌幅

## 🔧 故障排查

### 问题1: API 服务无法连接

**症状**: 页面显示"加载数据失败，请检查 API 服务是否运行"

**解决方案**:
```bash
# 检查 API 服务是否运行
curl http://localhost:8008/api/homepage/latest

# 如果没有响应，手动启动 API 服务
python api/main.py
```

### 问题2: 没有数据

**症状**: 页面显示"暂无数据"

**解决方案**:
```bash
# 手动抓取首页数据
python scripts/crawl_homepage.py

# 验证数据是否抓取成功
python scripts/test_kline_data.py
```

### 问题3: 端口被占用

**症状**: 启动失败，提示端口已被占用

**解决方案**:
```bash
# Windows: 查找占用端口的进程
netstat -ano | findstr :8008
netstat -ano | findstr :3000

# 杀死进程（替换 PID）
taskkill /F /PID <PID>
```

### 问题4: Redis/MongoDB 未启动

**症状**: 启动时提示服务检查失败

**解决方案**:
```bash
# 启动 Redis
D:\path\redis\redis-server.exe

# 启动 MongoDB
D:\path\mongodb\bin\mongod.exe --dbpath D:\path\mongodb\data
```

## 📝 手动启动（分步）

如果一键启动有问题，可以手动分步启动：

### 1. 启动基础服务
```bash
# Redis
D:\path\redis\redis-server.exe

# MongoDB
D:\path\mongodb\bin\mongod.exe --dbpath D:\path\mongodb\data
```

### 2. 抓取首页数据
```bash
python scripts/crawl_homepage.py
```

### 3. 启动 API 服务
```bash
python api/main.py
```

### 4. 启动 Web 服务
```bash
cd web
python -m http.server 3000
```

### 5. 启动监控窗口（可选）
```bash
python monitor/advanced_monitor.py
```

### 6. 启动爬虫（可选）
```bash
python scripts/crawl_all_enhanced.py --delay 1.5 --continue
```

## 🧪 测试

### 测试 API
```bash
python scripts/test_homepage_api.py
```

### 测试 K 线数据
```bash
python scripts/test_kline_data.py
```

### 测试数据库连接
```bash
python -c "from utils.mongo_client import MongoDBClient; client = MongoDBClient(); print('MongoDB 连接成功')"
python -c "from utils.redis_client import redis_client; redis_client.client.ping(); print('Redis 连接成功')"
```

## 🔄 更新数据

首页数据会自动每 30 秒刷新一次，也可以：

1. 点击页面右上角"🔄 刷新"按钮
2. 手动运行爬虫：`python scripts/crawl_homepage.py`

## 📚 相关文档

- [K线图功能说明](kline_chart_features.md)
- [首页使用指南](homepage_usage.md)
- [首页爬取指南](homepage_crawling_guide.md)

## ⚠️ 注意事项

1. **首次启动**: 必须先运行 `python scripts/crawl_homepage.py` 抓取数据
2. **端口冲突**: 确保 8008 和 3000 端口没有被占用
3. **数据更新**: 建议设置定时任务定期抓取最新数据
4. **浏览器兼容**: 推荐使用 Chrome、Edge 或 Firefox 浏览器

