from backend.extensions import db
from sqlalchemy.orm import contains_eager
from backend.fault.model import Fault
from backend.device.model import Device
from backend.mapping.model import DeviceMappingModel
from backend.fault.model import FaultOperationLog
from backend.user.model import User


def get_all_faults(page=1, per_page=10, filter_params=None, sort_by='fault_time', sort_order='desc', export=False):
    """获取故障列表，支持筛选、排序和分页。export=True 返回全部不分页。"""
    query = db.session.query(Fault).\
        outerjoin(Device, Fault.device_id == Device.id).\
        outerjoin(DeviceMappingModel, Device.model_id == DeviceMappingModel.id).\
        options(
            contains_eager(Fault.device).contains_eager(Device.model)
        ).\
        filter(Fault.is_deleted == False)

    # 筛选
    if filter_params:
        for key, value in filter_params.items():
            if value is None:
                continue
            if key == 'status':
                query = query.filter(Fault.status == value)
            elif key == 'device_id':
                # 业务设备号模糊匹配（连接 Device）
                query = query.filter(Device.device_id.like(f"%{value}%"))
            elif key == 'fault_code':
                query = query.filter(Fault.fault_code.like(f"%{value}%"))
            elif key == 'fault_level':
                query = query.filter(Fault.fault_level == value)
            elif key == 'fault_time_start':
                query = query.filter(Fault.fault_time >= value)
            elif key == 'fault_time_end':
                query = query.filter(Fault.fault_time <= value)
            elif key == 'model_name':
                query = query.filter(DeviceMappingModel.model_name.like(f"%{value}%"))

    # 排序
    sort_columns = {
        'fault_time': Fault.fault_time,
        'created_at': Fault.created_at,
        'status': Fault.status,
        'fault_level': Fault.fault_level,
        'device_id': Device.device_id,
        'fault_code':Fault.fault_code,
        'model_name': DeviceMappingModel.model_name,
    }
    sort_column = sort_columns.get(sort_by, Fault.fault_time)
    query = query.order_by(sort_column.desc() if sort_order == 'desc' else sort_column.asc())

    if export:
        return query.all()
    return query.paginate(page=page, per_page=per_page, error_out=False)


def get_non_fault_devices():
    """
    获取非故障设备：
    非故障设备 = 所有在线/离线设备 - 当前处于未维修/维修中的故障设备。
    """
    # 故障中（未处理、处理中）的设备主键集合
    faulty_device_id_subquery = db.session.query(Fault.device_id).filter(
        Fault.is_deleted == False,
        Fault.status.in_(['unprocessed', 'processing'])
    )

    query = db.session.query(Device).\
        outerjoin(DeviceMappingModel, Device.model_id == DeviceMappingModel.id).\
        options(contains_eager(Device.model)).\
        filter(
            Device.is_deleted == False,
            Device.online_status.in_(['online', 'offline']),
            ~Device.id.in_(faulty_device_id_subquery)
        ).\
        order_by(Device.last_online_time.desc(), Device.device_id.asc())

    return query.all()


def get_fault_devices():
    """
    获取故障设备：
    从故障列表中筛选状态为未处理/处理中且未删除的故障对应设备。
    """
    query = db.session.query(Device).\
        join(Fault, Fault.device_id == Device.id).\
        outerjoin(DeviceMappingModel, Device.model_id == DeviceMappingModel.id).\
        options(contains_eager(Device.model)).\
        filter(
            Fault.is_deleted == False,
            Fault.status.in_(['unprocessed', 'processing']),
            Device.is_deleted == False
        ).\
        distinct(Device.id).\
        order_by(Device.last_online_time.desc(), Device.device_id.asc())

    return query.all()


def get_fault_by_id(fault_id: str):
    return Fault.query.filter_by(id=fault_id, is_deleted=False).first()


def update_fault_status(fault: Fault, new_status: str):
    fault.status = new_status
    db.session.commit()
    return fault


def delete_fault(fault: Fault):
    fault.is_deleted = True
    db.session.commit()


