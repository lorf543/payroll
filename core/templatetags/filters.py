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




@register.filter
def format_timedelta(value):
    """Convierte un timedelta en formato legible HH:MM:SS"""
    if not value:
        return "—"
    total_seconds = int(value.total_seconds())
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    if hours:
        return f"{hours}h {minutes:02d}m {seconds:02d}s"
    elif minutes:
        return f"{minutes}m {seconds:02d}s"
    else:
        return f"{seconds}s"
