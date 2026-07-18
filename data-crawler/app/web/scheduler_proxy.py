"""
Web 进程对调度器进程的 HTTP 转发封装

web 进程不再持有 scheduler 实例，控制类接口通过本模块调用 scheduler 进程的 /internal/* 接口。
scheduler 不可达时抛 SchedulerUnavailable，由调用方返回 502。
"""
import os
import requests

from ..utils.logger import logger

SCHEDULER_URL = os.getenv('SCHEDULER_INTERNAL_URL', 'http://scheduler:5001')

# 任务执行可能耗时较长（爬虫），给 5 分钟
TASK_TIMEOUT = 300
# 状态/控制类操作应快速返回
CTRL_TIMEOUT = 30


class SchedulerUnavailable(Exception):
    """调度器进程不可达"""
    pass


def _request(method, path, json=None, timeout=CTRL_TIMEOUT):
    url = f"{SCHEDULER_URL}{path}"
    try:
        resp = requests.request(method, url, json=json, timeout=timeout)
        try:
            data = resp.json()
        except ValueError:
            data = {'message': resp.text}
        return data, resp.status_code
    except requests.exceptions.RequestException as e:
        logger.error(f"调度器不可达: {method} {url} - {e}")
        raise SchedulerUnavailable(str(e))


def get_status():
    """获取调度器状态。不可达时返回降级状态。"""
    try:
        data, _ = _request('GET', '/internal/status', timeout=CTRL_TIMEOUT)
        return data, 200
    except SchedulerUnavailable:
        return {
            'running': False,
            'message': '调度器不可达',
            'jobs': []
        }, 502


def start_scheduler():
    """启动调度器"""
    try:
        return _request('POST', '/internal/start', timeout=CTRL_TIMEOUT)
    except SchedulerUnavailable as e:
        return {'success': False, 'message': '调度器不可达'}, 502


def stop_scheduler():
    """停止调度器"""
    try:
        return _request('POST', '/internal/stop', timeout=CTRL_TIMEOUT)
    except SchedulerUnavailable as e:
        return {'success': False, 'message': '调度器不可达'}, 502


def run_task(task_func, force_run=False, triggered_by='manual'):
    """立即执行指定任务（异步：scheduler 立即返回 triggered，不再等任务跑完）"""
    try:
        return _request('POST', f'/internal/task/run/{task_func}',
                        json={'force_run': force_run, 'triggered_by': triggered_by},
                        timeout=CTRL_TIMEOUT)
    except SchedulerUnavailable:
        return {'success': False, 'message': '调度器不可达'}, 502


def get_all_jobs():
    """获取所有任务状态字典 {task_func: {id,name,next_run_time,trigger}}。

    不可达时返回 None，调用方需处理。
    """
    try:
        data, _ = _request('GET', '/internal/jobs', timeout=CTRL_TIMEOUT)
        return data
    except SchedulerUnavailable:
        return None


def get_job_status(task_func):
    """获取单个任务状态。不可达或任务不存在时返回 None。"""
    jobs = get_all_jobs()
    if jobs is None:
        return None
    return jobs.get(task_func)
