"""Jinja2 environment customization."""
from django.templatetags.static import static
from django.utils.formats import number_format
from django.urls import reverse


def environment(**options):
    from jinja2 import Environment

    env = Environment(**options)
    env.globals.update({"static": static, "url": reverse_url})
    env.filters["quantity"] = format_quantity
    return env


def reverse_url(viewname, *args, **kwargs):
    return reverse(viewname, args=args or None, kwargs=kwargs or None)


def format_quantity(value):
    if value is None:
        return "0"
    normalized = value.normalize() if hasattr(value, "normalize") else value
    decimal_places = max(0, min(3, -normalized.as_tuple().exponent)) if hasattr(normalized, "as_tuple") else 0
    return number_format(value, decimal_pos=decimal_places, use_l10n=True, force_grouping=True)
