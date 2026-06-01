from backend.fault import dao
from backend.common.exceptions import ResourceNotFoundError, InvalidUsageError
from backend.common.excel import create_excel_file, generate_filename


class FaultService:
    """故障服务层：分页查询/筛选/排序、逻辑删除、导出、修改状态"""

    def get_paged_faults(self, page, per_page, filter_params=None, sort_by=None, sort_order='desc'):
        return dao.get_all_faults(page, per_page, filter_params, sort_by, sort_order, export=False)

    def get_non_fault_devices(self):
        """获取非故障设备列表。"""
        return dao.get_non_fault_devices()

    def get_fault_devices(self):
        """获取故障设备列表（未处理/处理中）。"""
        return dao.get_fault_devices()

    def update_fault_status(self, fault_id: str, new_status: str):
        fault = dao.get_fault_by_id(fault_id)
        if not fault:
            raise ResourceNotFoundError(f"Fault ID '{fault_id}' does not exist")
        return dao.update_fault_status(fault, new_status)

    def delete_fault(self, fault_id: str):
        fault = dao.get_fault_by_id(fault_id)
        if not fault:
            raise ResourceNotFoundError(f"Fault ID '{fault_id}' does not exist")
        dao.delete_fault(fault)

    def delete_faults_batch(self, ids):
        if not ids or not isinstance(ids, list):
            raise InvalidUsageError("ids cannot be empty and must be a string list")
        success_ids, failed_ids = dao.delete_faults_batch(ids)
        return {
            'total_requested': len(ids),
            'successfully_deleted': success_ids,
            'not_found': failed_ids,
            'success_count': len(success_ids),
            'not_found_count': len(failed_ids)
        }

    def export_faults(self, filter_params=None, sort_by='fault_time', sort_order='desc'):
        faults = dao.get_all_faults(None, None, filter_params, sort_by, sort_order, export=True)
        export_data = []
        for f in faults:
            export_data.append({
                'device_id': f.device.device_id if f.device else '',
                'model_name': f.device.model.model_name if f.device and f.device.model else '',
                'latitude': f.device.latitude if f.device else None,
                'longitude': f.device.longitude if f.device else None,
                'address': f.device.address if f.device else '',
                'fault_code': f.fault_code or '',
                'fault_level': f.fault_level,
                'status': f.status,
                'description': f.description or '',
                'fault_time': f.fault_time,
                'created_at': f.created_at
            })

        headers = [
            {"key": "device_id", "title": "Device ID", "width": 20},
            {"key": "model_name", "title": "Device Model", "width": 20},
            {"key": "latitude", "title": "Latitude", "width": 15},
            {"key": "longitude", "title": "Longitude", "width": 15},
            {"key": "address", "title": "Address", "width": 40},
            {"key": "fault_code", "title": "Fault Code", "width": 20},
            {"key": "fault_level", "title": "Fault Level", "width": 15},
            {"key": "status", "title": "Status", "width": 15},
            {"key": "description", "title": "Description", "width": 40},
            {"key": "fault_time", "title": "Fault Time", "width": 25},
            {"key": "created_at", "title": "Report Time", "width": 25},
        ]

        excel_buffer = create_excel_file(export_data, headers, "faults")
        filename = generate_filename("faults")
        return excel_buffer, filename

    # ---- Logs ----
    def create_fault_log(self, fault_id: str, operator_id: str, content: str):
        # 校验故障存在
        if not dao.get_fault_by_id(fault_id):
            raise ResourceNotFoundError(f"Fault ID '{fault_id}' does not exist")
        return dao.create_fault_log(fault_id, operator_id, content)

    def get_paged_fault_logs(self, page, per_page, filter_params=None, sort_by='operation_time', sort_order='desc'):
        return dao.get_all_fault_logs(page, per_page, filter_params, sort_by, sort_order, export=False)

    def delete_fault_log(self, log_id: str):
        log = dao.get_fault_log_by_id(log_id)
        if not log:
            raise ResourceNotFoundError(f"Fault log ID '{log_id}' does not exist")
        dao.delete_fault_log(log)

    def delete_fault_logs_batch(self, ids):
        if not ids or not isinstance(ids, list):
            raise InvalidUsageError("ids cannot be empty and must be a string list")
        success_ids, failed_ids = dao.delete_fault_logs_batch(ids)
        return {
            'total_requested': len(ids),
            'successfully_deleted': success_ids,
            'not_found': failed_ids,
            'success_count': len(success_ids),
            'not_found_count': len(failed_ids)
        }

    def export_fault_logs(self, filter_params=None, sort_by='operation_time', sort_order='desc'):
        logs = dao.get_all_fault_logs(None, None, filter_params, sort_by, sort_order, export=True)
        export_data = []
        for l in logs:
            export_data.append({
                'device_id': l.fault.device.device_id if l.fault and l.fault.device else '',
                'model_name': l.fault.device.model.model_name if l.fault and l.fault.device and l.fault.device.model else '',
                'fault_code': l.fault.fault_code if l.fault else '',
                'fault_level': l.fault.fault_level if l.fault else '',
                'content': l.content,
                'operation_time': l.operation_time,
                'operator_name': l.operator.full_name if l.operator else '',
            })
        headers = [
            {"key": "device_id", "title": "Device ID", "width": 20},
            {"key": "model_name", "title": "Device Model", "width": 20},
            {"key": "fault_code", "title": "Fault Code", "width": 20},
            {"key": "fault_level", "title": "Fault Level", "width": 15},
            {"key": "content", "title": "Log Content", "width": 50},
            {"key": "operation_time", "title": "Operation Time", "width": 25},
            {"key": "operator_name", "title": "Creator", "width": 15},
        ]
        excel_buffer = create_excel_file(export_data, headers, "fault_logs")
        filename = generate_filename("fault_logs")
        return excel_buffer, filename


fault_service = FaultService()


