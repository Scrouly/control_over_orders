from django.contrib import admin, messages
from django import forms
from django.contrib.admin.widgets import FilteredSelectMultiple

# Импорт моделей из текущего приложения
from .models import Department, Position, Employee, AssignmentType, Assignment

# Импорт модели из приложения telegram (для отображения в сотрудниках)
from telegram.models import TelegramUser

# Импортируем библиотеку для Excel
from import_export import resources, fields
from import_export.widgets import ForeignKeyWidget
from import_export.admin import ImportExportModelAdmin
from import_export.formats import base_formats

# Импорт функций рассылки
from telegram.notifications import (
    process_new_assignments,
    process_deadline_extensions,
    process_reminders
)
from django.utils.html import format_html
from django.urls import reverse
from django.shortcuts import redirect
# ==========================================
# 1. ПРОСТЫЕ СПРАВОЧНИКИ
# ==========================================

class DepartmentResource(resources.ModelResource):
    class Meta:
        model = Department
        fields = ('id', 'name')
        export_order = ('id', 'name')

        # МАГИЯ ПРОПУСКА ДУБЛИКАТОВ:
        import_id_fields = ('name',)  # Ищем существующие записи по названию, а не по ID
        skip_unchanged = True  # Пропускаем строчку, если ничего не поменялось
        report_skipped = True  # Показывать пропущенные строки в отчете при импорте


class PositionResource(resources.ModelResource):
    class Meta:
        model = Position
        fields = ('id', 'name')
        export_order = ('id', 'name')

        # МАГИЯ ПРОПУСКА ДУБЛИКАТОВ:
        import_id_fields = ('name',)
        skip_unchanged = True


@admin.register(Department)
class DepartmentAdmin(ImportExportModelAdmin, admin.ModelAdmin):
    resource_class = DepartmentResource
    formats = (base_formats.XLSX, base_formats.CSV) # Оставляем только Excel и CSV
    list_display = ('id', 'name')
    search_fields = ('name',)

@admin.register(Position)
class PositionAdmin(ImportExportModelAdmin, admin.ModelAdmin):
    resource_class = PositionResource
    formats = (base_formats.XLSX, base_formats.CSV)
    list_display = ('id', 'name')
    search_fields = ('name',)

@admin.register(AssignmentType)
class AssignmentTypeAdmin(ImportExportModelAdmin, admin.ModelAdmin):
    # Видам поручений тоже можно дать импорт/экспорт на всякий случай
    formats = (base_formats.XLSX, base_formats.CSV)
    list_display = ('id', 'name')
    search_fields = ('name',)
# ==========================================
# 2. СОТРУДНИКИ И СВЯЗЬ С ТЕЛЕГРАМ
# ==========================================

# Блок для вывода Telegram-аккаунта внутри карточки сотрудника
class TelegramUserInline(admin.StackedInline):
    model = TelegramUser
    can_delete = False
    readonly_fields = ('telegram_id', 'username', 'created_at')
    fields = ('telegram_id', 'username', 'created_at')
    extra = 0

class EmployeeResource(resources.ModelResource):
    # Говорим плагину: "Когда видишь колонку department, ищи Отдел по его названию (name)"
    department = fields.Field(
        column_name='department',
        attribute='department',
        widget=ForeignKeyWidget(Department, 'name')
    )
    # То же самое для должности: ищем по названию
    position = fields.Field(
        column_name='position',
        attribute='position',
        widget=ForeignKeyWidget(Position, 'name')
    )

    class Meta:
        model = Employee
        # Указываем, какие колонки будут в нашем Excel
        fields = ('id', 'last_name', 'first_name', 'middle_name', 'department', 'position', 'is_approver', 'is_controller', 'is_active')
        export_order = fields
