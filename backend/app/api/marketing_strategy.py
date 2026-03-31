"""Marketing strategy API routes."""

import threading
import traceback

from flask import current_app, jsonify, request

from . import marketing_strategy_bp
from ..models.task import TaskManager, TaskStatus
from ..services.graph_tools import GraphToolsService
from ..services.marketing_strategy_agent import (
    MarketingStrategyAgent,
    MarketingStrategyManager,
    StrategyStatus,
)
from ..services.report_agent import ReportManager, ReportStatus
from ..utils.logger import get_logger

logger = get_logger('miroshark.api.marketing_strategy')


@marketing_strategy_bp.route('/generate', methods=['POST'])
def generate_marketing_strategy():
    """Generate a marketing strategy from a completed report."""
    try:
        data = request.get_json() or {}
        report_id = data.get('report_id')
        if not report_id:
            return jsonify({'success': False, 'error': 'Please provide report_id'}), 400

        report = ReportManager.get_report(report_id)
        if not report:
            return jsonify({'success': False, 'error': f'Report not found: {report_id}'}), 404
        if report.status != ReportStatus.COMPLETED:
            return jsonify({'success': False, 'error': 'Marketing strategy generation requires a completed report'}), 400

        force_regenerate = data.get('force_regenerate', False)
        if not force_regenerate:
            existing_strategy = MarketingStrategyManager.get_strategy_by_report(report_id)
            if existing_strategy and existing_strategy.status == StrategyStatus.COMPLETED:
                return jsonify({
                    'success': True,
                    'data': {
                        'report_id': report_id,
                        'strategy_id': existing_strategy.strategy_id,
                        'simulation_id': existing_strategy.simulation_id,
                        'status': 'completed',
                        'message': 'Marketing strategy already exists',
                        'already_generated': True,
                    },
                })

        storage = current_app.extensions.get('neo4j_storage')
        if not storage:
            return jsonify({'success': False, 'error': 'Neo4j storage not initialized'}), 503

        import uuid

        strategy_id = f'strategy_{uuid.uuid4().hex[:12]}'
        task_manager = TaskManager()
        task_id = task_manager.create_task(
            task_type='marketing_strategy_generate',
            metadata={
                'report_id': report_id,
                'strategy_id': strategy_id,
                'simulation_id': report.simulation_id,
                'graph_id': report.graph_id,
            },
        )
        graph_tools = GraphToolsService(storage=storage)

        def run_generate():
            try:
                task_manager.update_task(
                    task_id,
                    status=TaskStatus.PROCESSING,
                    progress=0,
                    message='Initializing Marketing Strategy Agent...',
                )

                agent = MarketingStrategyAgent(
                    graph_id=report.graph_id,
                    simulation_id=report.simulation_id,
                    simulation_requirement=report.simulation_requirement,
                    report_id=report.report_id,
                    source_report_markdown=report.markdown_content,
                    graph_tools=graph_tools,
                )

                def progress_callback(stage, progress, message):
                    task_manager.update_task(task_id, progress=progress, message=f'[{stage}] {message}')

                strategy = agent.generate_strategy(progress_callback=progress_callback, strategy_id=strategy_id)
                MarketingStrategyManager.save_strategy(strategy)

                if strategy.status == StrategyStatus.COMPLETED:
                    task_manager.complete_task(
                        task_id,
                        result={
                            'strategy_id': strategy.strategy_id,
                            'report_id': report_id,
                            'simulation_id': report.simulation_id,
                            'status': 'completed',
                        },
                    )
                else:
                    task_manager.fail_task(task_id, strategy.error or 'Marketing strategy generation failed')

            except Exception as error:
                logger.error(f'Marketing strategy generation failed: {error}')
                task_manager.fail_task(task_id, str(error))

        thread = threading.Thread(target=run_generate, daemon=True)
        thread.start()

        return jsonify({
            'success': True,
            'data': {
                'report_id': report_id,
                'strategy_id': strategy_id,
                'task_id': task_id,
                'status': 'generating',
                'message': 'Marketing strategy generation task started',
                'already_generated': False,
            },
        })

    except Exception as error:
        logger.error(f'Failed to start marketing strategy generation task: {error}')
        return jsonify({
            'success': False,
            'error': str(error),
            'traceback': traceback.format_exc(),
        }), 500


