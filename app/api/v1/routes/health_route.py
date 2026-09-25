from fastapi import APIRouter, HTTPException, status
from app.database.base import check_database_connection
from app.core.config import settings
import logging
import time

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/health")
async def health_check():
    """Health check endpoint"""
    start_time = time.time()
    
    try:
        db_healthy = await check_database_connection()
        response_time = round((time.time() - start_time) * 1000, 2)
        
        return {
            "status": "healthy",
            "timestamp": int(time.time()),
            "version": settings.APP_VERSION,
            "database": "connected" if db_healthy else "disconnected",
            "response_time_ms": response_time
        }
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "status": "unhealthy",
                "database": "connection failed",
                "error": str(e)
            }
        )
