from flask import Blueprint, jsonify, current_app, send_file, request
from flask_jwt_extended import jwt_required
from webargs import fields, validate
from webargs.flaskparser import use_args

from backend.institution.service import institution_service
from backend.common.exceptions import DuplicateResourceError, InvalidUsageError, ResourceNotFoundError
from backend.common.response import response_data
from backend.institution.schema import institution_schema,institution_create_schema,institution_update_schema,\
    institution_tree_schema,institution_list_query_args,institution_children_query_args,institution_export_query_args,\
        institution_batch_import_preview_schema,institution_batch_import_confirm_schema,institution_batch_import_result_schema
from backend.common.jwt_util import require_permissions


# 创建蓝图
institution_bp = Blueprint('institution', __name__, url_prefix='/api/institutions')




# --- Routes ---

@institution_bp.route('', methods=['POST'])
@jwt_required()
@use_args(institution_create_schema, location="json")
@require_permissions('OrgManagement')
def create_institution(args):
    """创建新机构"""
    try:
        new_institution = institution_service.create_institution(args)
        return response_data(data=new_institution, schema=institution_schema), 201
    except DuplicateResourceError as e:
        raise e
    except Exception as e:
        raise InvalidUsageError(f"Failed to create institution, unknown error occurred: {e}")

@institution_bp.route('', methods=['GET'])
@jwt_required()
@use_args(institution_list_query_args, location="query")
def get_institutions(args):
    """获取机构列表（支持筛选、排序和分页）"""
    # 提取分页参数
    page = args['page']
    per_page = args['per_page']
    # 提取排序参数
    sort_by = args['sort_by']
    sort_order = args['sort_order']
    # 提取筛选参数（去除分页和排序参数）
    filter_params = {k: v for k, v in args.items() 
                    if k not in ['page', 'per_page', 'sort_by', 'sort_order'] and v is not None}
    # 调用服务层获取分页数据
    paged_institutions = institution_service.get_paged_institutions(page, per_page, filter_params, sort_by, sort_order)
    return response_data(data=paged_institutions, schema=institution_schema)

@institution_bp.route('/tree', methods=['GET'])
@jwt_required()
def get_institution_tree():
    """获取机构树结构"""
    try:
        institution_tree = institution_service.get_institution_tree()
        return response_data(data=institution_tree, schema=institution_tree_schema, many=True)
    except Exception as e:
        raise InvalidUsageError(f"Failed to get institution tree, unknown error occurred: {e}")

@institution_bp.route('/<string:institution_id>/children', methods=['GET'])
@jwt_required()
@use_args(institution_children_query_args, location="query")
def get_institution_children(args, institution_id):
    """获取指定机构的所有子机构（分页）"""
    try:
        # 提取分页参数
        page = args['page']
        per_page = args['per_page']
        # 提取排序参数
        sort_by = args.get('sort_by', 'created_at')
        sort_order = args.get('sort_order', 'desc')
        # 调用服务层获取子机构分页数据
        paged_children = institution_service.get_institution_children(institution_id, page, per_page, sort_by, sort_order)
        return response_data(data=paged_children, schema=institution_schema)
    except ResourceNotFoundError as e:
        raise e
    except Exception as e:
        raise InvalidUsageError(f"Failed to get child institutions, unknown error occurred: {e}")


@institution_bp.route('/<string:institution_id>', methods=['PUT', 'PATCH'])
@jwt_required()
@use_args(institution_update_schema, location="json")
@require_permissions('OrgManagement')
def update_institution(args, institution_id):
    """更新机构信息"""
    try:
        updated_institution = institution_service.update_institution(institution_id, args)
        return response_data(data=updated_institution, schema=institution_schema)
    except (ResourceNotFoundError, DuplicateResourceError,InvalidUsageError) as e:
        raise e
    except Exception as e:
        raise InvalidUsageError(f"Failed to update institution, unknown error occurred: {e}")

@institution_bp.route('/<string:institution_id>', methods=['DELETE'])
@jwt_required()
@require_permissions('OrgManagement')
def delete_institution(institution_id):
    """删除机构（逻辑删除）"""
    try:
        institution_service.delete_institution(institution_id)
        return jsonify({"message": "Institution deleted successfully"}), 200
    except ResourceNotFoundError as e:
        raise e
    except Exception as e:
        raise InvalidUsageError(f"Failed to delete institution, unknown error occurred: {e}")

