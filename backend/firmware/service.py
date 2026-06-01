import os
import re
import hashlib
import base64
import shutil
from ftplib import FTP, error_perm
from werkzeug.utils import secure_filename
from flask import current_app
from backend.extensions import db, redis_client
from backend.firmware.model import Firmware
from backend.common.exceptions import InvalidUsageError, ResourceNotFoundError
# [新增] 导入其他模块的 DAO (如果需要验证外键的话)
from backend.mapping import dao as mapping_dao
from backend.user import dao as user_dao
from backend.firmware import dao
from backend.common.excel import create_excel_file, generate_filename
class FirmwareService:
    """固件服务层"""

    def analyze_firmware_file(self, file):
        """
        分析上传的固件文件，提取元数据，并将文件内容存储到Redis。
        :param file: Werkzeug FileStorage 对象
        :return: 包含文件元数据的字典（不包含临时路径）
        """
        try:
            # 1. 获取原始文件名
            original_filename = file.filename
            if not original_filename:
                raise InvalidUsageError("Filename is invalid")
            
            # 2. 先从原始文件名提取版本号（在secure_filename之前）
            version_parts = re.findall(r'\((.*?)\)', original_filename)
            
            if len(version_parts) < 2:
                raise InvalidUsageError(
                    f"Unable to extract the version number from the filename '{original_filename}'. Found {len(version_parts)}\
                          bracketed parts, at least 2 are required. The filename should contain at least two bracketed parts,\
                             for example 'name_(part1)_name_(part2).ext'."
                )
            version = f"{version_parts[0]}-{version_parts[1]}"

            # 3. 读取文件内容并计算MD5
            file_content = file.read()
            if not file_content:
                raise InvalidUsageError("File content is empty")
                
            md5 = hashlib.md5()
            md5.update(file_content)
            md5_hash = md5.hexdigest()
            
            # 4. 获取文件大小
            file_size = len(file_content)

            # 5. 将文件内容编码为base64并存储到Redis
            file_base64 = base64.b64encode(file_content).decode('utf-8')
            redis_key = f"firmware_temp:{md5_hash}"
            
            # 检查Redis连接
            try:
                redis_client.ping()
            except Exception as e:
                raise InvalidUsageError("Redis service connection failed, please contact administrator")
            
            # 设置过期时间为1小时（3600秒），避免Redis存储过多临时数据
            redis_client.setex(redis_key, 3600, file_base64)
            
            # 验证存储是否成功
            stored_data = redis_client.get(redis_key)
            if not stored_data:
                raise InvalidUsageError("Failed to store file data to Redis")

            # 6. 返回分析结果（不包含文件内容）
            return {
                "firmware_name": original_filename,  # 返回原始文件名
                "version": version,
                "md5_hash": md5_hash,
                "file_size": file_size
            }
        except InvalidUsageError:
            # 重新抛出我们的业务异常
            raise
        except Exception as e:
            raise InvalidUsageError(f"File analysis failed: {str(e)}")



    def create_firmware_from_analysis(self, firmware_data):
        """
        第二步：根据分析数据和用户输入创建固件记录，并上传到FTP。
        :param firmware_data: 包含所有固件元数据的字典
        :return: 创建的 Firmware 对象
        """
        
        # 根据MD5从Redis获取文件内容
        md5_hash = firmware_data.get('md5_hash')
        original_filename = firmware_data.get('firmware_name')  # 原始文件名
        redis_key = f"firmware_temp:{md5_hash}"

        try:
            # 1. 从Redis获取文件内容
            # 检查Redis连接
            try:
                redis_client.ping()
            except Exception as e:
                raise InvalidUsageError("Redis service connection failed, please contact administrator")
            
            file_base64 = redis_client.get(redis_key)
            if not file_base64:
                raise InvalidUsageError("File data has expired or does not exist, please upload file again for analysis")
            
            # 解码文件内容
            file_content = base64.b64decode(file_base64.encode('utf-8'))

            # 2. 验证外键有效性
            # 检查 compatible_model_id 是否有效
            model_id = firmware_data.get('compatible_model_id')
            if not mapping_dao.get_device_model_by_id(model_id):
                raise InvalidUsageError(f"Device model ID '{model_id}' is invalid")

            # 检查 uploader_id 是否有效
            uploader_id = firmware_data.get('uploader_id')
            if not user_dao.get_user_by_id(uploader_id):
                raise InvalidUsageError(f"Uploader ID '{uploader_id}' is invalid")

            # 3. 从 app config 获取 FTP 配置
            ftp_host = current_app.config['FTP_HOST']
            ftp_user = current_app.config['FTP_USER']
            ftp_pass = current_app.config['FTP_PASS']
            ftp_path = current_app.config['FTP_PATH']
            ftp_url = current_app.config['FTP_URL']

            # 4. 连接并上传到 FTP 服务器（使用原始文件名）
            try:
                # 创建内存中的文件对象
                from io import BytesIO
                file_obj = BytesIO(file_content)
                
                with FTP(ftp_host) as ftp:
                    ftp.login(user=ftp_user, passwd=ftp_pass)
                    try:
                        ftp.cwd(ftp_path)
                    except error_perm:
                        ftp.mkd(ftp_path)
                        ftp.cwd(ftp_path)
                    # 上传时使用原始文件名
                    ftp.storbinary(f'STOR {original_filename}', file_obj)
                # 构造存储路径 (FTP下载地址，使用原始文件名)
                storage_path = f"{ftp_url.rstrip('/')}/{ftp_path.lstrip('/')}/{original_filename}"
            except Exception as e:
                raise InvalidUsageError(f"FTP upload failed: {str(e)}")

            # 5. 创建并保存 Firmware 记录到数据库（使用原始文件名）
            new_firmware = Firmware(
                firmware_name=original_filename,  # 存储原始文件名
                version=firmware_data.get('version'),
                file_size=firmware_data.get('file_size'),
                md5_hash=firmware_data.get('md5_hash'),
                storage_path=storage_path,
                description=firmware_data.get('description'),
                uploader_id=firmware_data.get('uploader_id'),
                compatible_model_id=firmware_data.get('compatible_model_id')
            )
            
            db.session.add(new_firmware)
            db.session.commit()
            
            # 6. 成功后清理Redis中的临时数据
            try:
                redis_client.delete(redis_key)
            except Exception:
                pass  # 忽略清理Redis的错误
            
            return new_firmware

        except InvalidUsageError:
            # 重新抛出我们的业务异常
            raise
        except Exception as e:
            # 回滚数据库事务
            db.session.rollback()
            raise InvalidUsageError(f"Firmware creation failed: {str(e)}")
        # 注意：这里移除了finally块，因为我们只想在成功时清理Redis

    def get_paged_firmwares(self, page, per_page, filter_params=None, sort_by='uploaded_at', sort_order='desc'):
        """获取分页的固件列表"""
        return dao.get_firmwares(page, per_page, filter_params, sort_by, sort_order)

    def delete_firmware(self,firmware_id):
        firmware = dao.get_firmware_by_id(firmware_id)
        if not firmware:
            raise ResourceNotFoundError(f"Firmware ID '{firmware_id}' does not exist")
        return dao.delete_firmware(firmware)

    def batch_delete_firmwares(self, firmware_ids):
        """批量删除固件（逻辑删除）"""
        return dao.batch_delete_firmwares(firmware_ids)

    def export_firmwares(self, filter_params=None, sort_by='uploaded_at', sort_order='desc'):
        """导出固件数据"""
        firmwares = dao.get_firmwares_for_export(filter_params, sort_by, sort_order)
        # 构造导出数据
        export_data = []
        for fw in firmwares:
            # 将文件大小从字节转换为MB，保留2位小数
            file_size_mb = round(fw.file_size / (1024 * 1024), 2) if fw.file_size else 0
            
            export_data.append({
                'firmware_name': fw.firmware_name,
                'version': fw.version,
                'file_size': f"{file_size_mb} MB",
                'md5_hash': fw.md5_hash,
                'compatible_model_id': fw.compatible_model_id,
                'compatible_model_name': fw.compatible_model.model_name if fw.compatible_model else '',
                'uploader_id': fw.uploader_id,
                'uploader_name': fw.uploader.full_name if fw.uploader else '',
                'uploaded_at': fw.uploaded_at,
                'status': fw.status,
                'description': fw.description
            })
        # 构造表头
        headers = [
            {'key': 'firmware_name', 'title': 'Firmware Name', 'width': 80},
            {'key': 'version', 'title': 'Firmware Version', 'width': 40},
            {'key': 'file_size', 'title': 'Firmware Size (MB)', 'width': 18},
            {'key': 'compatible_model_name', 'title': 'Device Model', 'width': 20},
            {'key': 'uploader_name', 'title': 'Uploader', 'width': 15},
            {'key': 'uploaded_at', 'title': 'Upload Time', 'width': 30},
            {'key': 'md5_hash', 'title': 'Firmware MD5', 'width': 35},
            {'key': 'description', 'title': 'Firmware Description', 'width': 30}
        ]

        excel_buffer = create_excel_file(export_data, headers, "firmware")
        filename = generate_filename("firmware")
        return excel_buffer, filename

    # ------------------ 分片上传辅助方法 ------------------
    
    def _chunk_upload_root(self):
        """获取分片上传根目录，确保目录存在"""
        path = current_app.config.get('CHUNK_UPLOAD_DIR')
        if not path:
            raise InvalidUsageError("CHUNK_UPLOAD_DIR is not configured")
        # 确保目录存在
        os.makedirs(path, exist_ok=True)
        return path

    def _chunk_folder_key(self, uploader_id: str, filename: str, last_modified: str) -> str:
        """
        基于上传者ID、原始文件名和最后修改时间生成稳定的文件夹key（MD5哈希）。
        这样同一个文件的分片会被放在同一个目录中，支持断点续传。
        """
        raw = f"{uploader_id}|{filename}|{last_modified}"
        return hashlib.md5(raw.encode('utf-8')).hexdigest()

    def get_chunk_folder(self, uploader_id: str, filename: str, last_modified: str) -> str:
        """获取或创建分片会话目录"""
        root = self._chunk_upload_root()
        key = self._chunk_folder_key(uploader_id, filename, last_modified)
        folder = os.path.join(root, key)
        os.makedirs(folder, exist_ok=True)
        return folder

    def save_chunk_if_absent(self, folder: str, chunk_index: int, file_storage) -> bool:
        """
        将当前分片保存到目标目录下的以数字命名的文件中（如 1,2,3...）。
        如果同名分片已存在则不覆盖，返回 False；保存成功返回 True。
        :param folder: 分片目录
        :param chunk_index: 分片索引（从1开始）
        :param file_storage: Werkzeug FileStorage 对象
        :return: True 表示保存成功，False 表示分片已存在
        """
        if chunk_index <= 0:
            raise InvalidUsageError("chunk_index must be >= 1")
        
        chunk_path = os.path.join(folder, str(chunk_index))
        
        # 如果分片已存在，不覆盖（幂等性）
        if os.path.exists(chunk_path):
            return False
        
        try:
            # 以二进制方式流式写入，避免一次性读全文件内容到内存
            with open(chunk_path, 'wb') as f:
                while True:
                    buf = file_storage.stream.read(1024 * 1024)  # 每次读1MB
                    if not buf:
                        break
                    f.write(buf)
            return True
        except Exception as e:
            # 若写入失败，清理半成品文件
            try:
                if os.path.exists(chunk_path):
                    os.remove(chunk_path)
            except Exception:
                pass
            raise InvalidUsageError(f"Failed to save chunk: {e}")

    def find_missing_chunks(self, folder: str, total_chunks: int) -> list:
        """
        检查1~n的分片文件，返回缺失的分片索引列表。
        :param folder: 分片目录
        :param total_chunks: 总分片数
        :return: 缺失的分片索引列表（升序）
        """
        if total_chunks <= 0:
            raise InvalidUsageError("total_chunks must be >= 1")
        
        missing = []
        for i in range(1, total_chunks + 1):
            if not os.path.isfile(os.path.join(folder, str(i))):
                missing.append(i)
        return missing

    def merge_chunks_and_store_to_redis(self, folder: str, total_chunks: int, original_filename: str):
        """
        合并分片为一个完整文件，计算元信息（MD5、文件大小、版本），
        将内容写入 Redis（与 analyze 路径保持一致），并返回 analysis_result。
        成功后会立即删除分片目录（方案A：节省磁盘空间）。
        
        :param folder: 分片目录
        :param total_chunks: 总分片数
        :param original_filename: 原始文件名（用于提取版本号）
        :return: analysis_result 字典（与 analyze 接口返回格式一致）
        """
        if total_chunks <= 0:
            raise InvalidUsageError("total_chunks must be >= 1")

        merged_path = os.path.join(folder, 'merged.tmp')
        md5 = hashlib.md5()
        file_size = 0

        try:
            # 1. 按顺序合并分片 1..n，边合并边计算 MD5
            with open(merged_path, 'wb') as out_f:
                for i in range(1, total_chunks + 1):
                    chunk_path = os.path.join(folder, str(i))
                    if not os.path.isfile(chunk_path):
                        raise InvalidUsageError(f"Chunk {i} is missing during merge")
                    
                    with open(chunk_path, 'rb') as in_f:
                        while True:
                            buf = in_f.read(1024 * 1024)  # 每次读1MB
                            if not buf:
                                break
                            out_f.write(buf)
                            md5.update(buf)
                            file_size += len(buf)

            md5_hash = md5.hexdigest()

            # 2. 检查 Redis 连接
            try:
                redis_client.ping()
            except Exception:
                raise InvalidUsageError("Redis service connection failed, please contact administrator")

            # 3. 读取合并后的文件，将内容存入 Redis（与 analyze 一致）
            with open(merged_path, 'rb') as f:
                content = f.read()
            
            file_base64 = base64.b64encode(content).decode('utf-8')
            redis_key = f"firmware_temp:{md5_hash}"
            # 设置 TTL 为 3600 秒（1小时）
            redis_client.setex(redis_key, 3600, file_base64)

            # 验证存储是否成功
            stored_data = redis_client.get(redis_key)
            if not stored_data:
                raise InvalidUsageError("Failed to store file data to Redis")

            # 4. 从原始文件名提取版本（与 analyze 逻辑保持一致）
            version_parts = re.findall(r'\((.*?)\)', original_filename)
            if len(version_parts) < 2:
                raise InvalidUsageError(
                    f"Unable to extract the version number from the filename '{original_filename}'. "
                    f"Found {len(version_parts)} bracketed parts, at least 2 are required."
                )
            version = f"{version_parts[0]}-{version_parts[1]}"

            # 5. 构造分析结果（与 analyze 接口返回格式一致）
            analysis_result = {
                "firmware_name": original_filename,
                "version": version,
                "md5_hash": md5_hash,
                "file_size": file_size,
            }

            # 6. 清理分片目录（方案A：合并成功后立即删除，节省磁盘空间）
            try:
                shutil.rmtree(folder, ignore_errors=True)
            except Exception as e:
                # 记录日志但不抛出异常，因为主要任务（合并+存Redis）已完成
                current_app.logger.warning(f"Failed to cleanup chunk folder {folder}: {e}")

            return analysis_result

        except InvalidUsageError:
            # 重新抛出业务异常
            raise
        except Exception as e:
            raise InvalidUsageError(f"Failed to merge chunks: {str(e)}")
        finally:
            # 双保险：尝试删除临时合并文件
            try:
                if os.path.exists(merged_path):
                    os.remove(merged_path)
            except Exception:
                pass

    def delete_chunk_session(self, uploader_id: str, filename: str, last_modified: str):
        """
        删除分片会话目录（用于取消上传或清理残留分片）
        
        :param uploader_id: 上传者ID
        :param filename: 原始文件名
        :param last_modified: 文件最后修改时间
        :return: (是否删除成功, upload_key)
        """
        try:
            root = self._chunk_upload_root()
            upload_key = self._chunk_folder_key(uploader_id, filename, last_modified)
            folder = os.path.join(root, upload_key)
            
            # 检查目录是否存在
            if not os.path.exists(folder):
                return False, upload_key
            
            # 删除整个目录及其内容
            shutil.rmtree(folder, ignore_errors=True)
            
            # 验证是否删除成功
            if os.path.exists(folder):
                raise InvalidUsageError("Failed to delete chunk session directory")
            
            return True, upload_key
            
        except InvalidUsageError:
            raise
        except Exception as e:
            raise InvalidUsageError(f"Failed to delete chunk session: {str(e)}")


firmware_service = FirmwareService()
