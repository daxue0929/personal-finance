#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fetch_all_indexes_task 统一遍历抓取任务测试（TDD）

配套功能：PRD "index-basic-table" §AC-3 T3
- 遍历 index_basic.enabled=1 全量抓取
- ThreadPoolExecutor(max_workers=4) 并发
- 单支异常不中断其他
- kc100 (000698) 副作用：抓取后调 update_fund_remark('020292', ...)
"""
from unittest.mock import MagicMock, patch

import pytest

from app.parser.kc_index_parser import KcIndexData


def _make_index_data(code='000300', change_pct=1.5):
    return KcIndexData(
        index_code=code, index_name=f'测试_{code}', open_price=1000.0,
        close_price=1010.0, high_price=1020.0, low_price=990.0,
        change_percent=change_pct, volume=10000.0, amount=200.0,
        turnover_rate=0.0, pe_ratio=50.0, pb_ratio=0.0,
        update_time='2026-08-06 15:00:00', trade_date='2026-08-06'
    )


# ==================== 空列表处理 ====================

@patch('app.task.fetch_all_indexes_task.IndexBasicStorage')
@patch('app.task.fetch_all_indexes_task.FundInfoStorage')
@patch('app.task.fetch_all_indexes_task.fetch_and_store_index_with_market')
def test_no_enabled_indexes_logs_and_returns(mock_helper, mock_fund_storage, mock_basic_cls):
    """list_enabled()=[] 时打 WARN 日志并 return，不调 helper、不调副作用"""
    from app.task.fetch_all_indexes_task import fetch_all_indexes_task
    mock_basic_cls.return_value.list_enabled.return_value = []

    fetch_all_indexes_task(force_run=False)

    # helper 0 次
    mock_helper.assert_not_called()
    # 副作用 0 次
    mock_fund_storage.assert_not_called()


# ==================== 并发抓取 ====================

@patch('app.task.fetch_all_indexes_task.IndexBasicStorage')
@patch('app.task.fetch_all_indexes_task.FundInfoStorage')
@patch('app.task.fetch_all_indexes_task.ThreadPoolExecutor')
@patch('app.task.fetch_all_indexes_task.as_completed')
def test_concurrent_fetch_uses_threadpool(mock_as_completed, mock_executor_cls,
                                          mock_fund_storage, mock_basic_cls):
    """4 支指数时 ThreadPoolExecutor 收到 4 个 future；as_completed 用于收集"""
    from app.task.fetch_all_indexes_task import fetch_all_indexes_task
    # 4 支指数
    mock_basic_cls.return_value.list_enabled.return_value = [
        ('000300', 'sh', '沪深300'),
        ('000688', 'sh', '科创50'),
        ('000698', 'sh', '科创100'),
        ('399673', 'sz', '创业板50'),
    ]
    # mock ThreadPoolExecutor context manager
    mock_executor = MagicMock()
    mock_executor_cls.return_value.__enter__.return_value = mock_executor
    # submit 返回 mock future
    mock_futures = [MagicMock() for _ in range(4)]
    mock_executor.submit.side_effect = mock_futures
    # as_completed 返回完成列表
    mock_as_completed.return_value = []

    fetch_all_indexes_task(force_run=False)

    # ThreadPoolExecutor(max_workers=4) 被调用
    mock_executor_cls.assert_called_once_with(max_workers=4)
    # submit 被调 4 次
    assert mock_executor.submit.call_count == 4
    # 每次 submit 调的是 (_fetch_one_safe, code, market, force_run) 形式
    # args[0] 是 _fetch_one_safe wrapper 函数，args[1] 是 code, args[2] 是 market, args[3] 是 force_run
    for i, call in enumerate(mock_executor.submit.call_args_list):
        code = call.args[1]
        market = call.args[2]
        force_run = call.args[3]
        assert code in ('000300', '000688', '000698', '399673')
        assert market in ('sh', 'sz')
        assert force_run is False


# ==================== 单支失败不中断 ====================

@patch('app.task.fetch_all_indexes_task.IndexBasicStorage')
@patch('app.task.fetch_all_indexes_task.FundInfoStorage')
@patch('app.task.fetch_all_indexes_task.ThreadPoolExecutor')
@patch('app.task.fetch_all_indexes_task.as_completed')
def test_single_failure_does_not_block_others(mock_as_completed, mock_executor_cls,
                                              mock_fund_storage, mock_basic_cls):
    """一支 future 抛异常不影响其他 3 支完成"""
    from app.task.fetch_all_indexes_task import fetch_all_indexes_task
    mock_basic_cls.return_value.list_enabled.return_value = [
        ('000300', 'sh', '沪深300'),
        ('000688', 'sh', '科创50'),
        ('000698', 'sh', '科创100'),
        ('399673', 'sz', '创业板50'),
    ]

    mock_executor = MagicMock()
    mock_executor_cls.return_value.__enter__.return_value = mock_executor
    mock_futures = [MagicMock() for _ in range(4)]
    mock_executor.submit.side_effect = mock_futures

    # future.result() 一支抛异常，其他正常
    def result_with_failure(fut):
        # 简单：第一个抛，其他返 KcIndexData
        if fut is mock_futures[1]:  # 000688 失败
            raise Exception("网络超时")
        return _make_index_data(code='000300' if fut is mock_futures[0]
                                else '000698' if fut is mock_futures[2]
                                else '399673')

    # mock_as_completed 返回的 future，future.result() 走 result_with_failure
    async_results = [mock_futures[0], mock_futures[1], mock_futures[2], mock_futures[3]]
    mock_as_completed.return_value = async_results
    for i, f in enumerate(mock_futures):
        f.result.side_effect = lambda ff=f, i=i: result_with_failure(ff)

    # 不应抛异常
    fetch_all_indexes_task(force_run=False)

    # 4 支都被 submit
    assert mock_executor.submit.call_count == 4


# ==================== kc100 副作用 ====================

@patch('app.task.fetch_all_indexes_task.IndexBasicStorage')
@patch('app.task.fetch_all_indexes_task.FundInfoStorage')
@patch('app.task.fetch_all_indexes_task.ThreadPoolExecutor')
@patch('app.task.fetch_all_indexes_task.as_completed')
def test_kc100_side_effect_runs_after_concurrent(mock_as_completed, mock_executor_cls,
                                                 mock_fund_storage, mock_basic_cls):
    """000698 抓取后调 FundInfoStorage.update_fund_remark('020292', '1.50')"""
    from app.task.fetch_all_indexes_task import fetch_all_indexes_task
    mock_basic_cls.return_value.list_enabled.return_value = [
        ('000300', 'sh', '沪深300'),
        ('000698', 'sh', '科创100'),  # kc100
    ]
    mock_executor = MagicMock()
    mock_executor_cls.return_value.__enter__.return_value = mock_executor
    mock_futures = [MagicMock(), MagicMock()]
    mock_executor.submit.side_effect = mock_futures

    # future 0 = 000300 (1.2%), future 1 = 000698 (1.5%)
    results = [
        _make_index_data(code='000300', change_pct=1.2),
        _make_index_data(code='000698', change_pct=1.5),
    ]
    mock_as_completed.return_value = list(mock_futures)  # as_completed 返 futures
    for f, r in zip(mock_futures, results):
        f.result.return_value = r  # future.result() 返 data

    fetch_all_indexes_task(force_run=False)

    # 副作用：仅 kc100 触发
    mock_fund_storage.return_value.update_fund_remark.assert_called_once_with('020292', '1.50')


# ==================== kc100 副作用异常吞咽 ====================

@patch('app.task.fetch_all_indexes_task.IndexBasicStorage')
@patch('app.task.fetch_all_indexes_task.FundInfoStorage')
@patch('app.task.fetch_all_indexes_task.ThreadPoolExecutor')
@patch('app.task.fetch_all_indexes_task.as_completed')
def test_kc100_side_effect_swallows_exception(mock_as_completed, mock_executor_cls,
                                              mock_fund_storage, mock_basic_cls):
    """update_fund_remark 抛异常 → 任务不抛（吞咽）"""
    from app.task.fetch_all_indexes_task import fetch_all_indexes_task
    mock_basic_cls.return_value.list_enabled.return_value = [
        ('000698', 'sh', '科创100'),
    ]
    mock_executor = MagicMock()
    mock_executor_cls.return_value.__enter__.return_value = mock_executor
    future = MagicMock()
    future.result.return_value = _make_index_data(code='000698', change_pct=2.0)
    mock_executor.submit.return_value = future
    mock_as_completed.return_value = [future]

    # 副作用抛异常
    mock_fund_storage.return_value.update_fund_remark.side_effect = Exception("DB 写入失败")

    # 不应抛
    fetch_all_indexes_task(force_run=False)

    mock_fund_storage.return_value.update_fund_remark.assert_called_once()
