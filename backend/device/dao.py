from backend.extensions import db
from backend.device.model import Device
# 导入关联表模型（用于按关联表字段排序）
from backend.institution.model import Institution
from backend.mapping.model import DeviceMappingModel
from sqlalchemy.orm import contains_eager
# 导入生成base64 UUID的模块
import uuid
import base64
from datetime import datetime
# --- Device DAO ---

def add_device(device_data):
    """添加新设备"""
    new_device = Device(**device_data)
    db.session.add(new_device)
    db.session.commit()
    return new_device

def add_devices_batch(device_data_list):
    """
    批量添加设备 - 高性能且安全的版本
    使用分批插入策略，能够准确识别冲突的设备ID
    
    :param device_data_list: 设备数据字典列表，每个字典应包含设备的所有必要字段
    :return: 元组(成功插入的device_id列表, 失败插入的device_id列表及原因)
    """
    if not device_data_list:
        return [], []
    
    # 1. 为每个设备数据生成UUID主键和时间戳

    current_time = datetime.now()
    
    prepared_data = []
    device_id_to_data = {}
    
    for device_data in device_data_list:
        # 生成UUID主键
        device_uuid = str(uuid.uuid4())
        
        # 准备设备数据，只填充必要的字段
        full_device_data = {
            'id': device_uuid,
            'device_id': device_data['device_id'],
            'model_id': device_data['model_id'],
            'institution_id': device_data['institution_id'],
            'description': device_data.get('description'),
            'maintenance_threshold': device_data.get('maintenance_threshold', 0),
            'latitude': device_data.get('latitude'),
            'longitude': device_data.get('longitude'),
            'address': device_data.get('address'),
        }
        
        prepared_data.append(full_device_data)
        device_id_to_data[device_data['device_id']] = full_device_data
    
    # 2. 尝试批量插入，如果失败则回退到逐条插入
    success_device_ids = []
    failed_device_ids = []
    
    try:
        # 首先尝试批量插入（最高效）
        db.session.bulk_insert_mappings(Device, prepared_data)
        db.session.commit()
        
        # 如果成功，返回所有设备ID
        success_device_ids = [data['device_id'] for data in prepared_data]
        return success_device_ids, failed_device_ids
        
    except Exception as bulk_error:
        # 批量插入失败，回退到逐条插入以识别具体冲突
        db.session.rollback()
        
        # 3. 逐条插入，精确识别冲突设备
        for device_data in prepared_data:
            try:
                new_device = Device(**device_data)
                db.session.add(new_device)
                db.session.commit()
                success_device_ids.append(device_data['device_id'])
                
            except Exception as single_error:
                db.session.rollback()
                error_msg = str(single_error)
                
                # 判断是否为设备ID重复错误
                if 'Duplicate entry' in error_msg or 'UNIQUE constraint failed' in error_msg:
                    failed_device_ids.append((device_data['device_id'], "设备ID已存在"))
                else:
                    failed_device_ids.append((device_data['device_id'], f"插入失败: {error_msg}"))
    
    return success_device_ids, failed_device_ids

def check_devices_exist_batch(device_ids):
    """
    批量检查设备ID是否已存在
    
    :param device_ids: 设备ID列表
    :return: 已存在的设备ID集合
    """
    if not device_ids:
        return set()
        
    # 使用 with_entities + scalars() 直接获取设备ID列表，避免元组格式
    existing_device_ids = db.session.query(Device.device_id).filter(
        Device.device_id.in_(device_ids),
        Device.is_deleted == False
    ).all()
    """ 
        优化：
        existing_ids = db.session.query(Device.device_id).filter(
    Device.device_id.in_(device_ids),
    Device.is_deleted == False
).scalars().all()
return set(existing_ids)
    """
    # existing_device_ids 是元组列表，如 [('device_001',), ('device_002',)]
    # 每个元组的第一个元素就是device_id
    return {device_id_tuple[0] for device_id_tuple in existing_device_ids}

# [新增] 检查设备 ID 是否存在且未删除
def get_device_by_device_id(device_id):
    """根据 device_id 获取设备（包括已逻辑删除的）"""
    return Device.query.filter_by(device_id=device_id).first()

def get_device_by_id(device_id):
    """根据ID获取设备"""
    return Device.query.get(device_id)

