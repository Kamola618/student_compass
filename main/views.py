from django.contrib.auth.decorators import login_required
from django.db.models import Prefetch
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .forms import AssessmentForm, EnrollmentForm, NoteForm, TaskForm
from .models import Assessment, Enrollment, Score, Task


def _enrollments_for(user):
    """Every enrollment the user owns, with the rows the grade engine needs."""
    return (
        Enrollment.objects
        .filter(user=user)
        .select_related('course', 'semester')
        .prefetch_related('course__prerequisites')
        .prefetch_related(
            Prefetch('assessments', queryset=Assessment.objects.select_related('score')),
            'assessments__tasks',
        )
    )


@login_required
def dashboard(request):
    enrollments = list(_enrollments_for(request.user))
    open_tasks = (
        Task.objects
        .filter(user=request.user, due_at__isnull=False)
        .exclude(status__in=[Task.Status.DONE, Task.Status.ARCHIVED, Task.Status.MISSED])
        .select_related('enrollment__course')
        .order_by('due_at')[:5]
    )

    graded = [e for e in enrollments if e.has_any_grade()]
    credits = sum(e.course.credits for e in graded)
    weighted_gpa = (
        round(sum(e.projected_gpa() * e.course.credits for e in graded) / credits, 2)
        if credits else None
    )

    return render(request, 'dashboard.html', {
        'enrollments': enrollments,
        'open_tasks': open_tasks,
        'semester_gpa': weighted_gpa,
        'now': timezone.now(),
    })


@login_required
def courses(request):
    return render(request, 'courses.html', {'enrollments': _enrollments_for(request.user)})


@login_required
def add_course(request):
    if request.method == 'POST':
        form = EnrollmentForm(request.POST)
        if form.is_valid():
            enrollment = form.save(commit=False)
            enrollment.user = request.user
            enrollment.save()
            return redirect('courses')
    else:
        form = EnrollmentForm()
    return render(request, 'add_course.html', {'form': form})


@login_required
def grades(request):
    """Grade table plus the target calculator, per enrollment."""
    if request.method == 'POST':
        _save_scores(request)
        return redirect('grades')

    results = []
    for enrollment in _enrollments_for(request.user):
        rows = [
            {'assessment': a, 'percent': enrollment.score_percent(a)}
            for a in enrollment.assessments.all()
        ]
        target = _requested_target(request, enrollment)
        results.append({
            'enrollment': enrollment,
            'rows': rows,
            'total': enrollment.total(),
            'projected': enrollment.projected_total(),
            'letter': enrollment.letter(),
            'gpa': enrollment.gpa(),
            'projected_letter': enrollment.projected_letter(),
            'projected_gpa': enrollment.projected_gpa(),
            'target': target,
            'status': enrollment.target_status(target),
        })
    return render(request, 'grades.html', {'results': results})


def _requested_target(request, enrollment):
    """Target from the query string, falling back to the enrollment's own."""
    raw = request.GET.get(f'target_{enrollment.id}')
    try:
        return float(raw) if raw else enrollment.target_score
    except ValueError:
        return enrollment.target_score


def _save_scores(request):
    """Persist score_<assessment_id> fields, ignoring assessments not owned by the user."""
    owned = {
        a.id: a for a in Assessment.objects.filter(enrollment__user=request.user)
    }
    for key, value in request.POST.items():
        if not key.startswith('score_'):
            continue
        try:
            assessment = owned[int(key.removeprefix('score_'))]
        except (ValueError, KeyError):
            continue
        score, _ = Score.objects.get_or_create(assessment=assessment)
        if value == '':
            score.obtained = None
        else:
            try:
                score.obtained = float(value)
            except ValueError:
                continue
        score.graded_at = timezone.now() if score.obtained is not None else None
        score.save()


@login_required
def tasks(request):
    owned = Task.objects.filter(user=request.user).select_related('enrollment__course')
    now = timezone.now()
    return render(request, 'tasks.html', {
        'open_tasks': owned.exclude(
            status__in=[Task.Status.DONE, Task.Status.ARCHIVED, Task.Status.MISSED],
        ).order_by('due_at'),
        'closed_tasks': owned.filter(
            status__in=[Task.Status.DONE, Task.Status.MISSED],
        ).order_by('-updated_at')[:20],
        'statuses': Task.Status.choices,
        'now': now,
    })


@login_required
def add_task(request):
    if request.method == 'POST':
        form = TaskForm(request.POST, user=request.user)
        if form.is_valid():
            task = form.save(commit=False)
            task.user = request.user
            task.save()
            return redirect('tasks')
    else:
        form = TaskForm(user=request.user)
    return render(request, 'task_form.html', {'form': form, 'mode': 'add'})


@login_required
def edit_task(request, id):
    task = get_object_or_404(Task, id=id, user=request.user)
    if request.method == 'POST':
        form = TaskForm(request.POST, instance=task, user=request.user)
        if form.is_valid():
            form.save()
            return redirect('tasks')
    else:
        form = TaskForm(instance=task, user=request.user)
    return render(request, 'task_form.html', {'form': form, 'mode': 'edit', 'task': task})


@login_required
def delete_task(request, id):
    task = get_object_or_404(Task, id=id, user=request.user)
    if request.method == 'POST':
        task.delete()
        return redirect('tasks')
    return render(request, 'task_confirm_delete.html', {'task': task})
