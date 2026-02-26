from django.shortcuts import render, redirect
from django.contrib import messages
from django.utils import timezone
from django.db.models import Q
from django.views.decorators.http import require_POST
from datetime import timedelta, date as dt_date

from core.mixins import staff_required
from task_control.models import Assignment, Employee, Department, AssignmentType


@staff_required
def assignment_list(request):
    today = timezone.now().date()

    qs = Assignment.objects.select_related(
        'executor', 'executor__department', 'executor__position',
        'controller', 'approver', 'assignment_type'
    )

    # ── Фильтры ─────────────────────────────────────────────
    q       = request.GET.get('q', '').strip()
    status  = request.GET.get('status', '')
    dept_id = request.GET.get('dept', '')
    exec_id = request.GET.get('executor', '')
    ctrl_id = request.GET.get('controller', '')
    appr_id = request.GET.get('approver', '')
    type_id = request.GET.get('atype', '')
    date_from = request.GET.get('date_from', '')
    date_to   = request.GET.get('date_to', '')

    if q:
        qs = qs.filter(
            Q(document_number__icontains=q) |
            Q(description__icontains=q)     |
            Q(executor__last_name__icontains=q)
        )
    if status == 'active':
        qs = qs.filter(status__in=['NEW', 'IN_PROGRESS'])
    elif status:
        qs = qs.filter(status=status)
    if dept_id.isdigit():
        qs = qs.filter(executor__department_id=int(dept_id))

    position_id = request.GET.get('position', '')
    if position_id.isdigit():
        qs = qs.filter(executor__position_id=int(position_id))
    if exec_id.isdigit():
        qs = qs.filter(executor_id=int(exec_id))
    if ctrl_id.isdigit():
        qs = qs.filter(controller_id=int(ctrl_id))
    if appr_id.isdigit():
        qs = qs.filter(approver_id=int(appr_id))
    if type_id.isdigit():
        qs = qs.filter(assignment_type_id=int(type_id))
    if date_from:
        try:
            qs = qs.filter(deadline__gte=dt_date.fromisoformat(date_from))
        except ValueError:
            pass
    if date_to:
        try:
            qs = qs.filter(deadline__lte=dt_date.fromisoformat(date_to))
        except ValueError:
            pass

    # ── Сортировка ───────────────────────────────────────────
    sort = request.GET.get('sort', '-created_at')
    ALLOWED_SORTS = {
        'deadline':        'deadline',
        '-deadline':       '-deadline',
        'executor':        'executor__last_name',
        '-executor':       '-executor__last_name',
        'status':          'status',
        '-status':         '-status',
        'created_at':      'created_at',
        '-created_at':     '-created_at',
        'document_number': 'document_number',
        '-document_number':'-document_number',
    }
    qs = qs.order_by(ALLOWED_SORTS.get(sort, '-created_at'))

    # ── Данные для фильтров ──────────────────────────────────
    departments = Department.objects.order_by('name')
    assignment_types = AssignmentType.objects.order_by('name')

    executors = Employee.objects.filter(
        is_active=True,
        assignments_to_execute__isnull=False
    ).distinct().order_by('last_name', 'first_name')

    controllers = Employee.objects.filter(
        assignments_to_control__isnull=False
    ).distinct().order_by('last_name', 'first_name')

    approvers = Employee.objects.filter(
        assignments_to_approve__isnull=False
    ).distinct().order_by('last_name', 'first_name')

    total = qs.count()

    return render(request, 'assignments/list.html', {
        'assignments':      qs,
        'total':            total,
        'today':            today,
        'departments':      departments,
        'assignment_types': assignment_types,
        'executors':        executors,
        'controllers':      controllers,
        'approvers':        approvers,
        'status_choices':   Assignment.Status.choices,
        # Текущие значения фильтров
        'f_q':          q,
        'f_status':     status,
        'f_dept':       dept_id,
        'f_executor':   exec_id,
        'f_controller': ctrl_id,
        'f_approver':   appr_id,
        'f_atype':      type_id,
        'f_date_from':  date_from,
        'f_date_to':    date_to,
        'current_sort': sort,
    })


