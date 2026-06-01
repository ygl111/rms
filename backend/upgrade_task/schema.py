from webargs import fields, validate
from backend.common.fields import UTCDateTimeField
# 升级任务创建 Schema (输入)
upgrade_task_create_schema = {
    "firmware_id": fields.Str(required=True, validate=validate.Length(equal=36)),
    "model_id": fields.Int(required=True),
    "description": fields.Str(allow_none=True),
    "start_date": fields.DateTime(),
    "end_date": fields.DateTime(),
    "time_arrange_start": fields.Time(),
    "time_arrange_end": fields.Time(),
    "institution_ids": fields.List(fields.Str(required=True), required=True, validate=validate.Length(min=1)),
    "send_email": fields.Bool(load_default=True)  # 是否发送邮件通知，默认True，不存入数据库
}

# 升级任务 Schema (输出)
upgrade_task_schema = {
    "id": fields.Str(dump_only=True),
    "task_code": fields.Str(dump_only=True),
    "description": fields.Str(dump_only=True, allow_none=True),
    "status": fields.Str(dump_only=True),
    "start_date": fields.DateTime(dump_only=True),
    "end_date": fields.DateTime(dump_only=True),
    "time_arrange_start": fields.Time(dump_only=True),
    "time_arrange_end": fields.Time(dump_only=True),
    "created_at": UTCDateTimeField(dump_only=True),
    "firmware": fields.Nested({
        "id": fields.Str(dump_only=True),
        "firmware_name": fields.Str(dump_only=True),
        "version": fields.Str(dump_only=True)
    }, dump_only=True, allow_none=True),
    "creator": fields.Nested({
        "id": fields.Str(dump_only=True),
        "full_name": fields.Str(dump_only=True)
    }, dump_only=True, allow_none=True),
    "model": fields.Nested({
        "id": fields.Int(dump_only=True),
        "model_name": fields.Str(dump_only=True)
    }, dump_only=True, allow_none=True)
}

# 设备映射 Schema (输出)
device_mapping_schema = {
    "task_id": fields.Str(dump_only=True),
    "status": fields.Int(dump_only=True),
    "confirm_upgrade": fields.Int(dump_only=True),
    "device": fields.Nested({
        "id": fields.Str(dump_only=True),
        "device_id": fields.Str(dump_only=True),
        "device_type": fields.Int(dump_only=True),
        "firmware_version": fields.Str(dump_only=True),
        "ip_endpoint": fields.Str(dump_only=True),
        "online_status": fields.Str(dump_only=True),
        "institution":fields.Nested({
            "institution_code":fields.Str(dump_only=True),
            "institution_name":fields.Str(dump_only=True),
        },dump_only=True, allow_none=True)
    }, dump_only=True, allow_none=True)
}

# 设备映射查询参数（筛选与排序）
device_mappings_query_args = {
    "institution_id": fields.Str(),   # 机构ID，精确匹配
    "device_id": fields.Str(),        # 设备编号，包含匹配
}

# 批量更新设备映射 confirm_upgrade 的请求体
device_confirm_upgrade_update_schema = {
    "device_ids": fields.List(fields.Str(required=True), required=True, validate=validate.Length(min=1)),
    "confirm_upgrade": fields.Int(required=True, validate=validate.OneOf([0, 1]))
}

# 批量更新结果 Schema
device_confirm_upgrade_update_result_schema = {
    "affected": fields.Int(),
    "confirm_upgrade": fields.Int(),
    "device_ids": fields.List(fields.Str())
}

# --- 升级任务 update、批量删除、导出 schema ---
# update schema
upgrade_task_update_schema = {
    "firmware_id": fields.Str(validate=validate.Length(equal=36)),
    "description": fields.Str(allow_none=True),
    "start_date": fields.DateTime(),
    "end_date": fields.DateTime(),
    "time_arrange_start": fields.Time(),
    "time_arrange_end": fields.Time(),
    "status": fields.Str(validate=validate.OneOf(["active", "cancelled", "completed"]))
}

# 批量删除 schema
upgrade_task_batch_delete_schema = {
    "ids": fields.List(fields.Str(required=True), required=True, validate=validate.Length(min=1))
}
upgrade_task_batch_delete_result_schema = {
    "success_ids": fields.List(fields.Str()),
    "failed_ids": fields.List(fields.Str()),
    "message": fields.Str()
}



# 支持筛选、排序、分页的查询参数
upgrade_task_list_query_args = {
    "page": fields.Int(load_default=1),
    "per_page": fields.Int(load_default=10),
    "sort_by": fields.Str(load_default='created_at', validate=validate.OneOf([
        'task_code', 'status', 'start_date', 'end_date', 'created_at',
        'model.model_name', 'firmware.version','firmware.firmware_name','creator.full_name'])),
    "sort_order": fields.Str(validate=validate.OneOf(["asc", "desc"]), load_default="desc"),
    # 可选筛选字段
    "task_code": fields.Str(),
    "firmware_id": fields.Str(),
    "model_id": fields.Int(),
    "status": fields.Str(),
    "creator_id": fields.Str(),

}
