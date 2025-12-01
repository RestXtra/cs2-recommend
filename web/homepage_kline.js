// 首页 K 线图 JavaScript
const API_BASE_URL = 'http://localhost:8008';

let chart = null;
let candlestickSeries = null;
let currentChartType = 'hour'; // 'hour' 或 'day'
let cachedData = null; // 缓存数据

// 初始化图表
function initChart() {
    const chartContainer = document.getElementById('klineChart');

    // 检查 LightweightCharts 是否加载
    if (typeof LightweightCharts === 'undefined') {
        console.error('LightweightCharts 未加载');
        chartContainer.innerHTML = '<div style="padding: 20px; text-align: center; color: red;">K线图库加载失败，请刷新页面重试</div>';
        return;
    }

    console.log('LightweightCharts 版本:', LightweightCharts.version || '未知');

    chart = LightweightCharts.createChart(chartContainer, {
        width: chartContainer.clientWidth,
        height: 500,
        layout: {
            background: { color: '#ffffff' },
            textColor: '#333',
        },
        grid: {
            vertLines: { color: '#f0f0f0' },
            horzLines: { color: '#f0f0f0' },
        },
        crosshair: {
            mode: LightweightCharts.CrosshairMode.Normal,
        },
        rightPriceScale: {
            borderColor: '#ddd',
        },
        timeScale: {
            borderColor: '#ddd',
            timeVisible: true,
            secondsVisible: false,
            rightOffset: 5,
            // 自定义时间格式
            tickMarkFormatter: (time) => {
                const date = new Date(time * 1000);
                if (currentChartType === 'hour') {
                    // 时K: 显示 MM-DD HH:mm
                    const month = String(date.getMonth() + 1).padStart(2, '0');
                    const day = String(date.getDate()).padStart(2, '0');
                    const hour = String(date.getHours()).padStart(2, '0');
                    const minute = String(date.getMinutes()).padStart(2, '0');
                    return `${month}-${day} ${hour}:${minute}`;
                } else {
                    // 日K: 显示 MM-DD
                    const month = String(date.getMonth() + 1).padStart(2, '0');
                    const day = String(date.getDate()).padStart(2, '0');
                    return `${month}-${day}`;
                }
            },
        },
        localization: {
            locale: 'zh-CN',
            dateFormat: 'yyyy-MM-dd',
        },
    });

    // 创建K线系列
    candlestickSeries = chart.addCandlestickSeries({
        upColor: '#ef5350',
        downColor: '#26a69a',
        borderDownColor: '#26a69a',
        borderUpColor: '#ef5350',
        wickDownColor: '#26a69a',
        wickUpColor: '#ef5350',
    });

    // 响应式调整
    window.addEventListener('resize', () => {
        chart.applyOptions({ width: chartContainer.clientWidth });
    });
}

// 加载首页数据
async function loadHomepageData() {
    try {
        console.log('开始加载数据...');
        const response = await fetch(`${API_BASE_URL}/api/homepage/latest`);
        console.log('响应状态:', response.status);

        const result = await response.json();
        console.log('响应数据:', result);

        if (result.code === 0 && result.data) {
            cachedData = result.data; // 缓存数据
            console.log('数据字段:', Object.keys(cachedData));

            // 根据当前选择的图表类型获取对应数据
            const chartData = currentChartType === 'hour'
                ? cachedData.chart_data_hour
                : cachedData.chart_data_day;

            console.log(`${currentChartType}K数据点数:`, chartData ? chartData.length : 0);
            if (chartData && chartData.length > 0) {
                console.log('数据示例:', chartData[0]);
            }

            // 更新顶部信息
            updateMarketInfo(cachedData.summary, chartData);

            // 更新K线图
            updateKlineChart(chartData);

            // 更新类别和热门板块
            console.log('类别数据:', cachedData.categories ? cachedData.categories.length : 0);
            console.log('热门数据:', cachedData.hot_data ? cachedData.hot_data.length : 0);
            updateCategories(cachedData.categories);
            updateHotData(cachedData.hot_data);

            // 更新涨跌统计（需要在类别数据加载后）
            updateStats(cachedData.summary, cachedData.categories);
        } else {
            console.error('获取数据失败:', result.message);
            showError('暂无数据，请先运行爬虫抓取数据');
        }
    } catch (error) {
        console.error('加载数据失败:', error);
        console.error('错误详情:', error.stack);
        showError('加载数据失败，请检查 API 服务是否运行');
    }
}

