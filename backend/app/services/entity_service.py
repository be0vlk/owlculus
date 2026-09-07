"""
Entity management service for Owlculus OSINT data collection and tracking.

This module handles all entity-related business logic including entity creation,
validation, duplicate detection, and relationship management. Provides secure
entity operations with case access control, data enrichment capabilities,
and specialized search functions for OSINT investigation workflows.
"""

from dataclasses import dataclass
from typing import cast

from sqlalchemy import func
from sqlmodel import Session, col, or_, select

from app import schemas
from app.core.exceptions import (
    DuplicateResourceException,
    ResourceNotFoundException,
    ValidationException,
)
from app.core.hostname import canonical_hostname
from app.core.utils import get_utc_now
from app.database import models
from app.database.db_utils import transaction
from app.schemas.entity_schema import DuplicateAdvisory, entity_display_name
from app.services.case_access import CaseAccess


@dataclass(frozen=True)
class DuplicatePolicy:
    """Describe one database-backed entity identity rule."""

    entity_type: str
    fields: tuple[str, ...]
    error_template: str
    case_sensitive: bool = False


_DUPLICATE_POLICIES = (
    DuplicatePolicy(
        "company",
        ("name",),
        "A company with the name '{name}' already exists in this case",
    ),
    DuplicatePolicy(
        "ip_address",
        ("ip_address",),
        "An IP address '{ip_address}' already exists in this case",
        case_sensitive=True,
    ),
    DuplicatePolicy(
        "domain", ("domain",), "A domain '{domain}' already exists in this case"
    ),
)


