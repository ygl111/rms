from backend.extensions import db
from backend.upgrade_task import dao
from backend.common.exceptions import InvalidUsageError, ResourceNotFoundError
# 导入其他模块的DAO进行外键验证
from backend.firmware import dao as firmware_dao
from backend.user import dao as user_dao
from backend.mapping import dao as mapping_dao
from backend.upgrade_record import dao as record_dao
from backend.institution import dao as institution_dao
from backend.common.excel import create_excel_file, generate_filename
from backend.mapping import dao as mapping_dao
from backend.email.service import email_send_service
from flask import current_app
class UpgradeTaskService:
    """升级任务服务层"""

    def _send_upgrade_notification_email(self, upgrade_task):
        """
        发送升级任务通知邮件
        :param upgrade_task: 升级任务对象
        """
        try:
            # 准备邮件内容
            subject = "Upgrade Task Notification"
            
            # 构建详细的邮件内容
            model_name = upgrade_task.model.model_name if upgrade_task.model else "Unknown"
            firmware_version = upgrade_task.firmware.version if upgrade_task.firmware else "Unknown"
            firmware_name = upgrade_task.firmware.firmware_name if upgrade_task.firmware else "Unknown"
            
            content = f"""Upgrade Task Notification

Task Code: {upgrade_task.task_code}
Device Model: {model_name}
Firmware Version: {firmware_version}
Firmware Name: {firmware_name}

A new upgrade task has been created. Please check the system for more details."""
            
            # 调用邮件服务发送邮件
            email_send_service.send_email(
                email_type='upgrade',
                subject=subject,
                content=content,
                content_type='plain'
            )
            current_app.logger.info(f"升级任务 {upgrade_task.task_code} 的邮件通知发送成功")
        except Exception as e:
            # 邮件发送失败不影响升级任务创建，只记录日志
            current_app.logger.error(f"发送升级任务邮件通知失败: {e}")

    def create_upgrade_task(self, task_data):
        """
        创建升级任务并为同型号设备分配任务
        
        :param task_data: 包含任务所有信息的字典
        :return: 创建的 UpgradeTask 对象
        """
        try:
            # 1. 验证外键有效性
            # 检查固件ID是否有效
            firmware_id = task_data.get('firmware_id')
            if not firmware_dao.get_firmware_by_id(firmware_id):
                raise InvalidUsageError(f"Firmware ID '{firmware_id}' is invalid")

            # 检查创建人ID是否有效
            creator_id = task_data.get('creator_id')
            if not user_dao.get_user_by_id(creator_id):
                raise InvalidUsageError(f"Creator ID '{creator_id}' is invalid")

            # 检查设备型号ID是否有效
            model_id = task_data.get('model_id')
            if not mapping_dao.get_device_model_by_id(model_id):
                raise InvalidUsageError(f"Device model ID '{model_id}' is invalid")

            # 验证日期逻辑
            start_date = task_data.get('start_date')
            end_date = task_data.get('end_date')
            time_arrange_start = task_data.get('time_arrange_start')
            time_arrange_end = task_data.get('time_arrange_end')
            if start_date == None or end_date == None or time_arrange_end == None or time_arrange_start == None or start_date > end_date:
                task_data['start_date'] = None
                task_data['end_date'] = None    
                task_data['time_arrange_start'] = None
                task_data['time_arrange_end'] = None
            


            # 先验证是否有选择机构
            institution_ids = task_data.get('institution_ids', [])
            if not institution_ids:
                raise InvalidUsageError("Must select institutions to assign upgrade tasks to")
            #再验证这些机构是否存在
            valid_institutions = institution_dao.get_institution_by_ids(institution_ids)
            if not valid_institutions:
                raise InvalidUsageError("Selected institution IDs are invalid or do not exist")
            
            #移除掉institution_ids 让升级任务创建成功
            institution_ids_pop = task_data.pop('institution_ids', [])
            # 移除send_email参数，不存入数据库
            send_email = task_data.pop('send_email', False)


            # 4. 创建升级任务
            upgrade_task = dao.create_upgrade_task(task_data)

            # 5. 为机构创建任务-机构映射表
            institution_ids = []
            for institution in valid_institutions:
                institution_ids.append(institution.id)
            mapping_dao.create_institution_upgrade_task_mappings(upgrade_task.id,institution_ids)

            # 6. 为选择机构下同型号设备创建映射记录
            mappings = mapping_dao.create_device_upgrade_task_mappings(
                upgrade_task.id, 
                model_id,
                institution_ids
            )

            # 6. 提交所有数据
            db.session.commit()
            # 7. 如果需要发送邮件通知
            if send_email:
                self._send_upgrade_notification_email(upgrade_task)
            return upgrade_task

        except InvalidUsageError:
            # 重新抛出业务异常
            db.session.rollback()
            raise
        except Exception as e:
            # 回滚数据库事务
            db.session.rollback()
            raise InvalidUsageError(f"Failed to create upgrade task: {str(e)}")

    def get_paged_upgrade_tasks(self, page, per_page, filter_params=None, sort_by=None, sort_order='asc'):
        """获取分页的升级任务列表，支持筛选和排序"""
        return dao.get_all_upgrade_tasks(page, per_page, filter_params, sort_by, sort_order, export=False)

    def get_task_device_mappings(self, task_id, filters=None):
        """获取任务相关的所有设备映射记录，支持 institution_id 精确筛选、device_id 模糊筛选，并默认 confirm_upgrade=0 置前排序。"""
        # 先验证任务是否存在
        task = dao.get_upgrade_task_by_id(task_id)
        if not task:
            raise ResourceNotFoundError(f"Upgrade task ID '{task_id}' does not exist")
        
        # 基于关系集合做筛选
        mappings = [m for m in task.device_mappings if not m.is_deleted]

        if filters:
            institution_id = filters.get('institution_id')
            device_id_like = filters.get('device_id')

            if institution_id:
                mappings = [m for m in mappings if m.device and m.device.institution_id == institution_id]
            if device_id_like:
                mappings = [m for m in mappings if m.device and m.device.device_id and device_id_like in m.device.device_id]

        # confirm_upgrade=0 置前，然后维持原相对顺序（稳定排序）
        mappings.sort(key=lambda m: (0 if m.confirm_upgrade == 0 else 1))
        return mappings

    def delete_upgrade_task(self, task_id):
        """删除升级任务（逻辑删除）"""
        try:
            task = dao.get_upgrade_task_by_id(task_id)
            if not task:
                raise ResourceNotFoundError(f"Upgrade task ID '{task_id}' does not exist")
            
            # 1. 先删除相关的升级记录
            record_dao.delete_upgrade_records_by_task_id(task_id)
            
            # 2. 再删除相关的设备映射记录
            mapping_dao.delete_device_upgrade_task_mappings_by_task_id(task_id)
            
            # 3. 最后删除升级任务本身
            dao.delete_upgrade_task(task)
            
            # 3. 提交事务（因为涉及多个表的操作）
            db.session.commit()
            
        except ResourceNotFoundError:
            # 重新抛出资源不存在错误
            raise
        except Exception as e:
            # 回滚事务
            db.session.rollback()
            raise InvalidUsageError(f"Failed to delete upgrade task: {str(e)}")


    def update_upgrade_task(self, task_id, update_data):
        try:
            task = dao.get_upgrade_task_by_id(task_id)
            if not task:
                raise ResourceNotFoundError(f"Upgrade task ID '{task_id}' does not exist")
            dao.update_upgrade_task(task, update_data)
            db.session.commit()
            return task
        except ResourceNotFoundError:
            raise ResourceNotFoundError(f"Upgrade task ID '{task_id}' does not exist")
        except Exception as e:
            db.session.rollback()
            raise InvalidUsageError(f"Failed to update upgrade task: {str(e)}")

    def delete_upgrade_tasks_batch(self, ids):
        try:
            success_ids, failed_ids = dao.delete_upgrade_tasks_batch(ids)
            db.session.commit()
            return {
                "success_ids": success_ids,
                "failed_ids": failed_ids,
                "message": f"Successfully deleted {len(success_ids)} items, failed {len(failed_ids)} items"
            }
        except Exception as e:
            db.session.rollback()
            raise InvalidUsageError(f"Failed to batch delete upgrade tasks: {str(e)}")

    def export_upgrade_tasks(self, filter_params, sort_by, sort_order):
        try:
            #1. 获取要导出的升级任务数据
            tasks = dao.get_all_upgrade_tasks(filter_params=filter_params, sort_by=sort_by, sort_order=sort_order, export=True)
            export_data = []
            for task in tasks:
                # 组合升级时间段
                time_arrange = f"{task.time_arrange_start} - {task.time_arrange_end}" if task.time_arrange_start and task.time_arrange_end else ''
                
                export_data.append({
                    'task_code': task.task_code,
                    'model_name': task.model.model_name,
                    'firmware_version': task.firmware.version,
                    'firmware_name': task.firmware.firmware_name,
                    'status': "已取消" if task.status == 'cancelled' else "激活" if task.status == 'active' else "已完成",
                    'start_date': task.start_date,
                    'end_date': task.end_date,
                    'time_arrange': time_arrange,
                    'creator_name': task.creator.full_name,
                    'created_at': task.created_at
                })
            #2. 定义表头和字段
            headers = [
                {"key": "task_code", "title": "Task Code", "width": 20},
                {"key": "model_name", "title": "Device Model", "width": 20},
                {"key": "firmware_version", "title": "Firmware Version", "width": 40},
                {"key": "firmware_name", "title": "Firmware Name", "width": 80},
                {"key": "status", "title": "Status", "width": 15},
                {"key": "start_date", "title": "Start Date", "width": 30},
                {"key": "end_date", "title": "End Date", "width": 30},
                {"key": "time_arrange", "title": "Upgrade Time Period", "width": 50},
                {"key": "creator_name", "title": "Creator", "width": 15},
                {"key": "created_at", "title": "Created Time", "width": 30}
            ]
            #3.生成excel文件
            excel_buffer=create_excel_file(export_data, headers,"upgrade_tasks_export")
            #4.生成文件名
            filename=generate_filename("upgrade_tasks_export")
            return excel_buffer, filename

        except Exception as e:
            raise InvalidUsageError(f"Failed to export upgrade tasks: {str(e)}")

    def update_devices_confirm_upgrade(self, task_id, device_ids, confirm_upgrade):
        """在指定任务下，批量更新给定 device_ids 的 confirm_upgrade。"""
        # 校验任务存在
        task = dao.get_upgrade_task_by_id(task_id)
        if not task:
            raise ResourceNotFoundError(f"Upgrade task ID '{task_id}' does not exist")

        # 执行批量更新
        try:
            affected = mapping_dao.update_confirm_upgrade_by_device_ids(task_id, device_ids, confirm_upgrade)
            db.session.commit()
            return {"affected": affected, "confirm_upgrade": confirm_upgrade, "device_ids": device_ids}
        except Exception as e:
            db.session.rollback()
            raise InvalidUsageError(f"Failed to update upgrade confirmation status: {str(e)}")


# 创建服务实例
upgrade_task_service = UpgradeTaskService()
