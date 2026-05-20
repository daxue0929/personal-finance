from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import create_engine, Column, BigInteger, String, Integer, DateTime, CHAR, Text
from sqlalchemy.orm import sessionmaker, declarative_base
from datetime import datetime
import threading
import time
import hashlib

from ..utils.config import get_db_url
from ..utils.logger import logger

Base = declarative_base()


class TaskSchedule(Base):
    __tablename__ = 'task_schedule'

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    task_name = Column(String(100), nullable=False)
    task_func = Column(String(200), nullable=False, unique=True)
    cron_expression = Column(String(100), nullable=False)
    enabled = Column(Integer, default=1)
    description = Column(Text)
    del_flag = Column(CHAR(1), default='1')
    create_by = Column(String(64))
    create_time = Column(DateTime)
    update_by = Column(String(64))
    update_time = Column(DateTime)


class CronTaskScheduler:
    def __init__(self):
        self.scheduler = BackgroundScheduler(timezone='Asia/Shanghai')
        self.task_registry = {}
        self.last_check_time = 0
        self.check_interval = 10
        self._running = False
        self._check_thread = None
        self.engine = create_engine(get_db_url(), pool_size=5, max_overflow=10)
        self.Session = sessionmaker(bind=self.engine)
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
        session = self.Session()
        try:
            tasks = session.query(TaskSchedule).filter(
                TaskSchedule.del_flag == '1',
                TaskSchedule.enabled == 1
            ).all()

            current_hash = self._calculate_config_hash(tasks)
            if current_hash != self._config_hash:
                self._config_hash = current_hash
                for task in tasks:
                    self._update_task(task)

            return len(tasks)
        except Exception as e:
            logger.error(f"从数据库加载任务失败: {e}")
            return 0
        finally:
            session.close()

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
        logger.info("Cron 任务调度器已停止")

    def _start_check_thread(self):
        def check_loop():
            while self._running:
                try:
                    session = self.Session()
                    tasks = session.query(TaskSchedule).filter(
                        TaskSchedule.del_flag == '1',
                        TaskSchedule.enabled == 1
                    ).all()

                    current_hash = self._calculate_config_hash(tasks)
                    if current_hash != self._config_hash:
                        logger.info("检测到任务配置更新（数据库内容已变化），重新加载...")
                        self.load_tasks_from_db()

                    session.close()
                except Exception as e:
                    logger.error(f"检查任务配置更新失败: {e}")

                time.sleep(self.check_interval)

        self._check_thread = threading.Thread(target=check_loop, daemon=True)
        self._check_thread.start()

    def run_job_now(self, task_func_name):
        if task_func_name in self.task_registry:
            logger.info(f"立即执行任务: {task_func_name}")
            self.task_registry[task_func_name]()
            return True
        return False

    def get_job_status(self, task_func_name):
        job = self.scheduler.get_job(task_func_name)
        if job:
            return {
                'id': job.id,
                'name': job.name,
                'next_run_time': str(job.next_run_time) if job.next_run_time else None,
                'trigger': str(job.trigger)
            }
        return None

    def get_all_jobs(self):
        jobs = []
        for job in self.scheduler.get_jobs():
            jobs.append({
                'id': job.id,
                'name': job.name,
                'next_run_time': str(job.next_run_time) if job.next_run_time else None,
                'trigger': str(job.trigger)
            })
        return jobs


def create_cron_scheduler() -> CronTaskScheduler:
    return CronTaskScheduler()