class EntityService:
    def __init__(self, db: Session):
        self.db = db
        self.case_access = CaseAccess(db)

    async def _check_duplicates(
        self,
        case_id: int,
        entity: schemas.EntityCreate | schemas.EntityUpdate,
        entity_id: int | None = None,
    ) -> None:
        entity_data = entity.model_dump()
        entity_type = cast(
            str | None,
            getattr(entity, "entity_type", None)
            or getattr(entity, "entity_type_hint", None)
            or entity_data.get("__entity_type"),
        )

        if entity_type is None:
            return

        for decision in self._duplicate_decisions(
            case_id, entity_type, entity.data, entity_id
        ):
            if decision.blocking:
                raise DuplicateResourceException(decision.reason)

        if entity_type == "network_assets":
            conditions = []
            for field in ("domains", "ip_addresses", "subdomains"):
                values = entity.data.get(field, [])
                if values:
                    conditions.append(
                        or_(
                            *[
                                models.Entity.data[field].as_array().any(value.lower())
                                for value in values
                            ]
                        )
                    )
            if conditions:
                query = select(models.Entity).where(
                    models.Entity.case_id == case_id,
                    models.Entity.entity_type == "network_assets",
                    or_(*conditions),
                )
                if entity_id is not None:
                    query = query.where(models.Entity.id != entity_id)
                if self.db.exec(query).first():
                    raise DuplicateResourceException(
                        "Network assets with overlapping domains, IP addresses, or subdomains already exist in this case"
                    )

    def _duplicate_decisions(
        self, case_id: int, entity_type: str, data: dict, exclude_id: int | None = None
    ) -> list[DuplicateAdvisory]:
        """One literal identity policy for advisory reads and final writes."""

        def normalized(value: object) -> str:
            return str(value or "").strip().casefold()

        query = (
            select(models.Entity)
            .where(
                models.Entity.case_id == case_id,
                models.Entity.entity_type == entity_type,
            )
            .order_by(col(models.Entity.id))
        )
        if exclude_id is not None:
            query = query.where(models.Entity.id != exclude_id)
        if entity_type == "domain":
            candidate = self._find_domain(case_id, data["domain"], exclude_id)
            candidates = [candidate] if candidate else []
        else:
            candidates = list(self.db.exec(query))
        decisions = []
        for candidate in candidates:
            reason = ""
            blocking = True
            if entity_type == "person":
                name = tuple(
                    normalized(data.get(field)) for field in ("first_name", "last_name")
                )
                other = tuple(
                    normalized(candidate.data.get(field))
                    for field in ("first_name", "last_name")
                )
                if any(name) and name == other:
                    reason = "Same name; this may be a different Person."
                    blocking = False
            elif entity_type == "vehicle":
                vin, other_vin = normalized(data.get("vin")), normalized(
                    candidate.data.get("vin")
                )
                plate, other_plate = normalized(data.get("license_plate")), normalized(
                    candidate.data.get("license_plate")
                )
                state, other_state = normalized(
                    data.get("registration_state")
                ), normalized(candidate.data.get("registration_state"))
                if vin and vin == other_vin:
                    reason = "A vehicle with this VIN already exists in this case"
                elif plate and plate == other_plate:
                    conflicting_vins = bool(vin and other_vin and vin != other_vin)
                    if (
                        state
                        and other_state
                        and state != other_state
                        and not conflicting_vins
                    ):
                        continue
                    blocking = bool(
                        state and state == other_state and not conflicting_vins
                    )
                    reason = (
                        "A vehicle with this license plate and registration state already exists in this case"
                        if blocking
                        else "Same plate with missing/different jurisdiction or conflicting VINs; inspect before keeping a separate Vehicle."
                    )
            else:
                for policy in _DUPLICATE_POLICIES:
                    if policy.entity_type != entity_type:
                        continue
                    if entity_type == "domain" or all(
                        data.get(field)
                        and (
                            str(data[field]).strip()
                            == str(candidate.data.get(field) or "").strip()
                            if policy.case_sensitive
                            else normalized(data[field])
                            == normalized(candidate.data.get(field))
                        )
                        for field in policy.fields
                    ):
                        reason = policy.error_template.format(**data)
                        break
            if reason:
                summary_fields = (
                    ("email", "dob", "phone", "employer")
                    if entity_type == "person"
                    else ("vin", "license_plate", "registration_state")
                )
                decisions.append(
                    DuplicateAdvisory(
                        id=cast(int, candidate.id),
                        label=entity_display_name(entity_type, candidate.data)
                        or f"{entity_type} #{candidate.id}",
                        identifiers={
                            field: candidate.data[field]
                            for field in summary_fields
                            if candidate.data.get(field)
                        },
                        reason=reason,
                        blocking=blocking,
                    )
                )
        return decisions

    async def duplicate_advisories(
        self,
        case_id: int,
        entity: schemas.EntityCreate,
        current_user: models.User,
        exclude_id: int | None = None,
    ) -> list[DuplicateAdvisory]:
        self.case_access.readable(current_user, case_id)
        if exclude_id is not None:
            existing = await self.get_entity(case_id, exclude_id, current_user)
            if existing.entity_type != entity.entity_type:
                raise ValidationException("Entity type cannot change")
        return self._duplicate_decisions(
            case_id, entity.entity_type, entity.data, exclude_id
        )[:20]

    async def get_case_entities(
        self,
        case_id: int,
        current_user: models.User,
        entity_type: str | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> list[models.Entity]:
        case = self.case_access.readable(current_user, case_id)

        query = select(models.Entity).where(models.Entity.case_id == case.id)

        if entity_type:
            query = query.where(models.Entity.entity_type == entity_type)

        query = query.order_by(col(models.Entity.id)).offset(skip).limit(limit)
        result = self.db.exec(query)
        return list(result)

    async def get_entity(
        self,
        case_id: int,
        entity_id: int,
        current_user: models.User,
    ) -> models.Entity:
        case = self.case_access.readable(current_user, case_id)
        db_entity = self.db.get(models.Entity, entity_id)
        if not db_entity or db_entity.case_id != case.id:
            raise ResourceNotFoundException("Entity not found")

        return db_entity

    async def create_entity(
        self,
        case_id: int,
        entity: schemas.EntityCreate,
        current_user: models.User,
    ) -> models.Entity:
        case = self.case_access.writable(current_user, case_id)

        if case.id is None:
            raise ResourceNotFoundException("Case not found")
        await self._check_duplicates(case.id, entity)
        with transaction(self.db):
            db_entity = models.Entity(
                case_id=case.id,
                entity_type=entity.entity_type,
                data=entity.data,
                created_by_id=current_user.id,
                created_at=get_utc_now(),
                updated_at=get_utc_now(),
            )

            self.db.add(db_entity)

        self.db.refresh(db_entity)
        return db_entity

    async def update_entity(
        self,
        case_id: int,
        entity_id: int,
        entity_update: schemas.EntityUpdate,
        current_user: models.User,
    ) -> models.Entity:
        case = self.case_access.writable(current_user, case_id)
        db_entity = self.db.get(models.Entity, entity_id)
        if not db_entity or db_entity.case_id != case.id:
            raise ResourceNotFoundException("Entity not found")

        # Add entity type to update data for validation
        entity_update_dict = entity_update.model_dump()
        entity_update_dict["__entity_type"] = db_entity.entity_type

        try:
            validated_update = schemas.EntityUpdate(**entity_update_dict)
        except ValueError as e:
            raise ValidationException(str(e))

        await self._check_duplicates(db_entity.case_id, validated_update, entity_id)
        with transaction(self.db):
            db_entity.data = validated_update.data
            db_entity.updated_at = get_utc_now()

            self.db.add(db_entity)

        self.db.refresh(db_entity)

        return db_entity

    async def delete_entity(
        self,
        case_id: int,
        entity_id: int,
        current_user: models.User,
    ) -> None:
        case = self.case_access.writable(current_user, case_id)
        db_entity = self.db.get(models.Entity, entity_id)
        if not db_entity or db_entity.case_id != case.id:
            raise ResourceNotFoundException("Entity not found")
        with transaction(self.db):
            self.db.delete(db_entity)

    async def find_entity_by_ip_address(
        self, case_id: int, ip_address: str, current_user: models.User
    ) -> models.Entity | None:
        """Find an existing IP address entity in the given case"""
        case = self.case_access.readable(current_user, case_id)

        query = select(models.Entity).where(
            models.Entity.case_id == case.id,
            models.Entity.entity_type == "ip_address",
            func.trim(models.Entity.data["ip_address"].as_string()) == ip_address.strip(),
        )
        result = self.db.exec(query)
        return result.first()

    async def find_entity_by_domain(
        self, case_id: int, domain: str, current_user: models.User
    ) -> models.Entity | None:
        """Find an existing domain entity in the given case (case-insensitive)"""
        self.case_access.readable(current_user, case_id)

        return self._find_domain(case_id, domain)

    def _find_domain(
        self, case_id: int, domain: str, exclude_id: int | None = None
    ) -> models.Entity | None:
        """Compare new and historical Domain values without rewriting stored data."""
        identity = canonical_hostname(domain)
        query = (
            select(models.Entity)
            .where(
                models.Entity.case_id == case_id,
                models.Entity.entity_type == "domain",
            )
            .order_by(col(models.Entity.id))
        )
        if exclude_id is not None:
            query = query.where(models.Entity.id != exclude_id)
        for candidate in self.db.exec(query):
            raw = candidate.data.get("domain")
            if not isinstance(raw, str):
                continue
            try:
                if canonical_hostname(raw) == identity:
                    return candidate
            except ValueError:
                continue
        return None

    async def enrich_entity_description(
        self,
        case_id: int,
        entity_id: int,
        additional_description: str,
        current_user: models.User,
    ) -> models.Entity:
        """Enrich an existing entity's description with additional information"""
        case = self.case_access.writable(current_user, case_id)
        db_entity = self.db.get(models.Entity, entity_id)
        if not db_entity or db_entity.case_id != case.id:
            raise ResourceNotFoundException("Entity not found")

        current_description = db_entity.data.get("description", "")

        if current_description:
            enriched_description = f"{current_description}\n\n--- Additional Info ---\n{additional_description}"
        else:
            enriched_description = additional_description

        with transaction(self.db):
            updated_data = db_entity.data.copy()
            updated_data["description"] = enriched_description

            db_entity.data = updated_data
            db_entity.updated_at = get_utc_now()

            self.db.add(db_entity)

        self.db.refresh(db_entity)
        return db_entity
