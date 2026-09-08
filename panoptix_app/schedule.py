"""Weekly slots use the computer's local time, Monday first, end exclusive."""
from datetime import datetime, time, timedelta
import math


def parse_hhmm(value: str, fallback: time) -> time:
    try:
        hour, minute = str(value).split(":", 1)
        return time(max(0, min(23, int(hour))), max(0, min(59, int(minute))))
    except (TypeError, ValueError):
        return fallback


def validate_weekly_schedule(value):
    if value is None:
        return None  # Existing installations keep their exact daily times until saved.
    if not isinstance(value, list) or len(value) != 7:
        raise ValueError("Weekly timetable must contain seven days, Monday to Sunday")
    if any(not isinstance(day, list) or len(day) != 48 or any(type(slot) is not bool for slot in day) for day in value):
        raise ValueError("Each timetable day must contain 48 on/off half-hour slots")
    return [list(day) for day in value]


def timetable_for_editor(settings: dict) -> list[list[bool]]:
    value = settings.get("background_weekly_schedule")
    if value is not None:
        return validate_weekly_schedule(value)
    start = parse_hhmm(settings.get("background_start_time", "09:00"), time(9))
    end = parse_hhmm(settings.get("background_end_time", "15:30"), time(15, 30))
    first = (start.hour * 60 + start.minute) // 30
    last = math.ceil((end.hour * 60 + end.minute) / 30)
    day = [(first <= slot < last if start <= end else slot >= first or slot < last) for slot in range(48)]
    return [list(day) for _ in range(7)]


def active_schedule_window(settings: dict, now: datetime | None = None) -> str | None:
    current = now or datetime.now()
    weekly = settings.get("background_weekly_schedule")
    if weekly is None:
        start = parse_hhmm(settings.get("background_start_time", "09:00"), time(9))
        end = parse_hhmm(settings.get("background_end_time", "15:30"), time(15, 30))
        active = start <= current.time() <= end if start <= end else current.time() >= start or current.time() <= end
        if not active:
            return None
        date = current.date() - timedelta(days=int(start > end and current.time() <= end))
        return f"{date}:{start}:{end}"
    weekly = validate_weekly_schedule(weekly)
    index = current.weekday() * 48 + current.hour * 2 + current.minute // 30
    slots = [slot for day in weekly for slot in day]
    if not slots[index]:
        return None
    if all(slots):
        return "weekly-continuous"
    beginning = current.replace(minute=(current.minute // 30) * 30, second=0, microsecond=0)
    # Adjacent slots (even across Sunday/Monday) are a single capture block.
    for offset in range(1, 336):
        if not slots[(index - offset) % 336]:
            break
        beginning -= timedelta(minutes=30)
    return f"weekly:{beginning.isoformat()}"


def daily_window_is_active(settings: dict, now: datetime | None = None) -> bool:
    """Compatibility name used by status clients; supports either schedule format."""
    return active_schedule_window(settings, now) is not None
