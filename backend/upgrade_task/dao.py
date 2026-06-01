from backend.extensions import db
from backend.upgrade_task.model import UpgradeTask
from backend.firmware.model import Firmware
from backend.mapping.model import DeviceMappingModel
from backend.user.model import User
from sqlalchemy.orm import contains_eager
from backend.firmware.model import Firmware
from backend.mapping.model import DeviceMappingModel
def create_upgrade_task(task_data):
    """创建升级任务"""
    new_task = UpgradeTask(**task_data)
    db.session.add(new_task)
    db.session.flush()  # 获取生成的ID但不提交事务
    return new_task


def get_upgrade_task_by_id(task_id):
    """根据ID获取升级任务"""
    return UpgradeTask.query.filter_by(id=task_id, is_deleted=False).first()




def get_all_upgrade_tasks(page=1, per_page=10, filter_params=None, sort_by=None, sort_order='asc', export=False):
    """
    获取升级任务列表，支持筛选、排序和分页，关联firmware和model表
    """
    query = db.session.query(UpgradeTask).\
        outerjoin(Firmware, UpgradeTask.firmware_id == Firmware.id).\
        outerjoin(DeviceMappingModel, UpgradeTask.model_id == DeviceMappingModel.id).\
        outerjoin(User, UpgradeTask.creator_id == User.id).\
        options(
            contains_eager(UpgradeTask.firmware),
            contains_eager(UpgradeTask.model),
            contains_eager(UpgradeTask.creator)
        ).\
        filter(UpgradeTask.is_deleted == False)


    # 应用筛选条件
    if filter_params:
        for key, value in filter_params.items():
            if key == 'firmware_id':
                query = query.filter(UpgradeTask.firmware_id == value)
            elif key == 'model_id':
                query = query.filter(UpgradeTask.model_id == value)
            elif key == 'status':
                query = query.filter(UpgradeTask.status == value)
            elif key == 'task_code':
                query = query.filter(UpgradeTask.task_code.like(f"%{value}%"))
            elif key == 'creator_id':
                query = query.filter(UpgradeTask.creator_id == value)

    sort_columns = {
        'task_code': UpgradeTask.task_code,
        'status': UpgradeTask.status,
        'start_date': UpgradeTask.start_date,
        'end_date': UpgradeTask.end_date,
        'created_at': UpgradeTask.created_at,
        'firmware.version': Firmware.version,
        'firmware.firmware_name': Firmware.firmware_name,
        'model.model_name': DeviceMappingModel.model_name,
        'creator.full_name': User.full_name
    }
    sort_column = sort_columns.get(sort_by,UpgradeTask.created_at)
    query=query.order_by(sort_column.desc() if sort_order == 'desc' else sort_column.asc())
    if(export):
        return query.all()
    else:
        return query.paginate(page=page, per_page=per_page, error_out=False)



def delete_upgrade_task(task):
    """逻辑删除升级任务"""
    task.is_deleted = True
    # 注意：不在这里commit，由调用方统一提交事务
    return task

# --- 新增：升级任务 update、批量删除、导出 ---
def update_upgrade_task(task, update_data):
    for key, value in update_data.items():
        if hasattr(task, key) and value is not None:
            setattr(task, key, value)
    return task

def delete_upgrade_tasks_batch(ids):
    success_ids = []
    failed_ids = []
    for task_id in ids:
        task = get_upgrade_task_by_id(task_id)
        if task:
            task.is_deleted = True
            success_ids.append(task_id)
        else:
            failed_ids.append(task_id)
    return success_ids, failed_ids

