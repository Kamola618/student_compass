import pytest
from django.contrib.auth.models import User

from main import grading
from main.models import Assessment, Course, Enrollment, Score, Semester, Task


# --- pure grading rules ---------------------------------------------------

@pytest.mark.parametrize('total,letter,gpa', [
    (100, 'A+', 4.5),
    (93, 'A+', 4.5),      # lower boundary of A+
    (92.9, 'A', 4.0),
    (85, 'A', 4.0),
    (65, 'B', 3.0),
    (40, 'D', 2.0),
    (39.9, 'F', 0.0),
    (0, 'F', 0.0),
])
def test_scale_boundaries(total, letter, gpa):
    assert grading.letter_for(total) == letter
    assert grading.gpa_for(total) == gpa


def test_target_already_reached():
    status = grading.target_status(earned=88, remaining_weight=20, target=85)
    assert status.status == grading.REACHED
    assert status.is_reached


def test_target_needs_a_specific_average():
    # 60 points banked, 40% of the grade left, aiming for 85 overall.
    status = grading.target_status(earned=60, remaining_weight=40, target=85)
    assert status.status == grading.NEEDED
    assert status.needed_percent == 62.5


def test_target_unreachable_when_perfect_is_not_enough():
    status = grading.target_status(earned=30, remaining_weight=20, target=85)
    assert status.status == grading.UNREACHABLE
    assert status.reason == 'exceeds_maximum'
    assert status.needed_percent == 275.0


def test_target_unreachable_when_nothing_is_left():
    status = grading.target_status(earned=70, remaining_weight=0, target=85)
    assert status.status == grading.UNREACHABLE
    assert status.reason == 'no_work_remaining'


def test_exact_target_counts_as_reached():
    assert grading.target_status(85, 15, 85).is_reached


# --- fixtures -------------------------------------------------------------

@pytest.fixture
def semester(db):
    return Semester.objects.create(name='Fall 2026-2027', start_date='2026-09-01', is_active=True)


@pytest.fixture
def course(db):
    return Course.objects.create(code='SE201', title='Web Programming', credits=6)


@pytest.fixture
def enrollment(db, semester, course):
    user = User.objects.create_user('akbar', password='x')
    return Enrollment.objects.create(user=user, course=course, semester=semester, target_score=85)


def graded(enrollment, name, weight, obtained, maximum=100):
    assessment = Assessment.objects.create(enrollment=enrollment, name=name, weight=weight)
    Score.objects.create(assessment=assessment, obtained=obtained, maximum=maximum)
    return assessment


# --- the engine on real rows ---------------------------------------------

def test_total_counts_only_graded_weight(enrollment):
    graded(enrollment, 'Midterm', 30, 80)
    Assessment.objects.create(enrollment=enrollment, name='Final', weight=40)
    # 80% of 30 points banked; the ungraded final contributes nothing yet.
    assert enrollment.total() == 24.0


def test_score_is_stored_as_obtained_out_of_maximum(enrollment):
    assessment = graded(enrollment, 'Quiz 1', 20, obtained=17.5, maximum=20)
    assert enrollment.score_percent(assessment) == 87.5


def test_ungraded_assessment_reads_as_none(enrollment):
    assessment = Assessment.objects.create(enrollment=enrollment, name='Final', weight=40)
    assert enrollment.score_percent(assessment) is None


def test_target_status_uses_the_enrollments_own_target(enrollment):
    graded(enrollment, 'Midterm', 60, 100)
    Assessment.objects.create(enrollment=enrollment, name='Final', weight=40)
    # 60 banked, 40 weight left, target 85 -> needs 62.5% on the final.
    assert enrollment.target_status().needed_percent == 62.5


def test_projected_total_extrapolates_current_average(enrollment):
    graded(enrollment, 'Midterm', 50, 90)
    Assessment.objects.create(enrollment=enrollment, name='Final', weight=50)
    assert enrollment.total() == 45.0        # only the midterm has landed
    assert enrollment.projected_total() == 90.0  # assumes the final matches


def test_projected_total_survives_a_fully_ungraded_course(enrollment):
    Assessment.objects.create(enrollment=enrollment, name='Final', weight=100)
    assert enrollment.projected_total() == 0.0


def test_auto_assessment_averages_its_tasks(enrollment):
    assessment = Assessment.objects.create(
        enrollment=enrollment, name='Labs', weight=40, auto_from_tasks=True,
    )
    for obtained in (8, 10):
        Task.objects.create(
            user=enrollment.user, enrollment=enrollment, assessment=assessment,
            title=f'Lab {obtained}', obtained=obtained, maximum=10,
        )
    # (80% + 100%) / 2
    assert enrollment.score_percent(assessment) == 90.0


