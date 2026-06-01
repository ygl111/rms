import uuid
from backend.extensions import db
from sqlalchemy import Column, String, Enum, DateTime, Boolean, JSON, func, ForeignKey
from sqlalchemy.orm import relationship

class User(db.Model):
    """用户模型"""
    
    __tablename__ = 'users'

    # --- 核心字段 ---
    #为 id 字段添加了 default=lambda: str(uuid.uuid4())，这样在创建新用户时会自动生成一个 UUID。
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    account = Column(String(64), unique=True, nullable=False, comment='用户账号，业务唯一')
    password_hash = Column(String(60), nullable=False, comment='密码哈希值')
    
    # --- 基本信息字段 ---
    full_name = Column(String(64), comment='用户姓名')
    email = Column(String(128), comment='邮箱地址')
    contact_info = Column(String(32), comment='联系方式')
    address = Column(String(128), comment='地址')
    gender = Column(Enum('woman', 'man', 'none', 'others', name='user_gender'), default='none', comment='性别')

    # --- 状态与关系字段 ---
    status = Column(Enum('active', 'disabled', name='user_status'), nullable=False, default='active', comment='状态')
    role_id = Column(String(36), ForeignKey('roles.id'), comment='外键，关联角色表')
    institution_id = Column(String(36), ForeignKey('institutions.id'), comment='外键，关联机构表')

    # --- 扩展与审计字段 ---
    extra_data = Column(JSON, comment='预留扩展字段')
    is_deleted = Column(Boolean, nullable=False, default=False, comment='逻辑删除标记')
    created_at = Column(DateTime, nullable=False, server_default=func.utc_timestamp(), comment='创建时间')
    updated_at = Column(DateTime, nullable=False, server_default=func.utc_timestamp(), onupdate=func.utc_timestamp(), comment='更新时间')

    # --- 关系定义 ---
    # relationship 用于定义模型之间的关联关系，这使得我们可以通过 user.role 直接访问到关联的 Role 对象
    role = relationship('Role', back_populates='users')
    institution = relationship('Institution', back_populates='users')

    def __repr__(self):
        return f'<User {self.account}>'


