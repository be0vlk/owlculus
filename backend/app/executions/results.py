"""Ordered hunt chunks and compatibility materialization for existing consumers."""

from sqlmodel import Session, col, select

from app.database.models import HuntStep, HuntStepResult


def step_results(db: Session, step: HuntStep, cursor: int = 0, limit: int = 50) -> dict:
    rows = db.exec(
        select(HuntStepResult)
        .where(HuntStepResult.step_id == step.id, HuntStepResult.sequence > cursor)
        .order_by(col(HuntStepResult.sequence))
        .limit(limit + 1)
    ).all()
    page = rows[:limit]
    return {
        "items": [row.payload for row in page],
        "cursor": page[-1].sequence if page else cursor,
        "next_cursor": page[-1].sequence if len(rows) > limit else None,
    }


def step_output(db: Session, step: HuntStep) -> dict | None:
    if step.output is not None:
        return step.output
    # Incremental chunks survive a worker dying before its final StepOutput commit.
    results, errors = [], []
    cursor = 0
    while True:
        page = step_results(db, step, cursor, 200)
        for event in page["items"]:
            if event["type"] == "data":
                results.append(event["data"])
            elif event["type"] == "error":
                errors.append(event["data"])
        if page["next_cursor"] is None:
            break
        cursor = page["next_cursor"]
    if not results and not errors:
        return None
    return {
        "results": results,
        "result_count": len(results),
        "plugin": step.plugin_name,
        "errors": errors,
        "partial": True,
    }
