"""
Hunt executor for orchestrating hunt workflows
"""

from typing import Any

from sqlmodel import Session

from app.core.utils import get_utc_now
from app.database.models import HuntExecution, HuntStep, User
from app.services.plugin_service import PluginService

from .base_hunt import HuntStepDefinition
from .hunt_context import HuntContext
from .hunt_event import HuntEvent, HuntNotifier


class HuntExecutor:
    """Executes hunt workflows with state management"""

    def __init__(
        self,
        db: Session,
        notifier: HuntNotifier,
        *,
        plugin_service: Any | None = None,
    ):
        self.db = db
        self.notifier = notifier
        self.plugin_service = plugin_service or PluginService(db)

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
            self.db.commit()

            # Create HuntStep records for all steps
            step_records = {}
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
            self.db.commit()

            # Execute steps with dependency management
            completed_steps: set[str] = set()
            failed_required_steps: set[str] = set()

            while len(completed_steps) < len(steps):
                # Find executable steps (dependencies satisfied)
                executable = self._find_executable_steps(
                    steps, completed_steps, failed_required_steps, context
                )

                if not executable:
                    # No more steps can execute
                    break

                # Execute steps (could be parallelized in future)
                for step_def in executable:
                    step_record = step_records[step_def.step_id]

                    try:
                        await self._execute_step(
                            step_def,
                            step_record,
                            context,
                            execution,
                            current_user,
                            completed_steps,
                            len(steps),
                        )
                        completed_steps.add(step_def.step_id)

                        # Send step completion notification
                        progress = len(completed_steps) / len(steps)
                        await self.notifier.broadcast(
                            HuntEvent.step_complete(
                                execution_id, step_def.step_id, progress
                            )
                        )
                    # Plugin adapters can fail with provider-specific exceptions.
                    except Exception as e:  # noqa: BLE001
                        if not step_def.optional:
                            failed_required_steps.add(step_def.step_id)
                        context.mark_step_failed(step_def.step_id)
                        step_record.status = "failed"
                        step_record.error_details = str(e)
                        step_record.completed_at = get_utc_now()
                        self.db.commit()

                        # Send step failure notification
                        progress = len(completed_steps) / len(steps)
                        await self.notifier.broadcast(
                            HuntEvent.step_failed(
                                execution_id, step_def.step_id, progress
                            )
                        )

                # Update progress
                execution.progress = len(completed_steps) / len(steps)
                self.db.commit()

                # Send WebSocket notification
                await self.notifier.broadcast(
                    HuntEvent.progress(execution_id, execution.progress)
                )

            # Mark skipped steps
            for step_def in steps:
                if (
                    step_def.step_id not in completed_steps
                    and step_def.step_id not in failed_required_steps
                ):
                    context.mark_step_skipped(step_def.step_id)
                    step_record = step_records[step_def.step_id]
                    step_record.status = "skipped"
                    step_record.completed_at = get_utc_now()

            # Complete execution
            execution.status = "completed" if not failed_required_steps else "partial"
            execution.completed_at = get_utc_now()
            execution.context_data = context.to_dict()
            self.db.commit()

            # Send completion notification
            await self.notifier.broadcast(HuntEvent.complete(execution_id))

        except Exception as e:
            # Handle catastrophic failure
            execution.status = "failed"
            execution.completed_at = get_utc_now()
            self.db.commit()

            # Send error notification
            await self.notifier.broadcast(HuntEvent.error(execution_id, str(e)))
            raise

    def _find_executable_steps(
        self,
        steps: list[HuntStepDefinition],
        completed_steps: set[str],
        failed_required_steps: set[str],
        context: HuntContext,
    ) -> list[HuntStepDefinition]:
        """Find steps that can be executed based on dependencies"""
        executable = []

        for step in steps:
            if step.step_id in completed_steps or step.step_id in failed_required_steps:
                continue

            # Check if dependencies are satisfied
            deps_satisfied = all(dep in completed_steps for dep in step.depends_on)

            # Check if any required dependency failed
            deps_failed = any(dep in failed_required_steps for dep in step.depends_on)

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
        self.db.commit()

        # Send notification that step is starting
        # Include step_id so frontend knows which step is running
        progress = len(completed_steps) / total_steps
        if execution.id is None:
            raise ValueError("Hunt execution must be stored before a step can run")
        await self.notifier.broadcast(
            HuntEvent.progress(execution.id, progress, step_def.step_id)
        )

        # Execute plugin
        plugin = self.plugin_service.get_plugin(step_def.plugin_name)
        plugin._current_user = current_user

        # Collect results
        results = []
        async for result in plugin.execute_with_evidence_collection(parameters):
            if result.get("type") == "data":
                results.append(result.get("data", {}))

        # Store output in context
        output = {
            "results": results,
            "result_count": len(results),
            "plugin": step_def.plugin_name,
        }
        context.set_step_output(step_def.step_id, output)

        # Update step record
        step_record.status = "completed"
        step_record.output = output
        step_record.completed_at = get_utc_now()
        self.db.commit()

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

            self.db.commit()
