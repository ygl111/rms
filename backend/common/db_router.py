"""
读写分离工具：从库优先，失败自动降级到主库。

日志会经由 Flask app logger 输出，gunicorn 可捕获到 errorlog。
在 gunicorn error.log 中 grep "[DB_ROUTER]" 即可过滤所有路由决策。
"""
from contextlib import contextmanager
from flask import current_app, has_app_context, request
from backend.extensions import db
from sqlalchemy import text
from sqlalchemy.orm import Session


@contextmanager
def read_session():
    """
    获取只读数据库会话。

    - 配置了从库（slave bind != master）→ 尝试从库，失败降级主库
    - 未配置从库 → 直接走主库

    每次调用会在 gunicorn error.log 中输出一行路由决策日志。
    """
    if not has_app_context():
        raise RuntimeError("read_session() 必须在 Flask 应用上下文中使用")

    app = current_app
    slave_url = app.config.get('SQLALCHEMY_BINDS', {}).get('slave')
    master_url = app.config.get('SQLALCHEMY_DATABASE_URI')
    request_path = request.path if request else ''

    if slave_url and slave_url != master_url:
        try:
            engine = db.get_engine(app, bind='slave')


            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))

            session = Session(bind=engine)

            app.logger.info(
                "[DB_ROUTER] %s -> 从库", request_path
            )

            try:
                yield session
                return
            finally:
                session.close()

        except Exception as e:
            app.logger.warning(
                "[DB_ROUTER] %s -> 从库不可用 (%s)，降级到主库",
                request_path, e
            )

    else:
        app.logger.info(
            "[DB_ROUTER] %s -> 主库 (未配置从库)",
            request_path
        )

    # 降级 / 默认：走主库
    yield db.session