def get_all_devices(page, per_page, filter_params=None, sort_by='last_online_time', sort_order='desc', export=False):
    """
    获取设备列表，支持筛选、排序和分页。export=True时返回全部数据不分页。
    """
    query = db.session.query(Device).\
        outerjoin(Institution, Device.institution_id == Institution.id).\
        outerjoin(DeviceMappingModel, Device.model_id == DeviceMappingModel.id).\
        options(contains_eager(Device.institution), contains_eager(Device.model)).\
        filter(Device.is_deleted == False)
    # 筛选条件同上
    if filter_params:
        for key, value in filter_params.items():
            if key == 'model_id':
                query = query.filter(Device.model_id == value)
            elif key == 'institution_id':
                query = query.filter(Device.institution_id == value)
            elif key == 'online_status':
                query = query.filter(Device.online_status == value)
            elif key == 'device_id':
                query = query.filter(Device.device_id.like(f"%{value}%"))
            elif key == 'firmware_version':
                query = query.filter(Device.firmware_version.like(f"%{value}%"))
            elif key == 'ip_endpoint':
                query = query.filter(Device.ip_endpoint.like(f"{value}%"))
            elif key == 'created_at_start':
                query = query.filter(Device.created_at >= value)
            elif key == 'created_at_end':
                query = query.filter(Device.created_at <= value)
    # 排序
    sort_columns = {
        'device_id': Device.device_id,
        'model_id': Device.model_id,
        'institution_code': Institution.institution_code,
        'institution_name': Institution.institution_name,
        'firmware_version': Device.firmware_version,
        'ip_endpoint': Device.ip_endpoint,
        'online_status': Device.online_status,
        'last_online_time': Device.last_online_time,
        'created_at': Device.created_at
    }
    sort_columns= sort_columns.get(sort_by, Device.last_online_time)
    query = query.order_by(sort_columns.desc() if sort_order == 'desc' else sort_columns.asc())
    if export:
        return query.all()
    else:
        return query.paginate(page=page, per_page=per_page, error_out=False)

def update_device(device, update_data):
    """更新设备信息"""
    for key, value in update_data.items():
        if hasattr(device, key):
            setattr(device, key, value)
    db.session.commit()
    return device

def delete_device(device):
    """
    逻辑删除一个设备。
    :param device: 要删除的 Device 对象
    """
    # 1. 将 is_deleted 标志位设为 True
    device.is_deleted = True
    
    db.session.commit()

def delete_devices_batch(device_ids):
    """
    批量逻辑删除多个设备。
    :param device_ids: 要删除的设备ID列表
    :return: 成功删除的设备ID列表和未找到的设备ID列表
    """
    # 查找所有存在的设备（排除已经被逻辑删除的设备）
    existing_devices = Device.query.filter(
        Device.id.in_(device_ids),
        Device.is_deleted == False
    ).all()
    
    # 获取找到的设备ID列表
    found_device_ids = [device.id for device in existing_devices]
    
    # 计算未找到的设备ID列表
    not_found_device_ids = [device_id for device_id in device_ids if device_id not in found_device_ids]
    
    # 批量更新找到的设备：设置 is_deleted 为 True 并修改 device_id 字段
    if existing_devices:
        for device in existing_devices:
            # 1. 设置逻辑删除标志
            device.is_deleted = True    
        db.session.commit()
    
    # 返回成功删除的ID列表和未找到的ID列表
    return found_device_ids, not_found_device_ids

def get_devices_for_export(filter_params=None):
    """
    获取用于导出的设备数据（不分页，返回所有符合条件的记录）
    :param filter_params: 筛选条件字典
    :return: 设备列表
    """
    # 构建基础查询，关联institution和model表
    query = db.session.query(Device).\
        outerjoin(Institution, Device.institution_id == Institution.id).\
        outerjoin(DeviceMappingModel, Device.model_id == DeviceMappingModel.id).\
        options(contains_eager(Device.institution), contains_eager(Device.model)).\
        filter(Device.is_deleted == False)
    
    # 应用筛选条件（复用原有的筛选逻辑）
    if filter_params:
        for key, value in filter_params.items():
            if key == 'model_id':
                query = query.filter(Device.model_id == value)
            elif key == 'institution_id':
                query = query.filter(Device.institution_id == value)
            elif key == 'online_status':
                query = query.filter(Device.online_status == value)
            elif key == 'device_id':
                query = query.filter(Device.device_id.like(f"%{value}%"))
            elif key == 'firmware_version':
                query = query.filter(Device.firmware_version.like(f"%{value}%"))
            elif key == 'ip_endpoint':
                query = query.filter(Device.ip_endpoint.like(f"{value}%"))
    
    # 按创建时间排序
    query = query.order_by(Device.created_at.desc())
    
    # 返回所有匹配的设备（不分页）
    return query.all()
