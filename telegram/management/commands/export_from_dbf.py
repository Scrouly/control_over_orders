import os
import pandas as pd
from dbfread import DBF
from datetime import datetime
from django.core.management.base import BaseCommand
from django.db import transaction

# ВАЖНО: ЗАМЕНИТЕ 'main' на реальное название вашего приложения, если оно называется иначе
from task_control.models import Assignment, AssignmentType, Employee


class Command(BaseCommand):
    help = 'Импорт поручений напрямую из DBF файлов в базу данных'

    def add_arguments(self, parser):
        parser.add_argument('folder_path', type=str, help='Путь к папке с файлами DBF')

    def get_clean_df(self, folder_path, filename):
        """Читает DBF и очищает текстовые поля от лишних пробелов"""
        filepath = os.path.join(folder_path, filename)
        if not os.path.exists(filepath):
            self.stdout.write(self.style.WARNING(f"Файл {filename} не найден!"))
            return None

        dbf_data = DBF(filepath, encoding='cp866', char_decode_errors='replace')
        df = pd.DataFrame(iter(dbf_data))
        df = df.apply(lambda col: col.map(lambda x: x.strip() if isinstance(x, str) else x))
        return df

    def match_and_update_employee(self, fio_dbf, role=None):
        """
        Ищет сотрудника (например, 'Кобелев Д.Н.' -> 'КОБЕЛЕВ ДМИТРИЙ НИКОЛАЕВИЧ')
        и обновляет его статусы.
        """
        if not isinstance(fio_dbf, str) or not fio_dbf.strip():
            return None

        # Разбираем 'Кобелев Д.Н.' на части
        parts = fio_dbf.replace('.', ' ').split()
        if not parts:
            return None

        last_name = parts[0]
        first_initial = parts[1][0] if len(parts) > 1 else ""
        middle_initial = parts[2][0] if len(parts) > 2 else ""

        # Ищем в базе: Фамилия точно, Имя и Отчество начинаются на нужные буквы (игнорируем регистр)
        qs = Employee.objects.filter(last_name__iexact=last_name)
        if first_initial:
            qs = qs.filter(first_name__istartswith=first_initial)
        if middle_initial:
            qs = qs.filter(middle_name__istartswith=middle_initial)

        employee = qs.first()

        if employee:
            # Обновляем флаги, если нужно
            changed = False
            if not employee.is_active:
                employee.is_active = True
                changed = True

            if role == 'approver' and not employee.is_approver:
                employee.is_approver = True
                changed = True

            if role == 'controller' and not employee.is_controller:
                employee.is_controller = True
                changed = True

            if changed:
                employee.save()

        return employee

    def handle(self, *args, **options):
        folder_path = options['folder_path']
        self.stdout.write(f"Начинаем чтение DBF из: {folder_path}")

        # 1. Загружаем таблицы
        prikaz = self.get_clean_df(folder_path, 'PRIKAZ.DBF')
        sprviz = self.get_clean_df(folder_path, 'SPRVIZ.DBF')
        sprvid = self.get_clean_df(folder_path, 'SPRVID.DBF')
        sprkon = self.get_clean_df(folder_path, 'SPRKON.DBF')
        sprisp = self.get_clean_df(folder_path, 'SPRISP.DBF')

        if prikaz is None:
            self.stdout.write(self.style.ERROR("Главный файл PRIKAZ.DBF не найден. Отмена."))
            return

        # 2. Подготавливаем словари для быстрого перевода кодов в текст
        dict_viz = dict(
            zip(pd.to_numeric(sprviz['KVIZ'], errors='coerce'), sprviz['IMVI'])) if sprviz is not None else {}
        dict_vid = dict(
            zip(pd.to_numeric(sprvid['KDOC'], errors='coerce'), sprvid['NADO'])) if sprvid is not None else {}
        dict_kon = dict(
            zip(pd.to_numeric(sprkon['KKON'], errors='coerce'), sprkon['IMKO'])) if sprkon is not None else {}
        dict_isp = dict(
            zip(pd.to_numeric(sprisp['KISP'], errors='coerce'), sprisp['FIOISP'])) if sprisp is not None else {}

        count_created = 0
        count_skipped = 0

        # 3. Перебираем строки приказа и создаем записи в БД
        with transaction.atomic():
            for index, row in prikaz.iterrows():
                # Расшифровываем коды в текст
                doc_vid_text = dict_vid.get(pd.to_numeric(row.get('KDOC', 0), errors='coerce'))
                fio_viz = dict_viz.get(pd.to_numeric(row.get('KVIZ', 0), errors='coerce'))
                fio_kon = dict_kon.get(pd.to_numeric(row.get('KKON', 0), errors='coerce'))
                fio_isp = dict_isp.get(pd.to_numeric(row.get('KISP', 0), errors='coerce'))

                # --- ЧИТАЕМ ОСНОВНЫЕ ДАННЫЕ (с правильными колонками) ---
                doc_num = str(row.get('NDOC', f'Б/Н-{index}'))

                # Текст поручения
                description = row.get('TEKS')
                if not description or pd.isna(description):
                    description = 'Текст поручения отсутствует'

                # Обработка дат (конвертируем из строки в объект datetime.date)
                raw_issue = row.get('DAIZ')
                raw_deadline = row.get('DAIS')

                date_issue = pd.to_datetime(raw_issue, dayfirst=True, errors='coerce').date() if pd.notna(
                    raw_issue) else datetime.now().date()
                date_deadline = pd.to_datetime(raw_deadline, dayfirst=True, errors='coerce').date() if pd.notna(
                    raw_deadline) else datetime.now().date()

                # --- ИЩЕМ ИЛИ СОЗДАЕМ СВЯЗИ ---

                # Вид документа
                assign_type = None
                if doc_vid_text:
                    assign_type = AssignmentType.objects.filter(name__iexact=doc_vid_text).first()
                if not assign_type:
                    assign_type, _ = AssignmentType.objects.get_or_create(name=doc_vid_text or "Не указан")

                # Сотрудники
                approver = self.match_and_update_employee(fio_viz, role='approver')
                controller = self.match_and_update_employee(fio_kon, role='controller')
                executor = self.match_and_update_employee(fio_isp, role='executor')

                if not executor:
                    self.stdout.write(self.style.WARNING(
                        f"Строка {index + 1} (Док. №{doc_num}): Исполнитель '{fio_isp}' не найден в БД. Пропускаем поручение."))
                    count_skipped += 1
                    continue

                # --- СОЗДАЕМ ПОРУЧЕНИЕ В БАЗЕ ---
                Assignment.objects.create(
                    assignment_type=assign_type,
                    document_number=doc_num,
                    issue_date=date_issue,
                    deadline=date_deadline,
                    description=description,
                    executor=executor,
                    approver=approver,
                    controller=controller,
                    status=Assignment.Status.NEW
                )
                count_created += 1

        self.stdout.write(self.style.SUCCESS(f"\n--- ГОТОВО! ---"))
        self.stdout.write(self.style.SUCCESS(f"Создано поручений: {count_created}"))
        self.stdout.write(self.style.WARNING(f"Пропущено (исполнитель не найден): {count_skipped}"))