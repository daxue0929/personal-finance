"""
统一指数抓取任务
替代 fetch_kc50_index_task / fetch_kc100_index_task / fetch_hs300_index_task / fetch_cyb50_index_task。
参数由 task_schedule.func_args 注入（index_code / market）。
"""
from .index_fetch_helper import fetch_and_store_index_with_market
from ..storage import FundInfoStorage
from ..utils.logger import logger


def fetch_index_task(force_run: bool = False, **kwargs) -> None:
    """统一指数抓取任务。

    Args:
        force_run: True 时跳过交易时段检查（由调度器透传）
        **kwargs: 业务参数
            index_code (str): 6 位指数代码
            market (str): 'sh' 或 'sz'，腾讯接口市场前缀
    """
    index_code = kwargs.get('index_code', '')
    market = kwargs.get('market', 'sh')

    if not index_code or len(index_code) != 6:
        raise ValueError(f"index_code 必传且长度 6, got {index_code!r}")
    if market not in ('sh', 'sz'):
        raise ValueError(f"market 必须为 'sh' 或 'sz', got {market!r}")

    logger.info("=" * 50)
    logger.info(f"开始执行指数抓取任务: {index_code} ({market})")

    index_data = fetch_and_store_index_with_market(index_code, market, force_run)
    if not index_data:
        return

    # kc100 副作用（硬编码 magic code，详见 PRD §5 "不目标"）：
    # 将当日涨跌幅同步到基金 020292 remark。删除/迁移此分支需联动检查 fund_info.020292 业务方。
    if index_code == '000698':
        try:
            change_pct_str = f"{index_data.change_percent:.2f}"
            if FundInfoStorage().update_fund_remark('020292', change_pct_str):
                logger.info(f"  成功更新 fund_info 表中 020292 的 remark 字段 ({change_pct_str}%)")
            else:
                logger.warning("  更新 fund_info 表失败")
        except Exception as e:
            logger.error(f"更新 fund_info 020292 remark 失败: {e}")
