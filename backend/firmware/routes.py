from flask import Blueprint, request,jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from webargs import fields, validate
from webargs.flaskparser import use_args
from flask import send_file
from backend.firmware.service import firmware_service
from backend.common.exceptions import InvalidUsageError, ResourceNotFoundError, DuplicateResourceError
from backend.common.response import response_data
from backend.firmware.schema import firmware_schema,firmware_create_schema,firmware_analysis_schema,firmware_list_query_args,firmware_batch_delete_schema,firmware_export_query_args
from backend.common.jwt_util import require_permissions



# 创建固件蓝图
firmware_bp = Blueprint('firmware', __name__, url_prefix='/api/firmware')

@firmware_bp.route('/analyze', methods=['POST'])
@jwt_required()
@require_permissions('FirmwareManagement')
def analyze_firmware_route():
    """
    第一步：上传并分析固件文件。
    返回文件的元数据，用于前端展示和第二步提交。
    """
    try:
        if 'file' not in request.files:
            raise InvalidUsageError("Please select a file to upload")
        
        file = request.files['file']

        if file.filename == '':
            raise InvalidUsageError("Please select a valid file")

        # 调用服务层分析文件
        analysis_result = firmware_service.analyze_firmware_file(file)

        # 返回分析结果
        return response_data(data=analysis_result, schema=firmware_analysis_schema)
        
    except (InvalidUsageError, ResourceNotFoundError) as e:
        # 捕获我们已知的业务逻辑错误，并直接重新抛出
        # 全局错误处理器会把它格式化成正确的JSON
        raise e
    except Exception as e:
        # 只捕获真正的未知错误
        raise InvalidUsageError(f"File analysis failed: {e}")

@firmware_bp.route('/create', methods=['POST'])
@jwt_required()
@use_args(firmware_create_schema, location="json")
@require_permissions('FirmwareManagement')
def create_firmware_route(args):
    """
    第二步：创建固件记录。
    接收第一步分析出的数据和用户填写的其他数据。
    """
    try:
        # 添加上传者ID
        args['uploader_id'] = get_jwt_identity()

        # 调用服务层创建固件记录
        new_firmware = firmware_service.create_firmware_from_analysis(args)

        return response_data(data=new_firmware, schema=firmware_schema), 201
        
    except (InvalidUsageError, ResourceNotFoundError, DuplicateResourceError) as e:
        # 捕获我们已知的业务逻辑错误，并直接重新抛出
        # 全局错误处理器会把它格式化成正确的JSON
        raise e
    except Exception as e:
        # 只捕获真正的未知错误
        raise InvalidUsageError(f"Failed to create firmware: {e}")

@firmware_bp.route('', methods=['GET'])
@jwt_required()
@use_args(firmware_list_query_args, location="query")
def get_firmwares(args):
    """获取所有固件列表（支持筛选、排序、分页）"""
    try:
        page = args['page']
        per_page = args['per_page']
        sort_by = args.get('sort_by', 'uploaded_at')
        sort_order = args.get('sort_order', 'desc')
        filter_params = {k: v for k, v in args.items() if k not in ['page', 'per_page', 'sort_by', 'sort_order'] and v is not None}
        paged_firmwares = firmware_service.get_paged_firmwares(page, per_page, filter_params, sort_by, sort_order)
        return response_data(data=paged_firmwares, schema=firmware_schema)
    except Exception as e:
        raise InvalidUsageError(f"Failed to get firmware list: {e}")

@firmware_bp.route('/<string:firmware_id>', methods=['DELETE'])
@jwt_required()
@require_permissions('FirmwareManagement')
def delete_firmware(firmware_id):
    """删除固件（逻辑删除）"""
    try:
        firmware_service.delete_firmware(firmware_id)
        return jsonify({"message": "Firmware successfully deleted"}), 200
    except ResourceNotFoundError as e:
        raise e
    except Exception as e:
        raise InvalidUsageError(f"Failed to delete firmware, unknown error occurred: {e}")

@firmware_bp.route('/batch-delete', methods=['DELETE'])
@jwt_required()
@use_args(firmware_batch_delete_schema, location="json")
@require_permissions('FirmwareManagement')
def batch_delete_firmwares(args):
    """批量删除固件（逻辑删除）"""
    try:
        firmware_ids = args['firmware_ids']
        count=len(firmware_ids)
        if not firmware_ids:
            raise InvalidUsageError("Please provide a list of firmware IDs to delete")
        delete_count = firmware_service.batch_delete_firmwares(firmware_ids)
        
        return jsonify({"total_count": count,
                        "delete_count": delete_count,
                        "not_delete_count":count-delete_count}), 200
    except Exception as e:
        raise InvalidUsageError(f"Batch deletion failed: {e}")

