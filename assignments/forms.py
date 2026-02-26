from django import forms
from task_control.models import Assignment, Employee, AssignmentType, Department


class AssignmentForm(forms.ModelForm):
    """Форма редактирования одного поручения."""

    class Meta:
        model = Assignment
        fields = [
            'assignment_type', 'document_number', 'issue_date',
            'description', 'deadline', 'executor',
            'controller', 'approver', 'status',
        ]
        widgets = {
            'assignment_type':  forms.Select(attrs={'class': 'form-control'}),
            'document_number':  forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Например: 26-2-2-1'}),
            'issue_date':       forms.DateInput(attrs={'class': 'date-input', 'type': 'date'}),
            'description':      forms.Textarea(attrs={'class': 'form-control', 'rows': 5, 'placeholder': 'Текст поручения…'}),
            'deadline':         forms.DateInput(attrs={'class': 'date-input', 'type': 'date'}),
            'executor':         forms.Select(attrs={'class': 'form-control'}),
            'controller':       forms.Select(attrs={'class': 'form-control'}),
            'approver':         forms.Select(attrs={'class': 'form-control'}),
            'status':           forms.Select(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        active = Employee.objects.filter(is_active=True).select_related(
            'department', 'position'
        ).order_by('department__name', 'last_name')

        # Группировка по цеху для исполнителя
        dept_choices = [('', '— Выберите исполнителя —')]
        current_dept = None
        dept_group = []
        for emp in active:
            dept_name = emp.department.name if emp.department else 'Без подразделения'
            if dept_name != current_dept:
                if current_dept is not None:
                    dept_choices.append((current_dept, dept_group))
                current_dept = dept_name
                dept_group = []
            dept_group.append((emp.id, str(emp)))
        if dept_group:
            dept_choices.append((current_dept, dept_group))

        self.fields['executor'].choices = dept_choices
        self.fields['executor'].required = True

        # Контролёр и визирующий — необязательные, с пустым вариантом
        people_choices = [('', '— Не назначен —')] + [
            (e.id, str(e)) for e in active
        ]
        self.fields['controller'].choices = people_choices
        self.fields['controller'].required = False
        self.fields['approver'].choices = people_choices
        self.fields['approver'].required = False

        self.fields['assignment_type'].empty_label = '— Выберите вид —'
        self.fields['assignment_type'].queryset = AssignmentType.objects.order_by('name')


class AssignmentCreateForm(forms.Form):
    """
    Форма создания поручений с множественным выбором исполнителей.
    Создаёт отдельное поручение для каждого выбранного исполнителя.
    """
    assignment_type = forms.ModelChoiceField(
        queryset=AssignmentType.objects.order_by('name'),
        empty_label='— Выберите вид —',
        widget=forms.Select(attrs={'class': 'form-control'}),
        label='Вид поручения',
    )
    document_number = forms.CharField(
        max_length=100,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Например: 26-2-2-1'}),
        label='Номер документа',
    )
    issue_date = forms.DateField(
        widget=forms.DateInput(attrs={'class': 'date-input', 'type': 'date'}),
        label='Дата издания',
    )
    description = forms.CharField(
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 5, 'placeholder': 'Текст поручения…'}),
        label='Текст поручения',
    )
    deadline = forms.DateField(
        widget=forms.DateInput(attrs={'class': 'date-input', 'type': 'date'}),
        label='Срок исполнения',
    )
    executors = forms.ModelMultipleChoiceField(
        queryset=Employee.objects.filter(is_active=True).select_related('department').order_by('department__name', 'last_name'),
        widget=forms.CheckboxSelectMultiple,
        label='Исполнители',
        error_messages={'required': 'Выберите хотя бы одного исполнителя.'},
    )
    controller = forms.ModelChoiceField(
        queryset=Employee.objects.filter(is_active=True).order_by('last_name'),
        empty_label='— Не назначен —',
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'}),
        label='Контролирующий',
    )
    approver = forms.ModelChoiceField(
        queryset=Employee.objects.filter(is_active=True).order_by('last_name'),
        empty_label='— Не назначен —',
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'}),
        label='Визирующий',
    )
    send_notifications = forms.BooleanField(
        required=False,
        initial=True,
        label='Отправить уведомления после создания',
    )


class StatusChangeForm(forms.Form):
    status = forms.ChoiceField(
        choices=Assignment.Status.choices,
        widget=forms.Select(attrs={'class': 'form-control'}),
    )