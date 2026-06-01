import uuid
from backend.extensions import db
from sqlalchemy import Column, String, DateTime, Boolean, Integer, Text, func, Enum, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.mysql import BIGINT

class Firmware(db.Model):
    """固件信息表"""
    __tablename__ = 'firmwares'

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), comment='主键ID (UUID)')
    firmware_name = Column(String(128), nullable=False, comment='固件文件名/名称')
    version = Column(String(128), nullable=False, comment='固件版本号')
    file_size = Column(BIGINT, comment='固件大小(Bytes)')
    md5_hash = Column(String(32), comment='固件MD5值')
    storage_path = Column(String(255), nullable=False, comment='文件存储路径')
    description = Column(Text, comment='固件描述')
    status = Column(Enum('normal', 'deprecated', name='firmware_status'), nullable=False, default='normal', comment='固件状态')
    is_deleted = Column(Boolean, nullable=False, default=False, comment='是否逻辑删除')
    
    # --- 外键定义 ---
    uploader_id = Column(String(36), ForeignKey('users.id', ondelete='RESTRICT'), nullable=False, comment='外键，上传人ID')
    compatible_model_id = Column(Integer, ForeignKey('device_mapping_model.id'), nullable=False, comment='固件支持的型号ID')

    # --- 时间戳 ---
    uploaded_at = Column(DateTime, nullable=False, server_default=func.utc_timestamp(), comment='上传时间')

    # --- 关系定义 (Relationships) ---
    uploader = relationship('User') # 假设User模型存在
    compatible_model = relationship('DeviceMappingModel') # 假设DeviceMappingModel模型存在

    def __repr__(self):
        return f'<Firmware {self.firmware_name} v{self.version}>'

