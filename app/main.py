import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.api import api_router
from app.core.config import settings
from app.core.exceptions import validation_exception_handler
from app.core.logging import configure_logging
from app.database.base import async_engine, check_database_connection
import app.models  # noqa: F401 - ensure ORM metadata is registered for migrations

configure_logging()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting up %s v%s", settings.APP_NAME, settings.VERSION)
    try:
        await check_database_connection()
        logger.info("Database connection successful!")
    except Exception as e:
        logger.error("Startup failed: %s", str(e), exc_info=True)
        raise
    yield
    logger.info("Shutting down %s", settings.APP_NAME)
    try:
        await async_engine.dispose()
    except Exception as e:
        logger.error("Error during shutdown: %s", str(e), exc_info=True)


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.VERSION,
    lifespan=lifespan,
    debug=settings.DEBUG,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.DEBUG else [],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_exception_handler(RequestValidationError, validation_exception_handler)


@app.get("/")
async def root():
    return {"message": "Hello World"}


app.include_router(api_router, prefix="/api/v1")
