import uuid
from backend.extensions import db
from sqlalchemy import Column, String, DateTime, Boolean, BigInteger, Date, func, Index
from sqlalchemy.dialects.mysql import TINYINT


class DeviceWorkTimeDetail(db.Model):
    """有效工作时间详情表（记录设备每次点钞产生的有效工作时长明细，按UTC时间，支持逻辑删除）"""
    __tablename__ = 'device_work_time_detail'

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), comment='主键UUID')
    device_id = Column(String(64), nullable=False, comment='设备ID')
    event_time_utc = Column(DateTime, nullable=False, comment='设备上报的点钞时间（UTC）')
    duration_ms = Column(BigInteger, nullable=False, comment='本次点钞的有效工作时长（毫秒）')
    is_deleted = Column(Boolean, nullable=False, default=False, comment='逻辑删除标志：0-有效，1-已删除')
    created_at = Column(DateTime, nullable=False, server_default=func.utc_timestamp(), comment='服务端接收并入库时间（UTC）')

    def __repr__(self):
        return f'<DeviceWorkTimeDetail {self.device_id} {self.event_time_utc}>'


class DeviceWorkTimeDay(db.Model):
    """有效工作时间日汇总表（按UTC自然日汇总设备有效工作时长）"""
    __tablename__ = 'device_work_time_day'

    device_id = Column(String(64), primary_key=True, comment='设备ID')
    work_date = Column(Date, primary_key=True, comment='统计日期（UTC自然日）')
    duration_ms = Column(BigInteger, nullable=False, default=0, comment='当日累计有效工作时长（毫秒）')
    updated_at = Column(DateTime, nullable=False, server_default=func.utc_timestamp(), onupdate=func.utc_timestamp(), comment='最后一次汇总更新时间（UTC）')
    created_at = Column(DateTime, nullable=False, server_default=func.utc_timestamp(), comment='汇总行创建时间（UTC）')


    def __repr__(self):
        return f'<DeviceWorkTimeDay {self.device_id} {self.work_date}>'


class DeviceWorkTimeMonth(db.Model):
    """有效工作时间月汇总表（按UTC自然月汇总设备有效工作时长，单位：毫秒）"""
    __tablename__ = 'device_work_time_month'

    device_id = Column(String(64), primary_key=True, comment='设备ID')
    work_month = Column(Date, primary_key=True, comment='统计月份（UTC自然月，存储月初日期，如2025-01-01表示2025年1月）')
    duration_ms = Column(BigInteger, nullable=False, default=0, comment='当月累计有效工作时长（毫秒）')
    updated_at = Column(DateTime, nullable=False, server_default=func.utc_timestamp(), onupdate=func.utc_timestamp(), comment='最后一次汇总更新时间（UTC）')
    created_at = Column(DateTime, nullable=False, server_default=func.utc_timestamp(), comment='汇总行创建时间（UTC）')



    def __repr__(self):
        return f'<DeviceWorkTimeMonth {self.device_id} {self.work_month}>'


class DeviceWorkTimeConsumeLog(db.Model):
    """点钞工作时长消费幂等日志表（记录已处理的detail_id，防止重复消费）"""
    __tablename__ = 'device_work_time_consume_log'

    # 幂等主键：同一个 detail_id 只能插入一次
    detail_id = Column(String(36), primary_key=True, comment='对应明细ID（唯一幂等键）')
    # 当前仅定义 1=成功（后续可扩展 2=失败 等状态码）
    status = Column(TINYINT, nullable=False, default=1, comment='消费状态：1-成功')
    # 消费记录创建时间（UTC）
    consumed_at = Column(DateTime, nullable=False, server_default=func.utc_timestamp(), comment='消费时间')

    def __repr__(self):
        return f'<DeviceWorkTimeConsumeLog {self.detail_id}>'
