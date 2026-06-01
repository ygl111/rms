from flask import Blueprint, send_file
from flask_jwt_extended import jwt_required
from webargs.flaskparser import use_args

from backend.upgrade_record.service import upgrade_record_service
from backend.common.exceptions import InvalidUsageError, ResourceNotFoundError
from backend.common.response import response_data
from backend.upgrade_record.schema import (
    upgrade_record_schema,
    upgrade_record_list_query_args,
    upgrade_record_batch_delete_schema,
    upgrade_record_batch_delete_result_schema,
)
from backend.common.jwt_util import require_permissions


upgrade_record_bp = Blueprint('upgrade_record', __name__, url_prefix='/api/upgrade-records')


@upgrade_record_bp.route('', methods=['GET'])
@jwt_required()
@use_args(upgrade_record_list_query_args, location="query")
@require_permissions('UpgradeRecord')
def get_upgrade_records(args):
    """获取升级记录列表（分页/筛选/排序）"""
    try:
        page = args['page']
        per_page = args['per_page']
        filter_params = {k: v for k, v in args.items() if k not in ['page', 'per_page', 'sort_by', 'sort_order'] and v is not None}
        sort_by = args.get('sort_by')
        sort_order = args.get('sort_order')

        paged_records = upgrade_record_service.get_paged_upgrade_records(page, per_page, filter_params, sort_by, sort_order)
        return response_data(data=paged_records, schema=upgrade_record_schema)
    except Exception as e:
        raise InvalidUsageError(f"Failed to get upgrade record list: {e}")


@upgrade_record_bp.route('/<string:record_id>', methods=['DELETE'])
@jwt_required()
@require_permissions('UpgradeRecord')
def delete_upgrade_record(record_id):
    """删除升级记录（逻辑删除）"""
    try:
        upgrade_record_service.delete_upgrade_record(record_id)
        return response_data(data={"message": "Deleted successfully"}, schema={})
    except ResourceNotFoundError as e:
        raise e
    except Exception as e:
        raise InvalidUsageError(f"Failed to delete upgrade record, unknown error occurred: {e}")


@upgrade_record_bp.route('/batch-delete', methods=['DELETE'])
@jwt_required()
@use_args(upgrade_record_batch_delete_schema, location="json")
@require_permissions('UpgradeRecord')
def delete_upgrade_records_batch(args):
    """批量删除升级记录（逻辑删除）"""
    try:
        result = upgrade_record_service.delete_upgrade_records_batch(args['ids'])
        return response_data(data=result, schema=upgrade_record_batch_delete_result_schema)
    except InvalidUsageError as e:
        raise e
    except Exception as e:
        raise InvalidUsageError(f"Failed to batch delete upgrade records: {e}")


@upgrade_record_bp.route('/export', methods=['GET'])
@jwt_required()
@use_args(upgrade_record_list_query_args, location="query")
@require_permissions('UpgradeRecord')
def export_upgrade_records(args):
    """导出升级记录数据为Excel（支持筛选和排序）"""
    sort_by = args.get('sort_by', 'created_at')
    sort_order = args.get('sort_order', 'desc')
    filter_params = {k: v for k, v in args.items() if k not in ['page', 'per_page', 'sort_by', 'sort_order'] and v is not None}

    try:
        excel_buffer, filename = upgrade_record_service.export_upgrade_records(filter_params, sort_by, sort_order)
        return send_file(
            excel_buffer,
            as_attachment=True,
            download_name=filename,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
    except Exception as e:
        raise InvalidUsageError(f"Failed to export upgrade record data: {e}")


