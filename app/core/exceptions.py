from fastapi import Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
 
async def validation_exception_handler(request: Request, exc: RequestValidationError):
   
    errors = exc.errors()
    error_messages = []
   
    for error in errors:
        field = error.get("loc", [])[-1] if error.get("loc") else "unknown"
        error_messages.append({
            "field": field,
            "message": f"Field '{field}' is required" if error.get("type") == "missing" else error.get("msg")
        })
   
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={
            "status": "error",
            "message": "Validation error",
            "errors": error_messages
        }
    )