def test_auto_assessment_ignores_ungraded_tasks(enrollment):
    assessment = Assessment.objects.create(
        enrollment=enrollment, name='Labs', weight=40, auto_from_tasks=True,
    )
    Task.objects.create(
        user=enrollment.user, enrollment=enrollment, assessment=assessment, title='Lab 1',
    )
    assert enrollment.score_percent(assessment) is None


def test_one_students_scores_never_leak_into_anothers(db, semester, course):
    """Regression: the old score_for() averaged every assignment on a course,
    ignoring the user it was given, so totals blended across students."""
    akbar = User.objects.create_user('akbar', password='x')
    other = User.objects.create_user('other', password='x')

    mine = Enrollment.objects.create(user=akbar, course=course, semester=semester)
    theirs = Enrollment.objects.create(user=other, course=course, semester=semester)

    graded(mine, 'Midterm', 100, 90)
    graded(theirs, 'Midterm', 100, 10)

    assert mine.total() == 90.0
    assert theirs.total() == 10.0


def test_banked_letter_and_projected_letter_diverge_mid_semester(enrollment):
    """A strong midterm with the final still pending should not read as an F.

    total() is points banked, so it is near zero mid-semester; the projection
    is what a student should actually be shown.
    """
    graded(enrollment, 'Midterm', 25, 91)
    Assessment.objects.create(enrollment=enrollment, name='Final', weight=75)

    assert enrollment.total() == 22.8
    assert enrollment.letter() == 'F'           # banked points, correct but misleading
    assert enrollment.projected_total() == 91.0
    assert enrollment.projected_letter() == 'A'  # what the dashboard shows


def test_is_fully_graded_flips_once_every_score_lands(enrollment):
    graded(enrollment, 'Midterm', 50, 80)
    final = Assessment.objects.create(enrollment=enrollment, name='Final', weight=50)
    assert enrollment.is_fully_graded() is False

    Score.objects.create(assessment=final, obtained=70, maximum=100)
    assert enrollment.is_fully_graded() is True
    # Once complete, banked and projected agree.
    assert enrollment.total() == enrollment.projected_total() == 75.0


# --- shared catalogue -----------------------------------------------------

@pytest.mark.parametrize('written,stored', [
    ('MATH 221', 'MATH221'),
    ('math221', 'MATH221'),
    ('MATH221', 'MATH221'),
    ('  se 301 ', 'SE301'),
])
def test_course_codes_normalise_to_one_key(db, written, stored):
    """Codes arrive spaced three different ways; duplicates would split the
    catalogue and break sharing between students."""
    assert Course.objects.create(code=written, title='X').code == stored


def test_two_students_share_one_catalogue_row(db, semester):
    """The onboarding premise: one course row, two enrollments, separate scores."""
    ml = Course.objects.create(code='CS331', title='Introduction to Machine Learning')
    akbar = User.objects.create_user('akbar', password='x')
    partner = User.objects.create_user('partner', password='x')

    mine = Enrollment.objects.create(user=akbar, course=ml, semester=semester)
    theirs = Enrollment.objects.create(user=partner, course=ml, semester=semester)

    graded(mine, 'Midterm', 100, 89)

    assert ml.enrollments.count() == 2
    assert mine.has_any_grade() is True
    assert theirs.has_any_grade() is False   # my score is invisible to them


def test_prerequisites_are_navigable_in_both_directions(db):
    discrete = Course.objects.create(code='MATH221', title='Discrete Mathematics')
    crypto = Course.objects.create(code='MATH321', title='Number Theory and Cryptography')
    crypto.prerequisites.add(discrete)

    assert list(crypto.prerequisites.all()) == [discrete]
    assert list(discrete.postrequisites.all()) == [crypto]


# --- the not-yet-graded state --------------------------------------------

def test_enrollment_with_no_scores_reports_no_grade(enrollment):
    Assessment.objects.create(enrollment=enrollment, name='Final', weight=100)
    assert enrollment.has_any_grade() is False
    assert enrollment.is_fully_graded() is False


def test_enrollment_with_no_assessments_is_not_fully_graded(enrollment):
    """An empty course must not claim to be complete."""
    assert enrollment.is_fully_graded() is False
    assert enrollment.has_any_grade() is False
