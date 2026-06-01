from backend.extensions import db
from backend.worktime.model import DeviceWorkTimeDetail, DeviceWorkTimeDay, DeviceWorkTimeMonth
from sqlalchemy import text


def _execute_sql(sql, params):
    """统一执行参数化 SQL，减少重复样板代码。"""
    return db.session.execute(text(sql), params)


def _upsert_worktime_summary(table_name, period_column, duration_column, device_id, period_value, duration_value):
    """
    通用汇总 UPSERT：
    - table_name: 目标表名
    - period_column: 周期列名（work_date/work_month）
    - duration_column: 时长列名（duration_ms）
    """
    sql = (
        f"INSERT INTO {table_name} (device_id, {period_column}, {duration_column}, created_at, updated_at) "
        f"VALUES (:device_id, :period_value, :duration_value, UTC_TIMESTAMP(), UTC_TIMESTAMP()) "
        f"ON DUPLICATE KEY UPDATE "
        f"{duration_column} = {duration_column} + VALUES({duration_column}), "
        f"updated_at = UTC_TIMESTAMP()"
    )
    _execute_sql(
        sql,
        {
            "device_id": device_id,
            "period_value": period_value,
            "duration_value": duration_value,
        }
    )


# ==================== DeviceWorkTimeDetail DAO ====================

def get_worktime_detail_by_id(detail_id):
    """
    根据ID查询工作时间详情记录（不包括逻辑删除的）
    :param detail_id: 记录ID
    :return: DeviceWorkTimeDetail 对象或 None
    """
    return DeviceWorkTimeDetail.query.filter_by(id=detail_id, is_deleted=False).first()


def get_all_worktime_details(page, per_page, filter_params=None, sort_by='event_time_utc', sort_order='desc'):
    """
    获取工作时间详情列表，支持筛选、排序和分页
    :param page: 页码
    :param per_page: 每页数量
    :param filter_params: 筛选条件字典
    :param sort_by: 排序字段
    :param sort_order: 排序方向 ('asc' 或 'desc')
    :return: SQLAlchemy Pagination 对象
    """
    # 构建基础查询，排除逻辑删除的记录
    query = DeviceWorkTimeDetail.query.filter(DeviceWorkTimeDetail.is_deleted == False)
    
    # -------------------
    # 应用筛选条件
    # -------------------
    if filter_params:
        # 精确匹配
        if 'device_id' in filter_params:
            query = query.filter(DeviceWorkTimeDetail.device_id == filter_params['device_id'])
        
        # 时间范围筛选
        if 'event_time_utc_start' in filter_params:
            query = query.filter(DeviceWorkTimeDetail.event_time_utc >= filter_params['event_time_utc_start'])
        if 'event_time_utc_end' in filter_params:
            query = query.filter(DeviceWorkTimeDetail.event_time_utc <= filter_params['event_time_utc_end'])
        if 'created_at_start' in filter_params:
            query = query.filter(DeviceWorkTimeDetail.created_at >= filter_params['created_at_start'])
        if 'created_at_end' in filter_params:
            query = query.filter(DeviceWorkTimeDetail.created_at <= filter_params['created_at_end'])
    
    # -------------------
    # 应用排序
    # -------------------
    sort_columns = {
        'device_id': DeviceWorkTimeDetail.device_id,
        'event_time_utc': DeviceWorkTimeDetail.event_time_utc,
        'duration_ms': DeviceWorkTimeDetail.duration_ms,
        'created_at': DeviceWorkTimeDetail.created_at
    }
    
    sort_column = sort_columns.get(sort_by, DeviceWorkTimeDetail.event_time_utc)  # 默认按点钞时间排序
    query = query.order_by(sort_column.desc() if sort_order == 'desc' else sort_column.asc())
    
    # -------------------
    # 分页查询
    # -------------------
    return query.paginate(page=page, per_page=per_page, error_out=False)


def update_worktime_detail(detail, update_data):
    """
    更新工作时间详情记录
    :param detail: DeviceWorkTimeDetail 对象
    :param update_data: 包含要更新字段的字典
    :return: 更新后的 DeviceWorkTimeDetail 对象
    """
    for key, value in update_data.items():
        if hasattr(detail, key):
            setattr(detail, key, value)
    
    db.session.commit()
    return detail


def delete_worktime_detail(detail):
    """
    逻辑删除工作时间详情记录
    :param detail: 要删除的 DeviceWorkTimeDetail 对象
    """
    detail.is_deleted = True
    db.session.commit()


# ==================== DeviceWorkTimeDay DAO ====================

def get_all_worktime_days(page, per_page, filter_params=None, sort_by='work_date', sort_order='desc'):
    """
    获取工作时间日汇总列表，支持筛选、排序和分页
    :param page: 页码
    :param per_page: 每页数量
    :param filter_params: 筛选条件字典
    :param sort_by: 排序字段
    :param sort_order: 排序方向 ('asc' 或 'desc')
    :return: SQLAlchemy Pagination 对象
    """
    query = DeviceWorkTimeDay.query
    
    # 应用筛选条件
    if filter_params:
        if 'device_id' in filter_params:
            query = query.filter(DeviceWorkTimeDay.device_id == filter_params['device_id'])
        if 'work_date_start' in filter_params:
            query = query.filter(DeviceWorkTimeDay.work_date >= filter_params['work_date_start'])
        if 'work_date_end' in filter_params:
            query = query.filter(DeviceWorkTimeDay.work_date <= filter_params['work_date_end'])
    
    # 应用排序
    sort_columns = {
        'device_id': DeviceWorkTimeDay.device_id,
        'work_date': DeviceWorkTimeDay.work_date,
        'duration_ms': DeviceWorkTimeDay.duration_ms
    }
    
    sort_column = sort_columns.get(sort_by, DeviceWorkTimeDay.work_date)
    query = query.order_by(sort_column.desc() if sort_order == 'desc' else sort_column.asc())
    
    # 分页查询
    return query.paginate(page=page, per_page=per_page, error_out=False)