@institution_bp.route('/export', methods=['GET'])
@jwt_required()
@use_args(institution_export_query_args, location="query")
@require_permissions('OrgManagement')
def export_institutions(args):
    """导出机构数据为Excel文件"""
    try:
        # 提取排序参数
        sort_by = args.get('sort_by', 'level')
        sort_order = args.get('sort_order', 'desc')
        # 提取筛选参数（去除空值和排序参数）
        filter_params = {k: v for k, v in args.items() if v is not None and k not in ['sort_by', 'sort_order']}
        # 调用服务层获取Excel文件
        excel_buffer, filename = institution_service.export_institutions(filter_params, sort_by, sort_order)
        # 返回Excel文件
        return send_file(
            excel_buffer,
            as_attachment=True,
            download_name=filename,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
    except Exception as e:
        # 捕获其他可能的未知错误，并记录日志
        current_app.logger.error(f"导出机构数据时发生错误: {e}")
        raise InvalidUsageError(f"Export failed, unknown error occurred: {e}")

@institution_bp.route('/batch-import/preview', methods=['POST'])
@jwt_required()
@require_permissions('OrgManagement')
def batch_import_preview():
    """
    批量导入机构 - 第一步：预览Excel文件内容
    前端上传Excel文件，后端解析并返回可导入和不可导入的记录统计
    """
    try:
        # 检查是否有上传的文件
        if 'file' not in request.files:
            raise InvalidUsageError("Please upload an Excel file.")
        
        file = request.files['file']
        if file.filename == '':
            raise InvalidUsageError("No file selected.")
        
        # 检查文件类型
        if not file.filename.lower().endswith(('.xlsx', '.xls')):
            raise InvalidUsageError("Only Excel file format is supported (.xlsx or .xls).")
        
        # 调用服务层处理Excel文件
        result = institution_service.preview_batch_import(file)
        
        # 使用response_data统一返回格式
        return response_data(data=result, schema=institution_batch_import_preview_schema), 200
        
    except InvalidUsageError as e:
        raise e
    except Exception as e:
        current_app.logger.error(f"批量导入预览时发生错误: {e}")
        raise InvalidUsageError(f"File parsing failed, unknown error occurred: {e}")

@institution_bp.route('/batch-import/confirm', methods=['POST'])
@jwt_required()
@require_permissions('OrgManagement')
@use_args(institution_batch_import_confirm_schema, location="json")
def batch_import_confirm(args):
    """
    批量导入机构 - 第二步：确认导入
    根据缓存键从Redis获取数据，执行实际的导入操作
    """
    try:
        # 从验证后的参数中获取导入令牌
        import_token = args['import_token']
        
        # 调用服务层执行导入
        result = institution_service.confirm_batch_import(import_token)
        
        # 如果有失败记录的Excel文件，返回文件下载
        if result.get('has_failed_file') and 'excel_buffer' in result:
            excel_buffer = result['excel_buffer']
            filename = result['filename']
            
            # 返回Excel文件下载
            return send_file(
                excel_buffer,
                as_attachment=True,
                download_name=filename,
                mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            )
        else:
            # 没有失败记录，返回JSON结果
            return response_data(data=result, schema=institution_batch_import_result_schema), 200
        
    except InvalidUsageError as e:
        raise e
    except Exception as e:
        current_app.logger.error(f"批量导入确认时发生错误: {e}")
        raise InvalidUsageError(f"Batch import failed, unknown error occurred: {e}")

@institution_bp.route('/batch-import/template', methods=['GET'])
@jwt_required()
@require_permissions('OrgManagement')
def download_import_template():
    """
    下载机构批量导入的Excel模板文件
    返回包含标准表头的空Excel文件
    """
    try:
        # 调用服务层生成模板文件
        excel_buffer, filename = institution_service.create_import_template()
        
        # 返回Excel文件下载
        return send_file(
            excel_buffer,
            as_attachment=True,
            download_name=filename,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        
    except Exception as e:
        current_app.logger.error(f"生成导入模板时发生错误: {e}")
        raise InvalidUsageError(f"Failed to generate template, unknown error occurred: {e}")
