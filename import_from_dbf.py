



import os
import django
import pandas as pd
from dbfread import DBF

# 1. ИНИЦИАЛИЗАЦИЯ DJANGO
# !!! Убедись, что 'task_manager' заменено на название папки с твоим settings.py !!!
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from task_control.models import Department, Position, Employee


# --- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ---

def read_dbf_to_dataframe(file_path):
    """Читает DBF файл и возвращает DataFrame."""
    try:
        table = DBF(file_path, encoding='cp866')
        df = pd.DataFrame(iter(table))
        return df
    except Exception as e:
        print(f"Ошибка при чтении {file_path}: {e}")
        return None


def is_empty_uch(val):
    if val is None:
        return True
    if isinstance(val, str) and val.strip() == '':
        return True
    return False


def clean_key_code(val):
    """
    Превращает любое значение (123, '123 ', 123.0) в чистую строку '123'
    """
    if pd.isna(val) or val == '':
        return None
    # Преобразуем в строку
    s = str(val).strip()
    # Если вдруг там число с плавающей точкой (123.0), убираем хвост
    if s.endswith('.0'):
        s = s[:-2]
    return s


# --- ОСНОВНАЯ ЛОГИКА ---

def import_staff_to_django():
    # Проверь пути к файлам!
    lschet_path = 'C:/Users/ASUTP\Desktop/New Tabel/Timesheet/data/Tabel/LSCHET.DBF'
    dolgn_path = 'C:/Users/ASUTP\Desktop/New Tabel/Timesheet/data/Tabel/DOLGN.DBF'
    otdel_path = 'C:/Users/ASUTP\Desktop/New Tabel/Timesheet/data/Tabel/OTDEL.DBF'

    print("📂 Чтение DBF файлов...")
    df_lschet = read_dbf_to_dataframe(lschet_path)
    df_dolgn = read_dbf_to_dataframe(dolgn_path)
    df_otdel = read_dbf_to_dataframe(otdel_path)

    if df_lschet is None or df_dolgn is None or df_otdel is None:
        print("❌ Ошибка: Не удалось прочитать один из файлов.")
        return

    print("⚙️ Обработка данных...")

    # 1. Оставляем только работающих (DATA_UVL пустое)
    active_workers = df_lschet[df_lschet['DATA_UVL'].isnull()].copy()

    # 2. Фильтруем справочник отделов
    main_workshops = df_otdel[df_otdel['UCH'].apply(is_empty_uch)].copy()
    workshops_clean = main_workshops[['NO', 'ONAMED']].copy()

    # === ГЛАВНОЕ ИСПРАВЛЕНИЕ: ЧИСТКА КЛЮЧЕЙ ===
    # Приводим коды должностей к чистому строковому виду в обеих таблицах
    active_workers['clean_shdolgn'] = active_workers['SHDOLGN'].apply(clean_key_code)
    df_dolgn['clean_dshifr'] = df_dolgn['DSHIFR'].apply(clean_key_code)

    # Приводим номера цехов к чистому виду
    active_workers['clean_no'] = active_workers['NO'].apply(clean_key_code)
    workshops_clean['clean_no'] = workshops_clean['NO'].apply(clean_key_code)

    # 3. Объединяем таблицы по ОЧИЩЕННЫМ ключам
    print("🔄 Объединение таблиц (Merge)...")

    # Склеиваем с Должностями
    merged_with_dolgn = pd.merge(
        active_workers,
        df_dolgn[['clean_dshifr', 'DNAME']],
        left_on='clean_shdolgn',
        right_on='clean_dshifr',
        how='left'
    )

    # Склеиваем с Цехами
    final_merged = pd.merge(
        merged_with_dolgn,
        workshops_clean[['clean_no', 'ONAMED']],
        left_on='clean_no',
        right_on='clean_no',
        how='left'
    )

    # Заполняем пропуски
    final_merged['DNAME'] = final_merged['DNAME'].fillna('Должность не найдена')
    final_merged['ONAMED'] = final_merged['ONAMED'].fillna('Цех не найден')

    # Проверка для отладки
    empty_positions = final_merged[final_merged['DNAME'] == 'Должность не найдена']
    if not empty_positions.empty:
        print(f"⚠️ ВНИМАНИЕ: Не удалось найти должность для {len(empty_positions)} человек.")
        print("Пример проблемных кодов из LSCHET:", empty_positions['SHDOLGN'].unique()[:5])

    # Подготовка финального датафрейма
    final_df = final_merged[['ONAMED', 'FIO', 'DNAME']].copy()
    final_df.columns = ['Название цеха', 'ФИО', 'Должность']
    final_df = final_df.fillna('')

    print(f"📝 Подготовлено {len(final_df)} сотрудников. Запись в БД...")

    # --- ЗАПИСЬ В DJANGO ---

    # 1. Создаем справочник Отделов
    dept_cache = {}
    for dept_name in final_df['Название цеха'].unique():
        clean_name = str(dept_name).strip()
        if clean_name:
            obj, _ = Department.objects.get_or_create(name=clean_name)
            dept_cache[clean_name] = obj

    # 2. Создаем справочник Должностей
    pos_cache = {}
    for pos_name in final_df['Должность'].unique():
        clean_name = str(pos_name).strip()
        if clean_name:
            obj, _ = Position.objects.get_or_create(name=clean_name)
            pos_cache[clean_name] = obj

    # 3. Создаем/Обновляем Сотрудников
    count_new = 0
    count_update = 0

    for _, row in final_df.iterrows():
        fio = str(row['ФИО']).strip()
        if not fio:
            continue

        # Парсинг ФИО
        parts = fio.split()
        last_name = parts[0]
        first_name = parts[1] if len(parts) > 1 else ""
        middle_name = " ".join(parts[2:]) if len(parts) > 2 else ""

        # Получаем объекты (связи)
        dept = dept_cache.get(str(row['Название цеха']).strip())
        pos = pos_cache.get(str(row['Должность']).strip())

        # Запись
        person, created = Employee.objects.update_or_create(
            last_name=last_name,
            first_name=first_name,
            middle_name=middle_name,
            defaults={
                'department': dept,
                'position': pos,
                'is_active': True
            }
        )
        if created:
            count_new += 1
        else:
            count_update += 1

    print(f"✅ УСПЕХ! Добавлено новых: {count_new}, Обновлено: {count_update}")


if __name__ == "__main__":
    import_staff_to_django()