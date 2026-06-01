import uuid
from backend.extensions import db
from sqlalchemy import Column, String, Enum, DateTime, Boolean, Text, Float, Integer, ForeignKey, func,Time
from sqlalchemy.orm import relationship
import time
import random

class UpgradeTask(db.Model):
    """升级任务模型"""
    __tablename__ = 'upgrade_tasks'

    # 主键ID (UUID)
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    
    # 任务编码，业务唯一标识
    task_code = Column(
    String(32), 
    nullable=False, 
    unique=True, 
    comment='任务编码，业务唯一',
    default=lambda: f"UG-{str(int(time.time() * 1000))[-13:]}{random.randint(10, 99)}"
)
    
    # 外键关联
    firmware_id = Column(String(36), ForeignKey('firmwares.id'), nullable=False, comment='外键，目标固件ID')
    creator_id = Column(String(36), ForeignKey('users.id'), nullable=False, comment='外键，任务创建人ID')
    model_id = Column(Integer, ForeignKey('device_mapping_model.id'), nullable=False, comment='外键，设备型号ID')
    
    # 任务信息
    description = Column(Text, comment='升级任务说明')
    
    # 任务状态：active=活跃, cancelled=已取消, completed=已完成
    status = Column(Enum('active', 'cancelled', 'completed', name='task_status'), 
                   nullable=False, default='active', comment='任务状态')
    
    # 时间安排
    start_date = Column(DateTime, nullable=False, comment='计划开始日期')
    end_date = Column(DateTime, nullable=False, comment='计划结束日期')
    
    # 升级时间段控制 (0.0-24.0小时格式)
    time_arrange_start = Column(Time, nullable=False, comment='可以进行更新的时间段的开始时间')
    time_arrange_end = Column(Time, nullable=False, comment='可以进行更新的时间段的结束时间')
    
    # 系统字段
    is_deleted = Column(Boolean, nullable=False, default=False, comment='是否逻辑删除')
    created_at = Column(DateTime, nullable=False, server_default=func.utc_timestamp(), comment='创建时间')

    # 关系定义
    firmware = relationship('Firmware')
    creator = relationship('User')
    model = relationship('DeviceMappingModel')
    
    # 反向关系：一个任务可以有多个升级记录和设备映射
    upgrade_records = relationship('UpgradeRecord', back_populates='task')
    device_mappings = relationship('DeviceMappingUpgradeTask', back_populates='upgrade_task')

    def __repr__(self):
        return f'<UpgradeTask {self.task_code}>'
