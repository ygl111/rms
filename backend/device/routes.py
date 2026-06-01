from flask import Blueprint, jsonify, current_app, send_file, request
from urllib.parse import quote
from flask_jwt_extended import jwt_required
from webargs import fields, validate
from webargs.flaskparser import use_args

from backend.device.service import device_service
from backend.common.exceptions import InvalidUsageError, ResourceNotFoundError, DuplicateResourceError
from backend.common.response import response_data
from backend.device.schema import device_schema,device_create_schema,device_update_schema,\
    device_list_query_args,device_batch_delete_schema,device_batch_delete_result_schema,\
        device_batch_import_preview_schema,device_batch_import_confirm_schema,device_batch_import_result_schema
from backend.common.jwt_util import require_permissions

# 创建蓝图
device_bp = Blueprint('device', __name__, url_prefix='/api/devices')


# --- Device Routes ---

@device_bp.route('', methods=['POST'])
@jwt_required()
@use_args(device_create_schema, location="json")
@require_permissions('DeviceManagement')
def create_device(args):
    """创建新设备"""
    try:
        new_device = device_service.create_device(args)
        return response_data(data=new_device, schema=device_schema), 201
    except (InvalidUsageError, DuplicateResourceError) as e:
        # 捕获我们已知的业务逻辑错误，并直接重新抛出
        # 全局错误处理器会把它格式化成正确的JSON
        raise e
    except Exception as e:
        # 只捕获真正的未知错误
        raise InvalidUsageError(f"Failed to create device: {e}")

@device_bp.route('', methods=['GET'])
@jwt_required()
@use_args(device_list_query_args, location="query")
def get_devices(args):
    """获取设备列表（支持筛选、排序和分页）"""
    # 提取分页参数
    page = args['page']
    per_page = args['per_page']
    
    # 提取筛选参数（去除分页和排序参数）
    filter_params = {k: v for k, v in args.items() 
                    if k not in ['page', 'per_page', 'sort_by', 'sort_order'] and v is not None}
    
    # 提取排序参数
    sort_by = args.get('sort_by')
    sort_order = args.get('sort_order')
    
    # 调用服务层获取分页数据
    paged_devices = device_service.get_paged_devices(page, per_page, filter_params, sort_by, sort_order)
    
    return response_data(data=paged_devices, schema=device_schema)

@device_bp.route('/<string:device_id>', methods=['PUT', 'PATCH'])
@jwt_required()
@use_args(device_update_schema, location="json")
@require_permissions('DeviceManagement')
def update_device(args, device_id):
    """更新设备信息"""
    try:
        updated_device = device_service.update_device(device_id, args)
        return response_data(data=updated_device, schema=device_schema)
    except ResourceNotFoundError as e:
        raise e
    except Exception as e:
        raise InvalidUsageError(f"Failed to update device, unknown error occurred: {e}")

@device_bp.route('/<string:device_id>', methods=['DELETE'])
@jwt_required()
@require_permissions('DeviceManagement')
def delete_device(device_id):
    """删除设备（逻辑删除）"""
    try:
        device_service.delete_device(device_id)
        return jsonify({"message": "Device deleted successfully"}), 200
    except ResourceNotFoundError as e:
        raise e
    except Exception as e:
        raise InvalidUsageError(f"Failed to delete device, unknown error occurred: {e}")

@device_bp.route('/batch-delete', methods=['DELETE'])
@jwt_required()
@use_args(device_batch_delete_schema, location="json")
@require_permissions('DeviceManagement')
def delete_devices_batch(args):
    """批量删除设备（逻辑删除）"""
    try:
        # 从经过验证的参数中获取设备ID列表
        device_ids = args['device_ids']
        
        # 调用服务层进行批量删除
        result = device_service.delete_devices_batch(device_ids)
        
        # 使用 response_data 统一返回格式，并指定 schema 进行序列化
        return response_data(
            data=result, 
            schema=device_batch_delete_result_schema
        ), 200
        
    except InvalidUsageError as e:
        raise e
    except Exception as e:
        # 捕获其他可能的未知错误，并记录日志
        current_app.logger.error(f"批量删除设备时发生错误: {e}")
        raise InvalidUsageError(f"Batch deletion failed, unknown error occurred: {e}")

