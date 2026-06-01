#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Simulate device registration/login and periodic heartbeat (v1)."""

import argparse
import errno
import logging
import socket
import struct
import time
from dataclasses import dataclass
from typing import Optional, Tuple

LOG = logging.getLogger("heartbeat_sim_v1")

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
    device_model: str
    manufacturer: str = "TestDevice"
    device_type: int = 1
    firmware_version: str = "1.0.0"
    hardware_version: str = "1.0"


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

        header = self._build_header(2, len(body))
        packet = header + body
        return packet + self._tail(packet)

    def build_login(self, auth_code: bytes) -> bytes:
        auth = (auth_code or b"")[:16].ljust(16, b"\x00")
        body = struct.pack("<16s", auth)
        header = self._build_header(3, len(body))
        packet = header + body
        return packet + self._tail(packet)

    def build_heartbeat(self, maintenance_threshold: int = 0xFFFFFFFF) -> bytes:
        body = struct.pack("<I", maintenance_threshold & 0xFFFFFFFF)
        header = self._build_header(4, len(body))
        packet = header + body
        return packet + self._tail(packet)


def recv_exact(sock: socket.socket, size: int) -> bytes:
    data = bytearray()
    while len(data) < size:
        chunk = sock.recv(size - len(data))
        if not chunk:
            raise ConnectionError("socket closed while receiving data")
        data.extend(chunk)
    return bytes(data)


def receive_dp_packet_v1(sock: socket.socket, timeout: float) -> Optional[bytes]:
    sock.settimeout(timeout)
    try:
        header = recv_exact(sock, 34)
        msg_head = struct.unpack("<H", header[0:2])[0]
        body_len = struct.unpack("<H", header[3:5])[0]
        msg_id = struct.unpack("<H", header[6:8])[0]
        if msg_head != 0x5555:
            LOG.warning("unexpected msg_head=0x%04X", msg_head)
        packet = header + recv_exact(sock, body_len + 4)
        LOG.debug("recv msg_id=0x%04X len=%d", msg_id, len(packet))
        return packet
    except (socket.timeout, ConnectionError, OSError) as exc:
        if isinstance(exc, OSError):
            interrupted = {getattr(errno, "EINTR", 4), getattr(errno, "WSAEINTR", 10004)}
            if exc.errno in interrupted:
                raise KeyboardInterrupt
        return None


def parse_packet_header_v1(packet: bytes) -> Tuple[int, int, int]:
    body_len = struct.unpack("<H", packet[3:5])[0]
    msg_id = struct.unpack("<H", packet[6:8])[0]
    seq = struct.unpack("<H", packet[32:34])[0]
    return msg_id, body_len, seq


def parse_registration_response_v1(packet: Optional[bytes]) -> Optional[bytes]:
    if not packet or len(packet) < 38:
        return None
    msg_id, body_len, _ = parse_packet_header_v1(packet)
    if msg_id != 0x8002:
        LOG.warning("registration response msg_id unexpected: 0x%04X", msg_id)
        return None
    body = packet[34:34 + body_len]
    if len(body) < 3:
        return None
    result = body[2]
    auth_code = body[3:3 + 16]
    LOG.info("registration response result=0x%02X", result)
    if result in (0x00, 0x01, 0x02):
        return auth_code.rstrip(b"\x00") if auth_code else b""
    return None


def log_response(packet: Optional[bytes], label: str) -> None:
    if not packet:
        LOG.info("%s: no response", label)
        return
    msg_id, body_len, seq = parse_packet_header_v1(packet)
    LOG.info("%s: msg_id=0x%04X seq=%d body_len=%d", label, msg_id, seq, body_len)


def run(args: argparse.Namespace) -> int:
    config = DeviceConfig(
        device_id=args.device_id,
        device_model=args.device_model,
        manufacturer=args.manufacturer,
        device_type=args.device_type,
        firmware_version=args.firmware_version,
        hardware_version=args.hardware_version,
    )

    builder = DPv1MessageBuilder(config.device_id)

    with socket.create_connection((args.host, args.port), timeout=args.timeout) as sock:
        LOG.info("connected to %s:%s", args.host, args.port)

        reg_packet = builder.build_registration(config)
        sock.sendall(reg_packet)
        auth_code = parse_registration_response_v1(receive_dp_packet_v1(sock, args.timeout))
        if auth_code is None:
            auth_code = b""
        LOG.info("auth_code=%s", auth_code.hex() if auth_code else "<empty>")

        time.sleep(args.step_delay)

        login_packet = builder.build_login(auth_code)
        sock.sendall(login_packet)
        log_response(receive_dp_packet_v1(sock, args.timeout), "login")

        while True:
            time.sleep(args.heartbeat_interval)
            hb_packet = builder.build_heartbeat()
            sock.sendall(hb_packet)
            log_response(receive_dp_packet_v1(sock, args.timeout), "heartbeat")

    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Simulate v1 register/login + periodic heartbeat")
    parser.add_argument("--host", default="127.0.0.1", help="TCP gateway host")
    parser.add_argument("--port", type=int, default=9000, help="TCP gateway port")
    parser.add_argument("--device-id", default="SIM_DEVICE_001", help="Device ID (devUniqueId)")
    parser.add_argument("--device-model", default="MODEL_A", help="Device model")
    parser.add_argument("--manufacturer", default="TestDevice", help="Manufacturer")
    parser.add_argument("--device-type", type=int, default=1, help="Device type")
    parser.add_argument("--firmware-version", default="1.0.0", help="Firmware version")
    parser.add_argument("--hardware-version", default="1.0", help="Hardware version")
    parser.add_argument("--heartbeat-interval", type=float, default=10.0, help="Heartbeat interval (seconds)")
    parser.add_argument("--timeout", type=float, default=5.0, help="Socket timeout (seconds)")
    parser.add_argument("--step-delay", type=float, default=0.5, help="Delay between steps (seconds)")
    parser.add_argument("--log-level", default="INFO", help="Log level")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(message)s",
    )

    try:
        return run(args)
    except KeyboardInterrupt:
        LOG.info("interrupted")
        return 130
    except Exception as exc:  # pylint: disable=broad-except
        LOG.error("failed: %s", exc)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
