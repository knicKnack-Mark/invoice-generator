import logging
from abc import ABC, abstractmethod

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
    """Dev backend: prints the email instead of sending it. Swap for an SES /
    Resend / Postmark / SMTP backend later; callers don't change."""

    async def send(self, *, to: str, subject: str, html_body: str, attachments=None) -> None:
        if settings.environment == "development":
            names = [a[0] for a in (attachments or [])]
            logger.info("EMAIL (console backend) -> to=%s subject=%r attachments=%s\n%s", to, subject, names, html_body)
        else:
            # Reset links are credentials, so the body must never be logged outside development.
            logger.warning("EMAIL_BACKEND=console outside development: email to %s (%r) was NOT sent.", to, subject)


def get_email_backend() -> EmailBackend:
    if settings.email_backend == "console":
        return ConsoleEmailBackend()
    raise NotImplementedError(
        f"Email backend '{settings.email_backend}' is not implemented yet. "
        "Add a class implementing EmailBackend and wire it in."
    )


email_backend = get_email_backend()