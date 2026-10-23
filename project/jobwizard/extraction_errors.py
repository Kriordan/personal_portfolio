"""Public extraction errors contain fixed copy, never upstream responses."""
MESSAGES = {
    "unavailable": "Suggestions are unavailable. You can still save this job manually.",
    "unsupported": "Use a public Gem, Greenhouse, Lever, Ashby or Workday listing. You can still save other links manually.",
    "busy": "Another extraction is running. Check its status before starting another.",
    "capacity": "The service is busy. Try again later; nothing retries automatically.",
    "rate_limit": "The suggestion limit has been reached. Try again in an hour.",
    "provider_auth": "The suggestion provider needs to be reconnected by the maintainer.",
    "provider_quota": "The suggestion provider has reached its usage limit. Try again later.",
    "page_expired": "This listing appears to have expired. Open the original link to check.",
    "page_blocked": "The job site blocked access or requires sign-in. Enter the details manually.",
    "page_not_ready": "The listing did not finish loading. You can try again deliberately.",
    "page_unavailable": "The job site could not provide this listing. Check the original link.",
    "too_large": "The listing is too large to read safely. Enter the details manually.",
    "timeout": "This stage exceeded its time limit. Check the result before retrying.",
    "interrupted": "This stage was interrupted. Previously read details are still available.",
    "invalid_summary": "The summary could not be validated. Review the available title and company, or retry the summary.",
    "refused": "A summary could not be prepared. You can still use the available title and company.",
    "failed": "Suggestions could not be prepared. You can still save manually.",
    "expired": "These suggestions expired after 24 hours. Read the listing again to get fresh details.",
}


class SuggestionError(Exception):
    def __init__(self, code="failed", status=400):
        self.code = code if code in MESSAGES else "failed"
        self.status = status
        super().__init__(self.code)
