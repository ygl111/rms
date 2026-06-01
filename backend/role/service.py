from backend.role import dao
from backend.common.exceptions import DuplicateResourceError, ResourceNotFoundError, InvalidUsageError
# 导入Excel工具模块
from backend.common.excel import create_excel_file, generate_filename

class RoleService:
    """角色服务类，处理与角色相关的业务逻辑"""

    def create_role(self, role_data):
        """
        创建新角色。
        :param role_data: 包含角色信息的字典
        :return: 创建的 Role 对象
        :raises DuplicateResourceError: 如果角色编码已存在
        """
        # 1. 检查角色编码是否已存在
        if dao.get_role_by_code(role_data['role_code']):
            raise DuplicateResourceError(f"Role code '{role_data['role_code']}' already exists.")
            
        # 2. 调用 DAO 创建新角色
        new_role = dao.add_role(role_data)
        return new_role

    def get_paged_roles(self, page, per_page, filter_params=None, sort_by=None, sort_order='asc'):
        """
        获取分页的角色列表，支持筛选和排序。
        :param page: 页码
        :param per_page: 每页数量  
        :param filter_params: 筛选条件字典
        :param sort_by: 排序字段
        :param sort_order: 排序方向 ('asc' 或 'desc')
        :return: SQLAlchemy Pagination 对象
        """
        # 调用 DAO 层获取筛选、排序后的分页对象
        pagination = dao.get_all_roles(page, per_page, filter_params, sort_by, sort_order)
        return pagination

    def update_role(self, role_id, update_data):
        """
        更新角色信息。
        :param role_id: 要更新的角色的ID
        :param update_data: 包含要更新字段的字典
        :return: 更新后的 Role 对象
        """
        role = dao.get_role_by_id(role_id)
        if not role:
            raise ResourceNotFoundError(f"Role ID '{role_id}' does not exist.")
        
        # [修改] 明确禁止通过更新接口修改 role_code
        if 'role_code' in update_data:
            raise InvalidUsageError("Role code modification is not allowed.")
                
        return dao.update_role(role, update_data)

    def delete_role(self, role_id):
        """
        逻辑删除一个角色。
        :param role_id: 要删除的角色的ID
        """
        role = dao.get_role_by_id(role_id)
        if not role:
            raise ResourceNotFoundError(f"Role ID '{role_id}' does not exist.")
        
        return dao.delete_role(role)

    def delete_roles_batch(self, role_ids):
        """
        批量逻辑删除角色的业务逻辑处理。
        :param role_ids: 要删除的角色ID列表
        :return: 包含删除结果信息的字典
        :raises InvalidUsageError: 如果role_ids为空或格式不正确
        """
        # 1. 验证输入参数
        if not role_ids or not isinstance(role_ids, list):
            raise InvalidUsageError("Role ID list cannot be empty and must be in list format.")
        
        if len(role_ids) == 0:
            raise InvalidUsageError("Role ID list cannot be empty.")
        
        # 2. 调用DAO层执行批量删除
        successfully_deleted, not_found = dao.delete_roles_batch(role_ids)
        
        # 3. 构造返回结果
        result = {
            'total_requested': len(role_ids),           # 请求删除的总数
            'successfully_deleted': successfully_deleted,  # 成功删除的角色ID列表
            'not_found': not_found,                     # 未找到的角色ID列表
            'success_count': len(successfully_deleted),  # 成功删除的数量
            'not_found_count': len(not_found)           # 未找到的数量
        }
        
        return result

    def export_roles(self, filter_params=None):
        """
        导出角色数据为Excel文件
        :param filter_params: 筛选条件字典（与get_paged_roles相同的参数）
        :return: Excel文件的字节流和文件名
        """
        # 1. 获取要导出的角色数据（不分页）
        roles = dao.get_roles_for_export(filter_params)
        
        # 2. 定义Excel表头配置
        headers = [
            {'key': 'role_code', 'title': 'Role Code', 'width': 20},
            {'key': 'role_name', 'title': 'Role Name', 'width': 25},
            {'key': 'status', 'title': 'Status', 'width': 10},
            {'key': 'description', 'title': 'Description', 'width': 30},
            {'key': 'created_at', 'title': 'Created Time', 'width': 18},
        ]
        
        # 3. 生成Excel文件
        excel_buffer = create_excel_file(roles, headers, "RolesExport")
        
        # 4. 生成文件名
        filename = generate_filename("RoleExport")
        
        return excel_buffer, filename



    # 权限服务：获取所有未被删除的权限
    def list_all_permissions(self):
        return dao.get_all_permissions()

    def list_permissions_of_role(self, role_id: str):
        role = dao.get_role_by_id(role_id)
        if not role:
            return []
        
        # [新增] 如果角色被禁用，返回空权限列表
        if role.status != 'active':
            return []
       
        return dao.get_permissions_of_role(role)

    def delete_role_permissions_batch(self, role_id: str, permission_ids):
        if not permission_ids or not isinstance(permission_ids, list):
            raise InvalidUsageError("permission_ids cannot be empty and must be a string list")
        role = dao.get_role_by_id(role_id)
        if not role:
            raise ResourceNotFoundError(f"Role ID '{role_id}' does not exist.")
        success_ids, not_found_ids = dao.delete_role_permissions_batch(role_id, permission_ids)
        return {
            'total_requested': len(permission_ids),
            'successfully_deleted': success_ids,
            'not_found': not_found_ids,
            'success_count': len(success_ids),
            'not_found_count': len(not_found_ids)
        }

    def add_or_restore_role_permissions_batch(self, role_id: str, permission_ids):
        if not permission_ids or not isinstance(permission_ids, list):
            raise InvalidUsageError("permission_ids cannot be empty and must be a string list")
        role = dao.get_role_by_id(role_id)
        if not role:
            raise ResourceNotFoundError(f"Role ID '{role_id}' does not exist.")
        created_ids, restored_ids, not_found_ids = dao.add_or_restore_role_permissions_batch(role_id, permission_ids)
        return {
            'total_requested': len(permission_ids),
            'created': created_ids,
            'restored': restored_ids,
            'not_found': not_found_ids,
            'success_count': len(created_ids) + len(restored_ids),
            'not_found_count': len(not_found_ids)
        }

# 创建一个服务实例，方便其他地方调用
role_service = RoleService() 