@marketing_strategy_bp.route('/generate/status', methods=['POST'])
def get_marketing_strategy_generate_status():
    """Query marketing strategy generation task progress."""
    try:
        data = request.get_json() or {}
        task_id = data.get('task_id')
        report_id = data.get('report_id')

        if report_id:
            existing_strategy = MarketingStrategyManager.get_strategy_by_report(report_id)
            if existing_strategy and existing_strategy.status == StrategyStatus.COMPLETED:
                return jsonify({
                    'success': True,
                    'data': {
                        'report_id': report_id,
                        'strategy_id': existing_strategy.strategy_id,
                        'status': 'completed',
                        'progress': 100,
                        'message': 'Marketing strategy has been generated',
                        'already_completed': True,
                    },
                })

        if not task_id:
            return jsonify({'success': False, 'error': 'Please provide task_id or report_id'}), 400

        task_manager = TaskManager()
        task = task_manager.get_task(task_id)
        if not task:
            return jsonify({'success': False, 'error': f'Task not found: {task_id}'}), 404

        return jsonify({'success': True, 'data': task.to_dict()})

    except Exception as error:
        logger.error(f'Failed to query marketing strategy task status: {error}')
        return jsonify({'success': False, 'error': str(error)}), 500


@marketing_strategy_bp.route('/<strategy_id>', methods=['GET'])
def get_marketing_strategy(strategy_id: str):
    """Get marketing strategy details."""
    try:
        strategy = MarketingStrategyManager.get_strategy(strategy_id)
        if not strategy:
            return jsonify({'success': False, 'error': f'Marketing strategy not found: {strategy_id}'}), 404
        return jsonify({'success': True, 'data': strategy.to_dict()})
    except Exception as error:
        logger.error(f'Failed to get marketing strategy: {error}')
        return jsonify({'success': False, 'error': str(error), 'traceback': traceback.format_exc()}), 500


@marketing_strategy_bp.route('/by-report/<report_id>', methods=['GET'])
def get_marketing_strategy_by_report(report_id: str):
    """Get marketing strategy by source report ID."""
    try:
        strategy = MarketingStrategyManager.get_strategy_by_report(report_id)
        if not strategy:
            return jsonify({
                'success': False,
                'error': f'No marketing strategy available for report: {report_id}',
                'has_strategy': False,
            }), 404
        return jsonify({'success': True, 'data': strategy.to_dict(), 'has_strategy': True})
    except Exception as error:
        logger.error(f'Failed to get marketing strategy by report: {error}')
        return jsonify({'success': False, 'error': str(error), 'traceback': traceback.format_exc()}), 500


@marketing_strategy_bp.route('/<strategy_id>/agent-log', methods=['GET'])
def get_marketing_strategy_agent_log(strategy_id: str):
    """Get incremental agent log for a marketing strategy."""
    try:
        from_line = request.args.get('from_line', 0, type=int)
        return jsonify({'success': True, 'data': MarketingStrategyManager.get_agent_log(strategy_id, from_line=from_line)})
    except Exception as error:
        logger.error(f'Failed to get marketing strategy agent log: {error}')
        return jsonify({'success': False, 'error': str(error), 'traceback': traceback.format_exc()}), 500


@marketing_strategy_bp.route('/<strategy_id>/console-log', methods=['GET'])
def get_marketing_strategy_console_log(strategy_id: str):
    """Get incremental console log for a marketing strategy."""
    try:
        from_line = request.args.get('from_line', 0, type=int)
        return jsonify({'success': True, 'data': MarketingStrategyManager.get_console_log(strategy_id, from_line=from_line)})
    except Exception as error:
        logger.error(f'Failed to get marketing strategy console log: {error}')
        return jsonify({'success': False, 'error': str(error), 'traceback': traceback.format_exc()}), 500