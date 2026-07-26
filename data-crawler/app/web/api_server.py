import flask
from flask import Flask, jsonify, request, session, g
import threading
import traceback
from datetime import datetime as dt, timedelta
import time
import functools
import os
from sqlalchemy import text

from ..utils.logger import logger, trace_id_var, request_method_var, request_path_var, request_ip_var, category_var
from ..storage import TaskScheduleStorage, FundInfoStorage, FundBuyerStorage, FundSellerStorage, FundNavHistoryStorage, PortfolioStorage, PositionStorage, PortfolioPositionStorage, PortfolioPosition, UserStorage, IndexInfoStorage, PositionDailySnapshotStorage, FundDipPlanStorage, TaskRunRecordStorage
from ..analytics import calc_moving_average, calc_volatility, calc_annualized_return, calc_change_distribution, calc_monthly_returns, simulate_dca, calc_ma_signal, calc_bollinger_bands, calc_bollinger_signal, calc_position_overview, calc_position_allocation, calc_portfolio_profit_series, calc_portfolio_overview, compute_cost_index_series, filter_trading_days
from ..utils.datetime_utils import get_beijing_now
from . import scheduler_proxy

app = Flask(__name__)
_task_storage = TaskScheduleStorage()
_fund_storage = FundInfoStorage()
_buyer_storage = FundBuyerStorage()
_seller_storage = FundSellerStorage()
_nav_storage = FundNavHistoryStorage()
_portfolio_storage = PortfolioStorage()
_position_storage = PositionStorage()
_portfolio_position_storage = PortfolioPositionStorage()
_log_storage = None
_user_storage = UserStorage()
_index_storage = IndexInfoStorage()
_position_snapshot_storage = PositionDailySnapshotStorage()
_dip_plan_storage = FundDipPlanStorage()
_run_record_storage = TaskRunRecordStorage()

# 会话签名密钥（登录态 Cookie 鉴权依赖）。生产环境必须在 .env 设置 SECRET_KEY
app.secret_key = os.getenv('SECRET_KEY')
if not app.secret_key:
    app.secret_key = 'dev-insecure-secret-change-me'
    logger.warning("SECRET_KEY 未设置，使用不安全的开发默认值！生产环境必须在 .env 设置 SECRET_KEY。")

# Cookie 安全配置
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_SECURE'] = os.getenv('FLASK_COOKIE_SECURE', 'false').lower() == 'true'
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(minutes=60)
# 关闭「每次响应都刷新 Cookie」：让登录时按用户 TTL 烘焙的 Cookie 保持原样直到自然过期，
# 避免 app 级 permanent_session_lifetime 在多用户间交叉污染（默认 True 会使最后登录者的 TTL 覆盖所有人）
app.config['SESSION_REFRESH_EACH_REQUEST'] = False


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


# ==================== 鉴权与用户管理 ====================

# 无需登录即可访问的路径
_PUBLIC_PATHS = {'/api/login'}


def _is_admin(user):
    """判断是否管理员"""
    return bool(user and user.get('role') == 'admin')


def admin_required(func):
    """管理员权限装饰器：非管理员返回 403。须置于 @log_request 之下。"""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        if not _is_admin(getattr(g, 'user', None)):
            return jsonify({'error': '无权限'}), 403
        return func(*args, **kwargs)
    return wrapper


@app.before_request
def require_auth():
    """登录态校验：保护所有 /api/* 接口，放行 /api/login 与非 /api 路径。

    web→scheduler 的转发是出站 HTTP（scheduler_proxy），不经过本钩子，不受影响。
    scheduler 进程（5001）仅内部网络可达，不做鉴权。
    """
    if request.method == 'OPTIONS':
        return None
    # 非 /api 路径（如 /health、静态资源）不鉴权
    if not request.path.startswith('/api/'):
        return None
    if request.path in _PUBLIC_PATHS:
        return None

    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'error': '未登录或登录已过期'}), 401

    # 每次请求复核用户状态：get_user_by_id 已排除已删除用户；
    # 此处额外拦截「登录后被禁用」的用户，使其已建立会话立即失效
    user = _user_storage.get_user_by_id(user_id)
    if not user or not user.get('enabled'):
        session.clear()
        return jsonify({'error': '未登录或登录已过期'}), 401

    g.user = user
    return None


@app.route('/api/login', methods=['POST'])
@log_request
def login():
    """用户登录"""
    data = request.get_json(silent=True) or {}
    username = (data.get('username') or '').strip()
    password = data.get('password') or ''
    if not username or not password:
        return jsonify({'error': '请输入用户名和密码'}), 400

    user = _user_storage.verify_user(username, password)
    if not user:
        logger.info(f"登录失败: username={username}")
        return jsonify({'error': '用户名或密码错误'}), 401

    session.clear()
    session['user_id'] = user['id']
    session.permanent = True
    # 按用户配置的会话时长烘焙 Cookie。配合 SESSION_REFRESH_EACH_REQUEST=False，
    # 该 Cookie 保持此 TTL 直到自然过期（绝对时长，自登录起算）。
    app.permanent_session_lifetime = timedelta(
        minutes=user.get('session_ttl_minutes') or 60
    )
    logger.info(f"用户登录成功: {username} (id={user['id']})")
    return jsonify({'success': True, 'user': user}), 200


@app.route('/api/logout', methods=['POST'])
@log_request
def logout():
    """退出登录"""
    user = getattr(g, 'user', None)
    session.clear()
    if user:
        logger.info(f"用户退出登录: {user.get('username')} (id={user.get('id')})")
    return jsonify({'success': True, 'message': '已退出登录'}), 200