@staff_required
@require_POST
def assignment_bulk_action(request):
    action = request.POST.get('action')
    ids    = request.POST.getlist('ids')

    if not ids:
        messages.warning(request, 'Не выбрано ни одного поручения.')
        return redirect('assignments:list')

    qs = Assignment.objects.filter(id__in=ids)

    if action == 'status_done':
        qs.update(status='DONE', updated_at=timezone.now())
        messages.success(request, f'Помечено как исполненные: {len(ids)} поручений.')
    elif action == 'status_progress':
        qs.update(status='IN_PROGRESS', updated_at=timezone.now())
        messages.success(request, f'Статус «В работе»: {len(ids)} поручений.')
    elif action == 'notify_new':
        from telegram.notifications import process_new_assignments
        sent = process_new_assignments(qs)
        messages.success(request, f'Отправлено уведомлений: {sent}.')
    elif action == 'notify_remind':
        from telegram.notifications import process_reminders
        sent = process_reminders(qs)
        messages.success(request, f'Отправлено напоминаний: {sent}.')
    elif action == 'notify_deadline':
        from telegram.notifications import process_deadline_change
        sent = process_deadline_change(qs)
        messages.success(request, f'Отправлено уведомлений об изменении сроков: {sent}.')
    elif action == 'print':
        return redirect(f'/reports/print-selected/?ids={",".join(ids)}')
    else:
        messages.error(request, 'Неизвестное действие.')

    return redirect(request.POST.get('next', 'assignments:list'))


# ════════════════════════════════════════════════════════
#  КАРТОЧКА ПОРУЧЕНИЯ
# ════════════════════════════════════════════════════════

@staff_required
def assignment_detail(request, pk):
    task = get_object_or_404(
        Assignment.objects.select_related(
            'executor', 'executor__department', 'executor__position',
            'executor__telegram_profile',
            'controller', 'approver', 'assignment_type',
        ),
        pk=pk
    )
    today = timezone.now().date()

    # Быстрая смена статуса
    if request.method == 'POST' and 'change_status' in request.POST:
        new_status = request.POST.get('status')
        if new_status in dict(Assignment.Status.choices):
            old_status = task.get_status_display()
            task.status = new_status
            task.save(update_fields=['status', 'updated_at'])
            messages.success(request, f'Статус изменён: {old_status} → {task.get_status_display()}')
        return redirect('assignments:detail', pk=pk)

    # Отправка уведомления
    if request.method == 'POST' and 'send_notify' in request.POST:
        notify_type = request.POST.get('notify_type', 'new')
        try:
            if notify_type == 'new':
                from telegram.notifications import process_new_assignments
                process_new_assignments(Assignment.objects.filter(pk=pk))
                messages.success(request, 'Уведомление о новом поручении отправлено.')
            elif notify_type == 'remind':
                from telegram.notifications import process_reminders
                process_reminders(Assignment.objects.filter(pk=pk))
                messages.success(request, 'Напоминание отправлено.')
            elif notify_type == 'deadline':
                from telegram.notifications import process_deadline_change
                process_deadline_change(Assignment.objects.filter(pk=pk))
                messages.success(request, 'Уведомление об изменении срока отправлено.')
        except Exception as e:
            messages.error(request, f'Ошибка отправки: {e}')
        return redirect('assignments:detail', pk=pk)

    delta = task.deadline - today
    days_left = delta.days          # отрицательное если просрочено
    days_overdue = abs(delta.days)  # всегда положительное

    return render(request, 'assignments/detail.html', {
        'task':      task,
        'today':     today,
        'days_left':    days_left,
        'days_overdue': days_overdue,
        'status_choices': Assignment.Status.choices,
    })


# ════════════════════════════════════════════════════════
#  СОЗДАНИЕ ПОРУЧЕНИЯ
# ════════════════════════════════════════════════════════

