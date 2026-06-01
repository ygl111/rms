from backend.extensions import db
from backend.banknote.model import BanknoteCount, BanknoteCountCurrency, BanknoteDetailedData
from backend.common.db_router import read_session
from sqlalchemy.orm import joinedload, selectinload
from sqlalchemy import asc, desc, func

def get_banknote_count_by_id(count_id):
    """
    根据ID获取单条过钞记录,并预加载关联的币种信息。
    :param count_id: 过钞记录ID
    :return: BanknoteCount对象或None
    """
    return BanknoteCount.query.options(
        joinedload(BanknoteCount.currencies)
    ).filter_by(id=count_id).first()

def get_all_banknote_counts(page, per_page, filter_params=None, sort_by='count_time', sort_order='desc', export=False):
    """
    获取所有未被删除的过钞记录，支持筛选/排序/分页。
    当 export=True 时，返回所有记录列表（不分页），用于导出。
    使用冗余字段进行筛选，避免JOIN查询：
      - device_identifier: 按业务设备号模糊匹配（BanknoteCount.device_identifier LIKE %value%）
      - institution_name: 机构名称模糊匹配（BanknoteCount.institution_name LIKE %value%）
      - start_time/end_time: BanknoteCount.count_time 范围过滤
    支持的排序：
      - device_identifier、institution_name、currency_count、total_passed_count、failed_count、total_amount、count_time
    """
    query = db.session.query(BanknoteCount).filter(BanknoteCount.is_deleted == 0)

    # 关系加载策略
    load_options = []
    # 仅在导出时加载明细，避免分页列表行数膨胀
    if export:
        load_options.append(selectinload(BanknoteCount.detailed_data))
    if load_options:
        query = query.options(*load_options)

    # 筛选
    if filter_params:
        for key, value in filter_params.items():
            if value is None:
                continue
            if key == 'device_identifier':
                query = query.filter(BanknoteCount.device_identifier.like(f"%{value}%"))
            elif key == 'institution_name':
                query = query.filter(BanknoteCount.institution_name.like(f"%{value}%"))
            elif key == 'count_time_start':
                query = query.filter(BanknoteCount.count_time >= value)
            elif key == 'count_time_end':
                query = query.filter(BanknoteCount.count_time <= value)

    # 排序
    sort_columns = {
        'device_identifier': BanknoteCount.device_identifier,
        'institution_name': BanknoteCount.institution_name,
        'currency_count': BanknoteCount.currency_count,
        'total_passed_count': BanknoteCount.total_passed_count,
        'failed_count': BanknoteCount.failed_count,
        'total_amount': BanknoteCount.total_amount,
        'count_time': BanknoteCount.count_time,
    }
    sort_column = sort_columns.get(sort_by, BanknoteCount.count_time)
    query = query.order_by(desc(sort_column) if sort_order == 'desc' else asc(sort_column))

    if export:
        return query.all()
    return query.paginate(page=page, per_page=per_page, error_out=False)

def get_detailed_data_by_count_id(count_id):
    """
    根据BanknoteCount的ID获取所有关联的详细数据。
    """
    return BanknoteDetailedData.query.filter_by(count_id=count_id).all()

def delete_banknote_count(count_record):
    """
    逻辑删除一条过钞记录。
    (根据用户要求，不再级联删除子表记录)
    """
    count_record.is_deleted = 1
    db.session.commit() 


def stream_banknote_detailed_rows(filter_params=None, sort_by='count_time', sort_order='desc', chunk_size=5000):
    """
    针对导出场景的明细数据流式查询，避免一次性加载全部对象到内存。
    使用冗余字段，无需JOIN查询。
    返回的每行数据顺序为：
    device_identifier, stacker, institution_name, institution_code, serial_number,
    note_value, currency_code, note_version, error_type, error_code, error_group, count_time
    """
    query = db.session.query(
        BanknoteCount.device_identifier.label('device_identifier'),
        BanknoteDetailedData.stacker.label('stacker'),
        BanknoteCount.institution_name.label('institution_name'),
        BanknoteCount.institution_code.label('institution_code'),
        BanknoteDetailedData.serial_number.label('serial_number'),
        BanknoteDetailedData.note_value.label('note_value'),
        BanknoteDetailedData.currency_code.label('currency_code'),
        BanknoteDetailedData.note_version.label('note_version'),
        BanknoteDetailedData.error_type.label('error_type'),
        BanknoteDetailedData.error_code.label('error_code'),
        BanknoteDetailedData.error_group.label('error_group'),
        BanknoteCount.count_time.label('count_time'),
        BanknoteDetailedData.id.label('detail_id')
    ).join(BanknoteCount, BanknoteDetailedData.count_id == BanknoteCount.id)
    query = query.filter(BanknoteCount.is_deleted == 0)

    if filter_params:
        for key, value in filter_params.items():
            if value is None:
                continue
            if key == 'device_identifier':
                query = query.filter(BanknoteCount.device_identifier.like(f"%{value}%"))
            elif key == 'institution_name':
                query = query.filter(BanknoteCount.institution_name.like(f"%{value}%"))
            elif key == 'count_time_start':
                query = query.filter(BanknoteCount.count_time >= value)
            elif key == 'count_time_end':
                query = query.filter(BanknoteCount.count_time <= value)

    sort_columns = {
        'device_identifier': BanknoteCount.device_identifier,
        'institution_name': BanknoteCount.institution_name,
        'currency_count': BanknoteCount.currency_count,
        'total_passed_count': BanknoteCount.total_passed_count,
        'failed_count': BanknoteCount.failed_count,
        'total_amount': BanknoteCount.total_amount,
        'count_time': BanknoteCount.count_time,
    }
    sort_column = sort_columns.get(sort_by, BanknoteCount.count_time)
    primary_order = desc(sort_column) if sort_order == 'desc' else asc(sort_column)
    secondary_order = asc(BanknoteDetailedData.id)
    query = query.order_by(primary_order, secondary_order)

    streaming_query = query.execution_options(stream_results=True).yield_per(chunk_size)
    for row in streaming_query:
        yield (
            row.device_identifier,
            row.stacker,
            row.institution_name,
            row.institution_code,
            row.serial_number,
            row.note_value,
            row.currency_code,
            row.note_version,
            row.error_type,
            row.error_code,
            row.error_group,
            row.count_time
        )


