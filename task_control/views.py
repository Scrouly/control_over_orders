from django.http import HttpResponse
from django.shortcuts import render


# Create your views here.


def index(request):
    context = {"title": "Контроль", 'username': 'Vlad'}
    return render(request, 'task_control/index.html', context)


def task_type(request, type_id):
    return HttpResponse(f"<h1>Тип документа {type_id}</h1>")


def tasks(request):
    return render(request, 'task_control/tasks.html')
