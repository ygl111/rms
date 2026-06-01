from backend.extensions import db
from sqlalchemy import Column, String, Integer, SmallInteger, DateTime, func, ForeignKey, Numeric
from sqlalchemy.dialects.mysql import TINYINT, SMALLINT as MYSQL_SMALLINT
from sqlalchemy.orm import relationship

class BanknoteCount(db.Model):
    """
    过钞信息总统计表
    """
    __tablename__ = 'banknote_counts'

    id = Column(String(36), primary_key=True, comment='主键ID (UUID)')
    device_id = Column(String(36), ForeignKey('devices.id', ondelete='RESTRICT'), nullable=False, comment='外键，关联设备ID')
    institution_id = Column(String(36), comment='冗余外键，所属机构ID')
    device_identifier = Column(String(64), comment='冗余字段，设备ID字符串')
    institution_name = Column(String(64), comment='冗余字段，机构名称')
    institution_code = Column(String(64), comment='冗余字段，机构编码')
    work_mode = Column(TINYINT, comment='工作模式 (BYTE)')
    business_mode = Column(TINYINT, comment='业务模式 (BYTE)')
    accumulate_flag = Column(TINYINT, comment='累加开关：0=未开启，1=开启')
    count_time = Column(DateTime, nullable=False, comment='过钞时间')
    total_passed_count = Column(SmallInteger, comment='过钞总张数 (UINT16)')
    failed_count = Column(SmallInteger, comment='过钞失败数量')
    total_amount = Column(Numeric(27, 2), comment='总金额')
    currency_count = Column(TINYINT, comment='币种数量 (BYTE)')
    created_at = Column(DateTime, nullable=False, server_default=func.utc_timestamp())
    is_deleted = Column(TINYINT, nullable=False, default=0)

    # Relationships
    device = relationship('Device', backref='banknote_counts')
    currencies = relationship('BanknoteCountCurrency', back_populates='count', cascade="all, delete-orphan")
    detailed_data = relationship('BanknoteDetailedData', back_populates='count', cascade="all, delete-orphan")

    def __repr__(self):
        return f'<BanknoteCount {self.id}>'

class BanknoteCountCurrency(db.Model):
    """
    币种统计表
    """
    __tablename__ = 'banknote_count_currencies'

    id = Column(String(36), primary_key=True, comment='主键ID (UUID)')
    count_id = Column(String(36), ForeignKey('banknote_counts.id', ondelete='RESTRICT'), nullable=False, comment='外键，所属点钞记录ID')
    currency_code = Column(String(4), nullable=False, comment='币种编号 (BYTE[4])')
    value = Column(Numeric(20, 2), nullable=False, comment='单张面值')
    note_count = Column(SmallInteger, comment='张数 (UINT16)')
    amount = Column(Numeric(25, 2), comment='金额')
    is_deleted = Column(TINYINT, default=0)

    # Relationship
    count = relationship('BanknoteCount', back_populates='currencies')

    def __repr__(self):
        return f'<BanknoteCountCurrency {self.currency_code} value:{self.value}>'

class BanknoteDetailedData(db.Model):
    """
    单张钞票的详细数据表
    """
    __tablename__ = 'banknote_detailed_data'

    count_id = Column(String(36), ForeignKey('banknote_counts.id', ondelete='RESTRICT'), primary_key=True, nullable=False, comment='外键，所属点钞记录ID')
    seq = Column(Integer, primary_key=True, nullable=False, comment='同一次count内的明细序号')
    currency_code = Column(String(4), nullable=False, comment='币种编号 (BYTE[4])')
    note_value = Column(Numeric(20, 2), comment='钞票面值')
    note_version = Column(TINYINT, comment='钞票版本 (UINT8)')
    error_type = Column(MYSQL_SMALLINT(unsigned=True), comment='报错类型 (UINT16)')
    error_code = Column(String(128), comment='报错代码')
    error_group = Column(TINYINT, comment='报错分组 (UINT8)')
    serial_number = Column(String(40), comment='钞票序列号 (BYTE[20])')
    is_deleted = Column(TINYINT, nullable=False, default=0)
    stacker = Column(Integer, nullable=False, comment='钞口')

    # Relationship
    count = relationship('BanknoteCount', back_populates='detailed_data')

    def __repr__(self):
        return f'<BanknoteDetailedData sn:{self.serial_number}>' 
