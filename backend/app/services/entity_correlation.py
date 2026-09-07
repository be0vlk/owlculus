"""Cross-case correlation query with field-aware, explainable connections."""

import re
from dataclasses import dataclass
from enum import StrEnum
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
class MatchField:
    field: str
    value: str


@dataclass(frozen=True)
class CorrelationMatch:
    """One source entity matched to an entity in another readable case."""

    kind: CorrelationKind
    value: str
    source_entity: Entity
    other_entity: Entity
    other_case: Case
    normalized_value: str
    source_fields: tuple[MatchField, ...]
    other_fields: tuple[MatchField, ...]
    signal: str

    @property
    def found_in(self) -> str:
        return ", ".join(f"{item.field}: {item.value}" for item in self.other_fields)


@dataclass(frozen=True)
class SkippedReference:
    case_id: int
    entity_id: int | None
    field: str


References = dict[tuple[CorrelationKind, str], tuple[MatchField, ...]]


class EntityCorrelation:
    """Answer cross-case entity-correlation questions."""

    def __init__(self, db: Session):
        self.db = db
        self.case_access = CaseAccess(db)
        self.skipped_references: list[SkippedReference] = []

    def correlate(self, case: Case, user: User) -> list[CorrelationMatch]:
        """Return matches; record individually skipped references with Case scope."""
        self.skipped_references = []
        if case.id is None:
            return []
        source_case = self.case_access.readable(user, case.id)
        sources = self.db.exec(
            select(Entity)
            .where(Entity.case_id == source_case.id)
            .order_by(col(Entity.id))
        ).all()
        readable_case_ids = self.case_access.readable_case_ids(user)
        candidates = self.db.exec(
            select(Entity, Case)
            .join(Case)
            .where(
                Entity.case_id != source_case.id,
                col(Entity.case_id).in_(readable_case_ids),
            )
            .order_by(col(Entity.case_id), col(Entity.id))
        ).all()
        references = {
            entity.id: _references(entity, self.skipped_references)
            for entity in [*sources, *(entity for entity, _ in candidates)]
        }
        matches = []
        for source in sources:
            for candidate, other_case in candidates:
                for (kind, normalized), fields in references[source.id].items():
                    other_fields = references[candidate.id].get((kind, normalized))
                    if not other_fields:
                        continue
                    if (
                        kind is CorrelationKind.NAME
                        and source.entity_type != candidate.entity_type
                    ):
                        continue
                    if (
                        kind is CorrelationKind.DOMAIN
                        and source.entity_type == candidate.entity_type == "domain"
                    ):
                        continue  # Identical Domain Entities already have a name reason.
                    qualification = _match_qualification(kind, source, candidate)
                    if qualification is None:
                        continue
                    value = (
                        normalized
                        if kind is CorrelationKind.DOMAIN
                        else fields[0].value
                    )
                    if kind is CorrelationKind.NAME:
                        value = entity_display_name(source.entity_type, source.data)
                    if kind in {CorrelationKind.VIN, CorrelationKind.LICENSE_PLATE}:
                        value = value.upper()
                    matches.append(
                        CorrelationMatch(
                            kind,
                            value,
                            source,
                            candidate,
                            other_case,
                            normalized,
                            fields,
                            other_fields,
                            qualification,
                        )
                    )
        return matches


def correlation_label(entity: Entity) -> str:
    return (
        entity_display_name(entity.entity_type, entity.data).strip()
        or f"{entity.entity_type.replace('_', ' ').title()} #{entity.id}"
    )


def _hostname(value: str) -> str:
    host = value.strip().removesuffix(".").casefold()
    # Reject malformed references locally without DNS or ownership inference.
    labels = host.split(".")
    if (
        not host
        or len(host) > 253
        or any(
            not re.fullmatch(r"[^\W_](?:[\w-]{0,61}[^\W_])?", label) for label in labels
        )
    ):
        raise ValueError("Invalid hostname")
    return host


def _domain(value: str, *, bare: bool = False) -> str | None:
    text = value.strip()
    if text.lower().startswith(("http://", "https://")):
        parsed = urlsplit(text)
        # Accessing port also validates malformed port syntax.
        _ = parsed.port
        return _hostname(parsed.hostname or "")
    if "@" in text:
        local, host = text.rsplit("@", 1)
        if not local or any(char.isspace() for char in local) or "@" in local:
            raise ValueError("Invalid email reference")
        return _hostname(host)
    return _hostname(text) if bare else None


