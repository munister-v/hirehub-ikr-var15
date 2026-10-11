from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from .forms import RegistrationForm
from .roles import is_candidate, is_employer


def register(request):
    if request.user.is_authenticated:
        return redirect('accounts:profile')
    form = RegistrationForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        user = form.save()
        login(request, user)
        messages.success(request, 'Вітаємо! Акаунт створено.')
        return redirect('accounts:profile')
    return render(request, 'accounts/register.html', {'form': form})


@login_required
def profile(request):
    """Точка входу після логіну: перенаправляє у кабінет відповідно до ролі."""
    if is_employer(request.user):
        return redirect('jobs:employer_dashboard')
    if is_candidate(request.user):
        return redirect('jobs:candidate_cabinet')
    return redirect('admin:index' if request.user.is_staff else 'jobs:vacancy_list')
