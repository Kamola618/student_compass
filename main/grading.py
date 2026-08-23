"""NewUU grading scale and pure grade arithmetic.

Kept free of Django imports so the rules can be tested directly and swapped
per-university later without touching the models.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Band:
    """One row of a grading scale: score >= min_score earns this letter."""
    min_score: float
    letter: str
    gpa: float


# NewUU scale, highest band first. band_for() relies on that ordering.
NEWUU_SCALE = (
    Band(93, 'A+', 4.5),
    Band(85, 'A', 4.0),
    Band(75, 'B+', 3.5),
    Band(65, 'B', 3.0),
    Band(60, 'C+', 2.75),
    Band(50, 'C', 2.5),
    Band(40, 'D', 2.0),
    Band(0, 'F', 0.0),
)

# Status values returned by target_status().
REACHED = 'reached'
NEEDED = 'needed'
UNREACHABLE = 'unreachable'


@dataclass(frozen=True)
class TargetStatus:
    """Answer to "what do I still need to hit my target?"

    status is one of REACHED / NEEDED / UNREACHABLE.
    needed_percent is the average percentage required across all ungraded
    work; it is set for NEEDED, and for UNREACHABLE when the shortfall is
    quantifiable (i.e. work remains but even perfect scores fall short).
    """
    status: str
    needed_percent: float | None = None
    reason: str = ''

    @property
    def is_reached(self) -> bool:
        return self.status == REACHED


def band_for(total: float, scale=NEWUU_SCALE) -> Band:
    for band in scale:
        if total >= band.min_score:
            return band
    return scale[-1]


def letter_for(total: float, scale=NEWUU_SCALE) -> str:
    return band_for(total, scale).letter


def gpa_for(total: float, scale=NEWUU_SCALE) -> float:
    return band_for(total, scale).gpa


def target_status(earned: float, remaining_weight: float, target: float) -> TargetStatus:
    """Work out what average score the remaining assessments must earn.

    earned            points already banked, on the same 0-100 scale as target
    remaining_weight  combined weight of assessments not yet graded
    target            total the student is aiming for
    """
    if earned >= target:
        return TargetStatus(REACHED)

    if remaining_weight <= 0:
        return TargetStatus(UNREACHABLE, reason='no_work_remaining')

    needed = (target - earned) / remaining_weight * 100

    if needed > 100:
        return TargetStatus(UNREACHABLE, needed_percent=round(needed, 1),
                            reason='exceeds_maximum')
    return TargetStatus(NEEDED, needed_percent=round(needed, 1))
