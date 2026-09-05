"""
Hunt executor for orchestrating hunt workflows
"""

from collections.abc import Callable
from contextlib import nullcontext
from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any

from sqlmodel import Session

from app.core.utils import get_utc_now
from app.database.db_utils import transaction
from app.database.models import HuntExecution, HuntStep, HuntStepResult, User
from app.executions.ownership import OwnershipLost
from app.plugins.plugin_context import ProductionPluginRunAdapter
from app.plugins.plugin_registry import get_shipped_plugin_registry
from app.plugins.plugin_runner import PluginRunner
from app.services.api_key_vault import ConfigurationApiKeyVault

from .base_hunt import HuntStepDefinition
from .hunt_context import HuntContext
from .hunt_event import HuntEvent, HuntNotifier
from .step_output import StepOutput


@dataclass
class HuntStepState:
    """Track which hunt steps have reached a terminal state."""

    completed: set[str] = field(default_factory=set)
    failed: set[str] = field(default_factory=set)
    failed_required: set[str] = field(default_factory=set)

    def record_failure(self, step: HuntStepDefinition) -> None:
        self.failed.add(step.step_id)
        if not step.optional:
            self.failed_required.add(step.step_id)

    def is_terminal(self, step_id: str) -> bool:
        return step_id in self.completed or step_id in self.failed

    def dependencies_completed(self, step: HuntStepDefinition) -> bool:
        return all(dependency in self.completed for dependency in step.depends_on)

    def has_failed_required_dependency(self, step: HuntStepDefinition) -> bool:
        return any(dependency in self.failed_required for dependency in step.depends_on)


