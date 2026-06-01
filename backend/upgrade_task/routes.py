from flask import Blueprint
from flask_jwt_extended import jwt_required, get_jwt_identity
from webargs import fields, validate
from webargs.flaskparser import use_args
from datetime import datetime
from backend.user.schema import pagination_args # 复用分页参数
from backend.upgrade_task.service import upgrade_task_service
from flask import current_app, send_file
from backend.common.exceptions import InvalidUsageError, ResourceNotFoundError
from backend.common.response import response_data
from backend.upgrade_task.schema import upgrade_task_schema,upgrade_task_create_schema,device_mapping_schema,upgrade_task_update_schema,\
    upgrade_task_batch_delete_schema,upgrade_task_batch_delete_result_schema,upgrade_task_list_query_args, device_mappings_query_args, device_confirm_upgrade_update_schema, device_confirm_upgrade_update_result_schema
from backend.common.jwt_util import require_permissions
# 创建升级任务蓝图
upgrade_task_bp = Blueprint('upgrade_task', __name__, url_prefix='/api/upgrade-tasks')



@upgrade_task_bp.route('', methods=['POST'])
@jwt_required()
@use_args(upgrade_task_create_schema, location="json")
@require_permissions('UpgradeTask')
def create_upgrade_task_route(args):
    """创建升级任务"""
    try:
        # 添加创建人ID
        args['creator_id'] = get_jwt_identity()

        # 调用服务层创建升级任务
        new_task = upgrade_task_service.create_upgrade_task(args)

        return response_data(data=new_task, schema=upgrade_task_schema), 201

    except (InvalidUsageError, ResourceNotFoundError) as e:                                          
        # 捕获已知的业务逻辑错误，并直接重新抛出
        # 全局错误处理器会把它格式化成正确的JSON
        raise e
    except Exception as e:
        # 只捕获真正的未知错误
        raise InvalidUsageError(f"Failed to create upgrade task: {e}")




@upgrade_task_bp.route('', methods=['GET'])
@jwt_required()
@use_args(upgrade_task_list_query_args, location="query")
@require_permissions('UpgradeTask')
def get_upgrade_tasks(args):
    """获取升级任务列表（支持筛选、排序和分页）"""
    try:
        page = args['page']
        per_page = args['per_page']
        # 提取筛选参数（去除分页和排序参数）
        filter_params = {k: v for k, v in args.items() if k not in ['page', 'per_page', 'sort_by', 'sort_order'] and v is not None}
        sort_by = args.get('sort_by')
        sort_order = args.get('sort_order')
        paged_tasks = upgrade_task_service.get_paged_upgrade_tasks(page, per_page, filter_params, sort_by, sort_order)
        return response_data(data=paged_tasks, schema=upgrade_task_schema)
    except Exception as e:
        raise InvalidUsageError(f"Failed to get upgrade task list: {e}")


@upgrade_task_bp.route('/<string:task_id>/devices', methods=['GET'])
@jwt_required()
@use_args(device_mappings_query_args, location="query")
@require_permissions('UpgradeTask')
def get_task_device_mappings(args, task_id):
    """获取升级任务相关的所有设备映射记录"""
    try:
        mappings = upgrade_task_service.get_task_device_mappings(task_id, args)
        return response_data(data=mappings, schema=device_mapping_schema, many=True)
    except ResourceNotFoundError as e:
        raise e
    except Exception as e:
        raise InvalidUsageError(f"Failed to get task device mapping: {e}")


@upgrade_task_bp.route('/<string:task_id>/devices/confirm-upgrade', methods=['PATCH','PUT'])
@jwt_required()
@use_args(device_confirm_upgrade_update_schema, location="json")
@require_permissions('UpgradeTask')
def update_devices_confirm_upgrade(args, task_id):
    """批量更新指定任务下的一组 device_ids 的 confirm_upgrade 值。"""
    try:
        result = upgrade_task_service.update_devices_confirm_upgrade(
            task_id=task_id,
            device_ids=args['device_ids'],
            confirm_upgrade=args['confirm_upgrade']
        )
        return response_data(data=result, schema=device_confirm_upgrade_update_result_schema)
    except (InvalidUsageError, ResourceNotFoundError) as e:
        raise e
    except Exception as e:
        raise InvalidUsageError(f"Failed to update task device upgrade confirmation: {e}")


@upgrade_task_bp.route('/<string:task_id>', methods=['DELETE'])
@jwt_required()
@require_permissions('UpgradeTask')
def delete_upgrade_task(task_id):
    """删除升级任务（逻辑删除）"""
    try:
        upgrade_task_service.delete_upgrade_task(task_id)
        return response_data(data={"message": "Upgrade task deleted successfully"}, schema={})
    except ResourceNotFoundError as e:
        raise e
    except Exception as e:
        raise InvalidUsageError(f"Failed to delete upgrade task, unknown error occurred: {e}")


# --- 新增：升级任务 update、批量删除、导出 API ---
@upgrade_task_bp.route('/<string:task_id>', methods=['PUT', 'PATCH'])
@jwt_required()
@use_args(upgrade_task_update_schema, location="json")
@require_permissions('UpgradeTask')
def update_upgrade_task(args, task_id):
    """更新升级任务信息"""
    try:
        updated_task = upgrade_task_service.update_upgrade_task(task_id, args)
        return response_data(data=updated_task, schema=upgrade_task_schema)
    except ResourceNotFoundError as e:
        raise e
    except Exception as e:
        raise InvalidUsageError(f"Failed to update upgrade task: {e}")


@upgrade_task_bp.route('/batch-delete', methods=['POST'])
@jwt_required()
@use_args(upgrade_task_batch_delete_schema, location="json")
@require_permissions('UpgradeTask')
def batch_delete_upgrade_tasks(args):
    """批量删除升级任务"""
    try:
        result = upgrade_task_service.delete_upgrade_tasks_batch(args['ids'])
        return response_data(data=result, schema=upgrade_task_batch_delete_result_schema)
    except Exception as e:
        raise InvalidUsageError(f"Failed to batch delete upgrade tasks: {e}")



@upgrade_task_bp.route('/export', methods=['GET'])
@jwt_required()
@use_args(upgrade_task_list_query_args, location="query")
@require_permissions('UpgradeTask')
def export_upgrade_tasks(args):
    """导出升级任务为Excel文件"""
    sort_by = args.get('sort_by', 'created_at')
    sort_order = args.get('sort_order', 'asc')
    filter_params = {k: v for k, v in args.items() if k not in ['page', 'per_page', 'sort_by', 'sort_order'] and v is not None}

    try:
        filter_params = {k: v for k, v in args.items() if v is not None}
        excel_buffer, filename = upgrade_task_service.export_upgrade_tasks(filter_params, sort_by, sort_order)
        return send_file(
            excel_buffer,
            as_attachment=True,
            download_name=filename,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
    except Exception as e:
        current_app.logger.error(f"导出升级任务时发生错误: {e}")
        raise InvalidUsageError(f"Export failed, unknown error occurred: {e}")
