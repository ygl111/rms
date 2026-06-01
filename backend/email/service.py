from backend.email import dao
from backend.common.exceptions import DuplicateResourceError, ResourceNotFoundError, InvalidUsageError
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.header import Header
from flask import current_app


class UpgradeNotifyEmailService:
    """升级通知邮箱服务类"""

    def create_email(self, email_data):
        """
        创建升级通知邮箱
        :param email_data: 包含 'email' 和 'user_id' 的字典
        :return: 创建的 UpgradeNotifyEmail 对象
        :raises DuplicateResourceError: 如果邮箱地址已存在
        """
        # 检查邮箱地址是否已存在
        if dao.get_upgrade_notify_email_by_email(email_data['email']):
            raise DuplicateResourceError(f"Email address '{email_data['email']}' is already registered.")
        
        # 创建邮箱记录
        new_email = dao.add_upgrade_notify_email(email_data)
        return new_email

    def get_paged_emails(self, page, per_page, filter_params=None, sort_by=None, sort_order='desc'):
        """
        获取分页的升级通知邮箱列表，支持筛选和排序
        :param page: 页码
        :param per_page: 每页数量
        :param filter_params: 筛选条件字典
        :param sort_by: 排序字段
        :param sort_order: 排序方向 ('asc' 或 'desc')
        :return: SQLAlchemy Pagination 对象
        """
        pagination = dao.get_all_upgrade_notify_emails(page, per_page, filter_params, sort_by, sort_order)
        return pagination

    def update_email(self, email_id, update_data):
        """
        更新升级通知邮箱
        :param email_id: 要更新的邮箱ID
        :param update_data: 包含要更新字段的字典
        :return: 更新后的 UpgradeNotifyEmail 对象
        :raises ResourceNotFoundError: 如果邮箱ID不存在
        :raises DuplicateResourceError: 如果新邮箱地址已被使用
        """
        # 查找邮箱记录
        email_to_update = dao.get_upgrade_notify_email_by_id(email_id)
        if not email_to_update:
            raise ResourceNotFoundError(f"Upgrade notify email with ID '{email_id}' does not exist.")
        
        # 检查新邮箱地址是否与其他记录冲突
        new_email = update_data.get('email')
        if new_email and new_email != email_to_update.email:
            existing_email = dao.get_upgrade_notify_email_by_email(new_email)
            if existing_email:
                raise DuplicateResourceError(f"Email address '{new_email}' is already used by another record.")
        
        # 执行更新
        updated_email = dao.update_upgrade_notify_email(email_id, update_data)
        return updated_email

    def delete_email(self, email_id):
        """
        删除升级通知邮箱（物理删除）
        :param email_id: 要删除的邮箱ID
        :raises ResourceNotFoundError: 如果邮箱ID不存在
        """
        email_to_delete = dao.get_upgrade_notify_email_by_id(email_id)
        if not email_to_delete:
            raise ResourceNotFoundError(f"Upgrade notify email with ID '{email_id}' does not exist.")
        
        dao.delete_upgrade_notify_email(email_id)


class FaultNotifyEmailService:
    """故障通知邮箱服务类"""

    def create_email(self, email_data):
        """
        创建故障通知邮箱
        :param email_data: 包含 'email' 和 'user_id' 的字典
        :return: 创建的 FaultNotifyEmail 对象
        :raises DuplicateResourceError: 如果邮箱地址已存在
        """
        # 检查邮箱地址是否已存在
        if dao.get_fault_notify_email_by_email(email_data['email']):
            raise DuplicateResourceError(f"Email address '{email_data['email']}' is already registered.")
        
        # 创建邮箱记录
        new_email = dao.add_fault_notify_email(email_data)
        return new_email

    def get_paged_emails(self, page, per_page, filter_params=None, sort_by=None, sort_order='desc'):
        """
        获取分页的故障通知邮箱列表，支持筛选和排序
        :param page: 页码
        :param per_page: 每页数量
        :param filter_params: 筛选条件字典
        :param sort_by: 排序字段
        :param sort_order: 排序方向 ('asc' 或 'desc')
        :return: SQLAlchemy Pagination 对象
        """
        pagination = dao.get_all_fault_notify_emails(page, per_page, filter_params, sort_by, sort_order)
        return pagination

    def update_email(self, email_id, update_data):
        """
        更新故障通知邮箱
        :param email_id: 要更新的邮箱ID
        :param update_data: 包含要更新字段的字典
        :return: 更新后的 FaultNotifyEmail 对象
        :raises ResourceNotFoundError: 如果邮箱ID不存在
        :raises DuplicateResourceError: 如果新邮箱地址已被使用
        """
        # 查找邮箱记录
        email_to_update = dao.get_fault_notify_email_by_id(email_id)
        if not email_to_update:
            raise ResourceNotFoundError(f"Fault notify email with ID '{email_id}' does not exist.")
        
        # 检查新邮箱地址是否与其他记录冲突
        new_email = update_data.get('email')
        if new_email and new_email != email_to_update.email:
            existing_email = dao.get_fault_notify_email_by_email(new_email)
            if existing_email:
                raise DuplicateResourceError(f"Email address '{new_email}' is already used by another record.")
        
        # 执行更新
        updated_email = dao.update_fault_notify_email(email_id, update_data)
        return updated_email

    def delete_email(self, email_id):
        """
        删除故障通知邮箱（物理删除）
        :param email_id: 要删除的邮箱ID
        :raises ResourceNotFoundError: 如果邮箱ID不存在
        """
        email_to_delete = dao.get_fault_notify_email_by_id(email_id)
        if not email_to_delete:
            raise ResourceNotFoundError(f"Fault notify email with ID '{email_id}' does not exist.")
        
        dao.delete_fault_notify_email(email_id)