@device_bp.route('/export', methods=['GET'])
@jwt_required()
@use_args(device_list_query_args, location="query")
@require_permissions('DeviceManagement')
def export_devices(args):
    """导出设备数据为Excel（支持筛选和排序）"""
    sort_by = args.get('sort_by', 'last_online_time')
    sort_order = args.get('sort_order', 'desc')
    filter_params = {k: v for k, v in args.items() if k not in ['page', 'per_page', 'sort_by', 'sort_order'] and v is not None}
    
    try:
        excel_buffer, filename = device_service.export_devices(filter_params, sort_by, sort_order)
        return send_file(
            excel_buffer,
            as_attachment=True,
            download_name=filename,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
    except Exception as e:
        raise InvalidUsageError(f"Failed to export device data: {e}")

@device_bp.route('/batch-import/preview', methods=['POST'])
@jwt_required()
@require_permissions('DeviceManagement')
def batch_import_preview():
    """
    批量导入设备 - 第一步：预览Excel文件内容
    前端上传Excel文件，后端解析并返回可导入和不可导入的记录统计
    """
    try:
        # 检查是否有上传的文件
        if 'file' not in request.files:
            raise InvalidUsageError("Please upload an Excel file.")
        
        file = request.files['file']
        if file.filename == '':
            raise InvalidUsageError("No file selected.")
        
        # 检查文件类型
        if not file.filename.lower().endswith(('.xlsx', '.xls')):
            raise InvalidUsageError("Only Excel file format is supported (.xlsx or .xls).")
        
        # 调用服务层处理Excel文件
        result = device_service.preview_batch_import(file)
        
        # 使用response_data统一返回格式
        return response_data(data=result, schema=device_batch_import_preview_schema), 200
        
    except InvalidUsageError as e:
        raise e
    except Exception as e:
        current_app.logger.error(f"批量导入预览时发生错误: {e}")
        raise InvalidUsageError(f"File parsing failed, unknown error occurred: {e}")

@device_bp.route('/batch-import/confirm', methods=['POST'])
@jwt_required()
@use_args(device_batch_import_confirm_schema, location="json")
@require_permissions('DeviceManagement')
def batch_import_confirm(args):
    """
    批量导入设备 - 第二步：确认导入
    根据缓存键从Redis获取数据，执行实际的导入操作
    """
    try:
        # 从验证后的参数中获取导入令牌
        cache_key = args['import_token']
        
        # 调用服务层执行导入
        result = device_service.confirm_batch_import(cache_key)
        
        # 如果有失败记录的Excel文件，返回文件下载
        if result.get('has_failed_file') and 'excel_buffer' in result:
            excel_buffer = result['excel_buffer']
            filename = result['filename']
            
            # 返回Excel文件下载
            return send_file(
                excel_buffer,
                as_attachment=True,
                download_name=filename,
                mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            )
        else:
            # 没有失败记录，返回JSON结果
            return response_data(data=result, schema=device_batch_import_result_schema), 200
        
    except InvalidUsageError as e:
        raise e
    except Exception as e:
        current_app.logger.error(f"批量导入确认时发生错误: {e}")
        raise InvalidUsageError(f"Batch import failed, unknown error occurred: {e}")

@device_bp.route('/batch-import/template', methods=['GET'])
@jwt_required()
@require_permissions('DeviceManagement')
def download_import_template():
    """
    下载设备批量导入的Excel模板文件
    返回包含标准表头的空Excel文件
    """
    try:
        # 调用服务层生成模板文件
        excel_buffer, filename = device_service.create_import_template()
        
        # 返回Excel文件下载
        return send_file(
            excel_buffer,
            as_attachment=True,
            download_name=filename,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        
    except Exception as e:
        current_app.logger.error(f"生成导入模板时发生错误: {e}")
        raise InvalidUsageError(f"Failed to generate template, unknown error occurred: {e}")
