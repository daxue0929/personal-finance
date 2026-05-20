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
    'charset': 'utf8mb4'
}


def get_db_url():
    encoded_password = quote(DB_CONFIG['password'], safe='')
    return (f"mysql+pymysql://{DB_CONFIG['user']}:{encoded_password}"
            f"@{DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['database']}"
            f"?charset={DB_CONFIG['charset']}")
