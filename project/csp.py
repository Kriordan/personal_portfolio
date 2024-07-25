import os

csp = {
    "default-src": ["'self'"],
    "style-src": ["'self'", "https://fonts.googleapis.com", "'unsafe-inline'"],
    "script-src": [
        "'self'",
        "https://www.googletagmanager.com",
        "https://*.hotjar.com",
        "https://cdn.jsdelivr.net",  # Add this line for AlpineJS CDN
        "'unsafe-inline'",
    ],
    "img-src": [
        "'self'",
        f'https://{os.getenv("WISHLIST_S3_BUCKET")}.s3.amazonaws.com',
    ],
    "font-src": ["'self'", "https://fonts.gstatic.com"],
    "connect-src": [
        "'self'",
        "https://*.google-analytics.com",
        "https://stats.g.doubleclick.net",
        "https://*.hotjar.com",
        "https://*.hotjar.io",
        "wss://*.hotjar.com",
    ],
}
