from backend.institution import dao
from backend.common.exceptions import DuplicateResourceError, ResourceNotFoundError, InvalidUsageError
from backend.common.excel import create_excel_file, generate_filename
from backend.extensions import redis_client
import pandas as pd
import json
import uuid
from datetime import datetime
from flask import current_app
import re
class InstitutionService:
    """机构服务类，处理与机构相关的业务逻辑"""

    def create_institution(self, institution_data):
        """创建新机构。"""
        if dao.get_institution_by_code(institution_data['institution_code']):
            raise DuplicateResourceError(f"Institution code '{institution_data['institution_code']}' already exists.")
        return dao.add_institution(institution_data)

    def get_all_institutions(self):
        """获取所有机构的列表。"""
        return dao.get_all_institutions()
    
    def get_paged_institutions(self, page, per_page, filter_params=None, sort_by=None, sort_order=None):
        """
        获取分页的机构列表，支持筛选和排序，父机构信息通过模型关系自动获取
        :param page: 页码
        :param per_page: 每页数量  
        :param filter_params: 筛选条件字典
        :param sort_by: 排序字段
        :param sort_order: 排序方向 ('asc' 或 'desc')
        :return: SQLAlchemy Pagination 对象
        """
        pagination = dao.get_all_institutions_paged(page, per_page, filter_params, sort_by, sort_order)
        return pagination

    def get_institution_children(self, institution_id, page, per_page, sort_by='created_at', sort_order='desc'):
        """
        获取指定机构的所有子机构（分页），支持排序，父机构信息通过模型关系自动获取
        :param institution_id: 父机构ID
        :param page: 页码
        :param per_page: 每页数量
        :param sort_by: 排序字段
        :param sort_order: 排序方向 ('asc' 或 'desc')
        :return: SQLAlchemy Pagination 对象
        :raises ResourceNotFoundError: 如果父机构不存在
        """
        parent_institution = dao.get_institution_by_id(institution_id)
        if not parent_institution:
            raise ResourceNotFoundError(f"Parent institution ID '{institution_id}' does not exist.")
        pagination = dao.get_institution_children_paged(institution_id, page, per_page, sort_by, sort_order)
        return pagination

    def update_institution(self, institution_id, update_data):
        """更新机构信息。"""
        institution = dao.get_institution_by_id(institution_id)
        if not institution:
            raise ResourceNotFoundError(f"Institution ID '{institution_id}' does not exist.")
        
        if 'institution_code' in update_data:
            raise InvalidUsageError("Institution code modification is not allowed.")
        
        if institution_id== update_data.get('parent_id'):
            raise InvalidUsageError("Institution cannot be set as its own parent institution.")

        return dao.update_institution(institution, update_data)

    def delete_institution(self, institution_id):
        """逻辑删除一个机构。"""
        institution = dao.get_institution_by_id(institution_id)
        if not institution:
            raise ResourceNotFoundError(f"Institution ID '{institution_id}' does not exist.")
        
        dao.delete_institution(institution)

    def get_institution_tree(self):
        """
        获取机构树结构
        将扁平的机构列表转换为层级树形结构
        
        :return: 机构树列表（根节点列表，每个节点包含children字段）
        """
        # 1. 获取所有未删除的机构
        all_institutions = dao.get_all_institutions()
        
        # 2. 转换为字典格式，便于处理
        institution_dict = {}
        for inst in all_institutions:
            institution_data = {
                'id': inst.id,
                'institution_code': inst.institution_code,
                'institution_name': inst.institution_name,
                'parent_id': inst.parent_id,
                'level': inst.level,
                'address': inst.address,
                'contact_info': inst.contact_info,
                'status': inst.status,
                'created_at': inst.created_at,
                'updated_at': inst.updated_at,
                'children': []  # 初始化子节点列表
            }
            institution_dict[inst.id] = institution_data
        
        # 3. 构建树形结构
        root_nodes = []
        
        for inst_id, inst_data in institution_dict.items():
            parent_id = inst_data['parent_id']
            
            if parent_id is None or parent_id == '':
                # 根节点（没有父节点）
                root_nodes.append(inst_data)
            elif parent_id in institution_dict:
                # 有父节点，添加到父节点的children中
                institution_dict[parent_id]['children'].append(inst_data)
            else:
                # 父节点不存在或已被删除，视为根节点
                root_nodes.append(inst_data)
        
        # 4. 按层级和名称排序
        def sort_nodes(nodes):
            """递归排序节点"""
            # 按level升序，然后按institution_name排序
            nodes.sort(key=lambda x: (x.get('level', 0), x.get('institution_name', '')))
            for node in nodes:
                if node['children']:
                    sort_nodes(node['children'])
        
        sort_nodes(root_nodes)
        
        return root_nodes

    def export_institutions(self, filter_params=None, sort_by='level', sort_order='desc'):
        """
        导出机构数据为Excel文件，支持排序
        :param filter_params: 筛选条件字典
        :param sort_by: 排序字段
        :param sort_order: 排序方向 ('asc' 或 'desc')
        :return: Excel文件的字节流和文件名
        """
        institutions = dao.get_institutions_for_export(filter_params, sort_by, sort_order)
        
        # 2. 定义Excel表头配置
        headers = [
            {'key': 'institution_code', 'title': 'Institution Code', 'width': 15},
            {'key': 'institution_name', 'title': 'Institution Name', 'width': 25},
            {'key': 'parent_institution_code', 'title': 'Parent Institution Code', 'width': 20},
            {'key': 'parent_institution_name', 'title': 'Parent Institution Name', 'width': 25},
            {'key': 'level', 'title': 'Level', 'width': 10},
            {'key': 'status', 'title': 'Status', 'width': 10},
            {'key': 'contact_info', 'title': 'Contact Info', 'width': 20},
            {'key': 'address', 'title': 'Address', 'width': 30},
            {'key': 'created_at', 'title': 'Created Time', 'width': 18}
        ]
        # 处理导出数据，补充父机构信息
        export_data = []
        for inst in institutions:
            export_data.append({
                'institution_code': inst.institution_code,
                'institution_name': inst.institution_name,
                'parent_institution_code': inst.parent.institution_code if inst.parent else '',
                'parent_institution_name': inst.parent.institution_name if inst.parent else '',
                'parent_id': inst.parent_id,
                'level': inst.level,
                'address': inst.address,
                'contact_info': inst.contact_info,
                'status': inst.status,
                'created_at': inst.created_at
            })
        excel_buffer = create_excel_file(export_data, headers, "institution")
        filename = generate_filename("institution")
        return excel_buffer, filename

    # --- 批量导入相关方法 ---
    
    def preview_batch_import(self, excel_file):
        """
        批量导入机构 - 第一步：预览Excel文件
        解析Excel文件，验证数据，将结果缓存到Redis
        
        :param excel_file: 上传的Excel文件对象
        :return: 包含预览信息的字典
        """
        try:
            # 1. 读取Excel文件
            df = pd.read_excel(excel_file, dtype=str)  # 全部读取为字符串避免类型问题
            
            # 2. 检查必要的列是否存在
            required_columns = ['Institution Code (Required)', 'Institution Name (Required)', 'Parent Institution Code', 'Address', 'Contact Info', 'Status']
            missing_columns = [col for col in required_columns if col not in df.columns]
            if missing_columns:
                raise InvalidUsageError(f"Excel file is missing required columns: {', '.join(missing_columns)}")
            
            # 3. 去除空行
            df = df.dropna(subset=['Institution Code (Required)', 'Institution Name (Required)'], how='all')
            
            if df.empty:
                raise InvalidUsageError("No valid data rows in Excel file.")
                
            # 4. 提取所有数据并准备批量验证
            all_records = []
            for index, row in df.iterrows():
                record = {
                    'row_number': index + 2,  # Excel行号（考虑表头）
                    'institution_code': str(row['Institution Code (Required)']).strip() if pd.notna(row['Institution Code (Required)']) else '',
                    'institution_name': str(row['Institution Name (Required)']).strip() if pd.notna(row['Institution Name (Required)']) else '',
                    'parent_code': str(row['Parent Institution Code']).strip() if pd.notna(row['Parent Institution Code']) else None,
                    'address': str(row['Address']).strip() if pd.notna(row['Address']) else None,
                    'contact_info': str(row['Contact Info']).strip() if pd.notna(row['Contact Info']) else None,
                    'status': str(row['Status']).strip() if pd.notna(row['Status']) else 'active',
                    'errors': []  # 存储验证错误信息
                }
                all_records.append(record)
            
            # 5. 批量验证数据
            valid_records, invalid_records = self._validate_import_records_batch(all_records)
            
            # 6. 生成缓存键并存储到Redis
            cache_key = f"institution_batch_import:{uuid.uuid4()}"
            cache_data = {
                'valid_records': valid_records,
                'invalid_records': invalid_records,
                'created_at': datetime.now().isoformat()
            }
            
            # 检查Redis连接
            try:
                redis_client.ping()
            except Exception as e:
                raise InvalidUsageError("Redis service connection failed, please contact administrator")
            
            # 缓存2小时
            redis_client.setex(cache_key, 7200, json.dumps(cache_data, ensure_ascii=False))
            
            # 验证存储是否成功
            stored_data = redis_client.get(cache_key)
            if not stored_data:
                raise InvalidUsageError("Failed to store data to Redis")
            
            # 7. 准备返回数据
            result = {
                'total_records': len(all_records),
                'valid_count': len(valid_records),
                'invalid_count': len(invalid_records),
                'valid_records': valid_records[:100],  # 只返回前10条预览
                'import_token': cache_key
            }
            
            return result
            
        except pd.errors.EmptyDataError:
            raise InvalidUsageError("Excel file is empty or format is incorrect.")
        except Exception as e:
            if isinstance(e, InvalidUsageError):
                raise e
            raise InvalidUsageError(f"Failed to parse Excel file: {str(e)}")

    def _validate_import_records_batch(self, records):
        """
        批量验证导入记录
        :param records: 记录列表
        :return: (有效记录列表, 无效记录列表)
        """
        valid_records = []
        invalid_records = []
        

        if not records:
            return valid_records, invalid_records
        # 收集所有机构编码和父机构编码用于批量查询
        all_institution_codes = []
        all_parent_codes = []
        
        for record in records:
            if record['institution_code']:
                all_institution_codes.append(record['institution_code'])
            if record['parent_code']:
                all_parent_codes.append(record['parent_code'])
        
        # 批量查询已存在的机构编码
        existing_codes = dao.check_institutions_exist_batch(all_institution_codes)
        
        # 批量查询父机构
        parent_institutions = dao.get_institutions_by_codes(all_parent_codes)
        parent_code_to_id = {inst.institution_code: inst.id for inst in parent_institutions}
        parent_code_to_level = {inst.institution_code: inst.level for inst in parent_institutions}
        for record in records:
            errors = record['errors']
            
            # 1. 验证机构编码
            if not record['institution_code']:
                errors.append("Institution code cannot be empty")
            elif len(record['institution_code']) > 50:
                errors.append("Institution code cannot exceed 50 characters")
            elif not re.match("^[a-zA-Z0-9]+$", record['institution_code']):
                errors.append("Institution code can only contain letters and numbers")
            elif record['institution_code'] in existing_codes:
                errors.append(f"Institution code '{record['institution_code']}' already exists")
            
            # 2. 验证机构名称
            if not record['institution_name']:
                errors.append("Institution name cannot be empty")
            elif len(record['institution_name']) > 100:
                errors.append("Institution name cannot exceed 100 characters")
            
            # 3. 验证父机构编码
            if record['parent_code']:
                if record['parent_code'] not in parent_code_to_id:
                    errors.append("Parent institution does not exist")
                    # 不设置 parent_id/level，直接进入 invalid_records
                else:
                    record['parent_id'] = parent_code_to_id[record['parent_code']]
                    record['level'] = parent_code_to_level[record['parent_code']] + 1
            else:
                record['parent_id'] = None
                record['level'] = 1
            if record['address'] and len(record['address']) > 200:
                errors.append("Address cannot exceed 200 characters")
            
            # 6. 验证联系方式长度
            if record['contact_info'] and len(record['contact_info']) > 100:
                errors.append("Contact info cannot exceed 100 characters")
            
            # 7. 验证状态
            if record['status'] not in ['active', 'disabled']:
                errors.append("Status must be 'active' or 'disabled'")
            
            # 根据验证结果分类
            if errors:
                record['errors'] = errors
                invalid_records.append(record)
            else:
                valid_records.append(record)
        return valid_records, invalid_records

    def confirm_batch_import(self, cache_key):
        """
        批量导入机构 - 第二步：确认导入
        从Redis获取验证后的数据，执行实际的导入操作
        
        :param cache_key: 缓存键（导入令牌）
        :return: 导入结果字典
        """
        try:
            # 1. 检查Redis连接
            try:
                redis_client.ping()
            except Exception as e:
                raise InvalidUsageError("Redis service connection failed, please contact administrator")
            
            # 2. 从Redis获取缓存数据
            cache_data = redis_client.get(cache_key)
            if not cache_data:
                raise InvalidUsageError("Import data has expired or does not exist, please upload file again.")
            
            cache_data = json.loads(cache_data)
            valid_records = cache_data.get('valid_records', [])
            invalid_records = cache_data.get('invalid_records', [])
            
            # 3. 最终检查：验证机构编码是否仍然可用（防止并发插入）
            institution_codes = [record['institution_code'] for record in valid_records]
            existing_codes = dao.check_institutions_exist_batch(institution_codes)
            
            # 将新发现的重复记录移到无效记录中
            newly_invalid_records = []
            still_valid_records = []
            
            for record in valid_records:
                if record['institution_code'] in existing_codes:
                    record['errors'] = [f"The institution code '{record['institution_code']}' has already been inserted by another user"]
                    newly_invalid_records.append(record)
                else:
                    still_valid_records.append(record)
            
            # 4. 准备导入数据
            import_data = []
            for record in still_valid_records:
                import_data.append({
                    'institution_code': record['institution_code'],
                    'institution_name': record['institution_name'],
                    'parent_id': record['parent_id'],
                    'level': record['level'],
                    'address': record['address'],
                    'contact_info': record['contact_info'],
                    'status': record['status']
                })
            
            # 5. 执行批量导入
            successful_ids, failed_records = dao.add_institutions_batch(import_data)
            
            # 6. 处理导入结果
            final_invalid_records = invalid_records + newly_invalid_records
            
            # 添加批量导入失败的记录
            for failed_record in failed_records:
                final_invalid_records.append({
                    'row_number': 0,  # 未知行号
                    'institution_code': failed_record['institution_code'],
                    'institution_name': failed_record['institution_name'],
                    'errors': [failed_record['reason']]
                })
            
            # 7. 清理Redis缓存
            redis_client.delete(cache_key)
            
            # 8. 准备返回结果
            result = {
                'success_count': len(successful_ids),
                'imported_institutions': successful_ids,
                'has_failed_file': len(final_invalid_records) > 0
            }
            
            # 9. 如果有失败记录，生成Excel文件
            if final_invalid_records:
                excel_buffer, filename = self._create_failed_import_excel(final_invalid_records)
                result['excel_buffer'] = excel_buffer
                result['filename'] = filename
            
            return result
            
        except InvalidUsageError:
            raise
        except Exception as e:
            raise InvalidUsageError(f"Batch import failed: {str(e)}")

    def _create_failed_import_excel(self, invalid_records):
        """
        创建失败导入记录的Excel文件
        :param invalid_records: 失败的记录列表
        :return: Excel文件的字节流和文件名
        """
        # 定义表头
        headers = [
            {'key': 'row_number', 'title': 'Original Excel Row', 'width': 15},
            {'key': 'institution_code', 'title': 'Institution Code (Required)', 'width': 20},
            {'key': 'institution_name', 'title': 'Institution Name (Required)', 'width': 25},
            {'key': 'parent_code', 'title': 'Parent Institution Code', 'width': 20},
            {'key': 'address', 'title': 'Address', 'width': 30},
            {'key': 'contact_info', 'title': 'Contact Info', 'width': 20},
            {'key': 'status', 'title': 'Status', 'width': 10},
            {'key': 'error_messages', 'title': 'Error Messages', 'width': 50}
        ]
        
        # 处理数据，合并错误信息
        processed_records = []
        for record in invalid_records:
            processed_record = {
                'row_number': record.get('row_number', ''),
                'institution_code': record.get('institution_code', ''),
                'institution_name': record.get('institution_name', ''),
                'parent_code': record.get('parent_code', ''),
                'address': record.get('address', ''),
                'contact_info': record.get('contact_info', ''),
                'status': record.get('status', ''),
                'error_messages': '; '.join(record.get('errors', []))
            }
            processed_records.append(processed_record)
        
        # 生成Excel文件
        excel_buffer = create_excel_file(processed_records, headers, "institution_import_failed")
        filename = f"institution_import_failed_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        
        return excel_buffer, filename

    def create_import_template(self):
        """
        创建机构批量导入的Excel模板
        :return: Excel文件的字节流和文件名
        """
        # 定义表头（去除层级level字段）
        headers = [
            {'key': 'institution_code', 'title': 'Institution Code (Required)', 'width': 20},
            {'key': 'institution_name', 'title': 'Institution Name (Required)', 'width': 25},
            {'key': 'parent_code', 'title': 'Parent Institution Code', 'width': 20},
            {'key': 'address', 'title': 'Address', 'width': 30},
            {'key': 'contact_info', 'title': 'Contact Info', 'width': 20},
            {'key': 'status', 'title': 'Status', 'width': 10}
        ]
        
        # 创建空数据列表（只有表头）
        data = []
        
        # 生成Excel文件
        excel_buffer = create_excel_file(data, headers, "Institution Import Template")
        filename = "institution_import_template.xlsx"
        
        return excel_buffer, filename

# 创建一个服务实例，方便其他地方调用
institution_service = InstitutionService()
