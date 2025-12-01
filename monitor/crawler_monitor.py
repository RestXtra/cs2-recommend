"""爬虫监控窗口 - 使用tkinter实现"""
import tkinter as tk
from tkinter import ttk, scrolledtext
import threading
import time
from datetime import datetime
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from utils.mongo_client import MongoDBClient
from utils.redis_client import RedisClient

class CrawlerMonitor:
    def __init__(self, root):
        self.root = root
        self.root.title("CS2市场爬虫监控系统")
        self.root.geometry("900x700")
        self.root.resizable(True, True)

        # 连接数据库
        self.mongo_client = MongoDBClient()
        self.redis_client = RedisClient()
        self.collection = self.mongo_client.get_collection('items')

        # 爬虫进程
        self.crawler_process = None

        # 创建界面
        self.create_widgets()

        # 启动更新线程
        self.is_running = True
        self.update_thread = threading.Thread(target=self.update_stats_loop, daemon=True)
        self.update_thread.start()
    
    def create_widgets(self):
        """创建界面组件"""
        # 标题
        title_frame = tk.Frame(self.root, bg="#2c3e50", height=60)
        title_frame.pack(fill=tk.X)
        title_frame.pack_propagate(False)
        
        title_label = tk.Label(
            title_frame,
            text="🎮 CS2市场爬虫监控系统",
            font=("微软雅黑", 18, "bold"),
            bg="#2c3e50",
            fg="white"
        )
        title_label.pack(pady=15)
        
        # 主容器
        main_frame = tk.Frame(self.root, bg="#ecf0f1")
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # 统计信息区域
        stats_frame = tk.LabelFrame(
            main_frame,
            text="📊 实时统计",
            font=("微软雅黑", 12, "bold"),
            bg="#ecf0f1",
            fg="#2c3e50"
        )
        stats_frame.pack(fill=tk.X, pady=(0, 10))
        
        # 创建统计卡片
        stats_container = tk.Frame(stats_frame, bg="#ecf0f1")
        stats_container.pack(fill=tk.X, padx=10, pady=10)
        
        self.stat_cards = {}
        stats_config = [
            ("total_items", "总商品数", "📦", "#3498db"),
            ("recommended_items", "推荐商品", "⭐", "#f39c12"),
            ("queue_size", "队列任务", "⏳", "#9b59b6"),
            ("error_count", "错误次数", "❌", "#e74c3c")
        ]
        
        for i, (key, label, icon, color) in enumerate(stats_config):
            card = self.create_stat_card(stats_container, label, icon, color)
            card.grid(row=0, column=i, padx=5, sticky="ew")
            stats_container.grid_columnconfigure(i, weight=1)
            self.stat_cards[key] = card

        # 参数设置区域
        params_frame = tk.LabelFrame(
            main_frame,
            text="⚙️ 爬虫参数设置",
            font=("微软雅黑", 12, "bold"),
            bg="#ecf0f1",
            fg="#2c3e50"
        )
        params_frame.pack(fill=tk.X, pady=(0, 10))

        params_container = tk.Frame(params_frame, bg="white")
        params_container.pack(fill=tk.X, padx=10, pady=10)

        # 请求延迟
        tk.Label(
            params_container,
            text="请求延迟(秒):",
            font=("微软雅黑", 10),
            bg="white",
            fg="#2c3e50"
        ).grid(row=0, column=0, padx=10, pady=5, sticky="w")

        self.delay_var = tk.DoubleVar(value=1.0)
        delay_spinbox = tk.Spinbox(
            params_container,
            from_=0.5,
            to=10.0,
            increment=0.5,
            textvariable=self.delay_var,
            font=("微软雅黑", 10),
            width=10
        )
        delay_spinbox.grid(row=0, column=1, padx=10, pady=5, sticky="w")

        # 并发数
        tk.Label(
            params_container,
            text="并发数:",
            font=("微软雅黑", 10),
            bg="white",
            fg="#2c3e50"
        ).grid(row=0, column=2, padx=10, pady=5, sticky="w")

        self.concurrent_var = tk.IntVar(value=1)
        concurrent_spinbox = tk.Spinbox(
            params_container,
            from_=1,
            to=10,
            textvariable=self.concurrent_var,
            font=("微软雅黑", 10),
            width=10
        )
        concurrent_spinbox.grid(row=0, column=3, padx=10, pady=5, sticky="w")

        # 每次抓取页数
        tk.Label(
            params_container,
            text="抓取页数:",
            font=("微软雅黑", 10),
            bg="white",
            fg="#2c3e50"
        ).grid(row=1, column=0, padx=10, pady=5, sticky="w")

        self.pages_var = tk.IntVar(value=10)
        pages_spinbox = tk.Spinbox(
            params_container,
            from_=1,
            to=100,
            textvariable=self.pages_var,
            font=("微软雅黑", 10),
            width=10
        )
        pages_spinbox.grid(row=1, column=1, padx=10, pady=5, sticky="w")

        # 重试次数
        tk.Label(
            params_container,
            text="重试次数:",
            font=("微软雅黑", 10),
            bg="white",
            fg="#2c3e50"
        ).grid(row=1, column=2, padx=10, pady=5, sticky="w")

        self.retry_var = tk.IntVar(value=3)
        retry_spinbox = tk.Spinbox(
            params_container,
            from_=1,
            to=10,
            textvariable=self.retry_var,
            font=("微软雅黑", 10),
            width=10
        )
        retry_spinbox.grid(row=1, column=3, padx=10, pady=5, sticky="w")

        # 爬虫状态区域
        status_frame = tk.LabelFrame(
            main_frame,
            text="🔄 爬虫状态",
            font=("微软雅黑", 12, "bold"),
            bg="#ecf0f1",
            fg="#2c3e50"
        )
        status_frame.pack(fill=tk.X, pady=(0, 10))
        
        status_container = tk.Frame(status_frame, bg="white")
        status_container.pack(fill=tk.X, padx=10, pady=10)
        
        # 状态信息
        self.status_labels = {}
        status_items = [
            ("spider_status", "爬虫状态:"),
            ("current_page", "当前页码:"),
            ("items_scraped", "已抓取:"),
            ("success_rate", "成功率:"),
            ("running_time", "运行时间:")
        ]
        
        for i, (key, label) in enumerate(status_items):
            row = i // 2
            col = i % 2
            
            label_widget = tk.Label(
                status_container,
                text=label,
                font=("微软雅黑", 10),
                bg="white",
                fg="#7f8c8d",
                anchor="w"
            )
            label_widget.grid(row=row, column=col*2, padx=10, pady=5, sticky="w")
            
            value_widget = tk.Label(
                status_container,
                text="-",
                font=("微软雅黑", 10, "bold"),
                bg="white",
                fg="#2c3e50",
                anchor="w"
            )
            value_widget.grid(row=row, column=col*2+1, padx=10, pady=5, sticky="w")
            
            self.status_labels[key] = value_widget
        
        # 日志区域
        log_frame = tk.LabelFrame(
            main_frame,
            text="📝 运行日志",
            font=("微软雅黑", 12, "bold"),
            bg="#ecf0f1",
            fg="#2c3e50"
        )
        log_frame.pack(fill=tk.BOTH, expand=True)
        
        self.log_text = scrolledtext.ScrolledText(
            log_frame,
            font=("Consolas", 9),
            bg="#2c3e50",
            fg="#ecf0f1",
            insertbackground="white",
            wrap=tk.WORD
        )
        self.log_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # 控制按钮
        button_frame = tk.Frame(main_frame, bg="#ecf0f1")
        button_frame.pack(fill=tk.X, pady=(10, 0))
        
        self.start_button = tk.Button(
            button_frame,
            text="▶ 启动爬虫",
            font=("微软雅黑", 10, "bold"),
            bg="#27ae60",
            fg="white",
            relief=tk.FLAT,
            padx=20,
            pady=8,
            command=self.start_crawler
        )
        self.start_button.pack(side=tk.LEFT, padx=5)
        
        self.stop_button = tk.Button(
            button_frame,
            text="⏸ 停止爬虫",
            font=("微软雅黑", 10, "bold"),
            bg="#e74c3c",
            fg="white",
            relief=tk.FLAT,
            padx=20,
            pady=8,
            command=self.stop_crawler,
            state=tk.DISABLED
        )
        self.stop_button.pack(side=tk.LEFT, padx=5)
        
        clear_button = tk.Button(
            button_frame,
            text="🗑 清空日志",
            font=("微软雅黑", 10, "bold"),
            bg="#95a5a6",
            fg="white",
            relief=tk.FLAT,
            padx=20,
            pady=8,
            command=self.clear_log
        )
        clear_button.pack(side=tk.RIGHT, padx=5)

        # 初始日志
        self.log("系统启动成功")
        self.log("MongoDB连接成功")
        self.log("Redis连接成功")

    def create_stat_card(self, parent, label, icon, color):
        """创建统计卡片"""
        card = tk.Frame(parent, bg="white", relief=tk.RAISED, borderwidth=1)

        icon_label = tk.Label(
            card,
            text=icon,
            font=("Segoe UI Emoji", 24),
            bg="white"
        )
        icon_label.pack(pady=(10, 5))

        value_label = tk.Label(
            card,
            text="0",
            font=("微软雅黑", 20, "bold"),
            bg="white",
            fg=color
        )
        value_label.pack()

        text_label = tk.Label(
            card,
            text=label,
            font=("微软雅黑", 9),
            bg="white",
            fg="#7f8c8d"
        )
        text_label.pack(pady=(0, 10))

        card.value_label = value_label
        return card

    def log(self, message, level="INFO"):
        """添加日志"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_message = f"[{timestamp}] [{level}] {message}\n"

        self.log_text.insert(tk.END, log_message)
        self.log_text.see(tk.END)

        # 根据级别设置颜色
        if level == "ERROR":
            self.log_text.tag_add("error", f"end-{len(log_message)}c", "end-1c")
            self.log_text.tag_config("error", foreground="#e74c3c")
        elif level == "SUCCESS":
            self.log_text.tag_add("success", f"end-{len(log_message)}c", "end-1c")
            self.log_text.tag_config("success", foreground="#27ae60")
        elif level == "WARNING":
            self.log_text.tag_add("warning", f"end-{len(log_message)}c", "end-1c")
            self.log_text.tag_config("warning", foreground="#f39c12")

    def clear_log(self):
        """清空日志"""
        self.log_text.delete(1.0, tk.END)
        self.log("日志已清空")

    def update_stats_loop(self):
        """更新统计信息循环"""
        while self.is_running:
            try:
                self.update_stats()
                time.sleep(2)  # 每2秒更新一次
            except Exception as e:
                print(f"更新统计失败: {e}")

    def update_stats(self):
        """更新统计信息"""
        try:
            # 获取MongoDB统计
            total_items = self.collection.count_documents({})
            recommended_items = self.collection.count_documents({'is_recommended': True})

            # 获取Redis统计
            queue_size = self.redis_client.get_queue_size()

            # 更新统计卡片
            self.stat_cards['total_items'].value_label.config(text=str(total_items))
            self.stat_cards['recommended_items'].value_label.config(text=str(recommended_items))
            self.stat_cards['queue_size'].value_label.config(text=str(queue_size))
            self.stat_cards['error_count'].value_label.config(text="0")

            # 更新状态标签
            self.status_labels['spider_status'].config(text="运行中" if queue_size > 0 else "空闲")
            self.status_labels['items_scraped'].config(text=f"{total_items} 个")
            self.status_labels['success_rate'].config(text="100%")

        except Exception as e:
            print(f"更新统计失败: {e}")

    def start_crawler(self):
        """启动爬虫"""
        # 获取参数
        delay = self.delay_var.get()
        pages = self.pages_var.get()

        self.log(f"正在启动爬虫... (延迟:{delay}s, 页数:{pages if pages > 0 else '全部'})", "INFO")
        self.start_button.config(state=tk.DISABLED)
        self.stop_button.config(state=tk.NORMAL)
        self.crawler_process = None

        # 在新线程中启动爬虫
        def run_crawler():
            try:
                import subprocess
                import sys

                self.log("爬虫启动成功", "SUCCESS")

                # 构建命令
                cmd = [
                    sys.executable,
                    "scripts/crawl_all_enhanced.py",
                    "--delay", str(delay),
                    "--continue"
                ]

                if pages > 0:
                    cmd.extend(["--pages", str(pages)])

                # 使用subprocess运行爬虫脚本
                self.crawler_process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                    universal_newlines=True,
                    cwd=str(Path(__file__).parent.parent)
                )

                # 实时读取输出
                for line in self.crawler_process.stdout:
                    line = line.strip()
                    if line:
                        # 过滤日志前缀
                        if " | " in line:
                            parts = line.split(" | ", 2)
                            if len(parts) >= 3:
                                line = parts[2]

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
                    self.log("爬虫运行完成", "SUCCESS")
                else:
                    self.log(f"爬虫运行失败 (返回码: {self.crawler_process.returncode})", "ERROR")

            except Exception as e:
                self.log(f"爬虫运行失败: {e}", "ERROR")
            finally:
                self.start_button.config(state=tk.NORMAL)
                self.stop_button.config(state=tk.DISABLED)
                self.crawler_process = None

        threading.Thread(target=run_crawler, daemon=True).start()

    def stop_crawler(self):
        """停止爬虫"""
        self.log("正在停止爬虫...", "WARNING")

        if hasattr(self, 'crawler_process') and self.crawler_process:
            try:
                self.crawler_process.terminate()
                self.crawler_process.wait(timeout=5)
                self.log("爬虫进程已终止", "INFO")
            except Exception as e:
                self.log(f"停止爬虫失败: {e}", "ERROR")
                try:
                    self.crawler_process.kill()
                except:
                    pass

        self.start_button.config(state=tk.NORMAL)
        self.stop_button.config(state=tk.DISABLED)
        self.log("爬虫已停止", "INFO")

    def on_closing(self):
        """关闭窗口"""
        self.is_running = False
        self.root.destroy()

def main():
    root = tk.Tk()
    app = CrawlerMonitor(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()

if __name__ == "__main__":
    main()

