from webargs import fields, validate
from backend.common.fields import UTCDateTimeField
import re
from marshmallow import ValidationError


def validate_email_if_provided(value):
    """验证邮箱格式，允许空值"""
    if value and value.strip():  # 只在有值时验证
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_pattern, value):
            raise ValidationError('Invalid email format')
    return value


def validate_password_complexity(value):
    """验证密码复杂度：至少8个字符，且同时包含大小写字母、数字和符号中的至少3种"""
    if not value:
        return value
    
    # 检查长度
    if len(value) < 8:
        raise ValidationError('Password must be at least 8 characters long')
    
    # 检查是否包含中文字符
    if re.search(r'[\u4e00-\u9fff]', value):
        raise ValidationError('Password cannot contain Chinese characters')
    
    # 检查复杂度：统计包含的字符类型
    has_lowercase = bool(re.search(r'[a-z]', value))
    has_uppercase = bool(re.search(r'[A-Z]', value))
    has_digit = bool(re.search(r'[0-9]', value))
    has_symbol = bool(re.search(r'[\W_]', value))  # 特殊字符和下划线
    
    # 统计满足的字符类型数量
    complexity_count = sum([has_lowercase, has_uppercase, has_digit, has_symbol])
    
    if complexity_count < 3:
        raise ValidationError('Password must contain at least 3 of the following: lowercase letters, uppercase letters, numbers, and symbols')
    
    return value


# 定义用户导出查询参数 Schema（复用列表查询的筛选参数，但不需要分页）
user_export_query_args = {
    # 精确筛选参数（完整匹配）
    "institution_id": fields.Str(),  # 机构ID
    "role_id": fields.Str(),         # 角色ID
    "status": fields.Str(validate=validate.OneOf(['active', 'disabled'])),  # 用户状态
    "gender": fields.Str(validate=validate.OneOf(['woman', 'man', 'none', 'others'])),  # 性别
    "created_at_start": fields.DateTime(),  # 创建时间起
    "created_at_end": fields.DateTime(),   # 创建时间止

    # 模糊筛选参数（部分匹配）
    "account": fields.Str(),         # 账号（开头匹配）
    "full_name": fields.Str(),       # 姓名（包含匹配）
    "email": fields.Str(),           # 邮箱（包含匹配）
    "contact_info": fields.Str(),    # 联系方式（开头匹配）
    "address": fields.Str(),         # 地址（包含匹配）

    # 排序参数
    "sort_by": fields.Str(load_default='created_at',validate=validate.OneOf([
        'account', 'full_name', 'email', 'contact_info', 'address', 'status',
        'role_name', 'institution_code', 'institution_name','created_at'
    ])),  # 排序字段
    "sort_order": fields.Str(load_default='desc', validate=validate.OneOf(['asc', 'desc']))  # 排序方向，默认升序
}


# 定义 User 序列化 Schema，用于控制 API 输出
user_schema = {
    "id": fields.Str(dump_only=True),
    "account": fields.Str(dump_only=True),
    "full_name": fields.Str(dump_only=True),
    # 嵌套 Role 和 Institution 的关键信息
    "role": fields.Nested({
        "id": fields.Str(dump_only=True),
        "role_name": fields.Str(dump_only=True)
    }, dump_only=True),
    "institution": fields.Nested({
        "id": fields.Str(dump_only=True),
        "institution_name": fields.Str(dump_only=True),  
        "institution_code": fields.Str(dump_only=True)
    }, dump_only=True),
    "email": fields.Str(dump_only=True),
    "contact_info": fields.Str(dump_only=True),
    "address": fields.Str(dump_only=True),
    "status": fields.Str(dump_only=True),
    "gender": fields.Str(dump_only=True),
    "created_at": UTCDateTimeField(dump_only=True),
}

# User 更新 Schema，用于 API 输入验证
user_update_schema = {
    "password": fields.Str(
        validate=validate_password_complexity
    ),
    "full_name": fields.Str(),
    "email": fields.Str(validate=validate_email_if_provided),
    "role_id": fields.Str(),
    "institution_id": fields.Str(),
    "contact_info": fields.Str(),
    "address": fields.Str(),
    "gender": fields.Str(validate=validate.OneOf(['woman', 'man', 'none', 'others'])),
    "status": fields.Str(validate=validate.OneOf(['active', 'disabled'])),
}

