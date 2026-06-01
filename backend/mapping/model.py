import uuid
from backend.extensions import db
from sqlalchemy import Column, String, Integer, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy import Column, String, Boolean, ForeignKey

class DeviceMappingModel(db.Model):
    """设备型号映射表"""
    __tablename__ = 'device_mapping_model'

    id = Column(Integer, primary_key=True, autoincrement=True)
    model_name = Column(String(20), nullable=False, unique=True, comment='型号名称')
    is_deleted = Column(Boolean, nullable=False, default=False)

    # 反向关系，一个型号可以对应多个设备
    devices = relationship('Device', back_populates='model')

    def __repr__(self):
        return f'<DeviceMappingModel {self.model_name}>'




class DeviceMappingUpgradeTask(db.Model):
    """设备升级任务映射表"""
    __tablename__ = 'device_mapping_upgrade_task'

    # 复合主键：设备ID + 任务ID
    device_id = Column(String(36), ForeignKey('devices.id'), primary_key=True, comment='设备的id外键')
    task_id = Column(String(36), ForeignKey('upgrade_tasks.id'), primary_key=True, comment='分配升级任务的id外键')
    
    # 升级状态：0=未开始，1=开始升级
    status = Column(Integer, nullable=False, default=0, comment='0为未开始升级 1为开始升级 默认为0')
    
    # 确认升级：1=需要升级，0=不需要升级
    confirm_upgrade = Column(Integer, nullable=False, default=1, comment='确认是否需要升级 默认为1需要 0为不需要')
    
    # 逻辑删除标记
    is_deleted = Column(Boolean, nullable=False, default=False)

    # 关系定义
    device = relationship('Device')
    upgrade_task = relationship('UpgradeTask',back_populates='device_mappings')

    def __repr__(self):
        return f'<DeviceMappingUpgradeTask device_id={self.device_id} task_id={self.task_id}>' 
    
class InstitutionMappingUpgradeTask(db.Model):
    """机构升级任务映射表"""
    __tablename__ = 'institution_mapping_upgrade_task'

    # 复合主键：机构ID + 任务ID
    institution_id = Column(String(36), ForeignKey('institutions.id'), primary_key=True, comment='机构的id外键')
    upgrade_task_id = Column(String(36), ForeignKey('upgrade_tasks.id'), primary_key=True, comment='分配升级任务的id外键')

    # 逻辑删除标记
    is_deleted = Column(Boolean, nullable=False, default=False)

    def __repr__(self):
        return f'<InstitutionMappingUpgradeTask institution_id={self.institution_id} upgrade_task_id={self.upgrade_task_id}>'


class RolePermission(db.Model):
    """角色权限连接表"""
    __tablename__ = 'role_mapping_permissions'

    role_id = Column(String(36), ForeignKey('roles.id'), primary_key=True, comment='角色ID')
    permission_id = Column(String(36), ForeignKey('permissions.id'), primary_key=True, comment='权限ID')
    is_deleted = Column(Boolean, nullable=False, default=False)

    def __repr__(self):
        return f'<RolePermission role_id={self.role_id} permission_id={self.permission_id}>'