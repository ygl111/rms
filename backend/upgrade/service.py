import json
from datetime import datetime
from typing import Any, Dict, List, Optional

from backend.common.exceptions import InvalidUsageError, ResourceNotFoundError
from backend.device.model import Device
from backend.extensions import db, redis_client
from backend.firmware.model import Firmware
from backend.mapping.model import DeviceMappingModel, DeviceMappingUpgradeTask
from backend.upgrade_record.model import UpgradeRecord
from backend.upgrade_task.model import UpgradeTask


class UpgradeService:
    """Upgrade domain service used by adapters (MQTT/TCP/etc.)."""

    DEVICE_TASK_STATUS_PENDING = 0
    DEVICE_TASK_STATUS_ACTIVE = 1
    DEVICE_TASK_STATUS_SUCCESS = 2
    DEVICE_TASK_STATUS_FAILED = 3

    IDEMPOTENCY_TTL_SECONDS = 24 * 60 * 60

    def check_upgrade_task(
        self,
        device_id: str,
        sn: str,
        model: str,
        module_versions: Optional[List[Dict[str, Any]]] = None,
    ) -> List[Dict[str, Any]]:
        device = self._validate_device_identity(device_id=device_id, sn=sn, model=model)

        rows = (
            db.session.query(DeviceMappingUpgradeTask, UpgradeTask, Firmware)
            .join(
                UpgradeTask,
                DeviceMappingUpgradeTask.task_id == UpgradeTask.id,
            )
            .join(Firmware, UpgradeTask.firmware_id == Firmware.id)
            .filter(
                DeviceMappingUpgradeTask.device_id == device.id,
                DeviceMappingUpgradeTask.is_deleted.is_(False),
                DeviceMappingUpgradeTask.confirm_upgrade == 1,
                DeviceMappingUpgradeTask.status.in_(
                    [self.DEVICE_TASK_STATUS_PENDING, self.DEVICE_TASK_STATUS_ACTIVE]
                ),
                UpgradeTask.is_deleted.is_(False),
                UpgradeTask.status == "active",
                Firmware.is_deleted.is_(False),
            )
            .order_by(UpgradeTask.created_at.asc())
            .all()
        )

        tasks: List[Dict[str, Any]] = []
        for _, task, firmware in rows:
            tasks.append(
                {
                    "task_id": task.id,
                    "firmware_id": firmware.id,
                    "module_type": self._resolve_module_type(module_versions),
                    "firmware_version": firmware.version,
                    "file_size": int(firmware.file_size or 0),
                    "md5": firmware.md5_hash,
                    "sha256": None,
                    "download_url": firmware.storage_path,
                    "force_upgrade": False,
                    "time_window_start": self._format_time(task.time_arrange_start),
                    "time_window_end": self._format_time(task.time_arrange_end),
                }
            )

        return tasks

    def report_upgrade_result(self, result: Dict[str, Any]) -> Dict[str, Any]:
        self._validate_required_fields(
            result,
            required_fields=[
                "msg_id",
                "task_id",
                "device_id",
                "module_type",
                "sn",
                "model",
            ],
        )

        device = self._validate_device_identity(
            device_id=result["device_id"],
            sn=result["sn"],
            model=result["model"],
        )

        idempotency_key = self._build_result_idempotency_key(
            msg_id=result["msg_id"],
            task_id=result["task_id"],
            device_id=result["device_id"],
            module_type=result["module_type"],
        )

        existing_record = self._find_existing_result_record(
            task_id=result["task_id"],
            device_uuid=device.id,
            msg_id=result["msg_id"],
            module_type=result["module_type"],
        )
        if existing_record:
            return {
                "duplicate": True,
                "record_id": existing_record.id,
                "task_summary": self.summarize_upgrade_task_status(result["task_id"]),
            }

        if not self._acquire_idempotency_lock(idempotency_key):
            existing_record = self._find_existing_result_record(
                task_id=result["task_id"],
                device_uuid=device.id,
                msg_id=result["msg_id"],
                module_type=result["module_type"],
            )
            return {
                "duplicate": True,
                "record_id": existing_record.id if existing_record else None,
                "task_summary": self.summarize_upgrade_task_status(result["task_id"]),
            }

        try:
            upgrade_record = self.write_upgrade_record(result, commit=False)
            self.update_device_task_status(
                task_id=result["task_id"],
                device_id=result["device_id"],
                status="success" if bool(result.get("success")) else "failed",
                commit=False,
            )
            task_summary = self.summarize_upgrade_task_status(
                task_id=result["task_id"], commit=False
            )
            db.session.commit()
            self._mark_idempotency_done(idempotency_key, {"record_id": upgrade_record.id})
            return {
                "duplicate": False,
                "record_id": upgrade_record.id,
                "task_summary": task_summary,
            }
        except Exception:
            db.session.rollback()
            self._release_idempotency_lock(idempotency_key)
            raise

    def update_device_task_status(
        self, task_id: str, device_id: str, status: Any, commit: bool = True
    ) -> DeviceMappingUpgradeTask:
        task = UpgradeTask.query.filter_by(id=task_id, is_deleted=False).first()
        if not task:
            raise ResourceNotFoundError(f"Upgrade task ID '{task_id}' does not exist")

        device = Device.query.filter_by(device_id=device_id, is_deleted=False).first()
        if not device:
            raise ResourceNotFoundError(f"Device ID '{device_id}' does not exist")

        mapping = DeviceMappingUpgradeTask.query.filter_by(
            task_id=task_id,
            device_id=device.id,
            is_deleted=False,
        ).first()
        if not mapping:
            raise ResourceNotFoundError(
                f"Upgrade mapping does not exist for task '{task_id}' and device '{device_id}'"
            )

        mapping.status = self._map_device_task_status(status)
        if commit:
            db.session.commit()
        return mapping

    def write_upgrade_record(
        self, record: Dict[str, Any], commit: bool = True
    ) -> UpgradeRecord:
        self._validate_required_fields(
            record,
            required_fields=["task_id", "device_id", "module_type", "msg_id"],
        )

        task = UpgradeTask.query.filter_by(id=record["task_id"], is_deleted=False).first()
        if not task:
            raise ResourceNotFoundError(f"Upgrade task ID '{record['task_id']}' does not exist")

        device = Device.query.filter_by(
            device_id=record["device_id"], is_deleted=False
        ).first()
        if not device:
            raise ResourceNotFoundError(f"Device ID '{record['device_id']}' does not exist")

        mapping = DeviceMappingUpgradeTask.query.filter_by(
            task_id=task.id,
            device_id=device.id,
            is_deleted=False,
        ).first()
        if not mapping:
            raise ResourceNotFoundError(
                f"Upgrade mapping does not exist for task '{task.id}' and device '{record['device_id']}'"
            )

        payload_to_store = {
            "msg_id": record.get("msg_id"),
            "task_id": record.get("task_id"),
            "firmware_id": record.get("firmware_id"),
            "device_id": record.get("device_id"),
            "module_type": record.get("module_type"),
            "before_version": record.get("before_version"),
            "target_version": record.get("target_version"),
            "after_version": record.get("after_version"),
            "success": bool(record.get("success")),
            "error_code": record.get("error_code"),
            "error_message": record.get("error_message"),
            "started_at": record.get("started_at"),
            "completed_at": record.get("completed_at"),
        }

        completed_at = self._parse_datetime(record.get("completed_at"))
        status = "success" if bool(record.get("success")) else "failed"
        result_message = json.dumps(payload_to_store, ensure_ascii=False, sort_keys=True)

        upgrade_record = UpgradeRecord(
            task_id=task.id,
            device_id=device.id,
            status=status,
            result_message=result_message,
            completed_at=completed_at,
            is_deleted=False,
        )
        db.session.add(upgrade_record)
        if commit:
            db.session.commit()
        return upgrade_record

    def summarize_upgrade_task_status(
        self, task_id: str, commit: bool = True
    ) -> Dict[str, Any]:
        task = UpgradeTask.query.filter_by(id=task_id, is_deleted=False).first()
        if not task:
            raise ResourceNotFoundError(f"Upgrade task ID '{task_id}' does not exist")

        mappings = DeviceMappingUpgradeTask.query.filter_by(
            task_id=task_id,
            is_deleted=False,
            confirm_upgrade=1,
        ).all()

        total = len(mappings)
        pending = 0
        active = 0
        success = 0
        failed = 0

        for item in mappings:
            if item.status == self.DEVICE_TASK_STATUS_SUCCESS:
                success += 1
            elif item.status == self.DEVICE_TASK_STATUS_FAILED:
                failed += 1
            elif item.status == self.DEVICE_TASK_STATUS_ACTIVE:
                active += 1
            else:
                pending += 1

        terminal = success + failed
        completed = total > 0 and terminal == total
        if completed:
            task.status = "completed"
        elif task.status == "completed":
            task.status = "active"

        if commit:
            db.session.commit()

        return {
            "task_id": task_id,
            "task_status": task.status,
            "total_devices": total,
            "pending_devices": pending,
            "active_devices": active,
            "success_devices": success,
            "failed_devices": failed,
            "completed": completed,
        }

    def _validate_device_identity(self, device_id: str, sn: str, model: str) -> Device:
        device = (
            db.session.query(Device)
            .join(DeviceMappingModel, Device.model_id == DeviceMappingModel.id)
            .filter(
                Device.device_id == device_id,
                Device.is_deleted.is_(False),
                DeviceMappingModel.is_deleted.is_(False),
            )
            .first()
        )
        if not device:
            raise ResourceNotFoundError(f"Device ID '{device_id}' does not exist")

        if model and getattr(device.model, "model_name", None) != model:
            raise InvalidUsageError(
                f"Model mismatch for device '{device_id}', expected '{device.model.model_name}', got '{model}'"
            )

        expected_sn = self._extract_device_sn(device)
        if expected_sn and sn and expected_sn != sn:
            raise InvalidUsageError(
                f"SN mismatch for device '{device_id}', expected '{expected_sn}', got '{sn}'"
            )

        return device

    def _extract_device_sn(self, device: Device) -> Optional[str]:
        if device.authentication_code:
            return str(device.authentication_code)

        if isinstance(device.extra_data, dict):
            for key in ("sn", "serial_number", "serialNo", "serial"):
                value = device.extra_data.get(key)
                if value:
                    return str(value)
        return None

    def _map_device_task_status(self, status: Any) -> int:
        if isinstance(status, int):
            return status

        normalized = str(status).lower().strip()
        mapping = {
            "pending": self.DEVICE_TASK_STATUS_PENDING,
            "active": self.DEVICE_TASK_STATUS_ACTIVE,
            "in_progress": self.DEVICE_TASK_STATUS_ACTIVE,
            "progress": self.DEVICE_TASK_STATUS_ACTIVE,
            "success": self.DEVICE_TASK_STATUS_SUCCESS,
            "failed": self.DEVICE_TASK_STATUS_FAILED,
        }
        if normalized not in mapping:
            raise InvalidUsageError(f"Unsupported device task status: {status}")
        return mapping[normalized]

    def _build_result_idempotency_key(
        self, msg_id: str, task_id: str, device_id: str, module_type: str
    ) -> str:
        return f"iods:upgrade:result:{msg_id}:{task_id}:{device_id}:{module_type}"

    def _acquire_idempotency_lock(self, key: str) -> bool:
        if redis_client is None:
            return True
        try:
            return bool(redis_client.set(key, "processing", nx=True, ex=self.IDEMPOTENCY_TTL_SECONDS))
        except Exception:
            return True

    def _mark_idempotency_done(self, key: str, data: Dict[str, Any]) -> None:
        if redis_client is None:
            return
        try:
            redis_client.setex(
                key,
                self.IDEMPOTENCY_TTL_SECONDS,
                json.dumps({"state": "done", "data": data}, ensure_ascii=False),
            )
        except Exception:
            return

    def _release_idempotency_lock(self, key: str) -> None:
        if redis_client is None:
            return
        try:
            value = redis_client.get(key)
            if value == "processing":
                redis_client.delete(key)
        except Exception:
            return

    def _find_existing_result_record(
        self, task_id: str, device_uuid: str, msg_id: str, module_type: str
    ) -> Optional[UpgradeRecord]:
        records = (
            UpgradeRecord.query.filter_by(
                task_id=task_id,
                device_id=device_uuid,
                is_deleted=False,
            )
            .order_by(UpgradeRecord.created_at.desc())
            .all()
        )

        for item in records:
            payload = self._safe_parse_json(item.result_message)
            if not payload:
                continue
            if payload.get("msg_id") == msg_id and payload.get("module_type") == module_type:
                return item
        return None

    def _safe_parse_json(self, text: Optional[str]) -> Optional[Dict[str, Any]]:
        if not text:
            return None
        try:
            value = json.loads(text)
        except Exception:
            return None
        if isinstance(value, dict):
            return value
        return None

    def _parse_datetime(self, value: Any) -> Optional[datetime]:
        if value is None or value == "":
            return None
        if isinstance(value, datetime):
            return value
        if isinstance(value, str):
            normalized = value.replace("Z", "+00:00")
            try:
                return datetime.fromisoformat(normalized)
            except ValueError as exc:
                raise InvalidUsageError(f"Invalid datetime format: {value}") from exc
        raise InvalidUsageError(f"Unsupported datetime value: {value}")

    def _format_time(self, value: Any) -> Optional[str]:
        if value is None:
            return None
        if hasattr(value, "isoformat"):
            return value.isoformat()
        return str(value)

    def _validate_required_fields(
        self, payload: Dict[str, Any], required_fields: List[str]
    ) -> None:
        missing = [field for field in required_fields if not payload.get(field)]
        if missing:
            raise InvalidUsageError(
                f"Missing required fields: {', '.join(missing)}"
            )

    def _resolve_module_type(
        self, module_versions: Optional[List[Dict[str, Any]]]
    ) -> str:
        if not isinstance(module_versions, list):
            return "firmware"
        for item in module_versions:
            if isinstance(item, dict) and item.get("module_type"):
                return str(item["module_type"])
        return "firmware"

