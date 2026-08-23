from django.contrib import admin

from .models import (Assessment, Course, Enrollment, Note, Score, Semester,
                     StudentProfile, Task)


class AssessmentInline(admin.TabularInline):
    model = Assessment
    extra = 0


@admin.register(Enrollment)
class EnrollmentAdmin(admin.ModelAdmin):
    list_display = ('user', 'course', 'semester', 'target_score')
    list_filter = ('semester', 'user')
    inlines = [AssessmentInline]


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ('code', 'title', 'credits', 'department')
    search_fields = ('code', 'title')
    filter_horizontal = ('prerequisites',)


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ('title', 'user', 'enrollment', 'status', 'priority', 'due_at')
    list_filter = ('status', 'priority')


admin.site.register([Semester, StudentProfile, Assessment, Score, Note])