// 更新市场信息
function updateMarketInfo(summary, chartData) {
    if (!summary || !chartData || chartData.length === 0) return;

    const latest = chartData[chartData.length - 1];
    const updateTime = new Date(summary.updateTime * 1000);

    // 更新大盘指数和涨跌幅（标题中）
    const indexValue = summary.index || latest.close;
    const changePercent = summary.riseFallRate || 0;
    const changeValue = summary.riseFallDiff || 0;
    const changeSign = changePercent >= 0 ? '+' : '';
    const changeColor = changePercent >= 0 ? '#ef5350' : '#26a69a';  // 红涨绿跌

    // 更新顶部大盘指数
    document.getElementById('indexValue').textContent = indexValue.toFixed(2);
    document.getElementById('indexValue').style.color = changeColor;

    document.getElementById('indexChange').innerHTML =
        `${changeSign}${changePercent.toFixed(2)}% (${changeSign}${changeValue.toFixed(2)})`;
    document.getElementById('indexChange').style.color = changeColor;

    // 更新时间
    document.getElementById('updateTimeTop').textContent =
        updateTime.toLocaleString('zh-CN', {
            year: 'numeric', month: '2-digit', day: '2-digit',
            hour: '2-digit', minute: '2-digit'
        });

    // 更新详细信息
    document.getElementById('todayIndex').textContent = indexValue.toFixed(2);
    document.getElementById('todayIndex').style.color = changeColor;

    document.getElementById('highIndex').textContent = (summary.highIndex || latest.high).toFixed(2);
    document.getElementById('yesterdayIndex').textContent = (summary.yesterdayIndex || 0).toFixed(2);
    document.getElementById('lowIndex').textContent = (summary.lowIndex || latest.low).toFixed(2);

    const riseFallDiffEl = document.getElementById('riseFallDiff');
    riseFallDiffEl.textContent = `${changeSign}${changeValue.toFixed(2)}`;
    riseFallDiffEl.style.color = changeColor;
    riseFallDiffEl.style.fontWeight = 'bold';

    const riseFallRateEl = document.getElementById('riseFallRate');
    riseFallRateEl.textContent = `${changeSign}${changePercent.toFixed(2)}%`;
    riseFallRateEl.style.color = changeColor;
    riseFallRateEl.style.fontWeight = 'bold';

    document.getElementById('volume').textContent = (summary.upNum + summary.flatNum + summary.downNum).toLocaleString();
}

// 更新K线图
function updateKlineChart(chartData) {
    console.log('updateKlineChart 调用，数据点数:', chartData ? chartData.length : 0);
    console.log('candlestickSeries 存在:', !!candlestickSeries);

    if (!chartData || chartData.length === 0) {
        console.warn('没有图表数据');
        return;
    }

    if (!candlestickSeries) {
        console.error('candlestickSeries 未初始化');
        return;
    }

    // 获取最新的大盘指数
    const latestIndex = cachedData && cachedData.summary ? cachedData.summary.index : null;

    // 转换数据格式 - Lightweight Charts 需要 Unix 时间戳（秒）
    const klineData = chartData.map((item, index) => {
        // 如果时间戳是毫秒（13位），转换为秒（10位）
        let timestamp = item.time;
        if (timestamp > 10000000000) {
            timestamp = Math.floor(timestamp / 1000);
        }

        // 最后一条数据使用最新的大盘指数作为 close 值
        let closeValue = parseFloat(item.close);
        if (index === chartData.length - 1 && latestIndex) {
            closeValue = parseFloat(latestIndex);
        }

        return {
            time: timestamp,
            open: parseFloat(item.open),
            high: parseFloat(item.high),
            low: parseFloat(item.low),
            close: closeValue
        };
    });

    // 按时间排序
    klineData.sort((a, b) => a.time - b.time);

    console.log('K线数据示例:', klineData[0]);
    console.log('K线数据总数:', klineData.length);
    console.log('时间范围:', new Date(klineData[0].time * 1000), '-', new Date(klineData[klineData.length - 1].time * 1000));

    try {
        candlestickSeries.setData(klineData);
        console.log('✅ K线数据设置成功');

        // 自动缩放到合适的视图
        chart.timeScale().fitContent();
    } catch (error) {
        console.error('❌ 设置K线数据失败:', error);
        console.error('错误详情:', error.message);
    }
}

