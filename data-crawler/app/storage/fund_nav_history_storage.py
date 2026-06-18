from sqlalchemy import Column, Integer, String, Date, DECIMAL, DateTime, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import QueuePool
from sqlalchemy import event
from datetime import datetime

from ..utils.config import get_db_url

Base = declarative_base()


class FundNavHistory(Base):
    """基金历史净值实体类"""
    __tablename__ = 'fund_nav_history'
    
    id = Column(Integer, primary_key=True, autoincrement=True, comment='主键ID')
    fund_code = Column(String(10), nullable=False, comment='基金代码')
    fund_name = Column(String(64), default='', comment='基金名称')
    nav_date = Column(Date, nullable=False, comment='净值日期')
    unit_nav = Column(DECIMAL(8, 4), comment='单位净值')
    daily_growth_rate = Column(DECIMAL(8, 4), comment='日涨跌幅(%)')
    source = Column(String(20), default='manual', comment='数据来源（manual手动/crawler爬虫/system系统）')
    create_time = Column(DateTime, default=datetime.now, comment='创建时间')


class FundNavHistoryStorage:
    """基金历史净值存储类"""
    
    _engine = None
    _session_factory = None
    
    def __init__(self):
        if FundNavHistoryStorage._engine is None:
            FundNavHistoryStorage._engine = self._get_engine()
        if FundNavHistoryStorage._session_factory is None:
            FundNavHistoryStorage._session_factory = sessionmaker(bind=FundNavHistoryStorage._engine)
        self.Session = FundNavHistoryStorage._session_factory
    
    @classmethod
    def _get_engine(cls):
        if cls._engine is None:
            db_url = get_db_url()
            cls._engine = create_engine(
                db_url,
                poolclass=QueuePool,
                pool_size=5,
                max_overflow=10,
                pool_recycle=3600,
                pool_pre_ping=True,
                echo=False
            )

            @event.listens_for(cls._engine, 'connect')
            def set_timezone_on_connect(dbapi_connection, connection_record):
                cursor = dbapi_connection.cursor()
                cursor.execute("SET time_zone = '+08:00'")
                cursor.execute("SET NAMES utf8mb4")
                cursor.close()

        return cls._engine
    
    def get_session(self):
        """获取数据库会话"""
        return FundNavHistoryStorage._session_factory()
    
    def get_nav_history(self, fund_code=None, start_date=None, end_date=None, page=1, page_size=10):
        """
        获取基金历史净值列表
        :param fund_code: 基金代码（可选）
        :param start_date: 开始日期（可选）
        :param end_date: 结束日期（可选）
        :param page: 页码
        :param page_size: 每页条数
        :return: (数据列表, 总数)
        """
        session = self.get_session()
        try:
            query = session.query(FundNavHistory)
            
            # 添加筛选条件
            if fund_code:
                query = query.filter(FundNavHistory.fund_code == fund_code)
            if start_date:
                query = query.filter(FundNavHistory.nav_date >= start_date)
            if end_date:
                query = query.filter(FundNavHistory.nav_date <= end_date)
            
            # 获取总数
            total = query.count()
            
            # 分页查询，按日期降序排列
            history_list = query.order_by(FundNavHistory.nav_date.desc()) \
                                .offset((page - 1) * page_size) \
                                .limit(page_size) \
                                .all()
            
            result = []
            for item in history_list:
                result.append({
                    'id': item.id,
                    'fund_code': item.fund_code,
                    'fund_name': item.fund_name,
                    'nav_date': str(item.nav_date),
                    'unit_nav': float(item.unit_nav) if item.unit_nav else None,
                    'daily_growth_rate': float(item.daily_growth_rate) if item.daily_growth_rate else None,
                    'source': item.source,
                    'create_time': str(item.create_time) if item.create_time else None
                })
            
            return result, total
        finally:
            session.close()
    
    def get_nav_by_fund_date(self, fund_code, nav_date):
        """
        获取指定基金在指定日期的净值
        :param fund_code: 基金代码
        :param nav_date: 净值日期
        :return: 净值记录或None
        """
        session = self.get_session()
        try:
            item = session.query(FundNavHistory) \
                         .filter(FundNavHistory.fund_code == fund_code,
                                 FundNavHistory.nav_date == nav_date) \
                         .first()
            if item:
                return {
                    'id': item.id,
                    'fund_code': item.fund_code,
                    'fund_name': item.fund_name,
                    'nav_date': str(item.nav_date),
                    'unit_nav': float(item.unit_nav) if item.unit_nav else None,
                    'daily_growth_rate': float(item.daily_growth_rate) if item.daily_growth_rate else None,
                    'source': item.source,
                    'create_time': str(item.create_time) if item.create_time else None
                }
            return None
        finally:
            session.close()
    
    def add_nav_record(self, fund_code, fund_name, nav_date, unit_nav, 
                      daily_growth_rate=None, source='manual'):
        """
        添加基金净值记录
        :param fund_code: 基金代码
        :param fund_name: 基金名称
        :param nav_date: 净值日期
        :param unit_nav: 单位净值
        :param daily_growth_rate: 日涨跌幅（可选）
        :param source: 数据来源
        :return: True/False
        """
        session = self.get_session()
        try:
            # 检查是否已存在
            existing = session.query(FundNavHistory) \
                             .filter(FundNavHistory.fund_code == fund_code,
                                     FundNavHistory.nav_date == nav_date) \
                             .first()
            
            if existing:
                # 更新现有记录
                existing.fund_name = fund_name
                existing.unit_nav = unit_nav
                if daily_growth_rate is not None:
                    existing.daily_growth_rate = daily_growth_rate
                existing.source = source
                existing.create_time = datetime.now()
            else:
                # 创建新记录
                new_record = FundNavHistory(
                    fund_code=fund_code,
                    fund_name=fund_name,
                    nav_date=nav_date,
                    unit_nav=unit_nav,
                    daily_growth_rate=daily_growth_rate,
                    source=source,
                    create_time=datetime.now()
                )
                session.add(new_record)
            
            session.commit()
            return True
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()
    
    def delete_nav_record(self, record_id):
        """
        删除净值记录
        :param record_id: 记录ID
        :return: True/False
        """
        session = self.get_session()
        try:
            record = session.query(FundNavHistory) \
                           .filter(FundNavHistory.id == record_id) \
                           .first()
            if record:
                session.delete(record)
                session.commit()
                return True
            return False
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()
    
    def backup_nav_history(self):
        """
        调用存储过程备份基金净值历史数据
        :return: 插入的记录数
        """
        session = self.get_session()
        try:
            result = session.execute(text("CALL backup_fund_nav_history()"))
            session.commit()
            # 获取存储过程返回的结果
            for row in result:
                return row[0] if row else 0
            return 0
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()
