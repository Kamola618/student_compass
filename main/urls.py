from django.urls import path

from . import views

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('courses/', views.courses, name='courses'),
    path('courses/add/', views.add_course, name='add_course'),
    path('grades/', views.grades, name='grades'),
    path('tasks/', views.tasks, name='tasks'),
    path('tasks/add/', views.add_task, name='add_task'),
    path('tasks/<int:id>/edit/', views.edit_task, name='edit_task'),
    path('tasks/<int:id>/delete/', views.delete_task, name='delete_task'),
]
