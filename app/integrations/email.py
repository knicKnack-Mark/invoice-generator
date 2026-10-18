import asyncio
import base64
import logging
import smtplib
from abc import ABC, abstractmethod
from email.message import EmailMessage
from email.utils import formataddr

import httpx

from app.core.config import settings

logger = logging.getLogger("app.email")
if not logger.handlers:
    # uvicorn only configures its own loggers, so without this handler INFO
    # messages from the console backend would be silently dropped.
    _handler = logging.StreamHandler()
    _handler.setFormatter(logging.Formatter("%(levelname)s:     %(message)s"))
    logger.addHandler(_handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False


class EmailBackend(ABC):
    @abstractmethod
    async def send(
        self, *, to: str, subject: str, html_body: str, from_name: str | None = None,
        attachments: list[tuple[str, bytes, str]] | None = None,
    ) -> None:
        """attachments: list of (filename, content, mime_type)."""


class ConsoleEmailBackend(EmailBackend):
    """Development backend that prints email content instead of sending it."""

    async def send(
        self, *, to: str, subject: str, html_body: str,
        from_name: str | None = None, attachments=None,
    ) -> None:
        if settings.environment == "development":
            names = [a[0] for a in (attachments or [])]
            logger.info("EMAIL (console backend) -> to=%s subject=%r attachments=%s\n%s", to, subject, names, html_body)
        else:
            # Reset links are credentials, so the body must never be logged outside development.
            logger.warning("EMAIL_BACKEND=console outside development: email to %s (%r) was NOT sent.", to, subject)


class ResendEmailBackend(EmailBackend):
    """Email delivery through the Resend HTTP API."""

    endpoint = "https://api.resend.com/emails"

    def __init__(self, *, api_key: str, from_address: str):
        self.api_key = api_key
        self.from_address = from_address

    async def send(
        self, *, to: str, subject: str, html_body: str,
        from_name: str | None = None, attachments=None,
    ) -> None:
        payload = {
            "from": formataddr((from_name, self.from_address)) if from_name else self.from_address,
            "to": [to],
            "subject": subject,
            "html": html_body,
        }
        if attachments:
            payload["attachments"] = [
                {
                    "filename": filename,
                    "content": base64.b64encode(content).decode("ascii"),
                    "content_type": mime_type,
                }
                for filename, content, mime_type in attachments
            ]

        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.post(
                self.endpoint,
                json=payload,
                headers={"Authorization": f"Bearer {self.api_key}"},
            )
            response.raise_for_status()


class GmailEmailBackend(EmailBackend):
    """Email delivery through Gmail's authenticated SMTP service."""

    host = "smtp.gmail.com"
    port = 465

    def __init__(self, *, email_address: str, app_password: str):
        self.email_address = email_address.strip()
        self.app_password = "".join(app_password.split())

    async def send(
        self, *, to: str, subject: str, html_body: str,
        from_name: str | None = None, attachments=None,
    ) -> None:
        message = EmailMessage()
        message["From"] = formataddr((from_name or settings.app_name, self.email_address))
        message["To"] = to
        message["Subject"] = subject
        message.set_content("This message contains HTML content. Please view it in an HTML-capable email client.")
        message.add_alternative(html_body, subtype="html")

        for filename, content, mime_type in attachments or []:
            maintype, separator, subtype = mime_type.partition("/")
            if not separator:
                maintype, subtype = "application", "octet-stream"
            message.add_attachment(
                content,
                maintype=maintype,
                subtype=subtype,
                filename=filename,
            )

        await asyncio.to_thread(self._send_message, message)

    def _send_message(self, message: EmailMessage) -> None:
        with smtplib.SMTP_SSL(self.host, self.port, timeout=20) as smtp:
            smtp.login(self.email_address, self.app_password)
            smtp.send_message(message)


def get_email_backend() -> EmailBackend:
    if settings.email_backend == "console":
        return ConsoleEmailBackend()
    if settings.email_backend == "resend":
        if not settings.resend_api_key:
            raise RuntimeError("RESEND_API_KEY is required when EMAIL_BACKEND=resend.")
        return ResendEmailBackend(
            api_key=settings.resend_api_key,
            from_address=settings.email_from_address,
        )
    if settings.email_backend == "gmail":
        if not settings.gmail_email or not settings.gmail_app_password:
            raise RuntimeError(
                "GMAIL_EMAIL and GMAIL_APP_PASSWORD are required when EMAIL_BACKEND=gmail."
            )
        return GmailEmailBackend(
            email_address=settings.gmail_email,
            app_password=settings.gmail_app_password,
        )
    raise NotImplementedError(
        f"Email backend '{settings.email_backend}' is not supported. Choose 'console', 'resend', or 'gmail'."
    )


email_backend = get_email_backend()