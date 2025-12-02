// API配置
const API_BASE_URL = 'http://localhost:8008';

// 当前筛选条件
let currentFilter = {
    isRecommended: true,
    isFavorited: null,
    searchKeyword: '',
    page: 1,
    pageSize: 50,
    priceMin: null,
    priceMax: null,
    sellRatioMin: null,
    sellRatioMax: null,
    buyRatioMin: null,
    buyRatioMax: null,
    weaponType: null,
    exterior: null,
    category: null,
    quality: null,
    rarity: null,
    caseType: null,
    sticker: null
};

// 初始化标签页切换
document.addEventListener('DOMContentLoaded', function() {
    const tabButtons = document.querySelectorAll('.filter-tab-right');
    tabButtons.forEach(button => {
        button.addEventListener('click', function() {
            // 移除所有active类
            tabButtons.forEach(btn => btn.classList.remove('active'));
            document.querySelectorAll('.filter-tab-content').forEach(content => {
                content.classList.remove('active');
            });

            // 添加active类
            this.classList.add('active');
            const tabName = this.getAttribute('data-tab');
            document.getElementById(`tab-${tabName}`).classList.add('active');
        });
    });
});

// 加载统计数据
async function loadStats() {
    try {
        const response = await fetch(`${API_BASE_URL}/api/stats`);
        const result = await response.json();

        if (result.code === 0) {
            const { items_stats } = result.data;

            // 更新统计卡片
            document.getElementById('totalItems').textContent = (items_stats.total_count || 0).toLocaleString();
            document.getElementById('recommendedItems').textContent = (items_stats.recommended_count || 0).toLocaleString();
            document.getElementById('todayItems').textContent = (items_stats.today_count || 0).toLocaleString();

            // 平均涨幅
            const avgIncrease = items_stats.avg_buy_ratio ?
                ((items_stats.avg_buy_ratio - 1) * 100).toFixed(1) + '%' : '-';
            document.getElementById('avgIncrease').textContent = avgIncrease;
        }
    } catch (error) {
        console.error('加载统计数据失败:', error);
    }
}

// 总页数
let totalPages = 1;
let totalItems = 0;

// 加载商品列表
async function loadItems() {
    const itemList = document.getElementById('itemList');
    itemList.innerHTML = '<div class="loading">加载中...</div>';

    try {
        // 构建查询参数
        const queryParams = {
            page: currentFilter.page,
            page_size: currentFilter.pageSize,
            is_recommended: currentFilter.isRecommended,
            is_favorited: currentFilter.isFavorited,
            keyword: currentFilter.searchKeyword,
            sort_by: 'recommendation_score',
            order: 'desc'
        };

        // 添加价格筛选
        if (currentFilter.priceMin !== null) {
            queryParams.price_min = currentFilter.priceMin;
        }
        if (currentFilter.priceMax !== null) {
            queryParams.price_max = currentFilter.priceMax;
        }

        // 添加挂刀比例筛选
        if (currentFilter.sellRatioMin !== null) {
            queryParams.sell_ratio_min = currentFilter.sellRatioMin;
        }
        if (currentFilter.sellRatioMax !== null) {
            queryParams.sell_ratio_max = currentFilter.sellRatioMax;
        }
        if (currentFilter.buyRatioMin !== null) {
            queryParams.buy_ratio_min = currentFilter.buyRatioMin;
        }
        if (currentFilter.buyRatioMax !== null) {
            queryParams.buy_ratio_max = currentFilter.buyRatioMax;
        }

        // 添加武器类型筛选
        if (currentFilter.weaponType && currentFilter.weaponType.length > 0) {
            queryParams.weapon_type = currentFilter.weaponType;
        }

        // 添加外观筛选
        if (currentFilter.exterior && currentFilter.exterior.length > 0) {
            queryParams.exterior = currentFilter.exterior;
        }

        // 添加类别筛选
        if (currentFilter.category && currentFilter.category.length > 0) {
            queryParams.category = currentFilter.category;
        }

        // 添加品质筛选
        if (currentFilter.quality && currentFilter.quality.length > 0) {
            queryParams.quality = currentFilter.quality;
        }

        // 添加稀有度筛选
        if (currentFilter.rarity && currentFilter.rarity.length > 0) {
            queryParams.rarity = currentFilter.rarity;
        }

        // 添加箱子筛选
        if (currentFilter.caseType && currentFilter.caseType.length > 0) {
            queryParams.case_type = currentFilter.caseType;
        }

        const response = await fetch(`${API_BASE_URL}/api/items/query`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(queryParams)
        });
        
        const result = await response.json();

        if (result.code === 0 && result.data.items.length > 0) {
            itemList.innerHTML = result.data.items.map(item => renderMarketItem(item)).join('');

            // 更新分页信息
            totalItems = result.data.total || 0;
            totalPages = Math.ceil(totalItems / currentFilter.pageSize);
            updatePagination();

            // 绘制所有趋势图（延迟执行，确保DOM已渲染）
            setTimeout(() => {
                result.data.items.forEach(item => {
                    if (item.trend_list && item.trend_list.length > 0) {
                        const canvas = document.getElementById(`chart_${item.item_id}`);
                        if (canvas) {
                            drawTrendChart(`chart_${item.item_id}`, item.trend_list);
                        }
                    }
                });
            }, 100);
        } else {
            itemList.innerHTML = '<div class="loading">暂无数据</div>';
            totalItems = 0;
            totalPages = 1;
            updatePagination();
        }
    } catch (error) {
        console.error('加载商品列表失败:', error);
        itemList.innerHTML = '<div class="loading">加载失败</div>';
    }
}

