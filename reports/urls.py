from django.urls import path
from .views import print_executor_report, print_selected_assignments, deadline_filter_view

app_name = 'reports'

urlpatterns = [
    path('executor/<int:employee_id>/', print_executor_report,      name='executor_print'),
    path('print-selected/',            print_selected_assignments,  name='print_selected'),
    path('by-deadline/',               deadline_filter_view,        name='deadline_filter'),
]