from backend.extensions import db
from backend.institution.model import Institution
from datetime import datetime
import uuid
from sqlalchemy.orm import joinedload, aliased
def add_institution(institution_data):
    """向数据库中添加一个新机构。"""
    new_institution = Institution(**institution_data)
    db.session.add(new_institution)
    db.session.commit()
    return new_institution

def get_institution_by_id(institution_id):
    """根据机构ID查询机构。"""
    return Institution.query.options(joinedload(Institution.parent)).filter_by(id=institution_id, is_deleted=False).first()

def get_institution_by_id_is_deleted(institution_id):
    """根据机构ID查询机构，包括逻辑删除的机构。"""
    return Institution.query.get(institution_id)

def get_institution_by_code(institution_code):
    """根据机构编码查询机构（包括已逻辑删除的）"""
    return Institution.query.filter_by(institution_code=institution_code).first()

def get_institutions_by_codes(institution_codes):
    """批量根据机构编码查询机构。"""
    if not institution_codes:
        return []
    return Institution.query.filter(
        Institution.institution_code.in_(institution_codes),
        Institution.is_deleted == False
    ).all()

def get_institution_by_ids(institution_ids):
    """根据机构ID查询机构列表"""
    if not institution_ids:
        return []
    return Institution.query.filter(
        Institution.id.in_(institution_ids),
        Institution.is_deleted == False
    ).all()


def get_all_institutions():
    """查询所有未被逻辑删除的机构。"""
    return Institution.query.options(joinedload(Institution.parent)).filter_by(is_deleted=False).all()

def get_all_institutions_paged(page, per_page, filter_params=None, sort_by=None, sort_order=None):
    """
    获取机构列表，支持筛选、排序和分页
    :param page: 页码
    :param per_page: 每页数量
    :param filter_params: 筛选条件字典
    :param sort_by: 排序字段
    :param sort_order: 排序方向 ('asc' 或 'desc')
    :return: SQLAlchemy Pagination 对象
    """

    query = Institution.query.options(joinedload(Institution.parent)).filter(Institution.is_deleted == False)
    # 应用筛选条件
    if filter_params:
        for key, value in filter_params.items():
            if key == 'status':
                # 精确匹配状态
                query = query.filter(Institution.status == value)
            elif key == 'level':
                # 精确匹配层级
                query = query.filter(Institution.level == value)
            elif key == 'parent_id':
                # 精确匹配父机构ID
                if value:
                    query = query.filter(Institution.parent_id == value)
                else:
                    query = query.filter(Institution.parent_id.is_(None))
            elif key == 'institution_name':
                # 机构名称包含匹配
                query = query.filter(Institution.institution_name.like(f"%{value}%"))
            elif key == 'institution_code':
                # 机构编码包含匹配
                query = query.filter(Institution.institution_code.like(f"%{value}%"))
            elif key == 'address':
                # 地址包含匹配
                query = query.filter(Institution.address.like(f"%{value}%"))
            elif key == 'contact_info':
                # 联系方式包含匹配
                query = query.filter(Institution.contact_info.like(f"%{value}%"))
    # 排序字段映射
    sort_columns = {
        'institution_code': Institution.institution_code,
        'institution_name': Institution.institution_name,
        'level': Institution.level,
        'status': Institution.status,
        'contact_info': Institution.contact_info,
        'address': Institution.address,
        'created_at': Institution.created_at
    }
    
    # Handle sorting by parent institution fields
    if sort_by == 'parent_institution_code':
        ParentInstitution = aliased(Institution)
        query = query.join(ParentInstitution, Institution.parent_id == ParentInstitution.id)
        sort_column = ParentInstitution.institution_code
    elif sort_by == 'parent_institution_name':
        ParentInstitution = aliased(Institution)
        query = query.join(ParentInstitution, Institution.parent_id == ParentInstitution.id)
        sort_column = ParentInstitution.institution_name
    else:
        sort_column = sort_columns.get(sort_by, Institution.level)
    
    query = query.order_by(sort_column.desc() if sort_order == 'desc' else sort_column.asc())
    return query.paginate(page=page, per_page=per_page, error_out=False)

def get_institution_children_paged(parent_id, page, per_page, sort_by='created_at', sort_order='desc'):
    """
    获取指定机构的所有子机构（分页），支持排序
    :param parent_id: 父机构ID
    :param page: 页码
    :param per_page: 每页数量
    :param sort_by: 排序字段
    :param sort_order: 排序方向 ('asc' 或 'desc')
    :return: SQLAlchemy Pagination 对象
    """
    query = Institution.query.filter(
        Institution.parent_id == parent_id,
        Institution.is_deleted == False
    )
    sort_columns = {
        'institution_code': Institution.institution_code,
        'institution_name': Institution.institution_name,
        'level': Institution.level,
        'status': Institution.status,
        'contact_info': Institution.contact_info,
        'address': Institution.address,
        'created_at': Institution.created_at
    }
    
    # Handle sorting by parent institution fields
    if sort_by == 'parent_institution_code':
        ParentInstitution = aliased(Institution)
        query = query.join(ParentInstitution, Institution.parent_id == ParentInstitution.id)
        sort_column = ParentInstitution.institution_code
    elif sort_by == 'parent_institution_name':
        ParentInstitution = aliased(Institution)
        query = query.join(ParentInstitution, Institution.parent_id == ParentInstitution.id)
        sort_column = ParentInstitution.institution_name
    else:
        sort_column = sort_columns.get(sort_by, Institution.created_at)
    
    query = query.order_by(sort_column.desc() if sort_order == 'desc' else sort_column.asc())
    return query.paginate(page=page, per_page=per_page, error_out=False)

