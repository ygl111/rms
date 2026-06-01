import uuid
from backend.extensions import db
from sqlalchemy import Column, String, Enum, DateTime, Boolean, JSON, ForeignKey, Integer, Text, func
from sqlalchemy.orm import relationship


class Fault(db.Model):
    """设备故障信息表"""
    __tablename__ = 'faults'

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), comment='主键ID (UUID)')
    device_id = Column(String(36), ForeignKey('devices.id', ondelete='RESTRICT'), nullable=False, index=True, comment='外键，故障设备ID')
    fault_code = Column(String(64), comment='故障代码（事件等级）')
    description = Column(String(1024), comment='故障描述(事件内容)')
    status = Column(Enum('unprocessed', 'processing', 'processed', name='fault_status'), nullable=False, default='unprocessed', comment='处理状态')
    fault_time = Column(DateTime, nullable=False, comment='故障发生时间')
    extra_data = Column(JSON, comment='预留扩展字段')
    created_at = Column(DateTime, nullable=False, server_default=func.utc_timestamp(), comment='创建时间')
    is_deleted = Column(Boolean, nullable=False, default=False, comment='逻辑删除标记')
    img = Column(String(256), comment='故障图标存储位置')
    fault_level = Column(Integer, comment='故障等级(事件等级)')

    # 关系
    device = relationship('Device')
    operation_logs = relationship('FaultOperationLog', back_populates='fault')

    def __repr__(self) -> str:
        return f"<Fault id={self.id} device_id={self.device_id} status={self.status}>"


class FaultOperationLog(db.Model):
    """故障处理操作日志表"""
    __tablename__ = 'fault_operation_logs'

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), comment='主键ID (UUID)')
    fault_id = Column(String(36), ForeignKey('faults.id', ondelete='RESTRICT'), nullable=False, index=True, comment='外键，关联的故障ID')
    operator_id = Column(String(36), ForeignKey('users.id', ondelete='RESTRICT'), nullable=False, index=True, comment='外键，操作人ID')
    content = Column(Text, nullable=False, comment='操作内容/记录')
    operation_time = Column(DateTime, nullable=False, server_default=func.utc_timestamp(), comment='操作时间')
    is_deleted = Column(Boolean, nullable=False, default=False, comment='逻辑删除标记')

    # 关系
    fault = relationship('Fault', back_populates='operation_logs')
    operator = relationship('User')

    def __repr__(self) -> str:
        return f"<FaultOperationLog id={self.id} fault_id={self.fault_id} operator_id={self.operator_id}>"