from webargs import fields, validate
from backend.common.fields import UTCDateTimeField
from backend.mapping.schema import device_model_schema

# --- Schemas ---

# Device Schema (输出)
device_schema = {
    "id": fields.Str(dump_only=True),
    "device_id": fields.Str(dump_only=True),
    "device_type": fields.Int(dump_only=True),
    "online_status": fields.Str(dump_only=True),
    "last_online_time": UTCDateTimeField(dump_only=True, allow_none=True),
    "institution": fields.Nested({
        "id": fields.Str(dump_only=True),
        "institution_name": fields.Str(dump_only=True),
        "institution_code": fields.Str(dump_only=True)
    }, dump_only=True),
    "model": fields.Nested({
        "id": fields.Int(dump_only=True),
        "model_name": fields.Str(dump_only=True)
    }, dump_only=True),
    "firmware_version": fields.Str(dump_only=True),
    "ip_endpoint": fields.Str(dump_only=True),
    "created_at": UTCDateTimeField(dump_only=True),
    "updated_at": UTCDateTimeField(dump_only=True),
    "hardware_version": fields.Str(dump_only=True),
    "main_software_version": fields.Str(dump_only=True),
    "description": fields.Str(dump_only=True),
    "maintenance_threshold": fields.Int(dump_only=True),
    "latitude": fields.Decimal(dump_only=True, allow_none=True, places=7),
    "longitude": fields.Decimal(dump_only=True, allow_none=True, places=7),
    "address": fields.Str(dump_only=True, allow_none=True),
}

# Device 创建 Schema (输入)
device_create_schema = {
    "device_id": fields.Str(required=True, validate=validate.Length(min=1,max=64)),
    "institution_id": fields.Str(required=True),
    "model_id": fields.Int(required=True),
    "description": fields.Str(allow_none=True),
    "maintenance_threshold": fields.Int(load_default=0, validate=lambda x: x >= 0),
    "latitude": fields.Decimal(allow_none=True, places=7, validate=lambda x: -90 <= float(x) <= 90 if x is not None else True),
    "longitude": fields.Decimal(allow_none=True, places=7, validate=lambda x: -180 <= float(x) <= 180 if x is not None else True),
    "address": fields.Str(allow_none=True, validate=validate.Length(max=512)),
}

# Device 更新 Schema (输入)
device_update_schema = {
    "device_id": fields.Str(validate=validate.Length(min=1,max=64)),
    "model_id": fields.Int(),
    "institution_id": fields.Str(),
    "description": fields.Str(allow_none=True),
    "online_status": fields.Str(validate=validate.OneOf(['online', 'offline','maintenance','scrapped'])),
    "maintenance_threshold": fields.Int(validate=lambda x: x >= 0),
    "latitude": fields.Decimal(allow_none=True, places=7, validate=lambda x: -90 <= float(x) <= 90 if x is not None else True),
    "longitude": fields.Decimal(allow_none=True, places=7, validate=lambda x: -180 <= float(x) <= 180 if x is not None else True),
    "address": fields.Str(allow_none=True, validate=validate.Length(max=512)),
}

# 定义设备列表查询参数 Schema，包含筛选、排序和分页
device_list_query_args = {
    # 分页参数
    "page": fields.Int(load_default=1, validate=lambda p: p > 0),
    "per_page": fields.Int(load_default=10, validate=lambda p: p > 0),
    
    # 精确筛选参数（完整匹配）
    "model_id": fields.Int(),                      # 设备型号ID
    "institution_id": fields.Str(),               # 机构ID
    "online_status": fields.Str(validate=validate.OneOf(['online', 'offline','maintenance','scrapped'])),  # 在线状态
    "created_at_start": fields.DateTime(),  # 创建时间起
    "created_at_end": fields.DateTime(),   # 创建时间止
    # 模糊筛选参数（部分匹配）
    "device_id": fields.Str(),                    # 设备ID（包含匹配）
    "firmware_version": fields.Str(),             # 固件版本（包含匹配）
    "ip_endpoint": fields.Str(),                  # 设备IP（开头匹配）
    
    # 排序参数
    "sort_by": fields.Str(load_default='last_online_time',validate=validate.OneOf([
        'device_id', 'model_id', 'institution_code', 'institution_name', 
        'firmware_version', 'ip_endpoint', 'online_status', 'last_online_time', 'created_at'
    ])),  # 排序字段
    "sort_order": fields.Str(load_default='desc', validate=validate.OneOf(['asc', 'desc']))  # 排序方向，默认升序
}


# 定义批量删除设备的 Schema，用于 API 输入验证
device_batch_delete_schema = {
    "device_ids": fields.List(
        fields.Str(required=True), 
        required=True, 
        validate=validate.Length(min=1, max=100),  # 限制批量删除数量，避免一次删除过多
        error_messages={'required': 'device_ids field is required'}
    )
}

# 定义批量删除结果的 Schema，用于 API 输出序列化
device_batch_delete_result_schema = {
    "total_requested": fields.Int(dump_only=True),
    "successfully_deleted": fields.List(fields.Str(), dump_only=True),
    "not_found": fields.List(fields.Str(), dump_only=True),
    "success_count": fields.Int(dump_only=True),
    "not_found_count": fields.Int(dump_only=True)
}

# --- 批量导入相关 Schema ---

# 定义批量导入第一步的输出 Schema（预览数据）
device_batch_import_preview_schema = {
    "total_records": fields.Int(dump_only=True),           # 总记录数
    "valid_count": fields.Int(dump_only=True),             # 可导入的记录数
    "invalid_count": fields.Int(dump_only=True),           # 不可导入的记录数
    "valid_records": fields.List(fields.Dict(), dump_only=True),   # 可导入的记录列表
    "import_token": fields.Str(dump_only=True)             # 导入令牌（用于第二步确认）
}

# 定义批量导入第二步的输入 Schema
device_batch_import_confirm_schema = {
    "import_token": fields.Str(required=True, validate=validate.Length(min=1, max=100))
}

# 定义批量导入结果的 Schema，用于 API 输出序列化
device_batch_import_result_schema = {
    "success_count": fields.Int(dump_only=True),           # 成功导入的数量
    "imported_devices": fields.List(fields.Str(), dump_only=True), # 成功导入的设备ID列表
    "has_failed_file": fields.Bool(dump_only=True)         # 是否有失败记录的Excel文件
}