// 渲染单个商品项
function renderMarketItem(item) {
    const buyRatioClass = item.buy_ratio >= 1.0 ? 'ratio-good' : (item.buy_ratio >= 0.8 ? 'ratio-normal' : 'ratio-bad');
    const buyStableClass = item.buy_stable >= 1.0 ? 'ratio-good' : (item.buy_stable >= 0.8 ? 'ratio-normal' : 'ratio-bad');
    const sellRatioClass = item.sell_ratio >= 1.0 ? 'ratio-good' : (item.sell_ratio >= 0.8 ? 'ratio-normal' : 'ratio-bad');
    
    return `
        <div class="market-item">
            <div>
                <img src="${item.image_url || 'placeholder.png'}" alt="${item.name}" class="item-image">
            </div>
            <div class="item-name-col">
                <div class="item-weapon">
                    ${item.name || ''}
                    ${item.is_recommended ? '<span class="badge badge-recommend">推荐</span>' : ''}
                </div>
                <div class="item-skin">${item.exterior || ''}</div>
                <div class="item-count">在售: ${item.sell_num || 0}</div>
            </div>
            <div class="price-col">¥ ${(item.steam_price || 0).toFixed(2)}</div>
            <div class="price-col">¥ ${(item.buff_price || 0).toFixed(2)}</div>
            <div class="price-col">¥ ${(item.youpin_price || 0).toFixed(2)}</div>
            <div class="price-col">¥ ${(item.c5_price || 0).toFixed(2)}</div>
            <div class="ratio-col">
                <div>
                    <span class="ratio-label">寄售竞价:</span>
                    <span class="ratio-value ${sellRatioClass}">${(item.sell_ratio || 0).toFixed(2)}</span>
                </div>
                <div>
                    <span class="ratio-label">求购竞价:</span>
                    <span class="ratio-value ${buyRatioClass}">${(item.buy_ratio || 0).toFixed(2)}</span>
                </div>
                <div>
                    <span class="ratio-label">求购稳定:</span>
                    <span class="ratio-value ${buyStableClass}">${(item.buy_stable || 0).toFixed(2)}</span>
                </div>
            </div>
            <div class="chart-col">
                ${item.trend_list && item.trend_list.length > 0 ? `<canvas id="chart_${item.item_id}" width="120" height="40"></canvas>` : '<span style="font-size:11px;color:#999;">暂无走势图</span>'}
            </div>
            <div class="action-col">
                <button class="action-btn ${item.is_favorited ? 'favorited' : ''}" onclick="toggleFavorite('${item.item_id}', event)">
                    ${item.is_favorited ? '⭐' : '☆'}
                </button>
                <button class="action-btn predict-btn" onclick="predictPrice('${item.item_id}', '${item.name.replace(/'/g, "\\'")}')">📈</button>
                <button class="action-btn ai-btn" onclick="analyzeItem('${item.item_id}', '${item.name.replace(/'/g, "\\'")}')">🤖</button>
            </div>
        </div>
    `;
}

