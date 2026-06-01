# 导入 Flask 的 jsonify，它能把 Python 字典转换成 JSON 格式的响应体
from flask import jsonify
# 导入 marshmallow 的 Schema 类，它是所有数据模板（Schema）的基类
from marshmallow import Schema

def response_data(data, schema, many=False):
    """
    序列化数据并返回标准的 API 响应。
    
    :param data: 需要序列化（打包）的数据。它可以是单个对象、列表，或者我们之前创建的分页对象。
    :param schema: 打包时使用的“模板”或“规则”，告诉函数如何处理数据。
    :param many: 一个开关，当 data 是一个列表时，必须设为 True。默认为 False。
    :return: Flask Response 对象
    """
    
    # 1. 根据传入的 schema 字典，预先准备好 Schema 类
    if isinstance(schema, dict):
        schema_class = Schema.from_dict(schema)  #这个就是把 字典转成一个类 
        """
            class UserSchema(Schema):
                id = fields.Str()
                account = fields.Str()
                full_name = fields.Str()
        """  
        #这就是Schema的作用把 字典转成一个类
    
    else:
        # 如果传入的不是字典，假定它就是 Schema 类本身
        schema_class = schema
        
    # 2. 检查 data 是否是分页对象
    if hasattr(data, 'items') and hasattr(data, 'total'):
        # 如果是分页对象，我们需要序列化它的 .items 属性，这是一个列表。
        # 因此，在这里我们创建一个专门用于列表的序列化器 (many=True)。
        serializer = schema_class(many=True)
        items_data = serializer.dump(data.items)
        
        # 构建包含分页信息的响应体
        response_body = {
            "code": 0,
            "message": "success",
            "data": {
                "items": items_data,
                "pagination": {
                    "total": data.total,
                    "pages": data.pages,
                    "page": data.page,
                    "per_page": data.per_page
                }
            }
        }
    else: 
        # 如果不是分页对象，我们就根据函数调用时传入的 many 参数来创建序列化器。
        serializer = schema_class(many=many)
        serialized_data = serializer.dump(data)
        
        # 构建不含分页信息的响应体
        response_body = {
            "code": 0,
            "message": "success",
            "data": serialized_data
        }

    # 使用 jsonify 将字典转换为 JSON 响应
    return jsonify(response_body)