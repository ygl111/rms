#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Capacity test: ramp up DP v1 device concurrency until timeout appears."""
"""python concurrent_device_capacity_test.py --host 183.169.121.226 --port 8081 --start-device 1 --max-devices 10000 --step 100 --handshake-concurrency 15 --response-timeout 20 --timeout-grace-seconds 0.1 --heartbeat-interval 60 --stage-observe-seconds 70 --device-model RK3568-Pro --log-level INFO"""

import argparse
import asyncio
import logging
import random
import struct
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

LOG = logging.getLogger("capacity_test")

CRC16_TABLE = [
    0x0000, 0x1189, 0x2312, 0x329B, 0x4624, 0x57AD, 0x6536, 0x74BF,
    0x8C48, 0x9DC1, 0xAF5A, 0xBED3, 0xCA6C, 0xDBE5, 0xE97E, 0xF8F7,
    0x1081, 0x0108, 0x3393, 0x221A, 0x56A5, 0x472C, 0x75B7, 0x643E,
    0x9CC9, 0x8D40, 0xBFDB, 0xAE52, 0xDAED, 0xCB64, 0xF9FF, 0xE876,
    0x2102, 0x308B, 0x0210, 0x1399, 0x6726, 0x76AF, 0x4434, 0x55BD,
    0xAD4A, 0xBCC3, 0x8E58, 0x9FD1, 0xEB6E, 0xFAE7, 0xC87C, 0xD9F5,
    0x3183, 0x200A, 0x1291, 0x0318, 0x77A7, 0x662E, 0x54B5, 0x453C,
    0xBDCB, 0xAC42, 0x9ED9, 0x8F50, 0xFBEF, 0xEA66, 0xD8FD, 0xC974,
    0x4204, 0x538D, 0x6116, 0x709F, 0x0420, 0x15A9, 0x2732, 0x36BB,
    0xCE4C, 0xDFC5, 0xED5E, 0xFCD7, 0x8868, 0x99E1, 0xAB7A, 0xBAF3,
    0x5285, 0x430C, 0x7197, 0x601E, 0x14A1, 0x0528, 0x37B3, 0x263A,
    0xDECD, 0xCF44, 0xFDDF, 0xEC56, 0x98E9, 0x8960, 0xBBFB, 0xAA72,
    0x6306, 0x728F, 0x4014, 0x519D, 0x2522, 0x34AB, 0x0630, 0x17B9,
    0xEF4E, 0xFEC7, 0xCC5C, 0xDDD5, 0xA96A, 0xB8E3, 0x8A78, 0x9BF1,
    0x7387, 0x620E, 0x5095, 0x411C, 0x35A3, 0x242A, 0x16B1, 0x0738,
    0xFFCF, 0xEE46, 0xDCDD, 0xCD54, 0xB9EB, 0xA862, 0x9AF9, 0x8B70,
    0x8408, 0x9581, 0xA71A, 0xB693, 0xC22C, 0xD3A5, 0xE13E, 0xF0B7,
    0x0840, 0x19C9, 0x2B52, 0x3ADB, 0x4E64, 0x5FED, 0x6D76, 0x7CFF,
    0x9489, 0x8500, 0xB79B, 0xA612, 0xD2AD, 0xC324, 0xF1BF, 0xE036,
    0x18C1, 0x0948, 0x3BD3, 0x2A5A, 0x5EE5, 0x4F6C, 0x7DF7, 0x6C7E,
    0xA50A, 0xB483, 0x8618, 0x9791, 0xE32E, 0xF2A7, 0xC03C, 0xD1B5,
    0x2942, 0x38CB, 0x0A50, 0x1BD9, 0x6F66, 0x7EEF, 0x4C74, 0x5DFD,
    0xB58B, 0xA402, 0x9699, 0x8710, 0xF3AF, 0xE226, 0xD0BD, 0xC134,
    0x39C3, 0x284A, 0x1AD1, 0x0B58, 0x7FE7, 0x6E6E, 0x5CF5, 0x4D7C,
    0xC60C, 0xD785, 0xE51E, 0xF497, 0x8028, 0x91A1, 0xA33A, 0xB2B3,
    0x4A44, 0x5BCD, 0x6956, 0x78DF, 0x0C60, 0x1DE9, 0x2F72, 0x3EFB,
    0xD68D, 0xC704, 0xF59F, 0xE416, 0x90A9, 0x8120, 0xB3BB, 0xA232,
    0x5AC5, 0x4B4C, 0x79D7, 0x685E, 0x1CE1, 0x0D68, 0x3FF3, 0x2E7A,
    0xE70E, 0xF687, 0xC41C, 0xD595, 0xA12A, 0xB0A3, 0x8238, 0x93B1,
    0x6B46, 0x7ACF, 0x4854, 0x59DD, 0x2D62, 0x3CEB, 0x0E70, 0x1FF9,
    0xF78F, 0xE606, 0xD49D, 0xC514, 0xB1AB, 0xA022, 0x92B9, 0x8330,
    0x7BC7, 0x6A4E, 0x58D5, 0x495C, 0x3DE3, 0x2C6A, 0x1EF1, 0x0F78,
]


