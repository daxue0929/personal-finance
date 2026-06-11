import flask
from flask import Flask, jsonify, request
import threading
from datetime import datetime as dt
import time
import functools
from sqlalchemy import text

from ..utils.logger import logger
from ..storage import TaskScheduleStorage, FundInfoStorage, FundBuyerStorage
from ..utils.datetime_utils import get_beijing_now

app = Flask(__name__)
scheduler_instance = None
_task_storage = TaskScheduleStorage()
_fund_storage = FundInfoStorage()
_buyer_storage = FundBuyerStorage()


def set_scheduler(scheduler):
    global scheduler_instance
    scheduler_instance = scheduler


def log_request(func):
    """API请求日志记录装饰器（带TraceID追踪）"""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        method = request.method
        path = request.path
        query_params = request.args.to_dict()
        body = request.get_json(silent=True) if request.data else None
        
        # 获取或生成TraceID
        trace_id = request.headers.get('X-Trace-ID', generate_trace_id())
        
        # 将TraceID存入请求上下文，方便后续使用
        request.trace_id = trace_id
        
        # 记录客户端信息
        client_ip = request.remote_addr
        user_agent = request.headers.get('User-Agent', '')[:100]
        
        logger.info(f"【请求开始】[TraceID:{trace_id}] {method} {path} | IP: {client_ip} | 参数: {query_params} | 体: {body}")
        
        try:
            response = func(*args, **kwargs)
            status_code = response[1] if isinstance(response, tuple) else 200
            elapsed_time = (time.time() - start_time) * 1000
            
            # 将TraceID添加到响应头
            if isinstance(response, tuple):
                response_data, status = response
                if isinstance(response_data, flask.Response):
                    response_data.headers['X-Trace-ID'] = trace_id
                else:
                    # 创建新的响应对象
                    response_data = flask.jsonify(response_data)
                    response_data.headers['X-Trace-ID'] = trace_id
                    response = (response_data, status)
            else:
                if isinstance(response, flask.Response):
                    response.headers['X-Trace-ID'] = trace_id
                else:
                    response = flask.jsonify(response)
                    response.headers['X-Trace-ID'] = trace_id
            
            logger.info(f"【请求完成】[TraceID:{trace_id}] {method} {path} | 状态码: {status_code} | 耗时: {elapsed_time:.2f}ms")
            return response
        except Exception as e:
            elapsed_time = (time.time() - start_time) * 1000
            logger.error(f"【请求失败】[TraceID:{trace_id}] {method} {path} | 错误: {str(e)} | 耗时: {elapsed_time:.2f}ms")
            raise
    return wrapper


def generate_trace_id():
    """生成唯一的TraceID"""
    import uuid
    return str(uuid.uuid4())[:8] + '-' + str(int(time.time() * 1000))[-8:]


@app.route('/api/crawl', methods=['POST'])
@log_request
def trigger_crawl():
    """触发基金净值爬取任务"""
    return run_task('update_fund_net_values_task')


