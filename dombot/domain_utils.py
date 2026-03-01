from __future__ import annotations

import ipaddress
from urllib.parse import urlsplit

# Common multi-part public suffixes to keep canonicalization deterministic
# without external dependencies.
_MULTI_PART_SUFFIXES = {
    "co.uk",
    "org.uk",
    "gov.uk",
    "ac.uk",
    "com.au",
    "net.au",
    "org.au",
    "co.jp",
    "co.kr",
    "co.in",
    "com.br",
    "com.mx",
    "com.ar",
    "com.sg",
    "com.tr",
    "co.za",
    "com.cn",
    "com.hk",
    "com.tw",
    "k12.ca.us",
}


def _extract_host(raw: str) -> str:
    value = (raw or "").strip().lower()
    if not value:
        return ""

    parsed = urlsplit(value)
    host = parsed.hostname

    if not host:
        parsed = urlsplit(f"//{value}")
        host = parsed.hostname

    if not host:
        host = value.split("/")[0].split("?")[0].split("#")[0]
        if "@" in host:
            host = host.split("@")[-1]
        if ":" in host and host.count(":") == 1:
            host = host.split(":")[0]

    return host.strip(".")


def _is_ip_address(host: str) -> bool:
    try:
        ipaddress.ip_address(host)
        return True
    except ValueError:
        return False


def _registrable_domain(host: str) -> str:
    if not host:
        return ""

    domain = host[4:] if host.startswith("www.") else host
    if domain in {"localhost"} or _is_ip_address(domain):
        return domain

    labels = domain.split(".")
    if len(labels) <= 2:
        return domain

    for suffix in sorted(_MULTI_PART_SUFFIXES, key=lambda s: s.count("."), reverse=True):
        if domain == suffix:
            return domain
        if domain.endswith(f".{suffix}"):
            suffix_labels = suffix.split(".")
            if len(labels) > len(suffix_labels):
                return ".".join(labels[-(len(suffix_labels) + 1):])

    return ".".join(labels[-2:])


def canonicalize_domain(domain_or_url: str) -> str:
    """Canonicalize a domain or URL to a root hostname (e.g. www.walmart.com -> walmart.com)."""
    host = _extract_host(domain_or_url)
    if not host:
        return ""
    return _registrable_domain(host)