@staff_required
def assignment_create(request):
    from .forms import AssignmentCreateForm
    from task_control.models import Department

    today = timezone.now().date()
    departments = Department.objects.prefetch_related(
        'employee_set'
    ).order_by('name')

    if request.method == 'POST':
        form = AssignmentCreateForm(request.POST)
        if form.is_valid():
            data      = form.cleaned_data
            executors = data['executors']
            created   = []

            for executor in executors:
                task = Assignment.objects.create(
                    assignment_type = data['assignment_type'],
                    document_number = data['document_number'],
                    issue_date      = data['issue_date'],
                    description     = data['description'],
                    deadline        = data['deadline'],
                    executor        = executor,
                    controller      = data.get('controller'),
                    approver        = data.get('approver'),
                    status          = 'NEW',
                )
                created.append(task)

            # Отправка уведомлений если выбрано
            if data.get('send_notifications') and created:
                try:
                    from telegram.notifications import process_new_assignments
                    ids = [t.pk for t in created]
                    process_new_assignments(Assignment.objects.filter(pk__in=ids))
                    messages.success(request, f'Создано {len(created)} поручений. Уведомления отправлены.')
                except Exception as e:
                    messages.warning(request, f'Создано {len(created)} поручений. Ошибка отправки уведомлений: {e}')
            else:
                messages.success(request, f'Создано {len(created)} поручений.')

            if len(created) == 1:
                return redirect('assignments:detail', pk=created[0].pk)
            return redirect('assignments:list')
    else:
        form = AssignmentCreateForm(initial={'issue_date': today})

    import json as _json
    employees_json = _json.dumps([
        {
            'id':    str(e.pk),
            'name':  f'{e.last_name} {e.first_name} {e.middle_name}'.strip(),
            'short': f'{e.last_name} {e.first_name[:1]}.{e.middle_name[:1]}.' if e.first_name else e.last_name,
            'pos':   e.position.name if e.position else '',
            'dept':  e.department.name if e.department else 'Без подразделения',
            'av':    (e.last_name[:1] + e.first_name[:1]).upper() if e.first_name else e.last_name[:2].upper(),
        }
        for e in form.fields['executors'].queryset
    ], ensure_ascii=False)

    return render(request, 'assignments/create.html', {
        'form':          form,
        'today':         today,
        'departments':   departments,
        'employees_json': employees_json,
    })


# ════════════════════════════════════════════════════════
#  РЕДАКТИРОВАНИЕ ПОРУЧЕНИЯ
# ════════════════════════════════════════════════════════

@staff_required
def assignment_edit(request, pk):
    from .forms import AssignmentForm
    task = get_object_or_404(Assignment, pk=pk)
    old_deadline = task.deadline

    if request.method == 'POST':
        form = AssignmentForm(request.POST, instance=task)
        if form.is_valid():
            updated = form.save()

            # Если срок изменился — предложить уведомить
            deadline_changed = updated.deadline != old_deadline
            if deadline_changed:
                messages.warning(
                    request,
                    f'Срок изменён с {old_deadline.strftime("%d.%m.%Y")} '
                    f'на {updated.deadline.strftime("%d.%m.%Y")}. '
                    f'Не забудьте отправить уведомление об изменении срока.'
                )
            else:
                messages.success(request, 'Поручение обновлено.')

            # Кнопка «Сохранить и уведомить»
            if 'save_notify' in request.POST and deadline_changed:
                try:
                    from telegram.notifications import process_deadline_change
                    process_deadline_change(Assignment.objects.filter(pk=pk))
                    messages.success(request, 'Уведомление об изменении срока отправлено.')
                except Exception as e:
                    messages.error(request, f'Ошибка отправки: {e}')

            return redirect('assignments:detail', pk=pk)
    else:
        form = AssignmentForm(instance=task)

    return render(request, 'assignments/edit.html', {
        'form': form,
        'task': task,
    })


# ════════════════════════════════════════════════════════
#  УДАЛЕНИЕ ПОРУЧЕНИЯ
# ════════════════════════════════════════════════════════

@staff_required
def assignment_delete(request, pk):
    task = get_object_or_404(Assignment, pk=pk)
    if request.method == 'POST':
        from core.mixins import is_admin
        if not is_admin(request.user):
            messages.error(request, 'Удаление доступно только администраторам.')
            return redirect('assignments:detail', pk=pk)
        task.delete()
        messages.success(request, f'Поручение № {task.document_number} удалено.')
        return redirect('assignments:list')
    return redirect('assignments:detail', pk=pk)


# ════════════════════════════════════════════════════════
#  API: следующий номер документа
# ════════════════════════════════════════════════════════
from django.http import JsonResponse

@staff_required
def next_document_number(request):
    """Возвращает следующий номер документа на основе последнего."""
    from task_control.models import Assignment
    import re

    atype_id = request.GET.get('type', '')
    today = timezone.now().date()
    year  = today.year

    # Берём последнее поручение этого типа за текущий год
    qs = Assignment.objects.filter(issue_date__year=year)
    if atype_id.isdigit():
        qs = qs.filter(assignment_type_id=int(atype_id))

    last = qs.order_by('-id').first()

    if last:
        # Пытаемся найти последнее число в номере и инкрементировать
        m = re.search(r'(\d+)$', last.document_number)
        if m:
            base = last.document_number[:m.start()]
            num  = int(m.group(1)) + 1
            suggestion = f"{base}{num}"
        else:
            suggestion = ''
    else:
        suggestion = ''

    return JsonResponse({'number': suggestion})