def aggregate_banknote_counts(group_by: str, metric: str, filter_params=None,
                              time_agg: str = None, sort_order: str = 'desc', limit: int = None):
    """
    基于筛选条件进行聚合，使用冗余字段避免JOIN：
    - group_by: institution | device | count_time
    - metric: total_passed_count | failed_count | total_amount | currency_count
    - 当 group_by = count_time 时需要 time_agg in ['day','week','month']
    - 返回 list[dict]，每项包含分组键与 value
    """
    query = db.session.query().select_from(BanknoteCount)
    query = query.filter(BanknoteCount.is_deleted == 0)

    # 过滤参数
    if filter_params:
        device_identifier = filter_params.get('device_identifier')
        institution_name = filter_params.get('institution_name')
        start_time = filter_params.get('count_time_start') or filter_params.get('start_time')
        end_time = filter_params.get('count_time_end') or filter_params.get('end_time')
        if device_identifier:
            query = query.filter(BanknoteCount.device_identifier.like(f"%{device_identifier}%"))
        if institution_name:
            query = query.filter(BanknoteCount.institution_name.like(f"%{institution_name}%"))
        if start_time:
            query = query.filter(BanknoteCount.count_time >= start_time)
        if end_time:
            query = query.filter(BanknoteCount.count_time <= end_time)

    metric_map = {
        'total_passed_count': func.coalesce(func.sum(BanknoteCount.total_passed_count), 0),
        'failed_count': func.coalesce(func.sum(BanknoteCount.failed_count), 0),
        'total_amount': func.coalesce(func.sum(BanknoteCount.total_amount), 0),
        'currency_count': func.coalesce(func.sum(BanknoteCount.currency_count), 0),
    }
    metric_expr = metric_map[metric].label('value')

    if group_by == 'institution':
        query = query.with_entities(
            BanknoteCount.institution_id.label('institution_id'),
            BanknoteCount.institution_name.label('institution_name'),
            metric_expr
        ).group_by(BanknoteCount.institution_id, BanknoteCount.institution_name)
        order_col = metric_expr
    elif group_by == 'device':
        query = query.with_entities(
            BanknoteCount.device_identifier.label('device_identifier'),
            BanknoteCount.institution_id.label('institution_id'),
            BanknoteCount.institution_name.label('institution_name'),
            metric_expr
        ).group_by(BanknoteCount.device_identifier, BanknoteCount.institution_id, BanknoteCount.institution_name)
        order_col = metric_expr
    elif group_by == 'count_time':
        if time_agg not in ('day', 'week', 'month'):
            raise ValueError('time_agg 必须为 day|week|month')
        if time_agg == 'day':
            bucket = func.date_format(BanknoteCount.count_time, '%Y-%m-%d')
        elif time_agg == 'week':
            bucket = func.date_format(BanknoteCount.count_time, '%x-W%v')
        else:
            bucket = func.date_format(BanknoteCount.count_time, '%Y-%m')
        query = query.with_entities(
            bucket.label('time_bucket'),
            metric_expr
        ).group_by(bucket)
        order_col = bucket
        sort_order = 'asc'  # 时间分组强制正序
    else:
        raise ValueError('group_by 必须为 institution|device|count_time')

    query = query.order_by(asc(order_col) if sort_order == 'asc' else desc(order_col))
    if limit and limit > 0:
        query = query.limit(limit)

    rows = query.all()

    # 组装结果
    records = []
    for row in rows:
        if group_by == 'institution':
            records.append({
                'institution_id': row[0],
                'institution_name': row[1],
                'value': row[2],
            })
        elif group_by == 'device':
            records.append({
                'device_identifier': row[0],
                'institution_id': row[1],
                'institution_name': row[2],
                'value': row[3],
            })
        else:
            records.append({
                'time_bucket': row[0],
                'value': row[1],
            })

    return records



#-------------------------------此部分为新api的主从库分离示例----------------------------------
def get_summary_stats():
    """
    获取 overview 统计概览（走从库 / 降级主库）。

    返回:
        dict: {
            total_records: 总过钞记录数,
            total_passed: 累计过钞张数,
            total_failed: 累计失败张数,
            total_amount: 累计总金额,
            device_count: 涉及设备数,
            institution_count: 涉及机构数
        }
    """
    with read_session() as session:
        result = session.query(
            func.count(BanknoteCount.id).label('total_records'),
            func.coalesce(func.sum(BanknoteCount.total_passed_count), 0).label('total_passed'),
            func.coalesce(func.sum(BanknoteCount.failed_count), 0).label('total_failed'),
            func.coalesce(func.sum(BanknoteCount.total_amount), 0).label('total_amount'),
            func.count(func.distinct(BanknoteCount.device_identifier)).label('device_count'),
            func.count(func.distinct(BanknoteCount.institution_id)).label('institution_count')
        ).filter(BanknoteCount.is_deleted == 0).first()

        return {
            'total_records': result.total_records,
            'total_passed': int(result.total_passed),
            'total_failed': int(result.total_failed),
            'total_amount': float(result.total_amount),
            'device_count': result.device_count,
            'institution_count': result.institution_count,
        }
#---------------------------------------------------------------------------------------------