# Наследуемся от ImportExportModelAdmin для появления кнопок ИМПОРТ / ЭКСПОРТ
@admin.register(Employee)
class EmployeeAdmin(ImportExportModelAdmin, admin.ModelAdmin):
    formats = (base_formats.XLSX, base_formats.CSV)
    # 1. Что показываем в колонках
    list_display = ('last_name', 'first_name', 'department', 'position', 'is_approver', 'is_controller', 'is_active', 'print_button')

    # 2. Поля, на которые можно нажать, чтобы открыть карточку
    list_display_links = ('last_name', 'first_name')

    # 3. МАГИЯ: Поля, которые можно менять прямо в общем списке (без захода внутрь!)
    list_editable = ('is_approver', 'is_controller', 'is_active')

    # 4. Фильтры справа
    list_filter = ( 'is_active', 'department', 'is_approver', 'is_controller',)

    # 5. Умный поиск (ищет не только по ФИО, но и по названию отдела и должности)
    search_fields = ('last_name', 'first_name', 'middle_name', 'department__name', 'position__name')

    # 6. Пагинация: показывать по 50 человек на странице (чтобы не тормозило)
    list_per_page = 50

    # 7. Заменяем длинные выпадающие списки (select) на удобную строку поиска с автодополнением
    autocomplete_fields = ('department', 'position')

    inlines = [TelegramUserInline]

    # 8. Массовые действия для списка
    actions = ['make_active', 'make_inactive']

    @admin.action(description="✅ Отметить выбранных как РАБОТАЮЩИХ")
    def make_active(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(request, f"Восстановлено {updated} сотрудников.", messages.SUCCESS)

    @admin.action(description="❌ Отметить выбранных как УВОЛЕННЫХ")
    def make_inactive(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(request, f"Уволено {updated} сотрудников.", messages.WARNING)

    # Создаем саму кнопку
    def print_button(self, obj):
        # ИЗМЕНЕНИЕ ЗДЕСЬ:
        # Обращаемся к 'reports:executor_print' (app_name:url_name)
        url = reverse('reports:executor_print', args=[obj.pk])

        return format_html(
            '<a class="button" href="{}" target="_blank" style="background-color: #2c3e50;">🖨️ Печать</a>',
            url
        )

    print_button.short_description = "Отчет"
    print_button.allow_tags = True
# ==========================================
# 3. ПОРУЧЕНИЯ: КАСТОМНАЯ ФОРМА И АДМИНКА
# ==========================================

# Форма, которая будет показываться ТОЛЬКО при создании нового поручения
class AssignmentCreateForm(forms.ModelForm):
    # Создаем виртуальное поле для выбора нескольких исполнителей
    executors = forms.ModelMultipleChoiceField(
        queryset=Employee.objects.filter(is_active=True),
        widget=FilteredSelectMultiple('Исполнители', is_stacked=False),
        required=True,
        label="Исполнители (можно выбрать несколько)"
    )

    class Meta:
        model = Assignment
        # Исключаем стандартное одиночное поле, так как его заменит executors
        exclude = ('executor',)


@admin.register(Assignment)
class AssignmentAdmin(admin.ModelAdmin):
    # Поля, которые нельзя редактировать руками
    readonly_fields = (
        'created_at',
        'updated_at',
        'is_notified_created',
        'last_notified_deadline',
        'last_reminded_deadline'
    )

    # Как выглядит таблица
    list_display = ('document_number', 'assignment_type', 'deadline', 'executor', 'status', 'is_notified_created')
    list_filter = ('status', 'assignment_type', 'issue_date', 'deadline', 'executor', 'controller')
    search_fields = ('document_number', 'base_document_number', 'description', 'executor__last_name',
                     'executor__first_name')

    # Подключаем наши действия (кнопки)
    actions = ['action_send_new', 'action_send_extensions', 'action_send_reminders', 'action_print_selected']

    # --- Подмена формы ---
    def get_form(self, request, obj=None, **kwargs):
        if obj is None:
            # При СОЗДАНИИ нового поручения используем форму с множественным выбором
            kwargs['form'] = AssignmentCreateForm
        return super().get_form(request, obj, **kwargs)

    # --- Подмена группировки полей ---
    def get_fieldsets(self, request, obj=None):
        if obj is None:
            # При СОЗДАНИИ показываем виртуальное поле 'executors'
            return (
                ('Основная информация', {
                    'fields': ('assignment_type', 'document_number', 'base_document_number', 'status')
                }),
                ('Сроки и текст', {
                    'fields': ('issue_date', 'deadline', 'description')
                }),
                ('Роли', {
                    'fields': ('executors', 'approver', 'controller')
                }),
            )
        else:
            # При РЕДАКТИРОВАНИИ (когда поручения уже разбились) показываем 'executor'
            return (
                ('Основная информация', {
                    'fields': ('assignment_type', 'document_number', 'base_document_number', 'status')
                }),
                ('Сроки и текст', {
                    'fields': ('issue_date', 'deadline', 'description')
                }),
                ('Роли', {
                    'fields': ('executor', 'approver', 'controller')
                }),
                ('Системная информация (Логи)', {
                    'fields': ('created_at', 'updated_at', 'is_notified_created', 'last_notified_deadline',
                               'last_reminded_deadline'),
                    'classes': ('collapse',)  # Скрываем под кат
                }),
            )

    @admin.action(description="🖨️ ПЕЧАТЬ выбранных (для нарезки)")
    def action_print_selected(self, request, queryset):
        # Собираем ID всех выбранных галочками поручений в строку "1,5,12"
        selected_ids = list(queryset.values_list('id', flat=True))
        ids_string = ",".join(map(str, selected_ids))

        # Генерируем ссылку на наш новый View
        url = reverse('reports:print_selected') + f'?ids={ids_string}'

        # Перенаправляем пользователя на страницу печати
        return redirect(url)

    # --- Перехват сохранения: Массовое создание поручений ---
    def save_model(self, request, obj, form, change):
        if not change:
            # СЦЕНАРИЙ: СОЗДАНИЕ НОВЫХ
            executors_list = form.cleaned_data.get('executors')

            # Сохраняем самое первое поручение стандартным способом
            obj.executor = executors_list[0]
            super().save_model(request, obj, form, change)

            # В цикле создаем независимые клоны для всех остальных исполнителей
            for executor in executors_list[1:]:
                Assignment.objects.create(
                    assignment_type=obj.assignment_type,
                    document_number=obj.document_number,
                    base_document_number=obj.base_document_number,
                    issue_date=obj.issue_date,
                    deadline=obj.deadline,
                    description=obj.description,
                    approver=obj.approver,
                    controller=obj.controller,
                    status=obj.status,
                    executor=executor  # Подставляем следующего человека
                )
        else:
            # СЦЕНАРИЙ: РЕДАКТИРОВАНИЕ СУЩЕСТВУЮЩЕГО
            super().save_model(request, obj, form, change)

    # --- Фильтры — дата дедлайна ---
    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context['deadline_filter_url'] = reverse('reports:deadline_filter')
        return super().changelist_view(request, extra_context)
    # ==========================================
    # КНОПКИ ДЛЯ ОТПРАВКИ В ТЕЛЕГРАМ
    # ==========================================

    @admin.action(description="📨 1. Отправить НОВЫЕ поручения")
    def action_send_new(self, request, queryset):
        count = process_new_assignments(queryset)
        self.message_user(request, f"Успешно отправлено {count} поручений. Статусы изменены на «В работе».",
                          messages.SUCCESS)

    @admin.action(description="⏰ 2. Отправить ИЗМЕНЕНИЯ СРОКОВ")
    def action_send_extensions(self, request, queryset):
        count = process_deadline_extensions(queryset)
        self.message_user(request, f"Успешно отправлено {count} уведомлений о сдвиге сроков.", messages.SUCCESS)

    @admin.action(description="⚠️ 3. Отправить НАПОМИНАНИЯ (горят сроки)")
    def action_send_reminders(self, request, queryset):
        count = process_reminders(queryset)
        self.message_user(request, f"Успешно отправлено {count} напоминаний.", messages.SUCCESS)