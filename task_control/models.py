from django.db import models
from django.utils.translation import gettext_lazy as _


# 1. Справочник структурных подразделений
class Department(models.Model):
    name = models.CharField(max_length=150, unique=True, verbose_name="Структурное подразделение")

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Подразделение"
        verbose_name_plural = "Структурные подразделения"


# 2. Справочник должностей
class Position(models.Model):
    name = models.CharField(max_length=150, unique=True, verbose_name="Должность")

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Должность"
        verbose_name_plural = "Должности"


# 3. Самостоятельная модель Сотрудника (НЕ привязана к пользователям сайта)
class Employee(models.Model):
    last_name = models.CharField(max_length=100, verbose_name="Фамилия")
    first_name = models.CharField(max_length=100, verbose_name="Имя")
    middle_name = models.CharField(max_length=100, blank=True, verbose_name="Отчество")

    department = models.ForeignKey('Department', on_delete=models.SET_NULL, null=True, blank=True,
                                   verbose_name="Подразделение")
    position = models.ForeignKey('Position', on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Должность")

    # ПОЛЕ telegram_id УДАЛЕНО ОТСЮДА (теперь оно в модели TelegramUser)

    is_approver = models.BooleanField(default=False, verbose_name="Может быть визирующим")
    is_controller = models.BooleanField(default=False, verbose_name="Может быть контролирующим")
    is_active = models.BooleanField(default=True, verbose_name="Работает (активен)")

    # Удобное свойство, чтобы не переписывать код рассылки (notifications.py)
    @property
    def telegram_id(self):
        # Проверяем, привязан ли к сотруднику профиль из Telegram
        if hasattr(self, 'telegram_profile') and self.telegram_profile:
            return self.telegram_profile.telegram_id
        return None

    def __str__(self):
        dept = f" ({self.department.name})" if self.department else ""
        return f"{self.last_name} {self.first_name} {self.middle_name}".strip() + dept

    class Meta:
        verbose_name = "Сотрудник"
        verbose_name_plural = "Сотрудники"
        ordering = ['last_name', 'first_name']


# 4. Справочник видов поручений
class AssignmentType(models.Model):
    name = models.CharField(max_length=100, unique=True, verbose_name="Вид поручения")
    color = models.CharField(max_length=20, default='#6c757d', blank=True)
    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Вид поручения"
        verbose_name_plural = "Виды поручений"


# 5. Главная модель поручения
class Assignment(models.Model):
    class Status(models.TextChoices):
        NEW = 'NEW', _('Новое')
        IN_PROGRESS = 'IN_PROGRESS', _('В работе')
        DONE = 'DONE', _('Исполнено')
        OVERDUE = 'OVERDUE', _('Просрочено')

    assignment_type = models.ForeignKey(AssignmentType, on_delete=models.PROTECT, verbose_name="Вид документа")
    document_number = models.CharField(max_length=50, verbose_name="Номер документа")
    base_document_number = models.CharField(max_length=50, blank=True, null=True,
                                            verbose_name="Основание (номер документа)")

    issue_date = models.DateField(verbose_name="Дата издания")
    deadline = models.DateField(verbose_name="Срок исполнения")
    description = models.TextField(verbose_name="Текст поручения")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.NEW, verbose_name="Статус")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Создано")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Обновлено")

    # === НОВЫЕ ПОЛЯ ДЛЯ ЛОГИРОВАНИЯ ОТПРАВОК ===
    is_notified_created = models.BooleanField(
        default=False,
        verbose_name="Уведомление о создании отправлено"
    )
    last_notified_deadline = models.DateField(
        null=True, blank=True,
        verbose_name="Последний срок, о котором уведомляли"
    )
    last_reminded_deadline = models.DateField(
        null=True, blank=True,
        verbose_name="Срок, о котором уже было напоминание"
    )
    # Теперь связи идут к модели Employee, а не к пользователям сайта
    executor = models.ForeignKey(
        Employee,
        on_delete=models.CASCADE,
        related_name='assignments_to_execute',
        limit_choices_to={'is_active': True},
        verbose_name="Исполнитель"
    )

    approver = models.ForeignKey(
        Employee,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='assignments_to_approve',
        limit_choices_to={'is_approver': True, 'is_active': True},
        verbose_name="Визирующий"
    )

    controller = models.ForeignKey(
        Employee,
        on_delete=models.CASCADE,
        related_name='assignments_to_control',
        limit_choices_to={'is_controller': True, 'is_active': True},
        verbose_name="Контролирующий"
    )

    status = models.CharField(max_length=20, choices=Status.choices, default=Status.NEW, verbose_name="Статус")

    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Создано")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Обновлено")

    def __str__(self):
        return f"{self.assignment_type.name} №{self.document_number} от {self.issue_date}"

    class Meta:
        verbose_name = "Поручение"
        verbose_name_plural = "Поручения"
        ordering = ['-issue_date']