from django.http import JsonResponse


def health_view(request):
    """Сервисный endpoint для проверки доступности telegram-приложения."""
    return JsonResponse({'status': 'ok', 'service': 'telegram'})
