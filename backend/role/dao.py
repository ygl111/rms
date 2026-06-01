from backend.extensions import db
from backend.role.model import Role, Permission
from backend.mapping.model import RolePermission
from backend.common.exceptions import ResourceNotFoundError
def add_role(role_data):
    """
    向数据库中添加一个新角色。
    :param role_data: 包含角色信息的字典 (role_code, role_name, description)
    :return: 创建的 Role 对象
    """
    new_role = Role(**role_data)
    db.session.add(new_role)
    db.session.commit()
    return new_role

def get_role_by_id(role_id):
    """
    根据角色ID查询角色。
    :param role_id: 角色的ID
    :return: Role 对象或 None（排除已被逻辑删除的角色）
    """
    return Role.query.filter_by(id=role_id, is_deleted=False).first()

def get_role_by_code(role_code):
    """
    根据角色编码查询角色。
    :param role_code: 角色编码
    :return: Role 对象或 None
    """
    return Role.query.filter_by(role_code=role_code, is_deleted=False).first()

def get_all_roles(page, per_page, filter_params=None, sort_by=None, sort_order='asc'):
    """
    获取角色列表，支持筛选、排序和分页
    :param page: 页码
    :param per_page: 每页数量
    :param filter_params: 筛选条件字典
    :param sort_by: 排序字段
    :param sort_order: 排序方向
    :return: SQLAlchemy Pagination 对象
    """
    # 构建基础查询，筛选未被逻辑删除的角色
    query = Role.query.filter(Role.is_deleted == False)
    
    # 应用筛选条件
    if filter_params:
        for key, value in filter_params.items():
            if key == 'status':
                # 精确匹配状态
                query = query.filter(Role.status == value)
            elif key == 'role_code':
                # 角色编码开头匹配
                query = query.filter(Role.role_code.like(f"{value}%"))
            elif key == 'role_name':
                # 角色名称包含匹配
                query = query.filter(Role.role_name.like(f"%{value}%"))
    
    # 应用排序
    if sort_by:
        if sort_by == 'role_code':
            sort_column = Role.role_code
        elif sort_by == 'role_name':
            sort_column = Role.role_name
        elif sort_by == 'status':
            sort_column = Role.status
        else:
            sort_column = Role.created_at  # 默认按创建时间排序
            
        # 根据排序方向应用排序
        if sort_order == 'desc':
            query = query.order_by(sort_column.desc())
        else:
            query = query.order_by(sort_column.asc())
    else:
        # 如果没有指定排序，默认按创建时间倒序排序（新创建的在前面）
        query = query.order_by(Role.created_at.desc())
    
    # 执行分页查询
    return query.paginate(page=page, per_page=per_page, error_out=False)

def update_role(role, update_data):
    """
    更新一个已存在的角色。
    :param role: 要更新的 Role 对象
    :param update_data: 包含要更新字段的字典
    :return: 更新后的 Role 对象
    """
    for key, value in update_data.items():
        if hasattr(role, key):
            setattr(role, key, value)
    db.session.commit()
    return role

def delete_role(role):
    """
    逻辑删除一个角色。
    :param role: 要删除的 Role 对象
    """
    role.is_deleted = True
    db.session.commit()

def delete_roles_batch(role_ids):
    """
    批量逻辑删除多个角色。
    :param role_ids: 要删除的角色ID列表
    :return: 成功删除的角色ID列表和未找到的角色ID列表
    """
    # 查找所有存在的角色（排除已经被逻辑删除的角色）
    existing_roles = Role.query.filter(
        Role.id.in_(role_ids),
        Role.is_deleted == False
    ).all()
    
    # 获取找到的角色ID列表
    found_role_ids = [role.id for role in existing_roles]
    
    # 计算未找到的角色ID列表
    not_found_role_ids = [role_id for role_id in role_ids if role_id not in found_role_ids]
    
    # 批量更新找到的角色的 is_deleted 字段为 True
    if existing_roles:
        for role in existing_roles:
            role.is_deleted = True
        db.session.commit()
    
    # 返回成功删除的ID列表和未找到的ID列表
    return found_role_ids, not_found_role_ids

def get_roles_for_export(filter_params=None):
    """
    获取用于导出的角色数据（不分页，返回所有符合条件的记录）
    :param filter_params: 筛选条件字典
    :return: 角色列表
    """
    # 构建基础查询，筛选未被逻辑删除的角色
    query = Role.query.filter(Role.is_deleted == False)
    
    # 应用筛选条件（复用原有的筛选逻辑）
    if filter_params:
        for key, value in filter_params.items():
            if key == 'status':
                query = query.filter(Role.status == value)
            elif key == 'role_code':
                query = query.filter(Role.role_code.like(f"{value}%"))
            elif key == 'role_name':
                query = query.filter(Role.role_name.like(f"%{value}%"))
    
    # 按创建时间排序
    query = query.order_by(Role.created_at.desc())
    
    # 返回所有匹配的角色（不分页）
    return query.all()

# 权限：获取所有未被逻辑删除的权限
def get_all_permissions():
    return Permission.query.filter_by(is_deleted=False).all()

def get_permissions_of_role(role):
    """使用 Role.permissions 关系获取指定角色的有效权限（过滤逻辑删除）"""

    # 通过关系对象进行过滤
    return role.permissions.filter(
        Permission.is_deleted == False,
        RolePermission.is_deleted == False
    ).all()

def delete_role_permissions_batch(role_id: str, permission_ids):
    """批量逻辑删除角色-权限映射，返回(成功ID列表, 未找到ID列表)"""
    if not permission_ids:
        return [], permission_ids
    # 仅删除当前为未删除状态的映射
    mappings = RolePermission.query.filter(
        RolePermission.role_id == role_id,
        RolePermission.permission_id.in_(permission_ids),
        RolePermission.is_deleted == False
    ).all()

    found_ids = [m.permission_id for m in mappings]
    not_found_ids = [pid for pid in permission_ids if pid not in found_ids]

    if mappings:
        for m in mappings:
            m.is_deleted = True
        db.session.commit()
    return found_ids, not_found_ids

def add_or_restore_role_permissions_batch(role_id: str, permission_ids):
    """批量新增或恢复角色-权限映射。
    返回 (created_ids, restored_ids, not_found_ids)
    仅对存在于 permissions 表且未被逻辑删除的权限进行处理。
    """
    if not permission_ids:
        return [], [], permission_ids

    # 过滤出有效权限
    valid_permissions = Permission.query.filter(
        Permission.id.in_(permission_ids),
        Permission.is_deleted == False
    ).all()
    valid_ids = {p.id for p in valid_permissions}
    not_found_ids = [pid for pid in permission_ids if pid not in valid_ids]

    # 查询已有映射（包含已删除的）
    existing_mappings = RolePermission.query.filter(
        RolePermission.role_id == role_id,
        RolePermission.permission_id.in_(list(valid_ids))
    ).all()
    existing_by_pid = {m.permission_id: m for m in existing_mappings}

    created_ids = []
    restored_ids = []

    # 对有效ID进行处理：不存在则创建；存在且逻辑删除则恢复
    for pid in valid_ids:
        mapping = existing_by_pid.get(pid)
        if mapping is None:
            new_map = RolePermission(role_id=role_id, permission_id=pid, is_deleted=False)
            db.session.add(new_map)
            created_ids.append(pid)
        elif mapping.is_deleted:
            mapping.is_deleted = False
            db.session.add(mapping)
            restored_ids.append(pid)

    db.session.commit()
    return created_ids, restored_ids, not_found_ids
