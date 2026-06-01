import json
import logging
import os
import socket
import time
from typing import Any, Dict, Optional, Tuple

import paho.mqtt.client as mqtt
from flask import Flask

from backend.common.exceptions import ApiException, ResourceNotFoundError
from backend.extensions import redis_client
from backend.upgrade import upgrade_service


LOGGER = logging.getLogger(__name__)


class MqttUpgradeAdapter:
    """MQTT entry adapter for IoDs upgrade check/progress/result messages."""

    RESPONSE_CACHE_TTL_SECONDS = 24 * 60 * 60

    def __init__(self, app: Flask):
        self.app = app
        client_id = self._resolve_client_id()
        self.client = mqtt.Client(
            client_id=client_id,
            protocol=mqtt.MQTTv311,
        )
        self._apply_auth_config()
        self._apply_tls_config()
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.client.on_message = self._on_message

    def start(self) -> None:
        host = self.app.config.get("MQTT_BROKER_HOST", "127.0.0.1")
        port = int(self.app.config.get("MQTT_BROKER_PORT", 1883))
        keepalive = int(self.app.config.get("MQTT_KEEPALIVE", 60))
        retry_interval = int(self.app.config.get("MQTT_RETRY_INTERVAL_SECONDS", 3))
        self.client.reconnect_delay_set(min_delay=1, max_delay=max(2, retry_interval * 4))

        while True:
            try:
                LOGGER.info(
                    "Starting mqtt_upgrade_adapter: host=%s port=%s keepalive=%s client_id=%s",
                    host,
                    port,
                    keepalive,
                    self.client._client_id.decode(errors="ignore"),
                )
                self.client.connect(host, port=port, keepalive=keepalive)
                # Keep loop inside retry guard so socket/select errors won't kill process.
                self.client.loop_forever(retry_first_connection=True)
            except KeyboardInterrupt:
                LOGGER.info("mqtt_upgrade_adapter stopped by keyboard interrupt")
                raise
            except Exception:
                LOGGER.exception(
                    "MQTT loop exited unexpectedly, retrying in %s seconds",
                    retry_interval,
                )
                try:
                    self.client.disconnect()
                except Exception:
                    pass
                time.sleep(retry_interval)

    def _apply_auth_config(self) -> None:
        username = self.app.config.get("MQTT_USERNAME")
        password = self.app.config.get("MQTT_PASSWORD")
        if username:
            self.client.username_pw_set(username, password=password)

    def _apply_tls_config(self) -> None:
        if not bool(self.app.config.get("MQTT_TLS_ENABLED", False)):
            return

        ca_cert = self.app.config.get("MQTT_TLS_CA_CERT")
        certfile = self.app.config.get("MQTT_TLS_CERTFILE")
        keyfile = self.app.config.get("MQTT_TLS_KEYFILE")
        tls_insecure = bool(self.app.config.get("MQTT_TLS_INSECURE", False))
        self.client.tls_set(ca_certs=ca_cert, certfile=certfile, keyfile=keyfile)
        self.client.tls_insecure_set(tls_insecure)

    def _on_connect(
        self,
        client: mqtt.Client,
        _userdata: Any,
        _flags: Dict[str, Any],
        rc: int,
    ) -> None:
        with self.app.app_context():
            if rc != 0:
                LOGGER.error("MQTT connect failed, rc=%s", rc)
                return

            topics = self._get_subscribe_topics()
            qos = int(self.app.config.get("MQTT_UPGRADE_QOS", 1))
            for topic in topics:
                client.subscribe(topic, qos=qos)
                LOGGER.info("Subscribed topic=%s qos=%s", topic, qos)

    def _on_disconnect(
        self,
        _client: mqtt.Client,
        _userdata: Any,
        rc: int,
    ) -> None:
        if rc == 0:
            LOGGER.info("MQTT disconnected cleanly rc=%s", rc)
            return
        LOGGER.warning("MQTT disconnected unexpectedly rc=%s", rc)

    def _on_message(self, _client: mqtt.Client, _userdata: Any, msg: mqtt.MQTTMessage) -> None:
        with self.app.app_context():
            topic = msg.topic
            payload_text = self._decode_payload(msg.payload)

            try:
                payload = self._parse_json(payload_text)
                topic_type, device_id = self._parse_topic(topic)
                msg_id = payload.get("msg_id")
                if not msg_id:
                    raise ValueError("Missing msg_id in payload")

                self._validate_device_id_consistency(device_id, payload.get("device_id"))

                cached = self._load_response_cache(topic_type=topic_type, device_id=device_id, msg_id=msg_id)
                if cached:
                    self._publish_response(device_id, topic_type, cached)
                    return

                if topic_type == "check_request":
                    response = self._handle_check_request(device_id=device_id, payload=payload)
                elif topic_type == "progress_report":
                    response = self._handle_progress_report(device_id=device_id, payload=payload)
                elif topic_type == "result_report":
                    response = self._handle_result_report(device_id=device_id, payload=payload)
                else:
                    raise ValueError(f"Unsupported topic type: {topic_type}")

                self._save_response_cache(
                    topic_type=topic_type,
                    device_id=device_id,
                    msg_id=msg_id,
                    response=response,
                )
                self._publish_response(device_id, topic_type, response)
            except Exception as exc:
                LOGGER.exception("Failed to process MQTT message topic=%s", topic)
                response = self._build_error_response(
                    payload_text=payload_text,
                    device_id_from_topic=self._device_id_from_topic_safe(topic),
                    error=exc,
                )
                response_topic_type, response_device_id = self._infer_error_response_topic(topic, response)
                self._publish_response(response_device_id, response_topic_type, response)

    def _handle_check_request(self, device_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        self._validate_required_fields(payload, ["msg_id", "device_id", "sn", "model"])
        try:
            tasks = upgrade_service.check_upgrade_task(
                device_id=device_id,
                sn=payload["sn"],
                model=payload["model"],
                module_versions=payload.get("module_versions"),
            )
        except ResourceNotFoundError:
            # Device is not registered in RMS: treat as "no update task" for IoDs.
            return {
                "msg_id": payload["msg_id"],
                "device_id": device_id,
                "success": True,
                "code": 404,
                "message": "no_task",
                "tasks": [],
            }

        if not tasks:
            return {
                "msg_id": payload["msg_id"],
                "device_id": device_id,
                "success": True,
                "code": 404,
                "message": "no_task",
                "tasks": [],
            }

        return {
            "msg_id": payload["msg_id"],
            "device_id": device_id,
            "success": True,
            "code": "OK",
            "message": "success",
            "tasks": tasks,
        }

    def _handle_progress_report(self, device_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        self._validate_required_fields(
            payload,
            ["msg_id", "task_id", "device_id", "module_type", "sn", "model"],
        )
        upgrade_service.update_device_task_status(
            task_id=payload["task_id"],
            device_id=device_id,
            status="active",
        )
        return {
            "msg_id": payload["msg_id"],
            "device_id": device_id,
            "task_id": payload["task_id"],
            "module_type": payload["module_type"],
            "success": True,
            "code": "OK",
            "message": "progress accepted",
        }

    def _handle_result_report(self, device_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        self._validate_required_fields(
            payload,
            ["msg_id", "task_id", "device_id", "module_type", "sn", "model"],
        )
        result = upgrade_service.report_upgrade_result(payload)
        return {
            "msg_id": payload["msg_id"],
            "device_id": device_id,
            "task_id": payload["task_id"],
            "module_type": payload["module_type"],
            "success": True,
            "code": "OK",
            "message": "duplicate" if result.get("duplicate") else "success",
            "duplicate": bool(result.get("duplicate")),
            "record_id": result.get("record_id"),
            "task_summary": result.get("task_summary"),
        }

    def _build_error_response(
        self, payload_text: str, device_id_from_topic: Optional[str], error: Exception
    ) -> Dict[str, Any]:
        msg_id = None
        device_id = device_id_from_topic
        try:
            payload = self._parse_json(payload_text)
            msg_id = payload.get("msg_id")
            device_id = payload.get("device_id") or device_id
        except Exception:
            pass

        if isinstance(error, ApiException):
            code = f"API_{error.status_code}"
            message = error.message
        else:
            code = "INTERNAL_ERROR"
            message = str(error)

        return {
            "msg_id": msg_id,
            "device_id": device_id,
            "success": False,
            "code": code,
            "message": message,
        }

    def _publish_response(self, device_id: Optional[str], request_type: str, response: Dict[str, Any]) -> None:
        safe_device_id = device_id or "unknown"
        topic = self._response_topic(safe_device_id, request_type)
        payload = json.dumps(response, ensure_ascii=False)
        qos = int(self.app.config.get("MQTT_UPGRADE_QOS", 1))
        self.client.publish(topic, payload=payload, qos=qos)
        LOGGER.info("Published response topic=%s payload=%s", topic, payload)

    def _response_topic(self, device_id: str, request_type: str) -> str:
        if request_type == "check_request":
            return f"iods/{device_id}/upgrade/check/response"
        if request_type == "progress_report":
            return f"iods/{device_id}/upgrade/progress/response"
        if request_type == "result_report":
            return f"iods/{device_id}/upgrade/result/response"
        return f"iods/{device_id}/upgrade/unknown/response"

    def _get_subscribe_topics(self) -> Tuple[str, ...]:
        raw = self.app.config.get(
            "MQTT_UPGRADE_SUBSCRIBE_TOPICS",
            "iods/+/upgrade/check/request,iods/+/upgrade/progress/report,iods/+/upgrade/result/report",
        )
        topics = [item.strip() for item in str(raw).split(",") if item.strip()]
        return tuple(topics)

    def _parse_topic(self, topic: str) -> Tuple[str, str]:
        parts = topic.split("/")
        if len(parts) != 5 or parts[0] != "iods" or parts[2] != "upgrade":
            raise ValueError(f"Unsupported topic: {topic}")
        device_id = parts[1]
        key = f"{parts[3]}/{parts[4]}"
        mapping = {
            "check/request": "check_request",
            "progress/report": "progress_report",
            "result/report": "result_report",
        }
        topic_type = mapping.get(key)
        if not topic_type:
            raise ValueError(f"Unsupported topic action: {topic}")
        return topic_type, device_id

    def _infer_error_response_topic(
        self, topic: str, response: Dict[str, Any]
    ) -> Tuple[str, Optional[str]]:
        device_id = response.get("device_id") or self._device_id_from_topic_safe(topic)
        try:
            topic_type, _ = self._parse_topic(topic)
            return topic_type, device_id
        except Exception:
            return "check_request", device_id

    def _device_id_from_topic_safe(self, topic: str) -> Optional[str]:
        parts = topic.split("/")
        if len(parts) >= 2 and parts[0] == "iods":
            return parts[1]
        return None

    def _parse_json(self, text: str) -> Dict[str, Any]:
        payload = json.loads(text)
        if not isinstance(payload, dict):
            raise ValueError("Payload must be a JSON object")
        return payload

    def _decode_payload(self, raw: Any) -> str:
        if isinstance(raw, (bytes, bytearray)):
            return raw.decode("utf-8")
        return str(raw)

    def _validate_required_fields(self, payload: Dict[str, Any], fields: list) -> None:
        missing = [key for key in fields if not payload.get(key)]
        if missing:
            raise ValueError(f"Missing required fields: {', '.join(missing)}")

    def _validate_device_id_consistency(
        self, device_id_in_topic: str, device_id_in_payload: Optional[str]
    ) -> None:
        if not device_id_in_payload:
            return
        if device_id_in_topic != device_id_in_payload:
            raise ValueError(
                f"Device ID mismatch topic='{device_id_in_topic}' payload='{device_id_in_payload}'"
            )

    def _response_cache_key(self, topic_type: str, device_id: str, msg_id: str) -> str:
        return f"iods:mqtt:response:{topic_type}:{device_id}:{msg_id}"

    def _resolve_client_id(self) -> str:
        configured = str(self.app.config.get("MQTT_CLIENT_ID", "") or "").strip()
        default_id = "rms-mqtt-upgrade-adapter"
        if configured and configured != default_id:
            return configured

        host = socket.gethostname().replace(" ", "_")
        pid = os.getpid()
        return f"{default_id}-{host}-{pid}"

    def _save_response_cache(
        self, topic_type: str, device_id: str, msg_id: str, response: Dict[str, Any]
    ) -> None:
        if redis_client is None:
            return
        try:
            key = self._response_cache_key(topic_type, device_id, msg_id)
            redis_client.setex(
                key,
                self.RESPONSE_CACHE_TTL_SECONDS,
                json.dumps(response, ensure_ascii=False),
            )
        except Exception:
            return

    def _load_response_cache(
        self, topic_type: str, device_id: str, msg_id: str
    ) -> Optional[Dict[str, Any]]:
        if redis_client is None:
            return None
        try:
            key = self._response_cache_key(topic_type, device_id, msg_id)
            value = redis_client.get(key)
            if not value:
                return None
            cached = json.loads(value)
            if isinstance(cached, dict):
                return cached
            return None
        except Exception:
            return None
