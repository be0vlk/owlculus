"""
Case service layer handling all case-related business logic
"""

from datetime import datetime

from app import schemas
from app.core.dependencies import admin_only, check_case_access, no_analyst
from app.core.file_storage import create_case_directory
from app.core.logging import get_security_logger
from app.core.utils import get_utc_now
from app.database import crud, models
from app.database.db_utils import transaction
from app.services.system_config_service import SystemConfigService
from fastapi import HTTPException
from sqlmodel import Session, select


class CaseService:
    def __init__(self, db: Session):
        self.db = db
        self.config_service = SystemConfigService(db)

    async def _generate_case_number(self, current_time: datetime) -> str:
        # Get system configuration
        config = await self.config_service.get_configuration()

        # Extract year and month from current time
        year = str(current_time.year)[2:]
        month = str(current_time.month).zfill(2)

        # Build search pattern based on template
        if (
            config.case_number_template == "PREFIX-YYMM-NN"
            and config.case_number_prefix
        ):
            search_pattern = f"{config.case_number_prefix}-{year}{month}-%"
            base_format = f"{config.case_number_prefix}-{year}{month}"
        else:
            # Default to YYMM-NN format
            search_pattern = f"{year}{month}-%"
            base_format = f"{year}{month}"

        # Find the highest case number for this month
        stmt = select(models.Case).where(models.Case.case_number.like(search_pattern))
        cases = self.db.exec(stmt).all()

        if not cases:
            return f"{base_format}-01"

        # Get the highest number from the last part after the final dash
        highest = max(int(case.case_number.split("-")[-1]) for case in cases)
        # Increment and ensure 2 digits
        next_number = str(highest + 1).zfill(2)
        return f"{base_format}-{next_number}"

    @admin_only()
    async def create_case(
        self, case: schemas.CaseCreate, current_user: models.User
    ) -> models.Case:
        case_logger = get_security_logger(
            admin_user_id=current_user.id,
            action="create_case",
            case_name=case.title,
            event_type="case_creation_attempt",
        )

        try:
            # Use transaction to ensure atomicity
            with transaction(self.db):
                # Always generate a new case number, ignoring any provided value
                case_data = case.model_dump()
                current_time = get_utc_now()
                case_data["case_number"] = await self._generate_case_number(
                    current_time
                )

                # Create the case in the database
                new_case = await crud.create_case(
                    self.db,
                    case=schemas.CaseCreate(**case_data),
                    current_user=current_user,
                )

            # Create the case directory for file uploads (outside transaction)
            create_case_directory(new_case.id)

            case_logger.bind(
                case_id=new_case.id,
                case_number=new_case.case_number,
                client_id=new_case.client_id,
                event_type="case_creation_success",
            ).info("Case created successfully")

            return new_case

        except Exception as e:
            case_logger.bind(
                event_type="case_creation_error", error_type="system_error"
            ).error(f"Case creation error: {str(e)}")
            raise HTTPException(status_code=500, detail="Internal server error")

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
        # Check case access and return the case if authorized
        return check_case_access(self.db, case_id, current_user)

    @no_analyst()
    async def update_case(
        self, case_id: int, case_update: schemas.CaseUpdate, current_user: models.User
    ) -> models.Case:
        case_logger = get_security_logger(
            user_id=current_user.id,
            case_id=case_id,
            action="update_case",
            event_type="case_update_attempt",
        )

        try:
            # Check case access
            try:
                db_case = check_case_access(self.db, case_id, current_user)
            except HTTPException as e:
                if e.status_code == 404:
                    case_logger.bind(
                        event_type="case_update_failed", failure_reason="case_not_found"
                    ).warning("Case update failed: case not found")
                else:
                    case_logger.bind(
                        event_type="case_update_failed", failure_reason="not_authorized"
                    ).warning("Case update failed: not authorized")
                raise

            # Check case number uniqueness if being updated
            if (
                case_update.case_number
                and case_update.case_number != db_case.case_number
            ):
                existing_case = await crud.get_case_by_number(
                    self.db, case_number=case_update.case_number
                )
                if existing_case:
                    case_logger.bind(
                        event_type="case_update_failed",
                        failure_reason="case_number_exists",
                        requested_case_number=case_update.case_number,
                    ).warning("Case update failed: case number already exists")
                    raise HTTPException(
                        status_code=400, detail="Case number already exists"
                    )

            updated_case = await crud.update_case(
                self.db, case_id=case_id, case=case_update, current_user=current_user
            )

            case_logger.bind(
                case_number=updated_case.case_number, event_type="case_update_success"
            ).info("Case updated successfully")

            return updated_case

        except HTTPException:
            raise
        except Exception as e:
            case_logger.bind(
                event_type="case_update_error", error_type="system_error"
            ).error(f"Case update error: {str(e)}")
            raise HTTPException(status_code=500, detail="Internal server error")

    @admin_only()
    async def add_user_to_case(
        self, case_id: int, user_id: int, current_user: models.User
    ) -> models.Case:
        case_logger = get_security_logger(
            admin_user_id=current_user.id,
            case_id=case_id,
            target_user_id=user_id,
            action="add_user_to_case",
            event_type="case_user_add_attempt",
        )

        try:
            # Check if case exists first
            db_case = await crud.get_case(self.db, case_id=case_id)
            if not db_case:
                case_logger.bind(
                    event_type="case_user_add_failed", failure_reason="case_not_found"
                ).warning("Add user to case failed: case not found")
                raise HTTPException(status_code=404, detail="Case not found")

            db_user = await crud.get_user(self.db, user_id=user_id)
            if not db_user:
                case_logger.bind(
                    event_type="case_user_add_failed", failure_reason="user_not_found"
                ).warning("Add user to case failed: user not found")
                raise HTTPException(status_code=404, detail="User not found")

            updated_case = await crud.add_user_to_case(
                self.db, case=db_case, user=db_user
            )

            case_logger.bind(
                case_number=db_case.case_number,
                username=db_user.username,
                event_type="case_user_add_success",
            ).info("User added to case successfully")

            return updated_case

        except HTTPException:
            raise
        except Exception as e:
            # Check if this is a duplicate user error
            if "UNIQUE constraint failed" in str(e) and "caseuserlink" in str(e):
                case_logger.bind(
                    event_type="case_user_add_failed",
                    failure_reason="user_already_assigned",
                ).warning("Add user to case failed: user already assigned to case")
                raise HTTPException(
                    status_code=400, detail="User is already assigned to this case"
                )

            case_logger.bind(
                event_type="case_user_add_error", error_type="system_error"
            ).error(f"Add user to case error: {str(e)}")
            raise HTTPException(status_code=500, detail="Internal server error")

    @admin_only()
    async def remove_user_from_case(
        self, case_id: int, user_id: int, current_user: models.User
    ) -> models.Case:
        case_logger = get_security_logger(
            admin_user_id=current_user.id,
            case_id=case_id,
            target_user_id=user_id,
            action="remove_user_from_case",
            event_type="case_user_remove_attempt",
        )

        try:
            # Check if case exists first
            db_case = await crud.get_case(self.db, case_id=case_id)
            if not db_case:
                case_logger.bind(
                    event_type="case_user_remove_failed",
                    failure_reason="case_not_found",
                ).warning("Remove user from case failed: case not found")
                raise HTTPException(status_code=404, detail="Case not found")

            db_user = await crud.get_user(self.db, user_id=user_id)
            if not db_user:
                case_logger.bind(
                    event_type="case_user_remove_failed",
                    failure_reason="user_not_found",
                ).warning("Remove user from case failed: user not found")
                raise HTTPException(status_code=404, detail="User not found")

            updated_case = await crud.remove_user_from_case(
                self.db, case=db_case, user=db_user
            )

            case_logger.bind(
                case_number=db_case.case_number,
                username=db_user.username,
                event_type="case_user_remove_success",
            ).info("User removed from case successfully")

            return updated_case

        except HTTPException:
            raise
        except Exception as e:
            case_logger.bind(
                event_type="case_user_remove_error", error_type="system_error"
            ).error(f"Remove user from case error: {str(e)}")
            raise HTTPException(status_code=500, detail="Internal server error")
