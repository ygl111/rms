from flask import Blueprint, jsonify, current_app
from flask_jwt_extended import jwt_required
from webargs.flaskparser import use_args
from backend.email.service import upgrade_notify_email_service, fault_notify_email_service, email_send_service
from backend.common.exceptions import InvalidUsageError, DuplicateResourceError, ResourceNotFoundError
from backend.common.response import response_data
from backend.common.jwt_util import require_permissions
from backend.email.schema import (
    upgrade_notify_email_create_schema,
    upgrade_notify_email_update_schema,
    upgrade_notify_email_list_query_args,
    upgrade_notify_email_schema,
    fault_notify_email_create_schema,
    fault_notify_email_update_schema,
    fault_notify_email_list_query_args,
    fault_notify_email_schema,
    email_send_schema
)

# 创建升级通知邮箱蓝图
upgrade_email_bp = Blueprint('upgrade_notify_email', __name__, url_prefix='/api/upgrade-notify-emails')

# 创建故障通知邮箱蓝图
fault_email_bp = Blueprint('fault_notify_email', __name__, url_prefix='/api/fault-notify-emails')

# 创建邮件发送蓝图
email_send_bp = Blueprint('email_send', __name__, url_prefix='/api')


# ========== 升级通知邮箱路由 ==========

@upgrade_email_bp.route('', methods=['POST'])
@jwt_required()
@require_permissions('EmailManagement')
@use_args(upgrade_notify_email_create_schema, location="json")
def create_upgrade_notify_email(args):
    """创建升级通知邮箱"""
    try:
        new_email = upgrade_notify_email_service.create_email(args)
        return response_data(data=new_email, schema=upgrade_notify_email_schema), 201
    except DuplicateResourceError as e:
        raise e
    except Exception as e:
        current_app.logger.error(f"创建升级通知邮箱时发生错误: {e}")
        raise InvalidUsageError(f"Creation failed, unknown error occurred: {e}")


@upgrade_email_bp.route('', methods=['GET'])
@jwt_required()
@require_permissions('EmailManagement')
@use_args(upgrade_notify_email_list_query_args, location="query")
def get_upgrade_notify_emails(args):
    """获取升级通知邮箱列表（支持筛选、排序和分页）"""
    # 提取分页信息
    page = args['page']
    per_page = args['per_page']
    
    # 提取筛选条件
    filter_params = {k: v for k, v in args.items() 
                    if k not in ['page', 'per_page', 'sort_by', 'sort_order'] and v is not None}
    
    # 提取排序信息
    sort_by = args.get('sort_by')
    sort_order = args.get('sort_order')
    
    # 调用服务层获取数据
    paged_emails = upgrade_notify_email_service.get_paged_emails(page, per_page, filter_params, sort_by, sort_order)
    
    return response_data(data=paged_emails, schema=upgrade_notify_email_schema)


@upgrade_email_bp.route('/<string:email_id>', methods=['PUT', 'PATCH'])
@jwt_required()
@require_permissions('EmailManagement')
@use_args(upgrade_notify_email_update_schema, location="json")
def update_upgrade_notify_email(args, email_id):
    """更新升级通知邮箱"""
    try:
        updated_email = upgrade_notify_email_service.update_email(email_id, args)
        return response_data(data=updated_email, schema=upgrade_notify_email_schema)
    except ResourceNotFoundError as e:
        raise e
    except DuplicateResourceError as e:
        raise e
    except Exception as e:
        current_app.logger.error(f"更新升级通知邮箱时发生错误: {e}")
        raise InvalidUsageError(f"Update failed, unknown error occurred: {e}")


@upgrade_email_bp.route('/<string:email_id>', methods=['DELETE'])
@jwt_required()
@require_permissions('EmailManagement')
def delete_upgrade_notify_email(email_id):
    """删除升级通知邮箱（物理删除）"""
    try:
        upgrade_notify_email_service.delete_email(email_id)
        return jsonify({"message": "Upgrade notify email deleted successfully"}), 200
    except ResourceNotFoundError as e:
        raise e
    except Exception as e:
        current_app.logger.error(f"删除升级通知邮箱时发生错误: {e}")
        raise InvalidUsageError(f"Deletion failed, unknown error occurred: {e}")


