from urllib.parse import urlsplit


def safe_local_path(value: str, fallback: str = "/app/dashboard") -> str:
    """Return a same-origin absolute path or a known local fallback."""
    candidate = str(value or "").strip()
    lowered = candidate.lower()
    if (
        not candidate.startswith("/")
        or candidate.startswith("//")
        or "\\" in candidate
        or "%2f" in lowered
        or "%5c" in lowered
        or any(ord(char) < 32 for char in candidate)
    ):
        return fallback
    parsed = urlsplit(candidate)
    if parsed.scheme or parsed.netloc:
        return fallback
    return candidate
