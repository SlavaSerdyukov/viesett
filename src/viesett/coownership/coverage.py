from datetime import date, timedelta

from viesett.domain.coownership import Coverage, CoverageInterval


def years_before(value: date, years: int) -> date:
    try:
        return value.replace(year=value.year - years)
    except ValueError:
        return value.replace(year=value.year - years, day=28)


def coverage(when: date, years: int, periods: list[CoverageInterval]) -> Coverage:
    start = years_before(when, years)
    clipped = [
        p.model_copy(update={"start": max(start, p.start), "end": min(when, p.end)})
        for p in periods
        if p.end >= start and p.start <= when
    ]
    clipped.sort(key=lambda p: (p.start, p.end))
    cursor = start
    gaps = []
    for period in clipped:
        if period.start > cursor:
            gaps.append(CoverageInterval(start=cursor, end=period.start - timedelta(days=1)))
        cursor = max(cursor, period.end + timedelta(days=1))
    if cursor <= when:
        gaps.append(CoverageInterval(start=cursor, end=when))
    return Coverage(coverage_start=start, coverage_end=when, periods_present=clipped, gaps=gaps)
