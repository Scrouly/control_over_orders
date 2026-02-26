from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods
from django.utils import timezone
from django.db.models import Count, Q
from datetime import timedelta, date
import json

from .mixins import staff_required


@require_http_methods(['GET', 'POST'])
def login_view(request):
    if request.user.is_authenticated:
        return redirect('core:dashboard')

    error = None
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')
        user = authenticate(request, username=username, password=password)
        if user is not None:
            if user.is_staff:
                login(request, user)
                return redirect(request.GET.get('next', 'core:dashboard'))
            else:
                error = 'У вашей учётной записи нет доступа к системе.'
        else:
            error = 'Неверное имя пользователя или пароль.'

    return render(request, 'core/login.html', {'error': error})


def logout_view(request):
    logout(request)
    return redirect('core:login')


@login_required(login_url='/login/')
def forbidden_view(request):
    return render(request, 'core/forbidden.html', status=403)


@staff_required
def dashboard_view(request):
    from task_control.models import Assignment, Employee, Department

    today = timezone.now().date()
    week_end = today + timedelta(days=7)
    month_start = today.replace(day=1)

    # ── KPI-карточки ────────────────────────────────────────
    active_qs = Assignment.objects.exclude(status='DONE')

    kpi = {
        'active':    active_qs.count(),
        'overdue':   active_qs.filter(status='OVERDUE').count(),
        'today':     active_qs.filter(deadline=today).count(),
        'week':      active_qs.filter(deadline__gt=today, deadline__lte=week_end).count(),
        'done_month': Assignment.objects.filter(
            status='DONE',
            updated_at__date__gte=month_start
        ).count(),
        'total_employees': Employee.objects.filter(is_active=True).count(),
    }

    # ── Горящие поручения (просрочено + срок сегодня/завтра) ─
    urgent = Assignment.objects.filter(
        Q(status='OVERDUE') | Q(deadline__lte=today + timedelta(days=1), status__in=['NEW', 'IN_PROGRESS'])
    ).select_related(
        'executor', 'executor__department', 'assignment_type', 'controller'
    ).order_by('deadline')[:20]

    # ── График 1: Динамика по месяцам (последние 6) ──────────
    months_labels = []
    months_issued = []
    months_done   = []
    months_overdue = []

    for i in range(5, -1, -1):
        # Первый и последний день месяца
        d = today.replace(day=1) - timedelta(days=1)
        for _ in range(i):
            d = d.replace(day=1) - timedelta(days=1)
        m_start = d.replace(day=1)
        m_end   = (m_start + timedelta(days=32)).replace(day=1) - timedelta(days=1)

        label = m_start.strftime('%b %Y')
        months_labels.append(label)
        months_issued.append(
            Assignment.objects.filter(issue_date__gte=m_start, issue_date__lte=m_end).count()
        )
        months_done.append(
            Assignment.objects.filter(
                status='DONE', updated_at__date__gte=m_start, updated_at__date__lte=m_end
            ).count()
        )
        months_overdue.append(
            Assignment.objects.filter(
                deadline__gte=m_start, deadline__lte=m_end, status='OVERDUE'
            ).count()
        )

    chart_monthly = {
        'labels':  months_labels,
        'issued':  months_issued,
        'done':    months_done,
        'overdue': months_overdue,
    }

    # ── График 2: Нагрузка по исполнителям (топ 8) ───────────
    top_executors = (
        active_qs
        .values('executor__last_name', 'executor__first_name')
        .annotate(cnt=Count('id'))
        .order_by('-cnt')[:8]
    )
    chart_executors = {
        'labels': [
            f"{e['executor__last_name']} {e['executor__first_name'][:1]}."
            for e in top_executors
        ],
        'values': [e['cnt'] for e in top_executors],
    }

    # ── График 3: По подразделениям ───────────────────────────
    by_dept = (
        active_qs
        .values('executor__department__name')
        .annotate(cnt=Count('id'))
        .order_by('-cnt')[:8]
    )
    chart_departments = {
        'labels': [d['executor__department__name'] or 'Без подразд.' for d in by_dept],
        'values': [d['cnt'] for d in by_dept],
    }

    # ── График 4: Распределение по статусам (donut) ───────────
    by_status = (
        Assignment.objects.values('status')
        .annotate(cnt=Count('id'))
    )
    status_map = {'NEW': 'Новое', 'IN_PROGRESS': 'В работе', 'OVERDUE': 'Просрочено', 'DONE': 'Исполнено'}
    chart_statuses = {
        'labels': [status_map.get(s['status'], s['status']) for s in by_status],
        'values': [s['cnt'] for s in by_status],
    }

    # ── Последние поручения ───────────────────────────────────
    recent = Assignment.objects.select_related(
        'executor', 'assignment_type'
    ).order_by('-created_at')[:8]

    return render(request, 'core/dashboard.html', {
        'kpi':               kpi,
        'urgent':            urgent,
        'recent':            recent,
        'today':             today,
        'chart_monthly':     json.dumps(chart_monthly,     ensure_ascii=False),
        'chart_executors':   json.dumps(chart_executors,   ensure_ascii=False),
        'chart_departments': json.dumps(chart_departments, ensure_ascii=False),
        'chart_statuses':    json.dumps(chart_statuses,    ensure_ascii=False),
    })


@staff_required
def check_overdue_view(request):
    if request.method != 'POST':
        return redirect('core:dashboard')

    from django.contrib import messages
    from task_control.models import Assignment

    today = timezone.now().date()

    updated = Assignment.objects.filter(
        status__in=['NEW', 'IN_PROGRESS'],
        deadline__lt=today,
    ).update(status='OVERDUE')

    if updated:
        messages.warning(request, f'Обновлено {updated} поручений — статус изменён на «Просрочено».')
    else:
        messages.success(request, 'Просроченных поручений не обнаружено — все статусы актуальны.')

    return redirect('core:dashboard')