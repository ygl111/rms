from webargs import fields, validate
from backend.common.fields import UTCDateTimeField


# --- Schemas ---

# Firmware 分析结果 Schema (输出)
firmware_analysis_schema = {
    "firmware_name": fields.Str(dump_only=True),
    "version": fields.Str(dump_only=True),
    "md5_hash": fields.Str(dump_only=True),
    "file_size": fields.Int(dump_only=True)
}

# Firmware 创建 Schema (输入)
firmware_create_schema = {
    "firmware_name": fields.Str(required=True, validate=validate.Length(max=128)),
    "version": fields.Str(required=True, validate=validate.Length(max=128)),
    "md5_hash": fields.Str(required=True, validate=validate.Length(equal=32)),
    "file_size": fields.Int(required=True, validate=validate.Range(min=1)),
    "compatible_model_id": fields.Int(required=True),
    "description": fields.Str(allow_none=True)
}

# Firmware Schema (输出)
firmware_schema = {
    "id": fields.Str(dump_only=True),
    "firmware_name": fields.Str(dump_only=True),
    "version": fields.Str(dump_only=True),
    "file_size": fields.Int(dump_only=True),
    "md5_hash": fields.Str(dump_only=True),
    "storage_path": fields.Str(dump_only=True),
    "description": fields.Str(dump_only=True, allow_none=True),
    "status": fields.Str(dump_only=True),
    "uploaded_at": UTCDateTimeField(dump_only=True),
    "uploader": fields.Nested({
        "id": fields.Str(dump_only=True),
        "full_name": fields.Str(dump_only=True)
    }, dump_only=True, allow_none=True),
    "compatible_model": fields.Nested({
        "id": fields.Int(dump_only=True),
        "model_name": fields.Str(dump_only=True)
    }, dump_only=True, allow_none=True)
}

firmware_list_query_args = {
    # 分页参数
    "page": fields.Int(load_default=1, validate=lambda p: p > 0),
    "per_page": fields.Int(load_default=10, validate=lambda p: p > 0),
    # 排序参数
    "sort_by": fields.Str(load_default='uploaded_at', validate=validate.OneOf([
        'firmware_name', 'version', 'file_size', 'compatible_model.id', 'uploader.id', 'uploaded_at'
    ])),
    "sort_order": fields.Str(load_default='desc', validate=validate.OneOf(['asc', 'desc'])),
    # 筛选参数
    "firmware_name": fields.Str(),
    "version": fields.Str(),
    "compatible_model_id": fields.Int(),
    "uploaded_at_start": fields.DateTime(),
    "uploaded_at_end": fields.DateTime()
}

firmware_export_query_args = {
    # 导出参数与列表参数一致
    **firmware_list_query_args
}

firmware_batch_delete_schema = {
    "firmware_ids": fields.List(fields.Str(), required=True)
}
