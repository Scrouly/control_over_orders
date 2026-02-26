from django.contrib import admin
from .models import TelegramUser


@admin.register(TelegramUser)
class TelegramUserAdmin(admin.ModelAdmin):
    list_display = ('telegram_id', 'username', 'first_name', 'employee', 'created_at')

    # Фильтр EmptyFieldListFilter позволяет быстро найти тех, у кого поле employee пустое
    list_filter = ('created_at', ('employee', admin.EmptyFieldListFilter))

    search_fields = ('telegram_id', 'username', 'first_name', 'last_name')
    readonly_fields = ('telegram_id', 'username', 'first_name', 'last_name', 'created_at')

    fieldsets = (
        ('Данные из Telegram (заполняется ботом)', {
            'fields': ('telegram_id', 'username', 'first_name', 'last_name', 'created_at'),
            'classes': ('collapse',)  # Можно скрыть под кат, чтобы не занимало место
        }),
        ('Связь с корпоративной системой', {
            'fields': ('employee',),
            'description': 'Выберите сотрудника из базы, чтобы привязать к нему этот Telegram аккаунт. Без привязки уведомления приходить не будут.'
        }),
    )