def update_institution(institution, update_data):
    """更新一个已存在的机构。"""
    for key, value in update_data.items():
        if hasattr(institution, key):
            setattr(institution, key, value)
    db.session.commit()
    return institution

def get_institutions_for_export(filter_params=None, sort_by='level', sort_order='desc'):
    """
    获取用于导出的机构数据（不分页，返回所有符合条件的记录），支持排序
    :param filter_params: 筛选条件字典
    :param sort_by: 排序字段
    :param sort_order: 排序方向 ('asc' 或 'desc')
    :return: 机构列表
    """
    query = Institution.query.filter(Institution.is_deleted == False)
    if filter_params:
        for key, value in filter_params.items():
            if key == 'status':
                query = query.filter(Institution.status == value)
            elif key == 'level':
                query = query.filter(Institution.level == value)
            elif key == 'parent_id':
                query = query.filter(Institution.parent_id == value)
            elif key == 'institution_name':
                # 机构名称包含匹配
                query = query.filter(Institution.institution_name.like(f"%{value}%"))
            elif key == 'institution_code':
                # 机构编码包含匹配
                query = query.filter(Institution.institution_code.like(f"%{value}%"))
            elif key == 'address':
                # 地址包含匹配
                query = query.filter(Institution.address.like(f"%{value}%"))
            elif key == 'contact_info':
                # 联系方式包含匹配
                query = query.filter(Institution.contact_info.like(f"%{value}%"))
    sort_columns = {
        'institution_code': Institution.institution_code,
        'institution_name': Institution.institution_name,
        'level': Institution.level,
        'status': Institution.status,
        'contact_info': Institution.contact_info,
        'address': Institution.address,
        'created_at': Institution.created_at
    }
    
    # Handle sorting by parent institution fields
    if sort_by == 'parent_institution_code':
        ParentInstitution = aliased(Institution)
        query = query.join(ParentInstitution, Institution.parent_id == ParentInstitution.id)
        sort_column = ParentInstitution.institution_code
    elif sort_by == 'parent_institution_name':
        ParentInstitution = aliased(Institution)
        query = query.join(ParentInstitution, Institution.parent_id == ParentInstitution.id)
        sort_column = ParentInstitution.institution_name
    else:
        sort_column = sort_columns.get(sort_by, Institution.level)
    
    query = query.order_by(sort_column.desc() if sort_order == 'desc' else sort_column.asc())
    return query.all()

def add_institutions_batch(institution_data_list):
    """
    批量添加机构
    :param institution_data_list: 机构数据列表，每个元素是一个字典
    :return: (成功插入的机构ID列表, 失败的机构数据列表)
    """
    successful_ids = []
    failed_records = []
    
    try:
        # 使用bulk_insert_mappings进行批量插入
        prepared_data = []
        for record in institution_data_list:
            # 生成UUID和时间戳
            institution_id = str(uuid.uuid4())
            now = datetime.now()
            
            # 准备完整的机构数据
            full_institution_data = {
                'id': institution_id,
                'institution_code': record['institution_code'],
                'institution_name': record['institution_name'],
                'parent_id': record.get('parent_id'),
                'level': record.get('level', 1),
                'address': record.get('address'),
                'contact_info': record.get('contact_info'),
                'status': record.get('status', 'active'),
                'is_deleted': False,
                'created_at': now,
                'updated_at': now
            }
            prepared_data.append(full_institution_data)
            successful_ids.append(institution_id)
        
        # 批量插入
        db.session.bulk_insert_mappings(Institution, prepared_data)
        db.session.commit()
        
    except Exception as e:
        # 如果批量插入失败，回退到逐条插入以获取具体错误
        db.session.rollback()
        successful_ids = []
        failed_records = []
        
        for record in institution_data_list:
            try:
                institution_id = str(uuid.uuid4())
                now = datetime.now()
                
                new_institution = Institution(
                    id=institution_id,
                    institution_code=record['institution_code'],
                    institution_name=record['institution_name'],
                    parent_id=record.get('parent_id'),
                    level=record.get('level', 1),
                    address=record.get('address'),
                    contact_info=record.get('contact_info'),
                    status=record.get('status', 'active'),
                    is_deleted=False,
                    created_at=now,
                    updated_at=now
                )
                
                db.session.add(new_institution)
                db.session.commit()
                successful_ids.append(institution_id)
                
            except Exception as e:
                db.session.rollback()
                failed_records.append({
                    'institution_code': record.get('institution_code', ''),
                    'institution_name': record.get('institution_name', ''),
                    'reason': str(e)
                })
    
    return successful_ids, failed_records

def check_institutions_exist_batch(institution_codes):
    """
    批量检查机构编码是否已存在
    :param institution_codes: 机构编码列表
    :return: 已存在的机构编码集合
    """
    if not institution_codes:
        return set()


    existing_institutions = Institution.query.filter(
        Institution.institution_code.in_(institution_codes),
        Institution.is_deleted == False
    ).with_entities(Institution.institution_code).all()
    
    # 提取机构编码
    existing_codes = {institution[0] for institution in existing_institutions}
    return existing_codes

def delete_institution(institution):
    """
    逻辑删除一个机构，并修改 institution_code 字段，释放原机构编码供新机构使用。
    """
 
    # 1. 递归逻辑删除所有子机构
    def recursive_delete(inst):
        # 逻辑删除自身
        inst.is_deleted = True
        
        # 查找所有子机构
        children = Institution.query.filter_by(parent_id=inst.id).all()
        for child in children:
            recursive_delete(child)

    recursive_delete(institution)
    db.session.commit()
