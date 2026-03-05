from datetime import date, timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from task_control.models import Assignment, AssignmentType, Department, Employee, Position


class AssignmentBulkActionTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.user = user_model.objects.create_user(
            username='staff',
            password='pass123',
            is_staff=True,
        )
        self.client.force_login(self.user)

        dept = Department.objects.create(name='Отдел ИТ')
        pos = Position.objects.create(name='Специалист')

        self.executor = Employee.objects.create(
            last_name='Иванов',
            first_name='Иван',
            middle_name='Иванович',
            department=dept,
            position=pos,
            is_active=True,
        )
        self.controller = Employee.objects.create(
            last_name='Петров',
            first_name='Пётр',
            middle_name='Петрович',
            department=dept,
            position=pos,
            is_controller=True,
            is_active=True,
        )
        assignment_type = AssignmentType.objects.create(name='Распоряжение')

        self.assignment = Assignment.objects.create(
            assignment_type=assignment_type,
            document_number='1',
            issue_date=date.today(),
            deadline=date.today() + timedelta(days=3),
            description='Тестовое поручение',
            executor=self.executor,
            controller=self.controller,
        )

    @patch('telegram.notifications.process_deadline_change', return_value=1)
    def test_notify_deadline_bulk_action_calls_deadline_handler(self, mocked_deadline_change):
        response = self.client.post(
            reverse('assignments:bulk'),
            {
                'action': 'notify_deadline',
                'ids': [str(self.assignment.pk)],
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('assignments:list'))

        mocked_deadline_change.assert_called_once()
        called_qs = mocked_deadline_change.call_args.args[0]
        self.assertQuerysetEqual(
            called_qs.order_by('pk'),
            [self.assignment],
            transform=lambda obj: obj,
        )