// 更新分页显示
function updatePagination() {
    const paginationDiv = document.getElementById('pagination');
    if (!paginationDiv) return;

    const currentPage = currentFilter.page;
    const maxVisiblePages = 7;

    let html = `
        <div class="pagination-info">
            共 ${totalItems} 个商品，第 ${currentPage}/${totalPages} 页
        </div>
        <div class="pagination-buttons">
    `;

    // 上一页按钮
    html += `<button class="page-btn" ${currentPage === 1 ? 'disabled' : ''} onclick="goToPage(${currentPage - 1})">上一页</button>`;

    // 页码按钮
    let startPage = Math.max(1, currentPage - Math.floor(maxVisiblePages / 2));
    let endPage = Math.min(totalPages, startPage + maxVisiblePages - 1);

    if (endPage - startPage < maxVisiblePages - 1) {
        startPage = Math.max(1, endPage - maxVisiblePages + 1);
    }

    if (startPage > 1) {
        html += `<button class="page-btn" onclick="goToPage(1)">1</button>`;
        if (startPage > 2) {
            html += `<span class="page-ellipsis">...</span>`;
        }
    }

    for (let i = startPage; i <= endPage; i++) {
        html += `<button class="page-btn ${i === currentPage ? 'active' : ''}" onclick="goToPage(${i})">${i}</button>`;
    }

    if (endPage < totalPages) {
        if (endPage < totalPages - 1) {
            html += `<span class="page-ellipsis">...</span>`;
        }
        html += `<button class="page-btn" onclick="goToPage(${totalPages})">${totalPages}</button>`;
    }

    // 下一页按钮
    html += `<button class="page-btn" ${currentPage === totalPages ? 'disabled' : ''} onclick="goToPage(${currentPage + 1})">下一页</button>`;

    html += `</div>`;
    paginationDiv.innerHTML = html;
}

// 跳转到指定页
function goToPage(page) {
    if (page < 1 || page > totalPages || page === currentFilter.page) return;
    currentFilter.page = page;
    loadItems();
    // 滚动到顶部
    window.scrollTo({ top: 0, behavior: 'smooth' });
}

// 搜索商品
function searchItems() {
    const keyword = document.getElementById('searchInput').value.trim();
    currentFilter.searchKeyword = keyword;
    currentFilter.page = 1;
    loadItems();
}

// 按推荐筛选
function filterByRecommend(isRecommended) {
    currentFilter.isRecommended = isRecommended;
    currentFilter.isFavorited = false;  // 重置收藏筛选
    currentFilter.page = 1;
    
    // 更新按钮状态
    document.querySelectorAll('.filter-tab').forEach((tab, index) => {
        if (index === 0 && isRecommended) {
            tab.classList.add('active');
        } else if (index === 1 && !isRecommended) {
            tab.classList.add('active');
        } else {
            tab.classList.remove('active');
        }
    });
    
    loadItems();
}

// 刷新数据
function refreshData() {
    loadStats();
    loadItems();
    // 显示刷新提示
    const btn = document.querySelector('.btn-primary');
    if (btn) {
        btn.textContent = '✓ 已刷新';
        setTimeout(() => { btn.textContent = '🔄 刷新数据'; }, 1000);
    }
}

// 查看商品详情
async function viewDetail(itemId) {
    try {
        const response = await fetch(`${API_BASE_URL}/api/items/${itemId}`);
        const result = await response.json();

        if (result.code === 0) {
            const item = result.data;
            alert(`商品详情：\n\n名称：${item.name}\n价格：¥${item.steam_price}\n求购竞价：${item.buy_ratio}\n求购稳定：${item.buy_stable}\n推荐分数：${item.recommendation_score || 'N/A'}`);
        }
    } catch (error) {
        console.error('获取商品详情失败:', error);
    }
}

// 初始化
function init() {
    loadStats();
    loadItems();

    // 定时刷新统计
    setInterval(() => {
        loadStats();
    }, 10000); // 每10秒刷新统计

    // 搜索框回车事件
    document.getElementById('searchInput').addEventListener('keypress', (e) => {
        if (e.key === 'Enter') {
            searchItems();
        }
    });
}

// 筛选面板功能
function toggleFilterPanel() {
    const panel = document.getElementById('filterPanel');
    panel.classList.toggle('active');
}

