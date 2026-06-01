# 导入 flask_jwt_extended 中的 create_access_token 函数
from flask_jwt_extended import create_access_token

# 导入用户 DAO 和密码加密工具
from backend.user import dao as user_dao
from backend.extensions import bcrypt, redis_client
# [新增] 导入我们自己的异常类
from backend.common.exceptions import AuthenticationError
from datetime import datetime, timezone, timedelta
from captcha.image import ImageCaptcha
import random
import string
import uuid
import base64
from io import BytesIO
from flask import current_app

class AuthService:
    """认证服务类，处理登录和JWT相关逻辑"""

    def __init__(self):
        """初始化验证码图片生成器"""
        self.image_captcha = ImageCaptcha(width=160, height=60, fonts=None, font_sizes=(42, 50, 56))
    
    def _generate_captcha_code(self, length=4):
        """
        生成随机验证码文本
        :param length: 验证码长度
        :return: 验证码字符串
        """
        # 避免容易混淆的字符：0O, 1lI
        chars = string.ascii_uppercase + string.digits
        exclude_chars = set('0O1I')
        available_chars = [c for c in chars if c not in exclude_chars]
        
        return ''.join(random.choice(available_chars) for _ in range(length))
    
    def create_captcha(self):
        """
        创建验证码并存储到Redis
        :return: (captcha_id, base64_image)
        """
        # 1. 生成验证码文本
        captcha_code = self._generate_captcha_code(length=4)
        
        # 2. 生成唯一ID
        captcha_id = str(uuid.uuid4())
        
        # 3. 存储到Redis，有效期5分钟
        redis_key = f"captcha:{captcha_id}"
        redis_client.setex(redis_key, 300, captcha_code)
        
        current_app.logger.info(f"Created captcha: {captcha_id} = {captcha_code}")
        
        # 4. 生成验证码图片
        image = self.image_captcha.generate(captcha_code)
        
        # 5. 转换为base64编码
        buffer = BytesIO()
        buffer.write(image.read())
        buffer.seek(0)
        image_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
        image_data_url = f"data:image/png;base64,{image_base64}"
        
        return captcha_id, image_data_url
    
    def verify_captcha(self, captcha_id, captcha_input):
        """
        验证验证码
        :param captcha_id: 验证码ID
        :param captcha_input: 用户输入的验证码
        :return: True/False
        """
        if not captcha_id or not captcha_input:
            current_app.logger.warning("Captcha ID or input is empty")
            return False
        
        # 从Redis获取存储的验证码
        redis_key = f"captcha:{captcha_id}"
        stored_captcha = redis_client.get(redis_key)
        
        if not stored_captcha:
            current_app.logger.warning(f"Captcha not found or expired: {captcha_id}")
            return False
        
        # 处理Redis返回的数据类型（可能是bytes或str）
        if isinstance(stored_captcha, bytes):
            stored_captcha_str = stored_captcha.decode('utf-8')
        else:
            stored_captcha_str = stored_captcha
        
        # 验证码一次性使用，验证后立即删除
        redis_client.delete(redis_key)
        
        # 不区分大小写比较
        is_valid = stored_captcha_str.upper() == captcha_input.upper()
        
        if is_valid:
            current_app.logger.info(f"Captcha verified successfully: {captcha_id}")
        else:
            current_app.logger.warning(f"Captcha verification failed: {captcha_id}, expected={stored_captcha_str}, got={captcha_input}")
        
        return is_valid

    def login(self, account, password):
        """
        处理用户登录，验证成功则返回JWT。
        使用 Flask-JWT-Extended 来生成令牌。
        :param account: 用户账号
        :param password: 密码
        :return: access_token
        :raises AuthenticationError: 如果账号或密码错误、用户状态禁用
        """
        # 1. 根据用户名查找用户
        user = user_dao.get_user_by_account_login(account)

        # [修改]
        # 如果用户不存在，或者密码不匹配，都统一抛出认证失败异常
        if not user:
            raise AuthenticationError("User account does not exist.")
        if not bcrypt.check_password_hash(user.password_hash, password):
            # [修改] 抛出明确的异常
            raise AuthenticationError("Incorrect user password.")
        
        # [新增] 检查用户状态 - 只检查用户状态，不检查角色状态
        if user.status != 'active':
            raise AuthenticationError("This user account has been disabled and cannot log in.")
            
        # 3. 定义附加到 JWT 中的自定义声明 (claims)
            # 我们可以把用户的角色等非敏感信息放在这里
        additional_claims = {"role": user.role_id}
        # 4. 创建 access token
        # a. 第一个参数 'identity' 是令牌的核心身份标识，我们用 user.id
        # b. additional_claims 会被合并到 JWT 的载荷中
        access_token = create_access_token(
            identity=user.id, 
            additional_claims=additional_claims
        )
        return access_token

    def logout(self, jwt_payload):
        """
        [新增] 处理用户登出逻辑的核心方法。
        它的主要工作是计算出令牌的剩余生命周期，然后将它的 jti 以相同的生命周期存入 Redis。
        """
        # 从令牌的载荷中获取 'jti'。'jti' 是每个 JWT 的唯一标识符。
        jti = jwt_payload['jti']

        # 从载荷中获取 'exp'，这是令牌的过期时间，它是一个 Unix 时间戳 (从1970年1月1日到现在的秒数)。
        expires_timestamp = jwt_payload['exp']

        # 获取当前的 UTC 时间。我们使用 UTC 时间是为了避免时区问题，这在服务器编程中是最佳实践。
        now_timestamp = datetime.now(timezone.utc)

        # 将令牌的过期时间戳 (一个数字) 转换为一个 datetime 对象，同样设置为 UTC 时区。
        expires_datetime = datetime.fromtimestamp(expires_timestamp, tz=timezone.utc)

        # 计算出从现在到令牌过期还剩下多少时间，结果是一个 timedelta 对象。
        time_left = expires_datetime - now_timestamp

        # 构造用于存储在 Redis 中的键名。
        redis_key = f"jwt_blacklist:{jti}"

        # [修复] 调用我们从 extensions.py 导入的 redis_client 实例，而不是 self.redis_client。
        # setex 是 "SET with EXpire" 的缩写，它原子性地完成两件事：
        # 1. SET redis_key "true" (将键的值设为 "true")
        # 2. EXPIRE redis_key time_left (将这个键的过期时间设置为 time_left)
        # 这样做可以确保 Redis 不会永久存储这些已登出的令牌，它们会自动被清理。
        redis_client.setex(redis_key, time_left, "true")

# 创建一个服务实例
auth_service = AuthService()
