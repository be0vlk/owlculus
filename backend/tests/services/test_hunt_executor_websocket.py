"""Hunt executor event and input-flow tests."""

import asyncio
from contextlib import contextmanager
from unittest.mock import MagicMock

import pytest

from app.database.models import HuntExecution, User
from app.hunts.definitions.domain_hunt import DomainHunt
from app.hunts.hunt_event import HuntEvent
from app.hunts.hunt_executor import HuntExecutor
from app.plugins.base_plugin import ResultEvent


class EventRecorder:
    def __init__(self):
        self.events: list[HuntEvent] = []

    async def broadcast(self, event: HuntEvent) -> None:
        self.events.append(event)


class RecordingPlugin:
    def __init__(self, result, calls):
        self._result = result
        self._calls = calls
        self._current_user = None

    async def execute_with_evidence_collection(self, parameters, ctx):
        self._calls.append(parameters.copy())
        if isinstance(self._result, Exception):
            raise self._result
        if isinstance(self._result, list):
            for event in self._result:
                yield event
        else:
            yield ResultEvent.data(self._result)


class PluginCatalogueStub:
    def __init__(self, results):
        self.results = results
        self.calls: dict[str, list[dict]] = {}

    def get_plugin(self, name):
        calls = self.calls.setdefault(name, [])
        return RecordingPlugin(self.results.get(name, {}), calls)

    @contextmanager
    def open_run(self, parameters, *, current_user):
        yield object()


def execution():
    return HuntExecution(
        id=1,
        hunt_id=1,
        case_id=1,
        status="running",
        progress=0.0,
        initial_parameters={},
        created_by_id=1,
    )


def user():
    return User(
        id=1,
        username="test",
        email="test@test.com",
        password_hash="hash",
        role="Admin",
    )


def hunt_definition(*steps):
    return {"steps": list(steps)}


def step(step_id, *, depends_on=None, plugin_name="test_plugin", optional=False):
    return {
        "step_id": step_id,
        "plugin_name": plugin_name,
        "display_name": step_id,
        "description": f"Run {step_id}",
        "depends_on": depends_on or [],
        "parameter_mapping": {},
        "static_parameters": {},
        "save_to_case": False,
        "optional": optional,
    }


@pytest.mark.asyncio
async def test_executor_records_progress_and_completion_events(db_session):
    recorder = EventRecorder()
    plugins = PluginCatalogueStub({"test_plugin": {"result": "ok"}})
    executor = HuntExecutor(db_session, recorder, plugin_service=plugins)
    db_session.add = MagicMock()
    db_session.commit = MagicMock()

    await executor.execute_hunt(
        execution(),
        hunt_definition(step("step1"), step("step2", depends_on=["step1"])),
        user(),
    )

    assert recorder.events == [
        HuntEvent.progress(1, 0.0, "step1"),
        HuntEvent.step_complete(1, "step1", 0.5),
        HuntEvent.progress(1, 0.5),
        HuntEvent.progress(1, 0.5, "step2"),
        HuntEvent.step_complete(1, "step2", 1.0),
        HuntEvent.progress(1, 1.0),
        HuntEvent.complete(1),
    ]


@pytest.mark.asyncio
async def test_executor_records_required_step_failure(db_session):
    recorder = EventRecorder()
    plugins = PluginCatalogueStub({"failing_plugin": RuntimeError("plugin failed")})
    executor = HuntExecutor(db_session, recorder, plugin_service=plugins)
    db_session.add = MagicMock()
    db_session.commit = MagicMock()
    run = execution()

    await executor.execute_hunt(
        run,
        hunt_definition(step("step1", plugin_name="failing_plugin")),
        user(),
    )

    assert recorder.events == [
        HuntEvent.progress(1, 0.0, "step1"),
        HuntEvent.step_failed(1, "step1", 0.0),
        HuntEvent.progress(1, 0.0),
        HuntEvent.complete(1),
    ]
    assert run.status == "partial"


@pytest.mark.asyncio
async def test_executor_records_plugin_errors_and_fails_an_error_only_step(db_session):
    recorder = EventRecorder()
    plugins = PluginCatalogueStub(
        {"failing_plugin": [ResultEvent.error("provider rejected the request")]}
    )
    executor = HuntExecutor(db_session, recorder, plugin_service=plugins)
    db_session.add = MagicMock()
    db_session.commit = MagicMock()
    run = execution()

    await executor.execute_hunt(
        run,
        hunt_definition(step("step1", plugin_name="failing_plugin")),
        user(),
    )

    step_record = next(
        call.args[0]
        for call in db_session.add.call_args_list
        if getattr(call.args[0], "step_id", None) == "step1"
    )
    assert step_record.error_details == "provider rejected the request"
    assert recorder.events[-2:] == [HuntEvent.progress(1, 0.0), HuntEvent.complete(1)]
    assert run.status == "partial"


@pytest.mark.asyncio
async def test_executor_treats_an_optional_failure_as_terminal(db_session):
    recorder = EventRecorder()
    plugins = PluginCatalogueStub({"failing_plugin": RuntimeError("plugin failed")})
    executor = HuntExecutor(db_session, recorder, plugin_service=plugins)
    db_session.add = MagicMock()
    db_session.commit = MagicMock()
    run = execution()

    await asyncio.wait_for(
        executor.execute_hunt(
            run,
            hunt_definition(step("step1", plugin_name="failing_plugin", optional=True)),
            user(),
        ),
        timeout=0.1,
    )

    assert plugins.calls["failing_plugin"] == [{"case_id": 1, "save_to_case": False}]
    assert recorder.events[-1] == HuntEvent.complete(1)
    assert run.status == "completed"


@pytest.mark.asyncio
async def test_domain_hunt_passes_dns_address_to_shodan(db_session):
    recorder = EventRecorder()
    plugins = PluginCatalogueStub(
        {"DnsLookup": {"results": [{"records": ["192.0.2.44"]}]}}
    )
    executor = HuntExecutor(db_session, recorder, plugin_service=plugins)
    db_session.add = MagicMock()
    db_session.commit = MagicMock()
    run = execution()
    run.initial_parameters = {
        "domain": "example.com",
        "subdomain_concurrency": 10.0,
        "use_securitytrails": False,
    }

    await executor.execute_hunt(run, DomainHunt().to_definition(), user())

    assert plugins.calls["ShodanPlugin"][0]["query"] == "192.0.2.44"
