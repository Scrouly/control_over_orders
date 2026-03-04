from django.urls import path

from .views import health_view

app_name = 'telegram'

urlpatterns = [
    path('health/', health_view, name='health'),
]
