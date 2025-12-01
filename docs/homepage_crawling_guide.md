# SteamDT 首页数据爬取指南

## 📋 概述

SteamDT 首页 (https://steamdt.com/section?type=BROAD) 展示了 CS2 饰品市场的整体数据，包括：
- 大盘指数
- 各类别指数（匕首、步枪、手套等）
- 热门板块
- 历史趋势图表

## 🔍 技术分析

### 1. 页面加载方式
- 首页使用 **React/Vue 等前端框架**动态渲染
- 数据通过 **AJAX 请求**从 API 获取
- 页面源码中**不包含**实际数据

### 2. 数据来源 API

通过 Selenium + Chrome DevTools 捕获网络请求，发现以下 API：

#### API 1: 板块概要数据
```
POST https://api.steamdt.com/user/item/block/v1/summary?timestamp={timestamp}

请求体:
{
  "type": "BROAD",
  "level": 0,
  "platform": "ALL",
  "typeVal": "",
  "timestamp": "{timestamp}"
}

响应数据:
{
  "success": true,
  "data": {
    "name": "大盘",
    "index": 1304.58,           // 大盘指数
    "riseFallRate": 1.45,       // 涨跌幅 %
    "upNum": 1187,              // 上涨商品数
    "flatNum": 561,             // 持平商品数
    "downNum": 547,             // 下跌商品数
    ...
  }
}
```

#### API 2: 下级板块数据（各类别）
```
POST https://api.steamdt.com/user/item/block/v1/next-level?timestamp={timestamp}

请求体:
{
  "type": "BROAD",
  "level": 0,
  "platform": "ALL",
  "typeVal": "",
  "typeDay": "1",
  "timestamp": "{timestamp}"
}

响应数据:
{
  "success": true,
  "data": [
    {
      "type": "ITEM_TYPE",
      "name": "微型冲锋枪",
      "index": 61237.67,
      "riseFallRate": 2.05,
      ...
    },
    {
      "type": "ITEM_TYPE",
      "name": "匕首",
      "index": 1471707.39,
      "riseFallRate": 2.23,
      ...
    },
    ...
  ]
}
```

#### API 3: 热门关联数据
```
POST https://api.steamdt.com/user/item/block/v1/relation?timestamp={timestamp}

请求体:
{
  "type": "HOT",
  "level": 0,
  "platform": "ALL",
  "typeDay": "1",
  "timestamp": "{timestamp}"
}
```

#### API 4: 历史图表数据
```
GET https://api.steamdt.com/user/statistics/v2/chart?timestamp={timestamp}&type=2&dateType=2&maxTime

响应: 时间序列数据 [[timestamp, value], ...]
```

## 🛠️ 实现方法

### 方法 1: 使用 Selenium（推荐用于调试）

```python
from selenium import webdriver
from selenium.webdriver.chrome.service import Service

service = Service(executable_path=r'D:\path\chromedriver\chromedriver.exe')
driver = webdriver.Chrome(service=service)

driver.get("https://steamdt.com/section?type=BROAD")
time.sleep(5)  # 等待页面加载

# 捕获网络请求
logs = driver.get_log('performance')
# 分析日志找到 API 请求...
```

### 方法 2: 直接调用 API（推荐用于生产）

```python
import requests
import time

headers = {
    "accept": "application/json",
    "content-type": "application/json",
    "user-agent": "Mozilla/5.0 ...",
    "origin": "https://steamdt.com",
    "referer": "https://steamdt.com/"
}

timestamp = int(time.time() * 1000)
url = f"https://api.steamdt.com/user/item/block/v1/summary?timestamp={timestamp}"
payload = {
    "type": "BROAD",
    "level": 0,
    "platform": "ALL",
    "typeVal": "",
    "timestamp": str(timestamp)
}

response = requests.post(url, headers=headers, json=payload)
data = response.json()
```

## 📦 使用现成的爬虫

已实现的爬虫脚本：`scripts/crawl_homepage.py`

```bash
# 运行首页爬虫
python scripts/crawl_homepage.py
```

功能：
- ✅ 获取大盘概要数据
- ✅ 获取各类别指数
- ✅ 获取热门板块
- ✅ 获取历史图表数据
- ✅ 自动保存到 MongoDB (`homepage_data` 集合)

## 📊 数据字段说明

| 字段 | 说明 | 示例 |
|------|------|------|
| `index` | 指数值 | 1304.58 |
| `riseFallRate` | 涨跌幅 (%) | 1.45 |
| `upNum` | 上涨商品数 | 1187 |
| `flatNum` | 持平商品数 | 561 |
| `downNum` | 下跌商品数 | 547 |

## 🔧 工具脚本

| 脚本 | 功能 |
|------|------|
| `scripts/test_selenium.py` | 测试 Selenium 是否正常工作 |
| `scripts/capture_network_requests.py` | 捕获页面的所有 API 请求 |
| `scripts/test_homepage_apis.py` | 测试各个 API 是否可用 |
| `scripts/crawl_homepage.py` | 完整的首页数据爬虫 |

## ⚠️ 注意事项

1. **时间戳参数**: 所有 API 都需要 `timestamp` 参数（毫秒级）
2. **请求头**: 必须包含 `origin` 和 `referer` 头
3. **频率限制**: 建议添加延迟，避免请求过快
4. **数据更新**: 首页数据实时更新，建议定期抓取

## 🎯 下一步

- [ ] 添加定时任务，定期抓取首页数据
- [ ] 分析历史数据，生成趋势报告
- [ ] 可视化大盘指数变化

