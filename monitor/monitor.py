"""爬虫监控窗口 - 使用Kivy实现（任务管理 + 节点管理）"""
import os
import sys
import json
import logging
import subprocess
import threading
from pathlib import Path
from datetime import datetime

# 禁用 pymongo/mongodb DEBUG 日志
logging.getLogger('pymongo').setLevel(logging.WARNING)
logging.getLogger('mongodb').setLevel(logging.WARNING)

# Kivy 必须在导入前设置图形后端
os.environ['KIVY_GL_BACKEND'] = 'angle_sdl2'

from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.spinner import Spinner, SpinnerOption
from kivy.uix.checkbox import CheckBox
from kivy.uix.scrollview import ScrollView
from kivy.core.window import Window
from kivy.core.text import LabelBase
from kivy.metrics import dp
from kivy.lang import Builder
from kivy.clock import Clock

# 项目根路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from utils.mongo_client import MongoDBClient
from utils.redis_client import RedisClient

# 注册中文字体
try:
    LabelBase.register('ChineseFont', fn_regular='C:/Windows/Fonts/msyh.ttc')
    CHINESE_FONT = 'ChineseFont'
except Exception:
    try:
        LabelBase.register('ChineseFont', fn_regular='C:/Windows/Fonts/simhei.ttf')
        CHINESE_FONT = 'ChineseFont'
    except Exception:
        CHINESE_FONT = 'Roboto'

# 商品类别映射（用于任务创建）- 对应 crawl_category.py 中的 CATEGORY_CONFIG
ITEM_CATEGORIES = {
    '全部': '所有商品',
    '匕首': '所有匕首和手套（带★）',
    '手套': '所有手套',
    '步枪': '所有步枪',
    '手枪': '所有手枪',
    '冲锋枪': '所有冲锋枪',
    '霰弹枪': '所有霰弹枪',
    '机枪': '所有机枪',
    '印花': '印花',
    '武器箱': '武器箱',
    '探员': '探员'
}

