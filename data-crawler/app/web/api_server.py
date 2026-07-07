import flask
from flask import Flask, jsonify, request
import threading
import traceback
from datetime import datetime as dt
import time
import functools
from sqlalchemy import text

from ..utils.logger import logger, trace_id_var, request_method_var, request_path_var, request_ip_var, category_var
from ..storage import TaskScheduleStorage, FundInfoStorage, FundBuyerStorage, FundNavHistoryStorage, PortfolioStorage, PositionStorage, PortfolioPositionStorage, PortfolioPosition
from ..utils.datetime_utils import get_beijing_now
from . import scheduler_proxy

app = Flask(__name__)
_task_storage = TaskScheduleStorage()
_fund_storage = FundInfoStorage()
_buyer_storage = FundBuyerStorage()
_nav_storage = FundNavHistoryStorage()
_portfolio_storage = PortfolioStorage()
_position_storage = PositionStorage()
_portfolio_position_storage = PortfolioPositionStorage()
_log_storage = None


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
        
        # 使用ContextVar设置上下文信息（保存token以便后续清理）
        tokens = []
        try:
            tokens.append(trace_id_var.set(trace_id))
            tokens.append(request_method_var.set(method))
            tokens.append(request_path_var.set(path))
            tokens.append(request_ip_var.set(client_ip))
            tokens.append(category_var.set('api'))
            
            logger.info(
                f"【请求开始】[TraceID:{trace_id}] {method} {path} | IP: {client_ip} | 请求参数: {query_params} | 请求体: {body}"
            )
            
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
                
                logger.info(
                    f"【请求完成】[TraceID:{trace_id}] {method} {path} | 状态码: {status_code} | 耗时: {elapsed_time:.2f}ms"
                )
                return response
            except Exception as e:
                elapsed_time = (time.time() - start_time) * 1000
                logger.error(
                    f"【请求失败】[TraceID:{trace_id}] {method} {path} | 错误: {str(e)} | 耗时: {elapsed_time:.2f}ms",
                    exc_info=True
                )
                raise
        finally:
            # 清理ContextVar上下文
            for token in reversed(tokens):
                try:
                    token.var.reset(token)
                except Exception:
                    pass
    return wrapper


def generate_trace_id():
    """生成唯一的TraceID"""
    import uuid
    # 使用完整UUID确保唯一性
    return str(uuid.uuid4())


@app.route('/api/crawl', methods=['POST'])
@log_request
def trigger_crawl():
    """触发基金净值爬取任务（转发到调度器进程）"""
    data, code = scheduler_proxy.run_task('update_fund_net_values_task')
    return jsonify(data), code


