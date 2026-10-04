import logging
from abc import ABC, abstractmethod

from app.core.config import settings

logger = logging.getLogger("app.email")


class EmailBackend(ABC):
    @abstractmethod
    async def send(self, *, to: str, subject: str, html_body: str, attachments: list[tuple[str, bytes, str]] | None = None) -> None:
        """attachments: list of (filename, content, mime_type)."""


class ConsoleEmailBackend(EmailBackend):
    """Dev backend: logs instead of sending. Swap for SESEmailBackend /
    ResendEmailBackend / PostmarkEmailBackend later — same interface, no
    caller changes needed."""

    async def send(self, *, to: str, subject: str, html_body: str, attachments=None) -> None:
        attachment_names = [a[0] for a in (attachments or [])]
        logger.info(
            "EMAIL (console backend) -> to=%s subject=%r attachments=%s\n%s",
            to, subject, attachment_names, html_body,
        )


def get_email_backend() -> EmailBackend:
    if settings.email_backend == "console":
        return ConsoleEmailBackend()
    raise NotImplementedError(
        f"Email backend '{settings.email_backend}' is not implemented yet. "
        "Add a class implementing EmailBackend (e.g. SESEmailBackend) and wire it in."
    )


email_backend = get_email_backend()