@app.route('/api/task/run/<task_func>', methods=['POST'])
@log_request
def run_task(task_func):
    """立即执行指定任务"""
    try:
        force_run = request.json.get('force_run', False) if request.json else False

        if scheduler_instance:
            success = scheduler_instance.run_job_now(task_func, force_run=force_run)
            if success:
                return jsonify({
                    'success': True,
                    'message': f'任务 {task_func} 已触发' + (' (force_run)' if force_run else '')
                }), 200
            else:
                return jsonify({
                    'success': False,
                    'message': f'任务 {task_func} 未注册'
                }), 404
        else:
            return jsonify({
                'success': False,
                'message': '调度器未启动'
            }), 503
    except Exception as e:
        logger.error(f"触发任务失败: {e}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


@app.route('/api/status', methods=['GET'])
@log_request
def get_status():
    """获取调度器状态"""
    status = {
        'running': False,
        'message': '调度器未启动',
        'jobs': []
    }
    if scheduler_instance:
        status['running'] = scheduler_instance._running
        status['message'] = '调度器运行中' if scheduler_instance._running else '调度器已停止'
        status['jobs'] = scheduler_instance.get_all_jobs()
    return jsonify(status), 200


@app.route('/api/tasks', methods=['GET'])
@log_request
def get_tasks():
    """获取任务配置列表（支持搜索和分页）"""
    try:
        from ..storage.task_schedule_storage import TaskSchedule
        
        # 获取分页参数
        page = int(request.args.get('page', 1))
        page_size = int(request.args.get('page_size', 10))
        
        # 获取搜索参数
        task_name = request.args.get('task_name', '')
        task_func = request.args.get('task_func', '')
        enabled = request.args.get('enabled', '')
        
        # 获取session
        session = _task_storage.get_session()
        
        try:
            # 构建查询
            query = session.query(TaskSchedule).filter(TaskSchedule.del_flag == '1')
            
            # 添加搜索条件
            if task_name:
                query = query.filter(TaskSchedule.task_name.like(f'%{task_name}%'))
            if task_func:
                query = query.filter(TaskSchedule.task_func.like(f'%{task_func}%'))
            if enabled != '':
                query = query.filter(TaskSchedule.enabled == (1 if enabled == 'true' else 0))
            
            # 获取总数
            total = query.count()
            
            # 分页查询
            tasks = query.offset((page - 1) * page_size).limit(page_size).all()
            
            result = []
            for task in tasks:
                job_status = scheduler_instance.get_job_status(task.task_func) if scheduler_instance else None
                result.append({
                    'id': task.id,
                    'task_name': task.task_name,
                    'task_func': task.task_func,
                    'cron_expression': task.cron_expression,
                    'enabled': task.enabled == 1,
                    'description': task.description,
                    'next_run_time': job_status['next_run_time'] if job_status else None,
                    'create_time': str(task.create_time),
                    'update_time': str(task.update_time)
                })
            
            return jsonify({
                'data': result,
                'total': total,
                'page': page,
                'page_size': page_size
            }), 200
        finally:
            session.close()
    except Exception as e:
        logger.error(f"获取任务配置失败: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/tasks/<int:task_id>', methods=['GET'])
@log_request
def get_task(task_id):
    """获取单个任务配置"""
    try:
        task = _task_storage.get_task_by_id(task_id)
        if task:
            job_status = scheduler_instance.get_job_status(task.task_func) if scheduler_instance else None
            result = {
                'id': task.id,
                'task_name': task.task_name,
                'task_func': task.task_func,
                'cron_expression': task.cron_expression,
                'enabled': task.enabled == 1,
                'description': task.description,
                'next_run_time': job_status['next_run_time'] if job_status else None,
                'create_time': str(task.create_time),
                'update_time': str(task.update_time)
            }
            return jsonify(result), 200
        else:
            return jsonify({'error': '任务不存在'}), 404
    except Exception as e:
        logger.error(f"获取任务失败: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/tasks', methods=['POST'])
@log_request
def create_task():
    """创建任务配置"""
    try:
        data = request.json
        required_fields = ['task_name', 'task_func', 'cron_expression']
        for field in required_fields:
            if field not in data:
                return jsonify({'error': f'缺少必填字段: {field}'}), 400

        if _task_storage.task_exists(data['task_func']):
            return jsonify({'error': '任务函数已存在'}), 409

        new_task = _task_storage.create_task(
            task_name=data['task_name'],
            task_func=data['task_func'],
            cron_expression=data['cron_expression'],
            enabled=data.get('enabled', 1),
            description=data.get('description'),
            create_by='api'
        )

        if new_task:
            return jsonify({
                'success': True,
                'message': '任务创建成功',
                'task_id': new_task.id
            }), 201
        else:
            return jsonify({'error': '任务创建失败'}), 500
    except Exception as e:
        logger.error(f"创建任务失败: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/tasks/<int:task_id>', methods=['PUT'])
@log_request
def update_task(task_id):
    """更新任务配置"""
    try:
        data = request.json
        if not _task_storage.get_task_by_id(task_id):
            return jsonify({'error': '任务不存在'}), 404

        update_fields = {}
        if 'task_name' in data:
            update_fields['task_name'] = data['task_name']
        if 'cron_expression' in data:
            update_fields['cron_expression'] = data['cron_expression']
        if 'enabled' in data:
            update_fields['enabled'] = 1 if data['enabled'] else 0
        if 'description' in data:
            update_fields['description'] = data['description']
        update_fields['update_by'] = 'api'

        if _task_storage.update_task(task_id, **update_fields):
            return jsonify({
                'success': True,
                'message': '任务更新成功'
            }), 200
        else:
            return jsonify({'error': '任务更新失败'}), 500
    except Exception as e:
        logger.error(f"更新任务失败: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/tasks/<int:task_id>', methods=['DELETE'])
@log_request
def delete_task(task_id):
    """删除任务配置"""
    try:
        if not _task_storage.get_task_by_id(task_id):
            return jsonify({'error': '任务不存在'}), 404

        if _task_storage.delete_task(task_id, update_by='api'):
            return jsonify({
                'success': True,
                'message': '任务删除成功'
            }), 200
        else:
            return jsonify({'error': '任务删除失败'}), 500
    except Exception as e:
        logger.error(f"删除任务失败: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/start', methods=['POST'])
@log_request
def start_scheduler():
    """启动调度器"""
    try:
        if scheduler_instance:
            scheduler_instance.start()
            return jsonify({
                'success': True,
                'message': '调度器已启动'
            }), 200
        else:
            return jsonify({
                'success': False,
                'message': '调度器未初始化'
            }), 500
    except Exception as e:
        logger.error(f"启动调度器失败: {e}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


@app.route('/api/stop', methods=['POST'])
@log_request
def stop_scheduler():
    """停止调度器"""
    try:
        if scheduler_instance:
            scheduler_instance.stop()
            return jsonify({
                'success': True,
                'message': '调度器已停止'
            }), 200
        else:
            return jsonify({
                'success': False,
                'message': '调度器未初始化'
            }), 500
    except Exception as e:
        logger.error(f"停止调度器失败: {e}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


@app.route('/health', methods=['GET'])
@log_request
def health_check():
    """健康检查"""
    return jsonify({'status': 'ok2', 'service': 'fund-crawler'}), 200


# ==================== 基金管理API ====================

@app.route('/api/funds', methods=['GET'])
@log_request
def get_funds():
    """获取基金信息列表（支持搜索和分页）"""
    try:
        from ..storage.fund_info_storage import FundInfo
        from sqlalchemy import or_
        
        # 获取分页参数
        page = int(request.args.get('page', 1))
        page_size = int(request.args.get('page_size', 10))
        
        # 获取搜索参数
        fund_code = request.args.get('fund_code', '')
        fund_name = request.args.get('fund_name', '')
        fund_type = request.args.get('fund_type', '')
        
        # 创建新的session
        session = _fund_storage.Session()
        
        try:
            # 构建查询
            query = session.query(FundInfo).filter(FundInfo.del_flag == '1')
            
            # 添加搜索条件
            if fund_code:
                query = query.filter(FundInfo.fund_code.like(f'%{fund_code}%'))
            if fund_name:
                query = query.filter(FundInfo.fund_name.like(f'%{fund_name}%'))
            if fund_type:
                query = query.filter(FundInfo.fund_type == fund_type)
            
            # 获取总数
            total = query.count()
            
            # 分页查询
            funds = query.offset((page - 1) * page_size).limit(page_size).all()
            
            result = []
            for fund in funds:
                result.append({
                    'fund_id': fund.fund_id,
                    'fund_code': fund.fund_code,
                    'fund_name': fund.fund_name,
                    'fund_type': fund.fund_type,
                    'net_asset_value': float(fund.net_asset_value) if fund.net_asset_value else 0.0,
                    'net_value_date': str(fund.net_value_date) if fund.net_value_date else None,
                    'fund_manager': fund.fund_manager,
                    'establish_date': str(fund.establish_date) if fund.establish_date else None,
                    'fund_size': float(fund.fund_size) if fund.fund_size else 0.0,
                    'remark': fund.remark,
                    'create_time': str(fund.create_time) if fund.create_time else None,
                    'update_time': str(fund.update_time) if fund.update_time else None
                })
            
            return jsonify({
                'data': result,
                'total': total,
                'page': page,
                'page_size': page_size
            }), 200
        finally:
            session.close()
    except Exception as e:
        logger.error(f"获取基金列表失败: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/funds/<int:fund_id>', methods=['GET'])
@log_request
def get_fund(fund_id):
    """获取单个基金信息"""
    try:
        from ..storage.fund_info_storage import FundInfo
        
        # 创建新的session
        session = _fund_storage.Session()
        
        try:
            fund = session.query(FundInfo).filter(
                FundInfo.fund_id == fund_id,
                FundInfo.del_flag == '1'
            ).first()
            
            if fund:
                result = {
                    'fund_id': fund.fund_id,
                    'fund_code': fund.fund_code,
                    'fund_name': fund.fund_name,
                    'fund_type': fund.fund_type,
                    'net_asset_value': float(fund.net_asset_value) if fund.net_asset_value else 0.0,
                    'net_value_date': str(fund.net_value_date) if fund.net_value_date else None,
                    'fund_manager': fund.fund_manager,
                    'establish_date': str(fund.establish_date) if fund.establish_date else None,
                    'fund_size': float(fund.fund_size) if fund.fund_size else 0.0,
                    'remark': fund.remark,
                    'create_time': str(fund.create_time) if fund.create_time else None,
                    'update_time': str(fund.update_time) if fund.update_time else None
                }
                return jsonify(result), 200
            else:
                return jsonify({'error': '基金不存在'}), 404
        finally:
            session.close()
    except Exception as e:
        logger.error(f"获取基金失败: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/funds', methods=['POST'])
@log_request
def create_fund():
    """创建基金信息"""
    try:
        from ..storage.fund_info_storage import FundInfo
        data = request.json
        required_fields = ['fund_code', 'fund_name']
        for field in required_fields:
            if field not in data:
                return jsonify({'error': f'缺少必填字段: {field}'}), 400
        
        # 创建新的session
        session = _fund_storage.Session()
        
        try:
            # 检查基金代码是否已存在
            existing = session.query(FundInfo).filter(
                FundInfo.fund_code == data['fund_code'],
                FundInfo.del_flag == '1'
            ).first()
            
            if existing:
                return jsonify({'error': '基金代码已存在'}), 409
            
            new_fund = FundInfo(
                fund_code=data['fund_code'],
                fund_name=data['fund_name'],
                fund_type=data.get('fund_type', '混合型'),
                net_asset_value=data.get('net_asset_value', 0.0),
                net_value_date=dt.strptime(data.get('net_value_date'), '%Y-%m-%d').date() if data.get('net_value_date') else None,
                fund_manager=data.get('fund_manager', ''),
                establish_date=dt.strptime(data.get('establish_date'), '%Y-%m-%d').date() if data.get('establish_date') else None,
                fund_size=data.get('fund_size', 0.0),
                remark=data.get('remark', ''),
                del_flag='1',
                create_by='api',
                create_time=get_beijing_now(),
                update_by='api',
                update_time=get_beijing_now()
            )
            
            session.add(new_fund)
            session.commit()
            session.refresh(new_fund)
            
            return jsonify({
                'success': True,
                'message': '基金创建成功',
                'fund_id': new_fund.fund_id
            }), 201
        except Exception as e:
            session.rollback()
            logger.error(f"创建基金失败: {e}")
            return jsonify({'error': str(e)}), 500
        finally:
            session.close()
    except Exception as e:
        logger.error(f"创建基金失败: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/funds/<int:fund_id>', methods=['PUT'])
@log_request
def update_fund(fund_id):
    """更新基金信息"""
    try:
        from ..storage.fund_info_storage import FundInfo
        data = request.json
        
        # 创建新的session
        session = _fund_storage.Session()
        
        try:
            fund = session.query(FundInfo).filter(
                FundInfo.fund_id == fund_id,
                FundInfo.del_flag == '1'
            ).first()
            
            if not fund:
                return jsonify({'error': '基金不存在'}), 404
            
            # 更新字段
            if 'fund_name' in data:
                fund.fund_name = data['fund_name']
            if 'fund_type' in data:
                fund.fund_type = data['fund_type']
            if 'net_asset_value' in data:
                fund.net_asset_value = data['net_asset_value']
            if 'net_value_date' in data:
                fund.net_value_date = dt.strptime(data['net_value_date'], '%Y-%m-%d').date()
            if 'fund_manager' in data:
                fund.fund_manager = data['fund_manager']
            if 'establish_date' in data:
                fund.establish_date = dt.strptime(data['establish_date'], '%Y-%m-%d').date()
            if 'fund_size' in data:
                fund.fund_size = data['fund_size']
            if 'remark' in data:
                fund.remark = data['remark']
            
            fund.update_by = 'api'
            fund.update_time = get_beijing_now()
            
            session.commit()
            
            return jsonify({
                'success': True,
                'message': '基金更新成功'
            }), 200
        except Exception as e:
            session.rollback()
            logger.error(f"更新基金失败: {e}")
            return jsonify({'error': str(e)}), 500
        finally:
            session.close()
    except Exception as e:
        logger.error(f"更新基金失败: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/funds/<int:fund_id>', methods=['DELETE'])
@log_request
def delete_fund(fund_id):
    """删除基金信息"""
    try:
        from ..storage.fund_info_storage import FundInfo
        
        # 创建新的session
        session = _fund_storage.Session()
        
        try:
            fund = session.query(FundInfo).filter(
                FundInfo.fund_id == fund_id,
                FundInfo.del_flag == '1'
            ).first()
            
            if not fund:
                return jsonify({'error': '基金不存在'}), 404
            
            fund.del_flag = '0'
            fund.update_by = 'api'
            fund.update_time = get_beijing_now()
            
            session.commit()
            
            return jsonify({
                'success': True,
                'message': '基金删除成功'
            }), 200
        except Exception as e:
            session.rollback()
            logger.error(f"删除基金失败: {e}")
            return jsonify({'error': str(e)}), 500
        finally:
            session.close()
    except Exception as e:
        logger.error(f"删除基金失败: {e}")
        return jsonify({'error': str(e)}), 500


# ==================== 基金买入流水API ====================

@app.route('/api/buyers', methods=['GET'])
@log_request
def get_buyers():
    """获取买入记录列表（支持搜索和分页）"""
    try:
        from ..storage.fund_buyer_storage import FundBuyer
        
        # 获取分页参数
        page = int(request.args.get('page', 1))
        page_size = int(request.args.get('page_size', 10))
        
        # 获取搜索参数
        fund_code = request.args.get('fund_code', '')
        fund_name = request.args.get('fund_name', '')
        buy_type = request.args.get('type', '')
        buy_status = request.args.get('buy_status', '')
        start_time = request.args.get('start_time', '')
        end_time = request.args.get('end_time', '')
        
        # 获取排序参数
        sort_field = request.args.get('sort_field', '')
        sort_order = request.args.get('sort_order', '')
        
        # 创建新的session
        session = _buyer_storage.Session()
        
        try:
            # 构建查询
            query = session.query(FundBuyer).filter(FundBuyer.del_flag == '1')
            
            # 添加搜索条件
            if fund_code:
                query = query.filter(FundBuyer.fund_code.like(f'%{fund_code}%'))
            if fund_name:
                query = query.filter(FundBuyer.fund_name.like(f'%{fund_name}%'))
            if buy_type:
                query = query.filter(FundBuyer.type == buy_type)
            if buy_status:
                query = query.filter(FundBuyer.buy_status == buy_status)
            if start_time:
                query = query.filter(FundBuyer.time >= start_time)
            if end_time:
                query = query.filter(FundBuyer.time <= end_time)
            
            # 添加排序
            if sort_field and sort_order:
                field_map = {
                    'id': FundBuyer.id,
                    'fund_code': FundBuyer.fund_code,
                    'fund_name': FundBuyer.fund_name,
                    'time': FundBuyer.time,
                    'amt': FundBuyer.amt,
                    'type': FundBuyer.type,
                    'buy_status': FundBuyer.buy_status,
                    'policy': FundBuyer.policy,
                    'remark': FundBuyer.remark
                }
                if sort_field in field_map:
                    if sort_order == 'asc':
                        query = query.order_by(field_map[sort_field].asc())
                    else:
                        query = query.order_by(field_map[sort_field].desc())
            else:
                # 默认按时间降序排列
                query = query.order_by(FundBuyer.time.desc())
            
            # 获取总数
            total = query.count()
            
            # 分页查询
            buyers = query.offset((page - 1) * page_size).limit(page_size).all()
            
            result = []
            for buyer in buyers:
                result.append({
                    'id': buyer.id,
                    'fund_code': buyer.fund_code,
                    'fund_name': buyer.fund_name,
                    'time': str(buyer.time),
                    'amt': float(buyer.amt) if buyer.amt else 0.0,
                    'type': buyer.type,
                    'policy': buyer.policy,
                    'buy_status': buyer.buy_status,
                    'remark': buyer.remark,
                    'create_time': str(buyer.create_time) if buyer.create_time else None,
                    'update_time': str(buyer.update_time) if buyer.update_time else None
                })
            
            return jsonify({
                'data': result,
                'total': total,
                'page': page,
                'page_size': page_size
            }), 200
        finally:
            session.close()
    except Exception as e:
        logger.error(f"获取买入记录失败: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/buyers/<int:buyer_id>', methods=['GET'])
@log_request
def get_buyer(buyer_id):
    """获取单个买入记录"""
    try:
        from ..storage.fund_buyer_storage import FundBuyer
        
        # 创建新的session
        session = _buyer_storage.Session()
        
        try:
            buyer = session.query(FundBuyer).filter(
                FundBuyer.id == buyer_id,
                FundBuyer.del_flag == '1'
            ).first()
            
            if buyer:
                result = {
                    'id': buyer.id,
                    'fund_code': buyer.fund_code,
                    'fund_name': buyer.fund_name,
                    'time': str(buyer.time),
                    'amt': float(buyer.amt) if buyer.amt else 0.0,
                    'type': buyer.type,
                    'policy': buyer.policy,
                    'buy_status': buyer.buy_status,
                    'remark': buyer.remark,
                    'create_time': str(buyer.create_time) if buyer.create_time else None,
                    'update_time': str(buyer.update_time) if buyer.update_time else None
                }
                return jsonify(result), 200
            else:
                return jsonify({'error': '买入记录不存在'}), 404
        finally:
            session.close()
    except Exception as e:
        logger.error(f"获取买入记录失败: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/buyers', methods=['POST'])
@log_request
def create_buyer():
    """创建买入记录"""
    try:
        from ..storage.fund_buyer_storage import FundBuyer
        data = request.json
        required_fields = ['fund_code', 'time', 'amt']
        for field in required_fields:
            if field not in data:
                return jsonify({'error': f'缺少必填字段: {field}'}), 400
        
        # 数据类型验证
        try:
            amt = float(data['amt'])
            if amt <= 0:
                return jsonify({'error': '买入金额必须大于0'}), 400
        except (ValueError, TypeError):
            return jsonify({'error': '买入金额必须是有效的数字'}), 400
        
        # 创建新的session
        session = _buyer_storage.Session()
        
        try:
            new_buyer = FundBuyer(
                fund_code=data['fund_code'],
                fund_name=data.get('fund_name', ''),
                time=dt.strptime(data['time'], '%Y-%m-%d').date(),
                amt=amt,
                type=data.get('type', ''),
                policy=data.get('policy', ''),
                buy_status=data.get('buy_status', 'PENDING'),
                remark=data.get('remark', ''),
                del_flag='1',
                create_by='api',
                create_time=get_beijing_now(),
                update_by='api',
                update_time=get_beijing_now()
            )
            
            session.add(new_buyer)
            session.commit()
            session.refresh(new_buyer)
            
            return jsonify({
                'success': True,
                'message': '买入记录创建成功',
                'id': new_buyer.id
            }), 201
        except Exception as e:
            session.rollback()
            logger.error(f"创建买入记录失败: {e}")
            return jsonify({'error': str(e)}), 500
        finally:
            session.close()
    except Exception as e:
        logger.error(f"创建买入记录失败: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/buyers/<int:buyer_id>', methods=['PUT'])
@log_request
def update_buyer(buyer_id):
    """更新买入记录"""
    try:
        from ..storage.fund_buyer_storage import FundBuyer
        data = request.json
        
        # 创建新的session
        session = _buyer_storage.Session()
        
        try:
            buyer = session.query(FundBuyer).filter(
                FundBuyer.id == buyer_id,
                FundBuyer.del_flag == '1'
            ).first()
            
            if not buyer:
                return jsonify({'error': '买入记录不存在'}), 404
            
            if 'fund_code' in data:
                buyer.fund_code = data['fund_code']
            if 'fund_name' in data:
                buyer.fund_name = data['fund_name']
            if 'time' in data:
                buyer.time = dt.strptime(data['time'], '%Y-%m-%d').date()
            if 'amt' in data:
                buyer.amt = data['amt']
            if 'type' in data:
                buyer.type = data['type']
            if 'policy' in data:
                buyer.policy = data['policy']
            if 'buy_status' in data:
                buyer.buy_status = data['buy_status']
            if 'remark' in data:
                buyer.remark = data['remark']
            
            buyer.update_by = 'api'
            buyer.update_time = get_beijing_now()
            
            session.commit()
            
            return jsonify({
                'success': True,
                'message': '买入记录更新成功'
            }), 200
        except Exception as e:
            session.rollback()
            logger.error(f"更新买入记录失败: {e}")
            return jsonify({'error': str(e)}), 500
        finally:
            session.close()
    except Exception as e:
        logger.error(f"更新买入记录失败: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/buyers/<int:buyer_id>', methods=['DELETE'])
@log_request
def delete_buyer(buyer_id):
    """删除买入记录"""
    try:
        from ..storage.fund_buyer_storage import FundBuyer
        
        # 创建新的session
        session = _buyer_storage.Session()
        
        try:
            buyer = session.query(FundBuyer).filter(
                FundBuyer.id == buyer_id,
                FundBuyer.del_flag == '1'
            ).first()
            
            if not buyer:
                return jsonify({'error': '买入记录不存在'}), 404
            
            buyer.del_flag = '0'
            buyer.update_by = 'api'
            buyer.update_time = get_beijing_now()
            
            session.commit()
            
            return jsonify({
                'success': True,
                'message': '买入记录删除成功'
            }), 200
        except Exception as e:
            session.rollback()
            logger.error(f"删除买入记录失败: {e}")
            return jsonify({'error': str(e)}), 500
        finally:
            session.close()
    except Exception as e:
        logger.error(f"删除买入记录失败: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/buyers/quick-buy', methods=['POST'])
@log_request
def quick_buy():
    """快捷买入 - 调用存储过程"""
    try:
        data = request.get_json()
        fund_code = data.get('fund_code', '020292')
        change_pct = data.get('change_pct')
        
        if not change_pct:
            return jsonify({'error': '涨跌幅不能为空'}), 400
        
        # 创建新的session
        session = _buyer_storage.Session()
        
        try:
            # 调用存储过程
            result = session.execute(
                text("CALL sp_insert_fund_buyer_by_change(:fund_code, :change_pct)"),
                {'fund_code': fund_code, 'change_pct': change_pct}
            )
            session.commit()
            
            return jsonify({
                'success': True,
                'message': f'快捷买入成功，基金代码: {fund_code}，涨跌幅: {change_pct}%'
            }), 200
        except Exception as e:
            session.rollback()
            logger.error(f"快捷买入失败: {e}")
            return jsonify({'error': str(e)}), 500
        finally:
            session.close()
    except Exception as e:
        logger.error(f"快捷买入失败: {e}")
        return jsonify({'error': str(e)}), 500


def create_app():
    return app


def start_server(host='0.0.0.0', port=5000, debug=False):
    """启动 Web 服务器"""
    logger.info(f"Web 服务启动，监听 {host}:{port}, debug: {debug}")
    app.run(host=host, port=port, threaded=True, debug=debug, use_reloader=False)


def start_server_in_background(host='0.0.0.0', port=5000, debug=False):
    """在后台线程启动 Web 服务器"""
    thread = threading.Thread(target=start_server, args=(host, port, debug), daemon=True)
    thread.start()
    logger.info(f"Web 服务已在后台启动，监听 {host}:{port}, debug: {debug}")
    return thread
