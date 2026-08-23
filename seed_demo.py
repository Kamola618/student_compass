"""Local demo data.

Two students sharing one course catalogue, which is the point of the
Enrollment split: Course rows are common property, scores are not.

Run:  venv/Scripts/python.exe seed_demo.py
Idempotent — safe to re-run.
"""
import os
from datetime import timedelta

import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Admin.settings')
django.setup()

from django.contrib.auth.models import User  # noqa: E402
from django.utils import timezone  # noqa: E402

from main.models import (Assessment, Course, Enrollment, Score,  # noqa: E402
                         Semester, StudentProfile, Task)

# Older rows were saved as 'CS 305' before Course.save() normalised codes.
for course in Course.objects.all():
    normalized = Course.normalize_code(course.code)
    if course.code != normalized:
        Course.objects.filter(pk=course.pk).update(code=normalized)

SEMESTER, _ = Semester.objects.get_or_create(
    name='Fall 2026-2027', defaults={'start_date': '2026-09-01', 'is_active': True})


def account(username, first, last, student_id, group, program, password):
    user, _ = User.objects.get_or_create(
        username=username, defaults={'first_name': first, 'last_name': last})
    user.first_name, user.last_name = first, last
    user.set_password(password)
    user.save()
    StudentProfile.objects.get_or_create(user=user, defaults={
        'student_id': student_id, 'group': group, 'program': program})
    return user


def catalogue(code, title, department, credits=6, lec=0, tut=0, lab=0, elective=False):
    course, _ = Course.objects.get_or_create(
        code=Course.normalize_code(code),
        defaults={'title': title, 'department': department, 'credits': credits,
                  'ects': credits, 'lecture_hours': lec, 'tutorial_hours': tut,
                  'lab_hours': lab, 'is_elective': elective})
    return course


def enrol(user, course, teacher='', target=85):
    enrollment, _ = Enrollment.objects.get_or_create(
        user=user, course=course, semester=SEMESTER,
        defaults={'teacher': teacher, 'target_score': target})
    return enrollment


def assess(enrollment, rows):
    """rows: (name, weight, obtained or None, maximum or None)"""
    for i, (name, weight, obtained, maximum) in enumerate(rows):
        assessment, _ = Assessment.objects.get_or_create(
            enrollment=enrollment, name=name,
            defaults={'weight': weight, 'position': i,
                      'kind': (Assessment.Kind.FINAL if name == 'Final'
                               else Assessment.Kind.COURSEWORK)})
        if obtained is not None:
            Score.objects.get_or_create(assessment=assessment, defaults={
                'obtained': obtained, 'maximum': maximum, 'graded_at': timezone.now()})


# --- student one: Akbar, Software Engineering, mid-semester ----------------

akbar = account('akbar', 'Akbar', 'Evatov', '240418', 'JSE2',
                'Software Engineering', 'compass-akbar')
akbar.is_staff = akbar.is_superuser = True
akbar.save()

akbar_plan = [
    ('CS305', 'Introduction to Economics', 'Computer Science', '', 82,
     [('Midterm', 30, 78, 100), ('Final', 40, None, None), ('Quizzes', 30, 88, 100)]),
    ('CS310', 'Operating Systems', 'Computer Science', 'Khayotov Mukhammadali', 85,
     [('Midterm', 25, 91, 100), ('Labs', 35, None, None), ('Final', 40, None, None)]),
    ('SE301', 'Mobile Programming', 'Software Engineering', 'Khayotov Mukhammadali', 90,
     [('Project', 50, 94, 100), ('Final', 50, None, None)]),
    ('SE302', 'Fundamentals of Software Engineering', 'Software Engineering',
     'Toshnazarov Qobiljon', 85,
     [('Midterm', 30, 45, 100), ('Final', 70, None, None)]),
    # Code confirmed as CS331 by the semester-5 curriculum table, not CS401.
    ('CS331', 'Introduction to Machine Learning', 'Computer Science', '', 93,
     [('Assignments', 40, 96, 100), ('Midterm', 25, 89, 100), ('Final', 35, None, None)]),
]
for code, title, dept, teacher, target, rows in akbar_plan:
    assess(enrol(akbar, catalogue(code, title, dept), teacher, target), rows)

now = timezone.now()
for title, code, days, status, priority in [
    ('Rayleigh-Ritz Method write-up', 'CS310', 2, Task.Status.IN_PROGRESS, Task.Priority.HIGH),
    ('Mobile app prototype — screen flow', 'SE301', 5, Task.Status.NOT_STARTED, Task.Priority.HIGH),
    ('Reading: distributed scheduling', 'CS310', 9, Task.Status.NOT_STARTED, Task.Priority.LOW),
    ('Requirements document draft', 'SE302', 12, Task.Status.READY_TO_SUBMIT, Task.Priority.MEDIUM),
    ('Linear regression problem set', 'CS331', -3, Task.Status.DONE, Task.Priority.MEDIUM),
]:
    Task.objects.get_or_create(user=akbar, title=title, defaults={
        'enrollment': Enrollment.objects.filter(user=akbar, course__code=code).first(),
        'status': status, 'priority': priority, 'due_at': now + timedelta(days=days)})


# --- student two: Kamola, semester 5 curriculum from the shared table -----

kamola = account('kamola', 'Kamola', '', '', 'Semester 5', '', 'compass-kamola')

# Prerequisite courses referenced by the table. MATH221 and CS101 are already
# in Akbar's completed plan, so the two curricula genuinely share catalogue rows.
prereqs = {
    'MATH221': catalogue('MATH221', 'Discrete Mathematics', 'Math', lec=2, tut=2),
    'CS101': catalogue('CS101', 'Introduction to Programming', 'Computer Science', lec=1, lab=4),
    # Titles not known yet — stubs, fill in from the curriculum sheet.
    'CS311': catalogue('CS311', 'CS311', 'Computer Science'),
    'MATH101': catalogue('MATH101', 'MATH101', 'Math'),
}

semester_five = [
    ('MATH321', 'Introduction to Number Theory and Cryptography', 'Math', 2, 2, False, 'MATH221'),
    ('CS331', 'Introduction to Machine Learning', 'ComputerScience', 2, 2, False, 'CS101'),
    ('SEC111', 'Computer Security', 'Cybersecurity', 2, 2, False, 'CS311'),
    ('ED211', 'Assessment & Evaluation in Education', 'Education', 3, 0, False, None),
    ('MATH380', 'Foundations and Applications of Geometry', 'Math', 2, 2, True, 'MATH101'),
]
for code, title, dept, lec, tut, elective, prereq in semester_five:
    course = catalogue(code, title, dept, lec=lec, tut=tut, elective=elective)
    if prereq:
        course.prerequisites.add(prereqs[prereq])
    enrol(kamola, course)
    # No assessments seeded: their real weights aren't known, and inventing
    # them would be fabricating academic data. The empty state is the honest one.

print('akbar  :', Enrollment.objects.filter(user=akbar).count(), 'enrollments,',
      Task.objects.filter(user=akbar).count(), 'tasks')
print('kamola :', Enrollment.objects.filter(user=kamola).count(), 'enrollments')
print('catalogue:', Course.objects.count(), 'courses shared between them')
