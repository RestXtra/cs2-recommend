# 首页大盘功能使用指南

## 📋 功能说明

首页展示从 SteamDT 抓取的 CS2 饰品市场大盘数据，包括：

### 1. 大盘指数
- 当前指数值
- 涨跌幅度和百分比
- 最高/最低/昨收价

### 2. 涨跌统计
- 上涨商品数量
- 持平商品数量
- 下跌商品数量

### 3. 历史趋势图
- 大盘指数历史走势
- 使用 Chart.js 绘制

### 4. 各类别指数
- 匕首、步枪、手套等各类别指数
- 各类别涨跌幅

### 5. 热门板块
- 热门板块指数
- 热门板块涨跌幅

## 🚀 快速启动

### 一键启动（推荐）

```bash
python scripts/start_all.py
```

这个脚本会：
1. 检查 Redis 和 MongoDB 服务
2. 自动抓取最新的首页大盘数据
3. 启动 API 服务（端口 8000）
4. 启动 Web 服务（端口 3000）
5. 启动监控窗口
6. 启动爬虫

然后访问：
- **首页大盘**: http://localhost:3000/homepage.html
- **饰品市场**: http://localhost:3000/index.html

### 手动启动

```bash
# 1. 先抓取首页数据
python scripts/crawl_homepage.py

# 2. 启动 API 服务
python api/main.py

# 3. 启动 Web 服务
cd web
python -m http.server 3000
```

## 📡 API 接口

### GET /api/homepage/latest

获取最新的首页大盘数据

**URL**: `http://localhost:8008/api/homepage/latest`

**响应示例:**
```json
{
  "code": 0,
  "message": "success",
  "data": {
    "crawl_time": 1764427179.073,
    "summary": {
      "name": "大盘",
      "index": 1304.58,
      "riseFallRate": 1.45,
      "riseFallDiff": 18.61,
      "upNum": 1186,
      "flatNum": 561,
      "downNum": 548,
      "highIndex": 1306.12,
      "lowIndex": 1286.25,
      "yesterdayIndex": 1285.97,
      "updateTime": "1764426910"
    },
    "categories": [...],
    "hot_data": [...],
    "chart_data": [...]
  }
}
```

## 🔄 数据更新

### 自动更新
- 前端每 30 秒自动刷新一次数据
- 点击右上角"刷新数据"按钮手动刷新

### 手动抓取新数据
```bash
python scripts/crawl_homepage.py
```

### 定时任务（可选）
可以设置定时任务定期抓取：

**Windows (任务计划程序):**
```
程序: python
参数: D:\homework\Network-Program\End\CSGO\scripts\crawl_homepage.py
触发器: 每 5 分钟
```

**Linux (crontab):**
```bash
# 每 5 分钟抓取一次
*/5 * * * * cd /path/to/CSGO && python scripts/crawl_homepage.py
```

## 📂 数据存储

首页数据存储在 MongoDB 的 `homepage_data` 集合中：

```javascript
{
  crawl_time: 1764427179.073,  // 抓取时间戳
  summary: {...},               // 大盘概要
  categories: [...],            // 各类别数据
  hot_data: [...],              // 热门板块
  chart_data: [...]             // 历史图表数据
}
```

## 🎨 页面截图

首页包含：
1. 顶部导航栏（首页、饰品市场、排行榜等）
2. 大盘指数卡片（显示当前指数、涨跌幅）
3. 涨跌统计卡片（上涨/持平/下跌数量）
4. 历史趋势图（Chart.js 折线图）
5. 各类别指数网格
6. 热门板块网格

## 🔧 技术栈

- **前端**: HTML + CSS + JavaScript + Chart.js
- **后端**: FastAPI
- **数据库**: MongoDB
- **数据来源**: SteamDT API

## ⚠️ 注意事项

1. **首次使用**: 必须先运行 `python scripts/crawl_homepage.py` 抓取数据
2. **API 服务**: 确保 API 服务运行在 3000 端口
3. **MongoDB**: 确保 MongoDB 服务正常运行
4. **数据更新**: 建议设置定时任务定期抓取最新数据

## 🐛 常见问题

### Q: 首页显示"暂无数据"
A: 运行 `python scripts/crawl_homepage.py` 抓取数据

### Q: 图表不显示
A: 检查是否加载了 Chart.js CDN，确保网络连接正常

### Q: 数据不更新
A: 检查定时任务是否正常运行，或手动运行抓取脚本

## 📝 相关文件

| 文件 | 说明 |
|------|------|
| `web/homepage.html` | 首页 HTML |
| `web/homepage.css` | 首页样式 |
| `web/homepage.js` | 首页 JavaScript |
| `scripts/crawl_homepage.py` | 首页数据爬虫 |
| `scripts/start_with_homepage.py` | 一键启动脚本 |
| `api/main.py` | API 接口（包含 `/api/homepage/latest`） |