function setPriceRange(min, max) {
    event.target.classList.toggle('active');
    currentFilter.priceMin = min === '' ? null : min;
    currentFilter.priceMax = max === '' ? null : max;

    // 更新输入框
    document.getElementById('priceMin').value = min || '';
    document.getElementById('priceMax').value = max || '';
}

function setWeaponType(type) {
    event.target.classList.toggle('active');
    toggleArrayFilter('weaponType', type, event.target);
}

function setExterior(exterior) {
    event.target.classList.toggle('active');
    toggleArrayFilter('exterior', exterior, event.target);
}

function setCategory(category) {
    event.target.classList.toggle('active');
    toggleArrayFilter('category', category, event.target);
}

function setQuality(quality) {
    event.target.classList.toggle('active');
    toggleArrayFilter('quality', quality, event.target);
}

function setRarity(rarity) {
    event.target.classList.toggle('active');
    toggleArrayFilter('rarity', rarity, event.target);
}

function setAgent(agent) {
    event.target.classList.toggle('active');
    toggleArrayFilter('agent', agent, event.target);
}

function setCase(caseType) {
    event.target.classList.toggle('active');
    toggleArrayFilter('caseType', caseType, event.target);
}

function setSticker(sticker) {
    event.target.classList.toggle('active');
    toggleArrayFilter('sticker', sticker, event.target);
}

// 辅助函数：切换数组筛选
function toggleArrayFilter(filterKey, value, target) {
    if (!currentFilter[filterKey]) {
        currentFilter[filterKey] = [];
    }

    const isActive = target.classList.contains('active');
    if (isActive) {
        // 添加到数组
        if (!currentFilter[filterKey].includes(value)) {
            currentFilter[filterKey].push(value);
        }
    } else {
        // 从数组中移除
        currentFilter[filterKey] = currentFilter[filterKey].filter(v => v !== value);
    }

    // 如果数组为空，设为null
    if (currentFilter[filterKey].length === 0) {
        currentFilter[filterKey] = null;
    }
}

function selectAll(type) {
    // 定义各类型对应的武器名称
    const typeMap = {
        // 匕首
        'knife': ['蝴蝶刀', '爪子刀', 'M9 刺刀', '骷髅匕首', '刺刀', '折叠刀', '短剑', '锯齿爪刀', '流浪者匕首', '熊刀', '海豹短刀', '猎杀者匕首', '系绳匕首', '求生匕首', '弯刀', '暗影双匕', '鲍伊猎刀', '穿肠刀', '折刀', '廓尔喀刀'],
        // 手套
        'gloves': ['运动手套', '专业手套', '摩托手套', '驾驶手套', '裹手', '狂牙手套', '九头蛇手套', '血猎手套'],
        // 步枪
        'rifle': ['AK-47', 'AWP', 'M4A1 消音型', 'M4A4', '加利尔 AR', '法玛斯', 'SSG 08', 'AUG', 'SG 553', 'SCAR-20', 'G3SG1'],
        // 手枪
        'pistol': ['沙漠之鹰', 'USP 消音版', '格洛克 18 型', 'Tec-9', 'FN57', 'P250', '双持贝瑞塔', 'CZ75 自动手枪', 'R8 左轮手枪', 'P2000'],
        // 微冲
        'smg': ['MP9', 'MAC-10', 'P90', 'UMP-45', 'MP7', 'PP-野牛', 'MP5-SD'],
        // 霰弹枪
        'shotgun': ['MAG-7', 'XM1014', '截短霰弹枪', '新星'],
        // 机枪
        'machinegun': ['内格夫', 'M249'],
        // 其他类型
        'other': ['涂鸦', '探员', '挂件', '音乐盒', '武器箱', '布章', '印花'],
        // 外观
        'exterior': ['崭新出厂', '略有磨损', '久经沙场', '破损不堪', '战痕累累'],
    };

    // 找到对应的section并获取所有按钮
    const selectAllSpan = event.target;
    const section = selectAllSpan.closest('.filter-section');
    if (!section) return;

    const buttons = section.querySelectorAll('.filter-option');
    const allActive = Array.from(buttons).every(btn => btn.classList.contains('active'));

    // 如果全部选中，则取消全选；否则全选
    buttons.forEach(btn => {
        if (allActive) {
            btn.classList.remove('active');
        } else {
            btn.classList.add('active');
        }
    });

    // 更新筛选状态
    const weaponTypeCategories = ['knife', 'gloves', 'rifle', 'pistol', 'smg', 'shotgun', 'machinegun', 'other'];
    
    if (typeMap[type]) {
        if (allActive) {
            // 取消全选 - 从筛选中移除这些类型
            if (weaponTypeCategories.includes(type)) {
                if (currentFilter.weaponType) {
                    currentFilter.weaponType = currentFilter.weaponType.filter(
                        wt => !typeMap[type].includes(wt)
                    );
                    if (currentFilter.weaponType.length === 0) {
                        currentFilter.weaponType = null;
                    }
                }
            } else if (type === 'exterior') {
                if (currentFilter.exterior) {
                    currentFilter.exterior = currentFilter.exterior.filter(
                        ext => !typeMap[type].includes(ext)
                    );
                    if (currentFilter.exterior.length === 0) {
                        currentFilter.exterior = null;
                    }
                }
            }
        } else {
            // 全选 - 添加所有类型到筛选中
            if (weaponTypeCategories.includes(type)) {
                if (!currentFilter.weaponType) {
                    currentFilter.weaponType = [];
                }
                // 添加该分类下的所有武器类型
                typeMap[type].forEach(wt => {
                    if (!currentFilter.weaponType.includes(wt)) {
                        currentFilter.weaponType.push(wt);
                    }
                });
            } else if (type === 'exterior') {
                if (!currentFilter.exterior) {
                    currentFilter.exterior = [];
                }
                typeMap[type].forEach(ext => {
                    if (!currentFilter.exterior.includes(ext)) {
                        currentFilter.exterior.push(ext);
                    }
                });
            }
        }
    }
}

