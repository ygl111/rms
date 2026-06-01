from flask import Blueprint, send_file
from flask_jwt_extended import jwt_required, get_jwt_identity
from webargs.flaskparser import use_args
from backend.common.jwt_util import require_permissions
from backend.fault.service import fault_service
from backend.common.exceptions import InvalidUsageError, ResourceNotFoundError
from backend.common.response import response_data
from backend.fault.schema import (
    fault_schema,
    non_fault_device_schema,
    fault_list_query_args,
    fault_batch_delete_schema,
    fault_batch_delete_result_schema,
    fault_update_status_schema,
    fault_log_schema,
    fault_log_create_schema,
    fault_log_list_query_args,
)


fault_bp = Blueprint('fault', __name__, url_prefix='/api/faults')


@fault_bp.route('', methods=['GET'])
@jwt_required()
@require_permissions(['FaultList', 'FaultLogList'], mode='any')
@use_args(fault_list_query_args, location="query")
def get_faults(args):
    """获取故障列表（分页/筛选/排序）"""
    try:
        page = args['page']
        per_page = args['per_page']
        filter_params = {k: v for k, v in args.items() if k not in ['page', 'per_page', 'sort_by', 'sort_order'] and v is not None}
        sort_by = args.get('sort_by')
        sort_order = args.get('sort_order')

        paged_faults = fault_service.get_paged_faults(page, per_page, filter_params, sort_by, sort_order)
        return response_data(data=paged_faults, schema=fault_schema)
    except Exception as e:
        raise InvalidUsageError(f"Failed to get fault list: {e}")


@fault_bp.route('/non-fault-devices', methods=['GET'])
@jwt_required()
@require_permissions(['FaultList', 'FaultLogList'], mode='any')
def get_non_fault_devices():
    """获取非故障设备列表（在线/离线设备中排除未维修和维修中的故障设备）。"""
    try:
        devices = fault_service.get_non_fault_devices()
        return response_data(data=devices, schema=non_fault_device_schema, many=True)
    except Exception as e:
        raise InvalidUsageError(f"Failed to get non-fault devices: {e}")


@fault_bp.route('/fault-devices', methods=['GET'])
@jwt_required()
@require_permissions(['FaultList', 'FaultLogList'], mode='any')
def get_fault_devices():
    """获取故障设备列表（故障状态为未处理或处理中）。"""
    try:
        devices = fault_service.get_fault_devices()
        return response_data(data=devices, schema=non_fault_device_schema, many=True)
    except Exception as e:
        raise InvalidUsageError(f"Failed to get fault devices: {e}")


@fault_bp.route('/<string:fault_id>/status', methods=['PUT', 'PATCH'])
@jwt_required()
@require_permissions(['FaultList', 'FaultLogList'], mode='any')
@use_args(fault_update_status_schema, location="json")
def update_fault_status(args, fault_id):
    """更新故障状态"""
    try:
        updated = fault_service.update_fault_status(fault_id, args['status'])
        return response_data(data=updated, schema=fault_schema)
    except ResourceNotFoundError as e:
        raise e
    except Exception as e:
        raise InvalidUsageError(f"Failed to update fault status, unknown error occurred: {e}")


@fault_bp.route('/<string:fault_id>', methods=['DELETE'])
@jwt_required()
@require_permissions(['FaultList', 'FaultLogList'], mode='any')
def delete_fault(fault_id):
    """删除故障（逻辑删除）"""
    try:
        fault_service.delete_fault(fault_id)
        return response_data(data={"message": "Deleted successfully"}, schema={})
    except ResourceNotFoundError as e:
        raise e
    except Exception as e:
        raise InvalidUsageError(f"Failed to delete fault, unknown error occurred: {e}")


@fault_bp.route('/batch-delete', methods=['DELETE'])
@jwt_required()
@require_permissions(['FaultList', 'FaultLogList'], mode='any')
@use_args(fault_batch_delete_schema, location="json")
def delete_faults_batch(args):
    """批量删除故障（逻辑删除）"""
    try:
        result = fault_service.delete_faults_batch(args['ids'])
        return response_data(data=result, schema=fault_batch_delete_result_schema)
    except InvalidUsageError as e:
        raise e
    except Exception as e:
        raise InvalidUsageError(f"Failed to batch delete fault logs: {e}")


