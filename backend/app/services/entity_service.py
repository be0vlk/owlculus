"""
Entity service layer handling all entity-related business logic
"""

from typing import Optional

from app import schemas
from app.core.dependencies import check_case_access
from app.core.exceptions import (
    ResourceNotFoundException,
    ValidationException,
)
from app.core.utils import get_utc_now
from app.database import crud, models
from app.database.db_utils import transaction
from sqlmodel import Session, select


class EntityService:
    def __init__(self, db: Session):
        self.db = db

    async def get_case_entities(
        self,
        case_id: int,
        current_user: models.User,
        entity_type: Optional[str] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> list[models.Entity]:
        # Check case access
        check_case_access(self.db, case_id, current_user)

        query = select(models.Entity).where(models.Entity.case_id == case_id)

        if entity_type:
            query = query.where(models.Entity.entity_type == entity_type)

        query = query.offset(skip).limit(limit)
        result = self.db.exec(query)
        return list(result)

    async def create_entity(
        self,
        case_id: int,
        entity: schemas.EntityCreate,
        current_user: models.User,
    ) -> models.Entity:
        # Check case access
        check_case_access(self.db, case_id, current_user)

        # Check for duplicates using crud function
        await crud.check_entity_duplicates(self.db, case_id, entity)

        # Use transaction for entity creation
        with transaction(self.db):
            db_entity = models.Entity(
                case_id=case_id,
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
        entity_id: int,
        entity_update: schemas.EntityUpdate,
        current_user: models.User,
    ) -> models.Entity:
        db_entity = self.db.get(models.Entity, entity_id)
        if not db_entity:
            raise ResourceNotFoundException("Entity not found")

        # Check case access
        check_case_access(self.db, db_entity.case_id, current_user)

        # Add entity type to update data for validation
        entity_update_dict = entity_update.model_dump()
        entity_update_dict["__entity_type"] = db_entity.entity_type

        try:
            # Revalidate with entity type
            validated_update = schemas.EntityUpdate(**entity_update_dict)
        except ValueError as e:
            raise ValidationException(str(e))

        # Check for duplicates using crud function
        await crud.check_entity_duplicates(
            self.db, db_entity.case_id, validated_update, entity_id
        )

        # Use transaction for entity update
        with transaction(self.db):
            db_entity.data = validated_update.data
            db_entity.updated_at = get_utc_now()

            self.db.add(db_entity)

        self.db.refresh(db_entity)

        return db_entity

    async def delete_entity(
        self,
        entity_id: int,
        current_user: models.User,
    ) -> None:
        db_entity = self.db.get(models.Entity, entity_id)
        if not db_entity:
            raise ResourceNotFoundException("Entity not found")

        # Check case access
        check_case_access(self.db, db_entity.case_id, current_user)

        # Use transaction for entity deletion
        with transaction(self.db):
            self.db.delete(db_entity)

    async def find_entity_by_ip_address(
        self, case_id: int, ip_address: str, current_user: models.User
    ) -> Optional[models.Entity]:
        """Find an existing IP address entity in the given case"""
        # Check case access
        check_case_access(self.db, case_id, current_user)

        query = select(models.Entity).where(
            models.Entity.case_id == case_id,
            models.Entity.entity_type == "ip_address",
            models.Entity.data["ip_address"].as_string() == ip_address,
        )
        result = self.db.exec(query)
        return result.first()

    async def find_entity_by_domain(
        self, case_id: int, domain: str, current_user: models.User
    ) -> Optional[models.Entity]:
        """Find an existing domain entity in the given case (case-insensitive)"""
        # Check case access
        check_case_access(self.db, case_id, current_user)

        query = select(models.Entity).where(
            models.Entity.case_id == case_id,
            models.Entity.entity_type == "domain",
            models.Entity.data["domain"].as_string().ilike(domain),
        )
        result = self.db.exec(query)
        return result.first()

    async def enrich_entity_description(
        self,
        entity_id: int,
        additional_description: str,
        current_user: models.User,
    ) -> models.Entity:
        """Enrich an existing entity's description with additional information"""
        db_entity = self.db.get(models.Entity, entity_id)
        if not db_entity:
            raise ResourceNotFoundException("Entity not found")

        # Check case access
        check_case_access(self.db, db_entity.case_id, current_user)

        current_description = db_entity.data.get("description", "")

        if current_description:
            # Append new description with separator
            enriched_description = f"{current_description}\n\n--- Additional Info ---\n{additional_description}"
        else:
            enriched_description = additional_description

        # Use transaction for entity update
        with transaction(self.db):
            # Update the entity data with enriched description
            updated_data = db_entity.data.copy()
            updated_data["description"] = enriched_description

            db_entity.data = updated_data
            db_entity.updated_at = get_utc_now()

            self.db.add(db_entity)

        self.db.refresh(db_entity)
        return db_entity
