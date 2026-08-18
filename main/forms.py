from django import forms
from .models import *

class AssignmentForm(forms.ModelForm):
    class Meta:
        model = Assignment
        fields = ['name', 'course', 'difficulty', 'priority', 'progress', 'due_date']
        widgets = {
            'due_date': forms.DateTimeInput(attrs={'type': 'datetime-local'})
        }

class CourseForm(forms.ModelForm):
    class Meta:
        model = Course
        fields = ['name', 'code', 'teacher', 'office', 'office_hours', 'syllabus', 'color', 'semester']
        
class GradeForm(forms.ModelForm):
    class Meta:
        model = Grade
        fields = ['midterm_weight', 'midterm_score', 'assignments_weight', 'final_weight', 'final_score']