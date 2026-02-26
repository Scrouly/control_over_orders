from django.urls import path
from . import views

app_name = 'core'

urlpatterns = [
    path('',                views.dashboard_view,     name='dashboard'),
    path('login/',          views.login_view,          name='login'),
    path('logout/',         views.logout_view,         name='logout'),
    path('forbidden/',      views.forbidden_view,      name='forbidden'),
    path('check-overdue/',  views.check_overdue_view,  name='check_overdue'),

]