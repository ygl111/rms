from functools import wraps
from flask_jwt_extended import jwt_required, get_jwt , get_jwt_identity
from backend.common.exceptions import PermissionDeniedError
from backend.role.model import Permission
from backend.mapping.model import RolePermission
from backend.extensions import db
from backend.role.model import Role
from dotenv import load_dotenv
import os

def require_permissions(permission_codes, mode='any'):
    """权限检查装饰器。
    - permission_codes: str 或 List[str]
    - mode: 'any' 或 'all'，默认任一满足
    从 JWT 读取 role_id (claims['role'])，校验该角色是否拥有目标权限（未逻辑删除）。
    如果角色被禁用，视为拥有空权限列表，导致权限验证失败。
    """
    if isinstance(permission_codes, str):
        permission_codes = [permission_codes]

    def decorator(fn):
        @wraps(fn)
        @jwt_required()
        def wrapper(*args, **kwargs):
            #超级管理员判断
            admin_id=get_jwt_identity()
            load_dotenv()
            super_admin_id=os.getenv('ADMIN')
            if super_admin_id and admin_id == super_admin_id:
                return fn(*args, **kwargs)

            claims = get_jwt()
            role_id = claims.get('role')
            if not role_id:
                raise PermissionDeniedError("Role information not included, access denied")

            # 检查角色状态，如果角色被禁用或不存在，视为无任何权限

            role = db.session.query(Role).filter(
                Role.id == role_id,
                Role.is_deleted == False
            ).first()
            
            if not role or role.status != 'active':
                # 角色不存在或被禁用时，视为没有任何权限，直接返回权限不足
                raise PermissionDeniedError("Insufficient permissions")

            # 通过 code -> id，再验证 role_permission 未删除
            perm_ids = [pid for (pid,) in db.session.query(Permission.id).filter(
                Permission.permission_code.in_(permission_codes),
                Permission.is_deleted == False
            ).all()]

            if not perm_ids:
                raise PermissionDeniedError("Permission verification failed: target permission does not exist or has been deleted")

            # 统计该 role 拥有的目标权限数量
            owned_count = db.session.query(RolePermission).\
                filter(
                    RolePermission.role_id == role_id,
                    RolePermission.permission_id.in_(perm_ids),
                    RolePermission.is_deleted == False
                ).count()

            if mode == 'all' and owned_count < len(perm_ids):
                raise PermissionDeniedError("Insufficient permissions")
            if mode == 'any' and owned_count == 0:
                raise PermissionDeniedError("Insufficient permissions")

            return fn(*args, **kwargs)
        return wrapper
    return decorator


