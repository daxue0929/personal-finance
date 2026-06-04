from flask import Flask, jsonify, request
import threading
import datetime

from ..utils.logger import logger
from ..storage import TaskScheduleStorage, FundInfoStorage
from ..utils.datetime_utils import get_beijing_now

app = Flask(__name__)
scheduler_instance = None
_task_storage = TaskScheduleStorage()
_fund_storage = FundInfoStorage()


def set_scheduler(scheduler):
    global scheduler_instance
    scheduler_instance = scheduler


@app.route('/api/crawl', methods=['POST'])
def trigger_crawl():
    """触发基金净值爬取任务"""
    return run_task('update_fund_net_values_task')


@app.route('/api/task/run/<task_func>', methods=['POST'])
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
def get_tasks():
    """获取所有任务配置"""
    try:
        tasks = _task_storage.get_all_tasks()
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
        return jsonify(result), 200
    except Exception as e:
        logger.error(f"获取任务配置失败: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/tasks/<int:task_id>', methods=['GET'])
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
def health_check():
    """健康检查"""
    return jsonify({'status': 'ok', 'service': 'fund-crawler'}), 200


# ==================== 基金管理API ====================

@app.route('/api/funds', methods=['GET'])
def get_funds():
    """获取所有基金信息"""
    try:
        from ..storage.fund_info_storage import FundInfo
        funds = _fund_storage.session.query(FundInfo).filter(
            FundInfo.del_flag == '1'
        ).all()
        
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
        return jsonify(result), 200
    except Exception as e:
        logger.error(f"获取基金列表失败: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/funds/<int:fund_id>', methods=['GET'])
def get_fund(fund_id):
    """获取单个基金信息"""
    try:
        from ..storage.fund_info_storage import FundInfo
        fund = _fund_storage.session.query(FundInfo).filter(
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
    except Exception as e:
        logger.error(f"获取基金失败: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/funds', methods=['POST'])
def create_fund():
    """创建基金信息"""
    try:
        from ..storage.fund_info_storage import FundInfo
        data = request.json
        required_fields = ['fund_code', 'fund_name']
        for field in required_fields:
            if field not in data:
                return jsonify({'error': f'缺少必填字段: {field}'}), 400
        
        # 检查基金代码是否已存在
        existing = _fund_storage.session.query(FundInfo).filter(
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
            net_value_date=datetime.strptime(data.get('net_value_date'), '%Y-%m-%d').date() if data.get('net_value_date') else None,
            fund_manager=data.get('fund_manager', ''),
            establish_date=datetime.strptime(data.get('establish_date'), '%Y-%m-%d').date() if data.get('establish_date') else None,
            fund_size=data.get('fund_size', 0.0),
            remark=data.get('remark', ''),
            del_flag='1',
            create_by='api',
            create_time=get_beijing_now(),
            update_by='api',
            update_time=get_beijing_now()
        )
        
        _fund_storage.session.add(new_fund)
        _fund_storage.session.commit()
        _fund_storage.session.refresh(new_fund)
        
        return jsonify({
            'success': True,
            'message': '基金创建成功',
            'fund_id': new_fund.fund_id
        }), 201
    except Exception as e:
        _fund_storage.session.rollback()
        logger.error(f"创建基金失败: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/funds/<int:fund_id>', methods=['PUT'])
def update_fund(fund_id):
    """更新基金信息"""
    try:
        from ..storage.fund_info_storage import FundInfo
        data = request.json
        
        fund = _fund_storage.session.query(FundInfo).filter(
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
            fund.net_value_date = datetime.strptime(data['net_value_date'], '%Y-%m-%d').date()
        if 'fund_manager' in data:
            fund.fund_manager = data['fund_manager']
        if 'establish_date' in data:
            fund.establish_date = datetime.strptime(data['establish_date'], '%Y-%m-%d').date()
        if 'fund_size' in data:
            fund.fund_size = data['fund_size']
        if 'remark' in data:
            fund.remark = data['remark']
        
        fund.update_by = 'api'
        fund.update_time = get_beijing_now()
        
        _fund_storage.session.commit()
        
        return jsonify({
            'success': True,
            'message': '基金更新成功'
        }), 200
    except Exception as e:
        _fund_storage.session.rollback()
        logger.error(f"更新基金失败: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/funds/<int:fund_id>', methods=['DELETE'])
def delete_fund(fund_id):
    """删除基金信息"""
    try:
        from ..storage.fund_info_storage import FundInfo
        
        fund = _fund_storage.session.query(FundInfo).filter(
            FundInfo.fund_id == fund_id,
            FundInfo.del_flag == '1'
        ).first()
        
        if not fund:
            return jsonify({'error': '基金不存在'}), 404
        
        fund.del_flag = '0'
        fund.update_by = 'api'
        fund.update_time = get_beijing_now()
        
        _fund_storage.session.commit()
        
        return jsonify({
            'success': True,
            'message': '基金删除成功'
        }), 200
    except Exception as e:
        _fund_storage.session.rollback()
        logger.error(f"删除基金失败: {e}")
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
