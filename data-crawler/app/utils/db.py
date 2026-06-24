#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据库连接管理模块
提供统一的数据库连接池和会话管理
"""

import os
from urllib.parse import quote
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session
from sqlalchemy.pool import QueuePool
from sqlalchemy import event
import logging

# 获取logger
logger = logging.getLogger(__name__)

class DatabaseManager:
    """数据库管理器类"""

    _instance = None
    _engine = None
    _session_factory = None
    _session = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(DatabaseManager, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        if self._engine is None:
            self._init_engine()

    def _init_engine(self):
        """初始化数据库引擎"""
        # 从环境变量获取配置，如果没有则使用默认值
        db_config = {
            'host': os.getenv('MYSQL_HOST', '117.72.53.38'),
            'port': int(os.getenv('MYSQL_PORT', '3306')),
            'user': os.getenv('MYSQL_USER', 'root'),
            'password': os.getenv('MYSQL_PASSWORD', 'wangxuedi3319@'),
            'database': os.getenv('MYSQL_DATABASE', 'personal-finance'),
            'charset': 'utf8mb4',
            'pool_size': int(os.getenv('DB_POOL_SIZE', '20')),
            'max_overflow': int(os.getenv('DB_MAX_OVERFLOW', '30')),
            'pool_recycle': int(os.getenv('DB_POOL_RECYCLE', '3600')),
            'pool_timeout': int(os.getenv('DB_POOL_TIMEOUT', '30')),
        }

        # 构建数据库URL
        encoded_password = quote(db_config['password'], safe='')
        db_url = (
            f"mysql+pymysql://{db_config['user']}:{encoded_password}"
            f"@{db_config['host']}:{db_config['port']}/{db_config['database']}"
            f"?charset={db_config['charset']}"
        )

        logger.info(f"初始化数据库连接: {db_config['host']}:{db_config['port']}")

        # 创建引擎，配置连接池
        self._engine = create_engine(
            db_url,
            poolclass=QueuePool,
            pool_size=db_config['pool_size'],
            max_overflow=db_config['max_overflow'],
            pool_recycle=db_config['pool_recycle'],
            pool_timeout=db_config['pool_timeout'],
            pool_pre_ping=True,  # 连接前检查是否有效
            echo=os.getenv('SQL_ECHO', 'false').lower() == 'true',
            echo_pool=True,
            pool_logging_name='personal_finance_pool'
        )

        # 配置连接池事件监听
        @event.listens_for(self._engine.pool, 'checkout')
        def checkout(dbapi_con, connection_record, connection_proxy):
            # 连接检出时记录
            logger.debug(f"数据库连接被检出: {connection_record.info.get('id', 'unknown')}")

        @event.listens_for(self._engine.pool, 'checkin')
        def checkin(dbapi_con, connection_record):
            # 连接归还时记录
            logger.debug(f"数据库连接已归还: {connection_record.info.get('id', 'unknown')}")

        # 创建会话工厂
        self._session_factory = sessionmaker(
            bind=self._engine,
            autocommit=False,
            autoflush=False,
            expire_on_commit=False
        )

        # 创建线程安全的scoped session
        self._session = scoped_session(self._session_factory)

        logger.info("数据库连接池初始化完成")

    @property
    def engine(self):
        """获取数据库引擎"""
        return self._engine

    @property
    def session(self):
        """获取数据库会话"""
        return self._session

    def get_session(self):
        """获取新的数据库会话"""
        return self._session_factory()

    def close_all(self):
        """关闭所有连接"""
        if self._session:
            self._session.remove()
        if self._engine:
            self._engine.dispose()
            logger.info("数据库连接池已关闭")


# 全局数据库管理器实例
db_manager = DatabaseManager()


# 便捷函数
def get_db_session():
    """获取数据库会话"""
    return db_manager.session


def get_db_engine():
    """获取数据库引擎"""
    return db_manager.engine