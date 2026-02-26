from django.core.management.base import BaseCommand
from django.utils import timezone
from task_control.models import Assignment


class Command(BaseCommand):
    help = 'Помечает просроченные поручения статусом OVERDUE'

    def handle(self, *args, **kwargs):
        today = timezone.now().date()

        updated = Assignment.objects.filter(
            status__in=['NEW', 'IN_PROGRESS'],
            deadline__lt=today,
        ).update(status='OVERDUE')

        if updated:
            self.stdout.write(
                self.style.WARNING(f'Обновлено: {updated} поручений помечены как OVERDUE')
            )
        else:
            self.stdout.write(
                self.style.SUCCESS('Просроченных поручений не найдено')
            )
