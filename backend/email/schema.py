from webargs import fields, validate
from backend.common.fields import UTCDateTimeField


# ========== UpgradeNotifyEmail Schemas ==========

# 升级通知邮箱添加 Schema
upgrade_notify_email_create_schema = {
    "user_id": fields.Str(allow_none=True),
    "email": fields.Str(
        required=True,
        validate=validate.Email(error="Invalid email address format")
    ),
}

# 升级通知邮箱更新 Schema
upgrade_notify_email_update_schema = {
    "user_id": fields.Str(allow_none=True),
    "email": fields.Str(
        validate=validate.Email(error="Invalid email address format")
    ),
}

# 升级通知邮箱列表查询参数 Schema
upgrade_notify_email_list_query_args = {
    # 分页参数
    "page": fields.Int(load_default=1, validate=lambda p: p > 0),
    "per_page": fields.Int(load_default=10, validate=lambda p: p > 0),
    
    # 筛选参数
    "email": fields.Str(),  # 邮箱地址（模糊匹配）
    "full_name": fields.Str(),  # 用户姓名（模糊匹配）
    
    # 排序参数
    "sort_by": fields.Str(
        load_default='created_at',
        validate=validate.OneOf(['email', 'full_name', 'created_at', 'updated_at'])
    ),
    "sort_order": fields.Str(
        load_default='desc',
        validate=validate.OneOf(['asc', 'desc'])
    ),
}

# 升级通知邮箱输出 Schema
upgrade_notify_email_schema = {
    "id": fields.Str(dump_only=True),
    "user_id": fields.Str(dump_only=True),
    "email": fields.Str(dump_only=True),
    "user": fields.Nested({
        "id": fields.Str(dump_only=True),
        "account": fields.Str(dump_only=True),
        "full_name": fields.Str(dump_only=True)
    }, dump_only=True),
    "created_at": UTCDateTimeField(dump_only=True),
    "updated_at": UTCDateTimeField(dump_only=True),
}


# ========== FaultNotifyEmail Schemas ==========

# 故障通知邮箱添加 Schema
fault_notify_email_create_schema = {
    "user_id": fields.Str(allow_none=True),
    "email": fields.Str(
        required=True,
        validate=validate.Email(error="Invalid email address format")
    ),
}

# 故障通知邮箱更新 Schema
fault_notify_email_update_schema = {
    "user_id": fields.Str(allow_none=True),
    "email": fields.Str(
        validate=validate.Email(error="Invalid email address format")
    ),
}

# 故障通知邮箱列表查询参数 Schema
fault_notify_email_list_query_args = {
    # 分页参数
    "page": fields.Int(load_default=1, validate=lambda p: p > 0),
    "per_page": fields.Int(load_default=10, validate=lambda p: p > 0),
    
    # 筛选参数
    "email": fields.Str(),  # 邮箱地址（模糊匹配）
    "full_name": fields.Str(),  # 用户姓名（模糊匹配）
    
    # 排序参数
    "sort_by": fields.Str(
        load_default='created_at',
        validate=validate.OneOf(['email', 'full_name', 'created_at', 'updated_at'])
    ),
    "sort_order": fields.Str(
        load_default='desc',
        validate=validate.OneOf(['asc', 'desc'])
    ),
}

# 故障通知邮箱输出 Schema
fault_notify_email_schema = {
    "id": fields.Str(dump_only=True),
    "user_id": fields.Str(dump_only=True),
    "email": fields.Str(dump_only=True),
    "user": fields.Nested({
        "id": fields.Str(dump_only=True),
        "account": fields.Str(dump_only=True),
        "full_name": fields.Str(dump_only=True)
    }, dump_only=True),
    "created_at": UTCDateTimeField(dump_only=True),
    "updated_at": UTCDateTimeField(dump_only=True),
}


# ========== 邮件发送 Schemas ==========

# 邮件发送请求 Schema
email_send_schema = {
    "email_type": fields.Str(
        required=True,
        validate=validate.OneOf(['upgrade', 'fault'], error="email_type must be 'upgrade' or 'fault'")
    ),
    "subject": fields.Str(
        required=True,
        validate=validate.Length(min=1, max=200, error="Subject must be between 1 and 200 characters")
    ),
    "content": fields.Str(
        required=True,
        validate=validate.Length(min=1, error="Content cannot be empty")
    ),
    "content_type": fields.Str(
        load_default='plain',
        validate=validate.OneOf(['plain', 'html'], error="content_type must be 'plain' or 'html'")
    ),
}
