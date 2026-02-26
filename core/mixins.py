from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect
from functools import wraps


class StaffRequiredMixin(LoginRequiredMixin):
    """
    Миксин для Class-Based Views.
    Требует: пользователь залогинен И is_staff=True.
    """
    login_url = '/login/'

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        if not request.user.is_staff:
            return redirect('core:forbidden')
        return super().dispatch(request, *args, **kwargs)


def staff_required(view_func):
    """
    Декоратор для function-based views.
    """
    @wraps(view_func)
    @login_required(login_url='/login/')
    def wrapper(request, *args, **kwargs):
        if not request.user.is_staff:
            return redirect('core:forbidden')
        return view_func(request, *args, **kwargs)
    return wrapper


# ── РОЛИ ────────────────────────────────────────────────
# Определяем роль пользователя через группы Django.
# Создайте группы в Admin: "Администраторы", "Контролирующие", "Просмотр"

ROLE_ADMIN      = 'Администраторы'
ROLE_CONTROLLER = 'Контролирующие'
ROLE_VIEWER     = 'Просмотр'


def get_user_role(user):
    """Возвращает роль пользователя."""
    if user.is_superuser:
        return ROLE_ADMIN
    groups = set(user.groups.values_list('name', flat=True))
    if ROLE_ADMIN in groups:
        return ROLE_ADMIN
    if ROLE_CONTROLLER in groups:
        return ROLE_CONTROLLER
    return ROLE_VIEWER


def is_admin(user):
    return user.is_superuser or user.groups.filter(name=ROLE_ADMIN).exists()


def is_controller(user):
    return is_admin(user) or user.groups.filter(name=ROLE_CONTROLLER).exists()
