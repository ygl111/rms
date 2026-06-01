# backend/role/model.py
import uuid
from backend.extensions import db
from sqlalchemy import Column, String, DateTime, Boolean, JSON, func, Enum
from sqlalchemy.orm import relationship

class Role(db.Model):
    """角色模型"""
    __tablename__ = 'roles'

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    role_code = Column(String(32), unique=True, nullable=False, comment='角色编码，业务唯一')
    role_name = Column(String(64), nullable=False, comment='角色名称')
    description = Column(String(255), comment='角色描述')
    status = Column(Enum('active', 'disabled', name='role_status_enum'), nullable=False, default='active', comment='角色状态')
    extra_data = Column(JSON, comment='预留扩展字段')
    is_deleted = Column(Boolean, nullable=False, default=False, comment='逻辑删除标记')
    created_at = Column(DateTime, nullable=False, server_default=func.utc_timestamp(), comment='创建时间')
    updated_at = Column(DateTime, nullable=False, server_default=func.utc_timestamp(), onupdate=func.utc_timestamp(), comment='更新时间')

    # 定义与 User 的反向关系
    # back_populates='role' 必须与 User 模型中的 back_populates='users' 对应
    users = relationship('User', back_populates='role')

    # 角色与权限的多对多关系
    permissions = relationship(
        'Permission',
        secondary='role_mapping_permissions',
        backref='roles',
        lazy='dynamic'
    )

    def __repr__(self):
        return f'<Role {self.role_name}>'


class Permission(db.Model):
    """权限定义表"""
    __tablename__ = 'permissions'

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), comment='主键ID (UUID)')
    permission_code = Column(String(64), unique=True, nullable=False, comment='权限编码，程序判断用，如: user:create')
    permission_name = Column(String(64), nullable=False, comment='权限名称，界面显示用，如: 新增用户')
    description = Column(String(255), comment='权限描述')
    is_deleted = Column(Boolean, nullable=False, default=False)

    # 可选：如果需要直接通过 permission.roles 获取所有角色，无需额外定义，已在 Role 的 backref 中实现

    



    def __repr__(self):
        return f'<Permission {self.permission_code}>'