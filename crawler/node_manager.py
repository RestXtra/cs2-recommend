"""分布式爬虫节点管理器 - 动态调整爬虫节点数量应对负载"""
import subprocess
import sys
import time
import threading
import os
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass, field
from datetime import datetime
from loguru import logger

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from utils.redis_client import redis_client
from utils.config import config


@dataclass
class CrawlerNode:
    """爬虫节点信息"""
    node_id: str
    process: subprocess.Popen
    started_at: datetime
    pid: int = 0
    
    def is_alive(self) -> bool:
        return self.process.poll() is None


class NodeManager:
    """
    爬虫节点管理器 - 根据Redis队列负载动态调整节点数量
    
    工作原理：
    1. 监控Redis任务队列大小
    2. 队列任务多时自动启动更多爬虫进程
    3. 队列任务少时自动关闭多余进程
    4. 每个进程都是独立的Scrapy爬虫，从同一个Redis队列消费任务
    """
    
    def __init__(self):
        self.nodes: Dict[str, CrawlerNode] = {}
        self.min_nodes = config.get('distributed.auto_scaling.min_nodes', 1)
        self.max_nodes = config.get('distributed.auto_scaling.max_nodes', 5)
        self.scale_up_threshold = config.get('distributed.auto_scaling.scale_up_threshold', 1000)
        self.scale_down_threshold = config.get('distributed.auto_scaling.scale_down_threshold', 100)
        self.check_interval = 30  # 检查间隔（秒）
        
        self.is_running = False
        self.auto_scale_enabled = True
        self.monitor_thread: Optional[threading.Thread] = None
        
        # Redis队列键
        self.queue_key = config.get('redis.queue_key', 'csgo:start_urls')
        
        logger.info(f"节点管理器初始化: 最小节点={self.min_nodes}, 最大节点={self.max_nodes}")
    
    def start(self, initial_nodes: int = None):
        """启动节点管理器"""
        if self.is_running:
            logger.warning("节点管理器已在运行")
            return
        
        self.is_running = True
        initial = initial_nodes or self.min_nodes
        
        logger.info(f"🚀 节点管理器启动，初始节点数: {initial}")
        
        # 启动初始节点
        for i in range(initial):
            self.add_node()
        
        # 启动自动扩缩容监控
        if self.auto_scale_enabled:
            self.monitor_thread = threading.Thread(target=self._auto_scale_loop, daemon=True)
            self.monitor_thread.start()
            logger.info("✓ 自动扩缩容已启用")
    
    def stop(self):
        """停止所有节点"""
        self.is_running = False
        logger.info("正在停止所有爬虫节点...")
        
        for node_id in list(self.nodes.keys()):
            self._kill_node(node_id)
        
        self.nodes.clear()
        logger.info("✓ 所有节点已停止")
    
    def add_node(self) -> Optional[str]:
        """添加一个爬虫节点（启动新的Scrapy进程）"""
        if len(self.nodes) >= self.max_nodes:
            logger.warning(f"已达最大节点数 {self.max_nodes}，无法添加")
            return None
        
        node_id = f"node_{int(time.time() * 1000)}_{len(self.nodes)}"
        
        try:
            # 构建Scrapy命令
            cmd = [
                sys.executable, '-m', 'scrapy', 'crawl', 'csgo_market',
                '-s', 'LOG_LEVEL=INFO',
                '-s', f'JOBDIR=crawls/{node_id}'  # 每个节点独立的任务目录
            ]
            
            # 启动进程
            process = subprocess.Popen(
                cmd,
                cwd=str(project_root),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == 'nt' else 0
            )
            
            node = CrawlerNode(
                node_id=node_id,
                process=process,
                started_at=datetime.now(),
                pid=process.pid
            )
            self.nodes[node_id] = node
            
            logger.info(f"✓ 节点启动: {node_id} (PID: {process.pid}, 当前节点数: {len(self.nodes)})")
            return node_id
            
        except Exception as e:
            logger.error(f"启动节点失败: {e}")
            return None
    
    def remove_node(self) -> bool:
        """移除一个爬虫节点（关闭最后启动的进程）"""
        if len(self.nodes) <= self.min_nodes:
            logger.warning(f"已达最小节点数 {self.min_nodes}，无法移除")
            return False
        
        # 移除最后一个节点
        if self.nodes:
            node_id = list(self.nodes.keys())[-1]
            return self._kill_node(node_id)
        return False
    
    def _kill_node(self, node_id: str) -> bool:
        """终止指定节点"""
        if node_id not in self.nodes:
            return False
        
        node = self.nodes[node_id]
        try:
            node.process.terminate()
            node.process.wait(timeout=5)
        except:
            try:
                node.process.kill()
            except:
                pass
        
        del self.nodes[node_id]
        logger.info(f"✓ 节点已停止: {node_id} (当前节点数: {len(self.nodes)})")
        return True
    
    def _auto_scale_loop(self):
        """自动扩缩容循环"""
        logger.info("自动扩缩容监控线程启动")

        while self.is_running and self.auto_scale_enabled:
            try:
                self._check_and_scale()
                self._check_health()
            except Exception as e:
                logger.error(f"自动扩缩容异常: {e}")

            time.sleep(self.check_interval)

    def _check_and_scale(self):
        """检查负载并自动扩缩容"""
        queue_size = self.get_queue_size()
        current_nodes = len(self.nodes)

        # 扩容条件：队列任务多且未达上限
        if queue_size > self.scale_up_threshold and current_nodes < self.max_nodes:
            nodes_to_add = min(2, self.max_nodes - current_nodes)
            logger.info(f"📈 负载高 (队列: {queue_size})，扩容 {nodes_to_add} 个节点")
            for _ in range(nodes_to_add):
                self.add_node()

        # 缩容条件：队列任务少且超过最小节点数
        elif queue_size < self.scale_down_threshold and current_nodes > self.min_nodes:
            logger.info(f"📉 负载低 (队列: {queue_size})，缩容 1 个节点")
            self.remove_node()

    def _check_health(self):
        """检查节点健康状态，重启崩溃的节点"""
        for node_id, node in list(self.nodes.items()):
            if not node.is_alive():
                logger.warning(f"节点 {node_id} (PID: {node.pid}) 已退出，正在重启...")
                del self.nodes[node_id]
                self.add_node()

    def get_queue_size(self) -> int:
        """获取Redis任务队列大小"""
        try:
            return redis_client.client.llen(self.queue_key)
        except:
            return 0

    def get_status(self) -> Dict:
        """获取节点管理器状态"""
        return {
            'is_running': self.is_running,
            'auto_scale_enabled': self.auto_scale_enabled,
            'current_nodes': len(self.nodes),
            'min_nodes': self.min_nodes,
            'max_nodes': self.max_nodes,
            'queue_size': self.get_queue_size(),
            'scale_up_threshold': self.scale_up_threshold,
            'scale_down_threshold': self.scale_down_threshold,
            'nodes': [
                {
                    'node_id': n.node_id,
                    'pid': n.pid,
                    'started_at': n.started_at.isoformat(),
                    'is_alive': n.is_alive()
                }
                for n in self.nodes.values()
            ]
        }

    def set_auto_scale(self, enabled: bool):
        """启用/禁用自动扩缩容"""
        self.auto_scale_enabled = enabled
        logger.info(f"自动扩缩容: {'启用' if enabled else '禁用'}")


# 全局单例
node_manager = NodeManager()

