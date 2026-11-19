"""
Hunt executor for orchestrating hunt workflows
"""

from collections.abc import Callable
from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any, TypedDict

from sqlmodel import Session, select

from app.core.utils import get_utc_now
from app.database.db_utils import transaction
from app.database.models import HuntExecution, HuntStep, HuntStepResult, User
from app.executions.ownership import OwnershipLost
from app.plugins.plugin_context import ProductionPluginRunAdapter
from app.plugins.plugin_runner import PluginRunner
from app.plugins.plugin_types import Payload

from .base_hunt import HuntStepDefinition
from .hunt_context import HuntContext


class StepOutput(TypedDict):
    """Persisted output of one hunt step, read by later steps' parameter mapping."""

    results: list[Payload]
    result_count: int
    plugin: str
    errors: list[Payload]


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


class HuntExecutor:
    """Executes hunt workflows with state management"""

    def __init__(
        self,
        db: Session,
        *,
        plugin_runner: PluginRunner,
        run_adapter: ProductionPluginRunAdapter,
        before_step: Callable[[], None],
        sanitize: Callable[[Any], Any],
    ):
        self.before_step = before_step
        self.sanitize = sanitize
        self.db = db
        self.plugin_runner = plugin_runner
        self.run_adapter = run_adapter

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
            execution.status = "running"
            execution.started_at = execution.started_at or get_utc_now()
            with transaction(self.db):
                self.db.add(execution)

            # Completed outputs are the durable boundary, including optional errors.
            step_records = {
                record.step_id: record
                for record in self.db.exec(
                    select(HuntStep).where(HuntStep.execution_id == execution_id)
                ).all()
            }
            step_state = HuntStepState()
            for step_def in steps:
                record = step_records.get(step_def.step_id)
                if record and record.status in {"completed", "failed"}:
                    if record.output is not None:
                        context.set_step_output(
                            step_def.step_id, deepcopy(record.output)
                        )
                    if record.status == "completed":
                        step_state.completed.add(step_def.step_id)
                    else:
                        step_state.record_failure(step_def)
                        context.mark_step_failed(step_def.step_id)
                elif record and record.status != "pending":
                    raise ValueError("Hunt cannot resume an unfinished operation")
            with transaction(self.db):
                for step_def in steps:
                    if step_def.step_id in step_records:
                        continue
                    step_record = HuntStep(
                        execution_id=execution.id,
                        step_id=step_def.step_id,
                        plugin_name=step_def.plugin_name,
                        status="pending",
                        parameters={},
                    )
                    self.db.add(step_record)
                    step_records[step_def.step_id] = step_record

            while len(step_state.completed) < len(steps):
                executable = [
                    step
                    for step in steps
                    if not step_state.is_terminal(step.step_id)
                    and all(dep in step_state.completed for dep in step.depends_on)
                ]

                if not executable:
                    break

                # Could be parallelized in future
                for step_def in executable:
                    step_record = step_records[step_def.step_id]

                    self.before_step()
                    try:
                        await self._execute_step(
                            step_def, step_record, context, execution, current_user
                        )
                        if step_record.status == "failed":
                            step_state.record_failure(step_def)
                            context.mark_step_failed(step_def.step_id)
                            continue
                        step_state.completed.add(step_def.step_id)
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

                execution.progress = len(step_state.completed) / len(steps)
                with transaction(self.db):
                    self.db.add(execution)

            for step_def in steps:
                if not step_state.is_terminal(step_def.step_id):
                    context.mark_step_skipped(step_def.step_id)
                    step_record = step_records[step_def.step_id]
                    step_record.status = "skipped"
                    step_record.completed_at = get_utc_now()

            execution.status = (
                "completed" if not step_state.failed_required else "partial"
            )
            execution.progress = 1.0
            execution.completed_at = get_utc_now()
            execution.context_data = deepcopy(context.to_dict())
            with transaction(self.db):
                self.db.add(execution)

        except OwnershipLost:
            raise
        except Exception:
            execution.status = "failed"
            execution.error = {
                "code": "hunt_error",
                "message": "Hunt could not finish; check initiating user access and worker configuration",
            }
            execution.context_data = deepcopy(context.to_dict())
            execution.completed_at = get_utc_now()
            with transaction(self.db):
                self.db.add(execution)
            raise

    async def _execute_step(
        self,
        step_def: HuntStepDefinition,
        step_record: HuntStep,
        context: HuntContext,
        execution: HuntExecution,
        current_user: User,
    ):
        """Execute a single hunt step"""
        step_record.status = "running"
        step_record.started_at = get_utc_now()

        parameters = context.resolve_parameters(step_def)
        parameters["case_id"] = execution.case_id
        parameters["save_to_case"] = step_def.save_to_case

        step_record.parameters = parameters
        with transaction(self.db):
            self.db.add(step_record)

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

        step_record.status = "failed" if errors else "completed"
        step_record.output = dict(output)
        step_record.completed_at = get_utc_now()
        execution.context_data = deepcopy(context.to_dict())
        with transaction(self.db):
            self.db.add(step_record)
            self.db.add(execution)