# User 自助更新 Schema（用户修改自己的信息，不允许改角色/机构/状态等敏感字段）
user_self_update_schema = {
    "password": fields.Str(
        validate=validate_password_complexity
    ),
    "full_name": fields.Str(),
    "email": fields.Str(validate=validate_email_if_provided),
    "contact_info": fields.Str(),
    "address": fields.Str(),
    "gender": fields.Str(validate=validate.OneOf(['woman', 'man', 'none', 'others'])),
}

# 注册 Schema，用于 API 输入验证
user_register_schema = {
    "account": fields.Str(
        required=True,
        validate=validate.Regexp(
            r'^[a-zA-Z][a-zA-Z0-9_]{3,15}$',
            error="Account must start with a letter, can contain letters, numbers and underscores, length 4-16"
        )
    ),
    "password": fields.Str(
        required=True,
        validate=validate_password_complexity
    ),
    "full_name": fields.Str(),
    "email": fields.Str(validate=validate_email_if_provided),
    "role_id": fields.Str(),
    "institution_id": fields.Str(),
    "contact_info": fields.Str(),
    "address": fields.Str(),
    "gender": fields.Str(validate=validate.OneOf(['woman', 'man', 'none', 'others'])),
}


# 通用分页参数，可以被其他模块导入使用
pagination_args = {
    "page": fields.Int(load_default=1, validate=lambda p: p > 0),
    "per_page": fields.Int(load_default=10, validate=lambda p: p > 0),
}


# 定义用户列表查询参数 Schema，包含筛选、排序和分页
user_list_query_args = {
    # 分页参数
    "page": fields.Int(load_default=1, validate=lambda p: p > 0),
    "per_page": fields.Int(load_default=10, validate=lambda p: p > 0),
    
    # 精确筛选参数（完整匹配）
    "institution_id": fields.Str(),  # 机构ID
    "role_id": fields.Str(),         # 角色ID
    "status": fields.Str(validate=validate.OneOf(['active', 'disabled'])),  # 用户状态
    "gender": fields.Str(validate=validate.OneOf(['woman', 'man', 'none', 'others'])),  # 性别
    "created_at_start": fields.DateTime(),  # 创建时间起
    "created_at_end": fields.DateTime(),   # 创建时间止

    # 模糊筛选参数（部分匹配）
    "account": fields.Str(),         # 账号（开头匹配）
    "full_name": fields.Str(),       # 姓名（包含匹配）
    "email": fields.Str(),           # 邮箱（包含匹配）
    "contact_info": fields.Str(),    # 联系方式（开头匹配）
    "address": fields.Str(),         # 地址（包含匹配）

    # 排序参数
    "sort_by": fields.Str(load_default='created_at',validate=validate.OneOf([
        'account', 'full_name', 'email', 'contact_info', 'address', 'status',
        'role_name', 'institution_code', 'institution_name','created_at'
    ])),  # 排序字段
    "sort_order": fields.Str(load_default='desc', validate=validate.OneOf(['asc', 'desc']))  # 排序方向，默认升序
}

# 定义批量删除用户的 Schema，用于 API 输入验证
user_batch_delete_schema = {
    "user_ids": fields.List(
        fields.Str(required=True), 
        required=True, 
        validate=validate.Length(min=1, max=100),
        error_messages={'required': 'user_ids field is required'}
    )
}

# 定义批量删除结果的 Schema，用于 API 输出序列化
user_batch_delete_result_schema = {
    "total_requested": fields.Int(dump_only=True),
    "successfully_deleted": fields.List(fields.Str(), dump_only=True),
    "not_found": fields.List(fields.Str(), dump_only=True),
    "skipped_ids": fields.List(fields.Str(), dump_only=True),
    "success_count": fields.Int(dump_only=True),
    "not_found_count": fields.Int(dump_only=True),
    "skipped_count": fields.Int(dump_only=True)
}