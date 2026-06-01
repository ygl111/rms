# backend/__init__.py
import os
# [修改] 使用点 . 来表示相对导入，即从当前包（backend）中导入
from backend.app import create_app

config_name = os.environ.get('FLASK_CONFIG', 'dev')
app = create_app(config_name)