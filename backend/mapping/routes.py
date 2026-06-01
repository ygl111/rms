from flask import Blueprint, request
from flask_jwt_extended import jwt_required
from webargs import fields, validate
from webargs.flaskparser import use_args
from sqlalchemy import text
from backend.common.jwt_util import require_permissions
from backend.mapping.service import mapping_service
from backend.common.response import response_data
from backend.extensions import db
from backend.mapping.schema import device_model_schema, device_model_create_schema, \
    device_model_batch_delete_schema, device_model_batch_delete_result_schema, \
    device_model_update_schema, device_model_list_query_args

from backend.common.exceptions import DuplicateResourceError
# 创建蓝图
mapping_bp = Blueprint('mapping', __name__, url_prefix='/api/mappings')


# --- Routes ---

@mapping_bp.route('/device_models', methods=['GET'])
@jwt_required()
def get_device_models():
    """获取所有设备型号列表"""
    models = mapping_service.get_all_device_models()
    return response_data(data=models, schema=device_model_schema, many=True)


@mapping_bp.route('/device_models', methods=['POST'])
@jwt_required()
@require_permissions('DeviceManagement')
@use_args(device_model_create_schema, location="json")
def create_device_model(args):
    """新增设备型号"""
    try:
        new_model = mapping_service.add_device_model(args)
        return response_data(data=new_model, schema=device_model_schema), 201
    except Exception as e:
        return {"message": str(e)}, 400


@mapping_bp.route('/device_models/<string:model_id>', methods=['PUT', 'PATCH'])
@jwt_required()
@require_permissions('DeviceManagement')
@use_args(device_model_update_schema, location="json")
def update_device_model(args, model_id):
    """更新设备型号"""
    try:
        updated_model = mapping_service.update_device_model(model_id, args)
        if updated_model is None:
            return {"message": "Device model not found"}, 404
        return response_data(data=updated_model, schema=device_model_schema)
    except DuplicateResourceError :
        raise DuplicateResourceError("Model name already exists")
    except Exception as e:
        return {"message": str(e)}, 400


@mapping_bp.route('/device_models/batch-delete', methods=['DELETE'])
@jwt_required()
@require_permissions('DeviceManagement')
@use_args(device_model_batch_delete_schema, location="json")
def batch_delete_device_models(args):
    """批量删除设备型号"""
    result = mapping_service.batch_delete_device_models(args['model_ids'])
    return response_data(data=result, schema=device_model_batch_delete_result_schema), 200


@mapping_bp.route('/device_models/paged', methods=['GET'])
@jwt_required()
@use_args(device_model_list_query_args, location="query")
def get_device_models_paged(args):
    """分页获取设备型号列表（支持model_name模糊搜索）"""
    # 从参数中提取分页信息
    page = args['page']
    per_page = args['per_page']
    
    # 提取筛选条件（移除分页参数）
    filter_params = {k: v for k, v in args.items() 
                    if k not in ['page', 'per_page'] and v is not None}
    
    # 调用服务层获取筛选后的分页数据
    paged_models = mapping_service.get_device_models_paged(page, per_page, filter_params)
    
    return response_data(data=paged_models, schema=device_model_schema)


@mapping_bp.route('/database/size', methods=['GET'])
@jwt_required()
@require_permissions('DatabaseManagement')
def get_database_size():
    """获取rms数据库大小"""
    try:
        # 获取rms数据库总大小
        query = text("""
            SELECT 
                ROUND(SUM(data_length + index_length) / 1024 / 1024, 2) AS db_size_mb
            FROM information_schema.tables 
            WHERE table_schema = 'rms'
        """)
        result = db.session.execute(query).fetchone()
        db_size_mb = result[0] if result[0] else 0
        
        return {
            'database_name': 'rms',
            'total_size_mb': float(db_size_mb)
        }, 200
        
    except Exception as e:
        return {"error": f"获取数据库大小失败: {str(e)}"}, 500