@app.route('/api/task/run/<task_func>', methods=['POST'])
@log_request
def run_task(task_func):
    """立即执行指定任务（转发到调度器进程）"""
    try:
        force_run = False
        try:
            if request.json:
                force_run = request.json.get('force_run', False)
        except Exception:
            pass

        data, code = scheduler_proxy.run_task(task_func, force_run=force_run)
        return jsonify(data), code
    except Exception as e:
        logger.error(f"触发任务失败: {e}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


@app.route('/api/status', methods=['GET'])
@log_request
def get_status():
    """获取调度器状态（转发到调度器进程）"""
    data, code = scheduler_proxy.get_status()
    return jsonify(data), code


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

            # 一次性从调度器进程获取所有任务状态（避免 N+1 HTTP 调用）
            all_jobs = scheduler_proxy.get_all_jobs() or {}

            result = []
            for task in tasks:
                job_status = all_jobs.get(task.task_func)
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
            job_status = scheduler_proxy.get_job_status(task.task_func)
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
    """启动调度器（转发到调度器进程）"""
    try:
        data, code = scheduler_proxy.start_scheduler()
        return jsonify(data), code
    except Exception as e:
        logger.error(f"启动调度器失败: {e}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


@app.route('/api/stop', methods=['POST'])
@log_request
def stop_scheduler():
    """停止调度器（转发到调度器进程）"""
    try:
        data, code = scheduler_proxy.stop_scheduler()
        return jsonify(data), code
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
        # 获取分页参数
        page = int(request.args.get('page', 1))
        page_size = int(request.args.get('page_size', 10))
        
        # 获取搜索参数
        fund_code = request.args.get('fund_code', '')
        fund_name = request.args.get('fund_name', '')
        fund_type = request.args.get('fund_type', '')
        
        # 使用存储类方法获取数据（确保使用pool_pre_ping配置）
        funds, total = _fund_storage.get_funds_with_pagination(
            fund_code=fund_code if fund_code else None,
            fund_name=fund_name if fund_name else None,
            fund_type=fund_type if fund_type else None,
            page=page,
            page_size=page_size
        )
        
        return jsonify({
            'data': funds,
            'total': total,
            'page': page,
            'page_size': page_size
        }), 200
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
        
        # 使用存储类方法获取数据（确保使用pool_pre_ping配置）
        buyers, total = _buyer_storage.get_buyers_with_pagination(
            fund_code=fund_code if fund_code else None,
            fund_name=fund_name if fund_name else None,
            buy_type=buy_type if buy_type else None,
            buy_status=buy_status if buy_status else None,
            start_time=start_time if start_time else None,
            end_time=end_time if end_time else None,
            sort_field=sort_field if sort_field else None,
            sort_order=sort_order if sort_order else None,
            page=page,
            page_size=page_size
        )
        
        return jsonify({
            'data': buyers,
            'total': total,
            'page': page,
            'page_size': page_size
        }), 200
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
    """快捷买入 - 根据策略执行买入"""
    try:
        data = request.get_json()
        fund_code = data.get('fund_code', '020292')
        change_pct = data.get('change_pct')
        policy = data.get('policy', 'change_pct_strategy')
        
        # 创建新的session
        session = _buyer_storage.Session()
        
        try:
            if policy == 'change_pct_strategy':
                # 涨跌幅策略 - 调用存储过程
                if not change_pct:
                    return jsonify({'error': '涨跌幅策略需要传入涨跌幅参数'}), 400
                    
                result = session.execute(
                    text("CALL sp_insert_fund_buyer_by_change(:fund_code, :change_pct)"),
                    {'fund_code': fund_code, 'change_pct': change_pct}
                )
                session.commit()
                
                return jsonify({
                    'success': True,
                    'message': f'快捷买入成功（涨跌幅策略），基金代码: {fund_code}，涨跌幅: {change_pct}%'
                }), 200
            elif policy == 'fixed_strategy':
                # 固定策略 - 固定金额买入（预留）
                return jsonify({
                    'success': False,
                    'message': '固定策略尚未实现'
                }), 501
            else:
                return jsonify({'error': f'未知策略: {policy}'}), 400
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



# ==================== 基金历史净值API ====================

@app.route('/api/funds/history', methods=['GET'])
@log_request
def get_fund_nav_history():
    """获取基金历史净值列表（支持日期范围筛选和分页）"""
    fund_code = request.args.get('fund_code', '')
    try:
        # 获取分页参数
        page = int(request.args.get('page', 1))
        page_size = int(request.args.get('page_size', 10))

        # 获取日期范围参数
        start_date = request.args.get('start_date', '')
        end_date = request.args.get('end_date', '')

        # 使用存储类方法获取数据（确保使用pool_pre_ping配置）
        history_list, total = _nav_storage.get_nav_history(
            fund_code=fund_code if fund_code else None,
            start_date=start_date if start_date else None,
            end_date=end_date if end_date else None,
            page=page,
            page_size=page_size
        )

        return jsonify({
            'data': history_list,
            'total': total,
            'page': page,
            'page_size': page_size
        }), 200
    except Exception as e:
        logger.error(f"获取基金历史净值失败: {e}")
        return jsonify({'error': str(e)}), 500


# ==================== 持仓组合接口 ====================

@app.route('/api/portfolios', methods=['GET'])
@log_request
def get_portfolios():
    """获取持仓组合列表（不包含持仓详情）"""
    try:
        name = request.args.get('name', '')
        page = int(request.args.get('page', 1))
        page_size = int(request.args.get('page_size', 10))
        
        portfolios, total = _portfolio_storage.get_portfolios_with_pagination(
            name=name,
            page=page,
            page_size=page_size
        )
        
        return jsonify({
            'data': portfolios,
            'total': total,
            'page': page,
            'page_size': page_size
        })
    except Exception as e:
        logger.error(f"获取持仓组合列表失败: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/portfolios/<int:portfolio_id>/positions', methods=['GET'])
@log_request
def get_portfolio_positions(portfolio_id):
    """获取指定组合的持仓列表"""
    try:
        # 先验证组合是否存在
        portfolio = _portfolio_storage.get_portfolio_by_id(portfolio_id)
        if not portfolio:
            return jsonify({'error': '持仓组合不存在'}), 404

        # 使用优化后的查询方法，避免N+1查询问题
        from ..storage.position_storage import Position

        session = _portfolio_position_storage.get_session()
        try:
            # 使用JOIN查询一次获取所有关联数据
            query = session.query(
                Position
            ).join(
                PortfolioPosition,
                PortfolioPosition.position_id == Position.id,
                isouter=True
            ).filter(
                PortfolioPosition.portfolio_id == portfolio_id,
                PortfolioPosition.del_flag == '1',
                Position.del_flag == '1'
            ).all()

            positions = []
            total_value = 0.0
            total_cost = 0.0

            for position in query:
                pos_data = {
                    'id': position.id,
                    'fund_code': position.fund_code,
                    'fund_name': position.fund_name,
                    'shares': float(position.shares) if position.shares else 0.0,
                    'cost_price': float(position.cost_price) if position.cost_price else 0.0,
                    'current_price': float(position.current_price) if position.current_price else 0.0,
                    'current_value': float(position.current_value) if position.current_value else 0.0,
                    'cost_amount': float(position.cost_amount) if position.cost_amount else 0.0,
                    'profit_loss': float(position.profit_loss) if position.profit_loss else 0.0,
                    'profit_loss_rate': float(position.profit_loss_rate) if position.profit_loss_rate else 0.0,
                    'buy_date': str(position.buy_date) if position.buy_date else None,
                    'remark': position.remark,
                    'create_time': str(position.create_time) if position.create_time else None,
                    'update_time': str(position.update_time) if position.update_time else None
                }
                positions.append(pos_data)

                # 累加统计数据
                total_value += float(position.current_value) if position.current_value else 0.0
                total_cost += float(position.shares) * float(position.cost_price) if position.shares and position.cost_price else 0.0

            return jsonify({
                'data': positions,
                'total_value': total_value,
                'total_cost': total_cost,
                'total_profit_loss': total_value - total_cost
            })
        finally:
            session.close()
    except Exception as e:
        logger.error(f"获取组合持仓列表失败: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/portfolios/<int:portfolio_id>', methods=['GET'])
@log_request
def get_portfolio(portfolio_id):
    """获取单个持仓组合"""
    try:
        portfolio = _portfolio_storage.get_portfolio_by_id(portfolio_id)
        if not portfolio:
            return jsonify({'error': '持仓组合不存在'}), 404
        
        # 获取组合下的持仓列表并计算统计数据
        relations = _portfolio_position_storage.get_portfolio_positions(portfolio_id)
        positions = []
        total_value = 0.0
        total_cost = 0.0
        
        for relation in relations:
            position = _position_storage.get_position_by_id(relation['position_id'])
            if position:
                positions.append(position)
                # 累加市值和成本
                total_value += float(position.get('current_value', 0))
                total_cost += float(position.get('shares', 0)) * float(position.get('cost_price', 0))
        
        portfolio['positions'] = positions
        portfolio['total_value'] = total_value
        portfolio['total_cost'] = total_cost
        portfolio['total_profit_loss'] = total_value - total_cost
        return jsonify(portfolio)
    except Exception as e:
        logger.error(f"获取持仓组合失败: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/portfolios', methods=['POST'])
@log_request
def create_portfolio():
    """创建持仓组合"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': '请求数据为空'}), 400
        
        name = data.get('name')
        if not name:
            return jsonify({'error': '组合名称不能为空'}), 400
        
        portfolio_id = _portfolio_storage.create_portfolio(data)
        
        return jsonify({
            'id': portfolio_id,
            'message': '持仓组合创建成功'
        }), 201
    except Exception as e:
        logger.error(f"创建持仓组合失败: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/portfolios/<int:portfolio_id>', methods=['PUT'])
@log_request
def update_portfolio(portfolio_id):
    """更新持仓组合"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': '请求数据为空'}), 400
        
        success = _portfolio_storage.update_portfolio(portfolio_id, data)
        if not success:
            return jsonify({'error': '持仓组合不存在'}), 404
        
        return jsonify({'message': '持仓组合更新成功'})
    except Exception as e:
        logger.error(f"更新持仓组合失败: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/portfolios/<int:portfolio_id>', methods=['DELETE'])
@log_request
def delete_portfolio(portfolio_id):
    """删除持仓组合"""
    try:
        # 删除组合下的所有持仓关联
        _portfolio_position_storage.delete_portfolio_positions_by_portfolio(portfolio_id)
        
        # 删除组合
        success = _portfolio_storage.delete_portfolio(portfolio_id)
        if not success:
            return jsonify({'error': '持仓组合不存在'}), 404
        
        return jsonify({'message': '持仓组合删除成功'})
    except Exception as e:
        logger.error(f"删除持仓组合失败: {e}")
        return jsonify({'error': str(e)}), 500


# ==================== 持仓接口 ====================

@app.route('/api/positions', methods=['GET'])
@log_request
def get_positions():
    """获取持仓列表"""
    try:
        fund_code = request.args.get('fund_code', '')
        fund_name = request.args.get('fund_name', '')
        page = int(request.args.get('page', 1))
        page_size = int(request.args.get('page_size', 10))
        
        positions, total = _position_storage.get_positions_with_pagination(
            fund_code=fund_code,
            fund_name=fund_name,
            page=page,
            page_size=page_size
        )
        
        return jsonify({
            'data': positions,
            'total': total,
            'page': page,
            'page_size': page_size
        })
    except Exception as e:
        logger.error(f"获取持仓列表失败: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/positions/<int:position_id>', methods=['GET'])
@log_request
def get_position(position_id):
    """获取单个持仓"""
    try:
        position = _position_storage.get_position_by_id(position_id)
        if not position:
            return jsonify({'error': '持仓不存在'}), 404
        
        return jsonify(position)
    except Exception as e:
        logger.error(f"获取持仓失败: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/positions', methods=['POST'])
@log_request
def create_position():
    """创建持仓"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': '请求数据为空'}), 400
        
        fund_code = data.get('fund_code')
        if not fund_code:
            return jsonify({'error': '基金代码不能为空'}), 400
        
        position_id = _position_storage.create_position(data)
        
        return jsonify({
            'id': position_id,
            'message': '持仓创建成功'
        }), 201
    except Exception as e:
        logger.error(f"创建持仓失败: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/positions/<int:position_id>', methods=['PUT'])
@log_request
def update_position(position_id):
    """更新持仓"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': '请求数据为空'}), 400
        
        success = _position_storage.update_position(position_id, data)
        if not success:
            return jsonify({'error': '持仓不存在'}), 404
        
        return jsonify({'message': '持仓更新成功'})
    except Exception as e:
        logger.error(f"更新持仓失败: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/positions/<int:position_id>', methods=['DELETE'])
@log_request
def delete_position(position_id):
    """删除持仓"""
    try:
        success = _position_storage.delete_position(position_id)
        if not success:
            return jsonify({'error': '持仓不存在'}), 404
        
        return jsonify({'message': '持仓删除成功'})
    except Exception as e:
        logger.error(f"删除持仓失败: {e}")
        return jsonify({'error': str(e)}), 500


# ==================== 组合持仓关联接口 ====================

@app.route('/api/portfolios/batch', methods=['POST'])
@log_request
def get_portfolios_batch():
    """批量获取组合及其持仓信息（优化性能）"""
    try:
        data = request.get_json()
        if not data or 'portfolio_ids' not in data:
            return jsonify({'error': '缺少portfolio_ids参数'}), 400

        portfolio_ids = data['portfolio_ids']
        if not isinstance(portfolio_ids, list) or not portfolio_ids:
            return jsonify({'error': 'portfolio_ids必须是非空列表'}), 400

        results = []
        for portfolio_id in portfolio_ids:
            # 使用优化的方法获取组合信息
            portfolio_info = _portfolio_storage.get_portfolio_with_positions(portfolio_id)
            if portfolio_info:
                results.append(portfolio_info)

        return jsonify({
            'data': results,
            'count': len(results)
        })
    except Exception as e:
        logger.error(f"批量获取组合信息失败: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/portfolio-positions', methods=['POST'])
@log_request
def create_portfolio_position():
    """创建组合和持仓的关联"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': '请求数据为空'}), 400
        
        portfolio_id = data.get('portfolio_id')
        position_id = data.get('position_id')
        
        if not portfolio_id or not position_id:
            return jsonify({'error': '组合ID和持仓ID不能为空'}), 400
        
        relation_id = _portfolio_position_storage.create_portfolio_position(
            portfolio_id=portfolio_id,
            position_id=position_id,
            remark=data.get('remark', '')
        )
        
        return jsonify({
            'id': relation_id,
            'message': '关联创建成功'
        }), 201
    except Exception as e:
        logger.error(f"创建组合持仓关联失败: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/portfolio-positions/<int:relation_id>', methods=['DELETE'])
@log_request
def delete_portfolio_position(relation_id):
    """删除组合和持仓的关联"""
    try:
        success = _portfolio_position_storage.delete_portfolio_position(relation_id)
        if not success:
            return jsonify({'error': '关联不存在'}), 404
        
        return jsonify({'message': '关联删除成功'})
    except Exception as e:
        logger.error(f"删除组合持仓关联失败: {e}")
        return jsonify({'error': str(e)}), 500


# ==================== 系统日志API ====================

@app.route('/api/logs', methods=['GET'])
@log_request
def get_logs():
    """获取系统日志列表（支持搜索和分页）"""
    try:
        global _log_storage
        
        if not _log_storage:
            from ..storage import SystemLogStorage
            _log_storage = SystemLogStorage()
        
        page = int(request.args.get('page', 1))
        page_size = int(request.args.get('page_size', 20))
        level = request.args.get('level', '')
        category = request.args.get('category', '')
        trace_id = request.args.get('trace_id', '')
        request_path = request.args.get('request_path', '')
        task_name = request.args.get('task_name', '')
        start_time = request.args.get('start_time', '')
        end_time = request.args.get('end_time', '')
        
        logs, total = _log_storage.get_logs_with_pagination(
            level=level if level else None,
            category=category if category else None,
            trace_id=trace_id if trace_id else None,
            request_path=request_path if request_path else None,
            task_name=task_name if task_name else None,
            start_time=start_time if start_time else None,
            end_time=end_time if end_time else None,
            page=page,
            page_size=page_size
        )
        
        return jsonify({
            'data': logs,
            'total': total,
            'page': page,
            'page_size': page_size
        }), 200
    except Exception as e:
        logger.error(f"获取系统日志失败: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/logs/<int:log_id>', methods=['GET'])
@log_request
def get_log(log_id):
    """获取单个日志详情"""
    try:
        global _log_storage
        
        if not _log_storage:
            from ..storage import SystemLogStorage
            _log_storage = SystemLogStorage()
        
        log = _log_storage.get_log_by_id(log_id)
        if log:
            return jsonify(log), 200
        else:
            return jsonify({'error': '日志不存在'}), 404
    except Exception as e:
        logger.error(f"获取日志详情失败: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/logs/<int:log_id>', methods=['DELETE'])
@log_request
def delete_log(log_id):
    """删除日志记录"""
    try:
        global _log_storage
        
        if not _log_storage:
            from ..storage import SystemLogStorage
            _log_storage = SystemLogStorage()
        
        success = _log_storage.delete_log(log_id)
        if success:
            return jsonify({'message': '日志删除成功'}), 200
        else:
            return jsonify({'error': '日志不存在'}), 404
    except Exception as e:
        logger.error(f"删除日志失败: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/logs/clean', methods=['POST'])
@log_request
def clean_logs():
    """清理指定时间之前的日志"""
    try:
        global _log_storage
        
        if not _log_storage:
            from ..storage import SystemLogStorage
            _log_storage = SystemLogStorage()
        
        data = request.get_json()
        days_to_keep = data.get('days_to_keep', 30)
        
        from datetime import datetime, timedelta
        before_time = datetime.now() - timedelta(days=days_to_keep)
        
        deleted_count = _log_storage.delete_logs_by_time(before_time)
        
        return jsonify({
            'message': f'清理成功，共删除 {deleted_count} 条日志',
            'deleted_count': deleted_count
        }), 200
    except Exception as e:
        logger.error(f"清理日志失败: {e}")
        return jsonify({'error': str(e)}), 500


def start_server_in_background(host='0.0.0.0', port=5000, debug=False):
    """在后台线程启动 Web 服务器"""
    thread = threading.Thread(target=start_server, args=(host, port, debug), daemon=True)
    thread.start()
    logger.info(f"Web 服务已在后台启动，监听 {host}:{port}, debug: {debug}")
    return thread
