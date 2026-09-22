from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.exceptions import AppError
from app.middleware.csrf import CSRFMiddleware
from app.middleware.rate_limit import RateLimitMiddleware
from app.middleware.security_headers import SecurityHeadersMiddleware

app = FastAPI(title=f"{settings.app_name} API", version=settings.app_version)

# Middleware order (Starlette wraps last-added as outermost):
#   SecurityHeaders (outermost — decorates every response, even rejections)
#   -> CSRF          (blocks forged state-changing requests)
#   -> RateLimit      (blocks abusive traffic)
#   -> CORS           (innermost, closest to route handling)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(RateLimitMiddleware)
app.add_middleware(CSRFMiddleware)
app.add_middleware(SecurityHeadersMiddleware)


@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError):
    return JSONResponse(
        status_code=exc.status_code,
        content={"success": False, "message": exc.message, "error_code": exc.error_code},
    )


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content={
            "success": False,
            "message": "Validation failed.",
            "error_code": "VALIDATION_ERROR",
            "errors": exc.errors(),
        },
    )


app.include_router(api_router)