# 创建服务实例
upgrade_notify_email_service = UpgradeNotifyEmailService()
fault_notify_email_service = FaultNotifyEmailService()


class EmailSendService:
    """邮件发送服务类"""

    def send_email(self, email_type, subject, content, content_type='plain'):
        """
        发送邮件到指定类型的所有邮箱
        :param email_type: 邮箱类型 ('upgrade' 或 'fault')
        :param subject: 邮件主题
        :param content: 邮件内容
        :param content_type: 内容类型 ('plain' 或 'html')
        :return: 发送结果信息
        :raises InvalidUsageError: 如果配置错误或发送失败
        """
        # 获取SMTP配置
        smtp_server = current_app.config.get('MAIL_SERVER')
        smtp_port = current_app.config.get('MAIL_PORT')
        smtp_username = current_app.config.get('MAIL_USERNAME')
        smtp_password = current_app.config.get('MAIL_PASSWORD')
        sender_email = current_app.config.get('MAIL_DEFAULT_SENDER') or smtp_username
        use_tls = current_app.config.get('MAIL_USE_TLS')
        use_ssl = current_app.config.get('MAIL_USE_SSL')

        # 验证SMTP配置
        if not all([smtp_server, smtp_port, smtp_username, smtp_password]):
            raise InvalidUsageError("SMTP configuration is incomplete. Please check MAIL_SERVER, MAIL_PORT, MAIL_USERNAME, and MAIL_PASSWORD.")

        # 根据邮箱类型获取收件人列表
        if email_type == 'upgrade':
            recipients = dao.get_all_upgrade_notify_email_addresses()
        elif email_type == 'fault':
            recipients = dao.get_all_fault_notify_email_addresses()
        else:
            raise InvalidUsageError("Invalid email_type. Must be 'upgrade' or 'fault'.")

        if not recipients:
            raise InvalidUsageError(f"No recipients found for email type '{email_type}'.")

        # 创建邮件对象
        message = MIMEMultipart()
        message['From'] = Header(sender_email)
        message['To'] = Header(', '.join(recipients))
        message['Subject'] = Header(subject, 'utf-8')

        # 添加邮件正文
        message.attach(MIMEText(content, content_type, 'utf-8'))

        try:
            # 连接SMTP服务器并发送邮件
            if use_ssl:
                # 使用SSL连接（通常是465端口）
                server = smtplib.SMTP_SSL(smtp_server, smtp_port)
            else:
                # 使用普通连接
                server = smtplib.SMTP(smtp_server, smtp_port)
                if use_tls:
                    # 启用TLS加密（通常是587端口）
                    server.starttls()

            # 登录SMTP服务器
            server.login(smtp_username, smtp_password)
            
            # 发送邮件
            server.sendmail(sender_email, recipients, message.as_string())
            
            # 关闭连接
            server.quit()

            return {
                'success': True,
                'message': f'Email sent successfully to {len(recipients)} recipients.',
                'recipients': recipients
            }

        except smtplib.SMTPAuthenticationError as e:
            current_app.logger.error(f"SMTP authentication failed: {e}")
            raise InvalidUsageError("SMTP authentication failed. Please check your username and password.")
        except smtplib.SMTPException as e:
            current_app.logger.error(f"SMTP error occurred: {e}")
            raise InvalidUsageError(f"Failed to send email: {str(e)}")
        except Exception as e:
            current_app.logger.error(f"Unexpected error when sending email: {e}")
            raise InvalidUsageError(f"Unexpected error occurred: {str(e)}")


# 创建邮件发送服务实例
email_send_service = EmailSendService()
