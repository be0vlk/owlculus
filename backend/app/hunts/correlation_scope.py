"""Case provenance inherited by Hunt steps that consume correlation output."""

from sqlmodel import Session, select

from app.database.models import HuntExecution, HuntStep, User
from app.executions.correlation_visibility import CORRELATION_PLUGIN
from app.hunts.step_input_resolver import parse_input_expression
from app.services.case_access import CaseAccess


class HuntCorrelationScope:
    """Use the accepted dependency graph; unverified legacy copies fail closed."""

    def __init__(self, db: Session, execution: HuntExecution):
        self.source_case_id = execution.case_id
        self.steps = {
            step.step_id: step
            for step in db.exec(
                select(HuntStep).where(HuntStep.execution_id == execution.id)
            )
        }
        self.outputs = (execution.context_data or {}).get("step_outputs", {})
        self.roots = {
            key
            for key, step in self.steps.items()
            if step.plugin_name == CORRELATION_PLUGIN
        }
        self.roots.update(
            key
            for key, output in self.outputs.items()
            if isinstance(output, dict) and output.get("plugin") == CORRELATION_PLUGIN
        )
        snapshot = execution.definition_snapshot
        self.dependencies: dict[str, set[str]] | None = None
        if snapshot is not None:
            try:
                self.dependencies = {
                    step["step_id"]: {
                        parse_input_expression(value).source
                        for value in step.get("parameter_mapping", {}).values()
                        if parse_input_expression(value).source != "initial"
                    }
                    for step in snapshot["steps"]
                }
                self.roots.update(
                    step["step_id"]
                    for step in snapshot["steps"]
                    if step["plugin_name"] == CORRELATION_PLUGIN
                )
            except (KeyError, TypeError, ValueError):
                self.dependencies = None

    def inherited(self, step_id: str) -> tuple[int, ...] | None:
        """None: unrelated; empty: unverified; otherwise every required Case ID."""
        if not self.roots or step_id in self.roots:
            return None
        if self.dependencies is None or step_id not in self.dependencies:
            roots = self.roots
        else:
            pending, seen, roots = [step_id], set(), set()
            while pending:
                current = pending.pop()
                if current in seen:
                    continue
                seen.add(current)
                if current in self.roots:
                    roots.add(current)
                elif current not in self.dependencies:
                    roots.update(self.roots)
                else:
                    pending.extend(self.dependencies[current])
        if not roots:
            return None
        case_ids = {self.source_case_id}
        for root in roots:
            step = self.steps.get(root)
            output = (
                step.output
                if step and step.output is not None
                else self.outputs.get(root)
            )
            if (
                not isinstance(output, dict)
                or not isinstance(output.get("results"), list)
                or output.get("errors")
            ):
                return ()
            for group in output["results"]:
                if (
                    not isinstance(group, dict)
                    or group.get("case_id") != self.source_case_id
                    or not isinstance(group.get("matches"), list)
                ):
                    return ()
                for match in group["matches"]:
                    if (
                        not isinstance(match, dict)
                        or type(match.get("case_id")) is not int
                    ):
                        return ()
                    case_ids.add(match["case_id"])
        return tuple(sorted(case_ids))

    def can_read(self, db: Session, user: User, step_id: str) -> bool:
        scope = self.inherited(step_id)
        return (
            scope is None
            or CaseAccess.is_admin(user)
            or bool(scope and set(scope) <= set(CaseAccess(db).readable_case_ids(user)))
        )
