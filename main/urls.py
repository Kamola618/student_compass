from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('courses/', views.courses, name='courses'),
    path('assignments/', views.assignments, name='assignments'),
    path('assignments/add/', views.add_assignment, name='add_assignment'),
    path('courses/add/', views.add_course, name='add_course'),
    path('assignments/<int:id>/edit/', views.edit_assignment, name='edit_assignment'),
    path('assignments/<int:id>/delete/', views.delete_assignment, name='delete_assignment'),
    path('grades/', views.grades, name='grades'),
    path('grades/<int:course_id>/edit/', views.edit_grade, name='edit_grade'),
]