from django.contrib.auth.models import User
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models

from . import grading


class StudentProfile(models.Model):
    """Academic identity attached to a Django user."""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    student_id = models.CharField(max_length=20, blank=True)
    program = models.CharField(max_length=200, blank=True)
    group = models.CharField(max_length=50, blank=True)
    enrollment_year = models.PositiveIntegerField(null=True, blank=True)
    target_gpa = models.FloatField(default=3.5)

    def __str__(self):
        return f'{self.user.get_full_name() or self.user.username} ({self.group})'


class Semester(models.Model):
    name = models.CharField(max_length=100, unique=True)
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=False)

    class Meta:
        ordering = ['-start_date']

    def __str__(self):
        return self.name


class Course(models.Model):
    """A catalogue entry, shared by every student who takes it.

    Deliberately has no owner: one student filling in SE201's details makes
    them available to everyone else in the group. Personal data belongs on
    Enrollment instead.
    """
    code = models.CharField(max_length=20, unique=True)
    title = models.CharField(max_length=200)
    department = models.CharField(max_length=100, blank=True)
    description = models.TextField(blank=True)
    credits = models.PositiveIntegerField(default=6)
    ects = models.PositiveIntegerField(default=6)
    lecture_hours = models.PositiveIntegerField(default=0)
    tutorial_hours = models.PositiveIntegerField(default=0)
    lab_hours = models.PositiveIntegerField(default=0)
    is_elective = models.BooleanField(default=False)
    prerequisites = models.ManyToManyField(
        'self', symmetrical=False, related_name='postrequisites', blank=True,
    )

    class Meta:
        ordering = ['code']

    def __str__(self):
        return f'{self.code} {self.title}'

    @staticmethod
    def normalize_code(code):
        """Fold 'MATH 221', 'math221' and 'MATH221' onto one key.

        Course codes arrive from three places — the academic plan, curriculum
        tables, and whatever a student types — each spaced differently. Without
        this, two students adding the same course create two catalogue entries
        and the shared catalogue quietly stops being shared.
        """
        return ''.join(code.split()).upper()

    def save(self, *args, **kwargs):
        self.code = self.normalize_code(self.code)
        return super().save(*args, **kwargs)


class Enrollment(models.Model):
    """One student taking one course in one semester. Ownership lives here."""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='enrollments')
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='enrollments')
    semester = models.ForeignKey(Semester, on_delete=models.CASCADE, related_name='enrollments')
    teacher = models.CharField(max_length=200, blank=True)
    office = models.CharField(max_length=100, blank=True)
    office_hours = models.CharField(max_length=100, blank=True)
    color = models.CharField(max_length=20, blank=True)
    target_score = models.FloatField(
        default=85,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text='Total this student is aiming for, on a 0-100 scale.',
    )

    class Meta:
        unique_together = ('user', 'course', 'semester')
        ordering = ['course__code']

    def __str__(self):
        return f'{self.user.username} — {self.course.code}'

    # --- grade engine -----------------------------------------------------

    def score_percent(self, assessment):
        """This student's percentage on one assessment, or None if ungraded."""
        if assessment.auto_from_tasks:
            return assessment.task_average()
        score = getattr(assessment, 'score', None)
        return score.percent if score else None

    def _weight_split(self):
        """Return (earned points, weight still ungraded) across assessments."""
        earned = 0.0
        remaining = 0.0
        for assessment in self.assessments.all():
            percent = self.score_percent(assessment)
            if percent is None:
                remaining += assessment.weight
            else:
                earned += percent / 100 * assessment.weight
        return earned, remaining

    def total(self):
        """Points banked so far, on a 0-100 scale."""
        earned, _ = self._weight_split()
        return round(earned, 1)

    def projected_total(self):
        """Total if every ungraded assessment scored the same as the current average.

        Falls back to the banked total when nothing is graded yet.
        """
        earned, remaining = self._weight_split()
        graded_weight = self.total_weight() - remaining
        if graded_weight <= 0:
            return round(earned, 1)
        average = earned / graded_weight * 100
        return round(earned + remaining * average / 100, 1)

    def total_weight(self):
        return sum(a.weight for a in self.assessments.all())

    def letter(self):
        """Letter for points banked so far. Only meaningful once everything is graded."""
        return grading.letter_for(self.total())

    def gpa(self):
        return grading.gpa_for(self.total())

    # Display helpers. A half-finished course has most of its weight ungraded, so
    # total() reads as an F until the final lands — true, but useless to look at.
    # Anything shown as "where you stand" should use the projection instead.

    def projected_letter(self):
        return grading.letter_for(self.projected_total())

    def projected_gpa(self):
        return grading.gpa_for(self.projected_total())

    def is_fully_graded(self):
        assessments = list(self.assessments.all())
        return bool(assessments) and not any(
            self.score_percent(a) is None for a in assessments
        )

    def has_any_grade(self):
        """True once at least one assessment has a score.

        Until then there is nothing to project from, and showing 0.0 / F for a
        semester that has not started yet is worse than showing nothing.
        """
        return any(self.score_percent(a) is not None for a in self.assessments.all())

    def target_status(self, target=None):
        """What average the remaining work needs to hit the target."""
        earned, remaining = self._weight_split()
        goal = self.target_score if target is None else target
        return grading.target_status(earned, remaining, goal)


