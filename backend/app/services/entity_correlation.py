"""Cross-case correlation query with field-aware, explainable connections."""

from __future__ import annotations

import re
from collections.abc import Iterator
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
    EMAIL = "email"
    PHONE = "phone"
    VIN = "vin"
    LICENSE_PLATE = "license_plate"


EXACT_IDENTIFIER_KINDS = frozenset(
    {CorrelationKind.EMAIL, CorrelationKind.PHONE, CorrelationKind.VIN}
)


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
    def signal_rank(self) -> int:
        if self.kind in EXACT_IDENTIFIER_KINDS:
            return 0
        return 2 if self.signal.startswith("Low signal") else 1

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
        """Compatibility query for callers that need a materialized result."""
        return [
            item
            for item in self.iter_correlations(case, user)
            if isinstance(item, CorrelationMatch)
        ]

    def iter_correlations(
        self, case: Case, user: User
    ) -> Iterator[CorrelationMatch | ScanProgress]:
        """Index references once, then stream ranked matches without retaining pairs.

        Only candidate references sought by sources stay in memory. Keyset pages
        bound database fetches; progress between pages/pair batches lets the async
        adapter cooperate with cancellation, including scans without any matches.
        """
        self.skipped_references = []
        if case.id is None:
            return
        source_case = self.case_access.readable(user, case.id)
        source_references: list[tuple[Entity, References]] = []
        wanted: set[tuple[CorrelationKind, str, str]] = set()
        cursor = 0
        while True:
            sources = self.db.exec(
                select(Entity)
                .where(Entity.case_id == source_case.id, col(Entity.id) > cursor)
                .order_by(col(Entity.id))
                .limit(256)
            ).all()
            if not sources:
                break
            for source in sources:
                refs = _references(source, self.skipped_references)
                source_references.append((_entity_snapshot(source), refs))
                wanted.update(_index_key(source, key) for key in refs)
            cursor = sources[-1].id or cursor
            yield ScanProgress("Indexed source Entities", len(sources), (case.id,))
        readable_case_ids = self.case_access.readable_case_ids(user)
        index: dict[
            tuple[CorrelationKind, str, str],
            list[tuple[Entity, Case, tuple[MatchField, ...]]],
        ] = {}
        cursor = 0
        while True:
            candidates = self.db.exec(
                select(Entity, Case)
                .join(Case)
                .where(
                    Entity.case_id != source_case.id,
                    col(Entity.case_id).in_(readable_case_ids),
                    col(Entity.id) > cursor,
                )
                .order_by(col(Entity.id))
                .limit(256)
            ).all()
            if not candidates:
                break
            for candidate, other_case in candidates:
                refs = _references(candidate, self.skipped_references)
                snapshot = _entity_snapshot(candidate)
                case_snapshot = Case(
                    id=other_case.id,
                    title=other_case.title,
                    case_number=other_case.case_number,
                )
                for key, fields in refs.items():
                    lookup = _index_key(candidate, key)
                    if lookup in wanted:
                        index.setdefault(lookup, []).append(
                            (snapshot, case_snapshot, fields)
                        )
            cursor = candidates[-1][0].id or cursor
            yield ScanProgress(
                "Indexed candidate Entities",
                len(candidates),
                tuple(
                    sorted(
                        {case.id, *(candidate.case_id for candidate, _ in candidates)}
                    )
                ),
            )
        for entries in index.values():
            entries.sort(key=lambda entry: (entry[1].id or 0, entry[0].id or 0))
        # Three fixed signal tiers keep exact identifiers first and provider-only
        # overlap last. A group may recur in a later tier with the same identity.
        examined = 0
        scope = {case.id}
        for rank in (0, 1, 2):
            for source, refs in source_references:
                for (kind, normalized), fields in sorted(refs.items()):
                    exact = kind in EXACT_IDENTIFIER_KINDS
                    if (rank == 0) != exact or (
                        rank == 2 and kind is not CorrelationKind.DOMAIN
                    ):
                        continue
                    for candidate, other_case, other_fields in index.get(
                        _index_key(source, (kind, normalized)), ()
                    ):
                        examined += 1
                        scope.add(candidate.case_id)
                        if examined == 256:
                            yield ScanProgress(
                                "Compared indexed connections",
                                examined,
                                tuple(sorted(scope)),
                            )
                            examined, scope = 0, {case.id}
                        if (
                            kind is CorrelationKind.DOMAIN
                            and source.entity_type == candidate.entity_type == "domain"
                        ):
                            continue
                        qualification = _match_qualification(kind, source, candidate)
                        if qualification is None:
                            continue
                        if _low_signal_provider(
                            kind, normalized, source, candidate, fields, other_fields
                        ):
                            qualification = "Low signal: different email addresses share a common email provider; this does not establish identity"
                        value = (
                            normalized
                            if kind is CorrelationKind.DOMAIN
                            else fields[0].value
                        )
                        if kind is CorrelationKind.NAME:
                            value = entity_display_name(source.entity_type, source.data)
                        if kind in {CorrelationKind.VIN, CorrelationKind.LICENSE_PLATE}:
                            value = value.upper()
                        match = CorrelationMatch(
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
                        if match.signal_rank == rank:
                            yield match


@dataclass(frozen=True)
class ScanProgress:
    message: str
    count: int
    case_scope: tuple[int, ...]


def _entity_snapshot(entity: Entity) -> Entity:
    # Worker event boundaries roll back their read transaction. Detached values
    # prevent ORM expiry from turning indexed lookup into per-match SQL queries.
    return Entity(
        id=entity.id,
        case_id=entity.case_id,
        entity_type=entity.entity_type,
        data=entity.data,
    )


def _index_key(
    entity: Entity, key: tuple[CorrelationKind, str]
) -> tuple[CorrelationKind, str, str]:
    kind, value = key
    return kind, value, entity.entity_type if kind is CorrelationKind.NAME else ""


def _low_signal_provider(
    kind: CorrelationKind,
    normalized: str,
    source: Entity,
    other: Entity,
    fields: tuple[MatchField, ...],
    other_fields: tuple[MatchField, ...],
) -> bool:
    if (
        kind is not CorrelationKind.DOMAIN
        or normalized not in COMMON_EMAIL_PROVIDERS
        or source.entity_type != "person"
        or other.entity_type != "person"
    ):
        return False
    source_local = next(
        (
            field.value.strip().rsplit("@", 1)[0].strip()
            for field in fields
            if field.field == "email"
        ),
        None,
    )
    other_local = next(
        (
            field.value.strip().rsplit("@", 1)[0].strip()
            for field in other_fields
            if field.field == "email"
        ),
        None,
    )
    return (
        source_local is not None
        and other_local is not None
        and source_local != other_local
    )


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


def _email(value: str) -> str:
    """Conservative unquoted mailbox syntax, including older persisted references."""
    text = value.strip()
    if "@" not in text:
        raise ValueError("Invalid email reference")
    local, host = text.rsplit("@", 1)
    local = local.strip()
    if (
        not local
        or text.lower().startswith(("http://", "https://"))
        or any(char.isspace() or char in '@:<>(),;\\[]"' for char in local)
    ):
        raise ValueError("Invalid email reference")
    return f"{local}@{_hostname(host)}"


COMMON_EMAIL_PROVIDERS = frozenset(
    {
        "gmail.com",
        "googlemail.com",
        "outlook.com",
        "hotmail.com",
        "live.com",
        "yahoo.com",
        "icloud.com",
        "aol.com",
        "proton.me",
        "protonmail.com",
    }
)


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
            email = _email(raw) if field == "email" else None
            domain = email.rsplit("@", 1)[1] if email else _domain(raw, bare=bare)
        except ValueError:
            skipped.append(SkippedReference(entity.case_id, entity.id, field))
            continue
        if domain:
            fields = (MatchField(field, raw),)
            add(CorrelationKind.DOMAIN, domain, fields)
            if email:
                add(CorrelationKind.EMAIL, email, fields)
            if entity.entity_type == "domain":
                add(CorrelationKind.NAME, domain, fields)
    if entity.entity_type in {"person", "company"}:
        raw = str(entity.data.get("phone") or "")
        if raw.strip():
            normalized = re.sub(r"[ ().\-]", "", raw.strip())
            if re.fullmatch(r"\+?[0-9]+", normalized):
                add(CorrelationKind.PHONE, normalized, (MatchField("phone", raw),))
            else:
                skipped.append(SkippedReference(entity.case_id, entity.id, "phone"))
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
        CorrelationKind.EMAIL: "Exact email match",
        CorrelationKind.PHONE: "Exact phone match",
    }[kind]
