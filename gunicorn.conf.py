import multiprocessing
import os
base_dir = os.path.dirname(os.path.abspath(__file__))

bind = "127.0.0.1:8000"

workers = 16

worker_class = 'sync'

timeout=300
keepalive =2

accesslog = os.path.join(base_dir,"logs","access.log")
errorlog = os.path.join(base_dir,"logs","error.log")
loglevel="debug"




#user = "www-data"

#group = "www-data"



