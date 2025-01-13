"""
Case service layer handling all case-related business logic
"""

from sqlmodel import Session, select
from fastapi import HTTPException
from datetime import datetime

from app.database import models, crud
from app import schemas
from app.core.utils import get_utc_now
from app.core.dependencies import admin_only, no_analyst
from app.core.file_storage import create_case_directory


class CaseService:
    def __init__(self, db: Session):
        self.db = db

    async def _generate_case_number(self, current_time: datetime) -> str:
        # Extract year and month from current time
        year = str(current_time.year)[2:]
        month = str(current_time.month).zfill(2)
        prefix = f"{year}{month}"

        # Find the highest case number for this month
        stmt = select(models.Case).where(models.Case.case_number.like(f"{prefix}-%"))
        cases = self.db.exec(stmt).all()

        if not cases:
            return f"{prefix}-01"

        # Get the highest number
        highest = max(int(case.case_number.split("-")[1]) for case in cases)
        # Increment and ensure 2 digits
        next_number = str(highest + 1).zfill(2)
        return f"{prefix}-{next_number}"

    @admin_only()
    async def create_case(
        self, case: schemas.CaseCreate, current_user: models.User
    ) -> models.Case:
        # Always generate a new case number, ignoring any provided value
        case_data = case.model_dump()
        current_time = get_utc_now()
        case_data["case_number"] = await self._generate_case_number(current_time)

        # Create the case in the database
        new_case = await crud.create_case(
            self.db, case=schemas.CaseCreate(**case_data), current_user=current_user
        )

        # Create the case directory for file uploads
        create_case_directory(new_case.id)

        return new_case

    async def get_cases(
        self,
        current_user: models.User,
        skip: int = 0,
        limit: int = 100,
        status: str | None = None,
    ) -> list[models.Case]:
        if current_user.role == "Admin":
            stmt = select(models.Case)
            if status:
                stmt = stmt.where(models.Case.status == status)
            stmt = stmt.offset(skip).limit(limit)
            result = self.db.exec(stmt)
            return result.all()

        # For non-admin users, only return cases they are associated with
        stmt = (
            select(models.Case)
            .join(models.CaseUserLink)
            .where(models.CaseUserLink.user_id == current_user.id)
        )
        if status:
            stmt = stmt.where(models.Case.status == status)
        stmt = stmt.offset(skip).limit(limit)
        result = self.db.exec(stmt)
        return result.all()

    async def get_case(self, case_id: int, current_user: models.User) -> models.Case:
        db_case = await crud.get_case(self.db, case_id=case_id)
        if not db_case:
            raise HTTPException(status_code=404, detail="Case not found")

        # Admin can access any case
        if current_user.role == "Admin":
            return db_case

        # For non-admin users, check if they are associated with the case
        if current_user not in db_case.users:
            raise HTTPException(status_code=403, detail="Not authorized")
        return db_case

    @no_analyst()
    async def update_case(
        self, case_id: int, case_update: schemas.CaseUpdate, current_user: models.User
    ) -> models.Case:
        db_case = await crud.get_case(self.db, case_id=case_id)
        if not db_case:
            raise HTTPException(status_code=404, detail="Case not found")

        # Admin can update any case
        if current_user.role != "Admin" and current_user not in db_case.users:
            raise HTTPException(
                status_code=403, detail="You do not have permission to update this case"
            )

        # Check case number uniqueness if being updated
        if case_update.case_number and case_update.case_number != db_case.case_number:
            existing_case = await crud.get_case_by_number(
                self.db, case_number=case_update.case_number
            )
            if existing_case:
                raise HTTPException(
                    status_code=400, detail="Case number already exists"
                )

        return await crud.update_case(
            self.db, case_id=case_id, case=case_update, current_user=current_user
        )

    @admin_only()
    async def add_user_to_case(
        self, case_id: int, user_id: int, current_user: models.User
    ) -> models.Case:
        # Check if case exists first
        db_case = await crud.get_case(self.db, case_id=case_id)
        if not db_case:
            raise HTTPException(status_code=404, detail="Case not found")

        db_user = await crud.get_user(self.db, user_id=user_id)
        if not db_user:
            raise HTTPException(status_code=404, detail="User not found")

        return await crud.add_user_to_case(self.db, case=db_case, user=db_user)

    @admin_only()
    async def remove_user_from_case(
        self, case_id: int, user_id: int, current_user: models.User
    ) -> models.Case:
        # Check if case exists first
        db_case = await crud.get_case(self.db, case_id=case_id)
        if not db_case:
            raise HTTPException(status_code=404, detail="Case not found")

        db_user = await crud.get_user(self.db, user_id=user_id)
        if not db_user:
            raise HTTPException(status_code=404, detail="User not found")

        return await crud.remove_user_from_case(self.db, case=db_case, user=db_user)
