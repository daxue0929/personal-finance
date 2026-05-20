import time
import threading
from datetime import datetime
from typing import Callable, Optional

from ..utils.logger import logger


class FundTaskScheduler:
    def __init__(self, interval_hours: int = 1):
        self.interval_seconds = interval_hours * 3600
        self.running = False
        self.thread: Optional[threading.Thread] = None
        self.task_func: Optional[Callable] = None

    def set_task(self, task_func: Callable):
        self.task_func = task_func

    def start(self):
        if self.running:
            logger.warning("调度器已在运行中")
            return

        if not self.task_func:
            logger.error("未设置任务函数，请先调用 set_task()")
            return

        self.running = True
        self.thread = threading.Thread(target=self._run_loop, daemon=True)
        self.thread.start()
        logger.info(f"任务调度器已启动，间隔 {self.interval_seconds / 3600} 小时执行一次")

    def stop(self):
        if not self.running:
            logger.warning("调度器未在运行")
            return

        self.running = False
        if self.thread:
            self.thread.join(timeout=5)
        logger.info("任务调度器已停止")

    def _run_loop(self):
        while self.running:
            try:
                self._execute_task()
            except Exception as e:
                logger.error(f"任务执行异常: {e}")

            for _ in range(int(self.interval_seconds)):
                if not self.running:
                    break
                time.sleep(1)

    def _execute_task(self):
        start_time = datetime.now()
        logger.info(f"[{start_time}] 开始执行定时任务...")

        try:
            if self.task_func:
                self.task_func()
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            logger.info(f"任务执行完成，耗时 {duration:.2f} 秒")
        except Exception as e:
            logger.error(f"任务执行失败: {e}")

    def run_now(self):
        if not self.task_func:
            logger.error("未设置任务函数")
            return

        logger.info("立即执行任务...")
        self._execute_task()


def create_scheduler(interval_hours: int = 1) -> FundTaskScheduler:
    return FundTaskScheduler(interval_hours=interval_hours)
