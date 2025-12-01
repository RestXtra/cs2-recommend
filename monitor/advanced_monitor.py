"""高级监控窗口 - 真正有用的版本"""
import tkinter as tk
from tkinter import ttk, scrolledtext
import threading
import subprocess
import sys
import time
import json
from pathlib import Path
from datetime import datetime

# 尝试导入 ttkbootstrap 进行美化
try:
    import ttkbootstrap as tb
    from ttkbootstrap.constants import *
    HAS_BOOTSTRAP = True
except ImportError:
    HAS_BOOTSTRAP = False
    import tkinter as tk
    from tkinter import ttk

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from utils.mongo_client import MongoDBClient
from utils.redis_client import RedisClient


class AdvancedMonitor:
    def __init__(self, root):
        self.root = root
        self.root.title("CS2市场爬虫高级监控系统")
        self.root.geometry("1200x800")
        # self.root.resizable(True, True) # ttkbootstrap 可能会自动处理
        
        # 数据库连接
        self.mongo_client = MongoDBClient()
        self.redis_client = RedisClient()
        self.collection = self.mongo_client.get_collection('items')
        
        # 爬虫进程
        self.crawler_process = None
        self.is_running = False

        # 进度文件
        self.progress_file = project_root / 'data' / 'crawl_progress.json'

        # 抓取速率统计
        self.crawl_history = []  # 存储最近的抓取记录 [(timestamp, count), ...]
        self.last_crawled_count = 0
        self.speed_history = []  # 存储最近的速率数据（用于心电图）

        # 创建界面
        self.create_widgets()
        
        # 启动更新线程
        self.update_thread = threading.Thread(target=self.update_loop, daemon=True)
        self.update_thread.start()
    
    def create_widgets(self):
        """创建界面组件"""
        # 标题
        if HAS_BOOTSTRAP:
            title_frame = tb.Frame(self.root, bootstyle="primary")
            title_frame.pack(fill=tk.X)
            
            title_label = tb.Label(
                title_frame,
                text="🎮 CS2市场爬虫高级监控系统",
                font=('Microsoft YaHei UI', 20, 'bold'),
                bootstyle="inverse-primary"
            )
            title_label.pack(pady=20)
        else:
            title_frame = tk.Frame(self.root, bg='#2c3e50', height=80)
            title_frame.pack(fill=tk.X)
            title_frame.pack_propagate(False)
            
            title_label = tk.Label(
                title_frame,
                text="🎮 CS2市场爬虫高级监控系统",
                font=('Microsoft YaHei UI', 20, 'bold'),
                bg='#2c3e50',
                fg='white'
            )
            title_label.pack(pady=20)
        
        # 主容器
        if HAS_BOOTSTRAP:
            main_container = tb.Frame(self.root)
        else:
            main_container = tk.Frame(self.root)
        main_container.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # 左侧面板
        if HAS_BOOTSTRAP:
            left_panel = tb.Frame(main_container, width=400)
            right_panel = tb.Frame(main_container)
        else:
            left_panel = tk.Frame(main_container, width=400)
            right_panel = tk.Frame(main_container)

        left_panel.pack(side=tk.LEFT, fill=tk.BOTH, padx=(0, 5))
        right_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(5, 0))
        
        # === 左侧：统计和控制 ===
        self.create_stats_panel(left_panel)
        self.create_control_panel(left_panel)
        self.create_distributed_panel(left_panel)  # 分布式节点管理
        self.create_progress_panel(left_panel)

        # === 右侧：日志 ===
        self.create_log_panel(right_panel)
    
    def create_stats_panel(self, parent):
        """创建统计面板"""
        if HAS_BOOTSTRAP:
            frame = tb.LabelFrame(parent, text="📊 实时统计", bootstyle="info")
        else:
            frame = tk.LabelFrame(parent, text="📊 实时统计", font=('Microsoft YaHei UI', 12, 'bold'))
        frame.pack(fill=tk.X, pady=(0, 10))

        # 统计卡片容器
        if HAS_BOOTSTRAP:
            cards_frame = tb.Frame(frame)
        else:
            cards_frame = tk.Frame(frame)
        cards_frame.pack(fill=tk.X, padx=10, pady=10)

        # 创建3个统计卡片
        self.total_label = self.create_stat_card(cards_frame, "📦", "总商品数", "0", 0, 0, "primary")
        self.recommended_label = self.create_stat_card(cards_frame, "⭐", "推荐商品", "0", 0, 1, "warning")
        self.crawled_label = self.create_stat_card(cards_frame, "🔄", "已抓取", "0", 0, 2, "success")

        # 创建心电图样式的速率显示
        if HAS_BOOTSTRAP:
            speed_frame = tb.Frame(frame, bootstyle="light")
        else:
            speed_frame = tk.Frame(frame, bg='#ecf0f1', relief=tk.RAISED, borderwidth=2)
        speed_frame.pack(fill=tk.X, padx=10, pady=(0, 10))

        # 标题
        if HAS_BOOTSTRAP:
            title_frame = tb.Frame(speed_frame)
            title_frame.pack(fill=tk.X, padx=10, pady=5)
            tb.Label(title_frame, text="⚡ 抓取速率", font=('Microsoft YaHei UI', 12, 'bold')).pack(side=tk.LEFT)
            self.speed_value_label = tb.Label(title_frame, text="0/分钟", font=('Microsoft YaHei UI', 12, 'bold'), bootstyle="success")
        else:
            title_frame = tk.Frame(speed_frame, bg='#ecf0f1')
            title_frame.pack(fill=tk.X, padx=10, pady=5)
            tk.Label(title_frame, text="⚡ 抓取速率", font=('Microsoft YaHei UI', 12, 'bold'), bg='#ecf0f1').pack(side=tk.LEFT)
            self.speed_value_label = tk.Label(title_frame, text="0/分钟", font=('Microsoft YaHei UI', 12, 'bold'), bg='#ecf0f1', fg='#27ae60')
        
        self.speed_value_label.pack(side=tk.RIGHT)

        # 心电图画布
        self.speed_canvas = tk.Canvas(speed_frame, height=80, bg='#2c3e50', highlightthickness=0)
        self.speed_canvas.pack(fill=tk.X, padx=10, pady=(0, 10))

        # 速率历史数据（用于绘制心电图）
        self.speed_history = []  # 存储最近60秒的速率数据
    
    def create_stat_card(self, parent, icon, title, value, row, col, bootstyle="default"):
        """创建统计卡片"""
        if HAS_BOOTSTRAP:
            card = tb.Frame(parent, bootstyle="light", padding=10)
            card.grid(row=row, column=col, padx=5, pady=5, sticky='nsew')
            
            parent.grid_rowconfigure(row, weight=1)
            parent.grid_columnconfigure(col, weight=1)

            tb.Label(card, text=icon, font=('Segoe UI Emoji', 20)).pack(pady=(0, 5))
            value_label = tb.Label(card, text=value, font=('Microsoft YaHei UI', 16, 'bold'), bootstyle=bootstyle)
            value_label.pack()
            tb.Label(card, text=title, font=('Microsoft YaHei UI', 9), bootstyle="secondary").pack(pady=(5, 0))
            
            return value_label
        else:
            card = tk.Frame(parent, bg='#ecf0f1', relief=tk.RAISED, borderwidth=2)
            card.grid(row=row, column=col, padx=5, pady=5, sticky='nsew')

            parent.grid_rowconfigure(row, weight=1)
            parent.grid_columnconfigure(col, weight=1)

            icon_label = tk.Label(card, text=icon, font=('Segoe UI Emoji', 20), bg='#ecf0f1')
            icon_label.pack(pady=(10, 0))

            value_label = tk.Label(card, text=value, font=('Microsoft YaHei UI', 16, 'bold'), bg='#ecf0f1', fg='#2c3e50')
            value_label.pack()

            title_label = tk.Label(card, text=title, font=('Microsoft YaHei UI', 9), bg='#ecf0f1', fg='#7f8c8d')
            title_label.pack(pady=(0, 10))

            return value_label


    def draw_speed_chart(self):
        """绘制心电图样式的速率图"""
        try:
            self.speed_canvas.delete("all")

            if len(self.speed_history) < 2:
                # 数据不足，显示提示
                self.speed_canvas.create_text(
                    self.speed_canvas.winfo_width() / 2,
                    40,
                    text="等待数据...",
                    fill='#7f8c8d',
                    font=('Microsoft YaHei UI', 10)
                )
                return

            # 获取画布尺寸
            width = self.speed_canvas.winfo_width()
            height = 80

            if width <= 1:
                return

            # 绘制网格线
            for i in range(0, height, 20):
                self.speed_canvas.create_line(0, i, width, i, fill='#34495e', width=1)

            # 计算最大速率（用于缩放）
            max_speed = max(self.speed_history) if self.speed_history else 1
            if max_speed == 0:
                max_speed = 1

            # 绘制折线图
            points = []
            step = width / max(len(self.speed_history) - 1, 1)

            for i, speed in enumerate(self.speed_history):
                x = i * step
                y = height - (speed / max_speed * (height - 10)) - 5
                points.append((x, y))

            # 绘制线条
            if len(points) >= 2:
                for i in range(len(points) - 1):
                    self.speed_canvas.create_line(
                        points[i][0], points[i][1],
                        points[i+1][0], points[i+1][1],
                        fill='#27ae60',
                        width=2,
                        smooth=True
                    )

            # 绘制最大值标签
            self.speed_canvas.create_text(
                10, 10,
                text=f"峰值: {max_speed:.0f}/分钟",
                fill='#ecf0f1',
                font=('Microsoft YaHei UI', 8),
                anchor='nw'
            )

        except Exception as e:
            pass
    
    def create_control_panel(self, parent):
        """创建控制面板"""
        if HAS_BOOTSTRAP:
            frame = tb.LabelFrame(parent, text="⚙️ 爬虫控制", bootstyle="info")
        else:
            frame = tk.LabelFrame(parent, text="⚙️ 爬虫控制", font=('Microsoft YaHei UI', 12, 'bold'))
        frame.pack(fill=tk.X, pady=(0, 10))
        
        # 参数设置
        if HAS_BOOTSTRAP:
            params_frame = tb.Frame(frame)
        else:
            params_frame = tk.Frame(frame)
        params_frame.pack(fill=tk.X, padx=10, pady=10)
        
        # 延迟设置
        if HAS_BOOTSTRAP:
            tb.Label(params_frame, text="请求延迟(秒):").grid(row=0, column=0, sticky='w', pady=5)
            self.delay_var = tk.DoubleVar(value=1.5)
            delay_spin = tb.Spinbox(params_frame, from_=0.5, to=10.0, increment=0.5, textvariable=self.delay_var, width=10)
            delay_spin.grid(row=0, column=1, sticky='w', padx=5)
            
            # 抓取页数
            tb.Label(params_frame, text="抓取页数:").grid(row=1, column=0, sticky='w', pady=5)
            self.pages_var = tk.IntVar(value=0)
            pages_spin = tb.Spinbox(params_frame, from_=0, to=500, increment=10, textvariable=self.pages_var, width=10)
            pages_spin.grid(row=1, column=1, sticky='w', padx=5)
            tb.Label(params_frame, text="(0=全部)", bootstyle="secondary").grid(row=1, column=2, sticky='w')
        else:
            tk.Label(params_frame, text="请求延迟(秒):", font=('Microsoft YaHei UI', 10)).grid(row=0, column=0, sticky='w', pady=5)
            self.delay_var = tk.DoubleVar(value=1.5)
            delay_spin = tk.Spinbox(params_frame, from_=0.5, to=10.0, increment=0.5, textvariable=self.delay_var, width=10)
            delay_spin.grid(row=0, column=1, sticky='w', padx=5)
            
            # 抓取页数
            tk.Label(params_frame, text="抓取页数:", font=('Microsoft YaHei UI', 10)).grid(row=1, column=0, sticky='w', pady=5)
            self.pages_var = tk.IntVar(value=0)
            pages_spin = tk.Spinbox(params_frame, from_=0, to=500, increment=10, textvariable=self.pages_var, width=10)
            pages_spin.grid(row=1, column=1, sticky='w', padx=5)
            tk.Label(params_frame, text="(0=全部)", font=('Microsoft YaHei UI', 8), fg='gray').grid(row=1, column=2, sticky='w')
        
        # 按钮
        if HAS_BOOTSTRAP:
            buttons_frame = tb.Frame(frame)
        else:
            buttons_frame = tk.Frame(frame)
        buttons_frame.pack(fill=tk.X, padx=10, pady=(0, 10))
        
        if HAS_BOOTSTRAP:
            self.start_btn = tb.Button(
                buttons_frame,
                text="▶ 启动爬虫",
                command=self.start_crawler,
                bootstyle="success",
                cursor='hand2'
            )
            self.start_btn.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
            
            self.stop_btn = tb.Button(
                buttons_frame,
                text="⏸ 停止爬虫",
                command=self.stop_crawler,
                bootstyle="danger",
                cursor='hand2',
                state=tk.DISABLED
            )
            self.stop_btn.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(5, 0))
        else:
            self.start_btn = tk.Button(
                buttons_frame,
                text="▶ 启动爬虫",
                command=self.start_crawler,
                bg='#27ae60',
                fg='white',
                font=('Microsoft YaHei UI', 11, 'bold'),
                relief=tk.RAISED,
                borderwidth=2,
                cursor='hand2'
            )
            self.start_btn.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
            
            self.stop_btn = tk.Button(
                buttons_frame,
                text="⏸ 停止爬虫",
                command=self.stop_crawler,
                bg='#e74c3c',
                fg='white',
                font=('Microsoft YaHei UI', 11, 'bold'),
                relief=tk.RAISED,
                borderwidth=2,
                cursor='hand2',
                state=tk.DISABLED
            )
            self.stop_btn.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(5, 0))

    def create_distributed_panel(self, parent):
        """创建分布式节点管理面板"""
        if HAS_BOOTSTRAP:
            frame = tb.LabelFrame(parent, text="🖥️ 分布式节点管理 (Scrapy-Redis)", bootstyle="info")
        else:
            frame = tk.LabelFrame(parent, text="🖥️ 分布式节点管理 (Scrapy-Redis)", font=('Microsoft YaHei UI', 12, 'bold'))
        frame.pack(fill=tk.X, pady=(0, 10))

        # 说明
        if HAS_BOOTSTRAP:
            tb.Label(frame, text="使用多个Scrapy进程并行抓取，共享Redis任务队列", bootstyle="secondary").pack(anchor='w', padx=10, pady=(5,0))
        else:
            tk.Label(frame, text="使用多个Scrapy进程并行抓取，共享Redis任务队列",
                     font=('Microsoft YaHei UI', 8), fg='gray').pack(anchor='w', padx=10, pady=(5,0))

        # 状态显示
        if HAS_BOOTSTRAP:
            status_frame = tb.Frame(frame)
            status_frame.pack(fill=tk.X, padx=10, pady=5)

            tb.Label(status_frame, text="运行节点:").pack(side=tk.LEFT)
            self.nodes_count_label = tb.Label(status_frame, text="0 / 5", font=('Microsoft YaHei UI', 10, 'bold'), bootstyle="success")
            self.nodes_count_label.pack(side=tk.LEFT, padx=(5, 15))

            tb.Label(status_frame, text="队列任务:").pack(side=tk.LEFT)
            self.queue_size_label = tb.Label(status_frame, text="0", font=('Microsoft YaHei UI', 10, 'bold'), bootstyle="info")
            self.queue_size_label.pack(side=tk.LEFT, padx=5)
        else:
            status_frame = tk.Frame(frame)
            status_frame.pack(fill=tk.X, padx=10, pady=5)

            tk.Label(status_frame, text="运行节点:", font=('Microsoft YaHei UI', 10)).pack(side=tk.LEFT)
            self.nodes_count_label = tk.Label(status_frame, text="0 / 5", font=('Microsoft YaHei UI', 10, 'bold'), fg='#27ae60')
            self.nodes_count_label.pack(side=tk.LEFT, padx=(5, 15))

            tk.Label(status_frame, text="队列任务:", font=('Microsoft YaHei UI', 10)).pack(side=tk.LEFT)
            self.queue_size_label = tk.Label(status_frame, text="0", font=('Microsoft YaHei UI', 10, 'bold'), fg='#3498db')
            self.queue_size_label.pack(side=tk.LEFT, padx=5)

        # 控制按钮
        if HAS_BOOTSTRAP:
            btn_frame = tb.Frame(frame)
            btn_frame.pack(fill=tk.X, padx=10, pady=(0, 10))

            self.start_distributed_btn = tb.Button(
                btn_frame, text="▶ 启动集群", command=self.start_distributed,
                bootstyle="success-outline", cursor='hand2'
            )
            self.start_distributed_btn.pack(side=tk.LEFT, padx=2)

            self.stop_distributed_btn = tb.Button(
                btn_frame, text="■ 停止集群", command=self.stop_distributed,
                bootstyle="danger-outline", cursor='hand2', state=tk.DISABLED
            )
            self.stop_distributed_btn.pack(side=tk.LEFT, padx=2)

            tb.Button(
                btn_frame, text="➕ 增加节点", command=self.add_distributed_node,
                bootstyle="info-outline", cursor='hand2'
            ).pack(side=tk.LEFT, padx=2)

            tb.Button(
                btn_frame, text="➖ 减少节点", command=self.remove_distributed_node,
                bootstyle="warning-outline", cursor='hand2'
            ).pack(side=tk.LEFT, padx=2)
        else:
            btn_frame = tk.Frame(frame)
            btn_frame.pack(fill=tk.X, padx=10, pady=(0, 10))

            self.start_distributed_btn = tk.Button(
                btn_frame, text="▶ 启动集群", command=self.start_distributed,
                bg='#27ae60', fg='white', font=('Microsoft YaHei UI', 9), cursor='hand2'
            )
            self.start_distributed_btn.pack(side=tk.LEFT, padx=2)

            self.stop_distributed_btn = tk.Button(
                btn_frame, text="■ 停止集群", command=self.stop_distributed,
                bg='#e74c3c', fg='white', font=('Microsoft YaHei UI', 9), cursor='hand2', state=tk.DISABLED
            )
            self.stop_distributed_btn.pack(side=tk.LEFT, padx=2)

            tk.Button(
                btn_frame, text="➕ 增加节点", command=self.add_distributed_node,
                bg='#3498db', fg='white', font=('Microsoft YaHei UI', 9), cursor='hand2'
            ).pack(side=tk.LEFT, padx=2)

            tk.Button(
                btn_frame, text="➖ 减少节点", command=self.remove_distributed_node,
                bg='#e67e22', fg='white', font=('Microsoft YaHei UI', 9), cursor='hand2'
            ).pack(side=tk.LEFT, padx=2)

    def create_progress_panel(self, parent):
        """创建进度面板"""
        if HAS_BOOTSTRAP:
            frame = tb.LabelFrame(parent, text="📋 爬取进度", bootstyle="info")
        else:
            frame = tk.LabelFrame(parent, text="📋 爬取进度", font=('Microsoft YaHei UI', 12, 'bold'))
        frame.pack(fill=tk.BOTH, expand=True)

        if HAS_BOOTSTRAP:
            info_frame = tb.Frame(frame)
        else:
            info_frame = tk.Frame(frame)
        info_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # 状态信息
        self.status_text = tk.Text(info_frame, height=8, font=('Consolas', 10), bg='#f8f9fa', relief=tk.FLAT)
        self.status_text.pack(fill=tk.BOTH, expand=True)
        self.status_text.insert('1.0', '等待启动...')
        self.status_text.config(state=tk.DISABLED)

    def create_log_panel(self, parent):
        """创建日志面板"""
        if HAS_BOOTSTRAP:
            frame = tb.LabelFrame(parent, text="📝 运行日志", bootstyle="info")
        else:
            frame = tk.LabelFrame(parent, text="📝 运行日志", font=('Microsoft YaHei UI', 12, 'bold'))
        frame.pack(fill=tk.BOTH, expand=True)

        # 日志文本框
        self.log_text = scrolledtext.ScrolledText(
            frame,
            font=('Consolas', 9),
            bg='#1e1e1e',
            fg='#d4d4d4',
            insertbackground='white',
            relief=tk.FLAT
        )
        self.log_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # 配置标签颜色
        self.log_text.tag_config('INFO', foreground='#4ec9b0')
        self.log_text.tag_config('SUCCESS', foreground='#4ec9b0', font=('Consolas', 9, 'bold'))
        self.log_text.tag_config('WARNING', foreground='#dcdcaa')
        self.log_text.tag_config('ERROR', foreground='#f48771')

        # 清空按钮
        if HAS_BOOTSTRAP:
            clear_btn = tb.Button(
                frame,
                text="🗑 清空日志",
                command=self.clear_log,
                bootstyle="secondary",
                cursor='hand2'
            )
        else:
            clear_btn = tk.Button(
                frame,
                text="🗑 清空日志",
                command=self.clear_log,
                bg='#95a5a6',
                fg='white',
                font=('Microsoft YaHei UI', 10),
                cursor='hand2'
            )
        clear_btn.pack(pady=5)


    def log(self, message, level='INFO'):
        """添加日志"""
        timestamp = datetime.now().strftime('%H:%M:%S')
        log_line = f"[{timestamp}] {message}\n"

        self.log_text.config(state=tk.NORMAL)
        self.log_text.insert(tk.END, log_line, level)
        self.log_text.see(tk.END)
        self.log_text.config(state=tk.DISABLED)

    def clear_log(self):
        """清空日志"""
        self.log_text.config(state=tk.NORMAL)
        self.log_text.delete('1.0', tk.END)
        self.log_text.config(state=tk.DISABLED)
        self.log("日志已清空", "INFO")

    def update_stats(self):
        """更新统计信息"""
        try:
            # 数据库统计
            total = self.collection.count_documents({})
            recommended = self.collection.count_documents({'is_recommended': True})

            # 读取进度文件获取已抓取数量
            crawled = 0
            if self.progress_file.exists():
                with open(self.progress_file, 'r', encoding='utf-8') as f:
                    progress = json.load(f)
                    crawled = progress.get('total_crawled', 0)

            # 计算更新速率（基于进度文件中的抓取数量变化）
            import time
            current_time = time.time()

            # 记录当前抓取数量（用于计算速率）
            if crawled != self.last_crawled_count:
                self.crawl_history.append((current_time, crawled))
                self.last_crawled_count = crawled

            # 只保留最近2分钟的数据
            self.crawl_history = [(t, c) for t, c in self.crawl_history if current_time - t <= 120]

            # 计算速率（基于抓取数量的增长）
            speed = 0
            if len(self.crawl_history) >= 2:
                first_time, first_count = self.crawl_history[0]
                last_time, last_count = self.crawl_history[-1]
                time_diff = (last_time - first_time) / 60  # 转换为分钟
                if time_diff > 0:
                    count_diff = last_count - first_count
                    # 如果计数减少（可能是重启），重置历史记录
                    if count_diff < 0:
                        self.crawl_history = [(current_time, crawled)]
                        speed = 0
                    else:
                        speed = count_diff / time_diff

            # 更新速率历史（用于心电图）
            self.speed_history.append(speed)
            # 只保留最近60个数据点
            if len(self.speed_history) > 60:
                self.speed_history.pop(0)

            # 更新显示
            self.total_label.config(text=f"{total:,}")
            self.recommended_label.config(text=f"{recommended:,}")
            self.crawled_label.config(text=f"{crawled:,}")
            self.speed_value_label.config(text=f"{speed:.0f}/分钟")

            # 绘制心电图
            self.draw_speed_chart()

        except Exception as e:
            self.log(f"更新统计失败: {e}", "ERROR")

    def update_status(self):
        """更新状态信息"""
        try:
            status_info = []

            # 爬虫状态
            if self.is_running:
                status_info.append("🟢 爬虫状态: 运行中")
            else:
                status_info.append("🔴 爬虫状态: 已停止")

            # 读取进度
            if self.progress_file.exists():
                with open(self.progress_file, 'r', encoding='utf-8') as f:
                    progress = json.load(f)
                    status_info.append(f"当前页码: {progress.get('current_page', 0)}")
                    status_info.append(f"已抓取: {progress.get('total_crawled', 0)}")
                    status_info.append(f"最后更新: {progress.get('last_update', 'N/A')}")

            # 数据库状态
            total = self.collection.count_documents({})
            status_info.append(f"数据库商品数: {total:,}")

            # 更新显示
            self.status_text.config(state=tk.NORMAL)
            self.status_text.delete('1.0', tk.END)
            self.status_text.insert('1.0', '\n'.join(status_info))
            self.status_text.config(state=tk.DISABLED)

        except Exception as e:
            pass

    def update_loop(self):
        """更新循环"""
        while True:
            try:
                self.update_stats()
                self.update_status()
                self.update_distributed_status()
            except:
                pass
            time.sleep(2)

    def update_distributed_status(self):
        """更新分布式节点状态"""
        try:
            from crawler.node_manager import node_manager
            status = node_manager.get_status()
            self.nodes_count_label.config(text=f"{status['current_nodes']} / {status['max_nodes']}")
            self.queue_size_label.config(text=str(status['queue_size']))
        except:
            pass

    def start_crawler(self):
        """启动爬虫"""
        if self.is_running:
            self.log("爬虫已在运行中", "WARNING")
            return

        delay = self.delay_var.get()
        pages = self.pages_var.get()

        self.log(f"正在启动爬虫... (延迟:{delay}s, 页数:{'全部' if pages == 0 else pages})", "INFO")
        self.start_btn.config(state=tk.DISABLED)
        self.stop_btn.config(state=tk.NORMAL)
        self.is_running = True

        # 在新线程中启动
        threading.Thread(target=self._run_crawler, args=(delay, pages), daemon=True).start()

    def _run_crawler(self, delay, pages):
        """运行爬虫"""
        try:
            cmd = [
                sys.executable,
                str(project_root / "scripts" / "crawl_all_enhanced.py"),
                "--delay", str(delay),
                "--continue"
            ]

            if pages > 0:
                cmd.extend(["--pages", str(pages)])

            self.crawler_process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                cwd=str(project_root)
            )

            # 实时读取输出
            for line in self.crawler_process.stdout:
                line = line.strip()
                if " | " in line:
                    parts = line.split(" | ", 2)
                    if len(parts) >= 3:
                        line = parts[2]

                # 根据内容分类
                if "✓" in line or "成功" in line or "完成" in line:
                    self.log(line, "SUCCESS")
                elif "错误" in line or "失败" in line or "ERROR" in line:
                    self.log(line, "ERROR")
                elif "警告" in line or "WARNING" in line:
                    self.log(line, "WARNING")
                else:
                    self.log(line, "INFO")

            self.crawler_process.wait()

            if self.crawler_process.returncode == 0:
                self.log("✓ 爬虫运行完成", "SUCCESS")
            else:
                self.log(f"✗ 爬虫异常退出 (代码: {self.crawler_process.returncode})", "ERROR")

        except Exception as e:
            self.log(f"✗ 爬虫运行失败: {e}", "ERROR")
        finally:
            self.is_running = False
            self.start_btn.config(state=tk.NORMAL)
            self.stop_btn.config(state=tk.DISABLED)
            self.crawler_process = None

    def stop_crawler(self):
        """停止爬虫"""
        if not self.is_running or not self.crawler_process:
            self.log("没有运行中的爬虫", "WARNING")
            return

        self.log("正在停止爬虫...", "WARNING")

        try:
            self.crawler_process.terminate()
            self.crawler_process.wait(timeout=5)
            self.log("✓ 爬虫已停止", "INFO")
        except:
            try:
                self.crawler_process.kill()
                self.log("✓ 爬虫已强制停止", "WARNING")
            except:
                self.log("✗ 停止爬虫失败", "ERROR")

        self.is_running = False
        self.start_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.DISABLED)

    # ========== 分布式节点管理方法 ==========

    def start_distributed(self):
        """启动分布式爬虫集群"""
        try:
            from crawler.node_manager import node_manager
            node_manager.start(initial_nodes=2)
            self.log("✓ 分布式集群已启动", "SUCCESS")
            self.start_distributed_btn.config(state=tk.DISABLED)
            self.stop_distributed_btn.config(state=tk.NORMAL)
        except Exception as e:
            self.log(f"启动集群失败: {e}", "ERROR")

    def stop_distributed(self):
        """停止分布式爬虫集群"""
        try:
            from crawler.node_manager import node_manager
            node_manager.stop()
            self.log("✓ 分布式集群已停止", "WARNING")
            self.start_distributed_btn.config(state=tk.NORMAL)
            self.stop_distributed_btn.config(state=tk.DISABLED)
        except Exception as e:
            self.log(f"停止集群失败: {e}", "ERROR")

    def add_distributed_node(self):
        """添加一个分布式节点"""
        try:
            from crawler.node_manager import node_manager
            node_id = node_manager.add_node()
            if node_id:
                self.log(f"✓ 已添加节点: {node_id}", "SUCCESS")
            else:
                self.log("无法添加节点（已达上限或未启动）", "WARNING")
        except Exception as e:
            self.log(f"添加节点失败: {e}", "ERROR")

    def remove_distributed_node(self):
        """移除一个分布式节点"""
        try:
            from crawler.node_manager import node_manager
            if node_manager.remove_node():
                self.log("✓ 已移除一个节点", "WARNING")
            else:
                self.log("无法移除节点（已达下限）", "WARNING")
        except Exception as e:
            self.log(f"移除节点失败: {e}", "ERROR")


def main():
    if HAS_BOOTSTRAP:
        # 使用更现代的主题 'superhero' 或 'flatly'
        root = tb.Window(themename="superhero")
        # 设置默认字体大小
        style = tb.Style()
        style.configure('.', font=('Microsoft YaHei UI', 10))
    else:
        root = tk.Tk()
    app = AdvancedMonitor(root)
    root.mainloop()


if __name__ == "__main__":
    main()


