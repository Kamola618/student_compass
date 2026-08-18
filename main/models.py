from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db.models import Avg
from django.contrib.auth.models import User


class Semester(models.Model):
    name = models.CharField(max_length=100, unique=True)
    start_date = models.DateField()
    is_active = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class Course(models.Model):
    GRADE_SCALE = [(93, 'A+', 4.5), (85, 'A', 4.0), (75, 'B+', 3.5), (65, 'B', 3.0),
                   (60, 'C+', 2.75), (50, 'C', 2.5), (40, 'D', 2.0), (0, 'F', 0)]
    color = models.CharField(max_length=100)
    semester = models.ForeignKey(Semester, on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=100)
    teacher = models.CharField(max_length=200)
    office = models.CharField(max_length=100)
    office_hours = models.CharField(max_length=100)
    syllabus = models.TextField()
    created_at = models.DateField(auto_now_add=True)

    class Meta:
        unique_together = ('semester', 'name')

    def __str__(self):
        return self.name

    def score_for(self, assessment, user):
        if assessment.auto_calculated:
            avg = self.assignment_set.aggregate(Avg('score'))['score__avg']
            return avg or 0
        sg = StudentGrade.objects.filter(assessment=assessment, user=user).first()
        return sg.score if sg and sg.score is not None else None

    def total_for(self, user):
        total = 0
        for a in self.assessments.all():
            score = self.score_for(a, user)
            if score is not None:
                total += (score / 100) * a.weight
        return round(total, 1)

    def letter_for(self, user):
        total = self.total_for(user)
        for threshold, letter, gpa in self.GRADE_SCALE:
            if total >= threshold: return letter
        return 'F'

    def gpa_for(self, user):
        total = self.total_for(user)
        for threshold, letter, gpa in self.GRADE_SCALE:
            if total >= threshold: return gpa
        return 0

    def target_status_for(self, user, target):
        known, missing_weight = 0, 0
        for a in self.assessments.all():
            score = self.score_for(a, user)
            if score is not None:
                known += (score / 100) * a.weight
            else:
                missing_weight += a.weight
        if missing_weight == 0:
            return {'status': 'reached'} if known >= target else {'status': 'unreachable', 'reason': 'all_done'}
        needed = ((target - known) / missing_weight) * 100
        if needed <= 0: return {'status': 'reached'}
        if needed > 100: return {'status': 'unreachable', 'value': round(needed, 1)}
        return {'status': 'needed', 'value': round(needed, 1)}


class Assignment(models.Model):
    PRRT_CHOICES = [
        ('high', 'high'),
        ('med', 'med'),
        ('low', 'low'), ]
    name = models.CharField(max_length=200)
    course = models.ForeignKey(Course, on_delete=models.CASCADE)
    difficulty = models.IntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    priority = models.CharField(choices=PRRT_CHOICES, max_length=100)
    score = models.FloatField(null=True, blank=True)
    progress = models.IntegerField(
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    due_date = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    def __str__(self):
        return self.name

class Grade(models.Model):
    GRADE_SCALE = [
        (93, 'A+', 4.5),
        (85, 'A', 4.0),
        (75, 'B+', 3.5),
        (65, 'B', 3.0),
        (60, 'C+', 2.75),
        (50, 'C', 2.5),
        (40, 'D', 2.0),
        (0, 'F', 0),
    ]
    course = models.OneToOneField(Course, on_delete=models.CASCADE)
    midterm_weight = models.IntegerField()
    midterm_score = models.FloatField(null=True, blank=True)
    assignments_weight = models.IntegerField()
    final_weight = models.IntegerField()
    final_score = models.FloatField(null=True, blank=True)

    def __str__(self):
        return f"{self.course.name} grades"

    def assignments_average(self):
        avg = self.course.assignment_set.aggregate(Avg('score'))['score__avg']
        return avg or 0

    def current_total(self):
        total = 0
        if self.midterm_score is not None:
            total += (self.midterm_score / 100) * self.midterm_weight
        total += (self.assignments_average() / 100) * self.assignments_weight
        if self.final_score is not None:
            total += (self.final_score / 100) * self.final_weight
        return round(total, 1)

    def target_status(self, target):
        total = self.current_total()

        if self.final_score is not None:
            if total >= target:
                return {'status': 'reached'}
            return {'status': 'unreachable', 'reason': 'final_done'}

        if self.final_weight == 0:
            return {'status': 'unreachable', 'reason': 'no_final_weight'}

        remaining_points = target - total
        needed = (remaining_points / self.final_weight) * 100

        if needed <= 0:
            return {'status': 'reached'}
        if needed > 100:
            return {'status': 'unreachable', 'value': round(needed, 1)}
        return {'status': 'needed', 'value': round(needed, 1)}

    def letter_grade(self):
        total = self.current_total()
        for threshold, letter, gpa in self.GRADE_SCALE:
            if total >= threshold:
                return letter
        return 'F'

    def gpa_point(self):
        total = self.current_total()
        for threshold, letter, gpa in self.GRADE_SCALE:
            if total >= threshold:
                return gpa
        return 0


class Assessment(models.Model):
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='assessments')
    name = models.CharField(max_length=50)
    weight = models.IntegerField()
    auto_calculated = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.course.name} — {self.name}"


class StudentGrade(models.Model):
    assessment = models.ForeignKey(Assessment, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    score = models.FloatField(null=True, blank=True)

    class Meta:
        unique_together = ('assessment', 'user')











