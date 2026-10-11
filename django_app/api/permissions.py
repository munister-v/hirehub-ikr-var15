"""Власні permissions: ролі та доступ лише до власних об'єктів (чужі — заборонені)."""
from accounts.roles import is_candidate, is_employer
from rest_framework import permissions


class IsEmployer(permissions.BasePermission):
    message = 'Дія доступна лише роботодавцям.'

    def has_permission(self, request, view):
        return is_employer(request.user)


class IsCandidate(permissions.BasePermission):
    message = 'Дія доступна лише кандидатам.'

    def has_permission(self, request, view):
        return is_candidate(request.user)


class IsVacancyOwnerOrReadOnly(permissions.BasePermission):
    """Змінювати вакансію може лише роботодавець-власник (або адміністратор)."""
    message = 'Ви не є власником цієї вакансії.'

    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        return request.user.is_staff or (is_employer(request.user) and obj.company.user_id == request.user.pk)


class IsEmployerOrReadOnly(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.method in permissions.SAFE_METHODS or is_employer(request.user) or request.user.is_staff
