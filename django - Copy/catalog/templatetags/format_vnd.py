from django import template
from django.utils.html import strip_tags

register = template.Library()


@register.filter
def vnd(value):
    try:
        n = int(float(value))
    except (TypeError, ValueError):
        return value
    return f"{n:,}".replace(",", ".")


@register.filter
def strip_html(value):
    if not value:
        return ""
    return strip_tags(str(value))
