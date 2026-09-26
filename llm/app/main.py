from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.api.routes import router
from app.core.errors import AnalysisError


def create_app() -> FastAPI:
    application = FastAPI(
        title="Email Social-Engineering Analysis",
        version="0.1.0",
        description="Validate email evidence and return a structured AI assessment.",
    )

    @application.exception_handler(AnalysisError)
    async def analysis_error_handler(request: Request, exc: AnalysisError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": {"code": exc.code, "message": exc.message}},
        )

    @application.exception_handler(RequestValidationError)
    async def request_error_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        # Do not reflect raw email content or validation context into error responses.
        errors = [
            {"loc": error["loc"], "msg": error["msg"], "type": error["type"]}
            for error in exc.errors()
        ]
        return JSONResponse(status_code=422, content={"detail": errors})

    application.include_router(router)
    return application


app = create_app()
