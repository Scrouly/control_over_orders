import requests
from django.conf import settings
from django.utils import timezone
from datetime import timedelta
from collections import defaultdict

from task_control.models import Assignment


# ════════════════════════════════════════════════════════
#  КОНСТАНТЫ
# ════════════════════════════════════════════════════════

TG_MAX_LEN = 4096

# Короткие разделители — не тянутся на всю ширину
DIV   = "▬▬▬▬▬▬▬▬▬▬"   # секционный
HDIV  = "──────────"     # внутри блока поручения


# ════════════════════════════════════════════════════════
#  УТИЛИТЫ
# ════════════════════════════════════════════════════════

def send_telegram_message(chat_id, text):
    token = getattr(settings, 'TELEGRAM_BOT_TOKEN', None)
    if not token or not chat_id:
        return False
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    for part in _split_message(text):
        payload = {
            'chat_id': chat_id,
            'text': part,
            'parse_mode': 'HTML',
            'disable_web_page_preview': True,
        }
        try:
            r = requests.post(url, json=payload, timeout=5)
            if r.status_code != 200:
                print(f"[TG] {r.status_code}: {r.text}")
                return False
        except Exception as e:
            print(f"[TG] Ошибка: {e}")
            return False
    return True


def _split_message(text: str) -> list[str]:
    if len(text) <= TG_MAX_LEN:
        return [text]
    parts, buf, length = [], [], 0
    for line in text.split('\n'):
        if length + len(line) + 1 > TG_MAX_LEN and buf:
            parts.append('\n'.join(buf))
            buf, length = [], 0
        buf.append(line)
        length += len(line) + 1
    if buf:
        parts.append('\n'.join(buf))
    return parts


def group_by_executor(queryset):
    grouped = defaultdict(list)
    for task in queryset:
        tg_id = task.executor.telegram_id
        if tg_id:
            grouped[tg_id].append(task)
    return grouped


def days_label(n: int) -> str:
    abs_n = abs(n)
    if abs_n % 100 in range(11, 20): return f"{abs_n} дней"
    rem = abs_n % 10
    if rem == 1:          return f"{abs_n} день"
    if rem in (2, 3, 4):  return f"{abs_n} дня"
    return f"{abs_n} дней"


def fmt_person(emp) -> str:
    if not emp: return "—"
    parts = [emp.last_name, emp.first_name]
    if emp.middle_name: parts.append(emp.middle_name)
    return " ".join(p for p in parts if p)


def fmt_short(emp) -> str:
    if not emp: return "—"
    mid = f"{emp.middle_name[0]}." if emp.middle_name else ""
    return f"{emp.last_name} {emp.first_name[0]}.{mid}"


def deadline_note(days_left: int) -> str:
    """Нейтральная информационная пометка о сроке."""
    if days_left < 0:
        return f"<i>Срок истёк {days_label(abs(days_left))} назад.</i>"
    if days_left == 0:
        return "<i>Срок исполнения — сегодня.</i>"
    if days_left == 1:
        return "<i>Срок исполнения истекает завтра.</i>"
    return f"<i>До срока исполнения: {days_label(days_left)}.</i>"


def fmt_header(title: str, emoji: str, executor) -> list[str]:
    """Шапка письма."""
    now_str = timezone.now().strftime("%d.%m.%Y,  %H:%M")
    dept = executor.department.name if executor.department else "подразделение не указано"
    pos  = executor.position.name  if executor.position  else "должность не указана"
    return [
        f"{emoji}  <b>{title}</b>",
        f"<i>ОАО «Доломит»  ·  {now_str}</i>",
        DIV,
        "",
        f"👤  <b>{fmt_person(executor)}</b>",
        f"<i>{pos}  ·  {dept}</i>",
        "",
    ]