_NAME_FIELDS = {
    "person": ("first_name", "last_name"),
    "company": ("name",),
    "domain": ("domain",),
    "ip_address": ("ip_address",),
}


def _references(entity: Entity, skipped: list[SkippedReference]) -> References:
    reasons: References = {}

    def add(kind: CorrelationKind, normalized: str, fields: tuple[MatchField, ...]):
        if normalized:
            existing = reasons.get((kind, normalized), ())
            reasons[kind, normalized] = tuple(dict.fromkeys((*existing, *fields)))

    name_fields = tuple(
        MatchField(field, str(entity.data[field]))
        for field in _NAME_FIELDS.get(entity.entity_type, ())
        if str(entity.data.get(field) or "").strip()
    )
    if entity.entity_type == "network_assets":
        # Older persisted Entities still use the first domain/subdomain as a name.
        for field in ("domains", "subdomains"):
            if assets := entity.data.get(field):
                name_fields = (MatchField(f"{field}[0]", str(assets[0])),)
                break
    name = " ".join(field.value.strip() for field in name_fields).casefold()
    if entity.entity_type != "domain":
        add(CorrelationKind.NAME, name, name_fields)
    if entity.entity_type == "person":
        employer = str(entity.data.get("employer") or "")
        add(
            CorrelationKind.EMPLOYER,
            employer.strip().casefold(),
            (MatchField("employer", employer),),
        )
    values: list[tuple[str, str, bool]] = []
    if entity.entity_type == "domain":
        values = [("domain", str(entity.data.get("domain") or ""), True)]
    elif entity.entity_type == "company":
        values = [("website", str(entity.data.get("website") or ""), True)]
    elif entity.entity_type == "person":
        values = [("email", str(entity.data.get("email") or ""), False)]
        values.extend(
            (f"usernames[{index}]", str(value), False)
            for index, value in enumerate(entity.data.get("usernames") or [])
        )
    for field, raw, bare in values:
        if not raw.strip():
            continue
        try:
            domain = _domain(raw, bare=bare)
        except ValueError:
            skipped.append(SkippedReference(entity.case_id, entity.id, field))
            continue
        if domain:
            fields = (MatchField(field, raw),)
            add(CorrelationKind.DOMAIN, domain, fields)
            if entity.entity_type == "domain":
                add(CorrelationKind.NAME, domain, fields)
    if entity.entity_type == "vehicle":
        for kind in (CorrelationKind.VIN, CorrelationKind.LICENSE_PLATE):
            raw = str(entity.data.get(kind.value) or "")
            normalized = raw.strip().upper()
            if kind is CorrelationKind.LICENSE_PLATE:
                normalized = normalized.replace(" ", "").replace("-", "")
            vehicle_fields: tuple[MatchField, ...] = (MatchField(kind.value, raw),)
            if kind is CorrelationKind.LICENSE_PLATE:
                vehicle_fields += tuple(
                    MatchField(field, str(entity.data[field]))
                    for field in ("registration_state", "vin")
                    if str(entity.data.get(field) or "").strip()
                )
            add(kind, normalized, vehicle_fields)
    return reasons


def _match_qualification(
    kind: CorrelationKind, source: Entity, other: Entity
) -> str | None:
    """Explain the connection, or return None when identifiers exclude it."""
    if kind is CorrelationKind.LICENSE_PLATE:
        states = [
            str(entity.data.get("registration_state") or "").strip().casefold()
            for entity in (source, other)
        ]
        if all(states) and states[0] != states[1]:
            return None
        label = "License plate association"
        if not all(states):
            label = "Tentative license plate association: registration state unknown"
        vins = [
            str(entity.data.get("vin") or "").strip().upper()
            for entity in (source, other)
        ]
        if all(vins) and vins[0] != vins[1]:
            label += "; conflicting VINs; vehicle identity is not established"
        else:
            label += "; a shared plate does not establish vehicle identity"
        return label
    return {
        CorrelationKind.NAME: "Shared name association",
        CorrelationKind.EMPLOYER: "Shared employer association",
        CorrelationKind.DOMAIN: "Shared domain association",
        CorrelationKind.VIN: "Exact VIN match",
    }[kind]
