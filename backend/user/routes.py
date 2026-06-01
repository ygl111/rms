from flask import Blueprint, request, jsonify, current_app, send_file
from flask_jwt_extended import jwt_required, get_jwt_identity
from webargs.flaskparser import use_args
from backend.user.service import user_service
from backend.common.exceptions import InvalidUsageError, DuplicateResourceError, ResourceNotFoundError
from backend.common.response import response_data
from backend.user.schema import user_export_query_args,user_schema,user_list_query_args,user_register_schema,user_update_schema,user_batch_delete_schema,user_batch_delete_result_schema,user_self_update_schema
from backend.common.jwt_util import require_permissions
# 创建一个蓝图对象，第一个参数是蓝图的名字，第二个参数是固定的 __name__
user_bp = Blueprint('user', __name__, url_prefix='/api/users')
from backend.common.exceptions import PermissionDeniedError
from dotenv import load_dotenv
import os

# 使用 @user_bp.route() 装饰器来定义路由
# '/register' 是这个接口在蓝图内的路径
# methods=['POST'] 指定了这个接口只接受 POST 请求
@user_bp.route('/register', methods=['POST'])
@use_args(user_register_schema, location="json")
@require_permissions('UserManagement')
def register(args):
    """用户注册接口"""
    try:
        # args 已经是经过 schema 验证和处理的干净数据
        new_user = user_service.register_user(args)
        # 统一用 response_data 和 user_schema 返回
        return response_data(data=new_user, schema=user_schema), 201
    except DuplicateResourceError as e:
        # 当 service 层抛出此异常时，我们知道是账号冲突
        raise e # 重新抛出，交给全局处理器处理
    except Exception as e:
        # 捕获任何其他未知异常
        current_app.logger.error(f"注册用户时发生错误: {e}")
        raise InvalidUsageError(f"Registration failed, unknown error occurred: {e}")


@user_bp.route('', methods=['GET'])
@jwt_required()
@use_args(user_list_query_args, location="query")

def get_users(args):
    """获取用户列表（支持筛选、排序和分页）"""
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
    paged_users = user_service.get_paged_users(page, per_page, filter_params, sort_by, sort_order)
    
    return response_data(data=paged_users, schema=user_schema)


@user_bp.route('/<string:user_id>', methods=['PUT', 'PATCH'])
@jwt_required()
@use_args(user_update_schema, location="json")
@require_permissions('UserManagement')
def update_user(args, user_id):
    """更新用户信息"""
    try:
        # args 就是经过 user_update_schema 验证和处理后的数据
        updated_user = user_service.update_user(user_id, args)
        # 使用 user_schema (输出模板) 来序列化返回的数据
        return response_data(data=updated_user, schema=user_schema)
    except ResourceNotFoundError as e:
        raise e
    except Exception as e:
        # 捕获其他可能的未知错误
        current_app.logger.error(f"更新用户时发生错误: {e}")
        raise InvalidUsageError(f"Update failed, unknown error occurred: {e}")


@user_bp.route('/<string:user_id>', methods=['DELETE'])
@jwt_required()
@require_permissions('UserManagement')
def delete_user(user_id):
    """删除用户（逻辑删除）"""
    try:
        user_service.delete_user(user_id)
        return jsonify({"message": "User deleted successfully"}), 200
    except PermissionDeniedError as e:
       raise e
    except ResourceNotFoundError as e:
        raise e
    except Exception as e:
        current_app.logger.error(f"删除用户时发生错误: {e}")
        raise InvalidUsageError(f"Deletion failed, unknown error occurred: {e}")


@user_bp.route('/batch-delete', methods=['DELETE'])
@jwt_required()
@use_args(user_batch_delete_schema, location="json")
@require_permissions('UserManagement')
def delete_users_batch(args):
    """批量删除用户（逻辑删除）"""
    try:
        user_ids = args.get('user_ids')
        
        # 直接调用服务层进行批量删除，让服务层统一处理admin过滤逻辑
        result = user_service.delete_users_batch(user_ids)
        
        # 使用 response_data 统一返回格式，并指定 schema 进行序列化
        return response_data(
            data=result, 
            schema=user_batch_delete_result_schema
        ), 200
    except InvalidUsageError as e:
        raise e
    except Exception as e:
        current_app.logger.error(f"批量删除用户时发生错误: {e}")
        raise InvalidUsageError(f"Batch deletion failed, unknown error occurred: {e}")


@user_bp.route('/export', methods=['GET'])
@jwt_required()
@use_args(user_export_query_args, location="query")
@require_permissions('UserManagement')
def export_users(args):
    """导出用户数据为Excel文件"""
    try:
        # 提取筛选条件（移除空值）
        filter_params = {k: v for k, v in args.items() if v is not None}
        
        # 调用服务层获取Excel文件
        excel_buffer, filename = user_service.export_users(filter_params)
        
        # 返回Excel文件给前端下载
        # mimetype 指定文件类型，as_attachment=True 表示作为附件下载
        return send_file(
            excel_buffer,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name=filename
        )
        
    except Exception as e:
        current_app.logger.error(f"导出用户数据时发生错误: {e}")
        raise InvalidUsageError(f"Export failed, unknown error occurred: {e}")


@user_bp.route('/me', methods=['GET'])
@jwt_required()
def get_current_user():
    """获取当前用户自己的详细信息"""
    user_id = get_jwt_identity()
    user = user_service.get_user_information(user_id)
    if not user:
        return {"msg": "User does not exist"}, 404
    return response_data(data=user, schema=user_schema)


# 用户自助修改资料（无需权限，只要 JWT 有效）
@user_bp.route('/me', methods=['PUT', 'PATCH'])
@jwt_required()
@use_args(user_self_update_schema, location="json")
def update_current_user(args):
    """用户修改自己的信息（不可修改角色、机构、状态等敏感字段）"""
    try:
        user_id = get_jwt_identity()
        updated_user = user_service.update_user(user_id, args)
        return response_data(data=updated_user, schema=user_schema)
    except ResourceNotFoundError as e:
        raise e
    except Exception as e:
        current_app.logger.error(f"用户自助修改资料时发生错误: {e}")
        raise InvalidUsageError(f"Update failed, unknown error occurred: {e}")