function setRatioRange(type, min, max) {
    // 确定是哪个筛选区域
    const sectionIndex = type === 'sell' ? 2 : 3;

    // 移除所有该类型选项的active类
    document.querySelectorAll(`.filter-section:nth-child(${sectionIndex}) .filter-option`).forEach(btn => {
        btn.classList.remove('active');
    });
    // 添加active类到当前按钮
    event.target.classList.add('active');

    if (type === 'sell') {
        currentFilter.sellRatioMin = min === '' ? null : min;
        currentFilter.sellRatioMax = max === '' ? null : max;
    } else {
        currentFilter.buyRatioMin = min === '' ? null : min;
        currentFilter.buyRatioMax = max === '' ? null : max;
    }
}

function resetFilters() {
    // 只重置筛选面板里的筛选条件，不影响主页的标签选择(全部商品/全部推荐/我的关注)
    // 保留 isRecommended, isFavorited 不变
    currentFilter.searchKeyword = '';
    currentFilter.priceMin = null;
    currentFilter.priceMax = null;
    currentFilter.sellRatioMin = null;
    currentFilter.sellRatioMax = null;
    currentFilter.buyRatioMin = null;
    currentFilter.buyRatioMax = null;
    currentFilter.weaponType = null;
    currentFilter.exterior = null;
    currentFilter.category = null;
    currentFilter.quality = null;
    currentFilter.rarity = null;
    currentFilter.caseType = null;

    // 移除筛选面板内所有active类
    document.querySelectorAll('.filter-option').forEach(btn => {
        btn.classList.remove('active');
    });

    // 清空筛选面板里的输入框
    document.querySelectorAll('.filter-input-group input').forEach(input => {
        input.value = '';
    });
}

function applyFilters() {
    toggleFilterPanel();
    loadItems();
}

// 绘制趋势图
function drawTrendChart(canvasId, trendList) {
    const canvas = document.getElementById(canvasId);
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    const width = canvas.width;
    const height = canvas.height;

    // 清空画布
    ctx.clearRect(0, 0, width, height);

    // 提取价格数据
    const prices = trendList.map(item => item[1]);
    const maxPrice = Math.max(...prices);
    const minPrice = Math.min(...prices);
    const priceRange = maxPrice - minPrice || 1;

    // 绘制折线
    ctx.beginPath();
    ctx.strokeStyle = '#5b9aff';
    ctx.lineWidth = 1.5;

    trendList.forEach((item, index) => {
        const x = (index / (trendList.length - 1)) * width;
        const y = height - ((item[1] - minPrice) / priceRange) * height;

        if (index === 0) {
            ctx.moveTo(x, y);
        } else {
            ctx.lineTo(x, y);
        }
    });

    ctx.stroke();
}

