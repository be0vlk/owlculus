"""Hunt executor contracts at the runner and database seams."""

from collections.abc import AsyncGenerator
from contextlib import nullcontext
from typing import Any, ClassVar

import pytest
from sqlmodel import Session, select

from app.database.models import Case, Hunt, HuntExecution, HuntStep, User
from app.hunts.hunt_executor import HuntExecutor
from app.plugins.base_plugin import BasePlugin, PluginRun, ResultEvent
from app.plugins.plugin_context import ProductionPluginRunAdapter
from app.plugins.plugin_registry import PluginRegistry
from app.plugins.plugin_runner import PluginRunner
from app.services.api_key_vault import ConfigurationApiKeyVault


class TrivialPlugin(BasePlugin):
    async def run(
        self, params: dict[str, Any], ctx: PluginRun
    ) -> AsyncGenerator[ResultEvent, None]:
        yield self.data({"result": "ok"})


class FirstPlugin(BasePlugin):
    async def run(
        self, params: dict[str, Any], ctx: PluginRun
    ) -> AsyncGenerator[ResultEvent, None]:
        yield self.data({"address": "192.0.2.44"})


class SecondPlugin(BasePlugin):
    calls: ClassVar[list[dict[str, Any]]] = []

    async def run(
        self, params: dict[str, Any], ctx: PluginRun
    ) -> AsyncGenerator[ResultEvent, None]:
        self.calls.append(params.copy())
        yield self.data({"received": params["query"]})


def step(
    step_id: str,
    *,
    plugin_name: str = "TrivialPlugin",
    depends_on: list[str] | None = None,
    parameter_mapping: dict[str, str] | None = None,
    optional: bool = False,
) -> dict[str, Any]:
    return {
        "step_id": step_id,
        "plugin_name": plugin_name,
        "display_name": step_id,
        "description": f"Run {step_id}",
        "depends_on": depends_on or [],
        "parameter_mapping": parameter_mapping or {},
        "static_parameters": {},
        "save_to_case": False,
        "optional": optional,
    }


def stored_execution(session: Session, user: User) -> HuntExecution:
    case = Case(case_number="CASE-HUNT", title="Runner contract")
    hunt = Hunt(
        name="runner-contract",
        display_name="Runner contract",
        description="Exercise the plugin runner.",
        category="test",
        definition_json={"steps": []},
    )
    session.add_all([case, hunt])
    session.commit()
    execution = HuntExecution(
        hunt_id=hunt.id,
        case_id=case.id,
        initial_parameters={},
        created_by_id=user.id,
    )
    session.add(execution)
    session.commit()
    session.refresh(execution)
    return execution


def executor(session: Session, plugin_classes: list[type[BasePlugin]]) -> HuntExecutor:
    return HuntExecutor(
        session,
        plugin_runner=PluginRunner(PluginRegistry.from_classes(plugin_classes)),
        run_adapter=ProductionPluginRunAdapter(
            lambda: nullcontext(session), ConfigurationApiKeyVault
        ),
        before_step=lambda: None,
        sanitize=lambda value: value,
    )


@pytest.mark.asyncio
async def test_executor_persists_declared_step_output_and_progress(
    session: Session, test_user: User
):
    execution = stored_execution(session, test_user)

    await executor(session, [TrivialPlugin]).execute_hunt(
        execution, {"steps": [step("lookup")]}, test_user
    )

    persisted = session.exec(
        select(HuntStep).where(HuntStep.execution_id == execution.id)
    ).one()
    assert persisted.status == "completed"
    assert persisted.output == {
        "results": [{"result": "ok"}],
        "result_count": 1,
        "plugin": "TrivialPlugin",
        "errors": [],
    }
    assert execution.status == "completed"
    assert execution.progress == 1.0
    assert set(execution.context_data) == {
        "initial_parameters",
        "step_outputs",
        "failed_steps",
        "skipped_steps",
    }


@pytest.mark.asyncio
async def test_throwing_plugin_is_a_persisted_failed_step(
    session: Session, test_user: User, throwing_plugin_class
):
    execution = stored_execution(session, test_user)

    await executor(session, [throwing_plugin_class]).execute_hunt(
        execution,
        {"steps": [step("lookup", plugin_name="ThrowingPlugin")]},
        test_user,
    )

    persisted = session.exec(
        select(HuntStep).where(HuntStep.execution_id == execution.id)
    ).one()
    assert persisted.status == "failed"
    assert persisted.error_details == "Plugin execution error: provider exploded"
    assert persisted.output == {
        "results": [{"partial": True}],
        "result_count": 1,
        "plugin": "ThrowingPlugin",
        "errors": [{"message": "Plugin execution error: provider exploded"}],
    }
    assert execution.status == "partial"
    assert execution.context_data["failed_steps"] == ["lookup"]


@pytest.mark.asyncio
async def test_optional_plugin_failure_is_terminal_and_hunt_completes(
    session: Session, test_user: User, throwing_plugin_class
):
    execution = stored_execution(session, test_user)

    await executor(session, [throwing_plugin_class, TrivialPlugin]).execute_hunt(
        execution,
        {
            "steps": [
                step("lookup", plugin_name="ThrowingPlugin", optional=True),
                step("dependent", depends_on=["lookup"]),
                step("independent"),
            ]
        },
        test_user,
    )

    assert execution.status == "completed"
    assert execution.progress == 1.0
    statuses = {
        record.step_id: record.status
        for record in session.exec(
            select(HuntStep).where(HuntStep.execution_id == execution.id)
        )
    }
    assert statuses == {
        "lookup": "failed",
        "dependent": "skipped",
        "independent": "completed",
    }
    assert execution.context_data["skipped_steps"] == ["dependent"]


@pytest.mark.asyncio
async def test_executor_resolves_a_prior_step_result_for_the_next_plugin(
    session: Session, test_user: User
):
    SecondPlugin.calls = []
    execution = stored_execution(session, test_user)

    await executor(session, [FirstPlugin, SecondPlugin]).execute_hunt(
        execution,
        {
            "steps": [
                step("first", plugin_name="FirstPlugin"),
                step(
                    "second",
                    plugin_name="SecondPlugin",
                    depends_on=["first"],
                    parameter_mapping={"query": "first.results[0].address"},
                ),
            ]
        },
        test_user,
    )

    assert SecondPlugin.calls == [
        {"query": "192.0.2.44", "case_id": execution.case_id, "save_to_case": False}
    ]
