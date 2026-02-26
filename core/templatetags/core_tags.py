from django import template
from django.urls import resolve, Resolver404
from core.mixins import get_user_role, is_admin, is_controller

register = template.Library()


@register.simple_tag(takes_context=True)
def nav_active(context, *url_names):
    """
    Возвращает 'nav-item--active' если текущий URL совпадает
    с одним из переданных имён.

    Использование: {% nav_active 'core:dashboard' %}
    """
    request = context.get('request')
    if not request:
        return ''
    try:
        match = resolve(request.path_info)
        current = f"{match.app_name}:{match.url_name}" if match.app_name else match.url_name
        for name in url_names:
            if current == name or request.path_info.startswith(
                '/' + name.replace(':', '/').split('/')[0] + '/'
            ):
                return 'nav-item--active'
    except Resolver404:
        pass
    return ''


@register.simple_tag(takes_context=True)
def active_section(context, prefix):
    """
    Возвращает 'nav-section--open' если текущий путь начинается с prefix.
    Используется для раскрытия подменю.
    """
    request = context.get('request')
    if request and request.path_info.startswith(prefix):
        return 'nav-section--open'
    return ''


@register.filter
def user_role(user):
    return get_user_role(user)


@register.filter
def user_is_admin(user):
    return is_admin(user)


@register.filter
def user_is_controller(user):
    return is_controller(user)
