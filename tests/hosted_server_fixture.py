"""Only imported by isolated Gunicorn tests; never a production entry point."""
import os
import threading

from project import create_app


def app():
    application = create_app()  # Exercise the real environment configuration.
    assert not any(thread.name == "learning-ai-worker" for thread in threading.enumerate())
    if os.environ.get("HOSTED_FIXTURE_FAKE_AI") == "1":
        application.config.update(LEARNING_AI_PROVIDER="fake", LEARNING_AI_MODEL="fake-interviewer",
            LEARNING_AI_SELECTOR_MODEL="fake-interviewer", LEARNING_AI_FEEDBACK_MODEL="fake-interviewer")
        from project.services.learning_ai_provider import OpenAIProvider
        def forbidden(*args, **kwargs):
            raise AssertionError("Hosted server tests must never contact a paid provider")
        OpenAIProvider.call = forbidden
    return application