# ========== 故障通知邮箱路由 ==========

@fault_email_bp.route('', methods=['POST'])
@jwt_required()
@require_permissions('EmailManagement')
@use_args(fault_notify_email_create_schema, location="json")
def create_fault_notify_email(args):
    """创建故障通知邮箱"""
    try:
        new_email = fault_notify_email_service.create_email(args)
        return response_data(data=new_email, schema=fault_notify_email_schema), 201
    except DuplicateResourceError as e:
        raise e
    except Exception as e:
        current_app.logger.error(f"创建故障通知邮箱时发生错误: {e}")
        raise InvalidUsageError(f"Creation failed, unknown error occurred: {e}")


@fault_email_bp.route('', methods=['GET'])
@jwt_required()
@require_permissions('EmailManagement')
@use_args(fault_notify_email_list_query_args, location="query")
def get_fault_notify_emails(args):
    """获取故障通知邮箱列表（支持筛选、排序和分页）"""
    # 提取分页信息
    page = args['page']
    per_page = args['per_page']
    
    # 提取筛选条件
    filter_params = {k: v for k, v in args.items() 
                    if k not in ['page', 'per_page', 'sort_by', 'sort_order'] and v is not None}
    
    # 提取排序信息
    sort_by = args.get('sort_by')
    sort_order = args.get('sort_order')
    
    # 调用服务层获取数据
    paged_emails = fault_notify_email_service.get_paged_emails(page, per_page, filter_params, sort_by, sort_order)
    
    return response_data(data=paged_emails, schema=fault_notify_email_schema)


@fault_email_bp.route('/<string:email_id>', methods=['PUT', 'PATCH'])
@jwt_required()
@require_permissions('EmailManagement')
@use_args(fault_notify_email_update_schema, location="json")
def update_fault_notify_email(args, email_id):
    """更新故障通知邮箱"""
    try:
        updated_email = fault_notify_email_service.update_email(email_id, args)
        return response_data(data=updated_email, schema=fault_notify_email_schema)
    except ResourceNotFoundError as e:
        raise e
    except DuplicateResourceError as e:
        raise e
    except Exception as e:
        current_app.logger.error(f"更新故障通知邮箱时发生错误: {e}")
        raise InvalidUsageError(f"Update failed, unknown error occurred: {e}")


@fault_email_bp.route('/<string:email_id>', methods=['DELETE'])
@jwt_required()
@require_permissions('EmailManagement')
def delete_fault_notify_email(email_id):
    """删除故障通知邮箱（物理删除）"""
    try:
        fault_notify_email_service.delete_email(email_id)
        return jsonify({"message": "Fault notify email deleted successfully"}), 200
    except ResourceNotFoundError as e:
        raise e
    except Exception as e:
        current_app.logger.error(f"删除故障通知邮箱时发生错误: {e}")
        raise InvalidUsageError(f"Deletion failed, unknown error occurred: {e}")


# ========== 邮件发送路由 ==========

@email_send_bp.route('/send-email', methods=['POST'])
@use_args(email_send_schema, location="json")
def send_email(args):
    """
    发送邮件到指定类型的所有邮箱
    
    请求参数：
    - email_type: 邮箱类型 ('upgrade' 或 'fault')
    - subject: 邮件主题
    - content: 邮件内容
    - content_type: 内容类型 ('plain' 或 'html'，默认为 'plain')
    
    返回：发送结果信息
    """
    try:
        result = email_send_service.send_email(
            email_type=args['email_type'],
            subject=args['subject'],
            content=args['content'],
            content_type=args['content_type']
        )
        return jsonify({
            "success": True,
            "message": result['message'],
            "data": {
                "recipients": result['recipients'],
                "recipient_count": len(result['recipients'])
            }
        }), 200
    except InvalidUsageError as e:
        raise e
    except Exception as e:
        current_app.logger.error(f"发送邮件时发生错误: {e}")
        raise InvalidUsageError(f"Failed to send email: {str(e)}")
