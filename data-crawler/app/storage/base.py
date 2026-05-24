#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SQLAlchemy 共享 Base 类
所有数据库模型都应该从这里导入 Base
"""

from sqlalchemy.orm import declarative_base

Base = declarative_base()
