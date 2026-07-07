"""
调度器内部控制服务

仅在 scheduler 进程内运行的轻量 Flask 应用，暴露 /internal/* 接口供 web 进程转发调用。
不对外暴露，仅通过 docker 内部网络访问。
"""
from flask import Flask, jsonify, request

from ..utils.logger import logger


def create_control_app(scheduler):
    """创建内部控制 Flask 应用

    Args:
        scheduler: CronTaskScheduler 实例（本进程持有）
    """
    app = Flask(__name__)

    @app.route('/internal/status', methods=['GET'])
    def status():
        """调度器运行状态 + 所有任务列表"""
        return jsonify({
            'running': scheduler._running,
            'message': '调度器运行中' if scheduler._running else '调度器已停止',
            'jobs': scheduler.get_all_jobs()
        }), 200

    @app.route('/internal/start', methods=['POST'])
    def start():
        """启动调度器"""
        try:
            scheduler.start()
            return jsonify({'success': True, 'message': '调度器已启动'}), 200
        except Exception as e:
            logger.error(f"启动调度器失败: {e}")
            return jsonify({'success': False, 'message': str(e)}), 500

    @app.route('/internal/stop', methods=['POST'])
    def stop():
        """停止调度器"""
        try:
            scheduler.stop()
            return jsonify({'success': True, 'message': '调度器已停止'}), 200
        except Exception as e:
            logger.error(f"停止调度器失败: {e}")
            return jsonify({'success': False, 'message': str(e)}), 500

    @app.route('/internal/task/run/<task_func>', methods=['POST'])
    def run_task(task_func):
        """立即执行指定任务（同步阻塞，执行完返回）"""
        try:
            force_run = False
            try:
                if request.json:
                    force_run = request.json.get('force_run', False)
            except Exception:
                pass

            success = scheduler.run_job_now(task_func, force_run=force_run)
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
        except Exception as e:
            logger.error(f"触发任务失败: {e}")
            return jsonify({'success': False, 'message': str(e)}), 500

    @app.route('/internal/jobs', methods=['GET'])
    def all_jobs():
        """返回所有任务状态的字典 {task_func: {id,name,next_run_time,trigger}}

        供 web 进程批量查询，避免 N+1 HTTP 调用。
        """
        jobs = scheduler.get_all_jobs()
        return jsonify({j['id']: j for j in jobs}), 200

    @app.route('/internal/health', methods=['GET'])
    def health():
        """健康检查"""
        return jsonify({'status': 'ok', 'service': 'scheduler-control'}), 200

    return app
