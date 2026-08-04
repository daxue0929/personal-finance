"""
fetch_index_task 统一任务函数测试

签名：fetch_index_task(force_run=False, **kwargs)
kwargs 含 index_code / market；kc100 (000698) 副作用写入 fund_info.020292
"""
import pytest
from unittest.mock import MagicMock, patch

from app.parser.kc_index_parser import KcIndexData


def _make_index_data(code='000698', change_pct=1.23):
    return KcIndexData(
        index_code=code, index_name='科创100' if code == '000698' else '科创50',
        open_price=1000.0, close_price=1010.0, high_price=1020.0, low_price=990.0,
        change_percent=change_pct, volume=10000.0, amount=200.0,
        turnover_rate=0.0, pe_ratio=50.0, pb_ratio=0.0,
        update_time='2026-08-01 15:00:00', trade_date='2026-08-01'
    )


# ==================== 入参校验 ====================

def test_fetch_index_task_value_error_no_code():
    """缺 index_code -> ValueError"""
    from app.task.fetch_index_task import fetch_index_task
    with pytest.raises(ValueError, match="index_code 必传"):
        fetch_index_task(force_run=False)


def test_fetch_index_task_value_error_wrong_length_code():
    """index_code 长度非 6 -> ValueError"""
    from app.task.fetch_index_task import fetch_index_task
    with pytest.raises(ValueError, match="长度 6"):
        fetch_index_task(force_run=False, index_code='00068', market='sh')


def test_fetch_index_task_value_error_invalid_market():
    """market='xx' -> ValueError"""
    from app.task.fetch_index_task import fetch_index_task
    with pytest.raises(ValueError, match="market"):
        fetch_index_task(force_run=False, index_code='000688', market='xx')


# ==================== 正常路径：调 helper ====================

@patch('app.task.fetch_index_task.FundInfoStorage')
@patch('app.task.fetch_index_task.fetch_and_store_index_with_market')
def test_fetch_index_task_calls_helper(mock_helper, mock_fund_storage):
    """普通指数 (000688) 调 helper，不调副作用"""
    from app.task.fetch_index_task import fetch_index_task
    mock_helper.return_value = _make_index_data('000688', change_pct=2.5)

    fetch_index_task(force_run=False, index_code='000688', market='sh')

    mock_helper.assert_called_once_with('000688', 'sh', False)
    mock_fund_storage.assert_not_called()


@patch('app.task.fetch_index_task.FundInfoStorage')
@patch('app.task.fetch_index_task.fetch_and_store_index_with_market')
def test_fetch_index_task_force_run_true(mock_helper, mock_fund_storage):
    """force_run=True 透传到 helper"""
    from app.task.fetch_index_task import fetch_index_task
    mock_helper.return_value = _make_index_data('000300', change_pct=-0.5)

    fetch_index_task(force_run=True, index_code='000300', market='sh')

    mock_helper.assert_called_once_with('000300', 'sh', True)


# ==================== kc100 副作用 ====================

@patch('app.task.fetch_index_task.FundInfoStorage')
@patch('app.task.fetch_index_task.fetch_and_store_index_with_market')
def test_fetch_index_task_kc100_side_effect(mock_helper, mock_fund_storage):
    """kc100 (000698) 调 helper + update_fund_remark('020292', '1.23')"""
    from app.task.fetch_index_task import fetch_index_task
    mock_helper.return_value = _make_index_data('000698', change_pct=1.23)
    mock_fund_storage.return_value.update_fund_remark.return_value = True

    fetch_index_task(force_run=False, index_code='000698', market='sh')

    mock_helper.assert_called_once_with('000698', 'sh', False)
    mock_fund_storage.return_value.update_fund_remark.assert_called_once_with('020292', '1.23')


@patch('app.task.fetch_index_task.FundInfoStorage')
@patch('app.task.fetch_index_task.fetch_and_store_index_with_market')
def test_fetch_index_task_kc100_no_data_no_side_effect(mock_helper, mock_fund_storage):
    """kc100 helper 返回 None -> 不调副作用"""
    from app.task.fetch_index_task import fetch_index_task
    mock_helper.return_value = None

    fetch_index_task(force_run=False, index_code='000698', market='sh')

    mock_helper.assert_called_once_with('000698', 'sh', False)
    mock_fund_storage.assert_not_called()


@patch('app.task.fetch_index_task.FundInfoStorage')
@patch('app.task.fetch_index_task.fetch_and_store_index_with_market')
def test_fetch_index_task_kc100_side_effect_error_swallowed(mock_helper, mock_fund_storage):
    """update_fund_remark 抛异常 -> 任务不报错"""
    from app.task.fetch_index_task import fetch_index_task
    mock_helper.return_value = _make_index_data('000698', change_pct=1.5)
    mock_fund_storage.return_value.update_fund_remark.side_effect = Exception("db error")

    # 不应抛异常
    fetch_index_task(force_run=False, index_code='000698', market='sh')

    mock_helper.assert_called_once()
    mock_fund_storage.return_value.update_fund_remark.assert_called_once()


@patch('app.task.fetch_index_task.FundInfoStorage')
@patch('app.task.fetch_index_task.fetch_and_store_index_with_market')
def test_fetch_index_task_non_kc100_no_side_effect(mock_helper, mock_fund_storage):
    """非 kc100 (000688) 不调副作用（控制组）"""
    from app.task.fetch_index_task import fetch_index_task
    mock_helper.return_value = _make_index_data('000688', change_pct=2.0)

    fetch_index_task(force_run=False, index_code='000688', market='sh')

    mock_fund_storage.assert_not_called()
