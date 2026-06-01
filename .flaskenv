# FLASK_APP 指向我们的应用实例或工厂的位置
# 格式是 `目录.文件名:工厂函数名`
FLASK_APP=backend.app:create_app
# FLASK_DEBUG=1 会让应用以调试模式运行
FLASK_DEBUG=1
# FLASK_CONFIG 指定了我们想用哪个配置 (dev, prod, test)
FLASK_CONFIG=dev 