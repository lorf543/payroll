# attendance/templatetags/filters.py
from django import template

register = template.Library()

@register.filter
def format_duration(duration):
    if not duration:
        return "0m"
    total_seconds = int(duration.total_seconds())
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    if hours > 0:
        return f"{hours}h {minutes:02d}m"
    return f"{minutes}m"
