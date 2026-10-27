"""Deliberately narrow first release: public listing routes on evaluated platforms."""
import re
from urllib.parse import parse_qsl, urlsplit

ERROR_MESSAGES = {
    "unsupported_target": "Capture supports public Gem, Greenhouse, Lever, Ashby and Workday listing links. This link is not supported yet; you can still save and open it.",
    "page_expired": "This listing appears to have expired. Open the original link to check.",
    "page_blocked": "The job site blocked capture or requires sign-in. Open the original link to view it.",
    "page_not_ready": "The listing did not finish loading. Open the original link and try capture again later.",
    "page_unavailable": "The job site could not provide this listing. Open the original link to check.",
    "capture_capacity": "Both capture slots are in use. Try again after another capture finishes.",
    "provider_busy": "The screenshot service is busy or rate-limited. Try again later.",
    "provider_quota": "The screenshot service has reached its usage limit. Try again after the allowance resets.",
    "provider_auth": "The screenshot service needs to be reconnected by the maintainer.",
    "provider_access": "The screenshot service refused access. The maintainer can check its credentials and usage allowance.",
    "capture_timeout": "Capture exceeded its time limit. You can try again deliberately; it will not retry automatically.",
    "image_too_large": "This page is too large to capture safely. Open the original listing instead.",
    "capture_failed": "Capture failed. You can try again later.",
    "interrupted": "Capture was interrupted. You can try again.",
}


class CaptureError(Exception):
    def __init__(self, code="capture_failed"):
        self.code = code if code in ERROR_MESSAGES else "capture_failed"
        super().__init__(self.code)


def target_profile(url):
    from project.services.jobwizard_service import safe_listing_url
    if not safe_listing_url(url):
        return None
    parsed = urlsplit(url)
    if parsed.scheme != "https" or parsed.port not in (None, 443) or parsed.fragment:
        return None
    host, path = parsed.hostname, parsed.path
    greenhouse = (re.fullmatch(r"/[^/]+/jobs/([0-9]+)/?", path)
                  if host in {"boards.greenhouse.io", "job-boards.greenhouse.io", "job-boards.eu.greenhouse.io"}
                  else None)
    # Gem uses src for public job-board attribution. Do not broaden other hosts
    # or forward arbitrary query credentials/private invitation links.
    allowed_query = {"gh_src", "source", "lever-source"}
    if host == "jobs.gem.com":
        allowed_query.add("src")
    query = parse_qsl(parsed.query, keep_blank_values=True)
    # Greenhouse share links repeat the public path's job ID. Do not let a
    # mismatched ID select a different job or permit this parameter elsewhere.
    if greenhouse:
        allowed_query.add("gh_jid")
        if any(key == "gh_jid" and value != greenhouse.group(1) for key, value in query):
            return None
    if any(key not in allowed_query and not key.startswith("utm_") for key, _ in query):
        return None
    if host == "jobs.gem.com" and re.fullmatch(r"/[a-zA-Z0-9][a-zA-Z0-9_-]{0,99}/am9icG9zdD[a-zA-Z0-9_-]{22}/?", path):
        return "gem"
    if greenhouse:
        return "greenhouse"
    if host in {"jobs.lever.co", "jobs.eu.lever.co"} and re.fullmatch(r"/[^/]+/[a-fA-F0-9-]{36}/?", path):
        return "lever"
    if host == "jobs.ashbyhq.com" and re.fullmatch(r"/[^/]+/[a-fA-F0-9-]{36}/?", path):
        return "ashby"
    if re.fullmatch(r"[a-z0-9-]+\.wd[0-9]+\.myworkdayjobs\.com", host) and "/job/" in path:
        return "workday"
    return None
