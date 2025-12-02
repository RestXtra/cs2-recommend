# CS2 市场爬虫系统

一个用于爬取和分析 CS2（CSGO）饰品市场数据的分布式爬虫系统。

## 功能特性

- 🕷️ **数据爬取**: 从 SteamDT API 爬取饰品数据，支持断点续传
- 📊 **趋势分析**: 使用机器学习分析价格趋势
- 🤖 **AI 顾问**: 结合大模型提供投资建议
- 🖥️ **监控面板**: 实时监控爬虫状态
- 🌐 **Web 界面**: 可视化数据展示

## 项目结构

```
CSGO/
├── config/                 # 配置文件
│   └── settings.yaml       # 主配置
│
├── src/                    # 源代码
│   ├── core/              # 核心模块（配置、数据库、日志）
│   ├── crawler/           # 爬虫模块
│   └── ml/                # 机器学习模块
│
├── api/                    # FastAPI 后端
├── web/                    # 前端页面
├── monitor/                # 监控模块
├── data/                   # 数据文件
├── logs/                   # 日志文件
│
├── run.py                 # 统一启动脚本
├── requirements.txt       # 依赖
└── README.md
```

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置环境

复制 `.env.example` 为 `.env` 并填写配置：

```bash
cp .env.example .env
```

主要配置项：
- `SILICONFLOW_API_KEY`: AI 分析功能的 API 密钥
- `STEAMDT_ACCESS_TOKEN`: SteamDT API 访问令牌

### 3. 启动服务

确保 Redis 和 MongoDB 已启动，然后：

```bash
# 启动所有服务
python run.py

# 或单独启动
python -c "from scripts.start_all import start_api_server; start_api_server()"  # 只启动 API
python -m http.server 3000 --directory web  # 只启动 Web
python scripts/crawl_all_enhanced.py  # 运行爬虫
python monitor/monitor.py  # 启动监控
```

### 4. 访问

- Web 界面: http://localhost:3000
- API 文档: http://localhost:8008/docs

## 爬虫使用

```bash
# 爬取所有数据
python start.py crawl

# 爬取指定页数
python start.py crawl --pages 10

# 自定义延迟
python start.py crawl --delay 2.0

# 爬取首页大盘数据
python start.py homepage
```

## 技术栈

- **爬虫**: Scrapy + Scrapy-Redis
- **后端**: FastAPI + MongoDB + Redis
- **前端**: HTML + JavaScript + TradingView
- **ML**: scikit-learn + numpy
- **AI**: 硅基流动 API (DeepSeek)

## 配置说明

主配置文件: `config/settings.yaml`

```yaml
# MongoDB 配置
mongodb:
  host: localhost
  port: 27017
  database: csgo_market

# Redis 配置
redis:
  host: localhost
  port: 6379

# 爬虫配置
spider:
  concurrent_requests: 16
  download_delay: 0.5

# ML 配置
ml:
  filter:
    min_buy_ratio: 1.0
    min_buy_stable: 1.0
```

## 注意事项

1. 敏感信息（API 密钥等）请配置在 `.env` 文件中，不要提交到版本控制
2. 爬取时请遵守网站规则，适当控制请求频率
3. 投资建议仅供参考，不构成实际投资建议

## License

MIT