@app.route('/api/me', methods=['GET'])
@log_request
def get_me():
    """获取当前登录用户信息"""
    return jsonify({'user': getattr(g, 'user', None)}), 200


@app.route('/api/users', methods=['GET'])
@log_request
@admin_required
def get_users():
    """获取用户列表（仅管理员，支持搜索与分页）"""
    try:
        page = int(request.args.get('page', 1))
        page_size = int(request.args.get('page_size', 10))
        username = request.args.get('username', '')
        role = request.args.get('role', '')
        enabled = request.args.get('enabled', '')

        users, total = _user_storage.get_users_with_pagination(
            username=username if username else None,
            role=role if role else None,
            enabled=enabled if enabled != '' else None,
            page=page,
            page_size=page_size
        )
        return jsonify({
            'data': users,
            'total': total,
            'page': page,
            'page_size': page_size
        }), 200
    except Exception as e:
        logger.error(f"获取用户列表失败: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/users', methods=['POST'])
@log_request
@admin_required
def create_user():
    """创建用户（仅管理员）"""
    current = getattr(g, 'user', None)
    try:
        data = request.get_json(silent=True) or {}
        username = (data.get('username') or '').strip()
        password = data.get('password') or ''
        if not username or not password:
            return jsonify({'error': '用户名和密码为必填项'}), 400
        data['username'] = username
        data['create_by'] = current.get('username', 'api') if current else 'api'
        user = _user_storage.create_user(data)
        return jsonify({'success': True, 'message': '用户创建成功', 'id': user['id']}), 201
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"创建用户失败: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/users/<int:user_id>', methods=['PUT'])
@log_request
@admin_required
def update_user(user_id):
    """更新用户（仅管理员，含防自锁）"""
    current = getattr(g, 'user', None)
    data = request.get_json(silent=True) or {}

    # 防自锁：禁止对自己执行禁用或降级（覆盖 falsy 边界：False/0/""/None）
    if current and user_id == current.get('id'):
        if 'enabled' in data and not data['enabled']:
            return jsonify({'error': '不可禁用当前登录用户'}), 403
        if 'role' in data and data.get('role') != 'admin':
            return jsonify({'error': '不可取消自身管理员权限'}), 403

    try:
        data['update_by'] = current.get('username', 'api') if current else 'api'
        ok = _user_storage.update_user(user_id, data)
        if not ok:
            return jsonify({'error': '用户不存在'}), 404
        return jsonify({'success': True, 'message': '用户更新成功'}), 200
    except Exception as e:
        logger.error(f"更新用户 {user_id} 失败: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/users/<int:user_id>', methods=['DELETE'])
@log_request
@admin_required
def delete_user(user_id):
    """删除用户（仅管理员，不可删除自己）"""
    current = getattr(g, 'user', None)
    if current and user_id == current.get('id'):
        return jsonify({'error': '不可删除当前登录用户'}), 403
    try:
        ok = _user_storage.delete_user(user_id)
        if not ok:
            return jsonify({'error': '用户不存在'}), 404
        return jsonify({'success': True, 'message': '用户删除成功'}), 200
    except Exception as e:
        logger.error(f"删除用户 {user_id} 失败: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/crawl', methods=['POST'])
@log_request
def trigger_crawl():
    """触发基金净值爬取任务（转发到调度器进程）"""
    data, code = scheduler_proxy.run_task('update_fund_net_values_task')
    return jsonify(data), code


@app.route('/api/task/run/<task_func>', methods=['POST'])
@log_request
def run_task(task_func):
    """立即执行指定任务（异步：转发到调度器，立即返回 triggered+record_id+trace_id）"""
    try:
        force_run = False
        try:
            if request.json:
                force_run = request.json.get('force_run', False)
        except Exception:
            pass

        triggered_by = 'manual'
        try:
            triggered_by = g.user.get('username', 'manual')
        except Exception:
            pass

        data, code = scheduler_proxy.run_task(task_func, force_run=force_run, triggered_by=triggered_by)
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

            # 一次性查询所有运行中任务（避免 N+1 DB 调用）
            running_funcs = set(_run_record_storage.get_running_task_funcs())

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
                    'running': task.task_func in running_funcs,
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


@app.route('/api/tasks/running', methods=['GET'])
@log_request
def get_running_tasks():
    """轻量接口：返回当前 RUNNING 的 task_func 集合，供前端轮询运行状态（不拉全量任务列表）"""
    try:
        running_funcs = _run_record_storage.get_running_task_funcs()
        return jsonify({'running': running_funcs}), 200
    except Exception as e:
        logger.error(f"获取运行中任务失败: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/task-records', methods=['GET'])
@log_request
def get_task_records():
    """获取任务执行记录列表（支持 task_func/status 过滤 + 分页，供前端「执行计划」弹窗）"""
    try:
        page = int(request.args.get('page', 1))
        page_size = int(request.args.get('page_size', 20))
        task_func = request.args.get('task_func', '')
        status = request.args.get('status', '')

        records, total = _run_record_storage.get_records_with_pagination(
            task_func=task_func if task_func else None,
            status=status if status else None,
            page=page, page_size=page_size
        )

        data = [{
            'id': r.id,
            'task_func': r.task_func,
            'task_name': r.task_name,
            'trigger_type': r.trigger_type,
            'status': r.status,
            'trace_id': r.trace_id,
            'triggered_by': r.triggered_by,
            'start_time': str(r.start_time) if r.start_time else None,
            'end_time': str(r.end_time) if r.end_time else None,
            'duration_ms': r.duration_ms,
            'error_message': r.error_message
        } for r in records]

        return jsonify({
            'data': data, 'total': total, 'page': page, 'page_size': page_size
        }), 200
    except Exception as e:
        logger.error(f"获取任务执行记录失败: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/task-records/<int:record_id>', methods=['GET'])
@log_request
def get_task_record(record_id):
    """获取单条任务执行记录（前端轮询执行状态用）"""
    try:
        r = _run_record_storage.get_record_by_id(record_id)
        if not r:
            return jsonify({'error': '记录不存在'}), 404
        return jsonify({
            'id': r.id,
            'task_func': r.task_func,
            'task_name': r.task_name,
            'trigger_type': r.trigger_type,
            'status': r.status,
            'trace_id': r.trace_id,
            'triggered_by': r.triggered_by,
            'start_time': str(r.start_time) if r.start_time else None,
            'end_time': str(r.end_time) if r.end_time else None,
            'duration_ms': r.duration_ms,
            'error_message': r.error_message
        }), 200
    except Exception as e:
        logger.error(f"获取任务执行记录失败: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/task-records', methods=['DELETE'])
@log_request
@admin_required
def clean_task_records():
    """清理 N 天前的任务执行记录（RUNNING 不删，防误删在跑任务）"""
    try:
        days = int(request.args.get('days', 30))
        if days < 1:
            return jsonify({'error': '保留天数必须大于 0'}), 400
        deleted = _run_record_storage.clean_records_before(days)
        return jsonify({
            'success': True,
            'deleted': deleted,
            'message': f'已清理 {days} 天前的执行记录 {deleted} 条'
        }), 200
    except Exception as e:
        logger.error(f"清理任务执行记录失败: {e}")
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
        keyword = request.args.get('keyword', '')

        # 使用存储类方法获取数据（确保使用pool_pre_ping配置）
        funds, total = _fund_storage.get_funds_with_pagination(
            fund_code=fund_code if fund_code else None,
            fund_name=fund_name if fund_name else None,
            fund_type=fund_type if fund_type else None,
            keyword=keyword if keyword else None,
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


# ==================== 基金定投计划API ====================
# 一个基金可配多条定投计划（单基金多规则），净值更新任务命中当天且当天有净值时
# 自动插入当天 PENDING 买入流水，由 calculate_buyer_shares_task 计算份额。

@app.route('/api/dip-plans', methods=['GET'])
@log_request
def get_dip_plans():
    """获取定投计划列表。传 fund_code 查指定基金的，不传查全部。"""
    try:
        fund_code = request.args.get('fund_code', '')
        if fund_code:
            data = _dip_plan_storage.get_plans_by_fund_code(fund_code)
        else:
            # 不传 fund_code 时返回全部启用中的（任务视角），前端管理页一般传 fund_code
            data = _dip_plan_storage.get_enabled_plans()
        return jsonify({'data': data, 'total': len(data)}), 200
    except Exception as e:
        logger.error(f"获取定投计划失败: {e}")
        return jsonify({'error': str(e)}), 500


def _validate_dip_plan_data(data):
    """校验定投计划参数，返回 (ok, error_msg)"""
    freq = data.get('dip_frequency', '')
    if freq not in ('daily', 'weekly', 'monthly'):
        return False, 'dip_frequency 必须为 daily/weekly/monthly'
    # weekly: dip_day 1-7；monthly: dip_day 1-28；daily: dip_day 忽略
    if freq in ('weekly', 'monthly'):
        dip_day = str(data.get('dip_day', '')).strip()
        upper = 7 if freq == 'weekly' else 28
        try:
            day_val = int(dip_day)
        except (TypeError, ValueError):
            return False, f'dip_day 必须为 1-{upper} 的整数'
        if not 1 <= day_val <= upper:
            return False, f'dip_day 必须为 1-{upper}'
    # 金额必须 > 0
    try:
        amount = float(data.get('dip_amount', 0))
    except (TypeError, ValueError):
        return False, 'dip_amount 必须为数字'
    if amount <= 0:
        return False, 'dip_amount 必须大于 0'
    return True, None


@app.route('/api/dip-plans', methods=['POST'])
@log_request
def create_dip_plan():
    """创建定投计划"""
    try:
        data = request.json
        if not data.get('fund_code'):
            return jsonify({'error': '缺少必填字段: fund_code'}), 400
        ok, msg = _validate_dip_plan_data(data)
        if not ok:
            return jsonify({'error': msg}), 400

        plan_id = _dip_plan_storage.create_plan(data)
        if plan_id is None:
            return jsonify({'error': '创建定投计划失败'}), 500
        return jsonify({'success': True, 'message': '定投计划创建成功', 'id': plan_id}), 201
    except Exception as e:
        logger.error(f"创建定投计划失败: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/dip-plans/<int:plan_id>', methods=['PUT'])
@log_request
def update_dip_plan(plan_id):
    """更新定投计划"""
    try:
        data = request.json
        # 若改了频率/日期/金额，校验新值
        if any(k in data for k in ('dip_frequency', 'dip_day', 'dip_amount')):
            ok, msg = _validate_dip_plan_data(data)
            if not ok:
                return jsonify({'error': msg}), 400
        if _dip_plan_storage.update_plan(plan_id, data):
            return jsonify({'success': True, 'message': '定投计划更新成功'}), 200
        return jsonify({'error': '定投计划不存在或更新失败'}), 404
    except Exception as e:
        logger.error(f"更新定投计划失败: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/dip-plans/<int:plan_id>', methods=['DELETE'])
@log_request
def delete_dip_plan(plan_id):
    """删除定投计划（软删除）"""
    try:
        if _dip_plan_storage.delete_plan(plan_id):
            return jsonify({'success': True, 'message': '定投计划删除成功'}), 200
        return jsonify({'error': '定投计划不存在'}), 404
    except Exception as e:
        logger.error(f"删除定投计划失败: {e}")
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


@app.route('/api/buyers/backfill', methods=['POST'])
@log_request
def backfill_buyer():
    """补录买入：一步到位 - 建记录 + 立即算份额(buy_date 净值) + 立即更新持仓

    返回：SUCCESS/NO_POSITION -> 201 {success, shares, position_updated, message}；
          净值缺失 -> 400；持仓更新异常 -> 500（买入保持 PENDING，任务重试）。
    """
    from ..storage.fund_buyer_storage import FundBuyer, compute_buyer_shares
    from ..utils.nav_utils import get_nav_value_by_date
    from sqlalchemy.exc import IntegrityError
    try:
        data = request.json
        for field in ['fund_code', 'time', 'amt']:
            if field not in data:
                return jsonify({'error': f'缺少必填字段: {field}'}), 400
        try:
            amt = float(data['amt'])
            if amt <= 0:
                return jsonify({'error': '买入金额必须大于0'}), 400
        except (ValueError, TypeError):
            return jsonify({'error': '买入金额必须是有效的数字'}), 400

        fund_code = data['fund_code']
        buy_date = data['time']  # YYYY-MM-DD

        # 1. 取 buy_date 净值（精确日期匹配）
        nav = get_nav_value_by_date(_fund_storage, _nav_storage, fund_code, buy_date)
        if nav is None or nav <= 0:
            return jsonify({'error': f'无法获取 {buy_date} 的净值，请先录入该日净值'}), 400

        # 2. 算份额（用 buy_date 净值）
        shares = compute_buyer_shares(amt, nav)
        shares_float = float(shares)

        # 最新净值（用于持仓 current_price + 重算市值）
        # 补录是过去日期，持仓"现价"应用最新净值，而非买入日净值（否则 current_value 虚高/虚低）
        fund_info = _fund_storage.get_fund_by_code(fund_code)
        latest_nav = float(fund_info.net_asset_value) if (fund_info and fund_info.net_asset_value) else nav

        # 3. 建买入记录（PENDING），拿 id
        session = _buyer_storage.Session()
        try:
            new_buyer = FundBuyer(
                fund_code=fund_code,
                fund_name=data.get('fund_name', ''),
                time=dt.strptime(buy_date, '%Y-%m-%d').date(),
                amt=amt,
                type=data.get('type', '1'),
                policy='',
                buy_status='PENDING',
                remark=data.get('remark', ''),
                del_flag='1',
                create_by='api',
                create_time=get_beijing_now(),
                update_by='api',
                update_time=get_beijing_now(),
            )
            session.add(new_buyer)
            session.commit()
            session.refresh(new_buyer)
            buyer_id = new_buyer.id
        except IntegrityError as e:
            session.rollback()
            logger.warning(f"补录撞唯一键: {e}")
            return jsonify({'error': f'该基金在 {buy_date} 该买入类型已存在记录，无法重复补录（可删除/编辑已有记录）'}), 400
        except Exception as e:
            session.rollback()
            logger.error(f"补录建记录失败: {e}")
            return jsonify({'error': str(e)}), 500
        finally:
            session.close()

        # 4. 原子累加持仓 + 标 SUCCESS（current_price 用最新净值，ERROR 则记录留 PENDING，任务重试）
        result = _buyer_storage.process_buyer_transaction(
            [buyer_id], fund_code, shares_float, amt, latest_nav, buy_date
        )

        if result == 'ERROR':
            return jsonify({'error': '补录失败（持仓更新异常），买入记录保持待处理，将稍后重试'}), 500

        position_updated = (result == 'SUCCESS')
        message = '补录成功，持仓已更新' if position_updated else '补录成功，但该基金无持仓，未更新持仓（请先建持仓）'
        return jsonify({
            'success': True,
            'shares': shares_float,
            'position_updated': position_updated,
            'message': message
        }), 201
    except Exception as e:
        logger.error(f"补录买入失败: {e}")
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


# ==================== 基金卖出流水API ====================

@app.route('/api/sellers', methods=['GET'])
@log_request
def get_sellers():
    """获取卖出记录列表（支持搜索和分页）"""
    try:
        # 获取分页参数
        page = int(request.args.get('page', 1))
        page_size = int(request.args.get('page_size', 10))

        # 获取搜索参数
        fund_code = request.args.get('fund_code', '')
        fund_name = request.args.get('fund_name', '')
        sell_type = request.args.get('type', '')
        sell_status = request.args.get('sell_status', '')
        start_time = request.args.get('start_time', '')
        end_time = request.args.get('end_time', '')

        # 获取排序参数
        sort_field = request.args.get('sort_field', '')
        sort_order = request.args.get('sort_order', '')

        # 使用存储类方法获取数据
        sellers, total = _seller_storage.get_sellers_with_pagination(
            fund_code=fund_code if fund_code else None,
            fund_name=fund_name if fund_name else None,
            sell_type=sell_type if sell_type else None,
            sell_status=sell_status if sell_status else None,
            start_time=start_time if start_time else None,
            end_time=end_time if end_time else None,
            sort_field=sort_field if sort_field else None,
            sort_order=sort_order if sort_order else None,
            page=page,
            page_size=page_size
        )

        return jsonify({
            'data': sellers,
            'total': total,
            'page': page,
            'page_size': page_size
        }), 200
    except Exception as e:
        logger.error(f"获取卖出记录失败: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/sellers/<int:seller_id>', methods=['GET'])
@log_request
def get_seller(seller_id):
    """获取单个卖出记录"""
    try:
        from ..storage.fund_seller_storage import FundSeller

        session = _seller_storage.Session()

        try:
            seller = session.query(FundSeller).filter(
                FundSeller.id == seller_id,
                FundSeller.del_flag == '1'
            ).first()

            if seller:
                result = {
                    'id': seller.id,
                    'fund_code': seller.fund_code,
                    'fund_name': seller.fund_name,
                    'time': str(seller.time),
                    'shares': float(seller.shares) if seller.shares else 0.0,
                    'amt': float(seller.amt) if seller.amt is not None else None,
                    'nav': float(seller.nav) if seller.nav is not None else None,
                    'realized_profit': float(seller.realized_profit) if seller.realized_profit is not None else None,
                    'type': seller.type,
                    'policy': seller.policy,
                    'sell_status': seller.sell_status,
                    'remark': seller.remark,
                    'create_time': str(seller.create_time) if seller.create_time else None,
                    'update_time': str(seller.update_time) if seller.update_time else None
                }
                return jsonify(result), 200
            else:
                return jsonify({'error': '卖出记录不存在'}), 404
        finally:
            session.close()
    except Exception as e:
        logger.error(f"获取卖出记录失败: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/sellers', methods=['POST'])
@log_request
def create_seller():
    """创建卖出记录"""
    try:
        from ..storage.fund_seller_storage import FundSeller
        data = request.json
        required_fields = ['fund_code', 'time', 'shares']
        for field in required_fields:
            if field not in data:
                return jsonify({'error': f'缺少必填字段: {field}'}), 400

        # 数据类型验证
        try:
            shares = float(data['shares'])
            if shares <= 0:
                return jsonify({'error': '卖出份额必须大于0'}), 400
        except (ValueError, TypeError):
            return jsonify({'error': '卖出份额必须是有效的数字'}), 400

        # 创建新的session
        session = _seller_storage.Session()

        try:
            # 若存在同基金同日的软删除记录，恢复并覆盖（避免唯一键 uk_fund_code_time 冲突）
            sell_date = dt.strptime(data['time'], '%Y-%m-%d').date()
            existing = session.query(FundSeller).filter(
                FundSeller.fund_code == data['fund_code'],
                FundSeller.time == sell_date
            ).first()

            if existing:
                # 恢复软删除记录并覆盖字段
                existing.fund_name = data.get('fund_name', '')
                existing.shares = shares
                existing.type = data.get('type', '')
                existing.policy = data.get('policy', '')
                existing.sell_status = data.get('sell_status', 'PENDING')
                existing.remark = data.get('remark', '')
                existing.amt = None
                existing.nav = None
                existing.realized_profit = None
                existing.del_flag = '1'
                existing.create_by = 'api'
                existing.create_time = get_beijing_now()
                existing.update_by = 'api'
                existing.update_time = get_beijing_now()
                session.commit()
                session.refresh(existing)
                return jsonify({
                    'success': True,
                    'message': '卖出记录创建成功',
                    'id': existing.id
                }), 201

            new_seller = FundSeller(
                fund_code=data['fund_code'],
                fund_name=data.get('fund_name', ''),
                time=sell_date,
                shares=shares,
                type=data.get('type', ''),
                policy=data.get('policy', ''),
                sell_status=data.get('sell_status', 'PENDING'),
                remark=data.get('remark', ''),
                del_flag='1',
                create_by='api',
                create_time=get_beijing_now(),
                update_by='api',
                update_time=get_beijing_now()
            )

            session.add(new_seller)
            session.commit()
            session.refresh(new_seller)

            return jsonify({
                'success': True,
                'message': '卖出记录创建成功',
                'id': new_seller.id
            }), 201
        except Exception as e:
            session.rollback()
            logger.error(f"创建卖出记录失败: {e}")
            return jsonify({'error': str(e)}), 500
        finally:
            session.close()
    except Exception as e:
        logger.error(f"创建卖出记录失败: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/sellers/<int:seller_id>', methods=['PUT'])
@log_request
def update_seller(seller_id):
    """更新卖出记录"""
    try:
        from ..storage.fund_seller_storage import FundSeller
        data = request.json

        # 创建新的session
        session = _seller_storage.Session()

        try:
            seller = session.query(FundSeller).filter(
                FundSeller.id == seller_id,
                FundSeller.del_flag == '1'
            ).first()

            if not seller:
                return jsonify({'error': '卖出记录不存在'}), 404

            # RISK-7 防护：禁止修改计算字段（amt/nav/realized_profit 由任务回写，不可手动改）
            # 防止把 SUCCESS 改回 PENDING 导致任务重处理 -> 重复扣减持仓
            if 'sell_status' in data:
                new_status = data['sell_status']
                if seller.sell_status == 'SUCCESS' and new_status != 'SUCCESS':
                    return jsonify({
                        'error': '已成功的卖出记录不可回退状态（避免重复扣减持仓）'
                    }), 400
                seller.sell_status = new_status

            # 仅允许修改录入字段，计算字段（amt/nav/realized_profit）服务端忽略
            if 'fund_code' in data:
                seller.fund_code = data['fund_code']
            if 'fund_name' in data:
                seller.fund_name = data['fund_name']
            if 'time' in data:
                seller.time = dt.strptime(data['time'], '%Y-%m-%d').date()
            if 'shares' in data:
                seller.shares = data['shares']
            if 'type' in data:
                seller.type = data['type']
            if 'policy' in data:
                seller.policy = data['policy']
            if 'remark' in data:
                seller.remark = data['remark']

            seller.update_by = 'api'
            seller.update_time = get_beijing_now()

            session.commit()

            return jsonify({
                'success': True,
                'message': '卖出记录更新成功'
            }), 200
        except Exception as e:
            session.rollback()
            logger.error(f"更新卖出记录失败: {e}")
            return jsonify({'error': str(e)}), 500
        finally:
            session.close()
    except Exception as e:
        logger.error(f"更新卖出记录失败: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/sellers/<int:seller_id>', methods=['DELETE'])
@log_request
def delete_seller(seller_id):
    """删除卖出记录"""
    try:
        from ..storage.fund_seller_storage import FundSeller

        # 创建新的session
        session = _seller_storage.Session()

        try:
            seller = session.query(FundSeller).filter(
                FundSeller.id == seller_id,
                FundSeller.del_flag == '1'
            ).first()

            if not seller:
                return jsonify({'error': '卖出记录不存在'}), 404

            seller.del_flag = '0'
            seller.update_by = 'api'
            seller.update_time = get_beijing_now()

            session.commit()

            return jsonify({
                'success': True,
                'message': '卖出记录删除成功'
            }), 200
        except Exception as e:
            session.rollback()
            logger.error(f"删除卖出记录失败: {e}")
            return jsonify({'error': str(e)}), 500
        finally:
            session.close()
    except Exception as e:
        logger.error(f"删除卖出记录失败: {e}")
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
            # 使用JOIN查询一次获取持仓及关联关系（带 relation_id 供前端移除关联）
            query = session.query(
                Position, PortfolioPosition.id.label('relation_id')
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

            for position, relation_id in query:
                pos_data = {
                    'id': position.id,
                    'relation_id': relation_id,
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


@app.route('/api/positions/by-fund', methods=['GET'])
@log_request
def get_position_by_fund():
    """按基金代码查询已有持仓（供添加持仓时带出已有持仓）

    参数：fund_code。返回持仓信息或 {data: null}（无持仓时）。
    """
    fund_code = request.args.get('fund_code', '')
    if not fund_code:
        return jsonify({'error': '缺少参数 fund_code'}), 400
    try:
        position = _position_storage.get_position_by_fund_code(fund_code)
        return jsonify({'data': position}), 200
    except Exception as e:
        logger.error(f"按基金查询持仓失败: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/positions/allocation', methods=['GET'])
@log_request
def get_positions_allocation():
    """Dashboard 持仓占比（实时）：全量有效持仓按市值占比

    数据源为实时 position 表（current_value），非历史快照。
    返回 {data:[{fund_code, fund_name, value, percent}]}，无持仓返回空。
    """
    try:
        positions = _position_storage.get_all_active_positions()
        allocation = calc_position_allocation(positions)
        return jsonify({'data': allocation}), 200
    except Exception as e:
        logger.error(f"获取持仓占比失败: {e}")
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


# ==================== 指数分析接口 ====================

@app.route('/api/indexes', methods=['GET'])
@log_request
def get_indexes():
    """获取指数信息列表（支持搜索、日期范围、分页）"""
    try:
        page = int(request.args.get('page', 1))
        page_size = int(request.args.get('page_size', 10))
        index_code = request.args.get('index_code', '')
        index_name = request.args.get('index_name', '')
        index_type = request.args.get('index_type', '')
        start_date = request.args.get('start_date', '')
        end_date = request.args.get('end_date', '')

        data, total = _index_storage.get_index_list_with_pagination(
            index_code=index_code if index_code else None,
            index_name=index_name if index_name else None,
            index_type=index_type if index_type else None,
            start_date=start_date if start_date else None,
            end_date=end_date if end_date else None,
            page=page, page_size=page_size
        )
        return jsonify({'data': data, 'total': total, 'page': page, 'page_size': page_size}), 200
    except Exception as e:
        logger.error(f"获取指数列表失败: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/indexes/options', methods=['GET'])
@log_request
def get_index_options():
    """获取指数下拉选项（去重）"""
    try:
        data = _index_storage.get_all_indexes()
        return jsonify({'data': data}), 200
    except Exception as e:
        logger.error(f"获取指数选项失败: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/indexes/analysis', methods=['GET'])
@log_request
def get_index_analysis():
    """指数分析：概览 + 价格序列(含均线) + 涨跌幅分布 + 月度收益 + 均线信号"""
    index_code = request.args.get('index_code', '')
    if not index_code:
        return jsonify({'error': '缺少参数 index_code'}), 400
    try:
        start_date = request.args.get('start_date', '')
        end_date = request.args.get('end_date', '')

        # 均线预热：最大窗口 MA250，向前多取 400 日历日（≈285 交易日），
        # 使展示区间内每个点的均线/布林带都有值，而非区间开头一大段 None。
        warmup_start = None
        if start_date:
            warmup_start = (dt.strptime(start_date, '%Y-%m-%d') - timedelta(days=400)).strftime('%Y-%m-%d')

        all_rows = _index_storage.get_index_history(
            index_code=index_code,
            start_date=warmup_start,
            end_date=end_date if end_date else None
        )
        if not all_rows:
            return jsonify({
                'overview': {'count': 0, 'index_code': index_code},
                'series': [], 'change_distribution': [],
                'monthly_returns': [],
                'ma_signal': {'ma60': None, 'ma60_diff_pct': None,
                              'ma250': None, 'ma250_diff_pct': None,
                              'suggestion': '区间无数据'},
                'boll_signal': {'position': None, 'type': 'info',
                                'bandwidth_percentile': None, 'suggestion': '区间无数据'}
            }), 200

        # 基于含预热的全部数据计算均线/布林带（需要历史前置）
        all_closes = [r['close_price'] for r in all_rows]
        ma5 = calc_moving_average(all_closes, 5)
        ma20 = calc_moving_average(all_closes, 20)
        ma60 = calc_moving_average(all_closes, 60)
        ma250 = calc_moving_average(all_closes, 250)
        boll_upper, boll_middle, boll_lower = calc_bollinger_bands(all_closes, 20, 2)

        # 展示区间起始索引（预热部分不展示，仅用于均线计算）
        if start_date:
            start_idx = next((i for i, r in enumerate(all_rows) if r['trade_date'] >= start_date), 0)
        else:
            start_idx = 0
        rows = all_rows[start_idx:]

        dates = [r['trade_date'] for r in rows]
        closes = [r['close_price'] for r in rows]
        change_pcts = [r['change_percent'] for r in rows]
        amounts = [r['amount'] for r in rows]

        # series：区间内 K线 + 对应（含预热索引的）均线值
        series = []
        for j, r in enumerate(rows):
            i = start_idx + j
            series.append({
                'date': r['trade_date'],
                'open': r['open_price'], 'close': r['close_price'],
                'high': r['high_price'], 'low': r['low_price'],
                'change_percent': r['change_percent'],
                'volume': r['volume'], 'amount': r['amount'],
                'ma5': ma5[i], 'ma20': ma20[i], 'ma60': ma60[i], 'ma250': ma250[i],
                'boll_upper': boll_upper[i], 'boll_middle': boll_middle[i], 'boll_lower': boll_lower[i],
            })

        latest = rows[-1]
        first_close = rows[0]['close_price']
        latest_close = latest['close_price']
        high = max(r['high_price'] for r in rows)
        low = min(r['low_price'] for r in rows)
        days = len(rows)
        overview = {
            'index_code': index_code,
            'index_name': latest.get('index_name'),
            'latest_date': latest['trade_date'],
            'latest_close': latest_close,
            'start_date': rows[0]['trade_date'],
            'end_date': latest['trade_date'],
            'count': days,
            'interval_change_pct': (latest_close / first_close - 1) * 100 if first_close else 0.0,
            'high_price': high,
            'low_price': low,
            'amplitude': (high - low) / low * 100 if low else 0.0,
            'annualized_volatility': calc_volatility(change_pcts),
            'annualized_return': calc_annualized_return(first_close, latest_close, days),
            'avg_amount': sum(amounts) / len(amounts) if amounts else 0.0,
        }

        # 均线信号用区间最后一天（= all_rows 最后一天）的 MA60/MA250
        last_i = len(all_rows) - 1
        # 布林带信号：最新日三轨 + 区间内带宽序列（用于带宽分位判断）
        boll_bandwidths = []
        for i in range(start_idx, len(all_rows)):
            m, u, l = boll_middle[i], boll_upper[i], boll_lower[i]
            if m is not None and m != 0 and u is not None and l is not None:
                boll_bandwidths.append((u - l) / m * 100)
            else:
                boll_bandwidths.append(None)
        boll_signal = calc_bollinger_signal(
            latest_close, boll_upper[last_i], boll_middle[last_i], boll_lower[last_i],
            boll_bandwidths
        )
        return jsonify({
            'overview': overview,
            'series': series,
            'change_distribution': calc_change_distribution(change_pcts),
            'monthly_returns': calc_monthly_returns(dates, closes),
            'ma_signal': calc_ma_signal(latest_close, ma60[last_i], ma250[last_i]),
            'boll_signal': boll_signal,
        }), 200
    except Exception as e:
        logger.error(f"指数分析失败: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/indexes/dca', methods=['GET'])
@log_request
def get_index_dca():
    """定投模拟（含一次性买入对比）"""
    index_code = request.args.get('index_code', '')
    if not index_code:
        return jsonify({'error': '缺少参数 index_code'}), 400
    frequency = request.args.get('frequency', 'monthly')
    try:
        amount = float(request.args.get('amount', 1000))
    except ValueError:
        return jsonify({'error': 'amount 必须为数字'}), 400
    if frequency not in ('weekly', 'biweekly', 'monthly'):
        return jsonify({'error': 'frequency 仅支持 weekly/biweekly/monthly'}), 400

    try:
        start_date = request.args.get('start_date', '')
        end_date = request.args.get('end_date', '')
        rows = _index_storage.get_index_history(
            index_code=index_code,
            start_date=start_date if start_date else None,
            end_date=end_date if end_date else None
        )
        dates = [r['trade_date'] for r in rows]
        closes = [r['close_price'] for r in rows]
        result = simulate_dca(dates, closes, frequency, amount)
        result['index_code'] = index_code
        result['frequency'] = frequency
        result['amount'] = amount
        result['latest_close'] = closes[-1] if closes else 0.0
        return jsonify(result), 200
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"定投模拟失败: {e}")
        return jsonify({'error': str(e)}), 500


# ==================== 持仓分析接口 ====================

@app.route('/api/positions/snapshot/options', methods=['GET'])
@log_request
def get_position_snapshot_options():
    """获取有快照数据的可选持仓列表（供分析页下拉）"""
    try:
        data = _position_snapshot_storage.get_position_options()
        return jsonify({'data': data}), 200
    except Exception as e:
        logger.error(f"获取持仓快照选项失败: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/positions/snapshot/analysis', methods=['GET'])
@log_request
def get_position_snapshot_analysis():
    """持仓分析：概览 + 盈亏/市值序列 + 最大回撤 + 全部持仓占比饼图 + 累计收益序列 + 已实现盈亏

    参数：position_id（可选，空或 'all' 表示全部持仓/组合视角）、start_date/end_date（可选）
    - 选单持仓：series/overview 为该持仓视角（单持仓序列）
    - 选全部持仓（position_id 为空/'all'）：series/overview 为组合级聚合视角
    - portfolio_series：始终返回组合级每日聚合盈亏序列（累计收益图，随持仓切换展示不同视角由前端决定）
    - pie：最新日全部持仓占比（与 position_id 无关）
    - realized_profit_total：所有 SUCCESS 卖出记录的已实现盈亏求和
    """
    position_id_raw = request.args.get('position_id', '')

    try:
        start_date = request.args.get('start_date', '') or None
        end_date = request.args.get('end_date', '') or None

        # 交易日历（fund_nav_history 只在交易日有净值），过滤掉非交易日快照点（周末/节假日的无意义平段）
        trading_dates = _nav_storage.get_trading_dates(start_date, end_date)

        # 组合级累计收益序列（按日期聚合全部持仓）
        portfolio_rows = _position_snapshot_storage.get_portfolio_snapshot_series(
            start_date=start_date, end_date=end_date
        )
        portfolio_rows = filter_trading_days(portfolio_rows, trading_dates)
        portfolio_series = calc_portfolio_profit_series(portfolio_rows)

        # 单持仓 vs 组合视角
        is_portfolio_mode = position_id_raw in ('', 'all')
        if is_portfolio_mode:
            series = portfolio_rows
            overview = calc_portfolio_overview(portfolio_rows)
        else:
            try:
                position_id = int(position_id_raw)
            except ValueError:
                return jsonify({'error': 'position_id 必须为整数或 all'}), 400
            series = _position_snapshot_storage.get_position_snapshot_series(
                position_id=position_id, start_date=start_date, end_date=end_date
            )
            series = filter_trading_days(series, trading_dates)
            overview = calc_position_overview(series)

        # 饼图：最新快照日的全部持仓占比（与选中持仓无关）
        latest_all = _position_snapshot_storage.get_latest_snapshot_all_positions()
        pie = calc_position_allocation(latest_all)

        # 累计已实现盈亏：组合视角=全部 SUCCESS 卖出求和；单持仓视角=该基金 SUCCESS 卖出求和
        if is_portfolio_mode:
            realized_profit_total = _seller_storage.get_realized_profit_total()
        else:
            # 单持仓模式：取出该持仓的 fund_code 后按基金过滤
            pos = _position_storage.get_position_by_id(position_id)
            realized_profit_total = _seller_storage.get_realized_profit_total(
                fund_code=pos['fund_code'] if pos else None
            )

        return jsonify({
            'overview': overview,
            'series': series,
            'pie': pie,
            'portfolio_series': portfolio_series,
            'realized_profit_total': realized_profit_total,
        }), 200
    except Exception as e:
        logger.error(f"持仓分析失败: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/positions/snapshot/cost-index', methods=['GET'])
@log_request
def get_position_snapshot_cost_index():
    """持仓成本价↔指数对应走势（规则 A：固定比例·最新日）

    参数：position_id（单持仓）、start_date/end_date（可选）
    返回：{index_code, index_name, ratio, latest_fund_nav, latest_index_close, points}
    无关联指数时 index_code=None、ratio=None、points 仅含 cost_price。
    """
    position_id_raw = request.args.get('position_id', '')
    try:
        position_id = int(position_id_raw)
    except ValueError:
        return jsonify({'error': 'position_id 必须为整数'}), 400

    try:
        start_date = request.args.get('start_date', '') or None
        end_date = request.args.get('end_date', '') or None

        pos = _position_storage.get_position_by_id(position_id)
        if not pos:
            return jsonify({'error': '持仓不存在'}), 404

        index_code = pos.get('index_code')
        snapshots = _position_snapshot_storage.get_position_snapshot_series(
            position_id=position_id, start_date=start_date, end_date=end_date
        )

        index_history = []
        index_name = None
        if index_code:
            index_history = _index_storage.get_index_history(index_code, start_date, end_date)
            index_name = index_history[0].get('index_name') if index_history else None

        result = compute_cost_index_series(snapshots, index_history)
        return jsonify({
            'index_code': index_code,
            'index_name': index_name,
            'has_index': result['has_index'],
            'points': result['points'],
        }), 200
    except Exception as e:
        logger.error(f"持仓成本指数对应失败: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/positions/snapshots', methods=['GET'])
@log_request
def get_position_snapshots():
    """分页查询持仓快照列表（供管理/调试）"""
    try:
        page = int(request.args.get('page', 1))
        page_size = int(request.args.get('page_size', 10))
        position_id = request.args.get('position_id', '')
        fund_code = request.args.get('fund_code', '')
        start_date = request.args.get('start_date', '')
        end_date = request.args.get('end_date', '')

        data, total = _position_snapshot_storage.get_snapshots_with_pagination(
            position_id=int(position_id) if position_id else None,
            fund_code=fund_code if fund_code else None,
            start_date=start_date if start_date else None,
            end_date=end_date if end_date else None,
            page=page, page_size=page_size
        )
        return jsonify({'data': data, 'total': total, 'page': page, 'page_size': page_size}), 200
    except Exception as e:
        logger.error(f"获取持仓快照列表失败: {e}")
        return jsonify({'error': str(e)}), 500


def start_server_in_background(host='0.0.0.0', port=5000, debug=False):
    """在后台线程启动 Web 服务器"""
    thread = threading.Thread(target=start_server, args=(host, port, debug), daemon=True)
    thread.start()
    logger.info(f"Web 服务已在后台启动，监听 {host}:{port}, debug: {debug}")
    return thread