def fmt_task_card(task, index: int, total: int) -> list[str]:
    """
    Карточка одного поручения.
    Чёткая структура: шапка → текст → реквизиты.
    """
    ctrl = fmt_short(task.controller)
    appr = fmt_short(task.approver) if task.approver else "—"
    doc  = task.assignment_type.name.upper()

    return [
        # ── Заголовок карточки ──
        f"◾  <b>ПОРУЧЕНИЕ {index} / {total}</b>",
        f"<b>{doc}</b>   <code>№ {task.document_number}</code>",
        HDIV,

        # ── Текст поручения ──
        "<b>Текст поручения:</b>",
        f"<blockquote>{task.description.strip()}</blockquote>",

        # ── Реквизиты ──
        "",
        f"📅  <b>Дата издания:</b>    {task.issue_date.strftime('%d.%m.%Y')}",
        f"⏳  <b>Срок исполнения:</b>  <u>{task.deadline.strftime('%d.%m.%Y')}</u>",
        f"👤  <b>Контролирующий:</b>  {ctrl}",
        f"✅  <b>Визирующий:</b>      {appr}",
    ]


def fmt_footer(note: str) -> list[str]:
    return [
        DIV,
        f"<i>{note}</i>",
        "<i>Уведомление сформировано автоматически.</i>",
    ]


# ════════════════════════════════════════════════════════
#  1. НОВЫЕ ПОРУЧЕНИЯ
# ════════════════════════════════════════════════════════

def process_new_assignments(queryset):
    sent_count = 0
    assignments = queryset.filter(is_notified_created=False)
    grouped = group_by_executor(assignments)

    for tg_id, tasks in grouped.items():
        tasks.sort(key=lambda t: (
            str(t.controller) if t.controller else "ЯЯЯ",
            t.deadline
        ))

        today = timezone.now().date()
        lines = fmt_header(
            "УВЕДОМЛЕНИЕ О НАЗНАЧЕНИИ ПОРУЧЕНИЙ",
            "📨",
            tasks[0].executor
        )
        lines.append(f"Назначено поручений:  <b>{len(tasks)}</b>")

        for i, task in enumerate(tasks, 1):
            days_left = (task.deadline - today).days
            lines += ["", DIV]
            lines += fmt_task_card(task, i, len(tasks))
            lines += ["", deadline_note(days_left)]

        lines += [""]
        lines += fmt_footer(
            "Просим приступить к исполнению в установленные сроки."
        )

        if send_telegram_message(tg_id, "\n".join(lines)):
            for task in tasks:
                task.is_notified_created    = True
                task.last_notified_deadline = task.deadline
                task.status                 = 'IN_PROGRESS'
                task.save(update_fields=[
                    'is_notified_created', 'last_notified_deadline', 'status'
                ])
            sent_count += len(tasks)

    return sent_count


# ════════════════════════════════════════════════════════
#  2. ИЗМЕНЕНИЕ СРОКОВ
# ════════════════════════════════════════════════════════

def process_deadline_extensions(queryset):
    sent_count = 0
    assignments = queryset.filter(is_notified_created=True)
    changed = [
        t for t in assignments
        if t.last_notified_deadline and t.last_notified_deadline != t.deadline
    ]
    grouped = group_by_executor(changed)

    for tg_id, tasks in grouped.items():
        tasks.sort(key=lambda t: (
            str(t.controller) if t.controller else "ЯЯЯ",
            t.deadline
        ))

        today = timezone.now().date()
        lines = fmt_header(
            "УВЕДОМЛЕНИЕ ОБ ИЗМЕНЕНИИ СРОКОВ ИСПОЛНЕНИЯ",
            "📋",
            tasks[0].executor
        )
        lines.append(f"Количество изменений:  <b>{len(tasks)}</b>")

        for i, task in enumerate(tasks, 1):
            old_d     = task.last_notified_deadline
            new_d     = task.deadline
            shift     = (new_d - old_d).days
            direction = "продлён" if shift > 0 else "сокращён"
            days_left = (new_d - today).days

            lines += ["", DIV]
            lines += fmt_task_card(task, i, len(tasks))
            lines += [
                "",
                f"🔄  <b>Изменение срока:</b>",
                f"     <s>{old_d.strftime('%d.%m.%Y')}</s>  →  "
                f"<u><b>{new_d.strftime('%d.%m.%Y')}</b></u>",
                f"     <i>Срок {direction} на {days_label(abs(shift))}.</i>",
                "",
                deadline_note(days_left),
            ]

        lines += [""]
        lines += fmt_footer(
            "Просим учесть изменения при планировании работы."
        )

        if send_telegram_message(tg_id, "\n".join(lines)):
            for task in tasks:
                task.last_notified_deadline = task.deadline
                task.save(update_fields=['last_notified_deadline'])
            sent_count += len(tasks)

    return sent_count


