import uuid
from backend.extensions import db
from sqlalchemy import Column, String, DateTime, func, ForeignKey
from sqlalchemy.orm import relationship


class UpgradeNotifyEmail(db.Model):
    """升级通知邮箱配置模型"""
    
    __tablename__ = 'upgrade_notify_email'

    # --- 核心字段 ---
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), comment='主键UUID')
    user_id = Column(String(36), ForeignKey('users.id'), nullable=True, comment='关联用户ID（可为空，外键 users.id）')
    email = Column(String(128), unique=True, nullable=False, comment='升级通知邮箱地址')
    
    # --- 审计字段 ---
    created_at = Column(DateTime, nullable=False, server_default=func.current_timestamp(), comment='创建时间（UTC/取决于DB时区）')
    updated_at = Column(DateTime, nullable=False, server_default=func.current_timestamp(), onupdate=func.current_timestamp(), comment='更新时间（UTC/取决于DB时区）')

    # --- 关系定义 ---
    user = relationship('User')

    def __repr__(self):
        return f'<UpgradeNotifyEmail {self.email}>'


class FaultNotifyEmail(db.Model):
    """故障告警邮箱配置模型"""
    
    __tablename__ = 'fault_notify_email'

    # --- 核心字段 ---
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), comment='主键UUID')
    user_id = Column(String(36), ForeignKey('users.id'), nullable=True, comment='关联用户ID（可为空，外键 users.id）')
    email = Column(String(128), unique=True, nullable=False, comment='故障通知邮箱地址')
    
    # --- 审计字段 ---
    created_at = Column(DateTime, nullable=False, server_default=func.current_timestamp(), comment='创建时间（UTC）')
    updated_at = Column(DateTime, nullable=False, server_default=func.current_timestamp(), onupdate=func.current_timestamp(), comment='更新时间（UTC）')

    # --- 关系定义 ---
    user = relationship('User')

    def __repr__(self):
        return f'<FaultNotifyEmail {self.email}>'
