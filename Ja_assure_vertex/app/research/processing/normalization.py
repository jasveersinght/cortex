"""URL and content normalization.

All functions are pure and deterministic — no network calls, no AI.
"""

from __future__ import annotations

import hashlib
import re
import unicodedata
from urllib.parse import urlparse, urlencode, parse_qs, urlunparse


# Tracking parameters to strip from URLs
TRACKING_PARAMS = {
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
    "gclid", "fbclid", "mc_cid", "mc_eid", "ref", "source",
}

# Known HTTPS domains — we canonicalize http→https for these
KNOWN_HTTPS_DOMAINS = {
    "google.com", "facebook.com", "twitter.com", "linkedin.com",
    "youtube.com", "github.com", "reddit.com", "medium.com",
    "bloomberg.com", "reuters.com", "cnbc.com", "bbc.com",
    "straitstimes.com", "channelnewsasia.com", "nikkei.com",
    "example.com",
}

# Boilerplate patterns to strip from content
BOILERPLATE_PATTERNS = [
    r"(?i)cookie\s*(policy|notice|consent|settings|preferences).*?\.?",
    r"(?i)share this (article|story|post).*?\.?",
    r"(?i)subscribe to our newsletter.*?\.?",
    r"(?i)sign up for.*?newsletter.*?\.?",
    r"(?i)follow us on.*?\.?",
    r"(?i)related (articles|stories|posts).*?$",
    r"(?i)advertisement\s*$",
    r"(?i)sponsored content\s*$",
    r"(?i)read more:.*?$",
]


def normalize_url(url: str) -> str:
    """Normalize a URL for hashing and dedup.

    Rules (per §12.1):
    1. Lowercase scheme and host
    2. Force https for known-https domains
    3. Strip default ports (:80, :443)
    4. Strip tracking params
    5. Sort remaining query params
    6. Strip trailing slash (except root)
    7. Strip fragment
    8. Strip www. prefix for hashing
    """
    if not url:
        return ""

    parsed = urlparse(url)

    # 1. Lowercase scheme and host
    scheme = parsed.scheme.lower()
    host = parsed.hostname or ""
    host = host.lower()

    # 8. Strip www. prefix
    if host.startswith("www."):
        host = host[4:]

    # 2. Force https for known domains
    if scheme == "http":
        for domain in KNOWN_HTTPS_DOMAINS:
            if host == domain or host.endswith("." + domain):
                scheme = "https"
                break

    # 3. Strip default ports
    port = parsed.port
    if port in (80, 443, None):
        netloc = host
    else:
        netloc = f"{host}:{port}"

    # 4. Strip tracking params, 5. Sort remaining
    query_params = parse_qs(parsed.query, keep_blank_values=True)
    filtered_params = {
        k: v for k, v in sorted(query_params.items())
        if k.lower() not in TRACKING_PARAMS
    }
    query_string = urlencode(filtered_params, doseq=True)

    # 6. Strip trailing slash (except root path)
    path = parsed.path
    if path != "/" and path.endswith("/"):
        path = path.rstrip("/")

    # 7. Strip fragment
    result = urlunparse((scheme, netloc, path, "", query_string, ""))
    return result


def get_display_url(url: str) -> str:
    """Return the original URL cleaned up for display (preserves www.)."""
    if not url:
        return ""
    parsed = urlparse(url)
    scheme = parsed.scheme.lower() or "https"
    host = parsed.hostname or ""
    port = parsed.port
    if port in (80, 443, None):
        netloc = host
    else:
        netloc = f"{host}:{port}"
    path = parsed.path
    if path != "/" and path.endswith("/"):
        path = path.rstrip("/")
    return urlunparse((scheme, netloc, path, "", parsed.query, ""))


def normalize_content(content: str, max_length: int = 8000) -> tuple[str, bool]:
    """Normalize content for storage and hashing.

    Returns (normalized_content, was_truncated).

    Rules (per §12.2):
    1. Strip HTML tags
    2. Collapse whitespace, normalize newlines
    3. Strip boilerplate
    4. Unicode NFKC normalization
    5. Trim to max stored length
    """
    if not content:
        return "", False

    # 1. Strip HTML tags
    text = re.sub(r"<[^>]+>", " ", content)

    # 2. Collapse whitespace, normalize newlines
    text = re.sub(r"\r\n", "\n", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = text.strip()

    # 3. Strip boilerplate
    for pattern in BOILERPLATE_PATTERNS:
        text = re.sub(pattern, "", text, flags=re.MULTILINE)

    # 4. Unicode NFKC
    text = unicodedata.normalize("NFKC", text)

    text = text.strip()

    # 5. Trim to max
    truncated = len(text) > max_length
    if truncated:
        text = text[:max_length]

    return text, truncated


def hash_url(normalized_url: str) -> str:
    """SHA-256 hex digest of the normalized URL."""
    return hashlib.sha256(normalized_url.encode("utf-8")).hexdigest()


def hash_content(normalized_content: str) -> str:
    """SHA-256 hex digest of the first 4000 chars of normalized content.

    Bounded prefix so trivial tail differences don't defeat dedup (§12.3).
    """
    prefix = normalized_content[:4000]
    return hashlib.sha256(prefix.encode("utf-8")).hexdigest()


def extract_domain(url: str) -> str:
    """Extract the registrable domain from a URL."""
    try:
        host = urlparse(url).hostname or ""
        host = host.lower()
        if host.startswith("www."):
            host = host[4:]
        return host
    except Exception:
        return ""
