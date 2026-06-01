#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
增强版金融设备TCP通信仿真器
支持从数据库加载测试设备进行注册和性能测试
"""

import socket
import struct
import time
import random
import threading
import json
import hashlib
import os
import pymysql
from typing import Dict, List, Optional, Tuple, Union
from dataclasses import dataclass, asdict
from enum import Enum
from datetime import datetime
import logging
import queue
from contextlib import contextmanager

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

logger = logging.getLogger('EnhancedDeviceSimulator')


class ConnectionPool:
    """TCP连接池，用于复用连接提高性能"""
    
    def __init__(self, host: str, port: int, max_connections: int = 100):
        self.host = host
        self.port = port
        self.max_connections = max_connections
        self.pool = queue.Queue(maxsize=max_connections)
        self.active_connections = 0
        self.lock = threading.Lock()
        self.stats = {
            'created': 0,
            'reused': 0,
            'released': 0,
            'errors': 0
        }
    
    def _create_connection(self) -> Optional[socket.socket]:
        """创建新的TCP连接"""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            # 优化socket配置
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 524288)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 524288)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
            
            sock.settimeout(5.0)  # 连接超时
            sock.connect((self.host, self.port))
            sock.settimeout(8.0)  # 读写超时
            
            with self.lock:
                self.active_connections += 1
                self.stats['created'] += 1
            
            logger.debug(f"创建新连接到 {self.host}:{self.port}")
            return sock
            
        except Exception as e:
            with self.lock:
                self.stats['errors'] += 1
            logger.error(f"创建连接失败: {e}")
            return None
    
    def get_connection(self) -> Optional[socket.socket]:
        """从池中获取连接"""
        try:
            # 尝试从池中获取现有连接
            connection = self.pool.get_nowait()
            # 检查连接是否仍然有效
            try:
                # 使用MSG_PEEK检查连接状态，不会消费数据
                connection.recv(1, socket.MSG_PEEK | socket.MSG_DONTWAIT)
            except (socket.error, BlockingIOError):
                pass  # 连接正常
            
            with self.lock:
                self.stats['reused'] += 1
            
            logger.debug("重用池中连接")
            return connection
            
        except queue.Empty:
            # 池中没有连接，创建新连接
            return self._create_connection()
    
    def return_connection(self, connection: socket.socket):
        """将连接返回到池中"""
        try:
            if connection and not connection._closed:
                self.pool.put_nowait(connection)
                with self.lock:
                    self.stats['released'] += 1
                logger.debug("连接已返回到池中")
            else:
                self._close_connection(connection)
                
        except queue.Full:
            # 池已满，直接关闭连接
            self._close_connection(connection)
    
    def _close_connection(self, connection: socket.socket):
        """关闭连接"""
        try:
            if connection:
                connection.close()
                with self.lock:
                    self.active_connections -= 1
                logger.debug("连接已关闭")
        except Exception:
            pass
    
    @contextmanager
    def get_connection_context(self):
        """连接上下文管理器"""
        connection = self.get_connection()
        if connection is None:
            raise ConnectionError("无法获取连接")
        
        try:
            yield connection
        finally:
            self.return_connection(connection)
    
    def close_all(self):
        """关闭所有连接"""
        while True:
            try:
                connection = self.pool.get_nowait()
                self._close_connection(connection)
            except queue.Empty:
                break
        
        logger.info(f"连接池关闭，统计: {self.stats}")


class MessageType(Enum):
    """消息类型枚举"""
    REGISTRATION = 2        # 终端注册
    AUTHENTICATION = 3      # 终端鉴权
    HEARTBEAT = 4          # 心跳
    UPGRADE_REQUEST = 5    # 升级请求
    UPGRADE_RESULT = 6     # 升级结果
    FAULT_REPORT = 10      # 故障上报
    BANKNOTE_REPORT = 12   # 点钞上报


@dataclass
class DeviceConfig:
    """设备配置"""
    device_id: str
    manufacturer: str = "TestDevice"
    device_type: int = 1
    device_model: str = "TD-2000"
    firmware_version: str = "1.0.0"
    hardware_version: str = "1.0"
    authentication_code: str = ""
    model_id: int = 1
    institution_id: str = ""
    description: str = ""


@dataclass
class ConnectionConfig:
    """连接配置"""
    host: str = "127.0.0.1"
    port: int = 8081
    timeout: int = 30
    reconnect_interval: int = 5
    max_reconnect_attempts: int = 10


@dataclass
class DatabaseConfig:
    """数据库配置"""
    host: str
    port: int
    user: str
    password: str
    database: str


class DeviceRepository:
    """设备数据仓库，负责从数据库加载设备信息"""
    
    def __init__(self, db_config: DatabaseConfig):
        self.db_config = db_config
        self.connection = None
    
    def connect(self) -> bool:
        """连接数据库"""
        try:
            self.connection = pymysql.connect(
                host=self.db_config.host,
                port=self.db_config.port,
                user=self.db_config.user,
                password=self.db_config.password,
                database=self.db_config.database,
                charset='utf8mb4',
                cursorclass=pymysql.cursors.DictCursor
            )
            return True
        except Exception as e:
            logger.error(f"数据库连接失败: {e}")
            return False
    
    def disconnect(self):
        """断开数据库连接"""
        if self.connection:
            self.connection.close()
            self.connection = None
    
    def load_test_devices(self, device_id_prefix: str = "PERF_TEST", limit: int = None) -> List[DeviceConfig]:
        """从数据库加载测试设备配置"""
        try:
            if not self.connection:
                if not self.connect():
                    return []
            
            with self.connection.cursor() as cursor:
                sql = """
                SELECT d.device_id, d.device_type, d.firmware_version, d.hardware_version,
                       d.main_software_version, d.authentication_code, d.model_id, 
                       d.institution_id, d.description, m.model_name
                FROM devices d
                LEFT JOIN device_mapping_model m ON d.model_id = m.id
                WHERE d.device_id LIKE %s AND d.is_deleted = 0
                ORDER BY d.device_id
                """
                
                if limit:
                    sql += f" LIMIT {limit}"
                
                cursor.execute(sql, (f"{device_id_prefix}_%",))
                rows = cursor.fetchall()
                
                devices = []
                for row in rows:
                    device_config = DeviceConfig(
                        device_id=row['device_id'],
                        manufacturer="TestDevice",
                        device_type=row['device_type'],
                        device_model=row['model_name'] or "TD-2000",
                        firmware_version=row['firmware_version'] or "1.0.0",
                        hardware_version=row['hardware_version'] or "1.0",
                        authentication_code=row['authentication_code'] or "",
                        model_id=row['model_id'],
                        institution_id=row['institution_id'] or "",
                        description=row['description'] or ""
                    )
                    devices.append(device_config)
                
                logger.info(f"从数据库加载了 {len(devices)} 个测试设备")
                return devices
                
        except Exception as e:
            logger.error(f"加载测试设备失败: {e}")
            return []
    
    def get_device_by_id(self, device_id: str) -> Optional[DeviceConfig]:
        """根据设备ID获取设备配置"""
        devices = self.load_test_devices()
        for device in devices:
            if device.device_id == device_id:
                return device
        return None
    
    def update_device_status(self, device_id: str, online_status: str) -> bool:
        """更新设备在线状态"""
        try:
            if not self.connection:
                if not self.connect():
                    logger.warning(f"数据库连接失败，跳过设备状态更新: {device_id}")
                    return False
            
            with self.connection.cursor() as cursor:
                sql = """
                UPDATE devices 
                SET online_status = %s, last_online_time = %s, updated_at = NOW()
                WHERE device_id = %s AND is_deleted = 0
                """
                
                last_online = datetime.now() if online_status == 'online' else None
                cursor.execute(sql, (online_status, last_online, device_id))
                self.connection.commit()
                return cursor.rowcount > 0
                
        except pymysql.OperationalError as e:
            logger.warning(f"数据库操作错误，跳过设备状态更新 {device_id}: {e}")
            return False
        except pymysql.Error as e:
            logger.warning(f"数据库错误，跳过设备状态更新 {device_id}: {e}")
            return False
        except Exception as e:
            logger.warning(f"更新设备状态失败 {device_id}: {e}")
            return False


class DPProtocolMessage:
    """DP协议消息构造器"""
    
    MSG_HEAD = 0x5555  # 报文头固定值
    MSG_TYPE = 0x03    # 报文类型
    
    def __init__(self, device_id: str):
        self.device_id = device_id.ljust(24, '\x00')[:24]  # 设备ID，固定24字节
        self.seq_num = 0
    
    def _calculate_crc16(self, data: bytes) -> int:
        """计算CRC16校验码（与C++实现兼容）"""
        # 使用与C++实现完全相同的查表法
        crc_table = [
            0x0000, 0x1189, 0x2312, 0x329B, 0x4624, 0x57AD, 0x6536, 0x74BF, 0x8C48, 0x9DC1, 0xAF5A, 0xBED3, 0xCA6C, 0xDbe5,
            0xE97E, 0xF8F7, 0x1081, 0x0108, 0x3393, 0x221A, 0x56A5, 0x472C, 0x75B7, 0x643E, 0x9CC9, 0x8D40, 0xBFDB, 0xAE52,
            0xDAED, 0xCB64, 0xF9FF, 0xE876, 0x2102, 0x308B, 0x0210, 0x1399, 0x6726, 0x76AF, 0x4434, 0x55BD, 0xAD4A, 0xBCC3,
            0x8E58, 0x9FD1, 0xEB6E, 0xFAE7, 0xC87C, 0xD9F5, 0x3183, 0x200A, 0x1291, 0x0318, 0x77A7, 0x662E, 0x54B5, 0x453C,
            0xBDCB, 0xAC42, 0x9ED9, 0x8F50, 0xFBEF, 0xEA66, 0xD8FD, 0xC974, 0x4204, 0x538D, 0x6116, 0x709F, 0x0420, 0x15A9,
            0x2732, 0x36BB, 0xCE4C, 0xDFC5, 0xED5E, 0xFCD7, 0x8868, 0x99E1, 0xAB7A, 0xBAF3, 0x5285, 0x430C, 0x7197, 0x601E,
            0x14A1, 0x0528, 0x37B3, 0x263A, 0xDECD, 0xCF44, 0xFDDF, 0xEC56, 0x98E9, 0x8960, 0xBBFB, 0xAA72, 0x6306, 0x728F,
            0x4014, 0x519D, 0x2522, 0x34AB, 0x0630, 0x17B9, 0xEF4E, 0xFEC7, 0xCC5C, 0xDDD5, 0xA96A, 0xB8E3, 0x8A78, 0x9BF1,
            0x7387, 0x620E, 0x5095, 0x411C, 0x35A3, 0x242A, 0x16B1, 0x0738, 0xFFCF, 0xEE46, 0xDCDD, 0xCD54, 0xB9EB, 0xA862,
            0x9AF9, 0x8B70, 0x8408, 0x9581, 0xA71A, 0xB693, 0xC22C, 0xD3A5, 0xE13E, 0xF0B7, 0x0840, 0x19C9, 0x2B52, 0x3ADB,
            0x4E64, 0x5FED, 0x6D76, 0x7CFF, 0x9489, 0x8500, 0xB79B, 0xA612, 0xD2AD, 0xC324, 0xF1BF, 0xE036, 0x18C1, 0x0948,
            0x3BD3, 0x2A5A, 0x5EE5, 0x4F6C, 0x7DF7, 0x6C7E, 0xA50A, 0xB483, 0x8618, 0x9791, 0xE32E, 0xF2A7, 0xC03C, 0xD1B5,
            0x2942, 0x38CB, 0x0A50, 0x1BD9, 0x6F66, 0x7EEF, 0x4C74, 0x5DFD, 0xB58B, 0xA402, 0x9699, 0x8710, 0xF3AF, 0xE226,
            0xD0BD, 0xC134, 0x39C3, 0x284A, 0x1AD1, 0x0B58, 0x7FE7, 0x6E6E, 0x5CF5, 0x4D7C, 0xC60C, 0xD785, 0xE51E, 0xF497,
            0x8028, 0x91A1, 0xA33A, 0xB2B3, 0x4A44, 0x5BCD, 0x6956, 0x78DF, 0x0C60, 0x1DE9, 0x2F72, 0x3EFB, 0xD68D, 0xC704,
            0xF59F, 0xE416, 0x90A9, 0x8120, 0xB3BB, 0xA232, 0x5AC5, 0x4B4C, 0x79D7, 0x685E, 0x1CE1, 0x0D68, 0x3FF3, 0x2E7A,
            0xE70E, 0xF687, 0xC41C, 0xD595, 0xA12A, 0xB0A3, 0x8238, 0x93B1, 0x6B46, 0x7ACF, 0x4854, 0x59DD, 0x2D62, 0x3CEB,
            0x0E70, 0x1FF9, 0xF78F, 0xE606, 0xD49D, 0xC514, 0xB1AB, 0xA022, 0x92B9, 0x8330, 0x7BC7, 0x6A4E, 0x58D5, 0x495C,
            0x3DE3, 0x2C6A, 0x1EF1, 0x0F78
        ]
        
        crc = 0xFFFF
        
        for byte in data:
            # 使用查表法：crc = (crc >> 8) ^ table[(crc ^ byte) & 0xFF]
            crc = ((crc >> 8) ^ crc_table[(crc ^ byte) & 0xFF]) & 0xFFFF
        
        # 关键：最后取反！与C++实现保持一致
        return (~crc) & 0xFFFF
    
    def _build_header(self, msg_id: int, body_length: int) -> bytes:
        """构建消息头"""
        self.seq_num = (self.seq_num + 1) % 65536
        
        # 正确打包消息头
        header = struct.pack(
            '<HBHBH',
            self.MSG_HEAD,      # msg_head (2 bytes)
            self.MSG_TYPE,      # msg_type (1 byte)
            body_length,        # msg_body_len (2 bytes)
            0,                  # msg_attribute (1 byte)
            msg_id,             # msg_id (2 bytes)
        )
        header += self.device_id.encode('utf-8')[:24].ljust(24, b'\x00')  # devUniqueId (24 bytes)
        header += struct.pack('<H', self.seq_num)  # seNum (2 bytes)
        
        return header
    
    def _build_tail(self, message_without_tail: bytes) -> bytes:
        """构建消息尾（CRC + 尾标识）"""
        crc = self._calculate_crc16(message_without_tail)
        tail = struct.pack('<HH', crc, 0xAAAA)  # CRC16 + 尾标识
        return tail
    
    def _encode_bcd_time(self, time_struct) -> bytes:
        """将时间编码为BCD格式（6字节：年月日时分秒）"""
        def to_bcd(value):
            """将数值转换为BCD编码"""
            tens = value // 10
            ones = value % 10
            return (tens << 4) | ones
        
        year = time_struct.tm_year % 100  # 取年份后两位
        month = time_struct.tm_mon
        day = time_struct.tm_mday
        hour = time_struct.tm_hour
        minute = time_struct.tm_min
        second = time_struct.tm_sec
        
        # 转换为BCD并打包为6字节
        bcd_time = struct.pack('BBBBBB',
                              to_bcd(year),
                              to_bcd(month),
                              to_bcd(day),
                              to_bcd(hour),
                              to_bcd(minute),
                              to_bcd(second))
        
        return bcd_time
    
    def build_registration_message(self, config: DeviceConfig) -> bytes:
        """构建终端注册消息 (msg_id = 2)"""
        try:
            # 构建消息体 - 简化版本
            manufacturer = config.manufacturer.encode('utf-8')[:16].ljust(16, b'\x00')
            branch_info = b"TestBranch"
            device_model = config.device_model.encode('utf-8')[:16].ljust(16, b'\x00')
            suffix_flag = b"SUFFIX01"
            firmware_version = config.firmware_version.encode('utf-8')[:32].ljust(32, b'\x00')
            hardware_version = config.hardware_version.encode('utf-8')[:5].ljust(5, b'\x00')
            main_software_version = config.firmware_version.encode('utf-8')[:11].ljust(11, b'\x00')
            currency_db_version = b"CurrDB1.0"
            
            # 使用固定格式避免动态格式字符串问题
            body = struct.pack(
                '<16sB10sB16s8s32sB5sH11sH10s',
                manufacturer,                    # manufacturer (16 bytes)
                len(branch_info),               # branchInfoLength (1 byte)
                branch_info,                    # branchInfo (10 bytes)
                config.device_type,             # deviceType (1 byte)
                device_model,                   # deviceModel (16 bytes)
                suffix_flag,                    # suffixFlag (8 bytes)
                firmware_version,               # firmwareVersion (32 bytes)
                len(hardware_version),          # hardwareVersionLength (1 byte)
                hardware_version,               # hardwareVersion (5 bytes)
                len(main_software_version),     # mainSoftwareVersionLength (2 bytes)
                main_software_version,          # mainSoftwareVersion (11 bytes)
                len(currency_db_version),       # currencyDbVersionLength (2 bytes)
                currency_db_version             # currencyDbVersion (10 bytes)
            )
            
            # 构建完整消息
            header = self._build_header(MessageType.REGISTRATION.value, len(body))
            message_without_tail = header + body
            tail = self._build_tail(message_without_tail)
            
            return message_without_tail + tail
            
        except Exception as e:
            logger.error(f"构建注册消息失败: {e}")
            # 返回一个最简单的注册消息
            simple_body = struct.pack('<16sB16s', 
                                    config.manufacturer.encode('utf-8')[:16].ljust(16, b'\x00'),
                                    config.device_type,
                                    config.device_model.encode('utf-8')[:16].ljust(16, b'\x00'))
            header = self._build_header(MessageType.REGISTRATION.value, len(simple_body))
            message_without_tail = header + simple_body
            tail = self._build_tail(message_without_tail)
            return message_without_tail + tail
    
    def build_authentication_message(self, auth_code: str = None) -> bytes:
        """构建终端鉴权消息 (msg_id = 3)"""
        if auth_code is None:
            # 生成简单的认证码
            auth_code = hashlib.md5(self.device_config.device_id.encode()).hexdigest()[:16]
        
        # 修复鉴权码编码问题：
        # 如果auth_code是十六进制字符串，将其转换为实际字节
        # 服务器端期望接收到的是十六进制字符串对应的实际字节数据
        try:
            # 尝试将十六进制字符串转换为字节
            if len(auth_code) == 16 and all(c in '0123456789abcdef' for c in auth_code.lower()):
                # 这是一个有效的十六进制字符串，转换为字节
                auth_bytes = bytes.fromhex(auth_code)
                auth_bytes = auth_bytes.ljust(16, b'\x00')[:16]  # 确保16字节长度
            else:
                # 不是十六进制字符串，按ASCII编码处理
                auth_bytes = auth_code.encode('ascii')[:16].ljust(16, b'\x00')
        except (ValueError, UnicodeEncodeError):
            # 转换失败，回退到ASCII编码
            auth_bytes = auth_code.encode('ascii')[:16].ljust(16, b'\x00')
        
        body = struct.pack('<16s', auth_bytes)
        
        header = self._build_header(MessageType.AUTHENTICATION.value, len(body))
        message_without_tail = header + body
        tail = self._build_tail(message_without_tail)
        
        return message_without_tail + tail
    
    def build_heartbeat_message(self) -> bytes:
        """构建心跳消息 (msg_id = 4)"""
        # 心跳消息无消息体
        body = b''
        
        header = self._build_header(MessageType.HEARTBEAT.value, len(body))
        message_without_tail = header + body
        tail = self._build_tail(message_without_tail)
        
        return message_without_tail + tail
    
    def build_fault_report_message(self, event_level: int = 1, event_code: int = 1001, 
                                 event_content: str = "Test fault") -> bytes:
        """构建故障上报消息 (msg_id = 10)"""
        # 当前时间（6字节BCD格式：年月日时分秒）
        now = time.localtime()
        event_time = self._encode_bcd_time(now)
        
        # 限制event_content长度，避免内存问题
        if len(event_content) > 200:  # 限制最大长度
            event_content = event_content[:200]
        
        event_content_bytes = event_content.encode('utf-8')
        content_length = len(event_content_bytes)
        
        # 使用固定格式，避免动态格式字符串可能的问题
        body = struct.pack('<BH6sH', 
                          event_level,          # event_level (1 byte)
                          event_code,           # event_code (2 bytes)
                          event_time,           # event_time (6 bytes)
                          content_length)       # event_content_length (2 bytes)
        
        # 单独添加event_content
        body += event_content_bytes
        
        header = self._build_header(MessageType.FAULT_REPORT.value, len(body))
        message_without_tail = header + body
        tail = self._build_tail(message_without_tail)
        
        return message_without_tail + tail
    
    def build_banknote_report_message(self, total_notes: int = None, include_details: bool = True, detail_limit: int = 2000) -> bytes:
        """构建点钞上报消息 (msg_id = 12)

        协议要求：
          COUNTINFO[n] 后面必须跟 NOTEINFO[m]，其中 m = 过钞总张数。
        之前实现只发送 1 条 NOTEINFO，导致统计张数与明细不一致，已修复。

        参数:
          total_notes: 指定过钞总张数 (m)。缺省随机。
          include_details: 是否发送 NOTEINFO 明细。若 False，只发送汇总（解析端需允许 m>0 但无 NOTEINFO 的情况，一般不推荐）。
          detail_limit: 保护阈值，防止一次性生成超大报文。当 total_notes > detail_limit 时：
             1) 截断 NOTEINFO 生成 detail_limit 条；
             2) 同步修改统计张数与金额为截断后的值；
             3) 仍保证 COUNTINFO 与 NOTEINFO 数量一致，避免解析错误。
        """
        if total_notes is None:
            total_notes = random.randint(1, 300)  # 控制默认大小，避免超大报文

        if total_notes < 0:
            total_notes = 0
        if total_notes > 65535:
            total_notes = 65535  # 协议 2 字节上限

        # 生成时间 (BCD6)
        counting_time = self._encode_bcd_time(time.localtime())

        work_mode = 1
        business_mode = 1
        add_up_switch = 1
        currency_count = 1  # 仅一个币种 CNY

        # NOTEINFO 真实要生成的条数（可能截断）
        effective_notes = total_notes
        if include_details and total_notes > detail_limit:
            effective_notes = detail_limit

        # 面值策略：这里全部使用 100，可扩展为随机集合 [10,20,50,100] 等
        note_face_value = 100

        # 统计数据使用“有效条数”以保持一致性
        currency_symbol = b'CNY\x00'
        currency_notes = effective_notes
        currency_amount = currency_notes * note_face_value
        count_info = struct.pack('<4sHI', currency_symbol, currency_notes, currency_amount)

        # 生成 NOTEINFO 列表
        note_infos = b''
        if include_details and effective_notes > 0:
            for i in range(effective_notes):
                # 生成 20 字节序列号，未满填 0
                serial_core = f"SN{int(time.time())%100000:05d}{i:05d}"  # 约 12 位 + 前缀
                serial_bytes = serial_core.encode('ascii')[:20].ljust(20, b'\x00')
                note_infos += struct.pack('<4sIBBH20s',
                                          currency_symbol,          # 币种
                                          note_face_value,          # 面值
                                          1,                        # 版本
                                          0,                        # 报错类型
                                          0,                        # 报错代码
                                          serial_bytes)             # 序列号

        # 组装过钞信息主体 (NOTE: 如果 include_details=False, 仍然 m>0 则可能解析端期望 NOTEINFO；此处保持 m=effective_notes)
        banknote_data = struct.pack('<BBB', work_mode, business_mode, add_up_switch)
        banknote_data += counting_time
        banknote_data += struct.pack('<HB', currency_notes, currency_count)
        banknote_data += count_info + note_infos

        info_type = 0   # 基础版本
        packet_flag = 0x00
        body = struct.pack('<BB', info_type, packet_flag) + banknote_data

        header = self._build_header(MessageType.BANKNOTE_REPORT.value, len(body))
        message_without_tail = header + body
        tail = self._build_tail(message_without_tail)
        return message_without_tail + tail

    @staticmethod
    def parse_banknote_report(payload: bytes) -> dict:
        """解析由本构造器生成的点钞上报消息（调试用）
        注意：不做 CRC/头尾校验，只解析结构。供内部比对统计与明细是否一致。
        """
        try:
            # 跳过固定头部: msg_head(2)+msg_type(1)+body_len(2)+msg_attr(1)+msg_id(2)+device_id(24)+seq(2)
            # 当前头布局根据 _build_header 的实现（需与实际一致）
            header_len = 2 + 1 + 2 + 1 + 2 + 24 + 2
            body = payload[header_len:-4]  # -4 预留 CRC+Tail(假设)
            info_type, packet_flag = struct.unpack_from('<BB', body, 0)
            offset = 2
            work_mode, business_mode, add_up_switch = struct.unpack_from('<BBB', body, offset); offset += 3
            counting_time = body[offset:offset+6]; offset += 6
            total_notes, currency_count = struct.unpack_from('<HB', body, offset); offset += 3
            stats = []
            for _ in range(currency_count):
                sym, notes, amount = struct.unpack_from('<4sHI', body, offset)
                offset += 4+2+4
                stats.append({
                    'currency': sym.rstrip(b'\x00').decode(errors='ignore'),
                    'notes': notes,
                    'amount': amount
                })
            notes_list = []
            for i in range(total_notes):
                if offset + (4+4+1+1+2+20) > len(body):
                    break
                sym, val, ver, etype, ecode, serial = struct.unpack_from('<4sIBBH20s', body, offset)
                offset += (4+4+1+1+2+20)
                notes_list.append({
                    'currency': sym.rstrip(b'\x00').decode(errors='ignore'),
                    'value': val,
                    'version': ver,
                    'error_type': etype,
                    'error_code': ecode,
                    'serial': serial.rstrip(b'\x00').decode(errors='ignore')
                })
            return {
                'info_type': info_type,
                'packet_flag': packet_flag,
                'work_mode': work_mode,
                'business_mode': business_mode,
                'add_up_switch': add_up_switch,
                'total_notes_field': total_notes,
                'currency_count': currency_count,
                'statistics': stats,
                'notes_parsed': len(notes_list),
                'notes': notes_list[:5]  # 只返回前5条示例
            }
        except Exception as e:
            return {'parse_error': str(e)}


class EnhancedDeviceSimulator:
    """增强版金融设备仿真器"""
    
    def __init__(self, device_config: DeviceConfig, connection_config: ConnectionConfig, 
                 device_repository: Optional[DeviceRepository] = None):
        self.device_config = device_config
        self.connection_config = connection_config
        self.device_repository = device_repository
        self.message_builder = DPProtocolMessage(device_config.device_id)
        
        self.socket: Optional[socket.socket] = None
        self.connected = False
        self.running = False
        self.lock = threading.Lock()
        
        # 统计信息
        self.stats = {
            'messages_sent': 0,
            'messages_received': 0,
            'connection_errors': 0,
            'last_heartbeat': 0,
            'start_time': 0,
            'registration_time': 0,
            'authentication_time': 0,
            'last_error': None,
            'heartbeat_sent': 0,
            'heartbeat_received': 0,
            'fault_reports_sent': 0,
            'fault_reports_received': 0,
            'banknote_reports_sent': 0,
            'banknote_reports_received': 0,
            # 响应时间统计
            'fault_report_times': [],
            'banknote_report_times': [],
            'heartbeat_times': [],
            # 上报失败诊断
            'fault_report_failures': [],  # 每项: {'reason': str, 'detail': str}
            'banknote_report_failures': []
        }
        self.last_receive_details: Optional[Dict[str, Union[str, int]]] = None
    
    def connect(self) -> bool:
        """建立TCP连接"""
        try:
            if self.socket:
                self.socket.close()
            
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            # 优化socket性能配置
            try:
                # 启用TCP_NODELAY，减少延迟
                self.socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                # 启用地址重用
                self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                # 设置大缓冲区以适应高并发/大包场景
                self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 524288)  # 512KB发送缓冲区
                self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 524288)  # 512KB接收缓冲区
                # 启用KEEPALIVE机制
                self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
                # 设置KEEPALIVE参数（Linux）
                if hasattr(socket, 'TCP_KEEPIDLE'):
                    self.socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPIDLE, 60)
                if hasattr(socket, 'TCP_KEEPINTVL'):
                    self.socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPINTVL, 10)
                if hasattr(socket, 'TCP_KEEPCNT'):
                    self.socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPCNT, 3)
            except Exception as e:
                logger.debug(f"设置socket选项失败，继续执行: {e}")
                
            # 优化连接超时，减少等待时间
            self.socket.settimeout(5.0)  # 5秒连接超时，原来是10秒
            
            logger.debug(f"[{self.device_config.device_id}] 连接到 {self.connection_config.host}:{self.connection_config.port}")
            self.socket.connect((self.connection_config.host, self.connection_config.port))
            
            # 连接成功后设置更短的读写超时
            self.socket.settimeout(8.0)  # 8秒读写超时，原来是15秒
            self.connected = True
            
            # 性能测试时禁用数据库状态更新，避免数据库竞争
            # if self.device_repository:
            #     self.device_repository.update_device_status(self.device_config.device_id, 'online')
            
            logger.debug(f"[{self.device_config.device_id}] 连接成功")
            return True
            
        except socket.timeout:
            error_msg = f"连接超时 ({self.connection_config.host}:{self.connection_config.port})"
            logger.error(f"[{self.device_config.device_id}] {error_msg}")
            self.connected = False
            self.stats['connection_errors'] += 1
            self.stats['last_error'] = error_msg
            return False
        except ConnectionRefusedError:
            error_msg = f"连接被拒绝 ({self.connection_config.host}:{self.connection_config.port})"
            logger.error(f"[{self.device_config.device_id}] {error_msg}")
            self.connected = False
            self.stats['connection_errors'] += 1
            self.stats['last_error'] = error_msg
            return False
        except Exception as e:
            error_msg = f"连接失败: {str(e)}"
            logger.error(f"[{self.device_config.device_id}] {error_msg}")
            self.connected = False
            self.stats['connection_errors'] += 1
            self.stats['last_error'] = error_msg
            return False
    
    def disconnect(self):
        """断开连接"""
        with self.lock:
            if self.socket:
                try:
                    self.socket.close()
                except:
                    pass
                self.socket = None
            self.connected = False
            
            # 性能测试时禁用数据库状态更新，避免数据库竞争
            # if self.device_repository:
            #     self.device_repository.update_device_status(self.device_config.device_id, 'offline')
    
    def send_message(self, message: bytes) -> bool:
        """发送消息"""
        if not self.connected or not self.socket:
            logger.error(f"[{self.device_config.device_id}] 发送消息失败: 连接未建立")
            return False
        
        try:
            with self.lock:
                # 使用 sendall 确保完整发送，避免部分发送导致服务端解析失败
                self.socket.sendall(message)
                self.stats['messages_sent'] += 1
            return True
            
        except Exception as e:
            # 提供详细的发送失败信息
            msg_info = self._extract_message_info(message)
            msg_hex = self._format_message_hex(message, max_bytes=32)
            
            logger.error(f"[{self.device_config.device_id}] 发送消息失败: {e}")
            logger.error(f"  失败报文信息: 消息ID={msg_info.get('msg_id', 'N/A')}, 长度={len(message)}字节")
            logger.error(f"  失败报文内容: {msg_hex}")
            
            self.connected = False
            self.stats['last_error'] = str(e)
            return False
    
    def _recv_exact(self, nbytes: int, overall_timeout: float, stage: str) -> Optional[bytes]:
        """在 overall_timeout 内精确读取 nbytes 字节。
        返回 bytes 若成功；若超时但收到部分数据，记录 partial_* 细节并返回 None；
        若完全超时无数据则记录 timeout 并返回 None。
        """
        if not self.connected or not self.socket:
            return None

        buf = bytearray()
        deadline = time.monotonic() + max(0.0, overall_timeout)

        while len(buf) < nbytes:
            now = time.monotonic()
            remaining_time = deadline - now
            if remaining_time <= 0:
                # 超时
                if len(buf) == 0:
                    self.last_receive_details = {'stage': 'timeout', 'type': 'timeout'}
                else:
                    detail_type = 'partial_header' if stage == 'header' else 'partial_body'
                    self.last_receive_details = {
                        'stage': stage,
                        'type': detail_type,
                        'received_len': len(buf),
                        'expected_len': nbytes
                    }
                return None

            # 为本次 recv 设置较小的超时片段，避免长时间阻塞不可打断
            per_try_timeout = max(0.05, min(1.0, remaining_time))
            try:
                self.socket.settimeout(per_try_timeout)
                chunk = self.socket.recv(nbytes - len(buf))
                if not chunk:
                    # 连接被对端关闭
                    self.connected = False
                    self.last_receive_details = {
                        'stage': stage,
                        'type': 'exception',
                        'exception': 'ConnectionClosed',
                        'message': 'peer closed connection'
                    }
                    return None
                buf.extend(chunk)
            except socket.timeout:
                # 循环继续直到总体超时
                continue
            except Exception as e:
                self.connected = False
                self.stats['last_error'] = str(e)
                self.last_receive_details = {
                    'stage': stage,
                    'type': 'exception',
                    'exception': type(e).__name__,
                    'message': str(e)
                }
                return None

        return bytes(buf)

    def receive_message(self, timeout: float = 5.0) -> Optional[bytes]:
        """接收消息"""
        if not self.connected or not self.socket:
            return None
        
        try:
            # 整体超时内完成两阶段读取：头(34) + 体尾
            overall_deadline = time.monotonic() + max(0.0, timeout)
            # 1) 读取固定头
            header = self._recv_exact(34, timeout, stage='header')
            if header is None:
                return None

            # 2) 解析体长并读取体+尾
            msg_body_len = struct.unpack('<H', header[3:5])[0]
            remaining = msg_body_len + 4  # 消息体 + CRC(2) + 尾标识(2)

            # 计算剩余可用时间，至少给一点余量
            now = time.monotonic()
            body_timeout = max(0.05, overall_deadline - now)
            body_and_tail = self._recv_exact(remaining, body_timeout, stage='body')
            if body_and_tail is None:
                return None

            self.stats['messages_received'] += 1
            self.last_receive_details = {
                'stage': 'complete',
                'type': 'success',
                'length': 34 + len(body_and_tail)
            }
            return header + body_and_tail
            
        except socket.timeout:
            self.last_receive_details = {
                'stage': 'timeout',
                'type': 'timeout'
            }
            return None
        except Exception as e:
            logger.error(f"[{self.device_config.device_id}] 接收消息失败: {e}")
            self.connected = False
            self.stats['last_error'] = str(e)
            self.last_receive_details = {
                'stage': 'exception',
                'type': 'exception',
                'exception': type(e).__name__,
                'message': str(e)
            }
            return None
    
    def perform_registration(self) -> bool:
        """执行设备注册流程"""
        logger.info(f"[{self.device_config.device_id}] 开始设备注册")
        
        # 发送注册消息
        reg_msg = self.message_builder.build_registration_message(self.device_config)
        
        # ✅ 只在实际发送时开始计时，排除排队等待时间
        network_start_time = time.time()
        if not self.send_message(reg_msg):
            logger.error(f"[{self.device_config.device_id}] 注册报文发送失败")
            return False
        
        # 等待注册响应（减少超时时间提升效率）
        response = self.receive_message(timeout=6.0)
        if response:
            # ✅ 只计算网络往返时间
            self.stats['registration_time'] = time.time() - network_start_time
            logger.info(f"[{self.device_config.device_id}] 注册成功，用时 {self.stats['registration_time']:.3f}s，收到响应: {len(response)} 字节")
            return True
        else:
            # 打印注册失败的详细信息
            msg_info = self._extract_message_info(reg_msg)
            msg_hex = self._format_message_hex(reg_msg, max_bytes=64)
            
            logger.error(f"[{self.device_config.device_id}] 注册失败，未收到响应（超时6秒）")
            logger.error(f"  报文信息: 消息ID={msg_info.get('msg_id', 'N/A')}, 设备ID={msg_info.get('device_id', 'N/A')}, 序列号={msg_info.get('seq_num', 'N/A')}")
            logger.error(f"  失败报文内容: {msg_hex}")
            logger.error(f"  设备参数: 厂商={self.device_config.manufacturer}, 型号={self.device_config.device_model}, 固件版本={self.device_config.firmware_version}")
            
            return False
    
    def perform_authentication(self) -> bool:
        """执行设备鉴权流程"""
        logger.info(f"[{self.device_config.device_id}] 开始设备鉴权")
        
        # 使用设备配置中的认证码
        auth_code = self.device_config.authentication_code
        if not auth_code:
            auth_code = hashlib.md5(self.device_config.device_id.encode()).hexdigest()[:16]
        
        logger.debug(f"[{self.device_config.device_id}] 使用的鉴权码: {auth_code}")
        
        # 发送鉴权消息
        auth_msg = self.message_builder.build_authentication_message(auth_code)
        logger.debug(f"[{self.device_config.device_id}] 构建的鉴权消息长度: {len(auth_msg)} 字节")
        
        # ✅ 只在实际发送时开始计时，排除排队等待时间
        network_start_time = time.time()
        if not self.send_message(auth_msg):
            logger.error(f"[{self.device_config.device_id}] 鉴权报文发送失败")
            return False
        
        # 等待鉴权响应（减少超时时间提升效率）
        response = self.receive_message(timeout=6.0)
        if response:
            # ✅ 只计算网络往返时间
            self.stats['authentication_time'] = time.time() - network_start_time
            logger.info(f"[{self.device_config.device_id}] 鉴权成功，用时 {self.stats['authentication_time']:.3f}s，收到响应: {len(response)} 字节")
            return True
        else:
            # 打印鉴权失败的详细信息
            msg_info = self._extract_message_info(auth_msg)
            msg_hex = self._format_message_hex(auth_msg, max_bytes=48)
            
            logger.error(f"[{self.device_config.device_id}] 鉴权失败，未收到响应（超时6秒）")
            logger.error(f"  报文信息: 消息ID={msg_info.get('msg_id', 'N/A')}, 设备ID={msg_info.get('device_id', 'N/A')}, 序列号={msg_info.get('seq_num', 'N/A')}")
            logger.error(f"  失败报文内容: {msg_hex}")
            logger.error(f"  鉴权码: {auth_code}")
            
            return False
    
    def send_heartbeat(self) -> bool:
        """发送心跳"""
        current_time = time.time()
        heartbeat_msg = self.message_builder.build_heartbeat_message()
        if self.send_message(heartbeat_msg):
            # 记录心跳间隔时间
            if self.stats['last_heartbeat'] > 0:
                interval = current_time - self.stats['last_heartbeat']
                self.stats['heartbeat_times'].append(interval)
            
            self.stats['last_heartbeat'] = current_time
            self.stats['heartbeat_sent'] += 1
            
            # 心跳报文通常不需要应答，只是保持连接活跃
            # 不等待响应，直接返回成功
            logger.debug(f"[{self.device_config.device_id}] 心跳发送成功")
            
            return True
        return False
    
    def send_fault_report(self, event_code: int = None, event_content: str = None, max_retries: int = 3, recv_timeout: float = 4.0) -> bool:
        """发送故障上报"""
        if event_code is None:
            event_code = random.randint(1000, 9999)
        if event_content is None:
            event_content = f"Test fault event {event_code}"
        
        fault_msg = self.message_builder.build_fault_report_message(
            event_code=event_code, event_content=event_content
        )
        
        # 使用高精度计时
        import time as _t
        send_time = _t.perf_counter()
        if self.send_message(fault_msg):
            self.stats['fault_reports_sent'] += 1
            
            # 尝试接收响应，带重试机制
            timeouts = 0
            for retry in range(max_retries + 1):
                response = self.receive_message(timeout=recv_timeout)
                if response:
                    response_time = _t.perf_counter() - send_time
                    self.stats['fault_reports_received'] += 1
                    self.stats['fault_report_times'].append(response_time)
                    logger.debug(f"[{self.device_config.device_id}] 故障上报响应: {len(response)} 字节, 时间: {response_time:.3f}s")
                    return True
                else:
                    if self.last_receive_details and self.last_receive_details.get('type') == 'timeout':
                        timeouts += 1
                    if retry < max_retries:
                        # 使用指数退避但限制最大延迟，提升吞吐
                        backoff = min(0.1 * (2 ** retry), 0.5)
                        logger.debug(f"[{self.device_config.device_id}] 故障上报响应超时，重试 {retry + 1}/{max_retries}，等待 {backoff:.2f}s")
                        time.sleep(backoff)
            diag = self._classify_no_response(max_retries + 1, timeouts)
            self.stats['fault_report_failures'].append(diag)
            
            # 打印失败原因和报文内容
            msg_info = self._extract_message_info(fault_msg)
            msg_hex = self._format_message_hex(fault_msg, max_bytes=48)
            
            logger.warning(f"[{self.device_config.device_id}] 故障上报经过 {max_retries} 次重试仍无响应")
            logger.warning(f"  失败原因: {diag['reason']} - {diag['detail']}")
            logger.warning(f"  报文信息: 消息ID={msg_info.get('msg_id', 'N/A')}, 设备ID={msg_info.get('device_id', 'N/A')}, 序列号={msg_info.get('seq_num', 'N/A')}")
            logger.warning(f"  失败报文内容: {msg_hex}")
            logger.warning(f"  故障参数: event_code={event_code}, event_content='{event_content[:50]}{'...' if len(event_content or '') > 50 else ''}'")
            
            return True
        else:
            # 故障上报发送失败
            logger.error(f"[{self.device_config.device_id}] 故障上报发送失败")
        return False
    
    def send_banknote_report(self, total_notes: int = None, max_retries: int = 3, recv_timeout: float = 4.0) -> bool:
        """发送点钞上报"""
        banknote_msg = self.message_builder.build_banknote_report_message(total_notes)
        
        import time as _t
        send_time = _t.perf_counter()
        if self.send_message(banknote_msg):
            self.stats['banknote_reports_sent'] += 1
            
            # 尝试接收响应，带重试机制
            timeouts = 0
            for retry in range(max_retries + 1):
                response = self.receive_message(timeout=recv_timeout)
                if response:
                    response_time = _t.perf_counter() - send_time
                    self.stats['banknote_reports_received'] += 1
                    self.stats['banknote_report_times'].append(response_time)
                    logger.debug(f"[{self.device_config.device_id}] 点钞上报响应: {len(response)} 字节, 时间: {response_time:.3f}s")
                    return True
                else:
                    if self.last_receive_details and self.last_receive_details.get('type') == 'timeout':
                        timeouts += 1
                    if retry < max_retries:
                        backoff = min(0.1 * (2 ** retry), 0.5)
                        logger.debug(f"[{self.device_config.device_id}] 点钞上报响应超时，重试 {retry + 1}/{max_retries}，等待 {backoff:.2f}s")
                        time.sleep(backoff)
            diag = self._classify_no_response(max_retries + 1, timeouts)
            self.stats['banknote_report_failures'].append(diag)
            
            # 打印失败原因和报文内容
            msg_info = self._extract_message_info(banknote_msg)
            msg_hex = self._format_message_hex(banknote_msg, max_bytes=48)
            
            logger.warning(f"[{self.device_config.device_id}] 点钞上报经过 {max_retries} 次重试仍无响应")
            logger.warning(f"  失败原因: {diag['reason']} - {diag['detail']}")
            logger.warning(f"  报文信息: 消息ID={msg_info.get('msg_id', 'N/A')}, 设备ID={msg_info.get('device_id', 'N/A')}, 序列号={msg_info.get('seq_num', 'N/A')}")
            logger.warning(f"  失败报文内容: {msg_hex}")
            logger.warning(f"  点钞参数: total_notes={total_notes if total_notes else 'random'}")
            
            return True
        else:
            # 点钞上报发送失败
            logger.error(f"[{self.device_config.device_id}] 点钞上报发送失败")
        return False
    
    def start_heartbeat_loop(self, interval: int = 30):
        """启动心跳循环"""
        def heartbeat_worker():
            while self.running and self.connected:
                if not self.send_heartbeat():
                    logger.warning(f"[{self.device_config.device_id}] 心跳发送失败")
                    break
                time.sleep(interval)
        
        self.running = True
        thread = threading.Thread(target=heartbeat_worker, daemon=True)
        thread.start()
        return thread
    
    def get_stats(self) -> Dict:
        """获取统计信息"""
        current_stats = self.stats.copy()
        current_stats['connected'] = self.connected
        current_stats['running'] = self.running
        current_stats['device_id'] = self.device_config.device_id
        if self.stats['start_time'] > 0:
            current_stats['uptime'] = time.time() - self.stats['start_time']
        return current_stats
    
    def reset_stats(self):
        """重置统计信息"""
        self.stats = {
            'messages_sent': 0,
            'messages_received': 0,
            'connection_errors': 0,
            'last_heartbeat': 0,
            'start_time': time.time(),
            'registration_time': 0,
            'authentication_time': 0,
            'last_error': None,
            'heartbeat_sent': 0,
            'heartbeat_received': 0,
            'fault_reports_sent': 0,
            'fault_reports_received': 0,
            'banknote_reports_sent': 0,
            'banknote_reports_received': 0,
            # 保持响应时间与间隔数组，避免后续统计为空导致平均为0
            'fault_report_times': [],
            'banknote_report_times': [],
            'heartbeat_times': [],
            'fault_report_failures': [],
            'banknote_report_failures': []
        }
        self.last_receive_details = None

    def _optimize_memory_usage(self):
        """优化内存使用，定期清理过大的数组"""
        # 限制响应时间数组大小，避免内存积累
        MAX_TIME_RECORDS = 1000
        if len(self.stats['fault_report_times']) > MAX_TIME_RECORDS:
            self.stats['fault_report_times'] = self.stats['fault_report_times'][-MAX_TIME_RECORDS//2:]
        if len(self.stats['banknote_report_times']) > MAX_TIME_RECORDS:
            self.stats['banknote_report_times'] = self.stats['banknote_report_times'][-MAX_TIME_RECORDS//2:]
        if len(self.stats['heartbeat_times']) > MAX_TIME_RECORDS:
            self.stats['heartbeat_times'] = self.stats['heartbeat_times'][-MAX_TIME_RECORDS//2:]
        
        # 限制失败记录数组大小
        MAX_FAILURE_RECORDS = 100
        if len(self.stats['fault_report_failures']) > MAX_FAILURE_RECORDS:
            self.stats['fault_report_failures'] = self.stats['fault_report_failures'][-MAX_FAILURE_RECORDS//2:]
        if len(self.stats['banknote_report_failures']) > MAX_FAILURE_RECORDS:
            self.stats['banknote_report_failures'] = self.stats['banknote_report_failures'][-MAX_FAILURE_RECORDS//2:]

    # ---------- 报文格式化工具 ----------
    def _format_message_hex(self, message: bytes, max_bytes: int = 64) -> str:
        """格式化报文为十六进制字符串用于调试输出"""
        if not message:
            return "空报文"
        
        # 限制输出长度，避免日志过长
        display_bytes = message[:max_bytes]
        hex_str = ' '.join(f'{b:02X}' for b in display_bytes)
        
        if len(message) > max_bytes:
            hex_str += f" ... (共{len(message)}字节，只显示前{max_bytes}字节)"
        else:
            hex_str += f" (共{len(message)}字节)"
            
        return hex_str
    
    def _extract_message_info(self, message: bytes) -> Dict[str, str]:
        """从报文中提取关键信息用于调试"""
        if not message or len(message) < 34:
            return {"error": "报文长度不足"}
        
        try:
            # 解析报文头 (参考 _build_header 的格式)
            msg_head = int.from_bytes(message[0:2], byteorder='little')
            msg_type = message[2]
            msg_body_len = int.from_bytes(message[3:5], byteorder='little') 
            msg_attribute = message[5]
            msg_id = int.from_bytes(message[6:8], byteorder='little')
            device_id = message[8:32].rstrip(b'\x00').decode('utf-8', errors='ignore')
            seq_num = int.from_bytes(message[32:34], byteorder='little')
            
            return {
                "msg_head": f"0x{msg_head:04X}",
                "msg_type": f"{msg_type}",
                "msg_id": f"{msg_id}",
                "msg_body_len": f"{msg_body_len}",
                "device_id": f"{device_id}",
                "seq_num": f"{seq_num}",
                "total_len": f"{len(message)}"
            }
        except Exception as e:
            return {"error": f"解析失败: {str(e)}"}

    # ---------- 失败诊断 ----------
    def _classify_no_response(self, attempts: int, timeouts: int) -> Dict[str, str]:
        info = self.last_receive_details or {}
        t = info.get('type')
        if not self.connected:
            return {'reason': 'NOT_CONNECTED', 'detail': '连接已断开或未建立，服务器可能关闭或网络中断'}
        if t == 'partial_header':
            return {'reason': 'PARTIAL_HEADER', 'detail': f"仅收到 {info.get('received_len')} / {info.get('expected_len')} 头部字节"}
        if t == 'partial_body':
            missing = (info.get('expected_len', 0) - info.get('received_len', 0))
            return {'reason': 'PARTIAL_BODY', 'detail': f"消息体缺失 {missing} 字节，疑似服务器中断发送或网络丢包"}
        if t == 'timeout':
            if timeouts == attempts:
                return {'reason': 'TIMEOUT_SILENT', 'detail': '所有尝试均纯超时，服务器未返回任何数据'}
            return {'reason': 'INTERMITTENT_TIMEOUT', 'detail': '部分尝试超时，可能网络抖动或服务器负载高'}
        if t == 'exception':
            return {'reason': 'SOCKET_EXCEPTION', 'detail': f"接收异常 {info.get('exception')}: {info.get('message')}"}
        if t == 'success':
            return {'reason': 'LATE_SUCCESS', 'detail': '逻辑上不应出现：标记成功却仍判定失败'}
        return {'reason': 'UNKNOWN', 'detail': '无法分类，需抓包或服务器日志进一步分析'}


class DeviceSimulatorManager:
    """设备仿真器管理器，负责管理多个设备仿真器"""
    
    def __init__(self, config_file: str = "test_config.json", environment: str = "local"):
        self.config = self._load_config(config_file, environment)
        self.simulators: List[EnhancedDeviceSimulator] = []
        self.device_repository = None
        self.running = False
        self.last_batch_results = None  # 保存最后一次批处理结果
        # 全局测试时长（从命令执行开始到结束）
        self.global_test_start_time: Optional[float] = None
        self.global_test_end_time: Optional[float] = None
        self.global_test_duration: Optional[float] = None
        # 保存命令行传入的保持运行时长 (--test-duration)，默认 None，运行入口赋值
        self.configured_test_duration: Optional[float] = None
        
        # 初始化设备仓库
        db_config = DatabaseConfig(**self.config['database'])
        self.device_repository = DeviceRepository(db_config)
        
        # 初始化连接池
        tcp_config = self.config['tcp_gateway']
        self.connection_pool = ConnectionPool(
            host=tcp_config['host'],
            port=tcp_config['ports']['dp_protocol_v1'],
            max_connections=500  # 设置较大的连接池
        )
    
    def _load_config(self, config_file: str, environment: str) -> Dict:
        """加载配置文件"""
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            if environment not in config['test_environments']:
                raise ValueError(f"环境 '{environment}' 不存在于配置文件中")
            
            return config['test_environments'][environment]
            
        except Exception as e:
            logger.error(f"加载配置文件失败: {e}")
            raise
    
    def load_test_devices(self, device_id_prefix: str = "PERF_TEST", limit: int = None) -> List[DeviceConfig]:
        """从数据库加载测试设备"""
        return self.device_repository.load_test_devices(device_id_prefix, limit)
    
    def create_simulators(self, device_configs: List[DeviceConfig]) -> int:
        """创建设备仿真器"""
        tcp_config = self.config['tcp_gateway']
        connection_config = ConnectionConfig(
            host=tcp_config['host'],
            port=tcp_config['ports']['dp_protocol_v1'],
            timeout=30
        )
        
        self.simulators = []
        for device_config in device_configs:
            simulator = EnhancedDeviceSimulator(
                device_config, 
                connection_config, 
                self.device_repository
            )
            self.simulators.append(simulator)
        
        logger.info(f"创建了 {len(self.simulators)} 个设备仿真器")
        return len(self.simulators)

    def _build_global_total_duration_card(self) -> str:
        """构造全局总测试时长指标卡片 HTML
        情况：
          1) 未开始：显示 N/A
          2) 已开始未结束：使用当前时间临时计算持续时间
          3) 已结束：使用固定结束时间
        """
        start = getattr(self, 'global_test_start_time', None)
        end = getattr(self, 'global_test_end_time', None)
        if not start:
            # 尝试使用“批处理注册+鉴权耗时 + 配置的保持时长”作为估算
            if self.last_batch_results and 'total_duration' in self.last_batch_results and self.configured_test_duration:
                est_total = self.last_batch_results['total_duration'] + self.configured_test_duration
                display = self._format_duration_compact(est_total)
                return f"<div class=\"metric\"><h3>总测试时长(估算)</h3><div class=\"value\">{display}</div><div class=\"unit\">批处理+保持期</div></div>"
            # 只有批处理耗时时，也给出估算（不含保持期）
            if self.last_batch_results and 'total_duration' in self.last_batch_results:
                batch_only = self.last_batch_results['total_duration']
                display = self._format_duration_compact(batch_only)
                return f"<div class=\"metric\"><h3>总测试时长(估算)</h3><div class=\"value\">{display}</div><div class=\"unit\">仅批处理</div></div>"
            return """<div class=\"metric\"><h3>总测试时长</h3><div class=\"value\">N/A</div><div class=\"unit\">未开始</div></div>"""
        if not end:
            # 进行中的测试，动态显示
            end = time.time()
        total_duration = end - start
        if total_duration >= 3600:
            hours = int(total_duration // 3600)
            minutes = int((total_duration % 3600) // 60)
            seconds = total_duration % 60
            display = f"{hours}h {minutes}m {seconds:.1f}s"
        elif total_duration >= 60:
            minutes = int(total_duration // 60)
            seconds = total_duration % 60
            display = f"{minutes}m {seconds:.1f}s"
        else:
            display = f"{total_duration:.2f}s"
        # 评估状态（纯展示，不做严格告警）
        device_count = len(self.simulators) if hasattr(self, 'simulators') else 0
        status = 'metric'
        if device_count > 0:
            per = total_duration / device_count
            if per <= 1.0:
                status = 'metric success'
            elif per <= 2.0:
                status = 'metric warning'
            else:
                status = 'metric error'
        return f"<div class=\"{status}\"><h3>总测试时长</h3><div class=\"value\">{display}</div><div class=\"unit\">命令整体</div></div>"

    def _format_duration_compact(self, seconds: float) -> str:
        """辅助格式化（内部使用）"""
        if seconds >= 3600:
            h = int(seconds // 3600)
            m = int((seconds % 3600) // 60)
            s = seconds % 60
            return f"{h}h {m}m {s:.1f}s"
        if seconds >= 60:
            m = int(seconds // 60)
            s = seconds % 60
            return f"{m}m {s:.1f}s"
        return f"{seconds:.2f}s"
    
    def start_all_simulators(self, registration_interval: float = 0.01, max_concurrent: int = 500) -> Dict:
        """启动所有仿真器进行注册（支持并发）"""
        # 注意：以下时间统计仅针对本次批量注册/鉴权流程，不代表"总测试时长"
        results = {
            'total': len(self.simulators),
            'connected': 0,
            'registered': 0,
            'authenticated': 0,
            'failed': 0,
            'errors': [],
            'total_start_time': 0,  # 批处理开始时间
            'total_end_time': 0,    # 批处理结束时间
            'total_duration': 0,    # 批处理耗时
            'average_time_per_device': 0  # 批处理平均每设备耗时
        }
        
    # 🕒 记录批处理开始时间
        overall_start_time = time.time()
        results['total_start_time'] = overall_start_time
        
        logger.info(f"开始启动 {results['total']} 个设备仿真器 (并发数: {max_concurrent})...")
        logger.info(f"整体计时开始: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(overall_start_time))}")
        
        def process_simulator(simulator, index):
            """处理单个仿真器的连接、注册、鉴权流程"""
            local_result = {'connected': False, 'registered': False, 'authenticated': False, 'error': None}
            
            try:
                # 连接
                if simulator.connect():
                    local_result['connected'] = True
                    
                    # 注册
                    if simulator.perform_registration():
                        local_result['registered'] = True
                        
                        # 鉴权
                        if simulator.perform_authentication():
                            local_result['authenticated'] = True
                            logger.debug(f"设备 {simulator.device_config.device_id} 完成注册和鉴权 ({index+1}/{results['total']})")
                        else:
                            local_result['error'] = "鉴权失败"
                    else:
                        local_result['error'] = "注册失败"
                else:
                    local_result['error'] = "连接失败"
                    
            except Exception as e:
                local_result['error'] = f"异常 - {str(e)}"
                logger.error(f"设备 {simulator.device_config.device_id} 启动失败: {e}")
            
            return simulator.device_config.device_id, local_result
        
        # 使用线程池进行并发处理，动态调整线程池大小
        from concurrent.futures import ThreadPoolExecutor, as_completed
        import threading
        
        result_lock = threading.Lock()
        
        # 动态计算最优线程池大小
        optimal_workers = min(max_concurrent, max(100, results['total'] // 10))
        
        with ThreadPoolExecutor(max_workers=optimal_workers) as executor:
            # 提交所有任务，优化延迟策略
            futures = []
            for i, simulator in enumerate(self.simulators):
                # 大幅减少延迟影响，按批次提交
                if registration_interval > 0 and i > 0 and i % 50 == 0:
                    time.sleep(registration_interval)  # 每50个设备才延迟一次
                
                future = executor.submit(process_simulator, simulator, i)
                futures.append(future)
            
            # 收集结果，增加超时控制
            completed_count = 0
            for future in as_completed(futures, timeout=300):  # 5分钟总超时
                try:
                    device_id, local_result = future.result(timeout=30)  # 单个任务30秒超时
                    
                    with result_lock:
                        completed_count += 1
                        if local_result['connected']:
                            results['connected'] += 1
                        if local_result['registered']:
                            results['registered'] += 1
                        if local_result['authenticated']:
                            results['authenticated'] += 1
                        
                        if local_result['error']:
                            results['failed'] += 1
                            results['errors'].append(f"{device_id}: {local_result['error']}")
                        
                        # 每完成100个设备输出一次进度
                        if completed_count % 100 == 0:
                            logger.info(f"进度: {completed_count}/{results['total']} 设备已处理")
                        
                except Exception as e:
                    with result_lock:
                        results['failed'] += 1
                        results['errors'].append(f"Unknown device: 处理异常 - {str(e)}")
                    logger.error(f"处理设备时发生异常: {e}")
        
    # 🕒 记录批处理结束时间并计算平均时间
        overall_end_time = time.time()
        results['total_end_time'] = overall_end_time
        results['total_duration'] = overall_end_time - overall_start_time
        
        # 计算平均每设备处理时间（总时间 / 设备数量）
        if results['total'] > 0:
            results['average_time_per_device'] = results['total_duration'] / results['total']
        
        logger.info(f"并发连接完成 - 成功: {results['authenticated']}/{results['total']}")
        logger.info(f"整体计时结束: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(overall_end_time))}")
        logger.info(f"总耗时: {results['total_duration']:.3f}秒")
        logger.info(f"平均每设备处理时间: {results['average_time_per_device']:.3f}秒")
        
        # 打印详细的错误统计
        if results['errors']:
            print(f"\n❌ 发现 {len(results['errors'])} 个错误:")
            error_counts = {}
            for error in results['errors'][:20]:  # 只显示前20个错误
                error_type = error.split(': ')[-1] if ': ' in error else error
                error_counts[error_type] = error_counts.get(error_type, 0) + 1
                print(f"  - {error}")
            
            print(f"\n📊 错误类型统计:")
            for error_type, count in sorted(error_counts.items(), key=lambda x: x[1], reverse=True):
                print(f"  - {error_type}: {count}次")
        
        # 保存批处理结果供后续统计使用
        self.last_batch_results = results
        
        return results
    
    def start_heartbeat_for_all(self, interval: int = 30):
        """为所有已连接的设备启动心跳"""
        heartbeat_count = 0
        for simulator in self.simulators:
            if simulator.connected:
                simulator.start_heartbeat_loop(interval)
                heartbeat_count += 1
        
        logger.info(f"为 {heartbeat_count} 个设备启动了心跳")
        return heartbeat_count
    
    def send_test_messages(self, message_count: int = 10, interval: float = 0.5,
                           send_concurrency: Optional[int] = None,
                           recv_timeout: float = 4.0,
                           max_retries: int = 3,
                           max_notes: int = 400,
                           no_fault: bool = False,
                           no_banknote: bool = False):
        """发送测试消息"""
        logger.info(f"开始发送测试消息，每个设备 {message_count} 条...")
        
        # 使用线程池并发发送，提高效率
        import concurrent.futures
        
        def send_device_messages(simulator):
            """为单个设备发送测试消息"""
            if not simulator.connected:
                return {'device_id': simulator.device_config.device_id, 'sent': 0, 'errors': ['设备未连接']}
            
            sent_count = 0
            errors = []
            
            for i in range(message_count):
                try:
                    # 随机发送不同类型的消息（可禁用某类）
                    options = []
                    if not no_fault:
                        options.append('fault')
                    if not no_banknote:
                        options.append('banknote')
                    if not options:
                        options = ['banknote']
                    message_type = random.choice(options)
                    
                    if message_type == 'fault':
                        success = simulator.send_fault_report(
                            event_code=random.randint(1000, 9999),
                            event_content=f"Test fault from {simulator.device_config.device_id}",
                            max_retries=max_retries,
                            recv_timeout=recv_timeout
                        )
                    else:
                        success = simulator.send_banknote_report(
                            total_notes=random.randint(10, max(10, max_notes)),
                            max_retries=max_retries,
                            recv_timeout=recv_timeout
                        )
                    
                    if success:
                        sent_count += 1
                        logger.debug(f"[{simulator.device_config.device_id}] 发送测试消息 {i+1}/{message_count} ({message_type})")
                    else:
                        errors.append(f"消息 {i+1} 发送失败 ({message_type})")
                        logger.warning(f"[{simulator.device_config.device_id}] 测试消息 {i+1} 发送失败")
                    
                    # 更短的间隔以提升总体QPS
                    if interval > 0:
                        time.sleep(interval)
                    
                except Exception as e:
                    errors.append(f"消息 {i+1} 异常: {str(e)}")
                    logger.error(f"[{simulator.device_config.device_id}] 发送测试消息异常: {e}")
            
            return {
                'device_id': simulator.device_config.device_id, 
                'sent': sent_count, 
                'errors': errors
            }
        
        # 并发发送消息
        # 大幅提升并发度；默认按设备数与参数取较小值
        if send_concurrency is None:
            send_concurrency = min(200, max(1, len(self.simulators)))
        with concurrent.futures.ThreadPoolExecutor(max_workers=send_concurrency) as executor:
            futures = [executor.submit(send_device_messages, sim) for sim in self.simulators if sim.connected]
            
            total_sent = 0
            total_errors = 0
            
            for future in concurrent.futures.as_completed(futures):
                try:
                    result = future.result()
                    total_sent += result['sent']
                    total_errors += len(result['errors'])
                    
                    if result['errors']:
                        logger.warning(f"设备 {result['device_id']} 发送错误: {result['errors'][:3]}")  # 只显示前3个错误
                        
                except Exception as e:
                    logger.error(f"获取发送结果失败: {e}")
                    total_errors += 1
        
        logger.info(f"测试消息发送完成 - 总发送: {total_sent}, 总错误: {total_errors}")
    
    def get_all_stats(self) -> List[Dict]:
        """获取所有设备的统计信息"""
        return [simulator.get_stats() for simulator in self.simulators]
    
    def stop_all_simulators(self):
        """停止所有仿真器"""
        logger.info("停止所有设备仿真器...")
        
        for simulator in self.simulators:
            simulator.running = False
            simulator.disconnect()
        
        # 关闭连接池
        if hasattr(self, 'connection_pool'):
            self.connection_pool.close_all()
        
        if self.device_repository:
            self.device_repository.disconnect()
        
        logger.info("所有设备仿真器已停止")
    
    def print_summary_stats(self, batch_results: Dict = None):
        """打印汇总统计信息"""
        # 如果没有传入批处理结果，使用最后保存的结果
        if batch_results is None:
            batch_results = self.last_batch_results
            
        stats_list = self.get_all_stats()
        
        if not stats_list:
            print("没有统计数据")
            return
        
        total_sent = sum(s['messages_sent'] for s in stats_list)
        total_received = sum(s['messages_received'] for s in stats_list)
        total_errors = sum(s['connection_errors'] for s in stats_list)
        connected_count = sum(1 for s in stats_list if s['connected'])
        
        avg_reg_time = sum(s['registration_time'] for s in stats_list if s['registration_time'] > 0) / max(1, len([s for s in stats_list if s['registration_time'] > 0]))
        avg_auth_time = sum(s['authentication_time'] for s in stats_list if s['authentication_time'] > 0) / max(1, len([s for s in stats_list if s['authentication_time'] > 0]))
        
        print("\n" + "="*70)
        print("设备仿真器统计汇总")
        print("="*70)
        print(f"总设备数量: {len(stats_list)}")
        print(f"连接设备数: {connected_count}")
        print(f"发送消息总数: {total_sent}")
        print(f"接收消息总数: {total_received}")
        print(f"连接错误总数: {total_errors}")
        
        # 显示两种时间统计方式
        print(f"\n📊 时间统计:")
        
        # 如果有批处理结果，优先显示总体平均时间
        if batch_results and 'average_time_per_device' in batch_results:
            print(f"  📈 平均注册登录时间: {batch_results['average_time_per_device']:.4f}秒/设备")
            print(f"    - 总处理时间: {batch_results['total_duration']:.3f}秒")
            print(f"    - 处理设备数: {batch_results['total']}")
            print(f"    - 成功设备数: {batch_results['authenticated']}")
            
            # 计算吞吐量
            if batch_results['total_duration'] > 0:
                throughput = batch_results['authenticated'] / batch_results['total_duration']
                print(f"    - 设备处理吞吐量: {throughput:.1f} 设备/秒")
        else:
            # 如果没有批处理结果，显示传统的单次操作时间
            print(f"  单次操作平均时间:")
            print(f"    - 平均注册时间: {avg_reg_time:.3f}s (单个设备网络往返)")
            print(f"    - 平均鉴权时间: {avg_auth_time:.3f}s (单个设备网络往返)")
            
        print("="*70)
    
    def generate_simple_report(self) -> str:
        """生成简单的测试报告"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        # 自动补齐全局结束时间（如果还未设置但用户提前生成报告）
        if getattr(self, 'global_test_start_time', None) and not getattr(self, 'global_test_end_time', None):
            self.global_test_end_time = time.time()
            self.global_test_duration = self.global_test_end_time - self.global_test_start_time
        # 如果仍没有全局开始时间，尝试用批处理 + 配置时长估算（只影响显示，不写入 global_test_* 字段）
        synthetic_total_duration: Optional[float] = None
        if not getattr(self, 'global_test_start_time', None):
            if self.last_batch_results and 'total_duration' in self.last_batch_results and self.configured_test_duration:
                synthetic_total_duration = self.last_batch_results['total_duration'] + self.configured_test_duration
        
        # 创建报告目录
        report_dir = "performance_reports"
        os.makedirs(report_dir, exist_ok=True)
        
        # 收集统计数据
        stats_list = self.get_all_stats()
        
        if not stats_list:
            logger.warning("没有统计数据，无法生成报告")
            return ""
        
        # 计算汇总数据
        total_devices = len(stats_list)
        connected_count = sum(1 for s in stats_list if s['connected'])
        total_sent = sum(s['messages_sent'] for s in stats_list)
        total_received = sum(s['messages_received'] for s in stats_list)
        total_errors = sum(s['connection_errors'] for s in stats_list)
        
        reg_times = [s['registration_time'] for s in stats_list if s['registration_time'] > 0]
        auth_times = [s['authentication_time'] for s in stats_list if s['authentication_time'] > 0]
        
        # 故障上报和点钞上报统计
        total_fault_sent = sum(s.get('fault_reports_sent', 0) for s in stats_list)
        total_fault_received = sum(s.get('fault_reports_received', 0) for s in stats_list)
        total_banknote_sent = sum(s.get('banknote_reports_sent', 0) for s in stats_list)
        total_banknote_received = sum(s.get('banknote_reports_received', 0) for s in stats_list)
        total_heartbeat_sent = sum(s.get('heartbeat_sent', 0) for s in stats_list)
        
        # 计算平均响应时间
        all_fault_times = []
        all_banknote_times = []
        all_heartbeat_intervals = []
        for s in stats_list:
            all_fault_times.extend(s.get('fault_report_times', []))
            all_banknote_times.extend(s.get('banknote_report_times', []))
            all_heartbeat_intervals.extend(s.get('heartbeat_times', []))
        
        avg_reg_time = sum(reg_times) / len(reg_times) if reg_times else 0
        avg_auth_time = sum(auth_times) / len(auth_times) if auth_times else 0
        avg_fault_time = sum(all_fault_times) / len(all_fault_times) if all_fault_times else 0
        avg_banknote_time = sum(all_banknote_times) / len(all_banknote_times) if all_banknote_times else 0
        # 为显示准备格式化（优先用 ms，过小显示 <1ms）
        def _fmt_latency(sec: float) -> Tuple[str, str]:
            if sec == 0:
                return 'N/A', '无数据'
            if sec < 0.001:
                return '<1', 'ms'
            if sec < 1:
                return f"{sec*1000:.1f}", 'ms'
            return f"{sec:.3f}", '秒'
        fault_val, fault_unit = _fmt_latency(avg_fault_time)
        banknote_val, banknote_unit = _fmt_latency(avg_banknote_time)
        avg_heartbeat_interval = sum(all_heartbeat_intervals) / len(all_heartbeat_intervals) if all_heartbeat_intervals else 0
        
        connection_success_rate = connected_count / total_devices if total_devices > 0 else 0
        registration_success_rate = len(reg_times) / total_devices if total_devices > 0 else 0
        authentication_success_rate = len(auth_times) / total_devices if total_devices > 0 else 0
        fault_response_rate = total_fault_received / max(1, total_fault_sent) if total_fault_sent > 0 else 0
        banknote_response_rate = total_banknote_received / max(1, total_banknote_sent) if total_banknote_sent > 0 else 0

        # 若 synthetic_total_duration 存在且真实 global 测试时长缺失，可在日志中提示
        if synthetic_total_duration and not self.global_test_duration:
            logger.info(
                "使用估算总测试时长: 批处理 %.3fs + 保持 %.3fs = %.3fs" % (
                    self.last_batch_results['total_duration'],
                    self.configured_test_duration or 0,
                    synthetic_total_duration
                )
            )
        
        # 生成HTML报告
        html_file = os.path.join(report_dir, f"performance_report_{timestamp}.html")
        
        html_content = f"""
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>设备性能测试报告 - {timestamp}</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; background-color: #f5f5f5; }}
        .container {{ max-width: 1200px; margin: 0 auto; background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
        h1 {{ color: #333; text-align: center; border-bottom: 2px solid #4CAF50; padding-bottom: 10px; }}
        h2 {{ color: #555; border-bottom: 1px solid #ddd; padding-bottom: 5px; }}
        .summary {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 20px; margin: 20px 0; }}
        .metric {{ background: #f9f9f9; padding: 15px; border-radius: 5px; border-left: 4px solid #4CAF50; }}
        .metric h3 {{ margin: 0 0 10px 0; color: #333; }}
        .metric .value {{ font-size: 24px; font-weight: bold; color: #4CAF50; }}
        .metric .unit {{ font-size: 14px; color: #666; }}
        .success {{ border-left-color: #4CAF50; }}
        .warning {{ border-left-color: #FF9800; }}
        .error {{ border-left-color: #f44336; }}
        .table {{ width: 100%; border-collapse: collapse; margin: 20px 0; }}
        .table th, .table td {{ padding: 12px; text-align: left; border-bottom: 1px solid #ddd; }}
        .table th {{ background-color: #f2f2f2; font-weight: bold; }}
        .table tr:hover {{ background-color: #f5f5f5; }}
        .timestamp {{ text-align: center; color: #666; margin-top: 20px; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>设备性能测试报告</h1>
        
        <h2>测试概览</h2>
        <div class="summary">
            <div class="metric success">
                <h3>总设备数量</h3>
                <div class="value">{total_devices}</div>
                <div class="unit">台设备</div>
            </div>
            <div class="metric {'success' if connection_success_rate >= 0.95 else 'warning' if connection_success_rate >= 0.8 else 'error'}">
                <h3>连接成功率</h3>
                <div class="value">{connection_success_rate:.1%}</div>
                <div class="unit">{connected_count}/{total_devices} 连接成功</div>
            </div>
            <div class="metric {'success' if registration_success_rate >= 0.95 else 'warning' if registration_success_rate >= 0.8 else 'error'}">
                <h3>注册成功率</h3>
                <div class="value">{registration_success_rate:.1%}</div>
                <div class="unit">{len(reg_times)}/{total_devices} 注册成功</div>
            </div>
            <div class="metric {'success' if authentication_success_rate >= 0.95 else 'warning' if authentication_success_rate >= 0.8 else 'error'}">
                <h3>鉴权成功率</h3>
                <div class="value">{authentication_success_rate:.1%}</div>
                <div class="unit">{len(auth_times)}/{total_devices} 鉴权成功</div>
            </div>
            <div class="metric">
                <h3>消息发送总数</h3>
                <div class="value">{total_sent}</div>
                <div class="unit">条消息</div>
            </div>
            <div class="metric">
                <h3>消息接收总数</h3>
                <div class="value">{total_received}</div>
                <div class="unit">条响应</div>
            </div>"""
        
        # 添加总体平均注册登录时间指标（仍基于批处理）
        if hasattr(self, 'last_batch_results') and self.last_batch_results and 'average_time_per_device' in self.last_batch_results:
            avg_login_time = self.last_batch_results['average_time_per_device']
            time_status = 'success' if avg_login_time <= 0.1 else 'warning' if avg_login_time <= 0.5 else 'error'
            html_content += f"""
            <div class="metric {time_status}">
                <h3>平均注册登录时间</h3>
                <div class="value">{avg_login_time:.4f}</div>
                <div class="unit">秒/设备</div>
            </div>"""

        # 批处理（注册+鉴权）耗时：来自 last_batch_results 的 total_duration（如果已执行）
        if hasattr(self, 'last_batch_results') and self.last_batch_results and 'total_duration' in self.last_batch_results:
            batch_total = self.last_batch_results['total_duration']
            if batch_total >= 3600:
                hours = int(batch_total // 3600)
                minutes = int((batch_total % 3600) // 60)
                seconds = batch_total % 60
                batch_display = f"{hours}h {minutes}m {seconds:.1f}s"
            elif batch_total >= 60:
                minutes = int(batch_total // 60)
                seconds = batch_total % 60
                batch_display = f"{minutes}m {seconds:.1f}s"
            else:
                batch_display = f"{batch_total:.2f}s"
            html_content += f"""
            <div class="metric">
                <h3>注册+鉴权耗时</h3>
                <div class="value">{batch_display}</div>
                <div class="unit">批处理阶段</div>
            </div>"""
        
        html_content += f"""
            <div class="metric {'success' if fault_response_rate >= 0.95 else 'warning' if fault_response_rate >= 0.8 else 'error'}">
                <h3>故障上报响应率</h3>
                <div class="value">{fault_response_rate:.1%}</div>
                <div class="unit">{total_fault_received}/{total_fault_sent} 响应成功</div>
            </div>
            <div class="metric {'success' if avg_fault_time <= 0.5 and avg_fault_time > 0 else 'warning' if avg_fault_time <= 1.0 and avg_fault_time > 0 else 'error' if avg_fault_time > 0 else ''}">
                <h3>故障上报平均响应时间</h3>
                <div class="value">{fault_val}</div>
                <div class="unit">{fault_unit}</div>
            </div>
            <div class="metric {'success' if banknote_response_rate >= 0.95 else 'warning' if banknote_response_rate >= 0.8 else 'error'}">
                <h3>点钞上报响应率</h3>
                <div class="value">{banknote_response_rate:.1%}</div>
                <div class="unit">{total_banknote_received}/{total_banknote_sent} 响应成功</div>
            </div>
            <div class="metric {'success' if avg_banknote_time <= 0.5 and avg_banknote_time > 0 else 'warning' if avg_banknote_time <= 1.0 and avg_banknote_time > 0 else 'error' if avg_banknote_time > 0 else ''}">
                <h3>点钞上报平均响应时间</h3>
                <div class="value">{banknote_val}</div>
                <div class="unit">{banknote_unit}</div>
            </div>
            <div class="metric">
                <h3>心跳消息总数</h3>
                <div class="value">{total_heartbeat_sent}</div>
                <div class="unit">条心跳</div>
            </div>
            <!-- 全局总测试时长（命令整体运行）替换原 平均心跳间隔 -->
            {self._build_global_total_duration_card()}
        </div>
        
        <h2>详细设备状态</h2>
        <table class="table">
            <thead>
                <tr>
                    <th>设备ID</th>
                    <th>连接状态</th>
                    <th>注册时间(s)</th>
                    <th>鉴权时间(s)</th>
                    <th>发送消息</th>
                    <th>接收消息</th>
                    <th>心跳(发送)</th>
                    <th>故障报告(发送/接收)</th>
                    <th>点钞报告(发送/接收)</th>
                    <th>连接错误</th>
                    <th>最后错误</th>
                </tr>
            </thead>
            <tbody>
"""
        
        # 添加设备详细信息
        for stats in stats_list:
            status_class = "success" if stats['connected'] else "error"
            error_display = stats.get('last_error', '-')[:50] if stats.get('last_error') else '-'
            
            # 计算各类消息的响应率
            # 心跳不需要响应，所以显示为N/A
            heartbeat_display = f"{stats.get('heartbeat_sent', 0)}/N/A"
            fault_response_rate = (stats.get('fault_reports_received', 0) / max(1, stats.get('fault_reports_sent', 0))) * 100
            banknote_response_rate = (stats.get('banknote_reports_received', 0) / max(1, stats.get('banknote_reports_sent', 0))) * 100
            
            html_content += f"""
                <tr>
                    <td>{stats['device_id']}</td>
                    <td><span class="{status_class}">{'在线' if stats['connected'] else '离线'}</span></td>
                    <td>{stats['registration_time']:.3f}</td>
                    <td>{stats['authentication_time']:.3f}</td>
                    <td>{stats['messages_sent']}</td>
                    <td>{stats['messages_received']}</td>
                    <td>{heartbeat_display}</td>
                    <td>{stats.get('fault_reports_sent', 0)}/{stats.get('fault_reports_received', 0)} ({fault_response_rate:.0f}%)</td>
                    <td>{stats.get('banknote_reports_sent', 0)}/{stats.get('banknote_reports_received', 0)} ({banknote_response_rate:.0f}%)</td>
                    <td>{stats['connection_errors']}</td>
                    <td>{error_display}</td>
                </tr>
"""
        
        html_content += f"""
            </tbody>
        </table>
        
        <div class="timestamp">
            报告生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        </div>
    </div>
</body>
</html>
"""
        
        # 写入HTML文件
        try:
            with open(html_file, 'w', encoding='utf-8') as f:
                f.write(html_content)
            
            # 同时生成CSV文件用于数据分析
            csv_file = os.path.join(report_dir, f"test_results_{timestamp}.csv")
            with open(csv_file, 'w', encoding='utf-8') as f:
                f.write("设备ID,连接状态,注册时间,鉴权时间,发送消息数,接收消息数,心跳发送,故障报告发送,故障报告接收,点钞报告发送,点钞报告接收,连接错误数,最后错误\n")
                for stats in stats_list:
                    f.write(f"{stats['device_id']},{stats['connected']},{stats['registration_time']:.3f},"
                           f"{stats['authentication_time']:.3f},{stats['messages_sent']},{stats['messages_received']},"
                           f"{stats.get('heartbeat_sent', 0)},"
                           f"{stats.get('fault_reports_sent', 0)},{stats.get('fault_reports_received', 0)},"
                           f"{stats.get('banknote_reports_sent', 0)},{stats.get('banknote_reports_received', 0)},"
                           f"{stats['connection_errors']},\"{stats.get('last_error', '')}\"\n")
            
            logger.info(f"性能报告已生成:")
            logger.info(f"  HTML报告: {html_file}")
            logger.info(f"  CSV数据: {csv_file}")
            
            return html_file
            
        except Exception as e:
            logger.error(f"生成报告失败: {e}")
            return ""


if __name__ == "__main__":
    import argparse
    from datetime import datetime
    
    # 命令行参数解析
    parser = argparse.ArgumentParser(description="增强版设备仿真器")
    parser.add_argument("--environment", type=str, default="local", choices=["local", "vm", "staging"], help="环境名称")
    parser.add_argument("--config", type=str, default="test_config.json", help="配置文件路径")
    parser.add_argument("--device-count", type=int, default=5000, help="要测试的设备数量")
    parser.add_argument("--device-prefix", type=str, default="PERF_TEST", help="设备ID前缀")
    parser.add_argument("--registration-interval", type=float, default=0.01, help="设备注册间隔时间(秒)")
    parser.add_argument("--max-concurrent", type=int, default=500, help="最大并发连接数")
    parser.add_argument("--heartbeat-interval", type=int, default=30, help="心跳间隔时间(秒)")
    parser.add_argument("--test-messages", type=int, default=3, help="每个设备发送的测试消息数量")
    parser.add_argument("--message-interval", type=float, default=0.5, help="测试消息间隔时间(秒)")
    parser.add_argument("--test-duration", type=int, default=60, help="测试持续时间(秒)")
    # 新增可调性能参数
    parser.add_argument("--send-concurrency", type=int, default=None, help="发送阶段线程池并发度(默认=min(200, 设备数))")
    parser.add_argument("--recv-timeout", type=float, default=4.0, help="测试消息接收超时(秒)")
    parser.add_argument("--max-retries", type=int, default=3, help="测试消息接收重试次数")
    parser.add_argument("--max-notes", type=int, default=400, help="点钞上报单次最大张数(保护上限)")
    parser.add_argument("--no-fault", action="store_true", help="禁用故障上报，仅发送点钞上报")
    parser.add_argument("--no-banknote", action="store_true", help="禁用点钞上报，仅发送故障上报")
    
    args = parser.parse_args()
    
    try:
        # 创建管理器，并记录全局开始时间
        manager = DeviceSimulatorManager(args.config, args.environment)
        manager.global_test_start_time = time.time()
        # 保存命令行指定的测试持续时间以供估算总测试时长
        manager.configured_test_duration = args.test_duration
        
        # 加载测试设备
        devices = manager.load_test_devices(args.device_prefix, args.device_count)
        if not devices:
            print(f"❌ 未找到测试设备，请先运行 device_batch_inserter.py 创建测试设备")
            print(f"   python device_batch_inserter.py --count {args.device_count} --prefix {args.device_prefix}")
            exit(1)
        
        print(f"✅ 从数据库加载了 {len(devices)} 个测试设备")
        
        # 创建仿真器
        manager.create_simulators(devices)
        
        # 启动所有仿真器
        print(f"开始设备注册测试... (并发数: {args.max_concurrent})")
        start_time = time.time()
        results = manager.start_all_simulators(args.registration_interval, args.max_concurrent)
        connection_time = time.time() - start_time
        
        print(f"\n注册结果:")
        print(f"  总设备数: {results['total']}")
        print(f"  连接成功: {results['connected']}")
        print(f"  注册成功: {results['registered']}")
        print(f"  鉴权成功: {results['authenticated']}")
        print(f"  失败数量: {results['failed']}")
        print(f"  总耗时: {connection_time:.2f}秒")
        print(f"  平均连接速度: {results['total']/connection_time:.2f} 设备/秒")
        if results['authenticated'] > 0:
            print(f"  成功率: {results['authenticated']/results['total']*100:.1f}%")
        
        if results['errors']:
            print(f"  错误详情:")
            for error in results['errors'][:5]:  # 只显示前5个错误
                print(f"    - {error}")
            if len(results['errors']) > 5:
                print(f"    ... 还有 {len(results['errors']) - 5} 个错误")
        
        if results['authenticated'] > 0:
            # 启动心跳
            manager.start_heartbeat_for_all(args.heartbeat_interval)
            
            # 发送测试消息
            if args.test_messages > 0:
                manager.send_test_messages(
                    message_count=args.test_messages,
                    interval=args.message_interval,
                    send_concurrency=args.send_concurrency,
                    recv_timeout=args.recv_timeout,
                    max_retries=args.max_retries,
                    max_notes=args.max_notes,
                    no_fault=args.no_fault,
                    no_banknote=args.no_banknote
                )
            
            # 保持运行一段时间
            print(f"\\n测试运行 {args.test_duration} 秒...")
            time.sleep(args.test_duration)
            
            # 显示统计信息
            manager.print_summary_stats()
            
            # 生成性能报告
            print("\\n📊 正在生成性能测试报告...")
            # 记录生成报告前的结束时间
            manager.global_test_end_time = time.time()
            manager.global_test_duration = manager.global_test_end_time - manager.global_test_start_time
            report_file = manager.generate_simple_report()
            if report_file:
                print(f"✅ 性能报告已生成: {report_file}")
                print(f"   请在浏览器中打开查看详细报告")
            else:
                print("❌ 报告生成失败")
        
    except KeyboardInterrupt:
        print("\\n测试被用户中断")
    except Exception as e:
        logger.error(f"程序执行错误: {e}")
    finally:
        if 'manager' in locals():
            # 若尚未记录结束时间（例如中断提前退出），补记
            if manager.global_test_start_time and not manager.global_test_end_time:
                manager.global_test_end_time = time.time()
                manager.global_test_duration = manager.global_test_end_time - manager.global_test_start_time
            manager.stop_all_simulators()
            if manager.global_test_duration:
                print(f"总测试时长: {manager.global_test_duration:.2f} 秒")
        print("测试完成")