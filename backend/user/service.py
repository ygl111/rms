# 导入我们刚刚创建的 user DAO 模块
from backend.user import dao
# 导入我们定义在 extensions.py 中的密码加密工具
from backend.extensions import bcrypt
# [新增] 导入自定义异常
from backend.common.exceptions import DuplicateResourceError, ResourceNotFoundError, InvalidUsageError
 # 导入Excel工具模块
from backend.common.excel import create_excel_file, generate_filename
from backend.common.exceptions import PermissionDeniedError
from dotenv import load_dotenv
import os
class UserService:
    """用户服务类，处理与用户相关的业务逻辑"""



    #注册用户
    def register_user(self, user_data):
        """
        处理用户注册的业务逻辑。
        :param user_data: 包含 'account' 和 'password' 的字典
        
        :return: 创建的 User 对象
        :raises DuplicateResourceError: 如果用户账号已存在
        """
        # 1. 检查用户名是否已存在（包括逻辑删除的记录，避免数据库约束冲突）
        if dao.get_user_by_account(user_data['account']):
            # [修改] 抛出明确的异常，而不是返回 None
            raise DuplicateResourceError(f"User account '{user_data['account']}' is already registered.")

        # 2. 对密码进行加密 (业务逻辑核心)
        password_hash = bcrypt.generate_password_hash(user_data['password']).decode('utf-8')

        # 3. 准备要存入数据库的数据
        new_user_data = {
            'account': user_data['account'],
            'password_hash': password_hash,
            'full_name': user_data.get('full_name'),
            'email': user_data.get('email'),
            'role_id': user_data.get('role_id'),
            'institution_id': user_data.get('institution_id'),
            'contact_info': user_data.get('contact_info'),
            'address': user_data.get('address'),
            'gender': user_data.get('gender')
        }

        # 4. 调用 DAO 将新用户信息存入数据库
        new_user = dao.add_user(new_user_data)
        
        return new_user


    #获取全部用户(分页、筛选、排序)
    def get_paged_users(self, page, per_page, filter_params=None, sort_by=None, sort_order='asc'):
        """
        获取分页的用户列表，支持筛选和排序。
        :param page: 页码
        :param per_page: 每页数量  
        :param filter_params: 筛选条件字典
        :param sort_by: 排序字段
        :param sort_order: 排序方向 ('asc' 或 'desc')
        :return: SQLAlchemy Pagination 对象
        """
        # 调用 DAO 层获取筛选、排序后的分页对象
        pagination = dao.get_all_users(page, per_page, filter_params, sort_by, sort_order)
        return pagination


    #更新用户
    def update_user(self, user_id, update_data):
        """
        更新用户信息。
        :param user_id: 要更新的用户的ID
        :param update_data: 包含要更新字段的字典
        :return: 更新后的 User 对象
        :raises ResourceNotFoundError: 如果用户ID不存在
        """
        # 1. 根据 ID 查找用户，如果找不到，DAO 会返回 None
        user_to_update = dao.get_user_by_id(user_id)
        if not user_to_update:
            raise ResourceNotFoundError(f"User with ID '{user_id}' does not exist.")
            
        # 1.5. 检查新的account是否与其他用户冲突（包括逻辑删除的记录）
        new_account = update_data.get('account')
        if new_account and new_account != user_to_update.account:
            existing_user = dao.get_user_by_account(new_account)
            if existing_user:
                raise DuplicateResourceError(f"User account '{new_account}' is already used by another user.")
            
        # 2. [业务逻辑] 处理密码更新
        # 如果请求数据中包含了 'password' 字段，说明需要更新密码
        if 'password' in update_data:
            # 取出新密码
            new_password = update_data.pop('password')  #用pop会删除password K-V对
            # 对新密码进行加密
            password_hash = bcrypt.generate_password_hash(new_password).decode('utf-8')
            # 将加密后的哈希值存入 update_data，准备更新到数据库
            update_data['password_hash'] = password_hash
            
        # 3. 调用 DAO 层执行更新
        updated_user = dao.update_user(user_to_update, update_data)
        
        return updated_user


    #删除用户（逻辑删除）
    def delete_user(self, user_id):
        # 不能删除超级管理员
        load_dotenv()
        super_admin_id = os.getenv('ADMIN')
        if user_id == super_admin_id:
            raise PermissionDeniedError("Cannot delete super administrator user")

        user_to_delete=dao.get_user_by_id(user_id)
        if not user_to_delete:
            raise ResourceNotFoundError(f"User with ID '{user_id}' does not exist.")
        
        dao.delete_user(user_to_delete)
    #批量删除用户（逻辑删除）
    def delete_users_batch(self, user_ids):
        """
        批量逻辑删除用户的业务逻辑处理。
        :param user_ids: 要删除的用户ID列表
        :return: 包含删除结果信息的字典
        :raises InvalidUsageError: 如果user_ids为空或格式不正确
        """
        # 1. 验证输入参数
        if not user_ids or not isinstance(user_ids, list):
            raise InvalidUsageError("User ID list cannot be empty and must be in list format.")

        # 2. 过滤超级管理员
        load_dotenv()
        super_admin_id = os.getenv('ADMIN')
        skipped_ids = []
        
        # 创建一个新的列表用于处理，避免修改原始参数
        ids_to_delete = list(user_ids)
        
        if super_admin_id and super_admin_id in ids_to_delete:
            ids_to_delete.remove(super_admin_id)
            skipped_ids.append(super_admin_id)

        # 3. 如果过滤后列表为空，直接返回结果
        if not ids_to_delete:
            return {
                'total_requested': len(user_ids),
                'successfully_deleted': [],
                'not_found': [],
                'skipped_ids': skipped_ids,
                'success_count': 0,
                'not_found_count': 0,
                'skipped_count': len(skipped_ids)
            }

        # 4. 调用DAO层执行批量删除
        successfully_deleted, not_found = dao.delete_users_batch(ids_to_delete)
        
        # 5. 构造返回结果
        result = {
            'total_requested': len(user_ids),
            'successfully_deleted': successfully_deleted,
            'not_found': not_found,
            'skipped_ids': skipped_ids,
            'success_count': len(successfully_deleted),
            'not_found_count': len(not_found),
            'skipped_count': len(skipped_ids)
        }
        
        return result


    #导出用户数据
    def export_users(self, filter_params=None):
        """
        导出用户数据为Excel文件
        :param filter_params: 筛选条件字典（与get_paged_users相同的参数）
        :return: Excel文件的字节流和文件名
        """

        
        # 1. 获取要导出的用户数据（不分页）
        users = dao.get_users_for_export(filter_params)
        
        # 2. 定义Excel表头配置
        headers = [
            {'key': 'account', 'title': 'Account', 'width': 20},
            {'key': 'full_name', 'title': 'Full Name', 'width': 12},
            {'key': 'email', 'title': 'Email', 'width': 25},
            {'key': 'gender', 'title': 'Gender', 'width': 10},
            {'key': 'role.role_name', 'title': 'Role', 'width': 25},
            {'key': 'institution.institution_code', 'title': 'Institution Code', 'width': 15},
            {'key': 'institution.institution_name', 'title': 'Institution Name', 'width': 20},
            {'key': 'contact_info', 'title': 'Contact Info', 'width': 15},
            {'key': 'address', 'title': 'Address', 'width': 25},
            {'key': 'created_at', 'title': 'Created Time', 'width': 18},
            {'key': 'status', 'title': 'Status', 'width': 10}
        ]
        
        # 3. 生成Excel文件
        excel_buffer = create_excel_file(users, headers, "Users Export")
        
        # 4. 生成文件名
        filename = generate_filename("Users Export")
        
        return excel_buffer, filename


    def get_user_information(self, user_id):

        return dao.get_user_by_id(user_id)

# 创建一个服务实例，方便其他地方调用
user_service = UserService()