KV = f'''
#:import dp kivy.metrics.dp

<StatsCard@BoxLayout>:
    orientation: 'vertical'
    padding: dp(8)
    canvas.before:
        Color:
            rgba: 0.18, 0.2, 0.25, 1
        RoundedRectangle:
            pos: self.pos
            size: self.size
            radius: [dp(8)]

<ChineseSpinnerOption@SpinnerOption>:
    font_name: '{CHINESE_FONT}'
    font_size: dp(12)
    background_color: 0.2, 0.22, 0.26, 1
    color: 0.95, 0.96, 0.98, 1

<ChineseSpinner@Spinner>:
    font_name: '{CHINESE_FONT}'
    option_cls: 'ChineseSpinnerOption'
    background_normal: ''
    background_color: 0.2, 0.22, 0.26, 1
    color: 0.95, 0.96, 0.98, 1
    border: 0, 0, 0, 0

<MonitorLayout>:
    orientation: 'vertical'
    padding: dp(12)
    spacing: dp(12)
    canvas.before:
        Color:
            rgba: 0.12, 0.14, 0.18, 1
        Rectangle:
            pos: self.pos
            size: self.size

    BoxLayout:
        size_hint_y: None
        height: dp(55)
        padding: dp(15)
        canvas.before:
            Color:
                rgba: 0.2, 0.6, 0.86, 1
            RoundedRectangle:
                pos: self.pos
                size: self.size
                radius: [dp(10)]
        Label:
            text: 'CS2 市场爬虫监控系统'
            font_name: '{CHINESE_FONT}'
            bold: True
            font_size: dp(20)
            color: 1, 1, 1, 1

    # 统计卡片
    BoxLayout:
        size_hint_y: None
        height: dp(95)
        spacing: dp(10)

        StatsCard:
            Label:
                text: '[商品]'
                font_name: '{CHINESE_FONT}'
                color: 0.2, 0.6, 0.86, 1
                font_size: dp(12)
            Label:
                id: total_items
                text: '0'
                font_name: '{CHINESE_FONT}'
                font_size: dp(24)
                bold: True
                color: 0.2, 0.6, 0.86, 1
            Label:
                text: '总商品数'
                font_name: '{CHINESE_FONT}'
                font_size: dp(11)
                color: 0.65, 0.7, 0.75, 1
        StatsCard:
            Label:
                text: '[推荐]'
                font_name: '{CHINESE_FONT}'
                color: 0.95, 0.61, 0.07, 1
                font_size: dp(12)
            Label:
                id: recommended_items
                text: '0'
                font_name: '{CHINESE_FONT}'
                font_size: dp(24)
                bold: True
                color: 0.95, 0.61, 0.07, 1
            Label:
                text: '推荐商品'
                font_name: '{CHINESE_FONT}'
                font_size: dp(11)
                color: 0.65, 0.7, 0.75, 1
        StatsCard:
            Label:
                text: '[队列]'
                font_name: '{CHINESE_FONT}'
                color: 0.61, 0.35, 0.71, 1
                font_size: dp(12)
            Label:
                id: queue_size
                text: '0'
                font_name: '{CHINESE_FONT}'
                font_size: dp(24)
                bold: True
                color: 0.61, 0.35, 0.71, 1
            Label:
                text: '任务队列'
                font_name: '{CHINESE_FONT}'
                font_size: dp(11)
                color: 0.65, 0.7, 0.75, 1
        StatsCard:
            Label:
                text: '[节点]'
                font_name: '{CHINESE_FONT}'
                color: 0.15, 0.68, 0.38, 1
                font_size: dp(12)
            Label:
                id: node_count
                text: '0'
                font_name: '{CHINESE_FONT}'
                font_size: dp(24)
                bold: True
                color: 0.15, 0.68, 0.38, 1
            Label:
                text: '运行节点'
                font_name: '{CHINESE_FONT}'
                font_size: dp(11)
                color: 0.65, 0.7, 0.75, 1
        StatsCard:
            Label:
                text: '[状态]'
                font_name: '{CHINESE_FONT}'
                color: 0.91, 0.3, 0.24, 1
                font_size: dp(12)
            Label:
                id: spider_status
                text: '空闲'
                font_name: '{CHINESE_FONT}'
                font_size: dp(18)
                bold: True
                color: 0.7, 0.75, 0.8, 1
            Label:
                text: '爬虫状态'
                font_name: '{CHINESE_FONT}'
                font_size: dp(11)
                color: 0.65, 0.7, 0.75, 1

    # 主区域
    BoxLayout:
        spacing: dp(10)

        # 左侧：任务与节点
        BoxLayout:
            orientation: 'vertical'
            size_hint_x: 0.42
            spacing: dp(10)

            # 任务创建
            BoxLayout:
                orientation: 'vertical'
                padding: dp(10)
                spacing: dp(8)
                canvas.before:
                    Color:
                        rgba: 0.18, 0.2, 0.25, 1
                    RoundedRectangle:
                        pos: self.pos
                        size: self.size
                        radius: [dp(8)]

                Label:
                    text: '创建爬取任务'
                    font_name: '{CHINESE_FONT}'
                    bold: True
                    font_size: dp(14)
                    color: 1, 1, 1, 1
                    size_hint_y: None
                    height: dp(25)
                    halign: 'left'
                    text_size: self.size

                ScrollView:
                    size_hint_y: 0.58
                    do_scroll_x: False
                    bar_width: 0
                    GridLayout:
                        cols: 2
                        spacing: dp(6)
                        size_hint_y: None
                        height: self.minimum_height

                        BoxLayout:
                            spacing: dp(6)
                            size_hint_y: None
                            height: dp(26)
                            CheckBox:
                                id: chk_all
                                active: True
                                size_hint_x: None
                                width: dp(22)
                            Label:
                                text: '全部'
                                font_name: '{CHINESE_FONT}'
                                color: 0.95, 0.61, 0.07, 1
                                bold: True
                                halign: 'left'
                                valign: 'middle'
                                text_size: self.size

                        BoxLayout:
                            spacing: dp(6)
                            size_hint_y: None
                            height: dp(26)
                            CheckBox:
                                id: chk_knife
                                size_hint_x: None
                                width: dp(22)
                            Label:
                                text: '匕首'
                                font_name: '{CHINESE_FONT}'
                                color: 0.9, 0.9, 0.9, 1
                                halign: 'left'
                                valign: 'middle'
                                text_size: self.size

                        BoxLayout:
                            spacing: dp(6)
                            size_hint_y: None
                            height: dp(26)
                            CheckBox:
                                id: chk_gloves
                                size_hint_x: None
                                width: dp(22)
                            Label:
                                text: '手套'
                                font_name: '{CHINESE_FONT}'
                                color: 0.9, 0.9, 0.9, 1
                                halign: 'left'
                                valign: 'middle'
                                text_size: self.size

                        BoxLayout:
                            spacing: dp(6)
                            size_hint_y: None
                            height: dp(26)
                            CheckBox:
                                id: chk_rifle
                                size_hint_x: None
                                width: dp(22)
                            Label:
                                text: '步枪'
                                font_name: '{CHINESE_FONT}'
                                color: 0.9, 0.9, 0.9, 1
                                halign: 'left'
                                valign: 'middle'
                                text_size: self.size

                        BoxLayout:
                            spacing: dp(6)
                            size_hint_y: None
                            height: dp(26)
                            CheckBox:
                                id: chk_pistol
                                size_hint_x: None
                                width: dp(22)
                            Label:
                                text: '手枪'
                                font_name: '{CHINESE_FONT}'
                                color: 0.9, 0.9, 0.9, 1
                                halign: 'left'
                                valign: 'middle'
                                text_size: self.size

                        BoxLayout:
                            spacing: dp(6)
                            size_hint_y: None
                            height: dp(26)
                            CheckBox:
                                id: chk_smg
                                size_hint_x: None
                                width: dp(22)
                            Label:
                                text: '冲锋枪'
                                font_name: '{CHINESE_FONT}'
                                color: 0.9, 0.9, 0.9, 1
                                halign: 'left'
                                valign: 'middle'
                                text_size: self.size

                        BoxLayout:
                            spacing: dp(6)
                            size_hint_y: None
                            height: dp(26)
                            CheckBox:
                                id: chk_sticker
                                size_hint_x: None
                                width: dp(22)
                            Label:
                                text: '印花'
                                font_name: '{CHINESE_FONT}'
                                color: 0.9, 0.9, 0.9, 1
                                halign: 'left'
                                valign: 'middle'
                                text_size: self.size

                        BoxLayout:
                            spacing: dp(6)
                            size_hint_y: None
                            height: dp(26)
                            CheckBox:
                                id: chk_case
                                size_hint_x: None
                                width: dp(22)
                            Label:
                                text: '武器箱'
                                font_name: '{CHINESE_FONT}'
                                color: 0.9, 0.9, 0.9, 1
                                halign: 'left'
                                valign: 'middle'
                                text_size: self.size

                        BoxLayout:
                            spacing: dp(6)
                            size_hint_y: None
                            height: dp(26)
                            CheckBox:
                                id: chk_shotgun
                                size_hint_x: None
                                width: dp(22)
                            Label:
                                text: '霰弹枪'
                                font_name: '{CHINESE_FONT}'
                                color: 0.9, 0.9, 0.9, 1
                                halign: 'left'
                                valign: 'middle'
                                text_size: self.size

                        BoxLayout:
                            spacing: dp(6)
                            size_hint_y: None
                            height: dp(26)
                            CheckBox:
                                id: chk_machinegun
                                size_hint_x: None
                                width: dp(22)
                            Label:
                                text: '机枪'
                                font_name: '{CHINESE_FONT}'
                                color: 0.9, 0.9, 0.9, 1
                                halign: 'left'
                                valign: 'middle'
                                text_size: self.size

                        BoxLayout:
                            spacing: dp(6)
                            size_hint_y: None
                            height: dp(26)
                            CheckBox:
                                id: chk_agent
                                size_hint_x: None
                                width: dp(22)
                            Label:
                                text: '探员'
                                font_name: '{CHINESE_FONT}'
                                color: 0.9, 0.9, 0.9, 1
                                halign: 'left'
                                valign: 'middle'
                                text_size: self.size

                BoxLayout:
                    size_hint_y: None
                    height: dp(35)
                    spacing: dp(12)
                    Label:
                        text: '页数:'
                        font_name: '{CHINESE_FONT}'
                        color: 0.75, 0.78, 0.8, 1
                        size_hint_x: 0.3
                    ChineseSpinner:
                        id: task_pages_spinner
                        text: '10'
                        values: ['5', '10', '20', '50', '100', '全部']
                        size_hint_x: 0.7
                        height: dp(32)
                    Label:
                        text: '延迟:'
                        font_name: '{CHINESE_FONT}'
                        color: 0.75, 0.78, 0.8, 1
                        size_hint_x: 0.3
                    ChineseSpinner:
                        id: task_delay_spinner
                        text: '2.5'
                        values: ['1.5', '2.0', '2.5', '3.0', '4.0', '5.0']
                        size_hint_x: 0.7
                        height: dp(32)

                Button:
                    text: '创建任务'
                    font_name: '{CHINESE_FONT}'
                    bold: True
                    size_hint_y: None
                    height: dp(40)
                    background_normal: ''
                    background_color: 0.2, 0.6, 0.86, 1
                    on_press: root.create_task()

            # 节点管理
            BoxLayout:
                orientation: 'vertical'
                padding: dp(10)
                spacing: dp(8)
                canvas.before:
                    Color:
                        rgba: 0.18, 0.2, 0.25, 1
                    RoundedRectangle:
                        pos: self.pos
                        size: self.size
                        radius: [dp(8)]

                Label:
                    text: '节点管理'
                    font_name: '{CHINESE_FONT}'
                    bold: True
                    font_size: dp(14)
                    color: 1, 1, 1, 1
                    size_hint_y: None
                    height: dp(25)
                    halign: 'left'
                    text_size: self.size

                ScrollView:
                    size_hint_y: 1
                    BoxLayout:
                        id: node_list
                        orientation: 'vertical'
                        spacing: dp(5)
                        size_hint_y: None
                        height: self.minimum_height

                BoxLayout:
                    size_hint_y: None
                    height: dp(40)
                    spacing: dp(10)
                    Button:
                        text: '+ 添加节点'
                        font_name: '{CHINESE_FONT}'
                        bold: True
                        background_normal: ''
                        background_color: 0.15, 0.68, 0.38, 1
                        on_press: root.add_node()
                    Button:
                        text: '- 移除节点'
                        font_name: '{CHINESE_FONT}'
                        bold: True
                        background_normal: ''
                        background_color: 0.91, 0.3, 0.24, 1
                        on_press: root.remove_node()

        # 右侧：日志
        BoxLayout:
            orientation: 'vertical'
            padding: dp(10)
            canvas.before:
                Color:
                    rgba: 0.18, 0.2, 0.25, 1
                RoundedRectangle:
                    pos: self.pos
                    size: self.size
                    radius: [dp(8)]

            Label:
                text: '运行日志'
                font_name: '{CHINESE_FONT}'
                bold: True
                font_size: dp(14)
                color: 1, 1, 1, 1
                size_hint_y: None
                height: dp(25)
                halign: 'left'
                text_size: self.size

            ScrollView:
                TextInput:
                    id: log_text
                    readonly: True
                    font_name: '{CHINESE_FONT}'
                    font_size: dp(11)
                    background_color: 0.1, 0.12, 0.15, 1
                    foreground_color: 0.85, 0.88, 0.9, 1
                    cursor_color: 1, 1, 1, 1
                    size_hint_y: None
                    height: max(self.minimum_height, self.parent.height)

    # 底部控制
    BoxLayout:
        size_hint_y: None
        height: dp(45)
        spacing: dp(10)
        Button:
            id: start_btn
            text: '启动爬虫'
            font_name: '{CHINESE_FONT}'
            bold: True
            background_normal: ''
            background_color: 0.15, 0.68, 0.38, 1
            on_press: root.start_crawler()
        Button:
            id: stop_btn
            text: '停止爬虫'
            font_name: '{CHINESE_FONT}'
            bold: True
            background_normal: ''
            background_color: 0.91, 0.3, 0.24, 1
            disabled: True
            on_press: root.stop_crawler()
        Button:
            text: '清空队列'
            font_name: '{CHINESE_FONT}'
            bold: True
            background_normal: ''
            background_color: 0.95, 0.61, 0.07, 1
            on_press: root.clear_queue()
        Button:
            text: '清空日志'
            font_name: '{CHINESE_FONT}'
            bold: True
            background_normal: ''
            background_color: 0.58, 0.65, 0.65, 1
            on_press: root.clear_log()
        Button:
            text: '刷新数据'
            font_name: '{CHINESE_FONT}'
            bold: True
            background_normal: ''
            background_color: 0.2, 0.6, 0.86, 1
            on_press: root.refresh_stats()
'''


