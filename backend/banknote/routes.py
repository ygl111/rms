from flask import Blueprint, jsonify, Response, stream_with_context
from flask_jwt_extended import jwt_required
from webargs import fields
from webargs.flaskparser import use_args, use_kwargs
from backend.banknote.schema import banknote_count_list_item_schema, detailed_data_schema, currency_schema, \
    banknote_count_list_query_args, chart_query_args, analytics_response_schema, summary_stats_schema
from backend.banknote.service import banknote_service
from backend.common.response import response_data
from backend.common.exceptions import ResourceNotFoundError
from backend.user.schema import pagination_args # 复用分页参数
from backend.common.jwt_util import require_permissions

banknote_bp = Blueprint('banknote', __name__, url_prefix='/api/banknote')


# --- Routes ---

@banknote_bp.route('', methods=['GET'])
@jwt_required()
@use_args(banknote_count_list_query_args, location="query")
@require_permissions('BanknoteManagement')
def get_all_counts(args):
    """1. 获取所有BanknoteCount记录（分页/筛选/排序）"""
    page = args['page']
    per_page = args['per_page']
    filter_params = {k: v for k, v in args.items() if k not in ['page', 'per_page', 'sort_by', 'sort_order'] and v is not None}
    sort_by = args.get('sort_by', 'count_time')
    sort_order = args.get('sort_order', 'desc')
    paged_counts = banknote_service.get_paged_banknote_counts(page, per_page, filter_params, sort_by, sort_order)
    return response_data(data=paged_counts, schema=banknote_count_list_item_schema)


@banknote_bp.route('/export-detailed', methods=['GET'])
@jwt_required()
@use_args(banknote_count_list_query_args, location="query")
@require_permissions('BanknoteManagement')
def export_detailed(args):
    """导出筛选/排序后的明细数据（BanknoteDetailedData，CSV流式）"""
    filter_params = {k: v for k, v in args.items() if k not in ['page', 'per_page', 'sort_by', 'sort_order'] and v is not None}
    sort_by = args.get('sort_by', 'count_time')
    sort_order = args.get('sort_order', 'desc')

    csv_stream, filename = banknote_service.export_banknote_detailed_data_csv(filter_params, sort_by, sort_order)
    response = Response(
        stream_with_context(csv_stream),
        mimetype='text/csv; charset=utf-8'
    )
    response.headers['Content-Disposition'] = f'attachment; filename={filename}'
    return response


@banknote_bp.route('/analytics', methods=['GET'])
@jwt_required()
@use_args(chart_query_args, location="query")
@require_permissions('BanknoteManagement')
def analytics(args):
    """在筛选条件基础上，进行分组聚合，返回绘图所需数据（value 为选定指标的聚合值）。"""
    result = banknote_service.get_chart_data(args)
    return response_data(data=result, schema=analytics_response_schema)

@banknote_bp.route('/currency/<string:count_id>', methods=['GET'])
@jwt_required()
@require_permissions('BanknoteManagement')
def get_currencies_for_count(count_id):
    """2. 获取单个BanknoteCount关联的所有Currencies"""
    try:
        currencies = banknote_service.get_currencies_by_count_id(count_id)
        # 对于列表，我们直接序列化
        return response_data(data=currencies, schema=currency_schema, many=True)
    except ResourceNotFoundError as e:
        raise e

@banknote_bp.route('/detail/<string:count_id>', methods=['GET'])
@jwt_required()
@require_permissions('BanknoteManagement')
def get_details_for_count(count_id):
    """3. 获取单个BanknoteCount关联的所有DetailedData"""
    try:
        details = banknote_service.get_detailed_data_by_count_id(count_id)
        return response_data(data=details, schema=detailed_data_schema, many=True)
    except ResourceNotFoundError as e:
        raise e

@banknote_bp.route('/<string:count_id>', methods=['DELETE'])
@jwt_required()
@require_permissions('BanknoteManagement')
def delete_count(count_id):
    """4. 逻辑删除一条BanknoteCount"""
    try:
        banknote_service.delete_banknote_count(count_id)
        return jsonify({"message": "Record deleted successfully"}), 200
    except ResourceNotFoundError as e:
        raise e

#-------------------------------此部分为新api的主从库分离示例----------------------------------
@banknote_bp.route('/stats/summary', methods=['GET'])
@jwt_required()
@require_permissions('BanknoteManagement')
def summary_stats():
    """获取 overview 统计概览（走从库查询 / 失败降级主库）"""
    stats = banknote_service.get_summary_stats()
    return response_data(data=stats, schema=summary_stats_schema)
#---------------------------------------------------------------------------------------------