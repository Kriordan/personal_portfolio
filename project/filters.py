"""
Custom Jinja template filters for the Flask application.

This module contains all custom template filters used across the application.
Filters are registered with the app via the register_filters function.
"""


def datetimeformat(value, format="%b %d, %Y"):
    """Format a datetime object for display in templates.

    Args:
        value: A datetime object to format
        format: strftime format string (default: "Jan 15, 2026")

    Returns:
        Formatted date string, or empty string if value is None

    Usage in templates:
        {{ some_date|datetimeformat }}
        {{ some_date|datetimeformat("%Y-%m-%d") }}
    """
    if value is None:
        return ""
    return value.strftime(format)


def register_filters(app):
    """Register all custom Jinja filters with the Flask app.

    Args:
        app (Flask): The Flask app instance.

    Returns:
        None
    """
    app.template_filter("datetimeformat")(datetimeformat)
