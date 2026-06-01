from backend.worktime import dao
from backend.common.exceptions import ResourceNotFoundError, InvalidUsageError
from backend.extensions import db
from datetime import date


class WorkTimeService:
    """工作时间服务类，处理与工作时间详情相关的业务逻辑"""

    @staticmethod
    def _parse_year_month_to_date(year_month):
        """将 YYYY-M / YYYY-MM 转为该月月初 date。"""
        if year_month is None:
            return None
        try:
            year_str, month_str = str(year_month).split('-', 1)
            return date(int(year_str), int(month_str), 1)
        except Exception:
            raise InvalidUsageError("Invalid month format, expected YYYY-M or YYYY-MM.")
    
    # ==================== DeviceWorkTimeDetail 业务逻辑 ====================
    
    def get_paged_worktime_details(self, page, per_page, filter_params=None, sort_by=None, sort_order='desc'):
        """
        获取分页的工作时间详情列表，支持筛选和排序
        :param page: 页码
        :param per_page: 每页数量
        :param filter_params: 筛选条件字典
        :param sort_by: 排序字段
        :param sort_order: 排序方向 ('asc' 或 'desc')
        :return: SQLAlchemy Pagination 对象
        """
        pagination = dao.get_all_worktime_details(page, per_page, filter_params, sort_by, sort_order)
        return pagination
    
    def update_worktime_detail(self, detail_id, update_data):
        """
        更新工作时间详情记录
        :param detail_id: 要更新的记录ID
        :param update_data: 包含要更新字段的字典
        :return: 更新后的 DeviceWorkTimeDetail 对象
        :raises ResourceNotFoundError: 如果记录ID不存在
        """
        # 1. 根据 ID 查找记录
        detail_to_update = dao.get_worktime_detail_by_id(detail_id)
        if not detail_to_update:
            raise ResourceNotFoundError(f"WorkTime detail record with ID '{detail_id}' does not exist.")
        
        # 2. 调用 DAO 层执行更新
        updated_detail = dao.update_worktime_detail(detail_to_update, update_data)
        
        return updated_detail
    
    def delete_worktime_detail(self, detail_id):
        """
        逻辑删除工作时间详情记录
        :param detail_id: 要删除的记录ID
        :raises ResourceNotFoundError: 如果记录ID不存在
        """
        # 1. 根据 ID 查找记录
        detail_to_delete = dao.get_worktime_detail_by_id(detail_id)
        if not detail_to_delete:
            raise ResourceNotFoundError(f"WorkTime detail record with ID '{detail_id}' does not exist.")
        
        # 2. 调用 DAO 层执行逻辑删除
        dao.delete_worktime_detail(detail_to_delete)
    
    # ==================== DeviceWorkTimeDay 业务逻辑 ====================
    
    def get_paged_worktime_days(self, page, per_page, filter_params=None, sort_by=None, sort_order='desc'):
        """
        获取分页的工作时间日汇总列表，支持筛选和排序
        :param page: 页码
        :param per_page: 每页数量
        :param filter_params: 筛选条件字典
        :param sort_by: 排序字段
        :param sort_order: 排序方向 ('asc' 或 'desc')
        :return: SQLAlchemy Pagination 对象
        """
        pagination = dao.get_all_worktime_days(page, per_page, filter_params, sort_by, sort_order)
        return pagination
    
    # ==================== DeviceWorkTimeMonth 业务逻辑 ====================
    
    def get_paged_worktime_months(self, page, per_page, filter_params=None, sort_by=None, sort_order='desc'):
        """
        获取分页的工作时间月汇总列表，支持筛选和排序
        :param page: 页码
        :param per_page: 每页数量
        :param filter_params: 筛选条件字典
        :param sort_by: 排序字段
        :param sort_order: 排序方向 ('asc' 或 'desc')
        :return: SQLAlchemy Pagination 对象
        """
        # 前端月筛选传 YYYY-M / YYYY-MM，数据库仍存 Date(月初)，这里做统一转换
        normalized_filters = dict(filter_params or {})
        if 'work_month_start' in normalized_filters and normalized_filters['work_month_start'] is not None:
            normalized_filters['work_month_start'] = self._parse_year_month_to_date(normalized_filters['work_month_start'])
        if 'work_month_end' in normalized_filters and normalized_filters['work_month_end'] is not None:
            normalized_filters['work_month_end'] = self._parse_year_month_to_date(normalized_filters['work_month_end'])

        pagination = dao.get_all_worktime_months(page, per_page, normalized_filters, sort_by, sort_order)
        return pagination
    
    # ==================== DeviceWorkTimeRange 业务逻辑 ====================
    
    def get_worktime_by_date_range(self, start_date, end_date, device_id=None, page=1, per_page=20, sort_by='device_id', sort_order='asc'):
        """
        获取指定日期范围内每个设备的总有效工作时间，支持分页和排序
        :param start_date: 开始日期（如果为None，默认为当月1号）
        :param end_date: 结束日期（如果为None，默认为今天）
        :param device_id: 可选的设备ID筛选
        :param page: 页码
        :param per_page: 每页数量
        :param sort_by: 排序字段
        :param sort_order: 排序方向
        :return: Pagination 对象
        """
        from datetime import date
        
        # 如果没有提供日期参数，使用默认值
        if start_date is None:
            # 默认为当月1号
            today = date.today()
            start_date = date(today.year, today.month, 1)
        
        if end_date is None:
            # 默认为今天
            end_date = date.today()
        
        # 调用 DAO 层获取分页数据
        pagination = dao.get_worktime_by_date_range(
            start_date, end_date, device_id, page, per_page, sort_by, sort_order
        )
        
        # 格式化分页中的每个item
        formatted_items = []
        for row in pagination.items:
            total_ms = row.total_duration_ms or 0
            formatted_items.append({
                'device_id': row.device_id,
                'total_duration_ms': total_ms,
                'total_duration_minutes': round(total_ms / (1000 * 60), 2),
                'total_duration_sec': round(total_ms / 1000, 2),
                'total_duration_hours': round(total_ms / (1000 * 3600), 2),
                'start_date': start_date,
                'end_date': end_date
            })
        
        # 重新构建pagination对象的items属性
        pagination.items = formatted_items
        
        return pagination

    # ==================== WorkTime Consume 业务逻辑 ====================

    def consume_worktime_detail(self, detail_id: str):
        """
        消费单条详情消息，幂等写入日/月汇总。
        :return: dict(status=processed|duplicate)
        """
        if not detail_id:
            raise InvalidUsageError("detail_id is required")
        # 一个事务内完成：
        # 1) 幂等日志插入
        # 2) 读取详情
        # 3) 写入日汇总
        # 4) 写入月汇总
        # 任一步失败都会回滚，保证一致性
        with db.session.begin():
            # 幂等闸门：先尝试写日志
            inserted = dao.insert_consume_log_if_absent(detail_id, status=1)
            # 插入失败（rowcount=0）表示该 detail_id 已处理过
            if inserted == 0:
                return {"status": "duplicate"}

            # 查询详情（只查未逻辑删除）
            detail = dao.get_worktime_detail_by_id(detail_id)
            if not detail:
                # 理论上不该出现（消息应来自已落库详情），出现则抛错触发回滚与重试
                raise ResourceNotFoundError(f"WorkTime detail record with ID '{detail_id}' does not exist.")

            # 计算 UTC 自然日与自然月
            work_date = detail.event_time_utc.date()
            work_month = date(work_date.year, work_date.month, 1)

            # 日表按毫秒累加
            dao.upsert_worktime_day_summary(detail.device_id, work_date, detail.duration_ms)

            # 月表按毫秒累加，避免秒级截断导致精度丢失
            dao.upsert_worktime_month_summary(detail.device_id, work_month, detail.duration_ms)

        return {"status": "processed"}


# 创建服务实例
worktime_service = WorkTimeService()
