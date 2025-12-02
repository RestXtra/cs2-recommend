"""启动所有服务的脚本"""
import sys
import subprocess
import time
from pathlib import Path
import webbrowser

sys.path.insert(0, str(Path(__file__).parent.parent))

from monitor.logger import logger
from utils.config import config


def check_services():
    """检查必要服务是否运行"""
    logger.info("检查服务状态...")
    
    # 检查Redis
    try:
        from utils.redis_client import redis_client
        redis_client.client.ping()
        logger.info("✓ Redis服务正常")
    except Exception as e:
        logger.error(f"✗ Redis服务未启动: {e}")
        logger.info("请先启动Redis: D:\\path\\redis\\redis-server.exe")
        return False
    
    # 检查MongoDB
    try:
        from utils.mongo_client import mongo_client
        mongo_client.db.command('ping')
        logger.info("✓ MongoDB服务正常")
    except Exception as e:
        logger.error(f"✗ MongoDB服务未启动: {e}")
        logger.info("请先启动MongoDB: D:\\path\\mongodb\\bin\\mongod.exe --dbpath D:\\path\\mongodb\\data")
        return False
    
    return True


def start_api_server():
    """启动API服务器"""
    logger.info("启动API服务器...")
    
    api_dir = Path(__file__).parent.parent / 'api'
    api_script = api_dir / 'main.py'
    
    process = subprocess.Popen(
        [sys.executable, str(api_script)],
        cwd=str(api_dir)
    )
    
    logger.info(f"API服务器已启动 (PID: {process.pid})")
    return process


def start_web_server():
    """启动Web服务器"""
    logger.info("启动Web服务器...")

    web_dir = Path(__file__).parent.parent / 'web'

    # 使用Python内置的HTTP服务器
    process = subprocess.Popen(
        [sys.executable, '-m', 'http.server', '3000'],
        cwd=str(web_dir)
    )

    logger.info(f"Web服务器已启动 (PID: {process.pid})")
    logger.info("访问地址: http://localhost:3000")

    return process


def start_monitor():
    """启动监控窗口"""
    logger.info("启动监控窗口...")

    project_root = Path(__file__).parent.parent
    monitor_script = project_root / 'monitor' / 'monitor.py'

    process = subprocess.Popen(
        [sys.executable, str(monitor_script)],
        cwd=str(project_root)
    )

    logger.info(f"监控窗口已启动 (PID: {process.pid})")
    return process


def start_crawler():
    """启动爬虫"""
    logger.info("启动爬虫...")

    project_root = Path(__file__).parent.parent
    crawler_script = project_root / 'scripts' / 'crawl_all_enhanced.py'

    process = subprocess.Popen(
        [sys.executable, str(crawler_script), '--delay', '1.5', '--continue'],
        cwd=str(project_root)
    )

    logger.info(f"爬虫已启动 (PID: {process.pid})")
    return process


def open_browser():
    """打开浏览器"""
    time.sleep(3)  # 等待服务启动
    logger.info("打开浏览器...")
    webbrowser.open('http://localhost:3000/index.html')


def update_homepage_data():
    """增量更新首页大盘数据（只抓取最新数据）"""
    logger.info("更新首页大盘数据...")

    project_root = Path(__file__).parent.parent
    update_script = project_root / 'scripts' / 'update_homepage_incremental.py'

    try:
        result = subprocess.run(
            [sys.executable, str(update_script)],
            cwd=str(project_root),
            capture_output=True,
            text=True,
            timeout=30  # 增加超时时间到30秒
        )
        if result.returncode == 0:
            logger.info("✓ 首页数据更新成功")
        else:
            logger.warning(f"⚠ 首页数据更新失败（不影响使用）")
    except subprocess.TimeoutExpired:
        logger.warning("⚠ 首页数据更新超时，跳过（不影响使用）")
    except Exception as e:
        logger.warning(f"⚠ 首页数据更新异常: {e}（不影响使用）")


def main():
    """主函数"""
    logger.info("=" * 60)
    logger.info("CS2市场爬虫系统 - 启动所有服务")
    logger.info("=" * 60)

    # 检查服务
    if not check_services():
        logger.error("服务检查失败，请先启动必要的服务")
        return

    # 增量更新首页数据
    update_homepage_data()

    processes = []

    try:
        # 启动API服务器
        api_process = start_api_server()
        processes.append(api_process)
        time.sleep(2)

        # 启动Web服务器
        web_process = start_web_server()
        processes.append(web_process)
        time.sleep(1)

        # 启动监控窗口
        monitor_process = start_monitor()
        processes.append(monitor_process)
        time.sleep(1)

        # 启动爬虫
        crawler_process = start_crawler()
        processes.append(crawler_process)

        # 打开浏览器
        open_browser()

        logger.info("=" * 60)
        logger.info("所有服务已启动！")
        logger.info("API服务: http://localhost:8008")
        logger.info("Web界面: http://localhost:3000")
        logger.info("  - 首页大盘: http://localhost:3000/homepage.html")
        logger.info("  - 饰品市场: http://localhost:3000/index.html")
        logger.info("监控窗口: 已打开（Kivy 界面）")
        logger.info("爬虫: 后台运行中")
        logger.info("按 Ctrl+C 停止所有服务")
        logger.info("=" * 60)
        
        # 等待用户中断
        while True:
            time.sleep(1)
    
    except KeyboardInterrupt:
        logger.info("\n正在停止所有服务...")
        
        for process in processes:
            try:
                process.terminate()
                process.wait(timeout=5)
            except:
                process.kill()
        
        logger.info("所有服务已停止")


if __name__ == '__main__':
    main()

