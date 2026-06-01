from webargs import fields, validate
from backend.common.fields import UTCDateTimeField


# 定义 Role 序列化 Schema (输出)
role_schema = {
    "id": fields.Str(dump_only=True),
    "role_code": fields.Str(dump_only=True),
    "role_name": fields.Str(dump_only=True),
    "description": fields.Str(dump_only=True),
    "status": fields.Str(dump_only=True),
    "created_at": UTCDateTimeField(dump_only=True),
    "updated_at": UTCDateTimeField(dump_only=True),
}

# 权限项 Schema（仅返回必要字段）
permission_brief_schema = {
    "id": fields.Str(dump_only=True),
    "permission_code": fields.Str(dump_only=True),
    "permission_name": fields.Str(dump_only=True),
}

# 批量删除角色权限映射 输入 Schema
role_permission_batch_delete_schema = {
    "permission_ids": fields.List(fields.Str(required=True), required=True, validate=validate.Length(min=1))
}

# 批量删除结果 输出 Schema
role_permission_batch_delete_result_schema = {
    "total_requested": fields.Int(dump_only=True),
    "successfully_deleted": fields.List(fields.Str(), dump_only=True),
    "not_found": fields.List(fields.Str(), dump_only=True),
    "success_count": fields.Int(dump_only=True),
    "not_found_count": fields.Int(dump_only=True)
}

# 批量新增/恢复 角色权限映射 输入 Schema
role_permission_batch_add_schema = {
    "permission_ids": fields.List(fields.Str(required=True), required=True, validate=validate.Length(min=1))
}

# 批量新增/恢复 结果 输出 Schema
role_permission_batch_add_result_schema = {
    "total_requested": fields.Int(dump_only=True),
    "created": fields.List(fields.Str(), dump_only=True),
    "restored": fields.List(fields.Str(), dump_only=True),
    "not_found": fields.List(fields.Str(), dump_only=True),
    "success_count": fields.Int(dump_only=True),
    "not_found_count": fields.Int(dump_only=True)
}

# 定义 Role 创建 Schema (输入)
role_create_schema = {
    "role_code": fields.Str(required=True),
    "role_name": fields.Str(required=True),
    "description": fields.Str(load_default=""), # 如果不提供，默认为空字符串
}

# [新增] 定义 Role 更新 Schema (输入)
role_update_schema = {
    "role_name": fields.Str(),
    "description": fields.Str(),
    "status": fields.Str(validate=validate.OneOf(['active', 'disabled'])),
}

# 定义角色列表查询参数 Schema，包含筛选、排序和分页
role_list_query_args = {
    # 分页参数
    "page": fields.Int(load_default=1, validate=lambda p: p > 0),
    "per_page": fields.Int(load_default=10, validate=lambda p: p > 0),
    
    # 精确筛选参数（完整匹配）
    "status": fields.Str(validate=validate.OneOf(['active', 'disabled'])),  # 角色状态
    
    # 模糊筛选参数（部分匹配）
    "role_code": fields.Str(),    # 角色编码（开头匹配）
    "role_name": fields.Str(),    # 角色名称（包含匹配）
    
    # 排序参数
    "sort_by": fields.Str(validate=validate.OneOf([
        'role_code', 'role_name', 'status'
    ])),  # 排序字段
    "sort_order": fields.Str(load_default='asc', validate=validate.OneOf(['asc', 'desc']))  # 排序方向，默认升序
}

# 定义角色导出查询参数 Schema（复用列表查询的筛选参数，但不需要分页和排序）
role_export_query_args = {
    # 精确筛选参数
    "status": fields.Str(validate=validate.OneOf(['active', 'disabled'])),
    
    # 模糊筛选参数
    "role_code": fields.Str(),
    "role_name": fields.Str(),
}

# 定义批量删除角色的 Schema，用于 API 输入验证
role_batch_delete_schema = {
    "role_ids": fields.List(
        fields.Str(required=True), 
        required=True, 
        validate=validate.Length(min=1, max=100),  # 限制批量删除数量，避免一次删除过多
        error_messages={'required': 'role_ids field is required'}
    )
}

# 定义批量删除结果的 Schema，用于 API 输出序列化
role_batch_delete_result_schema = {
    "total_requested": fields.Int(dump_only=True),
    "successfully_deleted": fields.List(fields.Str(), dump_only=True),
    "not_found": fields.List(fields.Str(), dump_only=True),
    "success_count": fields.Int(dump_only=True),
    "not_found_count": fields.Int(dump_only=True)
}