from django.urls import path

from task_control.views import index, task_type, tasks

urlpatterns = [
    path('', index, name = 'index'),
    path('type/<int:type_id>', task_type, name='task_type'),
    path('tasks', tasks, name='tasks')
]
