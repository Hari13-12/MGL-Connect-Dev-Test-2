from sqlalchemy.orm import DeclarativeBase, sessionmaker
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy import text
import logging
from app.core.config import settings

logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    pass


DATABASE_URL = (
    f"postgresql+asyncpg://{settings.DATABASE_USER}:{settings.DATABASE_PASSWORD}"
    f"@{settings.DATABASE_HOST}:{settings.DATABASE_PORT}/{settings.DATABASE_NAME}"
)

# Connection options for schema
CONNECT_ARGS = {
    "server_settings": {
        "search_path": settings.DATABASE_SCHEMA
    }
}

async def check_database_connection() -> bool:
    """Check database connectivity"""
    try:
        logger.info("Attempting to connect to the database ")
        test_engine = create_async_engine(
            DATABASE_URL, 
            pool_pre_ping=True,
            connect_args=CONNECT_ARGS
        )
        async with test_engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        await test_engine.dispose()
        logger.info("Database connection successful!")
        return True
    except Exception as e:
        logger.error(f"Database connection failed: {str(e)}", exc_info=True)
        raise

try:
    # Engine configuration for production
    async_engine = create_async_engine(
        DATABASE_URL,
        echo=settings.DEBUG,
        pool_pre_ping=True,
        pool_size=20,
        max_overflow=20,
        pool_recycle=3600,
        connect_args=CONNECT_ARGS,
    )
    logger.info("Async engine created successfully.")
except Exception as e:
    logger.error(f"Failed to create async engine: {str(e)}", exc_info=True)
    raise

try:
    # Modern async session factory
    AsyncSessionLocal = async_sessionmaker(
        bind=async_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
        autocommit=False,
    )
    logger.info("Async session factory created successfully.")
except Exception as e:
    logger.error(f"Failed to create async session factory: {str(e)}", exc_info=True)
    raise