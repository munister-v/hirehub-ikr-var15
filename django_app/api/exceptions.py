"""Єдиний формат помилок REST API: {"error": {"code": "...", "message": "...", "details": ...}}."""
from rest_framework import exceptions
from rest_framework.views import exception_handler

CODES = {
    exceptions.ValidationError: 'validation_error',
    exceptions.AuthenticationFailed: 'authentication_failed',
    exceptions.NotAuthenticated: 'not_authenticated',
    exceptions.PermissionDenied: 'permission_denied',
    exceptions.NotFound: 'not_found',
    exceptions.MethodNotAllowed: 'method_not_allowed',
    exceptions.Throttled: 'throttled',
}


def _code(exc) -> str:
    for cls, code in CODES.items():
        if isinstance(exc, cls):
            return code
    return getattr(exc, 'default_code', 'error')


def unified_exception_handler(exc, context):
    response = exception_handler(exc, context)
    if response is None:   # необроблені виключення: відповідь 500 формує Django
        return None
    data = response.data
    if isinstance(exc, exceptions.ValidationError):
        message, details = 'Некоректні дані запиту.', data
    else:
        message = str(data.get('detail', exc)) if isinstance(data, dict) else str(data)
        details = None
    response.data = {'error': {'code': _code(exc), 'message': message, 'details': details}}
    return response
