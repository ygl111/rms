from webargs import fields, validate
from backend.common.fields import UTCDateTimeField


# ==================== DeviceWorkTimeDetail Schemas ====================

# 定义 DeviceWorkTimeDetail 列表查询参数 Schema（支持筛选、排序和分页）
worktime_detail_list_query_args = {
    # 分页参数
    "page": fields.Int(load_default=1, validate=validate.Range(min=1)),  # 页码，默认第1页
    "per_page": fields.Int(load_default=20, validate=validate.Range(min=1, max=100)),  # 每页数量，默认20条，最多100条
    
    # 精确筛选参数
    "device_id": fields.Str(),  # 设备ID（精确匹配）
    "event_time_utc_start": fields.DateTime(),  # 点钞时间起（UTC）
    "event_time_utc_end": fields.DateTime(),    # 点钞时间止（UTC）
    "created_at_start": fields.DateTime(),      # 创建时间起（UTC）
    "created_at_end": fields.DateTime(),        # 创建时间止（UTC）
    
    # 排序参数
    "sort_by": fields.Str(
        load_default='event_time_utc',
        validate=validate.OneOf([
            'device_id', 'event_time_utc', 'duration_ms', 'created_at'
        ])
    ),  # 排序字段，默认按点钞时间排序
    "sort_order": fields.Str(
        load_default='desc',
        validate=validate.OneOf(['asc', 'desc'])
    )  # 排序方向，默认降序
}


# 定义 DeviceWorkTimeDetail 序列化 Schema，用于控制 API 输出
worktime_detail_schema = {
    "id": fields.Str(dump_only=True),
    "device_id": fields.Str(dump_only=True),
    "event_time_utc": UTCDateTimeField(dump_only=True),
    "duration_ms": fields.Int(dump_only=True),
    "created_at": UTCDateTimeField(dump_only=True),
}


# 定义 DeviceWorkTimeDetail 更新 Schema，用于 API 输入验证
worktime_detail_update_schema = {
    "device_id": fields.Str(
        required=False,
        validate=validate.Length(min=1, max=64)
    ),
    "event_time_utc": fields.DateTime(required=False),
    "duration_ms": fields.Int(
        required=False,
        validate=validate.Range(min=0)
    ),
}


# ==================== DeviceWorkTimeDay Schemas ====================

# 定义 DeviceWorkTimeDay 列表查询参数 Schema（支持筛选、排序和分页）
worktime_day_list_query_args = {
    # 分页参数
    "page": fields.Int(load_default=1, validate=validate.Range(min=1)),
    "per_page": fields.Int(load_default=20, validate=validate.Range(min=1, max=100)),
    
    # 筛选参数
    "device_id": fields.Str(),  # 设备ID（精确匹配）
    "work_date_start": fields.Date(),  # 统计日期起
    "work_date_end": fields.Date(),    # 统计日期止
    
    # 排序参数
    "sort_by": fields.Str(
        load_default='work_date',
        validate=validate.OneOf(['device_id', 'work_date', 'duration_ms'])
    ),
    "sort_order": fields.Str(
        load_default='desc',
        validate=validate.OneOf(['asc', 'desc'])
    )
}


# 定义 DeviceWorkTimeDay 序列化 Schema
worktime_day_schema = {
    "device_id": fields.Str(dump_only=True),
    "work_date": fields.Date(dump_only=True),
    "duration_ms": fields.Int(dump_only=True),
    "updated_at": UTCDateTimeField(dump_only=True),
    "created_at": UTCDateTimeField(dump_only=True),
}


# ==================== DeviceWorkTimeMonth Schemas ====================

# 定义 DeviceWorkTimeMonth 列表查询参数 Schema（支持筛选、排序和分页）
worktime_month_list_query_args = {
    # 分页参数
    "page": fields.Int(load_default=1, validate=validate.Range(min=1)),
    "per_page": fields.Int(load_default=20, validate=validate.Range(min=1, max=100)),
    
    # 筛选参数
    "device_id": fields.Str(),  # 设备ID（精确匹配）
    "work_month_start": fields.Str(
        validate=validate.Regexp(r'^\d{4}-(?:0?[1-9]|1[0-2])$')
    ),  # 统计月份起（格式：YYYY-M 或 YYYY-MM）
    "work_month_end": fields.Str(
        validate=validate.Regexp(r'^\d{4}-(?:0?[1-9]|1[0-2])$')
    ),    # 统计月份止（格式：YYYY-M 或 YYYY-MM）
    
    # 排序参数
    "sort_by": fields.Str(
        load_default='work_month',
        validate=validate.OneOf(['device_id', 'work_month', 'duration_ms'])
    ),
    "sort_order": fields.Str(
        load_default='desc',
        validate=validate.OneOf(['asc', 'desc'])
    )
}


# 定义 DeviceWorkTimeMonth 序列化 Schema
worktime_month_schema = {
    "device_id": fields.Str(dump_only=True),
    "work_month": fields.Date(dump_only=True),
    "duration_ms": fields.Int(dump_only=True),
    "updated_at": UTCDateTimeField(dump_only=True),
    "created_at": UTCDateTimeField(dump_only=True),
}


# ==================== DeviceWorkTimeRange (日期范围) Schemas ====================

# 定义按设备汇总指定日期范围有效工作时间的查询参数 Schema
worktime_range_query_args = {
    # 分页参数
    "page": fields.Int(load_default=1, validate=validate.Range(min=1)),
    "per_page": fields.Int(load_default=20, validate=validate.Range(min=1, max=100)),
    
    # 筛选参数
    "start_date": fields.Date(),  # 开始日期（可选，默认为当月1号）
    "end_date": fields.Date(),    # 结束日期（可选，默认为今天）
    "device_id": fields.Str(),  # 可选的设备ID筛选
    
    # 排序参数
    "sort_by": fields.Str(
        load_default='device_id',
        validate=validate.OneOf([
            'device_id',
            'total_duration_ms',
            'total_duration_sec',
            'total_duration_minutes',
            'total_duration_hours'
        ])
    ),
    "sort_order": fields.Str(
        load_default='asc',
        validate=validate.OneOf(['asc', 'desc'])
    )
}


# 定义按设备汇总日期范围有效工作时间的输出 Schema
worktime_range_schema = {
    "device_id": fields.Str(),
    "total_duration_ms": fields.Int(),  # 总有效工作时长（毫秒）
    "total_duration_minutes": fields.Float(),  # 总有效工作时长（分钟）
    "total_duration_sec": fields.Float(),  # 总有效工作时长（秒）
    "total_duration_hours": fields.Float(),  # 总有效工作时长（小时）
    "start_date": fields.Date(),
    "end_date": fields.Date(),
}
