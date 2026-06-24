from __future__ import annotations

from dataclasses import dataclass
from uuid import uuid4

from app.schemas.notifications import NotificationChannel, NotificationStatus


@dataclass(frozen=True)
class NotificationDeliveryResult:
    channel: NotificationChannel
    status: NotificationStatus
    provider_message_id: str | None = None
    error_message: str | None = None


class NotificationDeliveryService:
    """Provider boundary for Email/SMS delivery.

    MVP에서는 외부 벤더 연동 대신 provider_message_id를 생성하는 mock delivery를 수행한다.
    운영 단계에서는 이 클래스의 메서드를 SES, SendGrid, Twilio, NCP SENS 등으로 교체한다.
    """

    def send_email(self, to: str, subject: str, message: str) -> NotificationDeliveryResult:
        return NotificationDeliveryResult(
            channel=NotificationChannel.EMAIL,
            status=NotificationStatus.SENT,
            provider_message_id=f"email-{uuid4()}",
        )

    def send_sms(self, to: str, message: str) -> NotificationDeliveryResult:
        return NotificationDeliveryResult(
            channel=NotificationChannel.SMS,
            status=NotificationStatus.SENT,
            provider_message_id=f"sms-{uuid4()}",
        )


notification_delivery_service = NotificationDeliveryService()
