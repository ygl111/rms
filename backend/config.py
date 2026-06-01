# 导入 os 模块，用于处理文件路径和访问环境变量
import os
# 导入 python-dotenv 库中的 load_dotenv 函数
# 这个函数可以读取 .env 文件，并将其中定义的变量加载到系统的环境变量中
from dotenv import load_dotenv
from datetime import timedelta

# --- 加载环境变量 ---
# 构建 .env 文件的绝对路径。__file__ 指的是当前文件(config.py)的路径
# os.path.dirname(__file__) 获取 config.py 所在的目录
# os.path.join 将目录和 '.env' 文件名拼接起来，形成完整路径
dotenv_path = os.path.join(os.path.dirname(__file__), '.env')
# 判断 .env 文件是否存在
if os.path.exists(dotenv_path):
    # 如果存在，则加载它
    load_dotenv(dotenv_path)


# --- 基础配置类 ---
class Config:
    """
    基础配置类，包含所有环境共有的配置。
    其他特定的配置类（如开发配置、生产配置）将继承自这个类。
    """
    
    # --- 安全密钥 ---
    # Flask 和其扩展（如 Flask-Login, Flask-JWT）需要一个密钥来保证会话和数据的安全。
    # os.environ.get('SECRET_KEY') 会尝试从环境变量中读取 'SECRET_KEY' 的值。
    # 如果环境变量中没有设置，就使用 'or' 后面的默认字符串 'a-very-secret-key'。
    # 在生产环境中，您必须设置一个复杂且唯一的 SECRET_KEY 环境变量。
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'a-very-secret-key-for-dev'



    # --- SQLAlchemy 配置 ---
    # 这个配置项用于追踪对象的修改并发送信号。
    # 官方建议关闭此功能以节省资源，因为它在未来版本中将被移除。
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    

    # JWT 配置
    JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY', 'a-default-secret-key-for-dev')
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=3)
    # 告诉 JWT 去哪里找 Redis 连接, True 表示使用 app.config['REDIS_URL']
    JWT_REDIS_BLOCKLIST = True

    # Redis 配置
    REDIS_URL = os.getenv('REDIS_URL')

    # 验证码配置
    CAPTCHA_ENABLED = True  # 验证码始终启用
    CAPTCHA_EXPIRE_SECONDS = 300  # 验证码有效期(秒)，5分钟
    CAPTCHA_LENGTH = 4  # 验证码长度

    # [新增] Flask-Limiter 的配置
    # 告诉 Limiter 使用哪个 URL 作为其后端存储。
    # 我们将其设置为与应用其他部分相同的 Redis 数据库，
    # 这样所有的进程/服务器都能共享同一个速率限制计数器。
    RATELIMIT_STORAGE_URL = os.getenv('REDIS_URL')

        # --- 数据库连接配置 ---
    # 这里我们构建数据库的连接字符串（URI）。
    # 格式为: '数据库类型+驱动://用户名:密码@主机地址:端口/数据库名'
    
    # 从环境变量中获取数据库用户名，如果未设置则默认为 'root'
    DB_USER = os.environ.get('DB_USER', 'root')
    # 从环境变量中获取数据库密码，如果未设置则默认为空字符串 ''
    DB_PASSWORD = os.environ.get('DB_PASSWORD', '')
    # 从环境变量中获取数据库主机地址，如果未设置则默认为 'localhost' (本机)
    DB_HOST = os.environ.get('DB_HOST', 'localhost')
    # 从环境变量中获取数据库端口，如果未设置则默认为 '3306' (MySQL默认端口)
    DB_PORT = os.environ.get('DB_PORT', '3306')
    # 从环境变量中获取数据库名称，如果未设置则默认为 'rms'
    DB_NAME = os.environ.get('DB_NAME', 'rms')

    # 使用 f-string 格式化字符串，拼接成最终的数据库连接URI
    # 添加时区设置参数
    SQLALCHEMY_DATABASE_URI = f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}?charset=utf8mb4"

    # --- 从库 MySQL 配置（可选，默认与主库相同）---
    DB_SLAVE_HOST = os.environ.get('DB_SLAVE_HOST', DB_HOST)
    DB_SLAVE_PORT = os.environ.get('DB_SLAVE_PORT', DB_PORT)
    DB_SLAVE_USER = os.environ.get('DB_SLAVE_USER', DB_USER)
    DB_SLAVE_PASSWORD = os.environ.get('DB_SLAVE_PASSWORD', DB_PASSWORD)
    DB_SLAVE_NAME = os.environ.get('DB_SLAVE_NAME', DB_NAME)
    DB_SLAVE_URL = f"mysql+pymysql://{DB_SLAVE_USER}:{DB_SLAVE_PASSWORD}@{DB_SLAVE_HOST}:{DB_SLAVE_PORT}/{DB_SLAVE_NAME}?charset=utf8mb4"

    # SQLAlchemy binds: 'slave' 用于只读查询
    SQLALCHEMY_BINDS = {
        'slave': DB_SLAVE_URL,
    }



    # --- FTP 配置 ---
    FTP_HOST = os.environ.get('FTP_HOST')
    FTP_USER = os.environ.get('FTP_USER')
    FTP_PASS = os.environ.get('FTP_PASS')
    FTP_PATH = os.environ.get('FTP_PATH', '/firmwares')
    FTP_URL = os.environ.get('FTP_URL')

    # --- RabbitMQ 配置 ---
    # RabbitMQ 连接串（例如 amqp://user:pass@host:5672/vhost）
    RABBITMQ_URL = os.environ.get('RABBITMQ_URL')
    # 工作时长详情消息队列名
    WORKTIME_QUEUE = os.environ.get('WORKTIME_QUEUE', 'worktime_detail_queue')
    # 单消费者预取条数（未ACK上限）
    WORKTIME_PREFETCH = int(os.environ.get('WORKTIME_PREFETCH', '10'))
    # 消费失败最大重试次数（超过后建议进入DLQ）
    WORKTIME_MAX_RETRIES = int(os.environ.get('WORKTIME_MAX_RETRIES', '3'))

    # --- SMTP 邮件配置 ---
    MAIL_SERVER = os.environ.get('MAIL_SERVER', 'smtp.qq.com')
    MAIL_PORT = int(os.environ.get('MAIL_PORT', '587'))
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS', 'True').lower() in ('true', '1', 'yes')
    MAIL_USE_SSL = os.environ.get('MAIL_USE_SSL', 'False').lower() in ('true', '1', 'yes')
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME')  # QQ邮箱地址
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')  # QQ邮箱授权码
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER')  # 默认发件人

    # SQLAlchemy引擎选项，设置时区
    # --- MQTT Upgrade Adapter ---
    MQTT_BROKER_HOST = os.environ.get('MQTT_BROKER_HOST', '127.0.0.1')
    MQTT_BROKER_PORT = int(os.environ.get('MQTT_BROKER_PORT', '1883'))
    MQTT_CLIENT_ID = os.environ.get('MQTT_CLIENT_ID', 'rms-mqtt-upgrade-adapter')
    MQTT_KEEPALIVE = int(os.environ.get('MQTT_KEEPALIVE', '60'))
    MQTT_USERNAME = os.environ.get('MQTT_USERNAME')
    MQTT_PASSWORD = os.environ.get('MQTT_PASSWORD')
    MQTT_TLS_ENABLED = os.environ.get('MQTT_TLS_ENABLED', 'False').lower() in ('true', '1', 'yes')
    MQTT_TLS_INSECURE = os.environ.get('MQTT_TLS_INSECURE', 'False').lower() in ('true', '1', 'yes')
    MQTT_TLS_CA_CERT = os.environ.get('MQTT_TLS_CA_CERT')
    MQTT_TLS_CERTFILE = os.environ.get('MQTT_TLS_CERTFILE')
    MQTT_TLS_KEYFILE = os.environ.get('MQTT_TLS_KEYFILE')
    MQTT_UPGRADE_QOS = int(os.environ.get('MQTT_UPGRADE_QOS', '1'))
    MQTT_UPGRADE_SUBSCRIBE_TOPICS = os.environ.get(
        'MQTT_UPGRADE_SUBSCRIBE_TOPICS',
        'iods/+/upgrade/check/request,iods/+/upgrade/progress/report,iods/+/upgrade/result/report'
    )

    SQLALCHEMY_ENGINE_OPTIONS = {
        'connect_args': {
            'init_command': "SET time_zone = '+00:00'"
        }
    }

    # --- 分片上传配置 ---
    # 分片上传的临时目录（可通过环境变量覆盖）
    # 默认放在项目根目录下的 uploads/chunks 目录
    CHUNK_UPLOAD_DIR = os.environ.get('CHUNK_UPLOAD_DIR') or os.path.normpath(
        os.path.join(os.path.dirname(__file__), '..', 'uploads', 'chunks')
    )

