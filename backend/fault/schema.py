from webargs import fields, validate
from backend.common.fields import UTCDateTimeField

# 输出 Schema
fault_schema = {
    "id": fields.Str(dump_only=True),
    "device": fields.Nested({
        "id": fields.Str(dump_only=True),
        "device_id": fields.Str(dump_only=True),
        "latitude": fields.Decimal(dump_only=True, allow_none=True, places=7),
        "longitude": fields.Decimal(dump_only=True, allow_none=True, places=7),
        "address": fields.Str(dump_only=True, allow_none=True),
        "model": fields.Nested({
            "id": fields.Int(dump_only=True),
            "model_name": fields.Str(dump_only=True)
        }, dump_only=True)
    }, dump_only=True, allow_none=True),
    "device_id": fields.Str(dump_only=True),
    "fault_code": fields.Str(dump_only=True),
    "description": fields.Str(dump_only=True),
    "status": fields.Str(dump_only=True),
    "fault_time": UTCDateTimeField(dump_only=True),
    "fault_level": fields.Int(dump_only=True, allow_none=True),
    "img": fields.Str(dump_only=True, allow_none=True),
    "extra_data": fields.Dict(dump_only=True, allow_none=True),
    "created_at": UTCDateTimeField(dump_only=True),
}

# 故障操作日志 输出 Schema
fault_log_schema = {
    "id": fields.Str(dump_only=True),
    "fault_id": fields.Str(dump_only=True),
    "operator": fields.Nested({
        "id": fields.Str(dump_only=True),
        "full_name": fields.Str(dump_only=True)
    }, dump_only=True, allow_none=True),
    "operator_id": fields.Str(dump_only=True),
    "content": fields.Str(dump_only=True),
    "operation_time": UTCDateTimeField(dump_only=True),
    # 附加来自关联的故障与设备/型号信息
    "fault_code": fields.Str(dump_only=True, attribute='fault.fault_code'),
    "fault_level": fields.Int(dump_only=True, attribute='fault.fault_level'),
    "device_id": fields.Str(dump_only=True, attribute='fault.device.device_id'),
    "model_name": fields.Str(dump_only=True, attribute='fault.device.model.model_name'),
    "creator_full_name": fields.Str(dump_only=True, attribute='operator.full_name'),
    "creator_id": fields.Str(dump_only=True, attribute='operator_id'),
}

# 列表查询参数（分页/筛选/排序）
fault_list_query_args = {
    "page": fields.Int(load_default=1, validate=lambda p: p > 0),
    "per_page": fields.Int(load_default=10, validate=lambda p: p > 0),

    # 筛选
    "status": fields.Str(validate=validate.OneOf(['unprocessed', 'processing', 'processed'])),
    "device_id": fields.Str(),            # 业务设备号，模糊匹配（需要 join Device）
    "fault_code": fields.Str(),           # 模糊匹配
    "fault_level": fields.Int(),
    "model_name": fields.Str(),
    "fault_time_start": fields.DateTime(),
    "fault_time_end": fields.DateTime(),

    # 排序
    "sort_by": fields.Str(load_default='fault_time', validate=validate.OneOf([
        'fault_time', 'created_at', 'status', 'fault_level', 'device_id', 'fault_code', 'model_name'
    ])),
    "sort_order": fields.Str(load_default='desc', validate=validate.OneOf(['asc', 'desc']))
}

# 批量删除
fault_batch_delete_schema = {
    "ids": fields.List(fields.Str(required=True), required=True, validate=validate.Length(min=1))
}

fault_batch_delete_result_schema = {
    "total_requested": fields.Int(dump_only=True),
    "successfully_deleted": fields.List(fields.Str(), dump_only=True),
    "not_found": fields.List(fields.Str(), dump_only=True),
    "success_count": fields.Int(dump_only=True),
    "not_found_count": fields.Int(dump_only=True)
}

# 更新状态
fault_update_status_schema = {
    "status": fields.Str(required=True, validate=validate.OneOf(['unprocessed', 'processing', 'processed']))
}

# 故障操作日志 创建 Schema
fault_log_create_schema = {
    "content": fields.Str(required=True, validate=validate.Length(min=1))
}

# 故障操作日志 列表查询参数（筛选/排序/分页）
fault_log_list_query_args = {
    "page": fields.Int(load_default=1, validate=lambda p: p > 0),
    "per_page": fields.Int(load_default=10, validate=lambda p: p > 0),
    "fault_id": fields.Str(),
    "operator_id": fields.Str(),
    "creator_id": fields.Str(),
    "creator_full_name": fields.Str(),
    "content": fields.Str(),
    "device_id": fields.Str(),
    "model_name": fields.Str(),
    "fault_code": fields.Str(),
    "fault_level": fields.Int(),
    "operation_time_start": fields.DateTime(),
    "operation_time_end": fields.DateTime(),
    "sort_by": fields.Str(load_default='operation_time', validate=validate.OneOf([
        'operation_time', 'operator_id', 'creator_id', 'creator_full_name', 'device_id', 'model_name', 'fault_code', 'fault_level'
    ])),
    "sort_order": fields.Str(load_default='desc', validate=validate.OneOf(['asc', 'desc']))
}

# 故障操作日志 批量删除 Schema
fault_log_batch_delete_schema = {
    "ids": fields.List(fields.Str(required=True), required=True, validate=validate.Length(min=1))
}


# 非故障设备 输出 Schema
non_fault_device_schema = {
    "id": fields.Str(dump_only=True),
    "device_id": fields.Str(dump_only=True),
    "online_status": fields.Str(dump_only=True),
    "last_online_time": UTCDateTimeField(dump_only=True, allow_none=True),
    "latitude": fields.Decimal(dump_only=True, allow_none=True, places=7),
    "longitude": fields.Decimal(dump_only=True, allow_none=True, places=7),
    "address": fields.Str(dump_only=True, allow_none=True),
    "model": fields.Nested({
        "id": fields.Int(dump_only=True),
        "model_name": fields.Str(dump_only=True)
    }, dump_only=True, allow_none=True)
}