"""
KcIndexParser market 参数校验测试

重构后 KcIndexParser(index_code, market) 两个都必传，market ∈ {sh, sz}。
"""
import pytest

from app.parser.kc_index_parser import KcIndexParser


def test_init_requires_market():
    """不传 market -> TypeError"""
    with pytest.raises(TypeError):
        KcIndexParser('000688')


def test_init_invalid_market_value():
    """market='xx' -> ValueError"""
    with pytest.raises(ValueError, match="market 必须是 sh/sz"):
        KcIndexParser('000688', market='xx')


def test_init_valid_sh_market():
    """market='sh' 不抛异常"""
    p = KcIndexParser('000688', market='sh')
    assert p.index_code == '000688'
    assert p.market == 'sh'
    assert p.index_name == ''  # 不再硬编码


def test_init_valid_sz_market():
    """market='sz' 不抛异常"""
    p = KcIndexParser('399673', market='sz')
    assert p.index_code == '399673'
    assert p.market == 'sz'


def test_index_config_removed():
    """INDEX_CONFIG 字典不存在"""
    assert not hasattr(KcIndexParser, 'INDEX_CONFIG')


def test_get_supported_indices_removed():
    """get_supported_indices 类方法不存在"""
    assert not hasattr(KcIndexParser, 'get_supported_indices')
