import base64
import logging
from abc import ABC, abstractmethod

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
        self, *, to: str, subject: str, html_body: str,
        attachments: list[tuple[str, bytes, str]] | None = None,
    ) -> None:
        """attachments: list of (filename, content, mime_type)."""


class ConsoleEmailBackend(EmailBackend):
    """Development backend that prints email content instead of sending it."""

    async def send(self, *, to: str, subject: str, html_body: str, attachments=None) -> None:
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

    async def send(self, *, to: str, subject: str, html_body: str, attachments=None) -> None:
        payload = {
            "from": self.from_address,
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
    raise NotImplementedError(
        f"Email backend '{settings.email_backend}' is not supported. Choose 'console' or 'resend'."
    )


email_backend = get_email_backend()