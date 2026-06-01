from flask import Blueprint
from flask_jwt_extended import jwt_required, get_jwt,get_jwt_identity
from dotenv import load_dotenv
import os
from webargs import fields
from webargs.flaskparser import use_args
from webargs import validate
from flask import jsonify
from flask import current_app, send_file
from backend.common.jwt_util import require_permissions
from backend.role.service import role_service
from backend.common.exceptions import DuplicateResourceError, InvalidUsageError, ResourceNotFoundError
from backend.common.response import response_data
from backend.role.schema import (
    role_schema,
    role_create_schema,
    role_update_schema,
    role_list_query_args,
    role_export_query_args,
    role_batch_delete_schema,
    role_batch_delete_result_schema,
    permission_brief_schema,
    role_permission_batch_delete_schema,
    role_permission_batch_delete_result_schema,
    role_permission_batch_add_schema,
    role_permission_batch_add_result_schema,
)
# 创建一个蓝图对象
role_bp = Blueprint('role', __name__, url_prefix='/api/roles')



@role_bp.route('', methods=['POST'])
@jwt_required()
@require_permissions('RoleManagement')
@use_args(role_create_schema, location="json")
def create_role(args):
    """创建新角色"""
    try:
        new_role = role_service.create_role(args)
        return response_data(data=new_role, schema=role_schema), 201
    except DuplicateResourceError as e:
        raise e
    except Exception as e:
        raise InvalidUsageError(f"Failed to create role, unknown error occurred: {e}")

@role_bp.route('', methods=['GET'])
@jwt_required()
@use_args(role_list_query_args, location="query")
def get_roles(args):
    """获取角色列表（支持筛选、排序和分页）"""
    # 提取分页参数
    page = args['page']
    per_page = args['per_page']
    
    # 提取筛选参数（去除分页和排序参数）
    filter_params = {k: v for k, v in args.items() 
                    if k not in ['page', 'per_page', 'sort_by', 'sort_order'] and v is not None}
    
    # 提取排序参数
    sort_by = args.get('sort_by')
    sort_order = args.get('sort_order', 'asc')
    
    # 调用服务层获取分页数据
    paged_roles = role_service.get_paged_roles(page, per_page, filter_params, sort_by, sort_order)
    
    return response_data(data=paged_roles, schema=role_schema)

@role_bp.route('/<string:role_id>', methods=['PUT', 'PATCH'])
@jwt_required()
@require_permissions('RoleManagement')
@use_args(role_update_schema, location="json")
def update_role(args, role_id):
    """更新角色信息"""
    try:
        updated_role = role_service.update_role(role_id, args)
        return response_data(data=updated_role, schema=role_schema)
    except (ResourceNotFoundError, DuplicateResourceError) as e:
        raise e
    except Exception as e:
        raise InvalidUsageError(f"Failed to update role, unknown error occurred: {e}")

@role_bp.route('/<string:role_id>', methods=['DELETE'])
@require_permissions('RoleManagement')
@jwt_required()
def delete_role(role_id):
    """删除角色（逻辑删除）"""
    try:
        role_service.delete_role(role_id)
        return jsonify({"message": "Role deleted successfully"}), 200
    except ResourceNotFoundError as e:
        raise e
    except Exception as e:
        raise InvalidUsageError(f"Failed to delete role, unknown error occurred: {e}")

@role_bp.route('/batch-delete', methods=['DELETE'])
@jwt_required()
@require_permissions('RoleManagement')
@use_args(role_batch_delete_schema, location="json")
def delete_roles_batch(args):
    """批量删除角色（逻辑删除）"""
    try:
        # 从经过验证的参数中获取角色ID列表
        role_ids = args.get('role_ids')
        
        # 调用服务层进行批量删除
        result = role_service.delete_roles_batch(role_ids)
        
        # 使用 response_data 统一返回格式，并指定 schema 进行序列化
        return response_data(
            data=result, 
            schema=role_batch_delete_result_schema
        ), 200
        
    except InvalidUsageError as e:
        raise e
    except Exception as e:
        # 捕获其他可能的未知错误，并记录日志
        current_app.logger.error(f"批量删除角色时发生错误: {e}")
        raise InvalidUsageError(f"Batch deletion failed, unknown error occurred: {e}")

@role_bp.route('/export', methods=['GET'])
@jwt_required()
@require_permissions('RoleManagement')
@use_args(role_export_query_args, location="query")
def export_roles(args):
    """导出角色数据为Excel文件"""
    try:
        # 提取筛选参数（去除空值）
        filter_params = {k: v for k, v in args.items() if v is not None}
        
        # 调用服务层获取Excel文件
        excel_buffer, filename = role_service.export_roles(filter_params)
        
        # 返回Excel文件
        return send_file(
            excel_buffer,
            as_attachment=True,
            download_name=filename,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        
    except Exception as e:
        # 捕获其他可能的未知错误，并记录日志
        current_app.logger.error(f"导出角色数据时发生错误: {e}")
        raise InvalidUsageError(f"Export failed, unknown error occurred: {e}") 

@role_bp.route('/permissions', methods=['GET'])
@jwt_required()
@require_permissions('RoleManagement')
def list_all_permissions_route():
    """获取所有未被逻辑删除的权限（仅返回 code 与 name）"""
    permissions = role_service.list_all_permissions()
    return response_data(data=permissions, schema=permission_brief_schema, many=True)

@role_bp.route('/permissions/current', methods=['GET'])
@jwt_required()
def list_current_role_permissions_route():
    # 超级管理员权限判断
    user_id = get_jwt_identity()
    load_dotenv()
    super_admin_id = os.getenv('ADMIN')
    if super_admin_id and user_id == super_admin_id:
        # 如果是超级管理员，返回所有权限
        permissions = role_service.list_all_permissions()
        return response_data(data=permissions, schema=permission_brief_schema, many=True)

    """从 JWT 中读取 role_id，返回该角色的有效权限列表"""
    claims = get_jwt()
    role_id = claims.get('role')
    permissions = role_service.list_permissions_of_role(role_id)
    return response_data(data=permissions, schema=permission_brief_schema, many=True)

@role_bp.route('/permissions/<string:role_id>', methods=['GET'])
@jwt_required()
@require_permissions('RoleManagement')
def list_role_permissions_route(role_id):
    """读取 role_id，返回该角色的有效权限列表"""
    permissions = role_service.list_permissions_of_role(role_id)
    return response_data(data=permissions, schema=permission_brief_schema, many=True)

@role_bp.route('/permissions/<string:role_id>/batch-delete', methods=['DELETE'])
@jwt_required()
@require_permissions('RoleManagement')
@use_args(role_permission_batch_delete_schema, location='json')
def delete_role_permissions_batch_route(args, role_id):
    """批量逻辑删除角色下的权限映射"""
    result = role_service.delete_role_permissions_batch(role_id, args['permission_ids'])
    return response_data(data=result, schema=role_permission_batch_delete_result_schema)

@role_bp.route('/permissions/<string:role_id>/batch-add', methods=['POST'])
@jwt_required()
@require_permissions('RoleManagement')
@use_args(role_permission_batch_add_schema, location='json')
def add_or_restore_role_permissions_batch_route(args, role_id):
    """批量新增或恢复角色下的权限映射"""
    result = role_service.add_or_restore_role_permissions_batch(role_id, args['permission_ids'])
    return response_data(data=result, schema=role_permission_batch_add_result_schema)