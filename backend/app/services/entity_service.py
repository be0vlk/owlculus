"""
Entity service layer handling all entity-related business logic
"""

from sqlmodel import Session, select
from fastapi import HTTPException
from typing import Optional

from app.database import models
from app import schemas
from app.core.utils import get_utc_now
from app.core.dependencies import no_analyst, case_must_be_open
from app.database import crud


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
        # Validate the case exists
        case = self.db.get(models.Case, case_id)
        if case is None:
            raise HTTPException(status_code=404, detail="Case not found")

        query = select(models.Entity).where(models.Entity.case_id == case_id)

        if entity_type:
            query = query.where(models.Entity.entity_type == entity_type)

        query = query.offset(skip).limit(limit)
        result = self.db.exec(query)
        return list(result)

    @no_analyst()
    async def create_entity(
        self,
        case_id: int,
        entity: schemas.EntityCreate,
        current_user: models.User,
    ) -> models.Entity:
        # Validate the case exists
        case = self.db.get(models.Case, case_id)
        if case is None:
            raise HTTPException(status_code=404, detail="Case not found")

        # Check for duplicates using crud function
        await crud.check_entity_duplicates(self.db, case_id, entity)

        db_entity = models.Entity(
            case_id=case_id,
            entity_type=entity.entity_type,
            data=entity.data,
            created_by_id=current_user.id,
            created_at=get_utc_now(),
            updated_at=get_utc_now(),
        )

        self.db.add(db_entity)
        self.db.commit()
        self.db.refresh(db_entity)
        return db_entity

    @no_analyst()
    async def update_entity(
        self,
        entity_id: int,
        entity_update: schemas.EntityUpdate,
        current_user: models.User,
    ) -> models.Entity:
        db_entity = self.db.get(models.Entity, entity_id)
        if not db_entity:
            raise HTTPException(status_code=404, detail="Entity not found")

        # Add entity type to update data for validation
        entity_update_dict = entity_update.model_dump()
        entity_update_dict["__entity_type"] = db_entity.entity_type

        try:
            # Revalidate with entity type
            validated_update = schemas.EntityUpdate(**entity_update_dict)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

        # Check for duplicates using crud function
        await crud.check_entity_duplicates(
            self.db, db_entity.case_id, validated_update, entity_id
        )

        db_entity.data = validated_update.data
        db_entity.updated_at = get_utc_now()

        self.db.add(db_entity)
        self.db.commit()
        self.db.refresh(db_entity)

        return db_entity

    @no_analyst()
    async def delete_entity(
        self,
        entity_id: int,
        current_user: models.User,
    ) -> None:
        db_entity = self.db.get(models.Entity, entity_id)
        if not db_entity:
            raise HTTPException(status_code=404, detail="Entity not found")

        self.db.delete(db_entity)
        self.db.commit()

    async def find_entity_by_ip_address(
        self, case_id: int, ip_address: str
    ) -> Optional[models.Entity]:
        """Find an existing IP address entity in the given case"""
        case = self.db.get(models.Case, case_id)
        if case is None:
            raise HTTPException(status_code=404, detail="Case not found")

        query = select(models.Entity).where(
            models.Entity.case_id == case_id,
            models.Entity.entity_type == "ip_address",
            models.Entity.data["ip_address"].as_string() == ip_address,
        )
        result = self.db.exec(query)
        return result.first()

    async def find_entity_by_domain(
        self, case_id: int, domain: str
    ) -> Optional[models.Entity]:
        """Find an existing domain entity in the given case (case-insensitive)"""
        case = self.db.get(models.Case, case_id)
        if case is None:
            raise HTTPException(status_code=404, detail="Case not found")

        query = select(models.Entity).where(
            models.Entity.case_id == case_id,
            models.Entity.entity_type == "domain",
            models.Entity.data["domain"].as_string().ilike(domain),
        )
        result = self.db.exec(query)
        return result.first()

    @no_analyst()
    async def enrich_entity_description(
        self,
        entity_id: int,
        additional_description: str,
        current_user: models.User,
    ) -> models.Entity:
        """Enrich an existing entity's description with additional information"""
        db_entity = self.db.get(models.Entity, entity_id)
        if not db_entity:
            raise HTTPException(status_code=404, detail="Entity not found")

        current_description = db_entity.data.get("description", "")

        if current_description:
            # Append new description with separator
            enriched_description = f"{current_description}\n\n--- Additional Info ---\n{additional_description}"
        else:
            enriched_description = additional_description

        # Update the entity data with enriched description
        updated_data = db_entity.data.copy()
        updated_data["description"] = enriched_description

        db_entity.data = updated_data
        db_entity.updated_at = get_utc_now()

        self.db.add(db_entity)
        self.db.commit()
        self.db.refresh(db_entity)

        return db_entity
