"""Offline hostname identity and HTTP website parsing shared by Entity consumers."""

import re
from urllib.parse import urlsplit, urlunsplit

import idna


def canonical_hostname(value: str) -> str:
    """Validate DNS labels and equate Unicode/ASCII spellings without DNS inference."""
    try:
        host = idna.encode(value.strip(), uts46=True).decode("ascii").lower()
    except idna.IDNAError as exc:
        raise ValueError("Invalid hostname") from exc
    host = host.removesuffix(".")
    if not host or len(host) > 253:
        raise ValueError("Invalid hostname")
    return host


def normalize_website(value: str) -> str:
    """Preserve URL components while normalizing the scheme and validated host."""
    text = value.strip()
    if any(char.isspace() or char == "\\" for char in text):
        raise ValueError("Invalid website")
    if not text.lower().startswith(("http://", "https://")):
        # A numeric port on a bare host is not a URI scheme.
        authority = re.split(r"[/\?#]", text, maxsplit=1)[0]
        if ":" in authority and not re.fullmatch(r"[^:]+:[0-9]+", authority):
            raise ValueError("Website must use HTTP or HTTPS")
        if text.startswith("//"):
            raise ValueError("Website must use HTTP or HTTPS")
        text = "https://" + text
    parsed = urlsplit(text)
    host = canonical_hostname(parsed.hostname or "")
    if host in {"http", "https"} and parsed.path.startswith("//"):
        raise ValueError("Ambiguous historical website")
    _ = parsed.port  # Validate port syntax/range before preserving its spelling.
    userinfo, separator, authority = parsed.netloc.rpartition("@")
    port = ":" + authority.rsplit(":", 1)[1] if ":" in authority else ""
    credentials = userinfo + separator
    if port == ":":
        raise ValueError("Invalid website port")
    return urlunsplit(
        (
            parsed.scheme.lower(),
            credentials + host + port,
            parsed.path,
            parsed.query,
            parsed.fragment,
        )
    )


def website_hostname(value: str) -> str:
    """Read supported historical websites using the same rules as new writes."""
    return urlsplit(normalize_website(value)).hostname or ""
