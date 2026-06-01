from backend.mapping import dao
from backend.common.exceptions import DuplicateResourceError
class MappingService:
    """映射关系服务类"""

    def get_all_device_models(self):
        return dao.get_all_device_models()

    def add_device_model(self, model_data):
        # 检查重名（包括逻辑删除的记录，避免数据库约束冲突）
        if dao.get_device_model_by_name_all(model_data['model_name']):
            raise Exception(f"Model name '{model_data['model_name']}' already exists")
        return dao.add_device_model(model_data)

    def batch_delete_device_models(self, model_ids):
        success, not_found = dao.batch_delete_device_models(model_ids)
        return {
            'total_requested': len(model_ids),
            'successfully_deleted': success,
            'not_found': not_found,
            'success_count': len(success),
            'not_found_count': len(not_found)
        }

    def get_device_models_paged(self, page, per_page, filter_params=None):
        """
        获取分页的设备型号列表，支持筛选
        :param page: 页码
        :param per_page: 每页数量
        :param filter_params: 筛选条件字典
        :return: SQLAlchemy Pagination 对象
        """
        return dao.get_device_models_paged(page, per_page, filter_params)

    def update_device_model(self, model_id, update_data):
        """更新设备型号"""
        # 检查设备型号是否存在
        existing_model = dao.get_device_model_by_id(model_id)
        if not existing_model:
            return None
        
        # 如果要更新型号名称，检查新名称是否已存在（包括逻辑删除的记录，排除当前记录）
        if 'model_name' in update_data:
            existing_name_model = dao.get_device_model_by_name_all(update_data['model_name'])
            if existing_name_model and existing_name_model.id != model_id:
                raise DuplicateResourceError(f"Model name '{update_data['model_name']}' already exists")
        
        # 执行更新
        return dao.update_device_model(model_id, update_data)

# 创建服务实例
mapping_service = MappingService()