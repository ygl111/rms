from webargs import fields, validate
from backend.common.fields import UTCDateTimeField
# --- Schemas ---

# 输出 Schema
institution_schema = {
    "id": fields.Str(dump_only=True),
    "institution_code": fields.Str(dump_only=True),
    "institution_name": fields.Str(dump_only=True),
    "parent": fields.Nested({
        "id": fields.Str(dump_only=True),
        "institution_code": fields.Str(dump_only=True),
        "institution_name": fields.Str(dump_only=True)
    }, dump_only=True, allow_none=True),
    "level": fields.Int(dump_only=True),
    "address": fields.Str(dump_only=True),
    "contact_info": fields.Str(dump_only=True),
    "status": fields.Str(dump_only=True),
    "created_at": UTCDateTimeField(dump_only=True),
    "updated_at": UTCDateTimeField(dump_only=True),
}

# 创建 Schema (输入)
institution_create_schema = {
    "institution_code": fields.Str(required=True),
    "institution_name": fields.Str(required=True),
    "parent_id": fields.Str(allow_none=True), # 明确允许传入 null
    "level": fields.Int(),
    "address": fields.Str(allow_none=True),
    "contact_info": fields.Str(allow_none=True),
}

# 更新 Schema (输入)
institution_update_schema = {
    "institution_name": fields.Str(),
    "parent_id": fields.Str(allow_none=True), # 明确允许传入 null
    "level": fields.Int(),
    "address": fields.Str(),
    "contact_info": fields.Str(),
    "status": fields.Str(validate=validate.OneOf(['active', 'disabled'])),
}

# 机构树输出 Schema
institution_tree_schema = {
    "id": fields.Str(dump_only=True),
    "institution_code": fields.Str(dump_only=True),
    "institution_name": fields.Str(dump_only=True),
    "parent_id": fields.Str(dump_only=True, allow_none=True),
    "level": fields.Int(dump_only=True),
    "address": fields.Str(dump_only=True),
    "contact_info": fields.Str(dump_only=True),
    "status": fields.Str(dump_only=True),
    "created_at": UTCDateTimeField(dump_only=True),
    "updated_at": UTCDateTimeField(dump_only=True),
    "children": fields.List(fields.Dict(), dump_only=True)  # 子机构列表（递归结构）
}

# 机构列表查询参数 Schema，包含筛选、排序和分页（参考user模块风格）
institution_list_query_args = {
    # 分页参数
    "page": fields.Int(load_default=1, validate=lambda p: p > 0),
    "per_page": fields.Int(load_default=10, validate=lambda p: p > 0),
    # 排序参数
    "sort_by": fields.Str(load_default='level', validate=validate.OneOf([
        'status', 'level', 'parent_institution_name', 'parent_institution_code',
        'institution_name', 'institution_code', 'contact_info', 'address', 'created_at'
    ])),
    "sort_order": fields.Str(load_default='asc', validate=validate.OneOf(['asc', 'desc'])),
    # 精确筛选参数
    "status": fields.Str(validate=validate.OneOf(['active', 'disabled'])),  # 机构状态
    "level": fields.Int(),  # 机构层级
    "parent_id": fields.Str(),  # 父机构ID
    # 模糊筛选参数（包含匹配）
    "institution_name": fields.Str(),  # 机构名称（包含匹配）
    "institution_code": fields.Str(),  # 机构编码（包含匹配）
    "address": fields.Str(),  # 地址（包含匹配）
    "contact_info": fields.Str(),  # 联系方式（包含匹配）
}

# 子机构查询参数 Schema（只需要分页参数）
institution_children_query_args = {
    # 分页参数
    "page": fields.Int(load_default=1, validate=lambda p: p > 0),
    "per_page": fields.Int(load_default=10, validate=lambda p: p > 0),
    # 排序参数
    "sort_by": fields.Str(load_default='created_at', validate=validate.OneOf([
        'institution_code', 'institution_name', 'parent_institution_code', 'parent_institution_name',
        'level', 'status', 'contact_info', 'address', 'created_at'
    ])),
    "sort_order": fields.Str(load_default='asc', validate=validate.OneOf(['asc', 'desc']))
}

# 机构导出查询参数 Schema（可复用列表参数，或根据实际需求精简）
institution_export_query_args = {
    "status": fields.Str(validate=validate.OneOf(['active', 'disabled'])),
    "level": fields.Int(),
    "parent_id": fields.Str(),
    "institution_name": fields.Str(),
    "institution_code": fields.Str(),
    "address": fields.Str(),
    "contact_info": fields.Str(),
    # 排序参数
    "sort_by": fields.Str(load_default='level', validate=validate.OneOf([
        'status', 'level', 'parent_institution_name', 'parent_institution_code',
        'institution_name', 'institution_code', 'contact_info', 'address', 'created_at'
    ])),
    "sort_order": fields.Str(load_default='asc', validate=validate.OneOf(['asc', 'desc'])),
}

# 机构批量导入预览 Schema
institution_batch_import_preview_schema = {
    "total_records": fields.Int(dump_only=True),
    "valid_count": fields.Int(dump_only=True),
    "invalid_count": fields.Int(dump_only=True),
    "valid_records": fields.List(fields.Dict(), dump_only=True),
    "import_token": fields.Str(dump_only=True)
}

# 机构批量导入确认 Schema
institution_batch_import_confirm_schema = {
    "import_token": fields.Str(required=True, validate=validate.Length(min=1, max=100))
}

# 机构批量导入结果 Schema
institution_batch_import_result_schema = {
    "success_count": fields.Int(dump_only=True),
    "imported_institutions": fields.List(fields.Str(), dump_only=True),
    "has_failed_file": fields.Bool(dump_only=True)
}