"""Typed values shared by plugin authors and runtime adapters."""

import ipaddress
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from typing import Any, Literal

Payload = dict[str, Any]
ResultKind = Literal["data", "error", "status", "complete"]


@dataclass(frozen=True)
class ResultEvent:
    """A typed plugin result with the legacy representation at the wire edge."""

    kind: ResultKind
    payload: Payload = field(default_factory=dict)

    @classmethod
    def data(cls, payload: Mapping[str, Any]) -> "ResultEvent":
        return cls("data", dict(payload))

    @classmethod
    def error(cls, message: str) -> "ResultEvent":
        return cls("error", {"message": message})

    @classmethod
    def status(cls, message: str) -> "ResultEvent":
        return cls("status", {"message": message})

    @classmethod
    def complete(cls) -> "ResultEvent":
        return cls("complete")

    def to_wire(self) -> dict[str, Any]:
        return {"type": self.kind, "data": self.payload}


@dataclass(frozen=True)
class EvidenceWrite:
    plugin_name: str
    display_name: str
    category: str
    case_id: int
    content: str
    filename: str


@dataclass(frozen=True)
class IpAddressWrite:
    address: str
    description: str
    sources: Mapping[str, str] | None = None


@dataclass(frozen=True)
class DomainSubdomainsWrite:
    domain: str
    subdomains: list[Payload]


type EntityWrite = IpAddressWrite | DomainSubdomainsWrite


def is_ip_address(value: str) -> bool:
    """Return whether a provider value is a syntactically valid IP address."""
    try:
        ipaddress.ip_address(value)
    except ValueError:
        return False
    return True


def unique_ip_writes(
    candidates: Iterable[tuple[str | None, str, Mapping[str, str] | None]],
) -> list[IpAddressWrite]:
    """Validate and deduplicate provider-specific IP discoveries."""
    writes: dict[str, IpAddressWrite] = {}
    for address, description, sources in candidates:
        if address is None:
            continue
        if not is_ip_address(address):
            continue
        writes.setdefault(address, IpAddressWrite(address, description, sources))
    return list(writes.values())
