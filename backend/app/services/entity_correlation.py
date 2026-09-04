"""Cross-case correlation query for persisted entities."""

from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from typing import Any
from urllib.parse import urlsplit

from sqlmodel import Session, col, select

from app.database.models import Case, Entity, User
from app.schemas.entity_schema import entity_display_name
from app.services.case_access import CaseAccess


class CorrelationKind(StrEnum):
    """Supported reasons why entities correlate across cases."""

    NAME = "name"
    EMPLOYER = "employer"
    DOMAIN = "domain"
    VIN = "vin"
    LICENSE_PLATE = "license_plate"


@dataclass(frozen=True)
class CorrelationMatch:
    """One source entity matched to an entity in another readable case."""

    kind: CorrelationKind
    value: str
    source_entity: Entity
    other_entity: Entity
    other_case: Case
    found_in: str | None = None


class EntityCorrelation:
    """Answer cross-case entity-correlation questions."""

    def __init__(self, db: Session):
        self.db = db
        self.case_access = CaseAccess(db)

    def correlate(self, case: Case, user: User) -> list[CorrelationMatch]:
        """Return correlations between one readable case and other readable cases."""
        if case.id is None:
            return []
        source_case = self.case_access.readable(user, case.id)
        sources = self.db.exec(
            select(Entity).where(Entity.case_id == source_case.id)
        ).all()
        readable_case_ids = self.case_access.readable_case_ids(user)
        candidates = self.db.exec(
            select(Entity, Case)
            .join(Case)
            .where(
                Entity.case_id != source_case.id,
                col(Entity.case_id).in_(readable_case_ids),
            )
        ).all()

        matches: list[CorrelationMatch] = []
        for source in sources:
            source_name = entity_display_name(source.entity_type, source.data)
            if not source_name:
                continue
            for candidate, other_case in candidates:
                other_name = entity_display_name(candidate.entity_type, candidate.data)
                if (
                    source.entity_type != "vehicle"
                    and candidate.entity_type == source.entity_type
                    and source_name
                    and other_name.casefold() == source_name.casefold()
                ):
                    matches.append(
                        CorrelationMatch(
                            CorrelationKind.NAME,
                            source_name,
                            source,
                            candidate,
                            other_case,
                        )
                    )
                employer = str(source.data.get("employer") or "")
                if (
                    source.entity_type == "person"
                    and candidate.entity_type == "person"
                    and employer
                    and str(candidate.data.get("employer") or "").casefold()
                    == employer.casefold()
                ):
                    matches.append(
                        CorrelationMatch(
                            CorrelationKind.EMPLOYER,
                            employer,
                            source,
                            candidate,
                            other_case,
                        )
                    )
                candidate_domains = {
                    reference.value: reference
                    for reference in _domain_references(candidate)
                }
                source_domains = (
                    [] if source.entity_type == "domain" else _domain_references(source)
                )
                for reference in source_domains:
                    candidate_reference = candidate_domains.get(reference.value)
                    if candidate_reference:
                        matches.append(
                            CorrelationMatch(
                                CorrelationKind.DOMAIN,
                                reference.value,
                                source,
                                candidate,
                                other_case,
                                candidate_reference.location,
                            )
                        )
                if source.entity_type == candidate.entity_type == "vehicle":
                    source_identifiers = _vehicle_identifiers(source)
                    candidate_identifiers = _vehicle_identifiers(candidate)
                    for kind in (
                        CorrelationKind.VIN,
                        CorrelationKind.LICENSE_PLATE,
                    ):
                        normalized = source_identifiers.get(kind)
                        if normalized and normalized == candidate_identifiers.get(kind):
                            value = str(source.data.get(kind.value) or normalized)
                            matches.append(
                                CorrelationMatch(
                                    kind,
                                    value.upper(),
                                    source,
                                    candidate,
                                    other_case,
                                )
                            )
        return matches


def _domain(value: object) -> str | None:
    text = str(value or "").strip()
    if "@" in text:
        return text.rsplit("@", 1)[-1].casefold() or None
    if text.startswith(("http://", "https://")):
        hostname = urlsplit(text).hostname
        return hostname.casefold() if hostname else None
    return None


@dataclass(frozen=True)
class _DomainReference:
    value: str
    location: str


def _domain_entity_references(data: dict[str, Any]) -> list[_DomainReference]:
    value = str(data.get("domain") or "").casefold()
    return [_DomainReference(value, "domain field")] if value else []


def _person_domain_references(data: dict[str, Any]) -> list[_DomainReference]:
    references: dict[str, list[str]] = {}
    values = [("email", data.get("email"))]
    values.extend(("username", username) for username in data.get("usernames") or [])
    for field, raw_value in values:
        if domain := _domain(raw_value):
            references.setdefault(domain, []).append(f"{field}: {raw_value}")
    return [
        _DomainReference(domain, ", ".join(locations))
        for domain, locations in references.items()
    ]


def _company_domain_references(data: dict[str, Any]) -> list[_DomainReference]:
    website = data.get("website")
    domain = _domain(website)
    return [_DomainReference(domain, f"website: {website}")] if domain else []


_DOMAIN_REFERENCES_BY_ENTITY_TYPE: dict[
    str, Callable[[dict[str, Any]], list[_DomainReference]]
] = {
    "domain": _domain_entity_references,
    "person": _person_domain_references,
    "company": _company_domain_references,
}


def _domain_references(entity: Entity) -> list[_DomainReference]:
    extractor = _DOMAIN_REFERENCES_BY_ENTITY_TYPE.get(entity.entity_type)
    return extractor(entity.data) if extractor else []


def _vehicle_identifiers(entity: Entity) -> dict[CorrelationKind, str]:
    values: dict[CorrelationKind, str] = {}
    vin = str(entity.data.get("vin") or "").strip().upper()
    if vin:
        values[CorrelationKind.VIN] = vin
    plate = str(entity.data.get("license_plate") or "")
    normalized_plate = plate.replace(" ", "").replace("-", "").upper()
    if normalized_plate:
        values[CorrelationKind.LICENSE_PLATE] = normalized_plate
    return values
