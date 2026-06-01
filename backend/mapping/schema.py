from webargs import fields, validate
# --- Schemas ---

device_model_schema = {
    "id": fields.Int(dump_only=True),
    "model_name": fields.Str(dump_only=True)
}

device_model_create_schema = {
    "model_name": fields.Str(required=True, validate=validate.Length(min=1, max=20))
}

device_model_batch_delete_schema = {
    "model_ids": fields.List(fields.Int(), required=True, validate=validate.Length(min=1, max=100))
}

device_model_batch_delete_result_schema = {
    "total_requested": fields.Int(dump_only=True),
    "successfully_deleted": fields.List(fields.Int(), dump_only=True),
    "not_found": fields.List(fields.Int(), dump_only=True),
    "success_count": fields.Int(dump_only=True),
    "not_found_count": fields.Int(dump_only=True)
}


device_model_update_schema = {
    "model_name":fields.Str(required=True,validate=validate.Length(min=1,max=20))
}

# 定义设备型号列表查询参数 Schema，包含筛选和分页
device_model_list_query_args = {
    # 分页参数
    "page": fields.Int(load_default=1, validate=lambda p: p > 0),
    "per_page": fields.Int(load_default=10, validate=lambda p: p > 0),
    
    # 模糊筛选参数
    "model_name": fields.Str(),  # 型号名称（包含匹配）
}