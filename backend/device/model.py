import uuid
from backend.extensions import db
from sqlalchemy import Column, String, Enum, DateTime, Boolean, JSON, func, Integer, ForeignKey
from sqlalchemy.orm import relationship
# [修改] 导入移动后的 DeviceMappingModel
from backend.mapping.model import DeviceMappingModel


class Device(db.Model):
    """设备模型"""
    __tablename__ = 'devices'

    # [修改] id 改为 UUID 主键，自动生成
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    # [新增] device_id 字段，存储实际设备 ID，非空但不唯一
    device_id = Column(String(64), unique=True, nullable=False, comment='设备ID')
    device_type = Column(Integer, nullable=False,default=0, comment='设备类型')
    firmware_version = Column(String(40), comment='当前固件版本')
    ip_endpoint = Column(String(50), comment='设备IP地址和端口')
    online_status = Column(Enum('online', 'offline','maintenance','scrapped', name='device_online_status'), nullable=False, default='offline')
    last_online_time = Column(DateTime, comment='最后在线时间')
    
    institution_id = Column(String(36), ForeignKey('institutions.id'), nullable=False, comment='外键，所属机构ID')
    model_id = Column(Integer, ForeignKey('device_mapping_model.id'), nullable=False, comment='外键，设备型号ID')
    
    extra_data = Column(JSON, comment='预留扩展字段')
    is_deleted = Column(Boolean, nullable=False, default=False)
    description = Column(String(256), comment='设备备注')
    created_at = Column(DateTime, nullable=False, server_default=func.utc_timestamp())
    updated_at = Column(DateTime, nullable=False, server_default=func.utc_timestamp(), onupdate=func.utc_timestamp())
    
    # 新增的字段
    currency_library_version = Column(String(8192), comment='币种库版本')
    hardware_version = Column(String(512), comment='硬件版本')
    main_software_version = Column(String(1024), comment='主程序版本')
    authentication_code = Column(String(45), comment='鉴权码')
    suffix_marker = Column(String(10), comment='后缀标记')
    maintenance_threshold = Column(Integer, nullable=False, default=0, comment='维护阈值')
    latitude = Column(db.Numeric(10, 7), comment='纬度')
    longitude = Column(db.Numeric(10, 7), comment='经度')
    address = Column(String(512), comment='设备详细地址')

    # 关系定义(关系实例)
    institution = relationship('Institution', back_populates='devices')
    model = relationship('DeviceMappingModel', back_populates='devices')

    def __repr__(self):
        return f'<Device {self.device_id}>'