# ==================== DeviceWorkTimeMonth DAO ====================

def get_all_worktime_months(page, per_page, filter_params=None, sort_by='work_month', sort_order='desc'):
    """
    获取工作时间月汇总列表，支持筛选、排序和分页
    :param page: 页码
    :param per_page: 每页数量
    :param filter_params: 筛选条件字典
    :param sort_by: 排序字段
    :param sort_order: 排序方向 ('asc' 或 'desc')
    :return: SQLAlchemy Pagination 对象
    """
    query = DeviceWorkTimeMonth.query
    
    # 应用筛选条件
    if filter_params:
        if 'device_id' in filter_params:
            query = query.filter(DeviceWorkTimeMonth.device_id == filter_params['device_id'])
        if 'work_month_start' in filter_params:
            query = query.filter(DeviceWorkTimeMonth.work_month >= filter_params['work_month_start'])
        if 'work_month_end' in filter_params:
            query = query.filter(DeviceWorkTimeMonth.work_month <= filter_params['work_month_end'])
    
    # 应用排序
    sort_columns = {
        'device_id': DeviceWorkTimeMonth.device_id,
        'work_month': DeviceWorkTimeMonth.work_month,
        'duration_ms': DeviceWorkTimeMonth.duration_ms
    }
    
    sort_column = sort_columns.get(sort_by, DeviceWorkTimeMonth.work_month)
    query = query.order_by(sort_column.desc() if sort_order == 'desc' else sort_column.asc())
    
    # 分页查询
    return query.paginate(page=page, per_page=per_page, error_out=False)


# ==================== DeviceWorkTimeRange DAO ====================

def get_worktime_by_date_range(start_date, end_date, device_id=None, page=1, per_page=20, sort_by='device_id', sort_order='asc'):
    """
    获取指定日期范围内每个设备的总有效工作时间，支持分页和排序
    :param start_date: 开始日期
    :param end_date: 结束日期
    :param device_id: 可选的设备ID筛选
    :param page: 页码
    :param per_page: 每页数量
    :param sort_by: 排序字段 ('device_id'、'total_duration_ms'、'total_duration_sec'、'total_duration_minutes'、'total_duration_hours')
    :param sort_order: 排序方向 ('asc' 或 'desc')
    :return: SQLAlchemy Pagination 对象
    """
    from sqlalchemy import func
    
    # 构建查询：按设备分组，汇总duration_ms
    query = db.session.query(
        DeviceWorkTimeDay.device_id,
        func.sum(DeviceWorkTimeDay.duration_ms).label('total_duration_ms')
    ).filter(
        DeviceWorkTimeDay.work_date >= start_date,
        DeviceWorkTimeDay.work_date <= end_date
    )
    
    # 如果指定了设备ID，则添加筛选条件
    if device_id:
        query = query.filter(DeviceWorkTimeDay.device_id == device_id)
    
    # 按设备分组
    query = query.group_by(DeviceWorkTimeDay.device_id)
    
    # 应用排序
    if sort_by in ('total_duration_ms', 'total_duration_sec', 'total_duration_minutes', 'total_duration_hours'):
        # 注意：这里使用 label 名称来排序
        from sqlalchemy import text
        if sort_order == 'desc':
            query = query.order_by(text('total_duration_ms DESC'))
        else:
            query = query.order_by(text('total_duration_ms ASC'))
    else:  # device_id
        if sort_order == 'desc':
            query = query.order_by(DeviceWorkTimeDay.device_id.desc())
        else:
            query = query.order_by(DeviceWorkTimeDay.device_id.asc())
    
    # 分页查询
    return query.paginate(page=page, per_page=per_page, error_out=False)


# ==================== WorkTime Consume & Aggregation DAO ====================

def insert_consume_log_if_absent(detail_id, status=1):
    """
    幂等插入消费日志。已存在则不插入。
    :return: 1 表示插入成功，0 表示已存在
    """
    # INSERT IGNORE：
    # - detail_id 不存在 -> 插入成功（rowcount=1）
    # - detail_id 已存在 -> 忽略插入（rowcount=0）
    result = _execute_sql(
        "INSERT IGNORE INTO device_work_time_consume_log (detail_id, status) "
        "VALUES (:detail_id, :status)",
        {"detail_id": detail_id, "status": status}
    )
    # 返回受影响行数，供业务层判断 processed/duplicate
    return result.rowcount


def upsert_worktime_day_summary(device_id, work_date, duration_ms):
    """
    日汇总幂等累加。
    """
    # 利用联合主键(device_id, work_date)做 UPSERT：不存在插入，存在累加
    _upsert_worktime_summary(
        table_name='device_work_time_day',
        period_column='work_date',
        duration_column='duration_ms',
        device_id=device_id,
        period_value=work_date,
        duration_value=duration_ms,
    )


def upsert_worktime_month_summary(device_id, work_month, duration_ms):
    """
    月汇总幂等累加。
    """
    # 利用联合主键(device_id, work_month)做 UPSERT：不存在插入，存在累加
    _upsert_worktime_summary(
        table_name='device_work_time_month',
        period_column='work_month',
        duration_column='duration_ms',
        device_id=device_id,
        period_value=work_month,
        duration_value=duration_ms,
    )