// 切换收藏状态
async function toggleFavorite(itemId, event) {
    event.stopPropagation();
    const button = event.target;

    try {
        const response = await fetch(`${API_BASE_URL}/api/items/${itemId}/favorite`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            }
        });

        const result = await response.json();

        if (result.code === 0) {
            // 更新按钮状态
            if (result.data.is_favorited) {
                button.textContent = '⭐ 已收藏';
                button.classList.add('favorited');
            } else {
                button.textContent = '☆ 收藏';
                button.classList.remove('favorited');
            }
        }
    } catch (error) {
        console.error('切换收藏失败:', error);
    }
}

// 筛选收藏商品
function filterByFavorite() {
    currentFilter.isRecommended = null;
    currentFilter.isFavorited = true;
    currentFilter.page = 1;

    // 更新标签页状态
    document.querySelectorAll('.filter-tab').forEach(tab => {
        tab.classList.remove('active');
    });
    event.target.classList.add('active');

    loadItems();
}

// AI分析商品
async function analyzeItem(itemId, itemName) {
    // 显示加载状态
    showAIModal(itemName, '正在分析中，请稍候...\n\n🤖 AI正在综合分析：\n- 价格走势\n- 市场供需\n- 历史数据\n- 投资价值');

    try {
        const response = await fetch(`${API_BASE_URL}/api/items/analyze?item_id=${itemId}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
        });

        const result = await response.json();

        if (result.code === 0) {
            const data = result.data;
            const ml = data.ml_analysis;

            // 格式化大盘情绪
            const getSentimentText = (sentiment) => {
                if (sentiment === 'bullish') return '🐂 牛市';
                if (sentiment === 'bearish') return '🐻 熊市';
                return '😐 震荡';
            };

            const getMarketTrendText = (trend) => {
                if (trend === 'up') return '📈 上涨';
                if (trend === 'down') return '📉 下跌';
                return '➡️ 横盘';
            };

            // 格式化ML分析结果
            const mlSection = `
📊 **机器学习分析**
━━━━━━━━━━━━━━━━
趋势方向: ${ml.trend_direction} ${ml.trend_direction === '上涨' ? '📈' : ml.trend_direction === '下跌' ? '📉' : '➡️'}
趋势强度: ${ml.trend_strength.toFixed(1)}%
波动性: ${(ml.volatility * 100).toFixed(1)}%
预测价格(7天后): ¥${ml.predicted_price.toFixed(2)}
预测置信度: ${(ml.confidence * 100).toFixed(0)}%
推荐评分: ${ml.recommendation_score.toFixed(0)}/100 ${getScoreEmoji(ml.recommendation_score)}

💰 **当前价格**
Steam: ¥${data.current_prices.steam.toFixed(2)}
BUFF: ¥${data.current_prices.buff.toFixed(2)}
悠悠有品: ¥${data.current_prices.youpin.toFixed(2)}
C5: ¥${data.current_prices.c5.toFixed(2)}

🌍 **大盘行情**
━━━━━━━━━━━━━━━━
大盘指数: ${ml.market_index ? ml.market_index.toFixed(2) : 'N/A'}
市场情绪: ${getSentimentText(ml.market_sentiment)}
7日走势: ${getMarketTrendText(ml.market_trend)} (${ml.market_7d_change ? (ml.market_7d_change * 100).toFixed(2) : 0}%)
24h波动: ${ml.market_24h_volatility ? (ml.market_24h_volatility * 100).toFixed(2) : 0}%
`;

            const content = mlSection + '\n\n' + data.ai_advice;
            showAIModal(itemName, content);
        } else {
            showAIModal(itemName, `❌ 分析失败: ${result.message}`);
        }
    } catch (error) {
        showAIModal(itemName, `❌ 请求失败: ${error.message}\n\n请确保API服务正常运行。`);
    }
}

function getScoreEmoji(score) {
    if (score >= 80) return '🔥 强烈推荐';
    if (score >= 65) return '👍 建议关注';
    if (score >= 50) return '😐 中性';
    if (score >= 35) return '⚠️ 谨慎';
    return '❌ 不推荐';
}

// 简单的Markdown解析
function parseMarkdown(text) {
    return text
        // 转义HTML
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        // 标题
        .replace(/^### (.+)$/gm, '<h4 class="md-h3">$1</h4>')
        .replace(/^## (.+)$/gm, '<h3 class="md-h2">$1</h3>')
        .replace(/^# (.+)$/gm, '<h2 class="md-h1">$1</h2>')
        // 粗体
        .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
        // 斜体
        .replace(/\*(.+?)\*/g, '<em>$1</em>')
        // 分隔线
        .replace(/━+/g, '<hr class="md-hr">')
        .replace(/---/g, '<hr class="md-hr">')
        // 列表
        .replace(/^- (.+)$/gm, '<li>$1</li>')
        // 换行
        .replace(/\n\n/g, '</p><p>')
        .replace(/\n/g, '<br>');
}

function showAIModal(itemName, content) {
    // 移除已存在的模态框
    const existingModal = document.getElementById('aiModal');
    if (existingModal) existingModal.remove();

    // 解析Markdown
    const htmlContent = parseMarkdown(content);

    const modal = document.createElement('div');
    modal.id = 'aiModal';
    modal.className = 'ai-modal';
    modal.innerHTML = `
        <div class="ai-modal-content">
            <div class="ai-modal-header">
                <h3>🤖 AI投资分析 - ${itemName}</h3>
                <button class="ai-modal-close" onclick="closeAIModal()">✕</button>
            </div>
            <div class="ai-modal-body">
                <div class="md-content"><p>${htmlContent}</p></div>
            </div>
        </div>
    `;

    document.body.appendChild(modal);

    // 点击背景关闭
    modal.addEventListener('click', (e) => {
        if (e.target === modal) closeAIModal();
    });
}

function closeAIModal() {
    const modal = document.getElementById('aiModal');
    if (modal) modal.remove();
}

// ==================== 价格预测功能 ====================

// 显示价格预测指南
function showPredictionGuide() {
    showPredictionModal('价格预测功能', `
🤖 **LSTM深度学习价格预测**
━━━━━━━━━━━━━━━━

本系统使用 **LSTM神经网络** 进行价格预测：

📊 **技术原理**
- 2层LSTM + 3层全连接网络
- 基于前30天的收盘价进行训练
- 自动学习价格走势规律

🎯 **使用方法**
1. 在商品列表中找到想预测的商品
2. 点击 "📈 预测" 按钮
3. 系统将自动分析并预测未来7天价格

⚠️ **风险提示**
- 预测结果仅供参考，不构成投资建议
- 市场波动较大时预测准确度可能下降
- 建议结合AI分析综合判断

💡 **最佳实践**
- 优先关注置信度高的预测
- 结合大盘走势进行分析
- 多看历史数据验证模型准确性
    `);
}

// LSTM价格预测 - 跳转到预测页面
async function predictPrice(itemId, itemName) {
    // 跳转到预测页面，并传递商品信息
    const encodedName = encodeURIComponent(itemName);
    window.location.href = `prediction.html?item_id=${itemId}&item_name=${encodedName}`;
}

// 显示预测模态框
function showPredictionModal(title, content) {
    const existingModal = document.getElementById('predictionModal');
    if (existingModal) existingModal.remove();

    const htmlContent = parseMarkdown(content);

    const modal = document.createElement('div');
    modal.id = 'predictionModal';
    modal.className = 'ai-modal';
    modal.innerHTML = `
        <div class="ai-modal-content" style="border-top: 4px solid #27ae60;">
            <div class="ai-modal-header" style="background: linear-gradient(135deg, #27ae60 0%, #2ecc71 100%);">
                <h3>📈 ${title}</h3>
                <button class="ai-modal-close" onclick="closePredictionModal()">✕</button>
            </div>
            <div class="ai-modal-body">
                <div class="md-content"><p>${htmlContent}</p></div>
            </div>
        </div>
    `;

    document.body.appendChild(modal);

    modal.addEventListener('click', (e) => {
        if (e.target === modal) closePredictionModal();
    });
}

function closePredictionModal() {
    const modal = document.getElementById('predictionModal');
    if (modal) modal.remove();
}

// 页面加载完成后初始化
document.addEventListener('DOMContentLoaded', init);

