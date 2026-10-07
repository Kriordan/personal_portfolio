from copy import deepcopy

from project.wishlist_storage import image_origins

csp = {
    "default-src": ["'self'"],
    "style-src": ["'self'", "https://fonts.googleapis.com", "'unsafe-inline'"],
    "script-src": [
        "'self'",
        "https://www.googletagmanager.com",
        "https://*.hotjar.com",
        "https://cdn.jsdelivr.net",  # AlpineJS CDN
        "https://cdn.socket.io",  # Socket.IO client
        "https://challenges.cloudflare.com",  # Turnstile
        "'unsafe-inline'",
    ],
    "img-src": [
        "'self'",
        "https://i.ytimg.com",
    ],
    "font-src": ["'self'", "https://fonts.gstatic.com"],
    "connect-src": [
        "'self'",
        "https://*.google-analytics.com",
        "https://stats.g.doubleclick.net",
        "https://*.hotjar.com",
        "https://*.hotjar.io",
        "wss://*.hotjar.com",
        "ws:",
        "wss:",
    ],
    "frame-src": [
        "'self'",
        "https://www.youtube.com",
        "https://www.youtube-nocookie.com",
        "https://challenges.cloudflare.com",  # Turnstile
    ],
    "media-src": [
        "'self'",
        "https://www.youtube.com",
        "https://www.youtube-nocookie.com",
    ],
}


def build_csp():
    # Resolve storage configuration after dotenv loads, once per application.
    policy = deepcopy(csp)
    policy["img-src"].extend(image_origins())
    return policy
