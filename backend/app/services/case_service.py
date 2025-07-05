"""
Case service layer handling all case-related business logic
"""

from datetime import datetime

from app import schemas
from app.core.dependencies import check_case_access
from app.core.exceptions import (
    AuthorizationException,
    BaseException,
    DuplicateResourceException,
    ResourceNotFoundException,
    ValidationException,
)
from app.core.file_storage import create_case_directory
from app.core.logging import get_security_logger
from app.core.roles import UserRole
from app.core.utils import get_utc_now
from app.database import crud, models
from app.database.db_utils import transaction
from app.services.system_config_service import SystemConfigService
from sqlmodel import Session, select


class CaseService:
    def __init__(self, db: Session):
        self.db = db
        self.config_service = SystemConfigService(db)

    async def _generate_case_number(self, current_time: datetime) -> str:
        config = await self.config_service.get_configuration()

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
            search_pattern = f"{year}{month}-%"
            base_format = f"{year}{month}"

        stmt = select(models.Case).where(models.Case.case_number.like(search_pattern))
        cases = self.db.exec(stmt).all()

        if not cases:
            return f"{base_format}-01"

        # Get the highest number from the last part after the final dash
        highest = max(int(case.case_number.split("-")[-1]) for case in cases)
        # Increment and ensure 2 digits
        next_number = str(highest + 1).zfill(2)
        return f"{base_format}-{next_number}"

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

                new_case = await crud.create_case(
                    self.db,
                    case=schemas.CaseCreate(**case_data),
                    current_user=current_user,
                )

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
            raise BaseException("Internal server error")

    async def get_cases(
        self,
        current_user: models.User,
        skip: int = 0,
        limit: int = 100,
        status: str | None = None,
    ) -> list[models.Case]:
        from app.core.dependencies import load_case_with_users
        
        if current_user.role == UserRole.ADMIN.value:
            stmt = select(models.Case)
            if status:
                stmt = stmt.where(models.Case.status == status)
            stmt = stmt.offset(skip).limit(limit)
            result = self.db.exec(stmt)
            cases = result.all()
        else:
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
            cases = result.all()

        # Load each case with users including is_lead information
        cases_with_users = []
        for case in cases:
            case_with_users = load_case_with_users(self.db, case.id)
            if case_with_users:
                cases_with_users.append(case_with_users)

        return cases_with_users

    async def get_case(self, case_id: int, current_user: models.User) -> models.Case:
        from app.core.dependencies import load_case_with_users

        # First check access
        check_case_access(self.db, case_id, current_user)

        # Then load case with users including is_lead information
        return load_case_with_users(self.db, case_id)

    async def update_case(
        self, case_id: int, case_update: schemas.CaseUpdate, current_user: models.User
    ) -> models.Case:
        # Check if user is not an analyst
        if current_user.role == UserRole.ANALYST.value:
            raise AuthorizationException("Not authorized")

        case_logger = get_security_logger(
            user_id=current_user.id,
            case_id=case_id,
            action="update_case",
            event_type="case_update_attempt",
        )

        try:
            try:
                db_case = check_case_access(self.db, case_id, current_user)
            except AuthorizationException:
                case_logger.bind(
                    event_type="case_update_failed", failure_reason="not_authorized"
                ).warning("Case update failed: not authorized")
                raise
            except ResourceNotFoundException:
                case_logger.bind(
                    event_type="case_update_failed", failure_reason="case_not_found"
                ).warning("Case update failed: case not found")
                raise

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
                    raise ValidationException("Case number already exists")

            updated_case = await crud.update_case(
                self.db, case_id=case_id, case=case_update, current_user=current_user
            )

            case_logger.bind(
                case_number=updated_case.case_number, event_type="case_update_success"
            ).info("Case updated successfully")

            return updated_case

        except (AuthorizationException, ResourceNotFoundException, ValidationException):
            raise
        except Exception as e:
            case_logger.bind(
                event_type="case_update_error", error_type="system_error"
            ).error(f"Case update error: {str(e)}")
            raise BaseException("Internal server error")

    async def add_user_to_case(
        self, case_id: int, user_id: int, current_user: models.User, is_lead: bool = False
    ) -> models.Case:
        # Check if user is admin
        if current_user.role != UserRole.ADMIN.value:
            raise AuthorizationException("Not authorized")

        case_logger = get_security_logger(
            admin_user_id=current_user.id,
            case_id=case_id,
            target_user_id=user_id,
            action="add_user_to_case",
            event_type="case_user_add_attempt",
        )

        try:
            db_case = await crud.get_case(self.db, case_id=case_id)
            if not db_case:
                case_logger.bind(
                    event_type="case_user_add_failed", failure_reason="case_not_found"
                ).warning("Add user to case failed: case not found")
                raise ResourceNotFoundException("Case not found")

            db_user = await crud.get_user(self.db, user_id=user_id)
            if not db_user:
                case_logger.bind(
                    event_type="case_user_add_failed", failure_reason="user_not_found"
                ).warning("Add user to case failed: user not found")
                raise ResourceNotFoundException("User not found")

            # Check if user is analyst and being set as lead
            if is_lead and db_user.role == UserRole.ANALYST.value:
                case_logger.bind(
                    event_type="case_user_add_failed",
                    failure_reason="analyst_cannot_be_lead",
                ).warning("Add user to case failed: analyst cannot be set as lead")
                raise ValidationException("Analysts cannot be set as case leads")

            updated_case = await crud.add_user_to_case(
                self.db, case=db_case, user=db_user, is_lead=is_lead
            )

            case_logger.bind(
                case_number=db_case.case_number,
                username=db_user.username,
                event_type="case_user_add_success",
            ).info("User added to case successfully")

            return updated_case

        except (AuthorizationException, ResourceNotFoundException, ValidationException):
            raise
        except Exception as e:
            if "UNIQUE constraint failed" in str(e) and "caseuserlink" in str(e):
                case_logger.bind(
                    event_type="case_user_add_failed",
                    failure_reason="user_already_assigned",
                ).warning("Add user to case failed: user already assigned to case")
                raise DuplicateResourceException(
                    "User is already assigned to this case"
                )

            case_logger.bind(
                event_type="case_user_add_error", error_type="system_error"
            ).error(f"Add user to case error: {str(e)}")
            raise BaseException("Internal server error")

    async def remove_user_from_case(
        self, case_id: int, user_id: int, current_user: models.User
    ) -> models.Case:
        # Check if user is admin
        if current_user.role != UserRole.ADMIN.value:
            raise AuthorizationException("Not authorized")

        case_logger = get_security_logger(
            admin_user_id=current_user.id,
            case_id=case_id,
            target_user_id=user_id,
            action="remove_user_from_case",
            event_type="case_user_remove_attempt",
        )

        try:
            db_case = await crud.get_case(self.db, case_id=case_id)
            if not db_case:
                case_logger.bind(
                    event_type="case_user_remove_failed",
                    failure_reason="case_not_found",
                ).warning("Remove user from case failed: case not found")
                raise ResourceNotFoundException("Case not found")

            db_user = await crud.get_user(self.db, user_id=user_id)
            if not db_user:
                case_logger.bind(
                    event_type="case_user_remove_failed",
                    failure_reason="user_not_found",
                ).warning("Remove user from case failed: user not found")
                raise ResourceNotFoundException("User not found")

            updated_case = await crud.remove_user_from_case(
                self.db, case=db_case, user=db_user
            )

            case_logger.bind(
                case_number=db_case.case_number,
                username=db_user.username,
                event_type="case_user_remove_success",
            ).info("User removed from case successfully")

            return updated_case

        except (AuthorizationException, ResourceNotFoundException):
            raise
        except Exception as e:
            case_logger.bind(
                event_type="case_user_remove_error", error_type="system_error"
            ).error(f"Remove user from case error: {str(e)}")
            raise BaseException("Internal server error")

    async def update_case_user_lead_status(
        self, case_id: int, user_id: int, is_lead: bool, current_user: models.User
    ) -> models.Case:
        # Check if user is admin
        if current_user.role != UserRole.ADMIN.value:
            raise AuthorizationException("Not authorized")

        case_logger = get_security_logger(
            admin_user_id=current_user.id,
            case_id=case_id,
            target_user_id=user_id,
            action="update_case_user_lead_status",
            event_type="case_user_lead_update_attempt",
        )

        try:
            # Check if case exists
            db_case = await crud.get_case(self.db, case_id=case_id)
            if not db_case:
                case_logger.bind(
                    event_type="case_user_lead_update_failed",
                    failure_reason="case_not_found",
                ).warning("Update case user lead status failed: case not found")
                raise ResourceNotFoundException("Case not found")

            # Check if user exists
            db_user = await crud.get_user(self.db, user_id=user_id)
            if not db_user:
                case_logger.bind(
                    event_type="case_user_lead_update_failed",
                    failure_reason="user_not_found",
                ).warning("Update case user lead status failed: user not found")
                raise ResourceNotFoundException("User not found")

            # Check if user is assigned to case
            if db_user not in db_case.users:
                case_logger.bind(
                    event_type="case_user_lead_update_failed",
                    failure_reason="user_not_in_case",
                ).warning("Update case user lead status failed: user not assigned to case")
                raise ValidationException("User is not assigned to this case")

            # Check if user is analyst and being set as lead
            if is_lead and db_user.role == UserRole.ANALYST.value:
                case_logger.bind(
                    event_type="case_user_lead_update_failed",
                    failure_reason="analyst_cannot_be_lead",
                ).warning("Update case user lead status failed: analyst cannot be set as lead")
                raise ValidationException("Analysts cannot be set as case leads")

            # Update the lead status
            updated_case = await crud.update_case_user_lead_status(
                self.db, case_id=case_id, user_id=user_id, is_lead=is_lead
            )

            case_logger.bind(
                case_number=db_case.case_number,
                username=db_user.username,
                is_lead=is_lead,
                event_type="case_user_lead_update_success",
            ).info("Case user lead status updated successfully")

            return updated_case

        except (AuthorizationException, ResourceNotFoundException, ValidationException):
            raise
        except Exception as e:
            case_logger.bind(
                event_type="case_user_lead_update_error", error_type="system_error"
            ).error(f"Update case user lead status error: {str(e)}")
            raise BaseException("Internal server error")
