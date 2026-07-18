#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
任务执行记录与状态追踪测试（TDD）

覆盖：
1. app/storage/task_run_record_storage.py - TaskRunRecordStorage CRUD（用 sqlite 内存库，不碰生产库）
2. app/scheduler/cron_scheduler.py - execute_task_with_record 状态机/防重叠、run_job_now 异步（mock Storage）

测试用 sqlite in-memory 建表测真实 ORM 行为；业务逻辑（状态机/防重叠/异步）mock Storage。
"""
import os
import time
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest


# ==================== sqlite 内存库 fixture ====================

@pytest.fixture
def sqlite_storage():
    """用 sqlite 内存库建 task_run_record 表，返回 TaskRunRecordStorage 实例（不碰生产 MySQL）"""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from app.storage.base import Base
    from app.storage import task_run_record_storage as mod
    from app.storage.task_run_record_storage import TaskRunRecord, TaskRunRecordStorage

    engine = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(engine, tables=[TaskRunRecord.__table__])
    Session = sessionmaker(bind=engine)

    # patch get_db_engine/get_db_session 返回 sqlite，避免 __init__ 连生产 MySQL
    with patch.object(mod, 'get_db_engine', return_value=engine), \
         patch.object(mod, 'get_db_session', return_value=Session):
        storage = TaskRunRecordStorage()
    storage.engine = engine
    storage.Session = Session
    return storage


# ==================== TaskRunRecordStorage CRUD ====================

def test_create_running_record(sqlite_storage):
    """create_running_record 插入 RUNNING 记录，返回带 id 的记录"""
    rec = sqlite_storage.create_running_record(
        task_func='fetch_fund_detail_task', task_name='基金详情网页抓取任务',
        trigger_type='manual', trace_id='trace-abc', triggered_by='admin')
    assert rec is not None
    assert rec.id is not None
    assert rec.status == 'RUNNING'
    assert rec.trace_id == 'trace-abc'
    assert rec.trigger_type == 'manual'
    assert rec.start_time is not None
    assert rec.end_time is None  # 未结束
    assert rec.duration_ms is None


def test_update_record_status_success(sqlite_storage):
    """update_record_status: RUNNING -> SUCCESS，写 end_time/duration_ms"""
    rec = sqlite_storage.create_running_record('f', 'n', 'cron', 't', 'scheduler')
    ok = sqlite_storage.update_record_status(rec.id, 'SUCCESS', duration_ms=12345)
    assert ok is True
    got = sqlite_storage.get_record_by_id(rec.id)
    assert got.status == 'SUCCESS'
    assert got.end_time is not None
    assert got.duration_ms == 12345
    assert got.error_message is None


def test_update_record_status_failed_with_error(sqlite_storage):
    """update_record_status: FAILED 时写 error_message"""
    rec = sqlite_storage.create_running_record('f', 'n', 'cron', 't', 'scheduler')
    sqlite_storage.update_record_status(rec.id, 'FAILED', duration_ms=100, error_message='boom')
    got = sqlite_storage.get_record_by_id(rec.id)
    assert got.status == 'FAILED'
    assert got.error_message == 'boom'


def test_get_running_record_by_func(sqlite_storage):
    """get_running_record_by_func: 有 RUNNING 返回记录，无返回 None（防重叠查询用）"""
    assert sqlite_storage.get_running_record_by_func('f') is None
    sqlite_storage.create_running_record('f', 'n', 'cron', 't', 'scheduler')
    running = sqlite_storage.get_running_record_by_func('f')
    assert running is not None
    assert running.status == 'RUNNING'
    # 已完成的任务不算 running
    sqlite_storage.update_record_status(running.id, 'SUCCESS', duration_ms=10)
    assert sqlite_storage.get_running_record_by_func('f') is None


def test_get_running_record_by_func_isolates_by_task(sqlite_storage):
    """A 任务 RUNNING 不影响 B 任务的 running 查询"""
    sqlite_storage.create_running_record('A', 'n', 'cron', 't', 'scheduler')
    assert sqlite_storage.get_running_record_by_func('A') is not None
    assert sqlite_storage.get_running_record_by_func('B') is None


def test_get_records_with_pagination(sqlite_storage):
    """get_records_with_pagination: 按 task_func 过滤 + 分页"""
    for i in range(5):
        sqlite_storage.create_running_record('f', 'n', 'cron', f't{i}', 'scheduler')
    logs, total = sqlite_storage.get_records_with_pagination(task_func='f', page=1, page_size=3)
    assert total == 5
    assert len(logs) == 3
    page2, _ = sqlite_storage.get_records_with_pagination(task_func='f', page=2, page_size=3)
    assert len(page2) == 2


def test_get_records_with_pagination_filter_status(sqlite_storage):
    """get_records_with_pagination: 按 status 过滤"""
    r1 = sqlite_storage.create_running_record('f', 'n', 'cron', 't1', 'scheduler')
    sqlite_storage.update_record_status(r1.id, 'SUCCESS', duration_ms=10)
    sqlite_storage.create_running_record('f', 'n', 'cron', 't2', 'scheduler')  # RUNNING
    running, total = sqlite_storage.get_records_with_pagination(task_func='f', status='RUNNING')
    assert total == 1
    assert running[0].status == 'RUNNING'


def test_clean_records_before_skips_running(sqlite_storage):
    """clean_records_before: 删 N 天前非 RUNNING 记录，RUNNING 不删"""
    # 一条已完成的旧记录
    old = sqlite_storage.create_running_record('f', 'n', 'cron', 't1', 'scheduler')
    sqlite_storage.update_record_status(old.id, 'SUCCESS', duration_ms=10)
    # 手动把 create_time 改成 10 天前（sqlite 内存库直接改）
    from app.storage.task_run_record_storage import TaskRunRecord
    session = sqlite_storage.get_session()
    session.query(TaskRunRecord).filter_by(id=old.id).update({'create_time': datetime.now() - timedelta(days=10)})
    session.commit()
    session.close()
    # 一条 RUNNING（也改旧时间，但不应被删）
    running = sqlite_storage.create_running_record('f', 'n', 'cron', 't2', 'scheduler')
    session = sqlite_storage.get_session()
    session.query(TaskRunRecord).filter_by(id=running.id).update({'create_time': datetime.now() - timedelta(days=10)})
    session.commit()
    session.close()

    deleted = sqlite_storage.clean_records_before(days=7)
    assert deleted == 1  # 只删了那条 SUCCESS 旧记录
    assert sqlite_storage.get_record_by_id(old.id) is None
    assert sqlite_storage.get_record_by_id(running.id) is not None  # RUNNING 保留


def test_create_skipped_record(sqlite_storage):
    """create_skipped_record: cron 防重叠跳过时记 SKIPPED（start==end, duration=0）"""
    rec = sqlite_storage.create_skipped_record('f', 'n', 'cron', trace_id='t', triggered_by='scheduler')
    assert rec.status == 'SKIPPED'
    assert rec.start_time is not None
    assert rec.end_time is not None
    assert rec.duration_ms == 0


# ==================== execute_task_with_record 状态机（mock Storage） ====================

@pytest.fixture
def scheduler_with_mock_storage():
    """CronTaskScheduler 实例，注入 mock 的 TaskRunRecordStorage，不连真实库"""
    from app.scheduler.cron_scheduler import CronTaskScheduler
    sched = CronTaskScheduler()
    sched._run_record_storage = MagicMock()
    return sched


def test_execute_task_success_flow(scheduler_with_mock_storage):
    """cron 路径：无 RUNNING -> INSERT RUNNING -> 跑任务 -> UPDATE SUCCESS（耗时>0）"""
    sched = scheduler_with_mock_storage
    sched._run_record_storage.get_running_record_by_func.return_value = None  # 无重叠
    fake_record = MagicMock(id=101)
    sched._run_record_storage.create_running_record.return_value = fake_record

    task_func = MagicMock()
    sched.task_registry['demo_task'] = task_func

    sched.execute_task_with_record('demo_task', '演示任务', trigger_type='cron', triggered_by='scheduler')

    task_func.assert_called_once()
    sched._run_record_storage.create_running_record.assert_called_once()
    # UPDATE 成功
    update_args = sched._run_record_storage.update_record_status.call_args
    assert update_args.args[0] == 101  # record_id
    assert update_args.args[1] == 'SUCCESS'
    assert update_args.kwargs['duration_ms'] >= 0


def test_execute_task_failed_on_exception(scheduler_with_mock_storage):
    """任务抛异常 -> UPDATE FAILED + error_message 有值，异常被吞（不向上抛）"""
    sched = scheduler_with_mock_storage
    sched._run_record_storage.get_running_record_by_func.return_value = None
    fake_record = MagicMock(id=102)
    sched._run_record_storage.create_running_record.return_value = fake_record

    task_func = MagicMock(side_effect=Exception('boom'))
    sched.task_registry['demo_task'] = task_func

    # 不应向上抛异常（包装器捕获记 FAILED）
    sched.execute_task_with_record('demo_task', '演示任务', trigger_type='cron', triggered_by='scheduler')

    update_args = sched._run_record_storage.update_record_status.call_args
    assert update_args.args[1] == 'FAILED'
    assert 'boom' in update_args.kwargs['error_message']


def test_execute_task_skipped_when_running(scheduler_with_mock_storage):
    """cron 防重叠：已有 RUNNING -> 不执行任务、记 SKIPPED、return"""
    sched = scheduler_with_mock_storage
    sched._run_record_storage.get_running_record_by_func.return_value = MagicMock(id=999)  # 已在运行

    task_func = MagicMock()
    sched.task_registry['demo_task'] = task_func

    sched.execute_task_with_record('demo_task', '演示任务', trigger_type='cron', triggered_by='scheduler')

    task_func.assert_not_called()  # 没执行任务
    sched._run_record_storage.create_running_record.assert_not_called()  # 没记 RUNNING
    sched._run_record_storage.create_skipped_record.assert_called_once()  # 记了 SKIPPED
    sched._run_record_storage.update_record_status.assert_not_called()  # 没 UPDATE


def test_execute_task_trace_id_reused(scheduler_with_mock_storage):
    """记录的 trace_id 与 run_with_trace_context 注入的一致（日志可串联）"""
    sched = scheduler_with_mock_storage
    sched._run_record_storage.get_running_record_by_func.return_value = None
    # create_running_record 返回的 record，其 trace_id 就是传入的 trace_id
    def _create(*args, **kwargs):
        return MagicMock(id=103, trace_id=kwargs.get('trace_id'))
    sched._run_record_storage.create_running_record.side_effect = _create

    captured_trace_ids = []
    def task_func():
        from app.utils.logger import trace_id_var
        captured_trace_ids.append(trace_id_var.get())
    sched.task_registry['demo_task'] = task_func

    sched.execute_task_with_record('demo_task', '演示', trigger_type='cron', triggered_by='scheduler')

    # create_running_record 收到的 trace_id（第 4 个位置参数）
    used_trace_id = sched._run_record_storage.create_running_record.call_args.args[3]
    # 任务执行时 ContextVar 的 trace_id 与记录一致
    assert captured_trace_ids == [used_trace_id]
    assert used_trace_id  # 非空


# ==================== run_job_now 异步（手动路径） ====================

def test_run_job_now_rejected_when_running(scheduler_with_mock_storage):
    """手动触发遇 RUNNING：不记表、不起线程、返回 rejected"""
    sched = scheduler_with_mock_storage
    sched._run_record_storage.get_running_record_by_func.return_value = MagicMock(id=999)  # 已在运行

    task_func = MagicMock()
    sched.task_registry['demo_task'] = task_func

    result = sched.run_job_now('demo_task', triggered_by='admin')

    assert result.get('rejected') is True
    task_func.assert_not_called()  # 没执行
    sched._run_record_storage.create_running_record.assert_not_called()  # 没记表


def test_run_job_now_returns_triggered_immediately(scheduler_with_mock_storage):
    """手动触发无重叠：立即返回 record_id+trace_id，不阻塞等任务完成"""
    sched = scheduler_with_mock_storage
    sched._run_record_storage.get_running_record_by_func.return_value = None
    fake_record = MagicMock(id=201)
    sched._run_record_storage.create_running_record.return_value = fake_record

    done_flag = []
    def slow_task(force_run=False):
        time.sleep(0.3)
        done_flag.append(True)
    sched.task_registry['demo_task'] = slow_task

    result = sched.run_job_now('demo_task', triggered_by='admin')

    # 立即返回（任务还在跑）
    assert result.get('record_id') == 201
    returned_trace_id = result.get('trace_id')
    assert returned_trace_id  # 非空
    # 返回的 trace_id 与传给 create_running_record 的一致
    assert sched._run_record_storage.create_running_record.call_args.args[3] == returned_trace_id
    assert done_flag == []  # 任务尚未完成（证明没阻塞）
    # 等后台线程跑完
    time.sleep(0.5)
    assert done_flag == [True]


def test_run_job_now_updates_success_after_thread(scheduler_with_mock_storage):
    """后台线程跑完后 UPDATE SUCCESS"""
    sched = scheduler_with_mock_storage
    sched._run_record_storage.get_running_record_by_func.return_value = None
    fake_record = MagicMock(id=202, trace_id='t')
    sched._run_record_storage.create_running_record.return_value = fake_record

    sched.task_registry['demo_task'] = lambda force_run=False: None  # 成功任务
    sched.run_job_now('demo_task', triggered_by='admin')
    time.sleep(0.3)  # 等线程

    update_args = sched._run_record_storage.update_record_status.call_args
    assert update_args.args[0] == 202
    assert update_args.args[1] == 'SUCCESS'


def test_run_job_now_updates_failed_on_exception(scheduler_with_mock_storage):
    """后台线程任务异常时 UPDATE FAILED，不卡 RUNNING"""
    sched = scheduler_with_mock_storage
    sched._run_record_storage.get_running_record_by_func.return_value = None
    fake_record = MagicMock(id=203, trace_id='t')
    sched._run_record_storage.create_running_record.return_value = fake_record

    sched.task_registry['demo_task'] = MagicMock(side_effect=Exception('boom'))
    sched.run_job_now('demo_task', triggered_by='admin')
    time.sleep(0.3)

    update_args = sched._run_record_storage.update_record_status.call_args
    assert update_args.args[1] == 'FAILED'
    assert 'boom' in update_args.kwargs['error_message']


def test_run_job_now_unknown_task(scheduler_with_mock_storage):
    """未注册任务返回 False"""
    sched = scheduler_with_mock_storage
    assert sched.run_job_now('not_exist') is False


# ==================== 执行记录 API（mock Storage，不碰库） ====================

@pytest.fixture
def api_client():
    """Flask 测试客户端 + mock 掉所有 Storage（参照 conftest 范式）"""
    from app.web import api_server
    api_server.app.config['TESTING'] = True
    api_server.app.config['SECRET_KEY'] = 'test-secret'
    api_server._run_record_storage = MagicMock()
    api_server._task_storage = MagicMock()
    api_server._user_storage = MagicMock()
    # mock 鉴权：get_user_by_id 返回有效用户，绕过登录
    api_server._user_storage.get_user_by_id.return_value = {'id': 1, 'username': 'admin', 'enabled': True, 'role': 'admin'}
    with api_server.app.test_client() as c:
        # 种 session 模拟已登录
        with c.session_transaction() as sess:
            sess['user_id'] = 1
        yield c


def test_api_get_task_records_pagination(api_client):
    """GET /api/task-records 分页 + task_func 过滤"""
    from app.web import api_server
    fake_records = [MagicMock(id=1, task_func='f', task_name='n', trigger_type='cron',
                              status='SUCCESS', trace_id='t1', triggered_by='scheduler',
                              start_time=datetime(2026,7,18,10,0), end_time=datetime(2026,7,18,10,1),
                              duration_ms=60000, error_message=None)]
    api_server._run_record_storage.get_records_with_pagination.return_value = (fake_records, 1)

    resp = api_client.get('/api/task-records?task_func=f&page=1&page_size=20')
    assert resp.status_code == 200
    body = resp.get_json()
    assert body['total'] == 1
    assert body['data'][0]['status'] == 'SUCCESS'
    assert body['data'][0]['duration_ms'] == 60000
    api_server._run_record_storage.get_records_with_pagination.assert_called_once()
    args = api_server._run_record_storage.get_records_with_pagination.call_args.kwargs
    assert args['task_func'] == 'f'


def test_api_get_task_record_single(api_client):
    """GET /api/task-records/<id> 单条轮询"""
    from app.web import api_server
    api_server._run_record_storage.get_record_by_id.return_value = MagicMock(
        id=5, task_func='f', task_name='n', trigger_type='manual', status='RUNNING',
        trace_id='t', triggered_by='admin', start_time=datetime(2026,7,18,10,0),
        end_time=None, duration_ms=None, error_message=None)
    resp = api_client.get('/api/task-records/5')
    assert resp.status_code == 200
    assert resp.get_json()['status'] == 'RUNNING'


def test_api_get_task_record_not_found(api_client):
    """GET /api/task-records/<id> 不存在返回 404"""
    from app.web import api_server
    api_server._run_record_storage.get_record_by_id.return_value = None
    resp = api_client.get('/api/task-records/999')
    assert resp.status_code == 404


def test_api_clean_task_records(api_client):
    """DELETE /api/task-records?days=30 清理"""
    from app.web import api_server
    api_server._run_record_storage.clean_records_before.return_value = 5
    resp = api_client.delete('/api/task-records?days=30')
    assert resp.status_code == 200
    body = resp.get_json()
    assert body['deleted'] == 5
    api_server._run_record_storage.clean_records_before.assert_called_once_with(30)


def test_api_tasks_returns_running_flag(api_client):
    """GET /api/tasks 返回每个任务的 running 字段"""
    from app.web import api_server
    from app.storage.task_schedule_storage import TaskSchedule
    # mock _task_storage.get_session 返回的 session 链式调用
    fake_task = MagicMock()
    fake_task.id = 1
    fake_task.task_name = '演示'
    fake_task.task_func = 'demo_task'
    fake_task.cron_expression = '0 * * * *'
    fake_task.enabled = 1
    fake_task.description = ''
    fake_task.create_time = datetime(2026, 7, 18)
    fake_task.update_time = datetime(2026, 7, 18)

    mock_session = MagicMock()
    mock_query = MagicMock()
    mock_query.filter.return_value = mock_query
    mock_query.like.return_value = mock_query
    mock_query.count.return_value = 1
    mock_query.offset.return_value.limit.return_value.all.return_value = [fake_task]
    mock_session.query.return_value = mock_query
    api_server._task_storage.get_session.return_value = mock_session

    # mock scheduler_proxy.get_all_jobs 与 running 查询
    with patch('app.web.api_server.scheduler_proxy.get_all_jobs', return_value={}), \
         patch('app.web.api_server._run_record_storage.get_running_task_funcs', return_value=['demo_task']):
        resp = api_client.get('/api/tasks?page=1&page_size=10')
    assert resp.status_code == 200
    data = resp.get_json()['data']
    assert data[0]['running'] is True  # demo_task 在 running 列表
    assert 'running' in data[0]
