"""Opt-in error reporting. Application content is never diagnostic context."""
import os
import re
from uuid import UUID, uuid4

from flask import g, has_request_context, request

SAFE_CODES = {"invalid_request", "invalid_request_id", "provider_auth", "provider_quota", "invalid_summary", "failed"}


def valid_request_id(value):
    try:
        return isinstance(value, str) and str(UUID(value)) == value
    except (ValueError, TypeError, AttributeError):
        return False


def scrub_event(event, hint):
    """Allowlist the outgoing payload, including automatic Flask exceptions."""
    hint.pop("attachments", None)
    clean = {key: event[key] for key in ("event_id", "timestamp", "platform", "level", "release", "environment", "sdk") if key in event}
    clean["user"] = {"ip_address": "0.0.0.0"}
    incoming, tags = event.get("tags", {}), {}
    if valid_request_id(incoming.get("request_id")):
        tags["request_id"] = incoming["request_id"]
    if incoming.get("operation") == "jobwizard.extraction":
        tags["operation"] = "jobwizard.extraction"
    if incoming.get("phase") in {"read", "summary", "status"}:
        tags["phase"] = incoming["phase"]
    if incoming.get("code") in SAFE_CODES:
        tags["code"] = incoming["code"]
    clean["tags"] = tags
    exceptions = []
    for item in event.get("exception", {}).get("values", []):
        kind = item.get("type", "Error")
        exception = {"type": kind if re.fullmatch(r"[\w.]{1,100}", kind) else "Error", "value": "Unexpected application error"}
        frames = []
        for frame in item.get("stacktrace", {}).get("frames", []):
            location = {key: frame[key] for key in ("function", "module", "lineno", "colno", "in_app") if key in frame}
            if isinstance(frame.get("filename"), str):
                location["filename"] = frame["filename"].split("?", 1)[0][-512:]
            frames.append(location)
        exception["stacktrace"] = {"frames": frames}
        if item.get("mechanism"):
            exception["mechanism"] = {key: item["mechanism"][key] for key in ("type", "handled") if key in item["mechanism"]}
        exceptions.append(exception)
    if exceptions:
        clean["exception"] = {"values": exceptions}
    else:
        clean["message"] = "Jobwizard extraction failed" if tags.get("operation") else "Application error"
    return clean


def configure_monitoring(app, *, transport=None):
    """No SDK initialization or network transmission until explicitly enabled."""
    enabled = app.config.get("SENTRY_ENABLED", os.getenv("SENTRY_ENABLED") == "1")
    dsn = app.config.get("SENTRY_DSN", os.getenv("SENTRY_DSN"))
    active = False
    if enabled and dsn and (not app.testing or transport is not None):
        import sentry_sdk
        from sentry_sdk.integrations.flask import FlaskIntegration
        options = dict(
            dsn=dsn,
            environment=app.config.get("SENTRY_ENVIRONMENT", os.getenv("SENTRY_ENVIRONMENT", "production")),
            release=os.getenv("SENTRY_RELEASE") or os.getenv("HEROKU_SLUG_COMMIT"),
            default_integrations=False,
            auto_enabling_integrations=False,
            integrations=[FlaskIntegration()],
            data_collection={
                "user_info": False,
                "cookies": {"mode": "off"},
                "http_headers": {"request": {"mode": "off"}},
                "http_bodies": [],
                "url_query_params": {"mode": "off"},
                "graphql": {"document": False, "variables": False},
                "gen_ai": {"inputs": False, "outputs": False},
                "database_query_data": False,
                "queues": False,
                "stack_frame_variables": False,
                "frame_context_lines": 0,
            },
            max_request_body_size="never",
            max_breadcrumbs=0,
            auto_session_tracking=False,
            enable_logs=False,
            enable_metrics=False,
            propagate_traces=False,
            trace_propagation_targets=[],
            before_send=scrub_event,
            before_breadcrumb=lambda _crumb, _hint: None,
        )
        if transport is not None:
            options["transport"] = transport
        try:
            sentry_sdk.init(**options)
            active = True
        except Exception:
            # Bad configuration or reporting failures must not break Flask.
            app.logger.warning("Error reporting initialization failed; reporting is disabled.")
    app.extensions["error_reporting_enabled"] = active

    @app.before_request
    def correlate_request():
        if not request.path.startswith("/api/v1/"):
            return
        incoming = request.headers.get("X-Request-ID")
        g.error_request_id = incoming if valid_request_id(incoming) else str(uuid4())
        if active:
            import sentry_sdk
            sentry_sdk.set_tag("request_id", g.error_request_id)

    @app.after_request
    def correlate_response(response):
        if getattr(g, "error_request_id", None):
            response.headers["X-Request-ID"] = g.error_request_id
        return response


def report_extraction_failure(phase, code, *, attempt_id=None, exception=None):
    from flask import current_app
    if not current_app.extensions.get("error_reporting_enabled") or code not in SAFE_CODES:
        return
    import sentry_sdk
    try:
        with sentry_sdk.new_scope() as scope:
            scope.set_tag("operation", "jobwizard.extraction")
            scope.set_tag("phase", phase)
            scope.set_tag("code", code)
            identifier = attempt_id or (getattr(g, "error_request_id", None) if has_request_context() else None)
            if valid_request_id(identifier):
                scope.set_tag("request_id", identifier)
            if exception is not None:
                sentry_sdk.capture_exception(exception)
            else:
                sentry_sdk.capture_message("Jobwizard extraction failed", level="error")
    except Exception:
        pass  # Never retry provider work or change an API result for telemetry.