// 更新涨跌统计（从类别数据中计算）
function updateStats(summary, categories) {
    if (!summary && !categories) return;

    // 如果 summary 中有数据且不为0，使用 summary 的数据
    if (summary && (summary.upNum > 0 || summary.flatNum > 0 || summary.downNum > 0)) {
        document.getElementById('upNum').textContent = summary.upNum || 0;
        document.getElementById('flatNum').textContent = summary.flatNum || 0;
        document.getElementById('downNum').textContent = summary.downNum || 0;
    }
    // 否则从类别数据中计算
    else if (categories && categories.length > 0) {
        let upNum = 0;
        let flatNum = 0;
        let downNum = 0;

        categories.forEach(cat => {
            const rate = cat.riseFallRate || 0;
            if (rate > 0) {
                upNum++;
            } else if (rate < 0) {
                downNum++;
            } else {
                flatNum++;
            }
        });

        document.getElementById('upNum').textContent = upNum;
        document.getElementById('flatNum').textContent = flatNum;
        document.getElementById('downNum').textContent = downNum;
    } else {
        document.getElementById('upNum').textContent = 0;
        document.getElementById('flatNum').textContent = 0;
        document.getElementById('downNum').textContent = 0;
    }
}

// 更新类别
function updateCategories(categories) {
    const container = document.getElementById('categoriesList');
    if (!categories || categories.length === 0) {
        container.innerHTML = '<div class="loading">暂无数据</div>';
        return;
    }
    
    container.innerHTML = categories.map(cat => {
        const changeClass = cat.riseFallRate >= 0 ? 'up' : 'down';
        const changeSign = cat.riseFallRate >= 0 ? '+' : '';
        return `
            <div class="category-item">
                <div class="category-header">
                    <span class="category-name">${cat.name}</span>
                    <span class="category-index">${cat.index.toFixed(2)}</span>
                </div>
                <div class="category-change ${changeClass}">
                    ${changeSign}${cat.riseFallRate.toFixed(2)}%
                </div>
            </div>
        `;
    }).join('');
}

// 更新热门板块
function updateHotData(hotData) {
    const container = document.getElementById('hotList');
    if (!hotData || hotData.length === 0) {
        container.innerHTML = '<div class="loading">暂无数据</div>';
        return;
    }

    container.innerHTML = hotData.map(item => {
        const changeClass = item.riseFallRate >= 0 ? 'up' : 'down';
        const changeSign = item.riseFallRate >= 0 ? '+' : '';
        return `
            <div class="hot-item">
                <div class="hot-header">
                    <span class="hot-name">${item.name}</span>
                    <span class="hot-index">${item.index.toFixed(2)}</span>
                </div>
                <div class="hot-change ${changeClass}">
                    ${changeSign}${item.riseFallRate.toFixed(2)}%
                </div>
            </div>
        `;
    }).join('');
}

// 显示错误
function showError(message) {
    document.getElementById('categoriesList').innerHTML = `<div class="loading">${message}</div>`;
    document.getElementById('hotList').innerHTML = `<div class="loading">${message}</div>`;
}

// 刷新数据
async function refreshData() {
    const btn = event.target;
    btn.textContent = '⏳ 刷新中...';
    btn.disabled = true;

    await loadHomepageData();

    setTimeout(() => {
        btn.textContent = '✓ 已刷新';
        setTimeout(() => {
            btn.textContent = '🔄 刷新';
            btn.disabled = false;
        }, 1000);
    }, 500);
}

// 切换图表类型
function switchChartType(type) {
    if (type === currentChartType || !cachedData) return;

    currentChartType = type;

    // 更新按钮状态
    document.querySelectorAll('.chart-btn[data-type]').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.type === type);
    });

    // 重新初始化图表以更新时间格式
    if (chart) {
        chart.remove();
    }
    initChart();

    // 获取对应的图表数据
    const chartData = type === 'hour'
        ? cachedData.chart_data_hour
        : cachedData.chart_data_day;

    // 更新图表
    updateKlineChart(chartData);
    updateMarketInfo(cachedData.summary, chartData);
}

// 页面加载完成后初始化
document.addEventListener('DOMContentLoaded', () => {
    initChart();
    loadHomepageData();

    // 绑定图表类型切换按钮
    document.querySelectorAll('.chart-btn[data-type]').forEach(btn => {
        btn.addEventListener('click', () => {
            switchChartType(btn.dataset.type);
        });
    });

    // 每30秒自动刷新
    setInterval(loadHomepageData, 30000);
});

