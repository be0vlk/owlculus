"""
Hunt management and execution service for Owlculus OSINT automated workflows.

This module handles all hunt-related operations including hunt definition loading,
execution management, and asynchronous workflow orchestration. Provides automated
OSINT investigation workflows that chain multiple plugins together with parameter
validation, progress tracking, and real-time status updates.
"""

import asyncio
from collections.abc import Callable
from typing import Any

from sqlmodel import Session, select

from app.core.exceptions import ResourceNotFoundException, ValidationException
from app.core.logging import get_security_logger
from app.core.utils import get_utc_now
from app.core.websocket_manager import websocket_manager
from app.database.models import Hunt, HuntExecution, HuntStep, User
from app.hunts.hunt_executor import HuntExecutor
from app.hunts.hunt_registry import HuntRegistry, shipped_hunt_registry
from app.services.case_access import CaseAccess

security_logger = get_security_logger


class HuntService:
    def __init__(
        self,
        db: Session,
        *,
        registry: HuntRegistry = shipped_hunt_registry,
        executor_factory: Callable[[Session], HuntExecutor] | None = None,
    ):
        self.db = db
        self.access = CaseAccess(db)
        self.registry = registry
        self._executor_factory = executor_factory or (
            lambda session: HuntExecutor(session, websocket_manager)
        )

    async def list_hunts(self, *, current_user: User) -> list[Hunt]:
        hunts = self.db.exec(
            select(Hunt)
            .where(Hunt.is_active == True)
            .order_by(Hunt.category, Hunt.display_name)
        ).all()
        return list(hunts)

    async def get_hunt(self, hunt_id: int, *, current_user: User) -> Hunt:
        hunt = self.db.get(Hunt, hunt_id)
        if hunt is None:
            raise ResourceNotFoundException("Hunt not found")
        return hunt

    async def create_execution(
        self,
        hunt_id: int,
        case_id: int,
        initial_parameters: dict[str, Any],
        *,
        current_user: User,
    ) -> HuntExecution:
        self.access.writable(current_user, case_id)
        hunt = self.db.get(Hunt, hunt_id)
        if not hunt or not hunt.is_active:
            raise ResourceNotFoundException("Hunt not found or inactive")

        hunt_instance = self.registry.create(hunt.name)
        if hunt_instance is not None:
            validated_params = hunt_instance.validate_parameters(initial_parameters)
        else:
            validated_params = initial_parameters

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

        asyncio.create_task(self._run_hunt_async(execution.id, current_user.id))

        return execution

    async def _run_hunt_async(self, execution_id: int, user_id: int):
        execution = None
        db = None
        try:
            from app.core.dependencies import get_db

            db = next(get_db())

            execution = db.get(HuntExecution, execution_id)
            user = db.get(User, user_id)

            if not execution or not user:
                security_logger(
                    action="hunt_execution_not_found",
                    execution_id=execution_id,
                    user_id=user_id,
                ).error(f"Hunt execution {execution_id} or user {user_id} not found")
                return

            hunt = db.get(Hunt, execution.hunt_id)
            if not hunt:
                security_logger(
                    action="hunt_not_found", hunt_id=execution.hunt_id
                ).error(f"Hunt {execution.hunt_id} not found")
                return

            executor = self._executor_factory(db)
            await executor.execute_hunt(execution, hunt.definition_json, user)

        except Exception as e:  # noqa: BLE001 - background jobs must record failure
            security_logger(
                action="hunt_execution_failed", execution_id=execution_id, error=str(e)
            ).error(f"Hunt execution {execution_id} failed: {e}")
            if execution and db:
                execution.status = "failed"
                execution.completed_at = get_utc_now()
                db.commit()
        finally:
            if db:
                db.close()

    async def get_execution(
        self, execution_id: int, *, current_user: User
    ) -> HuntExecution:
        execution = self.db.get(HuntExecution, execution_id)
        if execution is None:
            raise ResourceNotFoundException("Hunt execution not found")
        self.access.readable(current_user, execution.case_id)
        return execution

    async def list_case_executions(
        self, case_id: int, *, current_user: User
    ) -> list[HuntExecution]:
        self.access.readable(current_user, case_id)

        executions = self.db.exec(
            select(HuntExecution)
            .where(HuntExecution.case_id == case_id)
            .order_by(HuntExecution.created_at.desc())
        ).all()

        return list(executions)

    async def cancel_execution(
        self, execution_id: int, *, current_user: User
    ) -> HuntExecution:
        execution = self.db.get(HuntExecution, execution_id)
        if not execution:
            raise ResourceNotFoundException("Hunt execution not found")

        self.access.writable(current_user, execution.case_id)

        # Only running executions can be cancelled
        if execution.status != "running":
            raise ValidationException("Only running executions can be cancelled")

        executor = self._executor_factory(self.db)
        await executor.cancel_execution(execution_id)

        self.db.refresh(execution)
        return execution

    async def get_execution_steps(
        self, execution_id: int, *, current_user: User
    ) -> list[HuntStep]:
        await self.get_execution(execution_id, current_user=current_user)
        steps = self.db.exec(
            select(HuntStep)
            .where(HuntStep.execution_id == execution_id)
            .order_by(HuntStep.id)
        ).all()

        return list(steps)
