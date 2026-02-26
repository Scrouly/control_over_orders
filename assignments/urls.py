from django.urls import path
from . import views

app_name = 'assignments'

urlpatterns = [
    path('',                    views.assignment_list,        name='list'),
    path('create/',             views.assignment_create,      name='create'),
    path('<int:pk>/',           views.assignment_detail,      name='detail'),
    path('<int:pk>/edit/',      views.assignment_edit,        name='edit'),
    path('<int:pk>/delete/',    views.assignment_delete,      name='delete'),
    path('bulk/',               views.assignment_bulk_action, name='bulk'),
    path('api/next-number/',    views.next_document_number,   name='next_number'),
]