@firmware_bp.route('/export', methods=['GET'])
@jwt_required()
@use_args(firmware_export_query_args, location="query")
@require_permissions('FirmwareManagement')
def export_firmwares(args):
    """导出固件数据为Excel文件（支持筛选和排序）"""
    try:
        sort_by = args.get('sort_by', 'uploaded_at')
        sort_order = args.get('sort_order', 'desc')
        filter_params = {k: v for k, v in args.items() if k not in ['page', 'per_page', 'sort_by', 'sort_order'] and v is not None}
        excel_buffer, filename = firmware_service.export_firmwares(filter_params, sort_by, sort_order)

        return send_file(
            excel_buffer,
            as_attachment=True,
            download_name=filename,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
    except Exception as e:
        raise InvalidUsageError(f"Export failed: {e}")


@firmware_bp.route('/chunk', methods=['POST'])
@jwt_required()
@require_permissions('FirmwareManagement')
def upload_chunk():
    """
    分片上传接口（支持断点续传）
    
    请求参数（multipart/form-data）：
    - file: 当前分片的二进制数据（可选，仅查询状态时可不传）
    - chunk_index: int，当前分片索引（从1开始）
    - total_chunks: int，总分片数
    - filename: str，原始文件名（用于提取版本、定位会话）
    - last_modified: str，文件最后修改时间（客户端提供，用于定位会话）
    
    响应格式：
    - 未完成（还缺分片）：
      {
        "status": "partial",
        "next_index": 5,  # 下一个需要上传的分片索引
        "saved": true,    # 本次分片是否保存成功
        "total_chunks": 10,
        "upload_key": "abc123..."  # 会话key（可选）
      }
    - 已完成（所有分片已到齐并合并）：
      {
        "status": "complete",
        "analysis": {
          "firmware_name": "xxx.bin",
          "version": "1.0-2024",
          "md5_hash": "abc123...",
          "file_size": 12345
        },
        "next_action": "POST /api/firmware/create"
      }
    """
    try:
        # 1. 获取必要参数
        chunk_index = request.form.get('chunk_index', type=int)
        total_chunks = request.form.get('total_chunks', type=int)
        filename = request.form.get('filename')
        last_modified = request.form.get('last_modified')
        uploader_id = get_jwt_identity()
        
        # 2. 参数校验
        if not filename:
            raise InvalidUsageError("filename is required")
        if not last_modified:
            raise InvalidUsageError("last_modified is required")
        if not chunk_index or chunk_index < 1:
            raise InvalidUsageError("chunk_index must be >= 1")
        if not total_chunks or total_chunks < 1:
            raise InvalidUsageError("total_chunks must be >= 1")
        if chunk_index > total_chunks:
            raise InvalidUsageError("chunk_index cannot exceed total_chunks")
        
        # 3. 获取或创建分片会话目录
        folder = firmware_service.get_chunk_folder(uploader_id, filename, last_modified)
        upload_key = firmware_service._chunk_folder_key(uploader_id, filename, last_modified)
        
        # 4. 如果携带了文件，保存当前分片
        saved = False
        if 'file' in request.files:
            file = request.files['file']
            if file and file.filename:
                saved = firmware_service.save_chunk_if_absent(folder, chunk_index, file)
        
        # 5. 检查所有分片是否都已到齐
        missing_chunks = firmware_service.find_missing_chunks(folder, total_chunks)
        
        # 6. 如果还有缺失分片，返回下一个需要上传的分片索引
        if missing_chunks:
            return jsonify({
                "status": "partial",
                "next_index": missing_chunks[0],  # 返回最小的缺失分片索引
                "saved": saved,
                "total_chunks": total_chunks,
                "upload_key": upload_key
            }), 200
        
        # 7. 所有分片已到齐，开始合并
        analysis_result = firmware_service.merge_chunks_and_store_to_redis(
            folder, total_chunks, filename
        )
        
        # 8. 返回完成状态和分析结果（与 /analyze 接口返回格式一致）
        return jsonify({
            "status": "complete",
            "analysis": analysis_result,
            "next_action": "POST /api/firmware/create"
        }), 200
        
    except (InvalidUsageError, ResourceNotFoundError) as e:
        raise e
    except Exception as e:
        raise InvalidUsageError(f"Chunk upload failed: {e}")


@firmware_bp.route('/chunk', methods=['DELETE'])
@jwt_required()
@require_permissions('FirmwareManagement')
def delete_chunk_session():
    """
    删除分片会话目录（用于取消上传或清理残留分片）
    
    请求参数（JSON）：
    - filename: str，原始文件名
    - last_modified: str，文件最后修改时间
    
    响应格式：
    {
      "message": "Chunk session deleted successfully",
      "upload_key": "abc123..."
    }
    
    使用场景：
    1. 用户取消上传，需要清理已上传的分片
    2. 上传失败后重新开始，清理旧的残留分片
    3. 手动清理测试数据
    """
    try:
        # 1. 获取参数
        data = request.get_json()
        if not data:
            raise InvalidUsageError("Request body is required")
        
        filename = data.get('filename')
        last_modified = data.get('last_modified')
        uploader_id = get_jwt_identity()
        
        # 2. 参数校验
        if not filename:
            raise InvalidUsageError("filename is required")
        if not last_modified:
            raise InvalidUsageError("last_modified is required")
        
        # 3. 删除分片会话目录
        deleted, upload_key = firmware_service.delete_chunk_session(
            uploader_id, filename, last_modified
        )
        
        # 4. 返回结果
        if deleted:
            return jsonify({
                "message": "Chunk session deleted successfully",
                "upload_key": upload_key
            }), 200
        else:
            return jsonify({
                "message": "Chunk session not found or already deleted",
                "upload_key": upload_key
            }), 200
        
    except InvalidUsageError as e:
        raise e
    except Exception as e:
        raise InvalidUsageError(f"Failed to delete chunk session: {e}")




