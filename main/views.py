from django.shortcuts import render
from .models import *
from django.shortcuts import render, redirect
from .forms import AssignmentForm, CourseForm
from django.shortcuts import get_object_or_404
from django.contrib.auth.decorators import login_required


def dashboard(request):
    return render(request, 'dashboard.html')

def courses(request):
    courses = Course.objects.all()
    return render(request, 'courses.html', {'courses': courses})

from django.utils import timezone

def assignments(request):
    if request.method == 'POST':
        for key, value in request.POST.items():
            if key.startswith('score_') and value != '':
                aid = key.replace('score_', '')
                a = Assignment.objects.filter(id=aid).first()
                if a:
                    a.score = float(value)
                    a.save()
        return redirect('assignments')

    now = timezone.now()
    upcoming = Assignment.objects.filter(due_date__gte=now).order_by('due_date')
    completed = Assignment.objects.filter(due_date__lt=now).order_by('-due_date')
    return render(request, 'assignments.html', {'upcoming': upcoming, 'completed': completed})

def add_assignment(request):
    if request.method == 'POST':
        form = AssignmentForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('assignments')
    else:
        form = AssignmentForm()
    return render(request, 'add_assignment.html', {'form': form})

def edit_assignment(request, id):
    assignment = get_object_or_404(Assignment, id=id)
    if request.method == 'POST':
        form = AssignmentForm(request.POST, instance=assignment)
        if form.is_valid():
            form.save()
            return redirect('assignments')
    else:
        form = AssignmentForm(instance=assignment)
    return render(request, 'add_assignment.html', {'form': form})

def delete_assignment(request, id):
    assignment = get_object_or_404(Assignment, id=id)
    if request.method == 'POST':
        assignment.delete()
        return redirect('assignments')
    return render(request, 'delete_assignment.html', {'assignment': assignment})

def add_course(request):
    if request.method == 'POST':
        form = CourseForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('courses')
    else:
        form = CourseForm()
    return render(request, 'add_course.html', {'form': form})

def grades(request):
    grades = Grade.objects.select_related('course').all()
    results = []
    for g in grades:
        raw = request.GET.get(f'target_{g.id}')
        try:
            target = float(raw) if raw else 70
        except ValueError:
            target = 70
        results.append({
            'grade': g,
            'target_raw': raw or '',
            'status': g.target_status(target),
        })

    
    return render(request, 'grades.html', {'results': results})

from .forms import AssignmentForm, CourseForm, GradeForm

def edit_grade(request, course_id):
    course = get_object_or_404(Course, id=course_id)
    grade, created = Grade.objects.get_or_create(course=course)
    if request.method == 'POST':
        form = GradeForm(request.POST, instance=grade)
        if form.is_valid():
            form.save()
            return redirect('grades')
    else:
        form = GradeForm(instance=grade)
    return render(request, 'edit_grade.html', {'form': form, 'course': course})

from django.contrib.auth.decorators import login_required

@login_required
def grades(request):
    if request.method == 'POST':
        for key, value in request.POST.items():
            if key.startswith('score_') and value:
                sg_id = key.replace('score_', '')
                sg = StudentGrade.objects.filter(id=sg_id, user=request.user).first()
                if sg:
                    sg.score = float(value)
                    sg.save()
        return redirect('grades')

    courses = Course.objects.all()
    results = []
    for course in courses:
        rows = []
        for a in course.assessments.all():
            if not a.auto_calculated:
                sg, _ = StudentGrade.objects.get_or_create(assessment=a, user=request.user)
            else:
                sg = None
            rows.append({'assessment': a, 'grade': sg, 'score': course.score_for(a, request.user)})

        target_raw = request.GET.get(f'target_{course.id}')
        try:
            target = float(target_raw) if target_raw else 70
        except ValueError:
            target = 70

        results.append({
            'course': course, 'rows': rows,
            'total': course.total_for(request.user),
            'letter': course.letter_for(request.user),
            'gpa': course.gpa_for(request.user),
            'target_raw': target_raw or '',
            'status': course.target_status_for(request.user, target),
        })
    return render(request, 'grades.html', {'results': results})