"""
Service for managing and executing hunts
"""

import asyncio
import importlib
import inspect
import os
from typing import Any, Dict, List, Optional, Type

from app.core.dependencies import check_case_access, no_analyst
from app.core.logging import get_security_logger
from app.core.utils import get_utc_now
from app.database.models import Hunt, HuntExecution, HuntStep, User
from app.hunts import BaseHunt, HuntExecutor
from sqlmodel import Session, select

security_logger = get_security_logger


class HuntService:
    """Service for managing hunt definitions and executions"""

    def __init__(self, db: Session):
        self.db = db
        self._hunt_classes: Dict[str, Type[BaseHunt]] = {}
        self._load_hunt_definitions()
        self._sync_hunts_to_db()

    def _load_hunt_definitions(self):
        """Load built-in hunt definitions from the definitions directory"""
        definitions_dir = os.path.join(
            os.path.dirname(os.path.dirname(__file__)), "hunts", "definitions"
        )

        for filename in os.listdir(definitions_dir):
            if filename.endswith("_hunt.py") and filename != "__init__.py":
                module_name = filename[:-3]
                try:
                    module = importlib.import_module(
                        f"app.hunts.definitions.{module_name}"
                    )

                    # Find hunt classes in the module
                    for name, obj in inspect.getmembers(module):
                        if (
                            inspect.isclass(obj)
                            and issubclass(obj, BaseHunt)
                            and obj != BaseHunt
                        ):
                            self._hunt_classes[obj.__name__] = obj
                            security_logger(
                                action="hunt_definition_loaded", hunt_name=obj.__name__
                            ).info(f"Loaded hunt definition: {obj.__name__}")
                except Exception as e:
                    security_logger(
                        action="hunt_definition_load_failed",
                        module=module_name,
                        error=str(e),
                    ).error(f"Failed to load hunt {module_name}: {e}")

    def _sync_hunts_to_db(self):
        """Sync loaded hunt definitions to database"""
        for hunt_name, hunt_class in self._hunt_classes.items():
            hunt_instance = hunt_class()

            # Check if hunt already exists
            existing_hunt = self.db.exec(
                select(Hunt).where(Hunt.name == hunt_name)
            ).first()

            if existing_hunt:
                # Update existing hunt definition
                existing_hunt.display_name = hunt_instance.display_name
                existing_hunt.description = hunt_instance.description
                existing_hunt.category = hunt_instance.category
                existing_hunt.version = hunt_instance.version
                existing_hunt.definition_json = hunt_instance.to_definition()
            else:
                # Create new hunt record
                new_hunt = Hunt(
                    name=hunt_name,
                    display_name=hunt_instance.display_name,
                    description=hunt_instance.description,
                    category=hunt_instance.category,
                    version=hunt_instance.version,
                    definition_json=hunt_instance.to_definition(),
                    is_active=True,
                )
                self.db.add(new_hunt)

        self.db.commit()

    async def list_hunts(self, *, current_user: User) -> List[Hunt]:
        """List all available hunts"""
        hunts = self.db.exec(
            select(Hunt)
            .where(Hunt.is_active == True)
            .order_by(Hunt.category, Hunt.display_name)
        ).all()
        return list(hunts)

    async def get_hunt(self, hunt_id: int, *, current_user: User) -> Optional[Hunt]:
        """Get a specific hunt by ID"""
        return self.db.get(Hunt, hunt_id)

    @no_analyst()
    async def create_execution(
        self,
        hunt_id: int,
        case_id: int,
        initial_parameters: Dict[str, Any],
        *,
        current_user: User,
    ) -> HuntExecution:
        """Create and start a new hunt execution"""
        # Verify hunt exists
        hunt = self.db.get(Hunt, hunt_id)
        if not hunt or not hunt.is_active:
            raise ValueError("Hunt not found or inactive")

        # Check case access
        check_case_access(self.db, case_id, current_user)

        # Validate parameters if hunt class is available
        if hunt.name in self._hunt_classes:
            hunt_instance = self._hunt_classes[hunt.name]()
            validated_params = hunt_instance.validate_parameters(initial_parameters)
        else:
            validated_params = initial_parameters

        # Create execution record
        execution = HuntExecution(
            hunt_id=hunt_id,
            case_id=case_id,
            initial_parameters=validated_params,
            status="pending",
            created_by_id=current_user.id,
        )
        self.db.add(execution)
        self.db.commit()
        self.db.refresh(execution)

        # Start async execution
        asyncio.create_task(self._run_hunt_async(execution.id, current_user.id))

        return execution

    async def _run_hunt_async(self, execution_id: int, user_id: int):
        """Run hunt execution in background"""
        execution = None
        db = None
        try:
            # Get fresh database session for async execution
            from app.core.dependencies import get_db

            db = next(get_db())

            # Get execution and user
            execution = db.get(HuntExecution, execution_id)
            user = db.get(User, user_id)

            if not execution or not user:
                security_logger(
                    action="hunt_execution_not_found",
                    execution_id=execution_id,
                    user_id=user_id,
                ).error(f"Hunt execution {execution_id} or user {user_id} not found")
                return

            # Get hunt definition
            hunt = db.get(Hunt, execution.hunt_id)
            if not hunt:
                security_logger(
                    action="hunt_not_found", hunt_id=execution.hunt_id
                ).error(f"Hunt {execution.hunt_id} not found")
                return

            # Execute hunt
            executor = HuntExecutor(db)
            await executor.execute_hunt(execution, hunt.definition_json, user)

        except Exception as e:
            security_logger(
                action="hunt_execution_failed", execution_id=execution_id, error=str(e)
            ).error(f"Hunt execution {execution_id} failed: {e}")
            # Update execution status
            if execution and db:
                execution.status = "failed"
                execution.completed_at = get_utc_now()
                db.commit()
        finally:
            if db:
                db.close()

    async def get_execution(
        self, execution_id: int, *, current_user: User
    ) -> Optional[HuntExecution]:
        """Get hunt execution details"""
        execution = self.db.get(HuntExecution, execution_id)
        if execution:
            # Check case access
            check_case_access(self.db, execution.case_id, current_user)
        return execution

    async def list_case_executions(
        self, case_id: int, *, current_user: User
    ) -> List[HuntExecution]:
        """List all hunt executions for a case"""
        # Check case access
        check_case_access(self.db, case_id, current_user)

        executions = self.db.exec(
            select(HuntExecution)
            .where(HuntExecution.case_id == case_id)
            .order_by(HuntExecution.created_at.desc())
        ).all()

        return list(executions)

    @no_analyst()
    async def cancel_execution(
        self, execution_id: int, *, current_user: User
    ) -> HuntExecution:
        """Cancel a running hunt execution"""
        execution = self.db.get(HuntExecution, execution_id)
        if not execution:
            raise ValueError("Hunt execution not found")

        # Check case access
        check_case_access(self.db, execution.case_id, current_user)

        # Only running executions can be cancelled
        if execution.status != "running":
            raise ValueError("Only running executions can be cancelled")

        # Cancel execution
        executor = HuntExecutor(self.db)
        await executor.cancel_execution(execution_id)

        self.db.refresh(execution)
        return execution

    async def get_execution_steps(
        self, execution_id: int, *, current_user: User
    ) -> List[HuntStep]:
        """Get all steps for a hunt execution"""
        execution = await self.get_execution(execution_id, current_user=current_user)
        if not execution:
            raise ValueError("Hunt execution not found")

        steps = self.db.exec(
            select(HuntStep)
            .where(HuntStep.execution_id == execution_id)
            .order_by(HuntStep.id)
        ).all()

        return list(steps)
