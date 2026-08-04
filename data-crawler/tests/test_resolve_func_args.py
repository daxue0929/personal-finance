"""
_resolve_func_args 解析逻辑测试

覆盖：override 优先 / DB 字符串 / DB dict / DB None / 解析失败 / 行不存在
"""
from unittest.mock import MagicMock, patch

from app.scheduler.cron_scheduler import CronTaskScheduler


def _new_sched():
    """构造一个不触发 __init__ 重型初始化的实例，仅 stub 必要依赖"""
    s = CronTaskScheduler.__new__(CronTaskScheduler)
    s._task_storage = MagicMock()
    return s


def test_resolve_override_takes_priority():
    """override 优先于 DB"""
    s = _new_sched()
    s._task_storage.get_task_by_func.return_value = MagicMock(func_args={'a': 1})
    result = s._resolve_func_args('fetch_index_task', override={'b': 2})
    assert result == {'b': 2}


def test_resolve_override_isolated_copy():
    """override 返回的 dict 是副本，外部修改不影响内部"""
    s = _new_sched()
    src = {'x': 1}
    s._task_storage.get_task_by_func.return_value = MagicMock(func_args=None)
    result = s._resolve_func_args('fetch_index_task', override=src)
    src['y'] = 99
    assert 'y' not in result


def test_resolve_db_string_json():
    """DB func_args 是 JSON 字符串 -> 解析为 dict"""
    s = _new_sched()
    s._task_storage.get_task_by_func.return_value = MagicMock(
        func_args='{"index_code":"000688","market":"sh"}'
    )
    result = s._resolve_func_args('fetch_index_task')
    assert result == {'index_code': '000688', 'market': 'sh'}


def test_resolve_db_dict():
    """DB func_args 是 dict（MySQL JSON 列）-> 直接 dict() 拷贝"""
    s = _new_sched()
    s._task_storage.get_task_by_func.return_value = MagicMock(
        func_args={'index_code': '000300', 'market': 'sh'}
    )
    result = s._resolve_func_args('fetch_index_task')
    assert result == {'index_code': '000300', 'market': 'sh'}


def test_resolve_db_none_returns_empty():
    """DB func_args 是 None -> 返回空 dict"""
    s = _new_sched()
    s._task_storage.get_task_by_func.return_value = MagicMock(func_args=None)
    result = s._resolve_func_args('fetch_index_task')
    assert result == {}


def test_resolve_task_not_found_returns_empty():
    """行不存在 -> 返回空 dict"""
    s = _new_sched()
    s._task_storage.get_task_by_func.return_value = None
    result = s._resolve_func_args('unknown_task')
    assert result == {}


def test_resolve_invalid_json_string_returns_empty():
    """非法 JSON 字符串 -> 返回空 dict（不抛）"""
    s = _new_sched()
    s._task_storage.get_task_by_func.return_value = MagicMock(func_args='{not valid json')
    result = s._resolve_func_args('fetch_index_task')
    assert result == {}


def test_resolve_storage_exception_returns_empty():
    """DB 查询异常 -> 返回空 dict（不阻塞任务执行）"""
    s = _new_sched()
    s._task_storage.get_task_by_func.side_effect = Exception('db down')
    result = s._resolve_func_args('fetch_index_task')
    assert result == {}
