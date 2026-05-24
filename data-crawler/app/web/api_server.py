from flask import Flask, jsonify, request
import threading
import time

from ..utils.logger import logger
from ..storage import TaskScheduleStorage
from ..utils.datetime_utils import get_beijing_now

app = Flask(__name__)
scheduler_instance = None
_task_storage = TaskScheduleStorage()


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
        if scheduler_instance:
            success = scheduler_instance.run_job_now(task_func)
            if success:
                return jsonify({
                    'success': True,
                    'message': f'任务 {task_func} 已触发'
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
