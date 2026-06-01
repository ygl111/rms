# backend/institution/model.py
import uuid
from backend.extensions import db
from sqlalchemy import Column, String, Enum, DateTime, Boolean, JSON, func, Integer,ForeignKey
from sqlalchemy.orm import relationship

class Institution(db.Model):
    """机构模型"""
    __tablename__ = 'institutions'

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    institution_code = Column(String(64), unique=True, nullable=False, comment='机构编码，业务唯一')
    institution_name = Column(String(64), nullable=False, comment='机构名称')
    parent_id = Column(String(36), ForeignKey('institutions.id', ondelete='RESTRICT', onupdate='RESTRICT'), nullable=True, comment='父机构ID，外键自关联')
    level = Column(Integer, comment='机构层级')
    address = Column(String(128), comment='地址')
    contact_info = Column(String(128), comment='联系方式')
    status = Column(Enum('active', 'disabled', name='institution_status'), nullable=False, default='active', comment='状态')
    extra_data = Column(JSON, comment='预留扩展字段')
    is_deleted = Column(Boolean, nullable=False, default=False, comment='逻辑删除标记')
    created_at = Column(DateTime, nullable=False, server_default=func.utc_timestamp(), comment='创建时间')
    updated_at = Column(DateTime, nullable=False, server_default=func.utc_timestamp(), onupdate=func.utc_timestamp(), comment='更新时间')

    # 父机构关系（自关联）
    parent = relationship('Institution', remote_side=[id], backref='children', uselist=False)
    # 定义与 User 的反向关系
    users = relationship('User', back_populates='institution')
    # [新增] 定义与 Device 的反向关系
    devices = relationship('Device', back_populates='institution')

    def __repr__(self):
        return f'<Institution {self.institution_name}>'