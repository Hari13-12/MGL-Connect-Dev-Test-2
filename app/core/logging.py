import logging

from app.core.config import settings


def configure_logging() -> None:
    """Configure root logging for the application."""
    logging.basicConfig(
        level=logging.DEBUG if settings.DEBUG else logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