@fault_bp.route('/export', methods=['GET'])
@jwt_required()
@require_permissions(['FaultList', 'FaultLogList'], mode='any')
@use_args(fault_list_query_args, location="query")
def export_faults(args):
    """导出故障数据为Excel（支持筛选和排序）"""
    sort_by = args.get('sort_by', 'fault_time')
    sort_order = args.get('sort_order', 'desc')
    filter_params = {k: v for k, v in args.items() if k not in ['page', 'per_page', 'sort_by', 'sort_order'] and v is not None}

    try:
        excel_buffer, filename = fault_service.export_faults(filter_params, sort_by, sort_order)
        return send_file(
            excel_buffer,
            as_attachment=True,
            download_name=filename,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
    except Exception as e:
        raise InvalidUsageError(f"Failed to export fault logs: {e}")


# ----- Logs -----
@fault_bp.route('/<string:fault_id>/logs', methods=['POST'])
@jwt_required()
@require_permissions(['FaultList', 'FaultLogList'], mode='any')
@use_args(fault_log_create_schema, location="json")
def create_fault_log(args, fault_id):
    try:
        operator_id = get_jwt_identity()
        log = fault_service.create_fault_log(fault_id, operator_id, args['content'])
        return response_data(data=log, schema=fault_log_schema), 201
    except (InvalidUsageError, ResourceNotFoundError) as e:
        raise e
    except Exception as e:
        raise InvalidUsageError(f"Failed to create fault log: {e}")


@fault_bp.route('/logs', methods=['GET'])
@jwt_required()
@require_permissions(['FaultList', 'FaultLogList'], mode='any')
@use_args(fault_log_list_query_args, location="query")
def get_fault_logs(args):
    try:
        page = args['page']
        per_page = args['per_page']
        filter_params = {k: v for k, v in args.items() if k not in ['page', 'per_page', 'sort_by', 'sort_order'] and v is not None}
        sort_by = args.get('sort_by')
        sort_order = args.get('sort_order')
        paged_logs = fault_service.get_paged_fault_logs(page, per_page, filter_params, sort_by, sort_order)
        return response_data(data=paged_logs, schema=fault_log_schema)
    except Exception as e:
        raise InvalidUsageError(f"Failed to get fault logs: {e}")


@fault_bp.route('/logs/<string:log_id>', methods=['DELETE'])
@jwt_required()
@require_permissions(['FaultList', 'FaultLogList'], mode='any')
def delete_fault_log(log_id):
    try:
        fault_service.delete_fault_log(log_id)
        return response_data(data={"message": "Deleted successfully"}, schema={})
    except ResourceNotFoundError as e:
        raise e
    except Exception as e:
        raise InvalidUsageError(f"Failed to delete fault log: {e}")


@fault_bp.route('/logs/batch-delete', methods=['DELETE'])
@jwt_required()
@require_permissions(['FaultList', 'FaultLogList'], mode='any')
@use_args(fault_batch_delete_schema, location="json")
def delete_fault_logs_batch(args):
    try:
        result = fault_service.delete_fault_logs_batch(args['ids'])
        return response_data(data=result, schema=fault_batch_delete_result_schema)
    except InvalidUsageError as e:
        raise e
    except Exception as e:
        raise InvalidUsageError(f"Failed to batch delete fault logs: {e}")


@fault_bp.route('/logs/export', methods=['GET'])
@jwt_required()
@require_permissions(['FaultList', 'FaultLogList'], mode='any')
@use_args(fault_log_list_query_args, location="query")
def export_fault_logs(args):
    sort_by = args.get('sort_by', 'operation_time')
    sort_order = args.get('sort_order', 'desc')
    filter_params = {k: v for k, v in args.items() if k not in ['page', 'per_page', 'sort_by', 'sort_order'] and v is not None}
    try:
        excel_buffer, filename = fault_service.export_fault_logs(filter_params, sort_by, sort_order)
        return send_file(
            excel_buffer,
            as_attachment=True,
            download_name=filename,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
    except Exception as e:
        raise InvalidUsageError(f"Failed to export fault logs: {e}")


