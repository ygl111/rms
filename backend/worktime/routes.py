from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required
from webargs.flaskparser import use_args
from backend.worktime.service import worktime_service
from backend.common.exceptions import InvalidUsageError, ResourceNotFoundError
from backend.common.response import response_data
from backend.worktime.schema import (
    worktime_detail_schema,
    worktime_detail_list_query_args,
    worktime_detail_update_schema,
    worktime_day_schema,
    worktime_day_list_query_args,
    worktime_month_schema,
    worktime_month_list_query_args,
    worktime_range_query_args,
    worktime_range_schema
)
from backend.common.jwt_util import require_permissions

# 创建蓝图对象
worktime_bp = Blueprint('worktime', __name__, url_prefix='/api/worktime')


# ==================== DeviceWorkTimeDetail 路由 ====================

@worktime_bp.route('/details', methods=['GET'])
@jwt_required()
@use_args(worktime_detail_list_query_args, location="query")
def get_worktime_details(args):
    """获取工作时间详情列表（支持筛选、排序和分页）"""
    # 从参数中提取分页信息
    page = args['page']
    per_page = args['per_page']
    
    # 提取筛选条件（移除分页和排序参数）
    filter_params = {k: v for k, v in args.items() 
                    if k not in ['page', 'per_page', 'sort_by', 'sort_order'] and v is not None}
    
    # 提取排序信息
    sort_by = args.get('sort_by')
    sort_order = args.get('sort_order')
    
    # 调用服务层获取筛选、排序后的分页数据
    paged_details = worktime_service.get_paged_worktime_details(
        page, per_page, filter_params, sort_by, sort_order
    )
    
    return response_data(data=paged_details, schema=worktime_detail_schema)


# @worktime_bp.route('/details/<string:detail_id>', methods=['PUT', 'PATCH'])
# @jwt_required()
# @use_args(worktime_detail_update_schema, location="json")
# @require_permissions('WorkTimeManagement')
# def update_worktime_detail(args, detail_id):
#     """更新工作时间详情记录"""
#     try:
#         # args 就是经过 worktime_detail_update_schema 验证和处理后的数据
#         updated_detail = worktime_service.update_worktime_detail(detail_id, args)
#         # 使用 worktime_detail_schema (输出模板) 来序列化返回的数据
#         return response_data(data=updated_detail, schema=worktime_detail_schema)
#     except ResourceNotFoundError as e:
#         raise e
#     except Exception as e:
#         # 捕获其他可能的未知错误
#         current_app.logger.error(f"更新工作时间详情记录时发生错误: {e}")
#         raise InvalidUsageError(f"Update failed, unknown error occurred: {e}")


# @worktime_bp.route('/details/<string:detail_id>', methods=['DELETE'])
# @jwt_required()
# @require_permissions('WorkTimeManagement')
# def delete_worktime_detail(detail_id):
#     """删除工作时间详情记录（逻辑删除）"""
#     try:
#         worktime_service.delete_worktime_detail(detail_id)
#         return jsonify({"message": "WorkTime detail record deleted successfully"}), 200
#     except ResourceNotFoundError as e:
#         raise e
#     except Exception as e:
#         current_app.logger.error(f"删除工作时间详情记录时发生错误: {e}")
#         raise InvalidUsageError(f"Deletion failed, unknown error occurred: {e}")


# ==================== DeviceWorkTimeDay 路由 ====================

@worktime_bp.route('/days', methods=['GET'])
@jwt_required()
@use_args(worktime_day_list_query_args, location="query")
def get_worktime_days(args):
    """获取工作时间日汇总列表（支持筛选、排序和分页）"""
    # 从参数中提取分页信息
    page = args['page']
    per_page = args['per_page']
    
    # 提取筛选条件（移除分页和排序参数）
    filter_params = {k: v for k, v in args.items() 
                    if k not in ['page', 'per_page', 'sort_by', 'sort_order'] and v is not None}
    
    # 提取排序信息
    sort_by = args.get('sort_by')
    sort_order = args.get('sort_order')
    
    # 调用服务层获取筛选、排序后的分页数据
    paged_days = worktime_service.get_paged_worktime_days(
        page, per_page, filter_params, sort_by, sort_order
    )
    
    return response_data(data=paged_days, schema=worktime_day_schema)


# ==================== DeviceWorkTimeMonth 路由 ====================

@worktime_bp.route('/months', methods=['GET'])
@jwt_required()
@use_args(worktime_month_list_query_args, location="query")
def get_worktime_months(args):
    """获取工作时间月汇总列表（支持筛选、排序和分页）"""
    # 从参数中提取分页信息
    page = args['page']
    per_page = args['per_page']
    
    # 提取筛选条件（移除分页和排序参数）
    filter_params = {k: v for k, v in args.items() 
                    if k not in ['page', 'per_page', 'sort_by', 'sort_order'] and v is not None}
    
    # 提取排序信息
    sort_by = args.get('sort_by')
    sort_order = args.get('sort_order')
    
    # 调用服务层获取筛选、排序后的分页数据
    paged_months = worktime_service.get_paged_worktime_months(
        page, per_page, filter_params, sort_by, sort_order
    )
    
    return response_data(data=paged_months, schema=worktime_month_schema)


# ==================== DeviceWorkTimeRange 路由 ====================

@worktime_bp.route('/range', methods=['GET'])
@jwt_required()
@use_args(worktime_range_query_args, location="query")
def get_worktime_by_date_range(args):
    """获取指定日期范围内每个设备的总有效工作时间（支持分页和排序）"""
    # 提取分页参数
    page = args['page']
    per_page = args['per_page']
    
    # 提取筛选参数
    start_date = args.get('start_date')
    end_date = args.get('end_date')
    device_id = args.get('device_id')
    
    # 提取排序参数
    sort_by = args.get('sort_by')
    sort_order = args.get('sort_order')
    
    # 调用服务层获取分页数据
    paged_results = worktime_service.get_worktime_by_date_range(
        start_date, end_date, device_id, page, per_page, sort_by, sort_order
    )
    
    # 返回分页数据
    return response_data(data=paged_results, schema=worktime_range_schema)
