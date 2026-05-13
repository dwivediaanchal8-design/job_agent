"""
services/notifier.py — Error Alerting Service
==============================================
Sends alerts to administrators via Email and Slack.
"""

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import httpx
from loguru import logger

from backend.config import settings

class Notifier:
    """
    Handles sending notifications through various channels.
    """

    async def send_error_alert(self, subject: str, message: str):
        """
        Send an error alert to all configured channels.
        """
        logger.warning(f"🚀 Sending error alert: {subject}")
        
        # 1. Send Slack notification (Async)
        await self.send_slack_notification(f"*[{subject}]*\n{message}")
        
        # 2. Send Email notification (Sync, run in thread to avoid blocking)
        import asyncio
        await asyncio.to_thread(self.send_email_notification, subject, message)

    async def send_slack_notification(self, message: str):
        """
        Sends a message to the configured Slack Webhook URL.
        """
        if not settings.slack_webhook_url:
            logger.debug("Slack notification skipped: No SLACK_WEBHOOK_URL configured.")
            return

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    settings.slack_webhook_url,
                    json={"text": message},
                    timeout=10.0
                )
                if response.status_code == 200:
                    logger.success("Slack notification sent successfully.")
                else:
                    logger.error(f"Failed to send Slack notification: {response.status_code} {response.text}")
        except Exception as e:
            logger.error(f"Error sending Slack notification: {e}")

    def send_email_notification(self, subject: str, message: str):
        """
        Sends an email using the configured SMTP settings.
        """
        if not all([settings.smtp_host, settings.smtp_user, settings.smtp_pass, settings.admin_email]):
            logger.debug("Email notification skipped: SMTP settings incomplete.")
            return

        try:
            msg = MIMEMultipart()
            msg["From"] = settings.smtp_user
            msg["To"] = settings.admin_email
            msg["Subject"] = f"[{settings.app_name}] {subject}"

            msg.attach(MIMEText(message, "plain"))

            with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as server:
                server.starttls()
                server.login(settings.smtp_user, settings.smtp_pass)
                server.send_message(msg)
                
            logger.success(f"Email notification sent to {settings.admin_email}")
        except Exception as e:
            logger.error(f"Error sending email notification: {e}")

# Singleton instance
notifier = Notifier()
