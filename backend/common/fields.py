"""
通用字段模块
"""
from webargs import fields
from datetime import timezone


class UTCDateTimeField(fields.DateTime):
    """
    自定义UTC DateTime字段，将naive时间转换为UTC aware时间
    用于处理数据库中存储的naive格式UTC时间，在序列化时添加时区信息
    """
    def _serialize(self, value, attr, obj, **kwargs):
        if value is None:
            return None
        # 第1步：附加时区信息，将 naive 变成 aware
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        
        # 第2步：格式化输出 (父类的默认行为就是 isoformat)
        return super()._serialize(value, attr, obj, **kwargs)