# ════════════════════════════════════════════════════════
#  3. НАПОМИНАНИЯ О СРОКАХ
# ════════════════════════════════════════════════════════

def _bucket(days_left: int) -> tuple[int, str]:
    """(порядок сортировки, заголовок секции)"""
    if days_left < 0:  return 0, "Срок исполнения истёк"
    if days_left == 0: return 1, "Срок исполнения — сегодня"
    if days_left == 1: return 2, "Срок исполнения — завтра"
    return 3, "Срок исполнения в течение 3 дней"


def process_reminders(queryset):
    sent_count  = 0
    today       = timezone.now().date()
    target_date = today + timedelta(days=3)

    assignments = queryset.filter(
        status__in=['NEW', 'IN_PROGRESS'],
        deadline__lte=target_date,
        is_notified_created=True,
    )
    remind = [t for t in assignments if t.last_reminded_deadline != t.deadline]
    grouped = group_by_executor(remind)

    for tg_id, tasks in grouped.items():
        ann = [(t, (t.deadline - today).days) for t in tasks]
        ann.sort(key=lambda x: (
            _bucket(x[1])[0],
            str(x[0].controller) if x[0].controller else "ЯЯЯ",
            x[0].deadline,
        ))

        overdue  = sum(1 for _, d in ann if d < 0)
        today_n  = sum(1 for _, d in ann if d == 0)
        tomorrow = sum(1 for _, d in ann if d == 1)
        soon     = sum(1 for _, d in ann if d > 1)

        lines = fmt_header(
            "НАПОМИНАНИЕ О СРОКАХ ИСПОЛНЕНИЯ ПОРУЧЕНИЙ",
            "🗓",
            ann[0][0].executor
        )

        # Сводка
        lines.append("<b>Сводная информация:</b>")
        if overdue:  lines.append(f"  · срок истёк — <b>{overdue}</b>")
        if today_n:  lines.append(f"  · срок сегодня — <b>{today_n}</b>")
        if tomorrow: lines.append(f"  · срок завтра — <b>{tomorrow}</b>")
        if soon:     lines.append(f"  · срок в течение 3 дней — <b>{soon}</b>")

        # Поручения по секциям
        current_bucket = None
        for i, (task, days_left) in enumerate(ann, 1):
            _, bucket_title = _bucket(days_left)

            if bucket_title != current_bucket:
                lines += ["", f"{DIV}", f"<b>{bucket_title.upper()}</b>"]
                current_bucket = bucket_title

            lines += [""]
            lines += fmt_task_card(task, i, len(ann))
            lines += ["", deadline_note(days_left)]

        # Завершение
        lines += [""]
        if overdue:
            lines += fmt_footer(
                "По поручениям с истёкшим сроком просим проинформировать"
                " контролирующего о ходе исполнения."
            )
        else:
            lines += fmt_footer(
                "Просим принять меры для исполнения поручений в установленные сроки."
            )

        if send_telegram_message(tg_id, "\n".join(lines)):
            for task, _ in ann:
                task.last_reminded_deadline = task.deadline
                task.save(update_fields=['last_reminded_deadline'])
            sent_count += len(ann)

    return sent_count