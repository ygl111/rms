import uuid
from backend.extensions import db
from sqlalchemy import Column, String, Enum, DateTime, Boolean, Text, ForeignKey, func
from sqlalchemy.orm import relationship


class UpgradeRecord(db.Model):
    """设备升级记录表"""
    __tablename__ = 'upgrade_records'

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), comment='主键ID (UUID)')
    task_id = Column(String(36), ForeignKey('upgrade_tasks.id', ondelete='RESTRICT'), nullable=False, index=True, comment='外键，所属升级任务ID')
    device_id = Column(String(36), ForeignKey('devices.id', ondelete='RESTRICT'), nullable=False, index=True, comment='外键，目标设备ID')
    status = Column(Enum('pending', 'success', 'failed', 'cancelled', name='upgrade_record_status'), nullable=False, default='pending', comment='升级结果/状态')
    result_message = Column(Text, comment='结果信息（如失败原因）')
    completed_at = Column(DateTime, nullable=True, comment='升级完成时间')
    created_at = Column(DateTime, nullable=False, server_default=func.utc_timestamp(), comment='创建时间')
    is_deleted = Column(Boolean, nullable=False, default=False, comment='逻辑删除标记')

    # 关系
    task = relationship('UpgradeTask', back_populates='upgrade_records')
    device = relationship('Device')

    def __repr__(self) -> str:
        return f"<UpgradeRecord id={self.id} task_id={self.task_id} device_id={self.device_id} status={self.status}>"


