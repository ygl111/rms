# 从 extensions.py 中导入 db 实例
from backend.extensions import db
# 从 user.model 中导入我们定义的 User 模型
from backend.user.model import User
# 导入关联表模型（用于按关联表字段排序）
from backend.role.model import Role
from backend.institution.model import Institution
from sqlalchemy.orm import contains_eager
# 导入生成base64 UUID的模块
import uuid
import base64


#新增用户
def add_user(user_data):
    new_user = User(**user_data) #user_data中不能有多余的K-V对，否则会报错
    db.session.add(new_user)
    db.session.commit()
    return new_user


#通过用户id查询用户
def get_user_by_id(user_id):
    return User.query.filter_by(id=user_id, is_deleted=False).first()

#通过用户账号查询用户（包括已逻辑删除的）
def get_user_by_account(account):
    return User.query.filter_by(account=account).first()

def get_user_by_account_login(account):
    return User.query.filter_by(account=account,is_deleted=False).first()

def get_all_users(page, per_page, filter_params=None, sort_by='created_at', sort_order='desc'):
    """
    获取用户列表，支持筛选、排序和分页
    """
    query = db.session.query(User).\
        outerjoin(Role, User.role_id == Role.id).\
        outerjoin(Institution, User.institution_id == Institution.id).\
        options(contains_eager(User.role), contains_eager(User.institution)).\
        filter(User.is_deleted == False)

    # -------------------
    # 应用筛选条件
    # -------------------
    if filter_params:
        # 精确匹配
        if 'institution_id' in filter_params:
            query = query.filter(User.institution_id == filter_params['institution_id'])
        if 'role_id' in filter_params:
            query = query.filter(User.role_id == filter_params['role_id'])
        if 'status' in filter_params:
            query = query.filter(User.status == filter_params['status'])
        if 'gender' in filter_params:
            query = query.filter(User.gender == filter_params['gender'])
        if 'created_at_start' in filter_params:
            query = query.filter(User.created_at >= filter_params['created_at_start'])
        if 'created_at_end' in filter_params:
            query = query.filter(User.created_at <= filter_params['created_at_end'])

        # 模糊匹配
        if 'account' in filter_params:
            query = query.filter(User.account.like(f"{filter_params['account']}%"))
        if 'full_name' in filter_params:
            query = query.filter(User.full_name.like(f"%{filter_params['full_name']}%"))
        if 'email' in filter_params:
            query = query.filter(User.email.like(f"%{filter_params['email']}%"))
        if 'contact_info' in filter_params:
            query = query.filter(User.contact_info.like(f"{filter_params['contact_info']}%"))
        if 'address' in filter_params:
            query = query.filter(User.address.like(f"%{filter_params['address']}%"))

    # -------------------
    # 应用排序
    # -------------------
    sort_columns = {
        'account': User.account,
        'full_name': User.full_name,
        'email': User.email,
        'contact_info': User.contact_info,
        'address': User.address,
        'status': User.status,
        'role_name': Role.role_name,
        'institution_code': Institution.institution_code,
        'institution_name': Institution.institution_name,
        'created_at': User.created_at
    }

    sort_column = sort_columns.get(sort_by, User.created_at)  # 默认按创建时间排序
    query = query.order_by(sort_column.desc() if sort_order == 'desc' else sort_column.asc())

    # -------------------
    # 分页查询
    # -------------------
    return query.paginate(page=page, per_page=per_page, error_out=False)


def update_user(user, update_data):

    # 遍历包含新数据的字典
    for key, value in update_data.items():
        # setattr() 是 Python 的一个内置函数，它等价于 user.key = value
        # 例如，如果 key 是 'full_name', value 是 'New Name'
        # setattr(user, 'full_name', 'New Name') 就相当于 user.full_name = 'New Name'
        # 这样做的好处是我们可以动态地更新任意字段。
        if hasattr(user, key): # 检查 user 对象是否有这个属性，防止传入无效字段
            setattr(user, key, value)
    
    # 只需要提交会话即可，SQLAlchemy 会自动检测到 user 对象发生了变化
    db.session.commit()
    return user

def delete_user(user):
    """
    逻辑删除一个用户。
    :param user: 要删除的 User 对象
    """
    user.is_deleted = True
    db.session.commit()

def delete_users_batch(user_ids):
    """
    批量逻辑删除多个用户。
    :param user_ids: 要删除的用户ID列表
    :return: 成功删除的用户ID列表和未找到的用户ID列表
    """
    # 查找所有存在的用户（排除已经被逻辑删除的用户）
    existing_users = User.query.filter(
        User.id.in_(user_ids),
        User.is_deleted == False
    ).all()
    
    # 获取找到的用户ID列表
    found_user_ids = [user.id for user in existing_users]
    
    # 计算未找到的用户ID列表
    not_found_user_ids = [user_id for user_id in user_ids if user_id not in found_user_ids]
    
    # 批量更新找到的用户：设置 is_deleted 为 True 并修改 account 字段
    if existing_users:
        for user in existing_users:
            user.is_deleted = True
            
            
        db.session.commit()
    
    # 返回成功删除的ID列表和未找到的ID列表
    return found_user_ids, not_found_user_ids

def get_users_for_export(filter_params=None,sort_by='created_at', sort_order='desc'):
    """
    获取用于导出的用户数据（不分页，返回所有符合条件的记录）
    :param filter_params: 筛选条件字典
    :return: 用户列表
    """


    query = db.session.query(User).\
        outerjoin(Role, User.role_id == Role.id).\
        outerjoin(Institution, User.institution_id == Institution.id).\
        options(contains_eager(User.role), contains_eager(User.institution)).\
        filter(User.is_deleted == False)

    # -------------------
    # 应用筛选条件
    # -------------------
    if filter_params:
        # 精确匹配
        if 'institution_id' in filter_params:
            query = query.filter(User.institution_id == filter_params['institution_id'])
        if 'role_id' in filter_params:
            query = query.filter(User.role_id == filter_params['role_id'])
        if 'status' in filter_params:
            query = query.filter(User.status == filter_params['status'])
        if 'gender' in filter_params:
            query = query.filter(User.gender == filter_params['gender'])
        if 'created_at_start' in filter_params:
            query = query.filter(User.created_at >= filter_params['created_at_start'])
        if 'created_at_end' in filter_params:
            query = query.filter(User.created_at <= filter_params['created_at_end'])

        # 模糊匹配
        if 'account' in filter_params:
            query = query.filter(User.account.like(f"{filter_params['account']}%"))
        if 'full_name' in filter_params:
            query = query.filter(User.full_name.like(f"%{filter_params['full_name']}%"))
        if 'email' in filter_params:
            query = query.filter(User.email.like(f"%{filter_params['email']}%"))
        if 'contact_info' in filter_params:
            query = query.filter(User.contact_info.like(f"{filter_params['contact_info']}%"))
        if 'address' in filter_params:
            query = query.filter(User.address.like(f"%{filter_params['address']}%"))

    # -------------------
    # 应用排序
    # -------------------
    sort_columns = {
        'account': User.account,
        'full_name': User.full_name,
        'email': User.email,
        'contact_info': User.contact_info,
        'address': User.address,
        'status': User.status,
        'role_name': Role.role_name,
        'institution_code': Institution.institution_code,
        'institution_name': Institution.institution_name,
        'created_at': User.created_at
    }

    sort_column = sort_columns.get(sort_by, User.created_at)  # 默认按创建时间排序
    query = query.order_by(sort_column.desc() if sort_order == 'desc' else sort_column.asc())
    return query.all()
