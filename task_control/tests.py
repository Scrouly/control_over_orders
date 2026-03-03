from django.test import TestCase

from task_control.models import Employee


class EmployeeModelTests(TestCase):
    def test_telegram_id_property_without_profile_returns_none(self):
        employee = Employee.objects.create(last_name='Иванов', first_name='Иван')
        self.assertIsNone(employee.telegram_id)
