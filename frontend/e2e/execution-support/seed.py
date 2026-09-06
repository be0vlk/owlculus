"""Seed only Hunt definitions which cannot be created through product APIs."""

from sqlmodel import Session

from app.database.connection import engine
from app.database.models import Hunt


def step(name, *, barrier=False, mode="success", depends_on=None):
    mapping = {"marker": "initial.marker"}
    if barrier:
        mapping["barrier"] = "initial.barrier"
    return {
        "step_id": name,
        "plugin_name": "BrowserExecutionPlugin",
        "display_name": name,
        "description": name,
        "save_to_case": True,
        "depends_on": depends_on or [],
        "parameter_mapping": mapping,
        "static_parameters": {"mode": mode},
    }


def seed():
    with Session(engine) as db:
        for mode in ("success", "cancel", "error"):
            steps = [step("first", barrier=mode != "cancel", mode=mode)]
            if mode == "cancel":
                steps += [
                    step("held", barrier=True, depends_on=["first"]),
                    step("never", depends_on=["held"]),
                ]
            db.add(
                Hunt(
                    name=f"browser-{mode}",
                    display_name=f"Browser {mode} hunt",
                    description="Disposable browser execution fixture",
                    category="general",
                    definition_json={
                        "initial_parameters": {
                            "marker": {
                                "type": "string",
                                "required": True,
                                "label": "Marker",
                            },
                            "barrier": {
                                "type": "string",
                                "required": True,
                                "label": "Barrier",
                            },
                        },
                        "steps": steps,
                    },
                )
            )
        db.commit()


if __name__ == "__main__":
    seed()