class CrawlerNode:
    """爬虫节点对象"""

    def __init__(self, node_id: str, process: subprocess.Popen):
        self.node_id = node_id
        self.process = process
        self.started_at = datetime.now()

    def is_alive(self) -> bool:
        return self.process and self.process.poll() is None


class MonitorLayout(BoxLayout):
    """Kivy 主布局"""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        # 数据源
        try:
            self.mongo_client = MongoDBClient()
            self.redis_client = RedisClient()
            self.collection = self.mongo_client.get_collection('items')
            self.db_connected = True
        except Exception as exc:
            self.db_connected = False
            print(f"数据库连接失败: {exc}")

        # 节点管理
        self.nodes = {}
        self.node_seq = 0
        self.max_nodes = 5

        # 单进程脚本兼容
        self.crawler_process = None

        Clock.schedule_once(self.init_ui, 0.1)
        Clock.schedule_interval(self.update_stats, 2)
        Clock.schedule_interval(self.check_nodes_health, 5)

    # ---------- UI & 日志 ----------
    def init_ui(self, _dt):
        self.log("系统启动成功", "SUCCESS")
        if self.db_connected:
            self.log("MongoDB连接成功")
            self.log("Redis连接成功")
        else:
            self.log("数据库连接失败，请检查配置", "ERROR")
        self.update_stats()
        self.update_node_list()

    def log(self, message: str, level: str = "INFO"):
        prefix = {
            "ERROR": "[错误]",
            "SUCCESS": "[成功]",
            "WARNING": "[警告]"
        }.get(level, "[信息]")
        timestamp = datetime.now().strftime("%H:%M:%S")
        entry = f"[{timestamp}] {prefix} {message}\n"
        log_widget = self.ids.log_text
        log_widget.text += entry
        log_widget.cursor = (0, len(log_widget.text))

    def clear_log(self):
        self.ids.log_text.text = ""
        self.log("日志已清空")

    # ---------- 数据统计 ----------
    def update_stats(self, _dt=None):
        if not self.db_connected:
            return
        try:
            total_items = self.collection.count_documents({})
            recommended_items = self.collection.count_documents({'is_recommended': True})
            # 获取分类任务队列大小
            category_queue_size = self.redis_client.client.llen('csgo:category_tasks')
            url_queue_size = self.redis_client.get_queue_size()
            queue_size = category_queue_size + url_queue_size
            active_nodes = sum(1 for node in self.nodes.values() if node.is_alive())

            self.ids.total_items.text = str(total_items)
            self.ids.recommended_items.text = str(recommended_items)
            self.ids.queue_size.text = str(queue_size)
            self.ids.node_count.text = str(active_nodes)

            if active_nodes > 0 or (self.crawler_process and self.crawler_process.poll() is None):
                self.ids.spider_status.text = '运行中'
                self.ids.spider_status.color = (0.15, 0.68, 0.38, 1)
            else:
                self.ids.spider_status.text = '空闲'
                self.ids.spider_status.color = (0.7, 0.75, 0.8, 1)
        except Exception as exc:
            print(f"统计更新失败: {exc}")

    def refresh_stats(self):
        self.update_stats()
        self.log("数据已刷新", "SUCCESS")

    # ---------- 任务创建 ----------
    def _selected_categories(self):
        if self.ids.chk_all.active:
            return ['全部']
        categories = []
        if self.ids.chk_knife.active:
            categories.append('匕首')
        if self.ids.chk_gloves.active:
            categories.append('手套')
        if self.ids.chk_rifle.active:
            categories.append('步枪')
        if self.ids.chk_pistol.active:
            categories.append('手枪')
        if self.ids.chk_smg.active:
            categories.append('冲锋枪')
        if self.ids.chk_shotgun.active:
            categories.append('霰弹枪')
        if self.ids.chk_machinegun.active:
            categories.append('机枪')
        if self.ids.chk_sticker.active:
            categories.append('印花')
        if self.ids.chk_case.active:
            categories.append('武器箱')
        if self.ids.chk_agent.active:
            categories.append('探员')
        return categories or ['全部']

    def create_task(self):
        """创建分类爬取任务 - 将任务加入队列"""
        categories = self._selected_categories()
        pages = self.ids.task_pages_spinner.text
        delay = self.ids.task_delay_spinner.text
        
        # 构建任务信息并存入Redis队列
        try:
            import json
            for category in categories:
                task_info = {
                    'category': category,
                    'pages': pages if pages != '全部' else None,
                    'delay': delay
                }
                # 使用 Redis 列表存储任务
                queue_key = 'csgo:category_tasks'
                self.redis_client.client.rpush(queue_key, json.dumps(task_info))
            
            task_count = len(categories)
            self.log(f"已创建 {task_count} 个任务: {', '.join(categories)}", "SUCCESS")
            self.log(f"配置: 每类最大 {pages} 页, 延迟 {delay}s")
            self.log("点击「启动爬虫」按钮开始抓取")
            self.update_stats()
            
        except Exception as exc:
            self.log(f"创建任务失败: {exc}", "ERROR")

    def clear_queue(self):
        """清空任务队列"""
        try:
            # 清空分类任务队列
            self.redis_client.client.delete('csgo:category_tasks')
            # 也清空原来的URL队列
            self.redis_client.clear_queue()
            self.log("任务队列已清空", "SUCCESS")
            self.update_stats()
        except Exception as exc:
            self.log(f"清空队列失败: {exc}", "ERROR")

    # ---------- 节点管理 ----------
    def add_node(self):
        if len(self.nodes) >= self.max_nodes:
            self.log(f"已达到最大节点数 {self.max_nodes}", "WARNING")
            return
        self.node_seq += 1
        node_id = f"node_{self.node_seq}"
        try:
            cmd = [
                sys.executable, '-m', 'scrapy', 'crawl', 'csgo_market',
                '-s', 'LOG_LEVEL=INFO',
                '-s', f'JOBDIR=crawls/{node_id}'
            ]
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                cwd=str(project_root),
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == 'nt' else 0
            )
            node = CrawlerNode(node_id, process)
            self.nodes[node_id] = node
            self.log(f"节点启动: {node_id} (PID: {process.pid})", "SUCCESS")
            self.update_node_list()
            threading.Thread(target=self._read_node_output, args=(node,), daemon=True).start()
        except Exception as exc:
            self.log(f"启动节点失败: {exc}", "ERROR")

    def remove_node(self):
        if not self.nodes:
            self.log("没有可移除的节点", "WARNING")
            return
        # 移除最新节点
        node_id = list(self.nodes.keys())[-1]
        node = self.nodes.pop(node_id)
        try:
            if node.process:
                node.process.terminate()
                try:
                    node.process.wait(timeout=3)
                except Exception:
                    node.process.kill()
            self.log(f"节点已停止: {node_id}", "SUCCESS")
        except Exception as exc:
            self.log(f"停止节点失败: {exc}", "ERROR")
        self.update_node_list()

    def _read_node_output(self, node: CrawlerNode):
        try:
            for line in node.process.stdout:
                line = line.strip()
                if not line:
                    continue
                message = f"[{node.node_id}] {line}"
                Clock.schedule_once(lambda _dt, msg=message: self.log(msg), 0)
        except Exception:
            pass

    def check_nodes_health(self, _dt=None):
        dead = [node_id for node_id, node in self.nodes.items() if not node.is_alive()]
        for node_id in dead:
            self.nodes.pop(node_id, None)
            self.log(f"节点退出: {node_id}", "WARNING")
        if dead:
            self.update_node_list()

    def update_node_list(self):
        container = self.ids.node_list
        container.clear_widgets()
        if not self.nodes:
            container.add_widget(Label(
                text='暂无运行节点',
                font_name=CHINESE_FONT,
                font_size=dp(12),
                color=(0.6, 0.65, 0.7, 1),
                size_hint_y=None,
                height=dp(30)
            ))
            return
        for node_id, node in self.nodes.items():
            status = '运行中' if node.is_alive() else '已停止'
            color = (0.15, 0.68, 0.38, 1) if node.is_alive() else (0.91, 0.3, 0.24, 1)
            runtime = (datetime.now() - node.started_at).seconds
            row = BoxLayout(size_hint_y=None, height=dp(26), spacing=dp(5))
            row.add_widget(Label(
                text=node_id,
                font_name=CHINESE_FONT,
                font_size=dp(11),
                color=(0.85, 0.88, 0.92, 1)
            ))
            row.add_widget(Label(
                text=status,
                font_name=CHINESE_FONT,
                font_size=dp(11),
                color=color,
                size_hint_x=0.3
            ))
            row.add_widget(Label(
                text=f"{runtime}s",
                font_name=CHINESE_FONT,
                font_size=dp(11),
                color=(0.65, 0.7, 0.75, 1),
                size_hint_x=0.3
            ))
            container.add_widget(row)

    # ---------- 脚本模式 ----------
    def start_crawler(self):
        """启动爬虫 - 从任务队列读取并执行"""
        import json
        
        queue_key = 'csgo:category_tasks'
        task_count = self.redis_client.client.llen(queue_key)
        
        if task_count == 0:
            self.log("任务队列为空，请先创建任务", "WARNING")
            return
        
        self.log(f"开始执行队列中的 {task_count} 个任务")
        self.ids.start_btn.disabled = True
        self.ids.stop_btn.disabled = False

        def run_tasks():
            try:
                while True:
                    # 从队列取出任务
                    task_json = self.redis_client.client.lpop(queue_key)
                    if not task_json:
                        break
                    
                    task = json.loads(task_json)
                    category = task.get('category', '全部')
                    pages = task.get('pages')
                    delay = task.get('delay', '2.5')
                    
                    Clock.schedule_once(lambda dt, c=category: self.log(f"开始抓取分类: {c}"), 0)
                    
                    # 构建命令
                    cmd = [
                        sys.executable,
                        'scripts/crawl_category.py',
                        '--category', category,
                        '--delay', delay
                    ]
                    if pages:
                        cmd.extend(['--pages', str(pages)])
                    
                    # 运行爬取
                    self.crawler_process = subprocess.Popen(
                        cmd,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                        text=True,
                        bufsize=1,
                        cwd=str(project_root)
                    )
                    
                    # 读取输出
                    for line in self.crawler_process.stdout:
                        line = line.strip()
                        if not line:
                            continue
                        # 解析日志格式
                        if ' | ' in line:
                            parts = line.split(' | ', 2)
                            if len(parts) >= 3:
                                line = parts[2]
                        Clock.schedule_once(lambda dt, msg=line: self.log(msg), 0)
                    
                    self.crawler_process.wait()
                    
                    if self.crawler_process.returncode != 0:
                        Clock.schedule_once(lambda dt, c=category: self.log(f'{c} 抓取失败', 'ERROR'), 0)
                    else:
                        Clock.schedule_once(lambda dt, c=category: self.log(f'{c} 抓取完成', 'SUCCESS'), 0)
                    
                    self.crawler_process = None
                
                Clock.schedule_once(lambda dt: self.log('所有任务执行完成!', 'SUCCESS'), 0)
                
            except Exception as exc:
                Clock.schedule_once(lambda dt, err=str(exc): self.log(f'爬取出错: {err}', 'ERROR'), 0)
            finally:
                Clock.schedule_once(lambda dt: self.reset_buttons(), 0)
                Clock.schedule_once(lambda dt: self.update_stats(), 0)
                self.crawler_process = None

        threading.Thread(target=run_tasks, daemon=True).start()

    def stop_crawler(self):
        self.log('正在停止爬虫...', 'WARNING')
        if self.crawler_process:
            try:
                self.crawler_process.terminate()
                self.crawler_process.wait(timeout=5)
            except Exception:
                try:
                    self.crawler_process.kill()
                except Exception:
                    pass
            self.crawler_process = None
        for node_id, node in list(self.nodes.items()):
            try:
                if node.process:
                    node.process.terminate()
            except Exception:
                pass
            self.nodes.pop(node_id, None)
        self.update_node_list()
        self.reset_buttons()
        self.log('爬虫已停止', 'SUCCESS')

    def reset_buttons(self):
        self.ids.start_btn.disabled = False
        self.ids.stop_btn.disabled = True


class CrawlerMonitorApp(App):
    def build(self):
        Window.size = (1020, 760)
        self.title = 'CS2 市场爬虫监控系统'
        Builder.load_string(KV)
        return MonitorLayout()

    def on_stop(self):
        root = self.root
        if isinstance(root, MonitorLayout):
            if root.crawler_process:
                try:
                    root.crawler_process.terminate()
                except Exception:
                    pass
            for node in root.nodes.values():
                try:
                    if node.process:
                        node.process.terminate()
                except Exception:
                    pass


def main():
    CrawlerMonitorApp().run()


if __name__ == '__main__':
    main()
