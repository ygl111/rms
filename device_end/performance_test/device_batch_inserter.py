#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
设备批量插入工具
用于在性能测试前批量插入测试设备到数据库
"""

import json
import uuid
import logging
import random
from datetime import datetime
from typing import List, Dict, Optional
import pymysql
from dataclasses import dataclass


# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

logger = logging.getLogger('DeviceBatchInserter')


@dataclass
class DeviceRecord:
    """设备记录数据类"""
    id: str
    device_id: str
    device_type: int
    firmware_version: str
    ip_endpoint: str
    online_status: str
    institution_id: str
    model_id: int
    hardware_version: str
    main_software_version: str
    currency_library_version: str
    authentication_code: str
    suffix_marker: str
    description: str


@dataclass
class InstitutionRecord:
    """机构记录数据类"""
    id: str
    institution_code: str
    institution_name: str
    parent_id: Optional[str]
    level: int
    address: str
    contact_info: str
    status: str


@dataclass
class ModelRecord:
    """设备型号记录数据类"""
    id: int
    model_name: str


class DeviceBatchInserter:
    """设备批量插入器"""
    
    def __init__(self, config_file: str = "test_config.json", environment: str = "local"):
        """
        初始化
        
        Args:
            config_file: 配置文件路径
            environment: 环境名称 (local, vm, staging)
        """
        self.config = self._load_config(config_file, environment)
        self.connection = None
        
        # 设备类型和型号映射
        self.device_types = {
            1: "点钞机",
            2: "清分机", 
            3: "ATM机",
            4: "存取款机",
            5: "智能柜台"
        }
        
        # 设备型号配置
        self.device_models = [
            {"id": 1, "model_name": "DianChao-2000"},
            {"id": 2, "model_name": "QingFen-3000"},
            {"id": 3, "model_name": "ATM-5000"},
            {"id": 4, "model_name": "CunQuKuan-1000"},
            {"id": 5, "model_name": "ZhiNengGuiTai-8000"}
        ]
        
        # 固件版本列表
        self.firmware_versions = [
            "1.0.0", "1.0.1", "1.1.0", "1.1.1", 
            "1.2.0", "2.0.0", "2.0.1", "2.1.0"
        ]
        
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
    
    def connect_database(self) -> bool:
        """连接数据库"""
        try:
            db_config = self.config['database']
            self.connection = pymysql.connect(
                host=db_config['host'],
                port=db_config['port'],
                user=db_config['user'],
                password=db_config['password'],
                database=db_config['database'],
                charset='utf8mb4',
                cursorclass=pymysql.cursors.DictCursor,
                autocommit=False
            )
            
            logger.info(f"成功连接到数据库: {db_config['host']}:{db_config['port']}/{db_config['database']}")
            return True
            
        except Exception as e:
            logger.error(f"数据库连接失败: {e}")
            return False
    
    def disconnect_database(self):
        """断开数据库连接"""
        if self.connection:
            self.connection.close()
            self.connection = None
            logger.info("数据库连接已关闭")
    
    def _generate_uuid(self) -> str:
        """生成UUID"""
        return str(uuid.uuid4())
    
    def _generate_device_id(self, prefix: str = "PERF_TEST", index: int = 1) -> str:
        """生成设备ID"""
        return f"{prefix}_{index:06d}"
    
    def _generate_auth_code(self, device_id: str) -> str:
        """生成认证码"""
        import hashlib
        return hashlib.md5(device_id.encode()).hexdigest()[:16]
    
    def ensure_institutions_exist(self, count: int = 5) -> List[str]:
        """确保机构数据存在，返回机构ID列表"""
        try:
            with self.connection.cursor() as cursor:
                # 检查是否已有机构数据
                cursor.execute("SELECT COUNT(*) as count FROM institutions WHERE is_deleted = 0")
                result = cursor.fetchone()
                
                if result['count'] >= count:
                    # 获取现有机构ID
                    cursor.execute("SELECT id FROM institutions WHERE is_deleted = 0 LIMIT %s", (count,))
                    return [row['id'] for row in cursor.fetchall()]
                
                # 创建新机构
                institutions = []
                for i in range(1, count + 1):
                    institution = InstitutionRecord(
                        id=self._generate_uuid(),
                        institution_code=f"TEST_ORG_{i:03d}",
                        institution_name=f"测试机构{i}",
                        parent_id=None,
                        level=1,
                        address=f"测试地址{i}号",
                        contact_info=f"1380000{i:04d}",
                        status="active"
                    )
                    institutions.append(institution)
                
                # 批量插入机构
                insert_sql = """
                INSERT INTO institutions (id, institution_code, institution_name, parent_id, level, address, contact_info, status, is_deleted)
                VALUES (%(id)s, %(institution_code)s, %(institution_name)s, %(parent_id)s, %(level)s, %(address)s, %(contact_info)s, %(status)s, 0)
                ON DUPLICATE KEY UPDATE institution_name = VALUES(institution_name)
                """
                
                cursor.executemany(insert_sql, [institution.__dict__ for institution in institutions])
                self.connection.commit()
                
                logger.info(f"成功创建 {len(institutions)} 个机构记录")
                return [inst.id for inst in institutions]
                
        except Exception as e:
            logger.error(f"确保机构存在失败: {e}")
            self.connection.rollback()
            raise
    
    def ensure_device_models_exist(self) -> List[int]:
        """确保设备型号数据存在，返回型号ID列表"""
        try:
            with self.connection.cursor() as cursor:
                # 检查是否已有型号数据
                cursor.execute("SELECT COUNT(*) as count FROM device_mapping_model WHERE is_deleted = 0")
                result = cursor.fetchone()
                
                if result['count'] >= len(self.device_models):
                    # 获取现有型号ID
                    cursor.execute("SELECT id FROM device_mapping_model WHERE is_deleted = 0")
                    return [row['id'] for row in cursor.fetchall()]
                
                # 批量插入型号
                insert_sql = """
                INSERT INTO device_mapping_model (model_name, is_deleted)
                VALUES (%(model_name)s, 0)
                ON DUPLICATE KEY UPDATE model_name = VALUES(model_name)
                """
                
                cursor.executemany(insert_sql, self.device_models)
                self.connection.commit()
                
                # 获取插入后的ID
                cursor.execute("SELECT id FROM device_mapping_model WHERE is_deleted = 0")
                model_ids = [row['id'] for row in cursor.fetchall()]
                
                logger.info(f"成功创建 {len(self.device_models)} 个设备型号记录")
                return model_ids
                
        except Exception as e:
            logger.error(f"确保设备型号存在失败: {e}")
            self.connection.rollback()
            raise
    
    def generate_device_records(self, count: int, institution_ids: List[str], model_ids: List[int], 
                               device_id_prefix: str = "PERF_TEST") -> List[DeviceRecord]:
        """生成设备记录"""
        devices = []
        
        for i in range(1, count + 1):
            device_id = self._generate_device_id(device_id_prefix, i)
            device_type = random.choice(list(self.device_types.keys()))
            model_id = random.choice(model_ids)
            institution_id = random.choice(institution_ids)
            firmware_version = random.choice(self.firmware_versions)
            
            device = DeviceRecord(
                id=self._generate_uuid(),
                device_id=device_id,
                device_type=device_type,
                firmware_version=firmware_version,
                ip_endpoint=f"192.168.{random.randint(1, 254)}.{random.randint(1, 254)}:8080",
                online_status="offline",
                institution_id=institution_id,
                model_id=model_id,
                hardware_version=f"HW_{random.randint(1, 5)}.{random.randint(0, 9)}",
                main_software_version=f"SW_{firmware_version}",
                currency_library_version=f"CUR_{random.randint(1, 10)}.{random.randint(0, 9)}",
                authentication_code=self._generate_auth_code(device_id),
                suffix_marker=f"SUF{i:04d}",
                description=f"性能测试设备 - {self.device_types[device_type]} #{i}"
            )
            devices.append(device)
        
        return devices
    
    def insert_devices_batch(self, devices: List[DeviceRecord], batch_size: int = 1000) -> bool:
        """批量插入设备记录"""
        try:
            insert_sql = """
            INSERT INTO devices (
                id, device_type, firmware_version, ip_endpoint, online_status, 
                last_online_time, institution_id, created_at, updated_at, 
                currency_library_version, hardware_version, main_software_version, 
                authentication_code, suffix_marker, model_id, is_deleted, 
                description, device_id
            ) VALUES (
                %(id)s, %(device_type)s, %(firmware_version)s, %(ip_endpoint)s, %(online_status)s,
                NULL, %(institution_id)s, NOW(), NOW(),
                %(currency_library_version)s, %(hardware_version)s, %(main_software_version)s,
                %(authentication_code)s, %(suffix_marker)s, %(model_id)s, 0,
                %(description)s, %(device_id)s
            ) ON DUPLICATE KEY UPDATE 
                firmware_version = VALUES(firmware_version),
                ip_endpoint = VALUES(ip_endpoint),
                updated_at = NOW(),
                description = VALUES(description)
            """
            
            total_inserted = 0
            with self.connection.cursor() as cursor:
                # 分批插入
                for i in range(0, len(devices), batch_size):
                    batch = devices[i:i + batch_size]
                    cursor.executemany(insert_sql, [device.__dict__ for device in batch])
                    total_inserted += len(batch)
                    
                    logger.info(f"已插入 {total_inserted}/{len(devices)} 条设备记录")
                
                self.connection.commit()
                logger.info(f"成功插入 {len(devices)} 条设备记录")
                return True
                
        except Exception as e:
            logger.error(f"批量插入设备失败: {e}")
            self.connection.rollback()
            return False
    
    def cleanup_test_devices(self, device_id_prefix: str = "PERF_TEST") -> int:
        """清理测试设备数据"""
        try:
            with self.connection.cursor() as cursor:
                # 逻辑删除测试设备
                delete_sql = """
                UPDATE devices 
                SET is_deleted = 1, updated_at = NOW()
                WHERE device_id LIKE %s AND is_deleted = 0
                """
                
                cursor.execute(delete_sql, (f"{device_id_prefix}_%",))
                deleted_count = cursor.rowcount
                
                self.connection.commit()
                logger.info(f"成功清理 {deleted_count} 条测试设备记录")
                return deleted_count
                
        except Exception as e:
            logger.error(f"清理测试设备失败: {e}")
            self.connection.rollback()
            return 0
    
    def get_device_count(self, device_id_prefix: str = "PERF_TEST") -> int:
        """获取测试设备数量"""
        try:
            with self.connection.cursor() as cursor:
                cursor.execute(
                    "SELECT COUNT(*) as count FROM devices WHERE device_id LIKE %s AND is_deleted = 0",
                    (f"{device_id_prefix}_%",)
                )
                result = cursor.fetchone()
                return result['count']
                
        except Exception as e:
            logger.error(f"获取设备数量失败: {e}")
            return 0
    
    def get_test_devices(self, device_id_prefix: str = "PERF_TEST", limit: int = None) -> List[Dict]:
        """获取测试设备列表"""
        try:
            with self.connection.cursor() as cursor:
                sql = """
                SELECT device_id, device_type, firmware_version, authentication_code, 
                       model_id, institution_id, description
                FROM devices 
                WHERE device_id LIKE %s
                ORDER BY device_id
                """
                
                if limit:
                    sql += f" LIMIT {limit}"
                
                cursor.execute(sql, (f"{device_id_prefix}_%",))
                return cursor.fetchall()
                
        except Exception as e:
            logger.error(f"获取测试设备列表失败: {e}")
            return []
    
    def prepare_test_devices(self, count: int, device_id_prefix: str = "PERF_TEST", 
                           cleanup_existing: bool = False) -> bool:
        """准备测试设备（主要入口方法）"""
        try:
            logger.info(f"开始准备 {count} 个测试设备...")
            
            # 连接数据库
            if not self.connect_database():
                return False
            
            # 清理现有测试设备（如果需要）
            if cleanup_existing:
                self.cleanup_test_devices(device_id_prefix)
            
            # 检查现有设备数量
            existing_count = self.get_device_count(device_id_prefix)
            if existing_count >= count:
                logger.info(f"已存在 {existing_count} 个测试设备，无需重复创建")
                return True
            
            # 确保基础数据存在
            institution_ids = self.ensure_institutions_exist()
            model_ids = self.ensure_device_models_exist()
            
            # 需要创建的设备数量
            need_count = count - existing_count
            logger.info(f"需要新建 {need_count} 个测试设备")
            
            # 生成设备记录
            devices = self.generate_device_records(
                need_count, 
                institution_ids, 
                model_ids, 
                device_id_prefix
            )
            
            # 批量插入
            success = self.insert_devices_batch(devices)
            
            if success:
                final_count = self.get_device_count(device_id_prefix)
                logger.info(f"设备准备完成，总计 {final_count} 个测试设备")
            
            return success
            
        except Exception as e:
            logger.error(f"准备测试设备失败: {e}")
            return False
        finally:
            self.disconnect_database()


if __name__ == "__main__":
    import argparse
    
    # 命令行参数解析
    parser = argparse.ArgumentParser(description="设备批量插入工具")
    parser.add_argument("--count", type=int, default=1000, help="要创建的设备数量")
    parser.add_argument("--prefix", type=str, default="PERF_TEST", help="设备ID前缀")
    parser.add_argument("--environment", type=str, default="local", choices=["local", "vm", "staging"], help="环境名称")
    parser.add_argument("--cleanup", action="store_true", help="清理现有测试设备")
    parser.add_argument("--config", type=str, default="test_config.json", help="配置文件路径")
    parser.add_argument("--list", action="store_true", help="列出现有测试设备")
    parser.add_argument("--list-count", type=int, default=10, help="列出设备的数量")
    
    args = parser.parse_args()
    
    try:
        inserter = DeviceBatchInserter(args.config, args.environment)
        
        if args.list:
            # 列出设备
            inserter.connect_database()
            devices = inserter.get_test_devices(args.prefix, args.list_count)
            inserter.disconnect_database()
            
            print(f"\n现有测试设备 (前 {len(devices)} 个):")
            print("-" * 80)
            for device in devices:
                print(f"设备ID: {device['device_id']}, 类型: {device['device_type']}, "
                      f"固件版本: {device['firmware_version']}, 认证码: {device['authentication_code']}")
        else:
            # 准备设备
            success = inserter.prepare_test_devices(
                count=args.count,
                device_id_prefix=args.prefix,
                cleanup_existing=args.cleanup
            )
            
            if success:
                print(f"✅ 成功准备 {args.count} 个测试设备")
                
                # 显示一些示例设备
                inserter.connect_database()
                sample_devices = inserter.get_test_devices(args.prefix, 5)
                inserter.disconnect_database()
                
                print(f"\n示例设备 (前 5 个):")
                print("-" * 80)
                for device in sample_devices:
                    print(f"设备ID: {device['device_id']}, 类型: {device['device_type']}, "
                          f"认证码: {device['authentication_code']}")
            else:
                print("❌ 设备准备失败")
                
    except KeyboardInterrupt:
        print("\n操作被用户中断")
    except Exception as e:
        logger.error(f"程序执行错误: {e}")