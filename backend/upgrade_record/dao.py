from backend.extensions import db
from sqlalchemy.orm import contains_eager
from backend.upgrade_record.model import UpgradeRecord
from backend.device.model import Device
from backend.mapping.model import DeviceMappingModel
from backend.upgrade_task.model import UpgradeTask
from backend.firmware.model import Firmware


def get_all_upgrade_records(page=1, per_page=10, filter_params=None, sort_by='created_at', sort_order='desc', export=False):
    """获取升级记录列表，支持筛选、排序和分页。export=True 返回全部不分页。"""
    query = db.session.query(UpgradeRecord).\
        outerjoin(UpgradeTask, UpgradeRecord.task_id == UpgradeTask.id).\
        outerjoin(Firmware, UpgradeTask.firmware_id == Firmware.id).\
        outerjoin(Device, UpgradeRecord.device_id == Device.id).\
        outerjoin(DeviceMappingModel, Device.model_id == DeviceMappingModel.id).\
        options(
            contains_eager(UpgradeRecord.task).contains_eager(UpgradeTask.firmware),
            contains_eager(UpgradeRecord.device).contains_eager(Device.model)
        ).\
        filter(UpgradeRecord.is_deleted == False)

    # 筛选
    if filter_params:
        for key, value in filter_params.items():
            if value is None:
                continue
            if key == 'status':
                query = query.filter(UpgradeRecord.status == value)
            elif key == 'task_id':
                query = query.filter(UpgradeRecord.task_id == value)
            elif key == 'task_code':
                query = query.filter(UpgradeTask.task_code.like(f"%{value}%"))
            elif key == 'device_id':
                # 业务设备号模糊匹配（连接 Device）
                query = query.filter(Device.device_id.like(f"%{value}%"))
            elif key == 'model_name':
                query = query.filter(DeviceMappingModel.model_name.like(f"%{value}%"))
            elif key == 'completed_start':
                query = query.filter(UpgradeRecord.completed_at >= value)
            elif key == 'completed_end':
                query = query.filter(UpgradeRecord.completed_at <= value)
            elif key == 'created_start':
                query = query.filter(UpgradeRecord.created_at >= value)
            elif key == 'created_end':
                query = query.filter(UpgradeRecord.created_at <= value)

    # 排序
    sort_columns = {
        'created_at': UpgradeRecord.created_at,
        'completed_at': UpgradeRecord.completed_at,
        'status': UpgradeRecord.status,
        'device_id': Device.device_id,
        'task_code': UpgradeTask.task_code,
        'model_name': DeviceMappingModel.model_name,
    }
    sort_column = sort_columns.get(sort_by, UpgradeRecord.created_at)
    query = query.order_by(sort_column.desc() if sort_order == 'desc' else sort_column.asc())

    if export:
        return query.all()
    return query.paginate(page=page, per_page=per_page, error_out=False)


def get_upgrade_record_by_id(record_id: str):
    return UpgradeRecord.query.filter_by(id=record_id, is_deleted=False).first()


def delete_upgrade_record(record: UpgradeRecord):
    record.is_deleted = True
    db.session.commit()


def delete_upgrade_records_batch(ids):
    """批量逻辑删除，返回(成功ID列表, 未找到ID列表)"""
    if not ids:
        return [], ids
    records = UpgradeRecord.query.filter(
        UpgradeRecord.id.in_(ids),
        UpgradeRecord.is_deleted == False
    ).all()
    found_ids = [r.id for r in records]
    not_found_ids = [rid for rid in ids if rid not in found_ids]
    if records:
        for r in records:
            r.is_deleted = True
        db.session.commit()
    return found_ids, not_found_ids


def get_upgrade_records_for_export(filter_params=None, sort_by='created_at', sort_order='desc'):
    return get_all_upgrade_records(
        page=1, per_page=10, filter_params=filter_params,
        sort_by=sort_by, sort_order=sort_order, export=True
    )