def delete_faults_batch(ids):
    """批量逻辑删除，返回(成功ID列表, 未找到ID列表)"""
    if not ids:
        return [], ids
    existing_faults = Fault.query.filter(
        Fault.id.in_(ids),
        Fault.is_deleted == False
    ).all()
    found_ids = [f.id for f in existing_faults]
    not_found_ids = [fid for fid in ids if fid not in found_ids]

    if existing_faults:
        for f in existing_faults:
            f.is_deleted = True
        db.session.commit()

    return found_ids, not_found_ids


def get_faults_for_export(filter_params=None, sort_by='fault_time', sort_order='desc'):
    return get_all_faults(
        page=1, per_page=10, filter_params=filter_params,
        sort_by=sort_by, sort_order=sort_order, export=True
    )


# ----------------- Fault Operation Logs -----------------
def create_fault_log(fault_id: str, operator_id: str, content: str):
    log = FaultOperationLog(fault_id=fault_id, operator_id=operator_id, content=content)
    db.session.add(log)
    db.session.commit()
    return log


def get_all_fault_logs(page=1, per_page=10, filter_params=None, sort_by='operation_time', sort_order='desc', export=False):
    query = db.session.query(FaultOperationLog).\
        outerjoin(User, FaultOperationLog.operator_id == User.id).\
        outerjoin(Fault, FaultOperationLog.fault_id == Fault.id).\
        outerjoin(Device, Fault.device_id == Device.id).\
        outerjoin(DeviceMappingModel, Device.model_id == DeviceMappingModel.id).\
        options(
            contains_eager(FaultOperationLog.operator),
            contains_eager(FaultOperationLog.fault).contains_eager(Fault.device).contains_eager(Device.model)
        ).\
        filter(FaultOperationLog.is_deleted == False)

    if filter_params:
        for key, value in filter_params.items():
            if value is None:
                continue
            if key == 'fault_id':
                query = query.filter(FaultOperationLog.fault_id == value)
            elif key == 'operator_id' or key == 'creator_id':
                query = query.filter(FaultOperationLog.operator_id == value)
            elif key == 'content':
                query = query.filter(FaultOperationLog.content.like(f"%{value}%"))
            elif key == 'operation_time_start':
                query = query.filter(FaultOperationLog.operation_time >= value)
            elif key == 'operation_time_end':
                query = query.filter(FaultOperationLog.operation_time <= value)
            elif key == 'device_id':
                query = query.filter(Device.device_id.like(f"%{value}%"))
            elif key == 'model_name':
                query = query.filter(DeviceMappingModel.model_name.like(f"%{value}%"))
            elif key == 'fault_code':
                query = query.filter(Fault.fault_code.like(f"%{value}%"))
            elif key == 'fault_level':
                query = query.filter(Fault.fault_level == value)
            elif key == 'creator_full_name':
                query = query.filter(User.full_name.like(f"%{value}%"))

    sort_columns = {
        'operation_time': FaultOperationLog.operation_time,
        'operator_id': FaultOperationLog.operator_id,
        'creator_id': FaultOperationLog.operator_id,
        'creator_full_name': User.full_name,
        'device_id': Device.device_id,
        'model_name': DeviceMappingModel.model_name,
        'fault_code': Fault.fault_code,
        'fault_level': Fault.fault_level,
    }
    sort_column = sort_columns.get(sort_by, FaultOperationLog.operation_time)
    query = query.order_by(sort_column.desc() if sort_order == 'desc' else sort_column.asc())

    if export:
        return query.all()
    return query.paginate(page=page, per_page=per_page, error_out=False)


def get_fault_log_by_id(log_id: str):
    return FaultOperationLog.query.filter_by(id=log_id, is_deleted=False).first()


def delete_fault_log(log: FaultOperationLog):
    log.is_deleted = True
    db.session.commit()


def delete_fault_logs_batch(ids):
    if not ids:
        return [], ids
    logs = FaultOperationLog.query.filter(
        FaultOperationLog.id.in_(ids),
        FaultOperationLog.is_deleted == False
    ).all()
    found_ids = [l.id for l in logs]
    not_found_ids = [lid for lid in ids if lid not in found_ids]
    if logs:
        for l in logs:
            l.is_deleted = True
        db.session.commit()
    return found_ids, not_found_ids


def get_fault_logs_for_export(filter_params=None, sort_by='operation_time', sort_order='desc'):
    return get_all_fault_logs(
        page=1, per_page=10, filter_params=filter_params, sort_by=sort_by, sort_order=sort_order, export=True
    )


