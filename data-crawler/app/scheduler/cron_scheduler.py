from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
import threading
import time
import hashlib
from datetime import datetime

from ..storage import TaskScheduleStorage
from ..utils.logger import logger


class CronTaskScheduler:
    def __init__(self):
        self.scheduler = BackgroundScheduler(timezone='Asia/Shanghai')
        self.task_registry = {}
        self.last_check_time = 0
        self.check_interval = 60
        self._running = False
        self._check_thread = None
        self._task_storage = TaskScheduleStorage()
        self._config_hash = ""

    def _calculate_config_hash(self, tasks):
        config_str = "\n".join(
            f"{t.task_func}|{t.cron_expression}|{t.enabled}"
            for t in sorted(tasks, key=lambda x: x.task_func)
        )
        return hashlib.md5(config_str.encode()).hexdigest()

    def register_task(self, task_func_name, task_func):
        self.task_registry[task_func_name] = task_func

    def load_tasks_from_db(self):
        try:
            tasks = self._task_storage.get_all_enabled_tasks()

            current_hash = self._calculate_config_hash(tasks)
            if current_hash != self._config_hash:
                self._config_hash = current_hash
                for task in tasks:
                    self._update_task(task)

            return len(tasks)
        except Exception as e:
            logger.error(f"从数据库加载任务失败: {e}")
            return 0

    def _update_task(self, task):
        existing_job = self.scheduler.get_job(task.task_func)

        if existing_job:
            if existing_job.trigger != CronTrigger.from_crontab(task.cron_expression):
                self.scheduler.remove_job(task.task_func)
                self._add_job(task)
                logger.info(f"任务 [{task.task_name}] 按最新的 cron 表达式 [{task.cron_expression}] 已重新设置")
        else:
            self._add_job(task)
            logger.info(f"任务 [{task.task_name}] 按 cron 表达式 [{task.cron_expression}] 已设置")

    def _add_job(self, task):
        if task.task_func in self.task_registry:
            self.scheduler.add_job(
                self.task_registry[task.task_func],
                CronTrigger.from_crontab(task.cron_expression),
                id=task.task_func,
                name=task.task_name
            )

    def start(self):
        self._running = True
        self.load_tasks_from_db()
        self.scheduler.start()
        self._start_check_thread()
        logger.info("Cron 任务调度器已启动")

    def stop(self):
        self._running = False
        if self._check_thread:
            self._check_thread.join(timeout=5)
        self.scheduler.shutdown()
        self._task_storage.close()
        logger.info("Cron 任务调度器已停止")

    def _start_check_thread(self):
        def check_loop():
            while self._running:
                try:
                    tasks = self._task_storage.get_all_enabled_tasks()

                    current_hash = self._calculate_config_hash(tasks)
                    if current_hash != self._config_hash:
                        logger.info("检测到任务配置更新（数据库内容已变化），重新加载...")
                        self.load_tasks_from_db()

                except Exception as e:
                    logger.error(f"检查任务配置更新失败: {e}")

                time.sleep(self.check_interval)

        self._check_thread = threading.Thread(target=check_loop, daemon=True)
        self._check_thread.start()

    def run_job_now(self, task_func_name, force_run: bool = False):
        if task_func_name in self.task_registry:
            logger.info(f"立即执行任务: {task_func_name}, force_run={force_run}")
            self.task_registry[task_func_name](force_run=force_run)
            return True
        return False

    def format_next_run_time(self, next_run_time):
        """格式化下次执行时间"""
        if not next_run_time:
            return None
        if isinstance(next_run_time, datetime):
            return next_run_time.strftime('%Y-%m-%d %H:%M:%S')
        return str(next_run_time)

    def get_job_status(self, task_func_name):
        """获取任务状态"""
        job = self.scheduler.get_job(task_func_name)
        if job:
            return {
                'id': job.id,
                'name': job.name,
                'next_run_time': self.format_next_run_time(job.next_run_time),
                'trigger': str(job.trigger)
            }
        return None

    def get_all_jobs(self):
        jobs = []
        for job in self.scheduler.get_jobs():
            jobs.append({
                'id': job.id,
                'name': job.name,
                'next_run_time': self.format_next_run_time(job.next_run_time),
                'trigger': str(job.trigger)
            })
        return jobs


def create_cron_scheduler() -> CronTaskScheduler:
    return CronTaskScheduler()
