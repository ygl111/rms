from backend.extensions import db
from backend.mapping.model import DeviceMappingModel, DeviceMappingUpgradeTask,InstitutionMappingUpgradeTask
from backend.device.model import Device






#---------------------------------------
#---------device_mapping_model----------
#---------------------------------------
def add_device_model(model_data):
    """添加新设备型号"""
    new_model = DeviceMappingModel(**model_data)
    db.session.add(new_model)
    db.session.commit()
    return new_model

def get_all_device_models():
    """获取所有设备型号"""
    return DeviceMappingModel.query.filter_by(is_deleted=False).all()

def get_device_model_by_id(model_id):
    """根据ID获取设备型号"""
    return DeviceMappingModel.query.filter_by(id=model_id, is_deleted=False).first()

def get_device_model_by_name(model_name):
    """根据型号名称获取设备型号（未删除的）"""
    return DeviceMappingModel.query.filter_by(model_name=model_name, is_deleted=False).first()

def get_device_model_by_name_all(model_name):
    """根据型号名称获取设备型号（包括已删除的，用于唯一性检查）"""
    return DeviceMappingModel.query.filter_by(model_name=model_name).first()

def get_device_models_by_names(model_names):
    """批量根据型号名称获取设备型号（未删除的）"""
    if not model_names:
        return []
    return DeviceMappingModel.query.filter(
        DeviceMappingModel.model_name.in_(model_names),
        DeviceMappingModel.is_deleted == False
    ).all()

def batch_delete_device_models(model_ids):
    """
    批量逻辑删除设备型号
    """
    success = []
    not_found = []
    for mid in model_ids:
        model = DeviceMappingModel.query.filter_by(id=mid, is_deleted=False).first()
        if model:
            model.is_deleted = True
            success.append(mid)
        else:
            not_found.append(mid)
    db.session.commit()
    return success, not_found

def get_device_models_paged(page=1, per_page=10, filter_params=None):
    """
    分页获取所有设备型号，支持筛选
    :param page: 页码
    :param per_page: 每页数量
    :param filter_params: 筛选条件字典
    :return: SQLAlchemy Pagination 对象
    """
    query = DeviceMappingModel.query.filter_by(is_deleted=False)
    
    # 如果有筛选参数，应用筛选条件
    if filter_params:
        # 处理model_name模糊搜索
        if 'model_name' in filter_params and filter_params['model_name']:
            query = query.filter(DeviceMappingModel.model_name.like(f"%{filter_params['model_name']}%"))
    
    
    return query.paginate(page=page, per_page=per_page, error_out=False)

def update_device_model(model_id, update_data):
    """更新设备型号"""
    model = DeviceMappingModel.query.filter_by(id=model_id, is_deleted=False).first()
    if not model:
        return None
    
    # 更新字段
    for key, value in update_data.items():
        if hasattr(model, key):
            setattr(model, key, value)
    
    db.session.commit()
    return model

#----------------------------------------------
#---------device_mapping_upgrade_task----------
#----------------------------------------------
def create_device_upgrade_task_mappings(task_id, model_id, institution_ids):
    """为指定型号的所有设备创建升级任务映射

    优化点：
    - 使用单条 SQL 查询获取设备，避免基于关系对象的内存过滤导致的 N+1 查询
    - 仅选择需要的字段（设备主键），降低内存占用
    - 排除已有映射，避免重复插入导致主键冲突
    - 批量保存映射对象，提升插入性能
    """

    # 一次性查询所有符合条件的设备主键
    device_id_query = db.session.query(Device.id).filter(
        Device.institution_id.in_(institution_ids),
        Device.model_id == model_id,
        Device.is_deleted == False,
    )

    device_ids = [did for (did,) in device_id_query.all()]

    # 为每个设备创建映射记录（device_ids 为字符串 ID 列表）
    mappings = []
    for device_id in device_ids:
        mapping = DeviceMappingUpgradeTask(
            device_id=device_id,
            task_id=task_id,
            status=0,  # 默认未开始
            confirm_upgrade=1,  # 默认需要升级
            is_deleted=False
        )
        db.session.add(mapping)
        mappings.append(mapping)

    return mappings


def delete_device_upgrade_task_mappings_by_task_id(task_id):
    """根据任务ID逻辑删除所有相关的设备升级任务映射"""
    mappings = DeviceMappingUpgradeTask.query.filter_by(
        task_id=task_id,
        is_deleted=False
    ).all()
    
    for mapping in mappings:
        mapping.is_deleted = True
        db.session.add(mapping)
    
    return mappings


def update_confirm_upgrade_by_device_ids(task_id, device_ids, confirm_upgrade):
    """在指定任务下，按给定 device_ids 批量更新 confirm_upgrade。"""
    if not device_ids:
        return 0
    updated = db.session.query(DeviceMappingUpgradeTask).\
        filter(
            DeviceMappingUpgradeTask.task_id == task_id,
            DeviceMappingUpgradeTask.device_id.in_(device_ids),
            DeviceMappingUpgradeTask.is_deleted == False,
        ).\
        update({DeviceMappingUpgradeTask.confirm_upgrade: confirm_upgrade}, synchronize_session=False)
    return updated


#---------------------------------------------------
#---------intsitution_mapping_upgrade_task----------
#---------------------------------------------------

def create_institution_upgrade_task_mappings(task_id, institution_ids):
    """为指定机构创建升级任务映射"""
    mappings = []
    for institution_id in institution_ids:
        mapping = InstitutionMappingUpgradeTask(
            institution_id=institution_id,
            upgrade_task_id=task_id,
            is_deleted=False
        )
        db.session.add(mapping)
        mappings.append(mapping)
    
    return mappings