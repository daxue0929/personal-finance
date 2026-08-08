"""
SQL 迁移脚本结构验证（PRD multi-user AC-1）

不连真实 DB：纯文本解析 sql/alter/08_add_user_id_to_business_tables.sql +
sql/program/买入.sql + sql/program/持仓每日快照备份.sql，验证关键 DDL/DML 已就位。

开发环境跑过实际迁移后，再用真 DB 跑 SELECT 验证 6 表都有 user_id + invite_code 表
存在。生产部署时此测试通过 + 真 DB 验证两步缺一不可。
"""
import re
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[2]
MIGRATION_SQL = PROJECT_ROOT / 'sql' / 'alter' / '08_add_user_id_to_business_tables.sql'
BUY_SP_SQL = PROJECT_ROOT / 'sql' / 'program' / '买入.sql'
SNAPSHOT_SP_SQL = PROJECT_ROOT / 'sql' / 'program' / '持仓每日快照备份.sql'
SNAPSHOT_STRUCT_SQL = PROJECT_ROOT / 'sql' / 'struct' / 'position_daily_snapshot.sql'


# ==================== 迁移脚本存在性 + 6 步结构 ====================

def test_migration_sql_file_exists():
    assert MIGRATION_SQL.is_file(), f'缺少迁移脚本: {MIGRATION_SQL}'


@pytest.fixture
def migration_text():
    return MIGRATION_SQL.read_text(encoding='utf-8')


# 6 张业务表：每张都应出现 ADD COLUMN user_id + UPDATE user_id = admin + MODIFY NOT NULL + ADD INDEX
EXPECTED_TABLES = [
    'portfolio', 'fund_buyer', 'fund_seller',
    'position', 'position_daily_snapshot', 'fund_dip_plan',
]


# ==================== struct 文件同步：6 张表 DDL 加 user_id ====================

# 全部 6 个 struct 文件路径（fresh install 用的 CREATE TABLE DDL）
STRUCT_FILES = {
    'portfolio':               PROJECT_ROOT / 'sql' / 'struct' / 'portfolio.sql',
    'fund_buyer':              PROJECT_ROOT / 'sql' / 'struct' / 'fund_buyer.sql',
    'fund_seller':             PROJECT_ROOT / 'sql' / 'struct' / 'fund_seller.sql',
    'position':                PROJECT_ROOT / 'sql' / 'struct' / 'position.sql',
    'position_daily_snapshot': PROJECT_ROOT / 'sql' / 'struct' / 'position_daily_snapshot.sql',
    'fund_dip_plan':           PROJECT_ROOT / 'sql' / 'struct' / 'fund_dip_plan.sql',
}


@pytest.mark.parametrize('table', list(STRUCT_FILES.keys()))
def test_struct_sql_has_user_id_column(table):
    """6 张 struct DDL 都应有 user_id 列（fresh install 走 struct 不走 alter）"""
    path = STRUCT_FILES[table]
    assert path.is_file(), f'缺少 struct: {path}'
    text = path.read_text(encoding='utf-8')
    # user_id 列定义（带反引号）
    assert re.search(
        r'`user_id`\s+bigint\s+NOT\s+NULL\s+DEFAULT\s+\'1\'',
        text, re.IGNORECASE
    ), f'{table} struct 缺少 user_id bigint NOT NULL DEFAULT 1 列定义'


@pytest.mark.parametrize('table', list(STRUCT_FILES.keys()))
def test_struct_sql_has_idx_user_id(table):
    """6 张 struct DDL 都应有 idx_user_id 索引"""
    path = STRUCT_FILES[table]
    text = path.read_text(encoding='utf-8')
    assert re.search(
        r'KEY\s+`idx_user_id`\s*\(\s*`user_id`\s*\)',
        text, re.IGNORECASE
    ), f'{table} struct 缺少 KEY idx_user_id 索引'


@pytest.mark.parametrize('table', EXPECTED_TABLES)
def test_migration_adds_user_id_column(table, migration_text):
    """每张表应 ADD COLUMN user_id BIGINT NULL"""
    pattern = rf'ALTER\s+TABLE\s+`{table}`\s+ADD\s+COLUMN\s+`user_id`'
    assert re.search(pattern, migration_text, re.IGNORECASE), \
        f'{table} 缺少 ADD COLUMN user_id 步骤'


@pytest.mark.parametrize('table', EXPECTED_TABLES)
def test_migration_updates_old_data_to_admin(table, migration_text):
    """每张表应 UPDATE user_id = admin.id"""
    pattern = rf'UPDATE\s+`{table}`\s+SET\s+user_id\s*='
    assert re.search(pattern, migration_text, re.IGNORECASE), \
        f'{table} 缺少 UPDATE user_id 步骤'


