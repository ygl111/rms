from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from flask_cors import CORS
from flask_jwt_extended import JWTManager # 导入 JWTManager
from flask_redis import FlaskRedis
# [新增] 导入 Limiter 相关的模块
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from werkzeug.middleware.proxy_fix import ProxyFix # [新增] 导入 ProxyFix

db = SQLAlchemy()
bcrypt = Bcrypt()
cors = CORS()
jwt = JWTManager() # 创建 JWTManager 实例
# [修改] 初始化 FlaskRedis 时，添加 decode_responses=True。
# 这个设置非常重要，它让 redis_client 在从 Redis 读取数据时，
# 自动将二进制数据 (bytes) 解码成我们更容易处理的字符串 (string)。
# 如果没有它，我们从 Redis 取出的会是 b'value' 而不是 'value'。
redis_client = FlaskRedis(decode_responses=True)

# [新增] 创建 Limiter 实例
# Limiter 的初始化需要几个关键参数：
# 1. key_func: 这是一个函数，用来生成每个请求的唯一标识符，以决定谁是“同一个用户”。
#    get_remote_address 是最常用的方法，它会返回请求方的 IP 地址。
#    这样，速率限制就是基于 IP 地址的。
# 2. default_limits: 这是一个列表，定义了全局的、应用到所有接口的默认速率限制规则。
#    这里的 "200 per day" 和 "50 per hour" 意味着同一个IP地址，
#    在一天内最多能请求200次，一个小时内最多能请求50次。
# 注意：我们没有在这里指定 storage_uri，因为 Limiter 会自动从 app.config 中
# 读取我们在上一步设置的 RATELIMIT_STORAGE_URL。
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["10000000 per day", "10000000 per hour"]
)


@jwt.token_in_blocklist_loader
def check_if_token_in_blocklist(jwt_header, jwt_payload):
    """
    [新增] 这是一个回调函数，被注册为 Flask-JWT-Extended 的“黑名单加载器”。
    当一个被 @jwt_required() 保护的接口被请求时，这个函数会自动被调用。

    :param jwt_header: JWT 的头部，包含算法等信息。我们这里用不到。
    :param jwt_payload: JWT 的载荷，这是一个字典，包含了我们最关心的信息，
                       比如 'jti' (JWT ID), 'identity' (用户ID), 'exp' (过期时间) 等。
    :return: bool. 如果返回 True，表示当前令牌在黑名单中，请求将被拒绝。
                   如果返回 False，表示令牌有效，请求将继续处理。
    """
    # 'jti' 是 JWT 的唯一身份标识符。我们在退出登录时，就是把这个 jti 存入 Redis。
    jti = jwt_payload['jti']
    
    # 我们构造一个在 Redis 中用于存储黑名单 jti 的键 (key)。
    # 加上 "jwt_blacklist:" 前缀是一种好的实践，可以避免键名冲突。
    redis_key = f"jwt_blacklist:{jti}"
    
    # 使用 redis_client.get() 来查询这个键是否存在于 Redis 中。
    token_in_redis = redis_client.get(redis_key)
    
    # 如果 token_in_redis 不是 None，就意味着我们在 Redis 中找到了这个 jti 的记录。
    # 这说明这个令牌之前已经被执行过“退出登录”操作，它已经被吊销了。
    # 所以我们返回 True，告诉 Flask-JWT-Extended 这个令牌是无效的。
    # 如果是 None，说明 Redis 中没有它的记录，它是一个有效的令牌，我们返回 False。
    return token_in_redis is not None


def init_extensions(app):
    """用app实例初始化所有Flask扩展"""
    # [新增] 使用 ProxyFix 中间件来正确处理反向代理后的真实 IP
    # 这行代码必须在 limiter 初始化之前。
    # x_for=1 表示我们信任来自直接连接到应用的一个代理（即我们的 Nginx）
    # 所设置的 X-Forwarded-For 头部。
    # ProxyFix 会自动读取请求头中的 X-Forwarded-For, X-Forwarded-Proto, 和 X-Forwarded-Host,
    # 并相应地更新 request.remote_addr, request.scheme, 和 request.host。
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)
    
    db.init_app(app)
    bcrypt.init_app(app)
    cors.init_app(app,
                  resources={r"/api/*": {"origins": "*"}},
                  supports_credentials=True)
    jwt.init_app(app) # 初始化 jwt
    redis_client.init_app(app)
    # [新增] 初始化 limiter
    # 这一步将 limiter 实例与我们的 app 彻底绑定。
    # 从此刻起，app 中配置的 RATELIMIT_STORAGE_URL 将被 limiter 使用，
    # 并且全局的速率限制规则开始在整个应用上生效。
    limiter.init_app(app)
