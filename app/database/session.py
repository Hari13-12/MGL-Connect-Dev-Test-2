from app.database.base import AsyncSessionLocal
from typing import AsyncGenerator
import logging

logger = logging.getLogger(__name__)

async def get_db() -> AsyncGenerator:
    """Database dependency for FastAPI"""
    async with AsyncSessionLocal() as session:
        try:
            logger.info("Database session created.")
            yield session
        except Exception as e:
            logger.error("Exception in DB session: %s", str(e), exc_info=True)
            await session.rollback()
            raise
        finally:
            await session.close()
            logger.info("Database session closed.")