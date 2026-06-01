from backend.upgrade_record import dao
from backend.common.exceptions import ResourceNotFoundError, InvalidUsageError
from backend.common.excel import create_excel_file, generate_filename


class UpgradeRecordService:
    """升级记录服务层：分页查询/筛选/排序、逻辑删除、导出"""

    def get_paged_upgrade_records(self, page, per_page, filter_params=None, sort_by=None, sort_order='desc'):
        return dao.get_all_upgrade_records(page, per_page, filter_params, sort_by, sort_order, export=False)

    def delete_upgrade_record(self, record_id: str):
        record = dao.get_upgrade_record_by_id(record_id)
        if not record:
            raise ResourceNotFoundError(f"Upgrade record ID '{record_id}' does not exist")
        dao.delete_upgrade_record(record)

    def delete_upgrade_records_batch(self, ids):
        if not ids or not isinstance(ids, list):
            raise InvalidUsageError("ids cannot be empty and must be a string list")
        success_ids, failed_ids = dao.delete_upgrade_records_batch(ids)
        return {
            'total_requested': len(ids),
            'successfully_deleted': success_ids,
            'not_found': failed_ids,
            'success_count': len(success_ids),
            'not_found_count': len(failed_ids)
        }

    def export_upgrade_records(self, filter_params=None, sort_by='created_at', sort_order='desc'):
        records = dao.get_all_upgrade_records(None, None, filter_params, sort_by, sort_order, export=True)
        export_data = []
        for r in records:
            export_data.append({
                'task_code': r.task.task_code if getattr(r, 'task', None) else '',
                'model_name': r.device.model.model_name if getattr(r, 'device', None) and getattr(r.device, 'model', None) else '',
                'device_id': r.device.device_id if getattr(r, 'device', None) else '',
                'firmware_version': r.task.firmware.version if getattr(r, 'task', None) and getattr(r.task, 'firmware', None) else '',
                'status': r.status,
                'result_message': r.result_message or '',
                'created_at': r.created_at,
                'completed_at': r.completed_at,
            })

        headers = [
            {"key": "task_code", "title": "Upgrade Task Code", "width": 30},
            {"key": "model_name", "title": "Device Model", "width": 20},
            {"key": "device_id", "title": "Device ID", "width": 30},
            {"key": "firmware_version", "title": "Firmware Version", "width": 40},
            {"key": "status", "title": "Status", "width": 15},
            {"key": "result_message", "title": "Upgrade Result Message", "width": 50},
            {"key": "created_at", "title": "Created Time", "width": 30},
            {"key": "completed_at", "title": "Completed Time", "width": 30},
        ]

        excel_buffer = create_excel_file(export_data, headers, "upgrade_records")
        filename = generate_filename("upgrade_records")
        return excel_buffer, filename


upgrade_record_service = UpgradeRecordService()