class Assessment(models.Model):
    """A weighted component of a course grade, for one student."""

    class Kind(models.TextChoices):
        INTERMEDIATE = 'intermediate', 'Intermediate control'
        FINAL = 'final', 'Final control'
        COURSEWORK = 'coursework', 'Coursework'

    enrollment = models.ForeignKey(Enrollment, on_delete=models.CASCADE, related_name='assessments')
    name = models.CharField(max_length=100)
    weight = models.FloatField(validators=[MinValueValidator(0), MaxValueValidator(100)])
    kind = models.CharField(max_length=20, choices=Kind.choices, default=Kind.COURSEWORK)
    auto_from_tasks = models.BooleanField(
        default=False,
        help_text='Derive this score from the average of its graded tasks.',
    )
    position = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['position', 'id']

    def __str__(self):
        return f'{self.enrollment.course.code} — {self.name}'

    def task_average(self):
        """Mean percentage across this assessment's graded tasks, or None."""
        percentages = [t.percent for t in self.tasks.all() if t.percent is not None]
        if not percentages:
            return None
        return sum(percentages) / len(percentages)


class Score(models.Model):
    """A mark recorded against an assessment, stored as obtained out of maximum."""
    assessment = models.OneToOneField(Assessment, on_delete=models.CASCADE, related_name='score')
    obtained = models.FloatField(null=True, blank=True)
    maximum = models.FloatField(default=100, validators=[MinValueValidator(0.01)])
    graded_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f'{self.assessment} — {self.obtained}/{self.maximum}'

    @property
    def percent(self):
        if self.obtained is None or not self.maximum:
            return None
        return self.obtained / self.maximum * 100


class Task(models.Model):
    """A unit of work, with the lifecycle the university platform uses."""

    class Status(models.TextChoices):
        NOT_STARTED = 'not_started', 'Not started'
        IN_PROGRESS = 'in_progress', 'In progress'
        READY_TO_SUBMIT = 'ready_to_submit', 'Ready to submit'
        UNDER_REVIEW = 'under_review', 'Under review'
        DONE = 'done', 'Done'
        MISSED = 'missed', 'Not submitted'
        ARCHIVED = 'archived', 'Archived'

    class Priority(models.TextChoices):
        HIGH = 'high', 'High'
        MEDIUM = 'medium', 'Medium'
        LOW = 'low', 'Low'

    # Denormalised from enrollment so standalone tasks (no course) still have an owner.
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='tasks')
    enrollment = models.ForeignKey(
        Enrollment, on_delete=models.CASCADE, related_name='tasks', null=True, blank=True,
    )
    assessment = models.ForeignKey(
        Assessment, on_delete=models.SET_NULL, related_name='tasks', null=True, blank=True,
        help_text='Link to an assessment to feed its auto-calculated score.',
    )
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.NOT_STARTED)
    priority = models.CharField(max_length=10, choices=Priority.choices, default=Priority.MEDIUM)
    difficulty = models.PositiveIntegerField(
        default=3, validators=[MinValueValidator(1), MaxValueValidator(5)],
    )
    due_at = models.DateTimeField(null=True, blank=True)
    estimated_minutes = models.PositiveIntegerField(null=True, blank=True)
    actual_minutes = models.PositiveIntegerField(null=True, blank=True)
    obtained = models.FloatField(null=True, blank=True)
    maximum = models.FloatField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['due_at', '-priority']

    def __str__(self):
        return self.title

    @property
    def percent(self):
        if self.obtained is None or not self.maximum:
            return None
        return self.obtained / self.maximum * 100

    @property
    def is_open(self):
        return self.status not in (self.Status.DONE, self.Status.ARCHIVED, self.Status.MISSED)


class Note(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notes')
    enrollment = models.ForeignKey(
        Enrollment, on_delete=models.CASCADE, related_name='notes', null=True, blank=True,
    )
    title = models.CharField(max_length=200)
    body = models.TextField(blank=True)
    pinned = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-pinned', '-updated_at']

    def __str__(self):
        return self.title
