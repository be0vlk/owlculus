"""
Case management service for Owlculus OSINT investigations platform.

This module handles all case-related business logic including case creation,
user assignment, case number generation, and access control. Provides comprehensive
case lifecycle management with automated numbering, user role validation,
and security logging for OSINT investigation workflows.
"""

from datetime import datetime

from sqlmodel import Session, col, select

from app import schemas
from app.core.exceptions import (
    DuplicateResourceException,
    ResourceNotFoundException,
    ValidationException,
)
from app.core.logging import audit_operation
from app.core.utils import get_utc_now
from app.database import models
from app.database.db_utils import transaction
from app.schemas.case_schema import CaseUser
from app.services.case_access import CaseAccess
from app.services.system_config_service import SystemConfigService


class CaseService:
    def __init__(self, db: Session):
        self.db = db
        self.case_access = CaseAccess(db)
        self.config_service = SystemConfigService(db)

    async def _generate_case_number(self, current_time: datetime) -> str:
        config = await self.config_service.get_configuration()

        year = str(current_time.year)[2:]
        month = str(current_time.month).zfill(2)

        if (
            config.case_number_template == "PREFIX-YYMM-NN"
            and config.case_number_prefix
        ):
            search_pattern = f"{config.case_number_prefix}-{year}{month}-%"
            base_format = f"{config.case_number_prefix}-{year}{month}"
        else:
            search_pattern = f"{year}{month}-%"
            base_format = f"{year}{month}"

        stmt = select(models.Case).where(
            col(models.Case.case_number).like(search_pattern)
        )
        cases = self.db.exec(stmt).all()

        if not cases:
            return f"{base_format}-01"

        highest = max(int(case.case_number.split("-")[-1]) for case in cases)
        next_number = str(highest + 1).zfill(2)
        return f"{base_format}-{next_number}"

    @audit_operation("case_creation")
    async def create_case(
        self, case: schemas.CaseCreate, current_user: models.User
    ) -> models.Case:
        self.case_access.require_admin(current_user)
        with transaction(self.db):
            # Always generate a new case number, ignoring any provided value
            case_data = case.model_dump()
            current_time = get_utc_now()
            case_data["case_number"] = await self._generate_case_number(current_time)

            new_case = models.Case(
                **schemas.CaseCreate(**case_data).model_dump(),
                created_by_id=current_user.id,
                created_at=current_time,
                updated_at=current_time,
            )
            self.db.add(new_case)
            self.db.flush()

        return new_case

    async def get_cases(
        self,
        current_user: models.User,
        skip: int = 0,
        limit: int = 100,
        status: str | None = None,
    ) -> list[schemas.Case]:
        if self.case_access.is_admin(current_user):
            stmt = select(models.Case)
            if status:
                stmt = stmt.where(models.Case.status == status)
            stmt = stmt.offset(skip).limit(limit)
            result = self.db.exec(stmt)
            cases = result.all()
        else:
            stmt = (
                select(models.Case)
                .join(models.CaseUserLink)
                .where(models.CaseUserLink.user_id == current_user.id)
            )
            if status:
                stmt = stmt.where(models.Case.status == status)
            stmt = stmt.offset(skip).limit(limit)
            result = self.db.exec(stmt)
            cases = result.all()

        return self.load_cases_with_users(list(cases))

    async def get_case(self, case_id: int, current_user: models.User) -> schemas.Case:
        case = self.case_access.readable(current_user, case_id)
        return self.load_cases_with_users([case])[0]

    @audit_operation("case_update")
    async def update_case(
        self, case_id: int, case_update: schemas.CaseUpdate, current_user: models.User
    ) -> models.Case:
        db_case = self.case_access.writable(current_user, case_id)
        if case_update.case_number and case_update.case_number != db_case.case_number:
            existing_case = self.db.exec(
                select(models.Case).where(
                    models.Case.case_number == case_update.case_number
                )
            ).first()
            if existing_case:
                raise DuplicateResourceException("Case number already exists")

        with transaction(self.db):
            update_data = case_update.model_dump(exclude_unset=True)
            for field, value in update_data.items():
                setattr(db_case, field, value)
            db_case.updated_at = get_utc_now()
            self.db.add(db_case)
        self.db.refresh(db_case)
        return db_case

    def _case_and_user(
        self, case_id: int, user_id: int
    ) -> tuple[models.Case, models.User]:
        db_case = self.db.get(models.Case, case_id)
        if not db_case:
            raise ResourceNotFoundException("Case not found")
        db_user = self.db.get(models.User, user_id)
        if not db_user:
            raise ResourceNotFoundException("User not found")
        return db_case, db_user

    @audit_operation("case_user_add")
    async def add_user_to_case(
        self,
        case_id: int,
        user_id: int,
        current_user: models.User,
        is_lead: bool = False,
    ) -> models.Case:
        self.case_access.require_admin(current_user)
        db_case, db_user = self._case_and_user(case_id, user_id)
        self.case_access.validate_lead_assignment(db_user, is_lead=is_lead)

        with transaction(self.db):
            existing_link = self.db.exec(
                select(models.CaseUserLink).where(
                    models.CaseUserLink.case_id == db_case.id,
                    models.CaseUserLink.user_id == db_user.id,
                )
            ).first()
            if existing_link:
                existing_link.is_lead = is_lead
                self.db.add(existing_link)
            else:
                self.db.add(
                    models.CaseUserLink(
                        case_id=db_case.id,
                        user_id=db_user.id,
                        is_lead=is_lead,
                    )
                )
            db_case.updated_at = get_utc_now()
            self.db.add(db_case)
        self.db.refresh(db_case)
        return db_case

    @audit_operation("case_user_remove")
    async def remove_user_from_case(
        self, case_id: int, user_id: int, current_user: models.User
    ) -> models.Case:
        self.case_access.require_admin(current_user)
        db_case, db_user = self._case_and_user(case_id, user_id)

        with transaction(self.db):
            db_case.users.remove(db_user)
            db_case.updated_at = get_utc_now()
            self.db.add(db_case)
        self.db.refresh(db_case)
        return db_case

    @audit_operation("case_user_lead_update")
    async def update_case_user_lead_status(
        self, case_id: int, user_id: int, is_lead: bool, current_user: models.User
    ) -> models.Case:
        self.case_access.require_admin(current_user)
        db_case, db_user = self._case_and_user(case_id, user_id)
        if db_user not in db_case.users:
            raise ValidationException("User is not assigned to this case")
        self.case_access.validate_lead_assignment(db_user, is_lead=is_lead)

        with transaction(self.db):
            link = self.db.exec(
                select(models.CaseUserLink).where(
                    models.CaseUserLink.case_id == case_id,
                    models.CaseUserLink.user_id == user_id,
                )
            ).first()
            if link is None:
                raise ValidationException("User is not assigned to this case")
            link.is_lead = is_lead
            db_case.updated_at = get_utc_now()
            self.db.add(link)
            self.db.add(db_case)
        self.db.refresh(db_case)
        return db_case

    def load_cases_with_users(self, cases: list[models.Case]) -> list[schemas.Case]:
        """Enrich cases and lead flags with one joined query for any list size."""
        if not cases:
            return []

        case_ids = [case.id for case in cases if case.id is not None]
        rows = self.db.exec(
            select(
                models.CaseUserLink.case_id, models.User, models.CaseUserLink.is_lead
            )
            .join(
                models.User,
                col(models.User.id) == models.CaseUserLink.user_id,
            )
            .where(col(models.CaseUserLink.case_id).in_(case_ids))
            .order_by(
                col(models.CaseUserLink.case_id),
                col(models.User.id),
            )
        ).all()
        users_by_case: dict[int, list[CaseUser]] = {
            case_id: [] for case_id in case_ids if case_id is not None
        }
        for case_id, user, is_lead in rows:
            if case_id is None:
                continue
            user_data = user.model_dump()
            user_data["is_lead"] = is_lead
            users_by_case[case_id].append(CaseUser(**user_data))

        enriched = []
        for case in cases:
            case_data = case.model_dump()
            case_data["users"] = (
                users_by_case.get(case.id, []) if case.id is not None else []
            )
            enriched.append(schemas.Case(**case_data))
        return enriched
