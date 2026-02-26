from django.db import models
# Импортируем модель Employee из приложения assignments
from task_control.models import Employee


class TelegramUser(models.Model):
    telegram_id = models.CharField(max_length=100, unique=True, verbose_name="Telegram ID")
    username = models.CharField(max_length=255, null=True, blank=True, verbose_name="Никнейм (@username)")
    first_name = models.CharField(max_length=255, null=True, blank=True, verbose_name="Имя в TG")
    last_name = models.CharField(max_length=255, null=True, blank=True, verbose_name="Фамилия в TG")

    # Связываем с сотрудником из другого приложения
    employee = models.OneToOneField(
        Employee,  # Используем импортированную модель
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='telegram_profile',
        verbose_name="Сотрудник в базе"
    )

    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата первого запуска (/start)")

    def __str__(self):
        name = self.first_name or ""
        if self.last_name:
            name += f" {self.last_name}"
        username = f" (@{self.username})" if self.username else ""
        return f"{name}{username} [{self.telegram_id}]"

    class Meta:
        verbose_name = "Пользователь бота"
        verbose_name_plural = "Пользователи бота"
        ordering = ['-created_at']