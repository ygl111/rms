import json  # 解析消息体（JSON）
import logging  # 标准日志模块，用于输出运行状态与异常堆栈
import os  # 读取环境变量（连接串、队列名、重试参数）

import pika  # RabbitMQ Python 客户端
from flask import current_app

from backend.app import create_app  # 创建 Flask App（拿到配置、数据库上下文）
from backend.worktime.service import worktime_service  # 业务层：幂等 + 日/月汇总


class WorkTimeRabbitConsumer:
    """
    RabbitMQ 消费者：
    - 从队列读取 C++ 侧投递的 detail_id
    - 调用业务层执行幂等汇总（写入日/月表）
    - 成功后 ACK，失败后 NACK（可重试）
    """

    def __init__(self, rabbitmq_url: str, queue_name: str, prefetch: int = 10, max_retries: int = 3):
        # RabbitMQ 连接串，例如：amqp://user:pass@host:5672/vhost
        self.rabbitmq_url = rabbitmq_url
        # 业务队列名
        self.queue_name = queue_name
        # 每个消费者最多同时处理多少条“未ACK”消息（流控参数）
        self.prefetch = prefetch
        # 失败最大重试次数（超过后丢到死信或直接丢弃，取决于队列配置）
        self.max_retries = max_retries
        self.connection = None  # 连接对象（BlockingConnection）
        self.channel = None  # 信道对象（用于声明队列、消费、ACK/NACK）

    def connect(self):
        """建立连接并声明队列。"""
        # 把 amqp://... 连接串解析为 pika 参数对象
        parameters = pika.URLParameters(self.rabbitmq_url)
        # 建立到 RabbitMQ 的阻塞式连接
        self.connection = pika.BlockingConnection(parameters)
        # 在连接上打开 channel（绝大多数 RabbitMQ 操作都在 channel 上执行）
        self.channel = self.connection.channel()
        # durable=True：队列持久化（Broker 重启后队列定义仍在）
        self.channel.queue_declare(queue=self.queue_name, durable=True)
        # QoS：限制未确认消息数量，避免消费者被压垮
        self.channel.basic_qos(prefetch_count=self.prefetch)

    @staticmethod
    def _get_retry_count(properties) -> int:
        """
        从消息头中读取 x-death 计数。
        说明：只有消息被 dead-letter 过，通常才会有 x-death。
        """
        # properties 里可能没有 headers，这里统一兜底成空字典
        headers = getattr(properties, "headers", None) or {}
        # x-death 是 RabbitMQ 死信重投时的历史头，里面带 count
        deaths = headers.get("x-death", []) if isinstance(headers, dict) else []
        if deaths:
            # 取第一条 death 记录里的重试计数
            return int(deaths[0].get("count", 0))
        return 0

    def _handle_message(self, ch, method, properties, body):
        """
        单条消息处理入口。
        消息体示例：{"detail_id": "uuid"}
        """
        try:
            # 1) 解析消息体（兼容 bytes / str）
            payload = json.loads(body.decode("utf-8")) if isinstance(body, (bytes, bytearray)) else json.loads(body)
            # 约定消息字段：detail_id（由 C++ 写详情后投递）
            detail_id = payload.get("detail_id")
            # 消息缺字段，按业务错误处理
            if not detail_id:
                raise ValueError("detail_id missing in message")

            # 2) 调用业务层执行：
            #    - 幂等日志插入（已存在则视为 duplicate）
            #    - 查询详情
            #    - 更新日/月汇总
            result = worktime_service.consume_worktime_detail(detail_id)

            # 3) 处理成功或重复消息（duplicate）都 ACK，避免反复消费
            if result.get("status") in ("processed", "duplicate"):
                # processed：首次成功处理
                # duplicate：幂等判定已处理过，也应确认消息避免重复投递
                ch.basic_ack(delivery_tag=method.delivery_tag)
                return

            # 4) 其他未预期状态：先回队列重试
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)
        except Exception as exc:
            # 5) 异常分支：按重试次数决定 requeue 与否
            retry_count = self._get_retry_count(properties)
            # 带 detail_id 打日志，便于快速定位单条失败消息
            current_app.logger.error("处理消息失败 detail_id=%s, retry=%s", payload.get("detail_id") if 'payload' in locals() else None, retry_count, exc_info=exc)

            # 超过重试阈值后不再回队列（如果配置了 DLX，则会进入死信队列）
            if retry_count >= self.max_retries:
                # 超过阈值：不回队列。若配置了 DLX，会转入死信队列。
                ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
            else:
                # 未超阈值：回队列重试
                ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)

    def start(self):
        """开始消费循环（阻塞运行）。"""
        if not self.channel:
            # 首次启动先建立连接
            self.connect()
        # auto_ack=False：手动确认，确保“处理成功后再确认”
        self.channel.basic_consume(queue=self.queue_name, on_message_callback=self._handle_message, auto_ack=False)
        current_app.logger.info("WorkTime RabbitMQ consumer 启动. queue=%s", self.queue_name)
        # 进入阻塞循环，持续消费
        self.channel.start_consuming()


def run_consumer():
    """读取环境变量并启动消费者。"""
    # 尝试显式加载根目录的 .env 文件，确保独立运行时能读到配置
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass

    # 读取 Flask 配置环境（dev/test/prod）
    config_name = os.getenv("FLASK_CONFIG", "dev")
    # RabbitMQ 连接串（必填）
    rabbitmq_url = os.getenv("RABBITMQ_URL")
    # 队列名（可选，默认 worktime_detail_queue）
    queue_name = os.getenv("WORKTIME_QUEUE", "worktime_detail_queue")
    # 消费并发流控：每个消费者最多拉取多少条未确认消息
    prefetch = int(os.getenv("WORKTIME_PREFETCH", "10"))
    # 最大重试次数
    max_retries = int(os.getenv("WORKTIME_MAX_RETRIES", "3"))

    # RABBITMQ_URL 必填，否则无法连接
    if not rabbitmq_url:
        raise RuntimeError("RABBITMQ_URL is required")

    # 复用 Flask 应用上下文，便于使用现有 db/session/配置
    app = create_app(config_name)
    # 在 Flask 应用上下文中运行，确保 db/session 正常可用
    with app.app_context():
        consumer = WorkTimeRabbitConsumer(rabbitmq_url, queue_name, prefetch=prefetch, max_retries=max_retries)
        consumer.start()


if __name__ == "__main__":
    # 直接运行本文件时，启用基础日志并启动消费者
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s - %(message)s")
    run_consumer()
