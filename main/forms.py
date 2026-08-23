from django import forms

from .models import Assessment, Course, Enrollment, Note, Score, Task


class CourseForm(forms.ModelForm):
    class Meta:
        model = Course
        fields = ['code', 'title', 'department', 'credits', 'ects',
                  'lecture_hours', 'tutorial_hours', 'lab_hours', 'description']


class EnrollmentForm(forms.ModelForm):
    class Meta:
        model = Enrollment
        fields = ['course', 'semester', 'teacher', 'office', 'office_hours',
                  'color', 'target_score']


class AssessmentForm(forms.ModelForm):
    class Meta:
        model = Assessment
        fields = ['name', 'weight', 'kind', 'auto_from_tasks', 'position']


class ScoreForm(forms.ModelForm):
    class Meta:
        model = Score
        fields = ['obtained', 'maximum']


class TaskForm(forms.ModelForm):
    class Meta:
        model = Task
        fields = ['title', 'description', 'enrollment', 'assessment', 'status',
                  'priority', 'difficulty', 'due_at', 'estimated_minutes']
        widgets = {
            'due_at': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
            'description': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, user=None, **kwargs):
        """Restrict course pickers to the signed-in user's own enrollments."""
        super().__init__(*args, **kwargs)
        if user is not None:
            enrollments = Enrollment.objects.filter(user=user).select_related('course')
            self.fields['enrollment'].queryset = enrollments
            self.fields['assessment'].queryset = Assessment.objects.filter(
                enrollment__user=user,
            ).select_related('enrollment__course')


class NoteForm(forms.ModelForm):
    class Meta:
        model = Note
        fields = ['title', 'body', 'enrollment', 'pinned']
        widgets = {'body': forms.Textarea(attrs={'rows': 6})}

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        if user is not None:
            self.fields['enrollment'].queryset = Enrollment.objects.filter(user=user)
