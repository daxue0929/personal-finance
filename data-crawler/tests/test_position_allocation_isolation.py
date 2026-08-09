#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Dashboard allocation 路由的 user 隔离测试（storage 层）。

按项目惯例用 mock session，不连真实库（conftest.py 明确禁止）。
被测对象：PositionStorage.get_all_active_positions(user_id=...) 的 filter 行为。
"""

from unittest.mock import MagicMock

from app.storage.position_storage import PositionStorage, Position


def _make_storage_with_tracked_chain():
    """构造可追踪的链式 mock，每次 .filter() 调用都返回独立 mock 并计数。"""
    storage = PositionStorage()
    mock_session = MagicMock()
    storage.Session = MagicMock(return_value=mock_session)

    counter = {'filter': 0}

    def make_query(_cls):
        q = MagicMock(name='query')

        def _filter(cond):
            counter['filter'] += 1
            f = MagicMock(name=f'filter#{counter["filter"]}')

            def _inner(c2):
                counter['filter'] += 1
                f2 = MagicMock(name=f'filter#{counter["filter"]}')
                f2.all.return_value = []
                return f2
            f.filter.side_effect = _inner
            f.all.return_value = []
            return f
        q.filter.side_effect = _filter
        return q

    mock_session.query.side_effect = make_query
    return storage, counter


def test_user_id_none_只调一次_filter():
    storage, counter = _make_storage_with_tracked_chain()
    storage.get_all_active_positions(user_id=None)
    assert counter['filter'] == 1, (
        f'user_id=None 应只调 1 次 filter，实际 {counter["filter"]}'
    )


def test_user_id_传入时链上调两次_filter():
    storage, counter = _make_storage_with_tracked_chain()
    storage.get_all_active_positions(user_id=42)
    assert counter['filter'] == 2, (
        f'user_id=42 应调 2 次 filter（del_flag + user_id），实际 {counter["filter"]}'
    )


def test_user_id_传入时返回该_user_的持仓_dict():
    """mock all() 返 2 条 Position，storage 输出应含 2 条 dict。"""
    storage = PositionStorage()
    mock_session = MagicMock()
    storage.Session = MagicMock(return_value=mock_session)

    p1 = Position()
    p1.fund_code = 'TEST001'
    p1.fund_name = '测试A'
    p1.current_value = 1000.00
    p1.user_id = 42
    p1.del_flag = '1'

    p2 = Position()
    p2.fund_code = 'TEST002'
    p2.fund_name = '测试B'
    p2.current_value = 2000.00
    p2.user_id = 42
    p2.del_flag = '1'

    mock_session.query.return_value.filter.return_value.filter.return_value.all.return_value = [p1, p2]

    rows = storage.get_all_active_positions(user_id=42)
    codes = sorted(r['fund_code'] for r in rows)
    assert codes == ['TEST001', 'TEST002'], (
        f'user_id=42 应返其两条持仓，实际 {codes}'
    )
    values = sorted(r['current_value'] for r in rows)
    assert values == [1000.0, 2000.0]


def test_user_id_不同_查询相互隔离():
    """两次不同 user_id 的查询：链上 .filter() 总共调 4 次，无状态污染。"""
    storage, counter = _make_storage_with_tracked_chain()
    storage.get_all_active_positions(user_id=10)
    storage.get_all_active_positions(user_id=20)
    # 每次调用 2 次 filter × 2 次调用 = 4
    assert counter['filter'] == 4, (
        f'两次 user_id 查询应共调 4 次 filter，实际 {counter["filter"]}'
    )


def test_user_id_不同_捕获_filter_条件():
    """user_id=10 与 user_id=20 时，filter 条件应含对应的 user_id 过滤。"""
    storage = PositionStorage()
    mock_session = MagicMock()
    storage.Session = MagicMock(return_value=mock_session)

    captured_rights = []  # 每次 filter 条件的右侧值（user_id 时是 10/20，del_flag 时是 '1'）

    def make_query(_cls):
        q = MagicMock(name='query')

        def _filter(cond):
            # 提取 cond 的右侧值
            try:
                right = cond.right.value
            except AttributeError:
                right = None
            captured_rights.append(right)

            f = MagicMock(name='filter1')

            def _inner(c2):
                try:
                    r2 = c2.right.value
                except AttributeError:
                    r2 = None
                captured_rights.append(r2)
                f2 = MagicMock(name='filter2')
                f2.all.return_value = []
                return f2
            f.filter.side_effect = _inner
            f.all.return_value = []
            return f
        q.filter.side_effect = _filter
        return q

    mock_session.query.side_effect = make_query

    storage.get_all_active_positions(user_id=10)
    storage.get_all_active_positions(user_id=20)

    # 每次 user_id 路径调 2 次 filter：第一次 del_flag='1'，第二次 user_id
    # 顺序：[('1', 10), ('1', 20)]
    assert captured_rights == ['1', 10, '1', 20], (
        f'filter 条件顺序应为 ["1", 10, "1", 20]，实际 {captured_rights}'
    )
