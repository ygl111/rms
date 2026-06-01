from webargs import fields, validate
from backend.common.fields import UTCDateTimeField

# 输出 Schema
upgrade_record_schema = {
    "id": fields.Str(dump_only=True),
    "task": fields.Nested({
        "id": fields.Str(dump_only=True),
        "task_code": fields.Str(dump_only=True)
    }, dump_only=True, allow_none=True),
    "task_id": fields.Str(dump_only=True),
    "device": fields.Nested({
        "id": fields.Str(dump_only=True),
        "device_id": fields.Str(dump_only=True),
        "firmware_version": fields.Str(dump_only=True),
        "model": fields.Nested({
            "id": fields.Int(dump_only=True),
            "model_name": fields.Str(dump_only=True)
        }, dump_only=True)
    }, dump_only=True, allow_none=True),
    "device_id": fields.Str(dump_only=True),
    "status": fields.Str(dump_only=True),
    "result_message": fields.Str(dump_only=True, allow_none=True),
    "completed_at": UTCDateTimeField(dump_only=True, allow_none=True),
    "created_at": UTCDateTimeField(dump_only=True),
}


# 列表查询参数（分页/筛选/排序）
upgrade_record_list_query_args = {
    "page": fields.Int(load_default=1, validate=lambda p: p > 0),
    "per_page": fields.Int(load_default=10, validate=lambda p: p > 0),

    # 筛选
    "status": fields.Str(validate=validate.OneOf(['pending', 'success', 'failed', 'cancelled'])),
    "task_id": fields.Str(),
    "task_code": fields.Str(),
    "device_id": fields.Str(),  # 业务设备号模糊匹配
    "model_name": fields.Str(),
    "completed_start": fields.DateTime(),
    "completed_end": fields.DateTime(),
    "created_start": fields.DateTime(),
    "created_end": fields.DateTime(),

    # 排序
    "sort_by": fields.Str(load_default='created_at', validate=validate.OneOf([
        'created_at', 'completed_at', 'status', 'device_id', 'task_code', 'model_name'
    ])),
    "sort_order": fields.Str(load_default='desc', validate=validate.OneOf(['asc', 'desc']))
}


# 批量删除
upgrade_record_batch_delete_schema = {
    "ids": fields.List(fields.Str(required=True), required=True, validate=validate.Length(min=1))
}

upgrade_record_batch_delete_result_schema = {
    "total_requested": fields.Int(dump_only=True),
    "successfully_deleted": fields.List(fields.Str(), dump_only=True),
    "not_found": fields.List(fields.Str(), dump_only=True),
    "success_count": fields.Int(dump_only=True),
    "not_found_count": fields.Int(dump_only=True)
}


