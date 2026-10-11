"""Централізована обробка помилок: усі відповіді мають формат {"error": {"code", "message", "details"}}."""
import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger(__name__)


class AppError(Exception):
    status_code = 400
    code = 'bad_request'

    def __init__(self, message: str, *, details=None):
        super().__init__(message)
        self.message = message
        self.details = details


class NotFoundError(AppError):
    status_code = 404
    code = 'not_found'


class ConflictError(AppError):
    status_code = 409
    code = 'conflict'


class UnauthorizedError(AppError):
    status_code = 401
    code = 'unauthorized'


class ForbiddenError(AppError):
    status_code = 403
    code = 'forbidden'


def _payload(code, message, details=None):
    return {'error': {'code': code, 'message': message, 'details': details}}


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def app_error(_: Request, exc: AppError):
        headers = {'WWW-Authenticate': 'Bearer'} if exc.status_code == 401 else None
        return JSONResponse(_payload(exc.code, exc.message, exc.details), status_code=exc.status_code, headers=headers)

    @app.exception_handler(RequestValidationError)
    async def validation_error(_: Request, exc: RequestValidationError):
        details = [{'loc': list(e['loc']), 'msg': e['msg'], 'type': e['type']} for e in exc.errors()]
        return JSONResponse(_payload('validation_error', 'Некоректні дані запиту.', details), status_code=422)

    @app.exception_handler(StarletteHTTPException)
    async def http_error(_: Request, exc: StarletteHTTPException):
        return JSONResponse(_payload(f'http_{exc.status_code}', str(exc.detail)), status_code=exc.status_code)

    @app.exception_handler(Exception)
    async def unexpected(_: Request, exc: Exception):
        logger.exception('Необроблена помилка', exc_info=exc)
        return JSONResponse(_payload('server_error', 'Внутрішня помилка сервера.'), status_code=500)
