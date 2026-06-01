from backend.extensions import db
from backend.email.model import UpgradeNotifyEmail, FaultNotifyEmail
from backend.user.model import User
from sqlalchemy.orm import contains_eager


# ========== UpgradeNotifyEmail DAO ==========

def add_upgrade_notify_email(email_data):
    """添加升级通知邮箱"""
    new_email = UpgradeNotifyEmail(**email_data)
    db.session.add(new_email)
    db.session.commit()
    return new_email


def get_upgrade_notify_email_by_id(email_id):
    """通过ID查询升级通知邮箱"""
    return UpgradeNotifyEmail.query.filter_by(id=email_id).first()


def get_upgrade_notify_email_by_email(email):
    """通过邮箱地址查询升级通知邮箱"""
    return UpgradeNotifyEmail.query.filter_by(email=email).first()


def get_all_upgrade_notify_emails(page=1, per_page=10, filter_params=None, sort_by='created_at', sort_order='desc'):
    """
    获取升级通知邮箱列表，支持筛选、排序和分页
    """
    query = db.session.query(UpgradeNotifyEmail).\
        outerjoin(User, UpgradeNotifyEmail.user_id == User.id).\
        options(contains_eager(UpgradeNotifyEmail.user))

    # 应用筛选条件
    if filter_params:
        if 'email' in filter_params and filter_params['email']:
            query = query.filter(UpgradeNotifyEmail.email.like(f"%{filter_params['email']}%"))
        if 'full_name' in filter_params and filter_params['full_name']:
            query = query.filter(User.full_name.like(f"%{filter_params['full_name']}%"))

    # 应用排序
    sort_columns = {
        'email': UpgradeNotifyEmail.email,
        'created_at': UpgradeNotifyEmail.created_at,
        'updated_at': UpgradeNotifyEmail.updated_at,
        'full_name': User.full_name,
    }
    
    if sort_by and sort_by in sort_columns:
        order_column = sort_columns[sort_by]
        if sort_order == 'asc':
            query = query.order_by(order_column.asc())
        else:
            query = query.order_by(order_column.desc())
    else:
        query = query.order_by(UpgradeNotifyEmail.created_at.desc())

    # 分页
    paginated_data = query.paginate(page=page, per_page=per_page, error_out=False)
    return paginated_data


def update_upgrade_notify_email(email_id, update_data):
    """更新升级通知邮箱"""
    email_record = UpgradeNotifyEmail.query.filter_by(id=email_id).first()
    if email_record:
        for key, value in update_data.items():
            if hasattr(email_record, key):
                setattr(email_record, key, value)
        db.session.commit()
    return email_record


def delete_upgrade_notify_email(email_id):
    """删除升级通知邮箱（物理删除）"""
    email_record = UpgradeNotifyEmail.query.filter_by(id=email_id).first()
    if email_record:
        db.session.delete(email_record)
        db.session.commit()
        return True
    return False


# ========== FaultNotifyEmail DAO ==========

def add_fault_notify_email(email_data):
    """添加故障通知邮箱"""
    new_email = FaultNotifyEmail(**email_data)
    db.session.add(new_email)
    db.session.commit()
    return new_email


def get_fault_notify_email_by_id(email_id):
    """通过ID查询故障通知邮箱"""
    return FaultNotifyEmail.query.filter_by(id=email_id).first()


def get_fault_notify_email_by_email(email):
    """通过邮箱地址查询故障通知邮箱"""
    return FaultNotifyEmail.query.filter_by(email=email).first()


def get_all_fault_notify_emails(page=1, per_page=10, filter_params=None, sort_by='created_at', sort_order='desc'):
    """
    获取故障通知邮箱列表，支持筛选、排序和分页
    """
    query = db.session.query(FaultNotifyEmail).\
        outerjoin(User, FaultNotifyEmail.user_id == User.id).\
        options(contains_eager(FaultNotifyEmail.user))

    # 应用筛选条件
    if filter_params:
        if 'email' in filter_params and filter_params['email']:
            query = query.filter(FaultNotifyEmail.email.like(f"%{filter_params['email']}%"))
        if 'full_name' in filter_params and filter_params['full_name']:
            query = query.filter(User.full_name.like(f"%{filter_params['full_name']}%"))

    # 应用排序
    sort_columns = {
        'email': FaultNotifyEmail.email,
        'created_at': FaultNotifyEmail.created_at,
        'updated_at': FaultNotifyEmail.updated_at,
        'full_name': User.full_name,
    }
    
    if sort_by and sort_by in sort_columns:
        order_column = sort_columns[sort_by]
        if sort_order == 'asc':
            query = query.order_by(order_column.asc())
        else:
            query = query.order_by(order_column.desc())
    else:
        query = query.order_by(FaultNotifyEmail.created_at.desc())

    # 分页
    paginated_data = query.paginate(page=page, per_page=per_page, error_out=False)
    return paginated_data


def update_fault_notify_email(email_id, update_data):
    """更新故障通知邮箱"""
    email_record = FaultNotifyEmail.query.filter_by(id=email_id).first()
    if email_record:
        for key, value in update_data.items():
            if hasattr(email_record, key):
                setattr(email_record, key, value)
        db.session.commit()
    return email_record


def delete_fault_notify_email(email_id):
    """删除故障通知邮箱（物理删除）"""
    email_record = FaultNotifyEmail.query.filter_by(id=email_id).first()
    if email_record:
        db.session.delete(email_record)
        db.session.commit()
        return True
    return False


# ========== 通用邮箱获取方法 ==========

def get_all_upgrade_notify_email_addresses():
    """获取所有升级通知邮箱地址列表"""
    emails = db.session.query(UpgradeNotifyEmail.email).all()
    return [email[0] for email in emails]


def get_all_fault_notify_email_addresses():
    """获取所有故障通知邮箱地址列表"""
    emails = db.session.query(FaultNotifyEmail.email).all()
    return [email[0] for email in emails]