@pytest.mark.parametrize('table', EXPECTED_TABLES)
def test_migration_modifies_user_id_not_null(table, migration_text):
    """每张表应 MODIFY COLUMN user_id NOT NULL"""
    pattern = rf'ALTER\s+TABLE\s+`{table}`\s+MODIFY\s+COLUMN\s+`user_id`[^,]*NOT\s+NULL'
    assert re.search(pattern, migration_text, re.IGNORECASE), \
        f'{table} 缺少 MODIFY user_id NOT NULL 步骤'


@pytest.mark.parametrize('table', EXPECTED_TABLES)
def test_migration_adds_idx_user_id(table, migration_text):
    """每张表应 ADD INDEX idx_user_id"""
    pattern = rf'ALTER\s+TABLE\s+`{table}`\s+ADD\s+INDEX\s+`idx_user_id`'
    assert re.search(pattern, migration_text, re.IGNORECASE), \
        f'{table} 缺少 ADD INDEX idx_user_id 步骤'


def test_migration_creates_invite_code_table(migration_text):
    """应 CREATE TABLE invite_code"""
    assert re.search(r'CREATE\s+TABLE\s+`invite_code`', migration_text, re.IGNORECASE), \
        '缺少 CREATE TABLE invite_code 步骤'

    # 关键字段
    for col in ['`code`', '`created_by`', '`expires_at`', '`used_at`', '`used_by`', '`del_flag`']:
        assert col in migration_text, f'invite_code 缺少字段 {col}'

    # UNIQUE 约束
    assert re.search(r'UNIQUE\s+KEY\s+`uk_code`\s*\(`code`\)', migration_text, re.IGNORECASE), \
        'invite_code 缺少 UNIQUE KEY uk_code 约束'


def test_migration_has_null_count_check(migration_text):
    """应有兜底校验：SELECT COUNT(*) WHERE user_id IS NULL"""
    # SQL 字段带反引号（`user_id`），regex 兼容
    assert re.search(r'COUNT\s*\(\s*\*\s*\).*`?user_id`?\s+IS\s+NULL', migration_text, re.IGNORECASE | re.DOTALL), \
        '缺少 user_id IS NULL 兜底校验步骤'


# ==================== 存储过程：买入加 p_user_id ====================

def test_buy_sp_adds_p_user_id_param():
    assert BUY_SP_SQL.is_file(), f'缺少存储过程: {BUY_SP_SQL}'

    text = BUY_SP_SQL.read_text(encoding='utf-8')
    # 入参：IN p_user_id BIGINT
    assert re.search(r'IN\s+p_user_id\s+BIGINT', text, re.IGNORECASE), \
        'sp_insert_fund_buyer_by_change 缺少 p_user_id 入参'
    # INSERT 段应包含 user_id 字段（非贪婪匹配括号内列名）
    assert re.search(r'INSERT\s+INTO\s+`fund_buyer`\s*\([\s\S]*?`user_id`', text, re.IGNORECASE), \
        'sp_insert_fund_buyer_by_change INSERT 段缺少 user_id 字段'
    # VALUES 段应包含 p_user_id（允许括号嵌套如 CURDATE()，故用 [\s\S]*?）
    assert re.search(r'VALUES\s*\([\s\S]*?p_user_id', text, re.IGNORECASE), \
        'sp_insert_fund_buyer_by_change VALUES 段缺少 p_user_id'


# ==================== 存储过程：snapshot 携带 user_id ====================

def test_snapshot_sp_carries_user_id():
    assert SNAPSHOT_SP_SQL.is_file(), f'缺少存储过程: {SNAPSHOT_SP_SQL}'

    text = SNAPSHOT_SP_SQL.read_text(encoding='utf-8')
    # SELECT 段加 p.user_id AS user_id
    assert re.search(r'p\.user_id\s+AS\s+user_id', text, re.IGNORECASE), \
        'backup_position_daily_snapshot SELECT 段缺少 p.user_id AS user_id（关键，否则快照 user_id 全 NULL）'
    # INSERT 列应包含 user_id（允许反引号可选）
    assert re.search(r'INSERT\s+INTO\s+position_daily_snapshot\s*\([^)]*?`?user_id`?', text, re.IGNORECASE | re.DOTALL), \
        'backup_position_daily_snapshot INSERT 列缺少 user_id'


# ==================== snapshot struct sql 同步加 user_id ====================

def test_snapshot_struct_sql_has_user_id():
    assert SNAPSHOT_STRUCT_SQL.is_file(), f'缺少 struct: {SNAPSHOT_STRUCT_SQL}'

    text = SNAPSHOT_STRUCT_SQL.read_text(encoding='utf-8')
    assert re.search(r'`user_id`\s+bigint', text, re.IGNORECASE), \
        'sql/struct/position_daily_snapshot.sql 缺少 user_id 字段定义'
