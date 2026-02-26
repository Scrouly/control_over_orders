from django.urls import path
from . import views

app_name = 'references'

urlpatterns = [
    path('departments/',           views.departments,       name='departments'),
    path('departments/<int:pk>/update/', views.department_update, name='dept_update'),
    path('departments/<int:pk>/delete/', views.department_delete, name='dept_delete'),

    path('positions/',             views.positions,         name='positions'),
    path('positions/<int:pk>/update/', views.position_update, name='pos_update'),
    path('positions/<int:pk>/delete/', views.position_delete, name='pos_delete'),

    path('types/',                 views.assignment_types,  name='types'),
    path('types/<int:pk>/update/', views.type_update,       name='type_update'),
    path('types/<int:pk>/delete/', views.type_delete,       name='type_delete'),
]
