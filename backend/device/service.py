from backend.device import dao
from backend.common.exceptions import ResourceNotFoundError, InvalidUsageError, DuplicateResourceError
# [新增] 导入其他模块的 DAO
from backend.institution import dao as institution_dao
from backend.mapping import dao as mapping_dao
# 导入Excel工具模块
from backend.common.excel import create_excel_file, generate_filename
# [新增] 导入Redis客户端和Excel读取库
from backend.extensions import redis_client
import pandas as pd
import json
import uuid
from datetime import datetime
from flask import current_app

class DeviceService:
    """设备服务类"""

    # --- Device Methods ---
    def create_device(self, device_data):
        """创建新设备，并校验外键有效性"""
        # 1. 检查 device_id 是否已存在（包括逻辑删除的记录，避免数据库约束冲突）
        device_id = device_data.get('device_id')
        if dao.get_device_by_device_id(device_id):
            raise DuplicateResourceError(f"Device ID '{device_id}' already exists.")

        # 2. 检查 institution_id 是否有效
        institution_id = device_data.get('institution_id')
        if not institution_dao.get_institution_by_id(institution_id):
            raise InvalidUsageError(f"Institution ID '{institution_id}' is invalid.")

        # 3. 检查 model_id 是否有效
        model_id = device_data.get('model_id')
        if not mapping_dao.get_device_model_by_id(model_id):
            raise InvalidUsageError(f"Device model ID '{model_id}' is invalid.")
            
        # 4. 所有检查通过，执行创建（id 会自动生成 UUID）

        return dao.add_device(device_data)

        


    def get_paged_devices(self, page, per_page, filter_params=None, sort_by='last_online_time', sort_order='desc'):
        """
        获取分页的设备列表，支持筛选和排序。
        :param page: 页码
        :param per_page: 每页数量  
        :param filter_params: 筛选条件字典
        :param sort_by: 排序字段
        :param sort_order: 排序方向 ('asc' 或 'desc')
        :return: SQLAlchemy Pagination 对象
        """
        # 调用 DAO 层获取筛选、排序后的分页对象
        pagination = dao.get_all_devices(page, per_page, filter_params, sort_by, sort_order)
        return pagination

    def update_device(self, device_id, update_data):
        device = dao.get_device_by_id(device_id)
        if not device:
            raise ResourceNotFoundError(f"Device ID '{device_id}' does not exist.")

        # 检查新的 device_id 是否与现有设备冲突（包括逻辑删除的记录）
        new_device_id = update_data.get('device_id')
        if new_device_id and new_device_id != device.device_id:
            existing_device = dao.get_device_by_device_id(new_device_id)
            if existing_device:
                raise DuplicateResourceError(f"Device ID '{new_device_id}' is already used by another device.")

        # 检查新的 model_id 是否有效
        new_model_id = update_data.get('model_id')
        if new_model_id:
            if not mapping_dao.get_device_model_by_id(new_model_id):
                raise InvalidUsageError(f"Device model ID '{new_model_id}' is invalid.")
        
        return dao.update_device(device, update_data)

    def delete_device(self, device_id):
        device = dao.get_device_by_id(device_id)
        if not device:
            raise ResourceNotFoundError(f"Device ID '{device_id}' does not exist.")
        dao.delete_device(device)

    def delete_devices_batch(self, device_ids):
        """
        批量逻辑删除设备的业务逻辑处理。
        :param device_ids: 要删除的设备ID列表
        :return: 包含删除结果信息的字典
        :raises InvalidUsageError: 如果device_ids为空或格式不正确
        """
        # 1. 验证输入参数
        if not device_ids or not isinstance(device_ids, list):
            raise InvalidUsageError("Device ID list cannot be empty and must be in list format.")
        
        if len(device_ids) == 0:
            raise InvalidUsageError("Device ID list cannot be empty.")
        
        # 2. 调用DAO层执行批量删除
        successfully_deleted, not_found = dao.delete_devices_batch(device_ids)
        
        # 3. 构造返回结果
        result = {
            'total_requested': len(device_ids),           # 请求删除的总数
            'successfully_deleted': successfully_deleted,  # 成功删除的设备ID列表
            'not_found': not_found,                     # 未找到的设备ID列表
            'success_count': len(successfully_deleted),  # 成功删除的数量
            'not_found_count': len(not_found)           # 未找到的数量
        }
        
        return result

    def export_devices(self, filter_params=None, sort_by='last_online_time', sort_order='desc'):
        """
        导出设备数据为Excel文件，支持筛选和排序
        """
        devices = dao.get_all_devices(None, None, filter_params, sort_by, sort_order, export=True)
        export_data = []
        for dev in devices:
            export_data.append({
                'device_id': dev.device_id,
                'device_type': dev.device_type,
                'online_status': dev.online_status,
                'last_online_time': dev.last_online_time,
                'institution_code': dev.institution.institution_code if dev.institution else '',
                'institution_name': dev.institution.institution_name if dev.institution else '',
                'model_id': dev.model_id,
                'model_name': dev.model.model_name if dev.model else '',
                'firmware_version': dev.firmware_version,
                'ip_endpoint': dev.ip_endpoint,
                'created_at': dev.created_at,
                'updated_at': dev.updated_at,
                'hardware_version': dev.hardware_version,
                'main_software_version': dev.main_software_version,
                'description': dev.description,
                'maintenance_threshold': dev.maintenance_threshold,
                'latitude': dev.latitude,
                'longitude': dev.longitude,
                'address': dev.address
            })
        headers = [
            {'key': 'device_id', 'title': 'Device ID', 'width': 15},
            {'key': 'model_name', 'title': 'Device Model', 'width': 20},
            {'key': 'institution_code', 'title': 'Institution Code', 'width': 20},
            {'key': 'institution_name', 'title': 'Institution Name', 'width': 25},
            {'key': 'firmware_version', 'title': 'Firmware Version', 'width': 40},
            {'key': 'ip_endpoint', 'title': 'Device IP Address', 'width': 18},
            {'key': 'online_status', 'title': 'Online Status', 'width': 20},
            {'key': 'last_online_time', 'title': 'Last Online Time', 'width': 30},
            {'key': 'created_at', 'title': 'Created Time', 'width': 30},
            {'key': 'description', 'title': 'Description', 'width': 30},
            {'key': 'maintenance_threshold', 'title': 'Maintenance Threshold', 'width': 20},
            {'key': 'latitude', 'title': 'Latitude', 'width': 15},
            {'key': 'longitude', 'title': 'Longitude', 'width': 15},
            {'key': 'address', 'title': 'Address', 'width': 40}
        ]
        excel_buffer = create_excel_file(export_data, headers, "device")
        filename = generate_filename("device")
        return excel_buffer, filename

    # --- 批量导入相关方法 ---
    
    def preview_batch_import(self, excel_file):
        """
        批量导入设备 - 第一步：预览Excel文件
        解析Excel文件，验证数据，将结果缓存到Redis
        
        :param excel_file: 上传的Excel文件对象
        :return: 包含预览信息的字典
        """
        try:
            # 1. 读取Excel文件
            # 使用pandas读取Excel，指定列名
            df = pd.read_excel(excel_file, dtype=str)  # 全部读取为字符串避免类型问题
            
            # 2. 检查必要的列是否存在
            required_columns = ['Device ID', 'Device Model', 'Institution Code', 'Description', 'Maintenance Threshold', 'Latitude', 'Longitude', 'Address']
            missing_columns = [col for col in required_columns if col not in df.columns]
            if missing_columns:
                raise InvalidUsageError(f"Excel file is missing required columns: {', '.join(missing_columns)}")
            
            # 3. 去除空行
            df = df.dropna(subset=['Device ID', 'Device Model', 'Institution Code'], how='all')
            
            if df.empty:
                raise InvalidUsageError("No valid data rows in Excel file.")
                
            # 4. 提取所有数据并准备批量验证
            all_records = []
            for index, row in df.iterrows():
                # 解析维护阈值，确保是非负整数
                maintenance_threshold = 0
                if pd.notna(row['Maintenance Threshold']):
                    try:
                        maintenance_threshold = int(float(str(row['Maintenance Threshold']).strip()))
                        if maintenance_threshold < 0:
                            maintenance_threshold = 0
                    except (ValueError, TypeError):
                        maintenance_threshold = 0
                
                # 解析经度
                latitude = None
                if pd.notna(row['Latitude']):
                    try:
                        lat = float(str(row['Latitude']).strip())
                        if -90 <= lat <= 90:
                            latitude = lat
                    except (ValueError, TypeError):
                        pass
                
                # 解析纬度
                longitude = None
                if pd.notna(row['Longitude']):
                    try:
                        lon = float(str(row['Longitude']).strip())
                        if -180 <= lon <= 180:
                            longitude = lon
                    except (ValueError, TypeError):
                        pass
                
                # 解析地址
                address = str(row['Address']).strip() if pd.notna(row['Address']) else None
                
                record = {
                    'row_number': index + 2,  # Excel行号（考虑表头）
                    'device_id': str(row['Device ID']).strip() if pd.notna(row['Device ID']) else '',
                    'model_name': str(row['Device Model']).strip() if pd.notna(row['Device Model']) else '',
                    'institution_code': str(row['Institution Code']).strip() if pd.notna(row['Institution Code']) else '',
                    'description': str(row['Description']).strip() if pd.notna(row['Description']) else None,
                    'maintenance_threshold': maintenance_threshold,
                    'latitude': latitude,
                    'longitude': longitude,
                    'address': address,
                    'errors': []  # 存储验证错误信息
                }
                all_records.append(record)
            
            # 5. 批量验证数据
            valid_records, invalid_records = self._validate_import_records_batch(all_records)
            
            # 6. 生成缓存键并存储到Redis
            cache_key = f"device_batch_import:{uuid.uuid4()}"
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
            
            # 6. 准备返回数据
            result = {
                'total_records': len(df),
                'valid_count': len(valid_records),
                'invalid_count': len(invalid_records),
                'valid_records': valid_records[:100],  # 最多返回前100条预览
                'import_token': cache_key  # 重命名为import_token，更语义化
            }
            
            return result
            
        except pd.errors.EmptyDataError:
            raise InvalidUsageError("Excel file is empty or format is incorrect.")
        except Exception as e:
            if isinstance(e, InvalidUsageError):
                raise e
            raise InvalidUsageError(f"Failed to parse Excel file: {str(e)}")
    
    def _validate_import_record(self, record):
        """
        验证单条导入记录的有效性
        
        :param record: 包含设备信息的字典
        :return: True表示有效，False表示无效
        """
        is_valid = True
        errors = record['errors']
        
        # 1. 验证设备ID
        device_id = record['device_id']
        if not device_id:
            errors.append("Device ID cannot be empty")
            is_valid = False
        elif len(device_id) > 36:
            errors.append("The Device ID cannot exceed 36 characters in length")
            is_valid = False
        elif dao.get_device_by_device_id(device_id):
            errors.append(f"Device ID '{device_id}' already exists")
            is_valid = False
            
        # 2. 验证设备型号并获取model_id
        model_name = record['model_name']
        if not model_name:
            errors.append("Device model cannot be empty")
            is_valid = False
        else:
            # 根据型号名称查找model_id
            device_model = mapping_dao.get_device_model_by_name(model_name)
            if not device_model:
                errors.append(f"The device model '{model_name}' does not exist or has been deleted")
                is_valid = False
            else:
                record['model_id'] = device_model.id
                record['model_name_display'] = device_model.model_name
        
        # 3. 验证机构编码并获取institution_id
        institution_code = record['institution_code']
        if not institution_code:
            errors.append("Organization code cannot be empty")
            is_valid = False
        else:
            # 根据机构编码查找institution_id
            institution = institution_dao.get_institution_by_code(institution_code)
            if not institution:
                errors.append(f"The institution code '{institution_code}' does not exist or has been deleted")
                is_valid = False
            else:
                record['institution_id'] = institution.id
                record['institution_name_display'] = institution.institution_name
        
        # 4. 验证备注长度
        description = record.get('description')
        if description and len(description) > 256:
            errors.append("The note length cannot exceed 256 characters")
            is_valid = False
            
        return is_valid
    
    def confirm_batch_import(self, cache_key):
        """
        批量导入设备 - 第二步：确认导入
        从Redis获取数据，执行实际的导入操作
        
        :param cache_key: Redis缓存键
        :return: 包含导入结果的字典
        """
        try:
            # 1. 检查Redis连接
            try:
                redis_client.ping()
            except Exception as e:
                raise InvalidUsageError("Redis service connection failed, please contact administrator")
            
            # 2. 从Redis获取缓存数据
            cache_data_str = redis_client.get(cache_key)
            if not cache_data_str:
                raise InvalidUsageError("Import data has expired or does not exist, please upload file again.")
            
            cache_data = json.loads(cache_data_str)
            valid_records = cache_data.get('valid_records', [])
            invalid_records = cache_data.get('invalid_records', [])
            
            # 3. 批量检查设备ID重复（最后一次检查，防止并发问题）
            device_ids_to_check = [record['device_id'] for record in valid_records]
            existing_device_ids = dao.check_devices_exist_batch(device_ids_to_check)
            
            # 过滤掉已存在的设备（移到失败列表）
            final_valid_records = []
            for record in valid_records:
                if record['device_id'] in existing_device_ids:
                    record['errors'] = [f"Device ID '{record['device_id']}' already exists (concurrent import conflict)"]
                    invalid_records.append(record)
                else:
                    final_valid_records.append(record)
            
            # 4. 准备批量插入数据
            batch_device_data = []
            for record in final_valid_records:
                device_data = {
                    'device_id': record['device_id'],
                    'model_id': record['model_id'],
                    'institution_id': record['institution_id'],
                    'description': record.get('description'),
                    'maintenance_threshold': record.get('maintenance_threshold', 0),
                    'latitude': record.get('latitude'),
                    'longitude': record.get('longitude'),
                    'address': record.get('address')
                }
                batch_device_data.append(device_data)
            
            # 5. 执行批量插入
            imported_devices = []
            if batch_device_data:
                try:
                    success_device_ids, failed_device_list = dao.add_devices_batch(batch_device_data)
                    imported_devices = success_device_ids
                    
                    # 处理插入失败的设备（通常是并发冲突导致的重复）
                    if failed_device_list:
                        failed_device_map = {device_id: reason for device_id, reason in failed_device_list}
                        
                        # 将失败的设备记录移动到invalid_records
                        remaining_valid_records = []
                        for record in final_valid_records:
                            if record['device_id'] in failed_device_map:
                                record['errors'] = [failed_device_map[record['device_id']]]
                                invalid_records.append(record)
                            else:
                                remaining_valid_records.append(record)
                        
                        final_valid_records = remaining_valid_records
                        current_app.logger.warning(f"Batch import partially successful: {len(success_device_ids)} succeeded, {len(failed_device_list)} failed")
                    else:
                        current_app.logger.info(f"Batch import completed successfully: {len(success_device_ids)} device records")
                        
                except Exception as e:
                    # 整个批量插入过程失败（数据库连接问题等）
                    current_app.logger.error(f"Batch insert procedure failed: {str(e)}")
                    for record in final_valid_records:
                        record['errors'] = [f"Database operation failed: {str(e)}"]
                        invalid_records.append(record)
                    imported_devices = []
            
            # 6. 清除Redis缓存
            redis_client.delete(cache_key)
            
            # 7. 准备返回结果
            result = {
                'success_count': len(imported_devices),
                'imported_devices': imported_devices,
                'has_failed_file': len(invalid_records) > 0
            }
            
            # 5. 如果有失败记录，生成Excel文件
            if invalid_records:
                excel_buffer, filename = self._create_failed_import_excel(invalid_records)
                result['excel_buffer'] = excel_buffer
                result['filename'] = filename
            
            return result
            
        except json.JSONDecodeError:
            raise InvalidUsageError("Cache data format error.")
        except Exception as e:
            if isinstance(e, InvalidUsageError):
                raise e
            raise InvalidUsageError(f"Batch import failed: {str(e)}")
    
    def _create_failed_import_excel(self, invalid_records):
        """
        创建导入失败记录的Excel文件
        
        :param invalid_records: 失败记录列表
        :return: Excel文件的字节流和文件名
        """
        # 1. 准备表头配置
        headers = [
            {'key': 'row_number', 'title': 'Original Excel Row', 'width': 15},
            {'key': 'device_id', 'title': 'Device ID', 'width': 20},
            {'key': 'model_name', 'title': 'Device Model', 'width': 20},
            {'key': 'institution_code', 'title': 'Institution Code', 'width': 20},
            {'key': 'description', 'title': 'Description', 'width': 30},
            {'key': 'maintenance_threshold', 'title': 'Maintenance Threshold', 'width': 20},
            {'key': 'latitude', 'title': 'Latitude', 'width': 15},
            {'key': 'longitude', 'title': 'Longitude', 'width': 15},
            {'key': 'address', 'title': 'Address', 'width': 40},
            {'key': 'error_messages', 'title': 'Error Messages', 'width': 50}
        ]
        
        # 2. 处理数据，合并错误信息
        processed_records = []
        for record in invalid_records:
            processed_record = {
                'row_number': record.get('row_number', ''),
                'device_id': record.get('device_id', ''),
                'model_name': record.get('model_name', ''),
                'institution_code': record.get('institution_code', ''),
                'description': record.get('description', '') or '',
                'maintenance_threshold': record.get('maintenance_threshold', 0),
                'latitude': record.get('latitude', ''),
                'longitude': record.get('longitude', ''),
                'address': record.get('address', ''),
                'error_messages': '; '.join(record.get('errors', []))
            }
            processed_records.append(processed_record)
        
        # 3. 生成Excel文件
        excel_buffer = create_excel_file(processed_records, headers, "devices_import_failed")
        
        # 4. 生成文件名
        filename = f"devices_import_failed_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        
        return excel_buffer, filename
    
    def _validate_import_records_batch(self, records):
        """
        批量验证导入记录的有效性 - 高性能版本
        
        :param records: 包含设备信息的字典列表
        :return: 元组(有效记录列表, 无效记录列表)
        """
        valid_records = []
        invalid_records = []
        
        if not records:
            return valid_records, invalid_records
        
        # 1. 批量收集所有需要验证的数据
        device_ids_to_check = []
        model_names_to_check = []
        institution_codes_to_check = []
        
        for record in records:
            if record['device_id']:
                device_ids_to_check.append(record['device_id'])
            if record['model_name']:
                model_names_to_check.append(record['model_name'])
            if record['institution_code']:
                institution_codes_to_check.append(record['institution_code'])
        
        # 2. 批量查询数据库
        existing_device_ids = dao.check_devices_exist_batch(device_ids_to_check)
        
        # 查询所有需要的设备型号
        valid_models = {}
        if model_names_to_check:
            models = mapping_dao.get_device_models_by_names(list(set(model_names_to_check)))
            valid_models = {model.model_name: model for model in models}
        
        # 查询所有需要的机构
        valid_institutions = {}
        if institution_codes_to_check:
            institutions = institution_dao.get_institutions_by_codes(list(set(institution_codes_to_check)))
            valid_institutions = {inst.institution_code: inst for inst in institutions}
        
        # 3. 逐条验证记录
        for record in records:
            is_valid = True
            errors = record['errors']
            
            # 验证设备ID
            device_id = record['device_id']
            if not device_id:
                errors.append("Device ID cannot be empty")
                is_valid = False
            elif len(device_id) > 36:
                errors.append("Device ID cannot exceed 36 characters")
                is_valid = False
            elif device_id in existing_device_ids:
                errors.append(f"Device ID '{device_id}' already exists")
                is_valid = False
                
            # 验证设备型号
            model_name = record['model_name']
            if not model_name:
                errors.append("Device model cannot be empty")
                is_valid = False
            elif model_name in valid_models:
                model = valid_models[model_name]
                record['model_id'] = model.id
                record['model_name'] = model.model_name
            else:
                errors.append(f"Device model '{model_name}' does not exist or has been deleted")
                is_valid = False
            
            # 验证机构编码
            institution_code = record['institution_code']
            if not institution_code:
                errors.append("Institution code cannot be empty")
                is_valid = False
            elif institution_code in valid_institutions:
                institution = valid_institutions[institution_code]
                record['institution_id'] = institution.id
                record['institution_name'] = institution.institution_name
                record['institution_code'] = institution.institution_code
            else:
                errors.append(f"Institution code '{institution_code}' does not exist or has been deleted")
                is_valid = False
            
            # 验证备注长度
            description = record.get('description')
            if description and len(description) > 256:
                errors.append("Description cannot exceed 256 characters")
                is_valid = False
            
            # 验证维护阈值
            maintenance_threshold = record.get('maintenance_threshold', 0)
            if not isinstance(maintenance_threshold, int) or maintenance_threshold < 0:
                errors.append("Maintenance threshold must be a non-negative integer")
                is_valid = False
            
            # 验证经度
            latitude = record.get('latitude')
            if latitude is not None:
                try:
                    lat = float(latitude)
                    if not (-90 <= lat <= 90):
                        errors.append("Latitude must be between -90 and 90")
                        is_valid = False
                except (ValueError, TypeError):
                    errors.append("Latitude must be a valid number")
                    is_valid = False
            
            # 验证纬度
            longitude = record.get('longitude')
            if longitude is not None:
                try:
                    lon = float(longitude)
                    if not (-180 <= lon <= 180):
                        errors.append("Longitude must be between -180 and 180")
                        is_valid = False
                except (ValueError, TypeError):
                    errors.append("Longitude must be a valid number")
                    is_valid = False
            
            # 验证地址长度
            address = record.get('address')
            if address and len(address) > 512:
                errors.append("Address cannot exceed 512 characters")
                is_valid = False
                
            # 分类记录
            if is_valid:
                valid_records.append(record)
            else:
                invalid_records.append(record)
        
        return valid_records, invalid_records
    
    def create_import_template(self):
        """
        生成设备批量导入的Excel模板文件
        
        :return: Excel文件的字节流和文件名
        """
        # 1. 定义模板表头和示例数据
        headers = [
            {'key': 'device_id', 'title': 'Device ID', 'width': 20},
            {'key': 'model_name', 'title': 'Device Model', 'width': 20},
            {'key': 'institution_code', 'title': 'Institution Code', 'width': 20},
            {'key': 'description', 'title': 'Description', 'width': 30},
            {'key': 'maintenance_threshold', 'title': 'Maintenance Threshold', 'width': 20},
            {'key': 'latitude', 'title': 'Latitude', 'width': 15},
            {'key': 'longitude', 'title': 'Longitude', 'width': 15},
            {'key': 'address', 'title': 'Address', 'width': 40}
        ]
        
        # 2. 创建空数据（纯表头模板）
        # 如果需要示例数据，可以取消注释下面的代码
        sample_data = []
        
        # 示例数据版本（帮助用户理解格式）
        # sample_data = [
        #     {
        #         'device_id': '设备ID示例：DEV-001',
        #         'model_name': '设备型号示例：验钞机', 
        #         'institution_code': '机构编码示例：import',
        #         'description': '备注示例：可选填写设备描述信息'
        #     }
        # ]
        
        # 3. 生成Excel模板文件
        excel_buffer = create_excel_file(sample_data, headers, "Device Import Template")
        
        # 4. 生成文件名（使用英文避免编码问题）
        filename = "device_import_template.xlsx"
        
        return excel_buffer, filename

# 创建服务实例
device_service = DeviceService()
