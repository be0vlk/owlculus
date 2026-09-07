"""Canonical identity for supported, unscoped IP address literals."""

from ipaddress import ip_address


def canonical_ip_address(value: str) -> str:
    """Parse a complete literal without conflating address families or scopes."""
    text = value.strip()
    if "%" in text:
        raise ValueError("Please enter a valid IPv4 or IPv6 address without a scope")
    try:
        return str(ip_address(text))
    except ValueError as error:
        raise ValueError("Please enter a valid IPv4 or IPv6 address") from error
