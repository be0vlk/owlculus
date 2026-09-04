"""Cross-case correlation query for persisted entities."""

from dataclasses import dataclass
from enum import StrEnum
from urllib.parse import urlsplit

from sqlmodel import Session, select

from app.core.exceptions import AuthorizationException
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
    entity: Entity
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
        candidates = self.db.exec(
            select(Entity, Case).join(Case).where(Entity.case_id != source_case.id)
        ).all()

        readable_cases: dict[int, bool] = {}
        matches: list[CorrelationMatch] = []
        for source in sources:
            source_name = entity_display_name(source.entity_type, source.data)
            for candidate, other_case in candidates:
                other_case_id = other_case.id
                if other_case_id is None:
                    continue
                if other_case_id not in readable_cases:
                    try:
                        self.case_access.readable(user, other_case_id)
                    except AuthorizationException:
                        readable_cases[other_case_id] = False
                    else:
                        readable_cases[other_case_id] = True
                if not readable_cases[other_case_id]:
                    continue
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
                candidate_domains = _domains(candidate)
                source_domains = (
                    set() if source.entity_type == "domain" else _domains(source)
                )
                for domain in sorted(source_domains):
                    if domain in candidate_domains:
                        matches.append(
                            CorrelationMatch(
                                CorrelationKind.DOMAIN,
                                domain,
                                source,
                                candidate,
                                other_case,
                                _domain_location(candidate, domain),
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


def _domains(entity: Entity) -> set[str]:
    if entity.entity_type == "domain":
        value = str(entity.data.get("domain") or "").casefold()
        return {value} if value else set()
    if entity.entity_type == "person":
        values = [entity.data.get("email"), *(entity.data.get("usernames") or [])]
    elif entity.entity_type == "company":
        values = [entity.data.get("website")]
    else:
        values = []
    return {domain for value in values if (domain := _domain(value))}


def _domain_location(entity: Entity, domain: str) -> str:
    if entity.entity_type == "domain":
        return "domain field"
    if entity.entity_type == "company":
        return f"website: {entity.data.get('website', '')}"
    locations = []
    email = entity.data.get("email")
    if _domain(email) == domain:
        locations.append(f"email: {email}")
    locations.extend(
        f"username: {username}"
        for username in entity.data.get("usernames") or []
        if _domain(username) == domain
    )
    return ", ".join(locations)


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
