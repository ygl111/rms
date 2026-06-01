from webargs import fields, validate
from backend.common.fields import UTCDateTimeField
# --- Schemas ---

# 币种统计 Schema
currency_schema = {
    "currency_code": fields.Str(dump_only=True),
    "value": fields.Decimal(places=2, dump_only=True),
    "note_count": fields.Int(dump_only=True),
    "amount": fields.Decimal(places=2, dump_only=True),
}

# 单张钞票详细数据 Schema
detailed_data_schema = {
    "currency_code": fields.Str(dump_only=True),
    "note_value": fields.Decimal(places=2, dump_only=True),
    "note_version": fields.Int(dump_only=True),
    "error_type": fields.Int(dump_only=True),
    "error_code": fields.Str(dump_only=True),
    "error_group": fields.Int(dump_only=True),
    "serial_number": fields.Str(dump_only=True),
    "stacker": fields.Int(dump_only=True),
}

# BanknoteCount 列表项 Schema (用于分页列表)
banknote_count_list_item_schema = {
    "id": fields.Str(dump_only=True),
    "count_time": UTCDateTimeField(dump_only=True),
    "total_passed_count": fields.Int(dump_only=True),
    "failed_count": fields.Int(dump_only=True),
    "total_amount": fields.Decimal(places=2, dump_only=True),
    "currency_count": fields.Int(dump_only=True),
    "device_identifier": fields.Str(dump_only=True),
    "institution_name": fields.Str(dump_only=True),
    "institution_code": fields.Str(dump_only=True)
}

# BanknoteCount 列表查询参数（分页/筛选/排序）
banknote_count_list_query_args = {
    "page": fields.Int(load_default=1, validate=lambda p: p > 0),
    "per_page": fields.Int(load_default=10, validate=lambda p: p > 0),

    # 筛选参数
    "device_identifier": fields.Str(),          # 业务设备号（冗余字段），模糊匹配
    "institution_name": fields.Str(),           # 机构名称（冗余字段），模糊匹配
    "count_time_start": UTCDateTimeField(),      # 点钞开始时间（BanknoteCount.count_time >= count_time_start）
    "count_time_end": UTCDateTimeField(),        # 点钞结束时间（BanknoteCount.count_time <= count_time_end）

    # 排序参数
    "sort_by": fields.Str(load_default='count_time', validate=validate.OneOf([
        'device_identifier', 'institution_name', 'currency_count', 'total_passed_count', 'failed_count', 'total_amount', 'count_time'
    ])),
    "sort_order": fields.Str(load_default='desc', validate=validate.OneOf(['asc', 'desc']))
}

# 图表分析查询参数（在已筛选数据基础上进行分组与聚合）
chart_query_args = {
    "group_by": fields.Str(load_default='institution',validate=validate.OneOf(['institution', 'device', 'count_time'])),
    "metric": fields.Str(load_default='total_passed_count',validate=validate.OneOf([
        'total_passed_count', 'failed_count', 'total_amount', 'currency_count'
    ])),
    # 当 group_by = count_time 时必填
    "time_agg": fields.Str(validate=validate.OneOf(['day', 'week', 'month'])),
    # 排序与限制（时间分组默认按时间正序）
    "sort_order": fields.Str(load_default='desc', validate=validate.OneOf(['asc', 'desc'])),
    "limit": fields.Int(),

    # 过滤参数（与列表保持一致）
    "device_identifier": fields.Str(),
    "institution_name": fields.Str(),
    "count_time_start": UTCDateTimeField(),
    "count_time_end": UTCDateTimeField(),
}

# 图表分析响应 Schema（records 为字典列表，元素结构随 group_by 不同而不同）
analytics_response_schema = {
    "records": fields.List(fields.Dict(), dump_only=True)
}


#-------------------------------此部分为新api的主从库分离示例----------------------------------
# Overview 统计概览响应 Schema（走从库查询）
summary_stats_schema = {
    "total_records": fields.Int(dump_only=True),
    "total_passed": fields.Int(dump_only=True),
    "total_failed": fields.Int(dump_only=True),
    "total_amount": fields.Float(dump_only=True),
    "device_count": fields.Int(dump_only=True),
    "institution_count": fields.Int(dump_only=True),
}
#---------------------------------------------------------------------------------------------