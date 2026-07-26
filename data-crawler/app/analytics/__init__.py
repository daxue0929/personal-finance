"""分析计算模块（纯计算，不依赖数据库）"""
from .index_analysis import (
    calc_moving_average,
    calc_volatility,
    calc_annualized_return,
    calc_change_distribution,
    calc_monthly_returns,
    simulate_dca,
    calc_ma_signal,
    calc_bollinger_bands,
    calc_bollinger_signal,
)
from .position_analysis import (
    calc_max_drawdown,
    calc_position_overview,
    calc_position_allocation,
    calc_portfolio_profit_series,
    calc_portfolio_overview,
    compute_cost_index_series,
    filter_trading_days,
)

__all__ = [
    'calc_moving_average',
    'calc_volatility',
    'calc_annualized_return',
    'calc_change_distribution',
    'calc_monthly_returns',
    'simulate_dca',
    'calc_ma_signal',
    'calc_bollinger_bands',
    'calc_bollinger_signal',
    'calc_max_drawdown',
    'calc_position_overview',
    'calc_position_allocation',
    'calc_portfolio_profit_series',
    'calc_portfolio_overview',
    'compute_cost_index_series',
    'filter_trading_days',
]