# --- 开发环境配置 ---
class DevelopmentConfig(Config):
    """
    开发环境的配置。继承自 Config 类。
    """
    
    # --- 开启调试模式 ---
    # DEBUG = True 会让应用运行在调试模式下。
    # 这意味着当代码出错时，会显示一个详细的错误追踪页面。
    # 注意：在生产环境中绝对不能开启调试模式！
    DEBUG = True



    # --- Redis 配置 ---
    # 同样从环境变量读取 Redis 配置，并提供默认值
    REDIS_URL = os.environ.get('REDIS_URL')
    
    # Flask-Limiter 使用与应用相同的 Redis 配置
    RATELIMIT_STORAGE_URI = REDIS_URL
    
    # --- FTP 配置 (开发环境可以覆盖) ---
    FTP_HOST = os.environ.get('FTP_HOST', 'localhost')
    FTP_USER = os.environ.get('FTP_USER', 'ftp_user')
    FTP_PASS = os.environ.get('FTP_PASS', 'ftp_password')
    FTP_URL = os.environ.get('FTP_URL', 'ftp://localhost')


# --- 测试环境配置 ---
class TestingConfig(Config):
    """
    测试环境的配置。
    """
    # 开启测试模式
    TESTING = True
    # 使用内存中的 SQLite 数据库进行测试。
    # 这意味着测试将在一个临时的、隔离的数据库中运行，不会影响开发数据库。
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    # 测试时使用不同的 Redis 数据库，避免数据污染
    REDIS_DB = os.environ.get('REDIS_TEST_DB', '1')
    REDIS_URL = f"redis://localhost:6379/{REDIS_DB}"
    RATELIMIT_STORAGE_URI = REDIS_URL
    # 测试时可以模拟FTP
    FTP_HOST = 'localhost'
    FTP_USER = 'test_user'
    FTP_PASS = 'test_password'
    FTP_URL = 'ftp://localhost'


# --- 生产环境配置 ---
class ProductionConfig(Config):
    """
    生产环境的配置。
    """
    # 在生产环境中必须关闭调试模式
    DEBUG = False
    # 生产环境的数据库连接信息应该通过环境变量 'DATABASE_URL' 来设置
    # 这样可以避免将敏感信息写入代码中。
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL')
    # 生产环境的 Redis 连接信息也应该通过环境变量来设置
    REDIS_URL = os.environ.get('REDIS_URL')
    RATELIMIT_STORAGE_URI = REDIS_URL
    # 生产环境的FTP配置必须通过环境变量设置
    FTP_HOST = os.environ.get('FTP_HOST')
    FTP_USER = os.environ.get('FTP_USER')
    FTP_PASS = os.environ.get('FTP_PASS')
    FTP_URL = os.environ.get('FTP_URL')


# --- 配置字典 ---
# 这个字典将字符串名称映射到上面定义的配置类。
# 这样，我们就可以通过 'dev', 'test', 'prod' 这样的名字来选择使用哪个配置。
config_by_name = dict(
    dev=DevelopmentConfig,
    test=TestingConfig,
    prod=ProductionConfig
)
