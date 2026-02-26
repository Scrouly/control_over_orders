from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse
from django.views.decorators.http import require_POST, require_http_methods
from django.contrib import messages
from django.db.models import Count, Q
from django.utils import timezone
from core.mixins import staff_required, is_admin
from task_control.models import Department, Position, AssignmentType, Assignment, Employee
import json


# ════════════════════════════════════════════════════════
#  ПОДРАЗДЕЛЕНИЯ
# ════════════════════════════════════════════════════════

@staff_required
def departments(request):
    if request.method == 'POST':
        if not is_admin(request.user):
            return JsonResponse({'error': 'Нет прав'}, status=403)
        name = request.POST.get('name', '').strip()
        if name:
            dept = Department.objects.create(name=name)
            messages.success(request, f'Подразделение «{name}» добавлено.')
        return redirect('references:departments')

    depts = Department.objects.annotate(
        employee_count=Count('employee', distinct=True),
        active_count=Count(
            'employee__assignments_to_execute',
            filter=Q(employee__assignments_to_execute__status__in=['NEW', 'IN_PROGRESS']),
            distinct=True
        ),
    ).order_by('name')

    return render(request, 'references/departments.html', {
        'depts':    depts,
        'is_admin': is_admin(request.user),
    })


@require_POST
@staff_required
def department_update(request, pk):
    if not is_admin(request.user):
        return JsonResponse({'error': 'Нет прав'}, status=403)
    dept = get_object_or_404(Department, pk=pk)
    data = json.loads(request.body)
    name = data.get('name', '').strip()
    if not name:
        return JsonResponse({'error': 'Название не может быть пустым'}, status=400)
    dept.name = name
    dept.save()
    return JsonResponse({'ok': True, 'name': dept.name})


@require_POST
@staff_required
def department_delete(request, pk):
    if not is_admin(request.user):
        return JsonResponse({'error': 'Нет прав'}, status=403)
    dept = get_object_or_404(Department, pk=pk)
    emp_count = dept.employee_set.count()
    if emp_count > 0:
        return JsonResponse({
            'error': f'Нельзя удалить: в подразделении {emp_count} сотр.'
        }, status=400)
    dept.delete()
    return JsonResponse({'ok': True})


# ════════════════════════════════════════════════════════
#  ДОЛЖНОСТИ
# ════════════════════════════════════════════════════════

@staff_required
def positions(request):
    if request.method == 'POST':
        if not is_admin(request.user):
            return JsonResponse({'error': 'Нет прав'}, status=403)
        name = request.POST.get('name', '').strip()
        if name:
            Position.objects.create(name=name)
            messages.success(request, f'Должность «{name}» добавлена.')
        return redirect('references:positions')

    pos_list = Position.objects.annotate(
        employee_count=Count('employee', distinct=True),
    ).order_by('name')

    return render(request, 'references/positions.html', {
        'positions': pos_list,
        'is_admin':  is_admin(request.user),
    })


@require_POST
@staff_required
def position_update(request, pk):
    if not is_admin(request.user):
        return JsonResponse({'error': 'Нет прав'}, status=403)
    pos = get_object_or_404(Position, pk=pk)
    data = json.loads(request.body)
    name = data.get('name', '').strip()
    if not name:
        return JsonResponse({'error': 'Название не может быть пустым'}, status=400)
    pos.name = name
    pos.save()
    return JsonResponse({'ok': True, 'name': pos.name})


@require_POST
@staff_required
def position_delete(request, pk):
    if not is_admin(request.user):
        return JsonResponse({'error': 'Нет прав'}, status=403)
    pos = get_object_or_404(Position, pk=pk)
    emp_count = pos.employee_set.count()
    if emp_count > 0:
        return JsonResponse({
            'error': f'Нельзя удалить: {emp_count} сотр. с этой должностью'
        }, status=400)
    pos.delete()
    return JsonResponse({'ok': True})


# ════════════════════════════════════════════════════════
#  ВИДЫ ПОРУЧЕНИЙ
# ════════════════════════════════════════════════════════

@staff_required
def assignment_types(request):
    if request.method == 'POST':
        if not is_admin(request.user):
            return JsonResponse({'error': 'Нет прав'}, status=403)
        name  = request.POST.get('name', '').strip()
        color = request.POST.get('color', '#6c757d')
        if name:
            AssignmentType.objects.create(name=name, color=color if hasattr(AssignmentType, 'color') else None)
            messages.success(request, f'Вид «{name}» добавлен.')
        return redirect('references:types')

    types = AssignmentType.objects.annotate(
        total=Count('assignment', distinct=True),
        active=Count(
            'assignment',
            filter=Q(assignment__status__in=['NEW', 'IN_PROGRESS']),
            distinct=True
        ),
    ).order_by('name')

    COLORS = [
        '#3b5bdb', '#1971c2', '#0c8599', '#2f9e44',
        '#e67700', '#c2255c', '#7048e8', '#495057',
    ]

    return render(request, 'references/types.html', {
        'types':    types,
        'colors':   COLORS,
        'is_admin': is_admin(request.user),
    })


@require_POST
@staff_required
def type_update(request, pk):
    if not is_admin(request.user):
        return JsonResponse({'error': 'Нет прав'}, status=403)
    atype = get_object_or_404(AssignmentType, pk=pk)
    data  = json.loads(request.body)
    name  = data.get('name', '').strip()
    if not name:
        return JsonResponse({'error': 'Название не может быть пустым'}, status=400)
    atype.name = name
    if hasattr(atype, 'color') and data.get('color'):
        atype.color = data['color']
    atype.save()
    return JsonResponse({'ok': True, 'name': atype.name})


@require_POST
@staff_required
def type_delete(request, pk):
    if not is_admin(request.user):
        return JsonResponse({'error': 'Нет прав'}, status=403)
    atype = get_object_or_404(AssignmentType, pk=pk)
    count = Assignment.objects.filter(assignment_type=atype).count()
    if count > 0:
        return JsonResponse({
            'error': f'Нельзя удалить: {count} поручений этого вида'
        }, status=400)
    atype.delete()
    return JsonResponse({'ok': True})
