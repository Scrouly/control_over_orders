from django.shortcuts import render, get_object_or_404
from django.utils import timezone
from django.db.models import Count
from task_control.models import Employee, Assignment


def print_executor_report(request, employee_id):
    employee    = get_object_or_404(Employee, pk=employee_id)
    report_date = timezone.now().date()

    assignments = Assignment.objects.filter(
        executor=employee
    ).exclude(status='DONE').order_by('deadline')

    return render(request, 'reports/print_report.html', {
        'employee':    employee,
        'assignments': assignments,
        'report_date': report_date,
    })


def print_selected_assignments(request):
    ids_param = request.GET.get('ids', '')
    if not ids_param:
        return render(request, 'reports/cuttable_report.html', {'grouped_tasks': []})

    ids_list = [int(x) for x in ids_param.split(',') if x.isdigit()]

    assignments = Assignment.objects.filter(id__in=ids_list).select_related(
        'executor', 'executor__department', 'executor__position',
        'controller', 'approver', 'assignment_type'
    ).order_by('executor__id', 'controller__id', 'approver__id', 'deadline')

    grouped_tasks = []
    current_group = None

    for task in assignments:
        if current_group is None:
            current_group = {
                'executor':   task.executor,
                'controller': task.controller,
                'approver':   task.approver,
                'start_date': task.deadline,
                'tasks':      [task],
            }
            grouped_tasks.append(current_group)
            continue

        ctrl_id_1 = task.controller.id if task.controller else None
        ctrl_id_2 = current_group['controller'].id if current_group['controller'] else None
        appr_id_1 = task.approver.id if task.approver else None
        appr_id_2 = current_group['approver'].id if current_group['approver'] else None
        date_diff  = abs((task.deadline - current_group['start_date']).days)

        if (task.executor_id == current_group['executor'].id
                and ctrl_id_1 == ctrl_id_2
                and appr_id_1 == appr_id_2
                and date_diff <= 3):
            current_group['tasks'].append(task)
        else:
            current_group = {
                'executor':   task.executor,
                'controller': task.controller,
                'approver':   task.approver,
                'start_date': task.deadline,
                'tasks':      [task],
            }
            grouped_tasks.append(current_group)

    return render(request, 'reports/cuttable_report.html', {
        'grouped_tasks': grouped_tasks,
    })


def deadline_filter_view(request):
    today        = timezone.now().date()
    deadline_str = request.GET.get('deadline', '')
    print_mode   = request.GET.get('print') == '1'

    deadline_date = None
    assignments   = None
    error         = None

    from task_control.models import Department
    departments = Department.objects.filter(
        employee__assignments_to_execute__status__in=['NEW', 'IN_PROGRESS', 'OVERDUE']
    ).distinct().order_by('name')

    if deadline_str:
        try:
            from datetime import date
            deadline_date = date.fromisoformat(deadline_str)
        except ValueError:
            error = "Неверный формат даты."

    if deadline_date and not error:
        qs = Assignment.objects.filter(
            deadline__lte=deadline_date
        ).exclude(status='DONE').select_related(
            'executor', 'executor__department', 'executor__position',
            'controller', 'approver', 'assignment_type'
        )

        # Фильтры из печатной версии (переданы JS-ом)
        if print_mode:
            pexec   = request.GET.get('pexec', '').strip()
            pdept   = request.GET.get('pdept', '').strip()
            pstatus = request.GET.get('pstatus', '').strip()
            if pexec:
                qs = qs.filter(executor__last_name__icontains=pexec) | \
                     qs.filter(executor__first_name__icontains=pexec)
            if pdept.isdigit():
                qs = qs.filter(executor__department_id=int(pdept))
            if pstatus:
                qs = qs.filter(status=pstatus)

        assignments = qs.order_by(
            'executor__last_name', 'executor__first_name', 'deadline'
        )

    template = 'reports/deadline_filter_print.html' if print_mode else 'reports/deadline_filter.html'

    return render(request, template, {
        'today':          today,
        'deadline_date':  deadline_date,
        'deadline_str':   deadline_str,
        'assignments':    assignments,
        'departments':    departments,
        'error':          error,
        'report_date':    today,
        'status_choices': Assignment.Status.choices,
    })