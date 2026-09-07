"""Recognize historical reports without guessing their related Case identities."""

from pathlib import PurePosixPath

from sqlmodel import Session, select

from app.database.models import (
    CorrelationEvidence,
    Evidence,
    ExecutionControl,
    ExecutionEffect,
    HuntExecution,
    HuntStep,
    PluginExecution,
    PluginExecutionResult,
)


def report_provenance(db: Session, evidence: Evidence) -> CorrelationEvidence | None:
    """Return stored provenance or a conservative legacy classification.

    The reserved artifact path must match an execution receipt exactly. Names
    only recognize reports requiring protection; they never grant Case access.
    Read-time classification does not mutate historical evidence or receipts.
    """
    stored = db.get(CorrelationEvidence, evidence.id)
    if stored is not None or evidence.is_folder:
        return stored
    path = PurePosixPath(evidence.content)
    receipt = None
    if path.parent == PurePosixPath(str(evidence.case_id), ".execution-artifacts"):
        receipt = db.exec(
            select(ExecutionEffect).where(ExecutionEffect.artifact_id == path.stem)
        ).first()
    recognized = (
        "correlation scan" in evidence.title.casefold()
        or "correlationscan" in path.name.casefold()
        or "correlation scan" in (evidence.description or "").casefold()
    )
    payloads = None
    if (
        receipt is not None
        and evidence.content
        == f"{evidence.case_id}/.execution-artifacts/{receipt.artifact_id}.txt"
    ):
        control = db.get(ExecutionControl, receipt.control_id)
        if control is not None and control.plugin_execution_id is not None:
            execution = db.get(PluginExecution, control.plugin_execution_id)
            if execution is not None and execution.plugin_name == "CorrelationScan":
                recognized = True
                if (
                    execution.case_id == evidence.case_id
                    and execution.status == "completed"
                    and execution.save_to_case
                ):
                    payloads = [
                        row.payload["data"]
                        for row in db.exec(
                            select(PluginExecutionResult).where(
                                PluginExecutionResult.execution_id == execution.id
                            )
                        )
                        if row.payload.get("type") == "data"
                    ]
        elif control is not None and control.hunt_execution_id is not None:
            hunt_execution = db.get(HuntExecution, control.hunt_execution_id)
            operation, separator, index = receipt.operation_id.rpartition(":evidence:")
            if separator and index.isdigit():
                step = db.exec(
                    select(HuntStep).where(
                        HuntStep.execution_id == control.hunt_execution_id,
                        HuntStep.step_id == operation,
                    )
                ).first()
                if step is not None and hunt_execution is not None:
                    from app.hunts.correlation_scope import HuntCorrelationScope

                    inherited = HuntCorrelationScope(db, hunt_execution).inherited(
                        step.step_id
                    )
                    if inherited is not None:
                        return CorrelationEvidence(
                            evidence_id=evidence.id, case_ids=list(inherited) or None
                        )
                if step is not None and step.plugin_name == "CorrelationScan":
                    recognized = True
                    if (
                        hunt_execution is not None
                        and hunt_execution.case_id == evidence.case_id
                        and step.status == "completed"
                        and step.output
                    ):
                        payloads = step.output.get("results")
    if not recognized:
        return None
    case_ids = _verified_case_ids(payloads, evidence.case_id)
    return CorrelationEvidence(evidence_id=evidence.id, case_ids=case_ids)


def _verified_case_ids(payloads, source_case_id: int) -> list[int] | None:
    if not isinstance(payloads, list) or not payloads:
        return None
    case_ids = {source_case_id}
    for group in payloads:
        if (
            not isinstance(group, dict)
            or group.get("case_id") != source_case_id
            or not isinstance(group.get("matches"), list)
            or not group["matches"]
        ):
            return None
        for match in group["matches"]:
            if (
                not isinstance(match, dict)
                or type(match.get("case_id")) is not int
                or match["case_id"] <= 0
            ):
                return None
            case_ids.add(match["case_id"])
    return sorted(case_ids)