@dataclass
class DeviceConfig:
    device_id: str
    device_model: str = "RK3568-Pro"
    manufacturer: str = "TestDevice"
    device_type: int = 1
    firmware_version: str = "1.0.0"
    hardware_version: str = "1.0"


@dataclass
class RuntimeConfig:
    host: str
    port: int
    max_devices: int = 10000
    start_device: int = 1
    step: int = 50
    response_timeout: float = 20.0
    connect_timeout: float = 5.0
    timeout_grace_seconds: float = 0.05
    handshake_concurrency: int = 20
    heartbeat_interval: float = 60.0
    heartbeat_jitter: float = 10.0
    banknote_interval_min: float = 60.0
    banknote_interval_max: float = 120.0
    banknote_jitter: float = 10.0
    fault_interval_min: float = 900.0
    fault_interval_max: float = 1800.0
    fault_jitter: float = 30.0
    stage_observe_seconds: float = 70.0
    ramp_pause_seconds: float = 1.0
    device_model: str = "RK3568-Pro"
    log_progress_every: float = 10.0


@dataclass
class GlobalStats:
    total_sent: int = 0
    total_acked: int = 0
    total_timeout: int = 0
    total_connect_fail: int = 0
    timeout_device_id: str = ""
    timeout_phase: str = ""
    timeout_detail: str = ""


