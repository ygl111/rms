from backend.extensions import db
from backend.firmware.model import Firmware
from sqlalchemy.orm import joinedload

def get_firmware_by_id(firmware_id):
    """根据ID获取固件信息"""
    return Firmware.query.filter_by(id=firmware_id, is_deleted=False).first()

def get_all_firmwares(page=1, per_page=10):
    """分页获取所有固件列表"""
    return Firmware.query.filter_by(is_deleted=False).paginate(
        page=page, 
        per_page=per_page, 
        error_out=False
    )

def add_firmware(firmware_data):
    """添加新固件记录"""
    new_firmware = Firmware(**firmware_data)
    db.session.add(new_firmware)
    db.session.commit()
    return new_firmware

def update_firmware(firmware, update_data):
    """更新固件信息"""
    for key, value in update_data.items():
        if hasattr(firmware, key):
            setattr(firmware, key, value)
    db.session.commit()
    return firmware

def delete_firmware(firmware):
    """逻辑删除固件"""
    firmware.is_deleted = True
    db.session.commit()
    return firmware

def get_firmwares_by_model_id(model_id):
    """根据设备型号ID获取固件列表"""
    return Firmware.query.filter_by(
        compatible_model_id=model_id, 
        is_deleted=False
    ).all()

def get_firmware_by_version(version, model_id=None):
    """根据版本号获取固件（可选择型号）"""
    query = Firmware.query.filter_by(version=version, is_deleted=False)
    if model_id:
        query = query.filter_by(compatible_model_id=model_id)
    return query.first()

def get_firmwares(page=1, per_page=10, filter_params=None, sort_by='uploaded_at', sort_order='desc'):
    query = Firmware.query.options(joinedload(Firmware.uploader), joinedload(Firmware.compatible_model)).filter(Firmware.is_deleted == False)
    # 筛选条件
    if filter_params:
        if 'firmware_name' in filter_params:
            query = query.filter(Firmware.firmware_name.like(f"%{filter_params['firmware_name']}%"))
        if 'version' in filter_params:
            query = query.filter(Firmware.version.like(f"%{filter_params['version']}%"))
        if 'compatible_model_id' in filter_params:
            query = query.filter(Firmware.compatible_model_id == filter_params['compatible_model_id'])
        if 'uploaded_at_start' in filter_params:
            query = query.filter(Firmware.uploaded_at >= filter_params['uploaded_at_start'])
        if 'uploaded_at_end' in filter_params:
            query = query.filter(Firmware.uploaded_at <= filter_params['uploaded_at_end'])
    # 排序字段映射
    sort_columns = {
        'firmware_name': Firmware.firmware_name,
        'version': Firmware.version,
        'file_size': Firmware.file_size,
        'compatible_model.id': Firmware.compatible_model_id,
        'uploader.id': Firmware.uploader_id,
        'uploaded_at': Firmware.uploaded_at
    }
    sort_column = sort_columns.get(sort_by, Firmware.uploaded_at)
    query = query.order_by(sort_column.desc() if sort_order == 'desc' else sort_column.asc())
    return query.paginate(page=page, per_page=per_page, error_out=False)

def batch_delete_firmwares(firmware_ids):
    """
    批量逻辑删除固件
    """
    # 直接在数据库层面执行批量更新，只执行一次 UPDATE 语句
    result = Firmware.query.filter(
        Firmware.id.in_(firmware_ids),
        Firmware.is_deleted == False
    ).update(
        {"is_deleted": True}, 
        synchronize_session=False
    )
    
    db.session.commit()
    return result

def get_firmwares_for_export(filter_params=None, sort_by='uploaded_at', sort_order='desc'):
    query = Firmware.query.options(joinedload(Firmware.uploader), joinedload(Firmware.compatible_model)).filter(Firmware.is_deleted == False)
    # 筛选条件同 get_firmwares
    if filter_params:
        if 'firmware_name' in filter_params:
            query = query.filter(Firmware.firmware_name.like(f"%{filter_params['firmware_name']}%"))
        if 'version' in filter_params:
            query = query.filter(Firmware.version.like(f"%{filter_params['version']}%"))
        if 'compatible_model_id' in filter_params:
            query = query.filter(Firmware.compatible_model_id == filter_params['compatible_model_id'])
        if 'uploaded_at_start' in filter_params:
            query = query.filter(Firmware.uploaded_at >= filter_params['uploaded_at_start'])
        if 'uploaded_at_end' in filter_params:
            query = query.filter(Firmware.uploaded_at <= filter_params['uploaded_at_end'])
    sort_columns = {
        'firmware_name': Firmware.firmware_name,
        'version': Firmware.version,
        'file_size': Firmware.file_size,
        'compatible_model.id': Firmware.compatible_model_id,
        'uploader.id': Firmware.uploader_id,
        'uploaded_at': Firmware.uploaded_at
    }
    sort_column = sort_columns.get(sort_by, Firmware.uploaded_at)
    query = query.order_by(sort_column.desc() if sort_order == 'desc' else sort_column.asc())
    return query.all()
