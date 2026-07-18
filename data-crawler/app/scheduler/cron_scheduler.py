from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
import threading
import time
import hashlib
import uuid
from datetime import datetime

from ..storage import TaskScheduleStorage, TaskRunRecordStorage
from ..utils.logger import logger
from ..utils.logger import trace_id_var, request_method_var, request_path_var, category_var, task_name_var


def run_with_trace_context(task_func, task_name, *args, trace_id=None, **kwargs):
    """
    使用trace上下文执行任务的包装函数
    为定时任务生成唯一的trace_id并设置到ContextVar中。
    支持传入外部 trace_id（执行记录复用，保证日志串联）。
    """
    trace_id = trace_id or str(uuid.uuid4())
    task_path = f'/scheduler/task/{task_name}'

    # 设置ContextVar上下文
    tokens = []
    try:
        tokens.append(trace_id_var.set(trace_id))
        tokens.append(request_method_var.set('SCHEDULER'))
        tokens.append(request_path_var.set(task_path))
        tokens.append(category_var.set('task'))
        tokens.append(task_name_var.set(task_name))

        logger.info(f"【定时任务开始】[TraceID:{trace_id}] 任务: {task_name}")

        # 执行任务
        result = task_func(*args, **kwargs)

        logger.info(f"【定时任务完成】[TraceID:{trace_id}] 任务: {task_name}")

        return result
    except Exception as e:
        logger.error(f"【定时任务异常】[TraceID:{trace_id}] 任务: {task_name}, 错误: {str(e)}")
        raise
    finally:
        # 清理ContextVar上下文
        for token in reversed(tokens):
            try:
                token.var.reset(token)
            except Exception:
                pass


class CronTaskScheduler:
    def __init__(self):
        self.scheduler = BackgroundScheduler(timezone='Asia/Shanghai')
        self.task_registry = {}
        self.last_check_time = 0
        self.check_interval = 60
        self._running = False
        self._check_thread = None
        self._task_storage = TaskScheduleStorage()
        self._run_record_storage = TaskRunRecordStorage()
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
            task_func_name = task.task_func
            task_name = task.task_name
            # cron 路径：经 execute_task_with_record 包装（防重叠 + 执行记录），同步在 APScheduler 线程池跑
            wrapped_func = lambda *args, **kwargs: self.execute_task_with_record(
                task_func_name, task_name, trigger_type='cron', triggered_by='scheduler'
            )
            self.scheduler.add_job(
                wrapped_func,
                CronTrigger.from_crontab(task.cron_expression),
                id=task.task_func,
                name=task.task_name
            )

    def execute_task_with_record(self, task_func_name, task_name, trigger_type='cron', triggered_by='scheduler'):
        """执行任务并记录状态（cron 路径同步）。

        防重叠：已有 RUNNING 则记 SKIPPED 并 return，不执行。
        否则 INSERT RUNNING -> 跑任务 -> UPDATE SUCCESS/FAILED（记录耗时/错误）。
        trace_id 复用：记录的 trace_id 与任务日志的 trace_id 一致，可串联 system_log。
        异常被捕获记 FAILED，不向上抛（避免 APScheduler 因异常告警；失败信息已入记录表）。
        """
        if task_func_name not in self.task_registry:
            logger.warning(f"任务 {task_func_name} 未注册")
            return

        # 防重叠：已有 RUNNING -> 记 SKIPPED（复用 RUNNING 的 trace_id 便于追溯"因谁而跳过"），不执行
        running = self._run_record_storage.get_running_record_by_func(task_func_name)
        if running:
            self._run_record_storage.create_skipped_record(
                task_func_name, task_name, trigger_type,
                trace_id=running.trace_id or '', triggered_by=triggered_by)
            logger.info(f"任务 {task_name}({task_func_name}) 已在运行，跳过本次 {trigger_type} 触发")
            return

        trace_id = str(uuid.uuid4())
        record = self._run_record_storage.create_running_record(
            task_func_name, task_name, trigger_type, trace_id, triggered_by)
        record_id = record.id if record else None
        if not record:
            # 记录失败仍执行任务（不因记录表故障阻断业务），但无状态追踪
            logger.warning(f"任务 {task_name} 执行记录创建失败，仍执行任务")

        start = time.time()
        try:
            run_with_trace_context(
                self.task_registry[task_func_name], task_name,
                trace_id=trace_id)
            status, error_message = 'SUCCESS', None
        except Exception as e:
            status, error_message = 'FAILED', str(e)
            logger.error(f"任务 {task_name} 执行失败: {e}")
        finally:
            duration_ms = int((time.time() - start) * 1000)
            if record_id is not None:
                self._run_record_storage.update_record_status(
                    record_id, status, duration_ms=duration_ms, error_message=error_message)

    def start(self):
        self._running = True
        # 启动时重置上次进程残留的僵尸 RUNNING 记录（崩溃/重启未完成的任务）
        try:
            self._run_record_storage.reset_stale_running(threshold_minutes=60)
        except Exception as e:
            logger.error(f"启动时重置僵尸 RUNNING 记录异常: {e}")
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

    def run_job_now(self, task_func_name: str, force_run: bool = False, triggered_by: str = 'manual'):
        """手动触发任务（异步）：立即返回 record_id+trace_id，后台线程跑任务。

        - 遇 RUNNING：不触发、不记表，返回 {rejected:True, message:...} 让前端弹框提示。
        - 否则：INSERT RUNNING + 起后台线程跑任务 -> 立即返回 {record_id, trace_id}。
        - 后台线程跑完 UPDATE SUCCESS/FAILED（_run_task_in_thread）。
        - force_run 参数保留兼容（本期不跳过防重叠；后续可扩展）。
        """
        if task_func_name not in self.task_registry:
            logger.warning(f"任务 {task_func_name} 未注册，无法手动触发")
            return False

        job = self.scheduler.get_job(task_func_name)
        task_name = job.name if job else task_func_name

        # 防重叠：手动触发遇 RUNNING -> 不记表、不起线程、返回 rejected
        if self._run_record_storage.get_running_record_by_func(task_func_name):
            logger.info(f"任务 {task_name}({task_func_name}) 正在运行，手动触发被拒绝")
            return {'rejected': True, 'message': '任务正在运行，请等待完成'}

        trace_id = str(uuid.uuid4())
        record = self._run_record_storage.create_running_record(
            task_func_name, task_name, 'manual', trace_id, triggered_by)
        record_id = record.id if record else None

        # 起后台线程跑任务，立即返回
        thread = threading.Thread(
            target=self._run_task_in_thread,
            args=(task_func_name, task_name, record_id, trace_id, force_run),
            daemon=True
        )
        thread.start()

        return {'record_id': record_id, 'trace_id': trace_id}

    def _run_task_in_thread(self, task_func_name, task_name, record_id, trace_id, force_run=False):
        """后台线程执行任务（手动触发用）：复用 trace_id，finally UPDATE 状态。"""
        start = time.time()
        try:
            run_with_trace_context(
                self.task_registry[task_func_name], task_name,
                force_run=force_run, trace_id=trace_id)
            status, error_message = 'SUCCESS', None
        except Exception as e:
            status, error_message = 'FAILED', str(e)
            logger.error(f"任务 {task_name} 手动执行失败: {e}")
        finally:
            duration_ms = int((time.time() - start) * 1000)
            if record_id is not None:
                self._run_record_storage.update_record_status(
                    record_id, status, duration_ms=duration_ms, error_message=error_message)

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
