from datetime import date, datetime, timezone


def normalize_datetime(d):
    if d.tzinfo is None:
        d = d.replace(tzinfo=timezone.utc)
    else:
        d = d.astimezone(timezone.utc)

    d = d.replace(second=0, microsecond=0)
    return d


def normalize_date(d):
    if isinstance(d, datetime):
        d = d.date()
    return d


def compare_date(date1, date2):
    if isinstance(date1, datetime) and isinstance(date2, datetime):
        date1 = normalize_datetime(date1)
        date2 = normalize_datetime(date2)
    elif isinstance(date1, date) or isinstance(date2, date):
        date1 = normalize_date(date1)
        date2 = normalize_date(date2)
    return date1 == date2
