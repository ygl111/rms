class ApiException(Exception):
    """所有自定义API异常的基类"""
    status_code = 500
    message = "Internal server error"

    def __init__(self, message=None, status_code=None, payload=None):
        Exception.__init__(self)
        if message is not None:
            self.message = message
        if status_code is not None:
            self.status_code = status_code
        self.payload = payload

    def to_dict(self):
        # 1. 如果 self.payload 不为空，就把它转成一个字典，否则创建一个空字典
        #extra_info = {'field': 'email', 'error_code': 'E1001'}
        #raise InvalidUsageError(message="邮箱格式错误", payload=extra_info)
        #payload也是字典格式的  所以可以直接转换
        rv = dict(self.payload or ()) 
        # 2. 在这个字典里，添加一个 'message' 键
        rv['message'] = self.message
        # 3. 返回这个构建好的字典
        return rv

class DuplicateResourceError(ApiException):
    """当资源已存在时抛出，例如用户账号已被注册。"""
    status_code = 409  # HTTP 状态码 409 Conflict
    message = "Resource already exists"

class AuthenticationError(ApiException):
    """当认证失败时抛出，例如账号或密码错误。"""
    status_code = 401  # HTTP 状态码 401 Unauthorized
    message = "Authentication failed"

class InvalidUsageError(ApiException):
    """当用户提供了无效的输入时抛出。"""
    status_code = 400 # HTTP 状态码 400 Bad Request
    message = "Invalid request" 

class ResourceNotFoundError(ApiException):
    """当请求的资源不存在时抛出，例如根据ID查找用户失败。"""
    status_code = 404 # HTTP 状态码 404 Not Found
    message = "Requested resource does not exist" 


# 新增：权限不足
class PermissionDeniedError(ApiException):
    """当用户没有访问某资源或执行某操作的权限时抛出。"""
    status_code = 403  # HTTP 状态码 403 Forbidden
    message = "Insufficient permissions"