class HuntExecutor:
    """Executes hunt workflows with state management"""

    def __init__(
        self,
        db: Session,
        notifier: HuntNotifier,
        *,
        plugin_runner: PluginRunner | None = None,
        run_adapter: ProductionPluginRunAdapter | None = None,
        before_step: Callable[[], None] | None = None,
        sanitize: Callable[[Any], Any] = lambda value: value,
    ):
        self.before_step = before_step
        self.sanitize = sanitize
        self.db = db
        self.notifier = notifier
        self.plugin_runner = plugin_runner or PluginRunner(
            get_shipped_plugin_registry()
        )
        self.run_adapter = run_adapter or ProductionPluginRunAdapter(
            lambda: nullcontext(self.db), ConfigurationApiKeyVault
        )

    async def execute_hunt(
        self, execution: HuntExecution, hunt_definition: dict, current_user: User
    ):
        """
        Execute a hunt workflow

        Args:
            execution: The HuntExecution database record
            hunt_definition: The hunt definition JSON
            current_user: The user executing the hunt
        """
        context = HuntContext(execution.initial_parameters)
        steps = [HuntStepDefinition(**step) for step in hunt_definition["steps"]]
        if execution.id is None:
            raise ValueError("Hunt execution must be stored before it can run")
        execution_id = execution.id

        try:
            # Update execution status
            execution.status = "running"
            execution.started_at = get_utc_now()
            with transaction(self.db):
                self.db.add(execution)

            # Create HuntStep records for all steps
            step_records = {}
            with transaction(self.db):
                for step_def in steps:
                    step_record = HuntStep(
                        execution_id=execution.id,
                        step_id=step_def.step_id,
                        plugin_name=step_def.plugin_name,
                        status="pending",
                        parameters={},
                    )
                    self.db.add(step_record)
                    step_records[step_def.step_id] = step_record

            # Execute steps with dependency management
            step_state = HuntStepState()

            while len(step_state.completed) < len(steps):
                # Find executable steps (dependencies satisfied)
                executable = self._find_executable_steps(
                    steps,
                    step_state,
                    context,
                )

                if not executable:
                    # No more steps can execute
                    break

                # Execute steps (could be parallelized in future)
                for step_def in executable:
                    step_record = step_records[step_def.step_id]

                    if self.before_step:
                        self.before_step()
                    try:
                        await self._execute_step(
                            step_def,
                            step_record,
                            context,
                            execution,
                            current_user,
                            step_state.completed,
                            len(steps),
                        )
                        if step_record.status == "failed":
                            step_state.record_failure(step_def)
                            context.mark_step_failed(step_def.step_id)
                            progress = len(step_state.completed) / len(steps)
                            await self.notifier.broadcast(
                                HuntEvent.step_failed(
                                    execution_id, step_def.step_id, progress
                                )
                            )
                            continue
                        step_state.completed.add(step_def.step_id)

                        # Send step completion notification
                        progress = len(step_state.completed) / len(steps)
                        await self.notifier.broadcast(
                            HuntEvent.step_complete(
                                execution_id, step_def.step_id, progress
                            )
                        )
                    # Plugin adapters can fail with provider-specific exceptions.
                    except OwnershipLost:
                        raise
                    except Exception as e:  # noqa: BLE001
                        step_state.record_failure(step_def)
                        context.mark_step_failed(step_def.step_id)
                        step_record.status = "failed"
                        step_record.error_details = self.sanitize(str(e))
                        step_record.completed_at = get_utc_now()
                        with transaction(self.db):
                            self.db.add(step_record)

                        # Send step failure notification
                        progress = len(step_state.completed) / len(steps)
                        await self.notifier.broadcast(
                            HuntEvent.step_failed(
                                execution_id, step_def.step_id, progress
                            )
                        )

                # Update progress
                execution.progress = len(step_state.completed) / len(steps)
                with transaction(self.db):
                    self.db.add(execution)

                # Send WebSocket notification
                await self.notifier.broadcast(
                    HuntEvent.progress(execution_id, execution.progress)
                )

            # Mark skipped steps
            for step_def in steps:
                if not step_state.is_terminal(step_def.step_id):
                    context.mark_step_skipped(step_def.step_id)
                    step_record = step_records[step_def.step_id]
                    step_record.status = "skipped"
                    step_record.completed_at = get_utc_now()

            # Complete execution
            execution.status = (
                "completed" if not step_state.failed_required else "partial"
            )
            execution.progress = 1.0
            execution.completed_at = get_utc_now()
            execution.context_data = deepcopy(context.to_dict())
            with transaction(self.db):
                self.db.add(execution)

            # Send completion notification
            await self.notifier.broadcast(HuntEvent.complete(execution_id))

        except OwnershipLost:
            raise
        except Exception as e:
            # Handle catastrophic failure
            execution.status = "failed"
            execution.error = {
                "code": "hunt_error",
                "message": "Hunt could not finish; check initiating user access and worker configuration",
            }
            execution.context_data = deepcopy(context.to_dict())
            execution.completed_at = get_utc_now()
            with transaction(self.db):
                self.db.add(execution)

            # Send error notification
            await self.notifier.broadcast(
                HuntEvent.error(execution_id, self.sanitize(str(e)))
            )
            raise

    def _find_executable_steps(
        self,
        steps: list[HuntStepDefinition],
        step_state: HuntStepState,
        context: HuntContext,
    ) -> list[HuntStepDefinition]:
        """Find steps that can be executed based on dependencies"""
        executable = []

        for step in steps:
            if step_state.is_terminal(step.step_id):
                continue

            deps_satisfied = step_state.dependencies_completed(step)
            deps_failed = step_state.has_failed_required_dependency(step)

            if deps_satisfied and not deps_failed:
                executable.append(step)
            elif deps_failed:
                # Skip this step since a required dependency failed
                context.mark_step_skipped(step.step_id)

        return executable

    async def _execute_step(
        self,
        step_def: HuntStepDefinition,
        step_record: HuntStep,
        context: HuntContext,
        execution: HuntExecution,
        current_user: User,
        completed_steps: set,
        total_steps: int,
    ):
        """Execute a single hunt step"""
        # Update step status
        step_record.status = "running"
        step_record.started_at = get_utc_now()

        # Resolve parameters
        parameters = context.resolve_parameters(step_def)
        parameters["case_id"] = execution.case_id
        parameters["save_to_case"] = step_def.save_to_case

        step_record.parameters = parameters
        with transaction(self.db):
            self.db.add(step_record)

        # Send notification that step is starting
        # Include step_id so frontend knows which step is running
        progress = len(completed_steps) / total_steps
        if execution.id is None:
            raise ValueError("Hunt execution must be stored before a step can run")
        await self.notifier.broadcast(
            HuntEvent.progress(execution.id, progress, step_def.step_id)
        )

        # Bounded per-step materialization preserves StepOutput and parameter mapping.
        results = []
        errors = []
        sequence = 0
        with self.run_adapter.open(
            user=current_user,
            case_id=execution.case_id,
            save_to_case=step_def.save_to_case,
            operation_id=step_def.step_id,
        ) as run:
            async for result in self.plugin_runner.run(
                step_def.plugin_name, parameters, run
            ):
                sequence += 1
                # Persist every event independently before asking the provider for more.
                with transaction(self.db):
                    self.db.add(
                        HuntStepResult(
                            step_id=step_record.id,
                            sequence=sequence,
                            payload=self.sanitize(result.to_wire()),
                        )
                    )
                if result.kind == "data":
                    results.append(self.sanitize(result.payload))
                elif result.kind == "error":
                    errors.append(self.sanitize(result.payload))

        # Store output in context
        output: StepOutput = {
            "results": results,
            "result_count": len(results),
            "plugin": step_def.plugin_name,
            "errors": errors,
        }
        if errors:
            step_record.error_details = "; ".join(
                error.get("message", "Plugin error") for error in errors
            )
        context.set_step_output(step_def.step_id, output)

        # Update step record
        step_record.status = "failed" if errors else "completed"
        step_record.output = dict(output)
        step_record.completed_at = get_utc_now()
        execution.context_data = deepcopy(context.to_dict())
        with transaction(self.db):
            self.db.add(step_record)
            self.db.add(execution)

    async def cancel_execution(self, execution_id: int):
        """Cancel a running hunt execution"""
        execution = self.db.get(HuntExecution, execution_id)
        if execution and execution.status == "running":
            execution.status = "cancelled"
            execution.completed_at = get_utc_now()

            # Mark pending steps as cancelled
            for step in execution.steps:
                if step.status == "pending":
                    step.status = "cancelled"
                    step.completed_at = get_utc_now()

            with transaction(self.db):
                self.db.add(execution)
