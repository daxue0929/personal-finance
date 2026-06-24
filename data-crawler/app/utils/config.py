import os
from urllib.parse import quote


def get_config(key, default=None):
    return os.environ.get(key, default)


DB_CONFIG = {
    'host': get_config('MYSQL_HOST', '117.72.53.38'),
    'port': int(get_config('MYSQL_PORT', '3306')),
    'user': get_config('MYSQL_USER', 'root'),
    'password': get_config('MYSQL_PASSWORD', 'wangxuedi3319@'),
    'database': get_config('MYSQL_DATABASE', 'personal-finance'),
    'charset': 'utf8mb4',
    # 连接池配置
    'pool_size': int(get_config('DB_POOL_SIZE', '20')),
    'max_overflow': int(get_config('DB_MAX_OVERFLOW', '30')),
    'pool_recycle': int(get_config('DB_POOL_RECYCLE', '3600')),
    'pool_timeout': int(get_config('DB_POOL_TIMEOUT', '30')),
}


def get_db_url():
    encoded_password = quote(DB_CONFIG['password'], safe='')
    return (f"mysql+pymysql://{DB_CONFIG['user']}:{encoded_password}"
            f"@{DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['database']}"
            f"?charset={DB_CONFIG['charset']}")


def get_pool_config():
    """获取连接池配置"""
    return {
        'pool_size': DB_CONFIG['pool_size'],
        'max_overflow': DB_CONFIG['max_overflow'],
        'pool_recycle': DB_CONFIG['pool_recycle'],
        'pool_timeout': DB_CONFIG['pool_timeout'],
    }