class DPv1MessageBuilder:
    MSG_HEAD = 0x5555
    MSG_TYPE = 0x03

    def __init__(self, device_id: str):
        encoded = device_id.encode("ascii", errors="ignore")
        self.device_id = encoded[:24].ljust(24, b"\x00")
        self.seq_num = 0

    def _next_seq(self) -> int:
        self.seq_num = (self.seq_num + 1) % 65536
        return self.seq_num

    def _build_header(self, msg_id: int, body_len: int, msg_attribute: int = 0) -> bytes:
        seq = self._next_seq()
        header = struct.pack(
            "<HBHBH",
            self.MSG_HEAD,
            self.MSG_TYPE,
            body_len,
            msg_attribute & 0xFF,
            msg_id & 0xFFFF,
        )
        header += self.device_id
        header += struct.pack("<H", seq)
        return header

    @staticmethod
    def _crc16(data: bytes) -> int:
        crc = 0xFFFF
        for byte in data:
            crc = ((crc >> 8) ^ CRC16_TABLE[(crc ^ byte) & 0xFF]) & 0xFFFF
        return (~crc) & 0xFFFF

    @staticmethod
    def _tail(packet_without_tail: bytes) -> bytes:
        crc = DPv1MessageBuilder._crc16(packet_without_tail)
        return struct.pack("<HH", crc, 0xAAAA)

    @staticmethod
    def _ascii_fixed(value: str, size: int) -> bytes:
        return value.encode("utf-8", errors="ignore")[:size].ljust(size, b"\x00")

    @staticmethod
    def _bcd_time_now_utc() -> bytes:
        now = datetime.now(timezone.utc)
        values = [now.year % 100, now.month, now.day, now.hour, now.minute, now.second]
        out = bytearray()
        for v in values:
            out.append(((v // 10) << 4) | (v % 10))
        return bytes(out)

    def build_registration(self, config: DeviceConfig) -> bytes:
        manufacturer = self._ascii_fixed(config.manufacturer, 16)
        branch = b"SimBranch"
        device_model = self._ascii_fixed(config.device_model, 16)
        suffix_flag = self._ascii_fixed("SUFFIX01", 8)
        firmware_version = self._ascii_fixed(config.firmware_version, 32)
        hardware_version = self._ascii_fixed(config.hardware_version, 5)
        main_soft = self._ascii_fixed(config.firmware_version, 11)
        currency_db = self._ascii_fixed("CurrDB1.0", 10)
        body = struct.pack(
            "<16sB10sB16s8s32sB5sH11sH10s",
            manufacturer,
            len(branch),
            branch,
            config.device_type & 0xFF,
            device_model,
            suffix_flag,
            firmware_version,
            len(hardware_version),
            hardware_version,
            len(main_soft),
            main_soft,
            len(currency_db),
            currency_db,
        )
        packet = self._build_header(2, len(body)) + body
        return packet + self._tail(packet)

    def build_login(self, auth_code: bytes) -> bytes:
        auth = (auth_code or b"")[:16].ljust(16, b"\x00")
        body = struct.pack("<16s", auth)
        packet = self._build_header(3, len(body)) + body
        return packet + self._tail(packet)

    def build_heartbeat(self, maintenance_threshold: int = 0xFFFFFFFF) -> bytes:
        body = struct.pack("<I", maintenance_threshold & 0xFFFFFFFF)
        packet = self._build_header(4, len(body)) + body
        return packet + self._tail(packet)

    def build_fault_report(self, event_level: int, event_code: int, event_content: str) -> bytes:
        event_time_bcd = self._bcd_time_now_utc()
        content_bytes = event_content.encode("utf-8", errors="ignore")
        body = struct.pack("<BH6sH", event_level & 0xFF, event_code & 0xFFFF, event_time_bcd, len(content_bytes))
        body += content_bytes
        packet = self._build_header(10, len(body)) + body
        return packet + self._tail(packet)

    def build_banknote_report(self, total_notes_count: int, denomination_cents: int, duration_ms: int, serial_prefix: str) -> bytes:
        count_time = self._bcd_time_now_utc()
        currency_symbol = b"CNY\x00"
        body = struct.pack(
            "<BBBBB6sIHB",
            0,
            0,
            1,
            1,
            1,
            count_time,
            duration_ms & 0xFFFFFFFF,
            total_notes_count & 0xFFFF,
            1,
        )
        total_amount_cents = total_notes_count * denomination_cents
        body += struct.pack("<4sHQ", currency_symbol, total_notes_count & 0xFFFF, total_amount_cents)

        # Realistic short detail set: only for first 3 notes to reduce payload size pressure.
        detail_notes = min(total_notes_count, 3)
        for idx in range(detail_notes):
            serial = f"{serial_prefix}{idx + 1:05d}".encode("ascii", errors="ignore")[:20].ljust(20, b"\x00")
            body += struct.pack("<4sIBBHB", currency_symbol, denomination_cents, 1, 0, 0, 0)
            body += struct.pack("<20sB", serial, 1)

        packet = self._build_header(12, len(body)) + body
        return packet + self._tail(packet)


class DeviceSession:
    def __init__(self, config: DeviceConfig, runtime: RuntimeConfig, stats: GlobalStats):
        self.cfg = config
        self.runtime = runtime
        self.stats = stats
        self.builder = DPv1MessageBuilder(config.device_id)
        self.reader: Optional[asyncio.StreamReader] = None
        self.writer: Optional[asyncio.StreamWriter] = None
        self.auth_code = b""
        self.connected = False
        self.last_timeout: str = ""

        now = time.monotonic()
        # Spread first schedules to avoid synchronized bursts when many sessions start together.
        self.next_heartbeat = now + random.uniform(0.0, runtime.heartbeat_interval)
        self.next_banknote = now + random.uniform(0.0, self._next_banknote_delay())
        self.next_fault = now + random.uniform(0.0, self._next_fault_delay())

    def _next_heartbeat_delay(self) -> float:
        jitter = random.uniform(-self.runtime.heartbeat_jitter, self.runtime.heartbeat_jitter)
        delay = self.runtime.heartbeat_interval + jitter
        return max(1.0, delay)

    def _next_banknote_delay(self) -> float:
        base = random.uniform(self.runtime.banknote_interval_min, self.runtime.banknote_interval_max)
        jitter = random.uniform(-self.runtime.banknote_jitter, self.runtime.banknote_jitter)
        return max(1.0, base + jitter)

    def _next_fault_delay(self) -> float:
        base = random.uniform(self.runtime.fault_interval_min, self.runtime.fault_interval_max)
        jitter = random.uniform(-self.runtime.fault_jitter, self.runtime.fault_jitter)
        return max(1.0, base + jitter)

    async def connect_and_handshake(self) -> bool:
        try:
            self.reader, self.writer = await asyncio.wait_for(
                asyncio.open_connection(self.runtime.host, self.runtime.port),
                timeout=self.runtime.connect_timeout,
            )
            ok, detail = await self._send_and_expect(self.builder.build_registration(self.cfg), "register")
            if not ok:
                self.last_timeout = detail or "register failed"
                await self.close()
                return False

            ok, detail = await self._send_and_expect(self.builder.build_login(self.auth_code), "login")
            if not ok:
                self.last_timeout = detail or "login failed"
                await self.close()
                return False

            self.connected = True
            return True
        except Exception as exc:  # pylint: disable=broad-except
            self.stats.total_connect_fail += 1
            self.last_timeout = f"connect/handshake failed: {exc}"
            await self.close()
            return False

    async def close(self) -> None:
        if self.writer is not None:
            try:
                self.writer.close()
                await self.writer.wait_closed()
            except Exception:
                pass
        self.connected = False

    async def run_once_due(self) -> Tuple[bool, str]:
        now = time.monotonic()
        if now >= self.next_heartbeat:
            ok, msg = await self.send_heartbeat()
            self.next_heartbeat = now + self._next_heartbeat_delay()
            if not ok:
                return False, msg
            return True, ""

        if now >= self.next_banknote:
            ok, msg = await self.send_banknote_report()
            self.next_banknote = now + self._next_banknote_delay()
            if not ok:
                return False, msg
            return True, ""

        if now >= self.next_fault:
            ok, msg = await self.send_fault_report()
            self.next_fault = now + self._next_fault_delay()
            if not ok:
                return False, msg
            return True, ""

        return True, ""

    async def send_heartbeat(self) -> Tuple[bool, str]:
        return await self._send_and_expect(self.builder.build_heartbeat(), "heartbeat", expect_auth=False)

    async def send_banknote_report(self) -> Tuple[bool, str]:
        note_count = random.randint(20, 120)
        denomination_cents = random.choice([1000, 2000, 5000, 10000])
        duration_ms = random.randint(4000, 25000)
        serial_prefix = self.cfg.device_id[-6:]
        pkt = self.builder.build_banknote_report(note_count, denomination_cents, duration_ms, serial_prefix)
        return await self._send_and_expect(pkt, "banknote", expect_auth=False)

    async def send_fault_report(self) -> Tuple[bool, str]:
        event_level = random.choice([1, 2, 3])
        event_code = random.choice([1001, 1002, 1103, 1205, 2001])
        content = random.choice([
            "motor warning",
            "sensor abnormal",
            "paper path blocked",
            "temporary jam",
            "cash box open",
        ])
        pkt = self.builder.build_fault_report(event_level, event_code, content)
        return await self._send_and_expect(pkt, "fault", expect_auth=False)

    async def _send_and_expect(self, packet: bytes, phase: str, expect_auth: bool = False) -> Tuple[bool, str]:
        if self.writer is None or self.reader is None:
            return False, "socket not ready"

        try:
            start = time.monotonic()
            self.writer.write(packet)
            await self.writer.drain()
            self.stats.total_sent += 1

            raw = await asyncio.wait_for(self._recv_packet(), timeout=self.runtime.response_timeout)
            latency = time.monotonic() - start
            allowed_timeout = self.runtime.response_timeout + self.runtime.timeout_grace_seconds
            if latency > allowed_timeout:
                self.stats.total_timeout += 1
                return False, f"{phase} response latency {latency:.3f}s > {allowed_timeout:.3f}s"

            self.stats.total_acked += 1
            msg_id, body_len, _ = parse_packet_header_v1(raw)
            if phase == "register":
                if msg_id != 0x8002:
                    return False, f"register response msg_id=0x{msg_id:04X}"
                body = raw[34:34 + body_len]
                if len(body) < 3:
                    return False, "register response body too short"
                result = body[2]
                auth = body[3:3 + 16]
                if result not in (0x00, 0x01, 0x02):
                    return False, f"register result=0x{result:02X}"
                self.auth_code = auth.rstrip(b"\x00") if auth else b""
            elif phase == "login":
                if msg_id not in (0x8003, 0x8001):
                    return False, f"login response msg_id=0x{msg_id:04X}"
            return True, ""
        except asyncio.TimeoutError:
            self.stats.total_timeout += 1
            return False, f"{phase} wait response timeout > {self.runtime.response_timeout:.3f}s"
        except Exception as exc:  # pylint: disable=broad-except
            return False, f"{phase} exception: {exc}"

    async def _recv_packet(self) -> bytes:
        if self.reader is None:
            raise ConnectionError("reader not ready")
        header = await self.reader.readexactly(34)
        body_len = struct.unpack("<H", header[3:5])[0]
        body_and_tail = await self.reader.readexactly(body_len + 4)
        return header + body_and_tail


def parse_packet_header_v1(packet: bytes) -> Tuple[int, int, int]:
    body_len = struct.unpack("<H", packet[3:5])[0]
    msg_id = struct.unpack("<H", packet[6:8])[0]
    seq = struct.unpack("<H", packet[32:34])[0]
    return msg_id, body_len, seq


class CapacityRunner:
    def __init__(self, cfg: RuntimeConfig):
        self.cfg = cfg
        self.stats = GlobalStats()
        self.sessions: Dict[str, DeviceSession] = {}
        self.stop_due_to_timeout = False
        self.stable_concurrency = 0

    @staticmethod
    def _device_id_list(start: int, count: int) -> List[str]:
        return [f"DEV_{idx:06d}" for idx in range(start, start + count)]

    async def run(self) -> int:
        LOG.info("start capacity test host=%s port=%d", self.cfg.host, self.cfg.port)
        LOG.info("device range DEV_%06d..DEV_%06d model=%s", self.cfg.start_device, self.cfg.max_devices, self.cfg.device_model)
        LOG.info(
            "effective config step=%d observe=%.1fs timeout=%.1fs grace=%.3fs hs_conc=%d heartbeat=%.1fs jitter=%.1fs banknote=[%.1f, %.1f] jitter=%.1fs fault=[%.1f, %.1f] jitter=%.1fs",
            self.cfg.step,
            self.cfg.stage_observe_seconds,
            self.cfg.response_timeout,
            self.cfg.timeout_grace_seconds,
            self.cfg.handshake_concurrency,
            self.cfg.heartbeat_interval,
            self.cfg.heartbeat_jitter,
            self.cfg.banknote_interval_min,
            self.cfg.banknote_interval_max,
            self.cfg.banknote_jitter,
            self.cfg.fault_interval_min,
            self.cfg.fault_interval_max,
            self.cfg.fault_jitter,
        )
        target = self.cfg.start_device
        last_log = time.monotonic()

        while len(self.sessions) < self.cfg.max_devices:
            remain = self.cfg.max_devices - len(self.sessions)
            add_count = min(self.cfg.step, remain)
            ids = self._device_id_list(target, add_count)
            target += add_count

            LOG.info("ramp: trying add=%d current=%d", add_count, len(self.sessions))
            add_ok = await self._add_sessions(ids)
            if not add_ok:
                self.stop_due_to_timeout = True
                break

            stable = await self._observe_current_stage()
            if not stable:
                self.stop_due_to_timeout = True
                break

            self.stable_concurrency = len(self.sessions)
            LOG.info("stage stable at concurrency=%d", self.stable_concurrency)

            now = time.monotonic()
            if now - last_log >= self.cfg.log_progress_every:
                LOG.info(
                    "progress current=%d sent=%d acked=%d timeout=%d conn_fail=%d",
                    len(self.sessions),
                    self.stats.total_sent,
                    self.stats.total_acked,
                    self.stats.total_timeout,
                    self.stats.total_connect_fail,
                )
                last_log = now

            await asyncio.sleep(self.cfg.ramp_pause_seconds)

        await self._close_all()

        LOG.info("test finished stable_concurrency=%d", self.stable_concurrency)
        if self.stop_due_to_timeout:
            LOG.warning(
                "stop reason timeout device=%s phase=%s detail=%s",
                self.stats.timeout_device_id,
                self.stats.timeout_phase,
                self.stats.timeout_detail,
            )
        LOG.info(
            "stats sent=%d acked=%d timeout=%d connect_fail=%d",
            self.stats.total_sent,
            self.stats.total_acked,
            self.stats.total_timeout,
            self.stats.total_connect_fail,
        )
        return self.stable_concurrency

    async def _add_sessions(self, ids: List[str]) -> bool:
        tasks = []
        sem = asyncio.Semaphore(self.cfg.handshake_concurrency)

        async def _connect_with_limit(sess: DeviceSession) -> bool:
            async with sem:
                return await sess.connect_and_handshake()

        for dev_id in ids:
            sess = DeviceSession(DeviceConfig(device_id=dev_id, device_model=self.cfg.device_model), self.cfg, self.stats)
            tasks.append(asyncio.create_task(_connect_with_limit(sess)))
            self.sessions[dev_id] = sess

        results = await asyncio.gather(*tasks, return_exceptions=True)
        for idx, res in enumerate(results):
            dev_id = ids[idx]
            ok = bool(res) and not isinstance(res, Exception)
            if not ok:
                detail = str(res) if isinstance(res, Exception) else self.sessions[dev_id].last_timeout
                self.stats.timeout_device_id = dev_id
                self.stats.timeout_phase = "connect_handshake"
                self.stats.timeout_detail = detail or "connect/handshake failed"
                await self._remove_session(dev_id)
                return False
        return True

    async def _observe_current_stage(self) -> bool:
        end_time = time.monotonic() + self.cfg.stage_observe_seconds
        while time.monotonic() < end_time:
            session_items = list(self.sessions.items())
            tasks = [asyncio.create_task(sess.run_once_due()) for _, sess in session_items]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            for (dev_id, _), result in zip(session_items, results):
                if isinstance(result, Exception):
                    self.stats.timeout_device_id = dev_id
                    self.stats.timeout_phase = "runtime"
                    self.stats.timeout_detail = f"runtime exception: {result}"
                    return False

                ok, detail = result
                if not ok:
                    self.stats.timeout_device_id = dev_id
                    self.stats.timeout_phase = "runtime"
                    self.stats.timeout_detail = detail
                    return False
            await asyncio.sleep(0.05)
        return True

    async def _remove_session(self, dev_id: str) -> None:
        sess = self.sessions.pop(dev_id, None)
        if sess is not None:
            await sess.close()

    async def _close_all(self) -> None:
        if not self.sessions:
            return
        tasks = [asyncio.create_task(sess.close()) for sess in self.sessions.values()]
        await asyncio.gather(*tasks, return_exceptions=True)
        self.sessions.clear()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Concurrent capacity test for DP v1 devices")
    parser.add_argument("--host", required=True, help="Server host")
    parser.add_argument("--port", type=int, required=True, help="Server port")

    parser.add_argument("--start-device", type=int, default=1, help="Start ID number, default 1 -> DEV_000001")
    parser.add_argument("--max-devices", type=int, default=10000, help="Max device count, default 10000 -> DEV_010000")
    parser.add_argument("--step", type=int, default=50, help="How many devices to add each stage")

    parser.add_argument("--response-timeout", type=float, default=20.0, help="Response timeout seconds")
    parser.add_argument("--connect-timeout", type=float, default=5.0, help="Connect timeout seconds")
    parser.add_argument("--timeout-grace-seconds", type=float, default=0.05, help="Extra timeout grace seconds")
    parser.add_argument("--handshake-concurrency", type=int, default=20, help="Concurrent handshakes per ramp stage")
    parser.add_argument("--stage-observe-seconds", type=float, default=70.0, help="Observe duration after each ramp stage")
    parser.add_argument("--ramp-pause-seconds", type=float, default=1.0, help="Pause seconds between stages")

    parser.add_argument("--heartbeat-interval", type=float, default=60.0, help="Heartbeat interval seconds")
    parser.add_argument("--heartbeat-jitter", type=float, default=5.0, help="Heartbeat jitter range in seconds (+/-)")
    parser.add_argument("--banknote-interval-min", type=float, default=60.0, help="Banknote interval min seconds")
    parser.add_argument("--banknote-interval-max", type=float, default=120.0, help="Banknote interval max seconds")
    parser.add_argument("--banknote-jitter", type=float, default=10.0, help="Banknote jitter range in seconds (+/-)")
    parser.add_argument("--fault-interval-min", type=float, default=900.0, help="Fault interval min seconds")
    parser.add_argument("--fault-interval-max", type=float, default=1800.0, help="Fault interval max seconds")
    parser.add_argument("--fault-jitter", type=float, default=30.0, help="Fault jitter range in seconds (+/-)")

    parser.add_argument("--device-model", default="RK3568-Pro", help="Device model")
    parser.add_argument("--log-level", default="INFO", help="Log level")
    return parser.parse_args()


def build_runtime_config(args: argparse.Namespace) -> RuntimeConfig:
    if args.start_device < 1 or args.start_device > 10000:
        raise ValueError("--start-device must be in [1, 10000]")
    if args.max_devices < args.start_device or args.max_devices > 10000:
        raise ValueError("--max-devices must be in [start-device, 10000]")
    if args.step <= 0:
        raise ValueError("--step must be > 0")
    if args.stage_observe_seconds <= 0:
        raise ValueError("--stage-observe-seconds must be > 0")
    if args.timeout_grace_seconds < 0:
        raise ValueError("--timeout-grace-seconds must be >= 0")
    if args.handshake_concurrency <= 0:
        raise ValueError("--handshake-concurrency must be > 0")
    if args.heartbeat_interval <= 0:
        raise ValueError("--heartbeat-interval must be > 0")
    if args.heartbeat_jitter < 0:
        raise ValueError("--heartbeat-jitter must be >= 0")
    if args.banknote_jitter < 0:
        raise ValueError("--banknote-jitter must be >= 0")
    if args.fault_jitter < 0:
        raise ValueError("--fault-jitter must be >= 0")
    if args.banknote_interval_min <= 0 or args.banknote_interval_max < args.banknote_interval_min:
        raise ValueError("banknote interval range invalid")
    if args.fault_interval_min <= 0 or args.fault_interval_max < args.fault_interval_min:
        raise ValueError("fault interval range invalid")

    return RuntimeConfig(
        host=args.host,
        port=args.port,
        max_devices=args.max_devices,
        start_device=args.start_device,
        step=args.step,
        response_timeout=args.response_timeout,
        connect_timeout=args.connect_timeout,
        timeout_grace_seconds=args.timeout_grace_seconds,
        handshake_concurrency=args.handshake_concurrency,
        heartbeat_interval=args.heartbeat_interval,
        heartbeat_jitter=args.heartbeat_jitter,
        banknote_interval_min=args.banknote_interval_min,
        banknote_interval_max=args.banknote_interval_max,
        banknote_jitter=args.banknote_jitter,
        fault_interval_min=args.fault_interval_min,
        fault_interval_max=args.fault_interval_max,
        fault_jitter=args.fault_jitter,
        stage_observe_seconds=args.stage_observe_seconds,
        ramp_pause_seconds=args.ramp_pause_seconds,
        device_model=args.device_model,
    )


def main() -> int:
    args = parse_args()
    logging.basicConfig(
        level=getattr(logging, args.log_level.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    try:
        cfg = build_runtime_config(args)
    except ValueError as exc:
        LOG.error("invalid arguments: %s", exc)
        return 2

    start = time.time()
    try:
        stable_concurrency = asyncio.run(CapacityRunner(cfg).run())
    except KeyboardInterrupt:
        LOG.warning("interrupted by user")
        return 130

    elapsed = time.time() - start
    print("\n=== CAPACITY TEST RESULT ===")
    print(f"stable_concurrency={stable_concurrency}")
    print(f"elapsed_seconds={elapsed:.2f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


