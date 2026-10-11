"""Власні сторінки помилок 404 і 500."""
from django.shortcuts import render


def not_found(request, exception=None):
    return render(request, '404.html', status=404)


def server_error(request):
    return render(request, '500.html', status=500)
