"""Hunt Entity effects preserve Case boundaries, receipts and owner fencing."""

from contextlib import contextmanager
from datetime import timedelta

import pytest
from sqlmodel import Session

from app.core.dependencies import get_current_user
from app.core.utils import get_utc_now
from app.database.models import (
    CaseUserLink,
    Entity,
    ExecutionControl,
    Hunt,
    HuntExecution,
    HuntStep,
)
from app.executions.effects import CaseEffects
from app.executions.ownership import Ownership, OwnershipLost
from app.main import app
from app.plugins.plugin_types import DomainSubdomainsWrite, IpAddressWrite


@pytest.mark.parametrize("kind", ["ip_address", "domain"])
@pytest.mark.parametrize("existing", [False, True])
@pytest.mark.parametrize(
    "provenance",
    [
        "direct",
        "transitive",
        "unknown-output",
        "unknown-dependency",
        "missing-graph",
        "destination",
        "unrelated",
        "no-correlation",
        "ordering-only",
        "partial",
        "malformed-graph",
    ],
)
async def test_entity_effect_scope_and_replay(
    client, session, test_case, test_admin, test_user, kind, existing, provenance
):
    app.dependency_overrides[get_current_user] = lambda: test_admin
    destination = test_case.id
    initiator = test_user if provenance == "unknown-output" else test_admin
    scan = {"step_id": "scan", "plugin_name": "CorrelationScan"}
    consumer = {
        "step_id": "copy",
        "plugin_name": "DnsLookup",
        "parameter_mapping": {"domain": "scan.results"},
    }
    steps = [scan, consumer]
    if provenance == "transitive":
        steps.insert(
            1,
            {
                "step_id": "middle",
                "plugin_name": "Other",
                "parameter_mapping": {"query": "scan.results"},
            },
        )
        consumer["parameter_mapping"] = {"domain": "middle.results"}
    elif provenance == "unknown-dependency":
        steps = [consumer]
    elif provenance in {"unrelated", "no-correlation", "ordering-only"}:
        consumer["parameter_mapping"] = {}
        if provenance == "no-correlation":
            steps = [consumer]
        elif provenance == "ordering-only":
            consumer["depends_on"] = ["scan"]
    hunt = Hunt(
        name="effects",
        display_name="Effects",
        description="Test",
        category="test",
        definition_json={"steps": steps},
    )
    session.add(hunt)
    session.flush()
    execution = HuntExecution(
        hunt_id=hunt.id,
        case_id=destination,
        created_by_id=initiator.id,
        initial_parameters={},
        status="running",
        definition_snapshot=(
            None if provenance == "missing-graph" else {"steps": steps}
        ),
    )
    session.add(execution)
    session.flush()
    output = {
        "plugin": "CorrelationScan",
        "results": [
            {
                "case_id": destination,
                "matches": (
                    []
                    if provenance == "destination"
                    else [{"case_id": destination + 100}]
                ),
            }
        ],
    }
    if provenance == "partial":
        output = {"results": [], "partial": True}
    if provenance == "malformed-graph":
        execution.definition_snapshot = {
            "steps": [{"step_id": "copy", "parameter_mapping": []}]
        }
    if provenance not in {"unknown-dependency", "no-correlation"}:
        session.add(
            HuntStep(
                execution_id=execution.id,
                step_id="scan",
                plugin_name="CorrelationScan",
                status="completed",
                parameters={},
                output=None if provenance == "unknown-output" else output,
            )
        )
    control = ExecutionControl(
        hunt_execution_id=execution.id,
        owner="original",
        generation=1,
        lease_until=get_utc_now() + timedelta(minutes=5),
    )
    session.add(control)
    data = (
        {"ip_address": "192.0.2.55", "description": "PUBLIC"}
        if kind == "ip_address"
        else {"domain": "example.test", "subdomains": [], "description": "PUBLIC"}
    )
    if existing:
        session.add(
            Entity(
                case_id=destination,
                entity_type=kind,
                data=data,
                created_by_id=test_admin.id,
            )
        )
    session.commit()

    @contextmanager
    def session_factory():
        with Session(
            bind=session.connection(), join_transaction_mode="create_savepoint"
        ) as db:
            yield db

    owner = Ownership(control.id, 1, "original")
    request = (
        IpAddressWrite("192.0.2.55", "SECRET")
        if kind == "ip_address"
        else DomainSubdomainsWrite(
            "example.test", [{"subdomain": "SECRET.example.test", "resolved": True}]
        )
    )

    def effects(ownership=owner, operation="copy"):
        return CaseEffects(
            session_factory, ownership, operation, destination, initiator, True
        )

    permitted = provenance in {
        "destination",
        "unrelated",
        "no-correlation",
        "ordering-only",
    }
    session.add(CaseUserLink(case_id=destination, user_id=test_user.id))
    copied_output = {
        "results": [{"notice_type": "entity_save_skipped", "message": "SECRET"}]
    }
    session.add(
        HuntStep(
            execution_id=execution.id,
            step_id="copy",
            plugin_name="DnsLookup",
            parameters={"domain": "SECRET"},
            output=copied_output,
        )
    )
    execution.context_data = {"step_outputs": {"copy": copied_output}}
    session.commit()
    warning = await effects().entity(request)
    assert warning == (
        None
        if permitted
        else "Entity save skipped: correlation provenance does not permit saving to this Case."
    )
    url = f"/api/cases/{destination}/entities"
    before = client.get(url).json()
    assert len(before) == int(existing or permitted)
    assert ("SECRET" in str(before)) == permitted
    if not permitted:
        app.dependency_overrides[get_current_user] = lambda: test_user
        detail_url = f"/api/hunts/executions/{execution.id}"
        for suffix in (
            "?include_steps=true",
            "/steps/copy/results",
            "/export?format=json",
        ):
            response = client.get(detail_url + suffix)
            assert response.status_code == 200
            assert warning in response.text
            assert "SECRET" not in response.text
        app.dependency_overrides[get_current_user] = lambda: test_admin
    # A recovered worker must retain the original decision even if provenance is now different.
    execution.definition_snapshot = {
        "steps": [{"step_id": "copy", "plugin_name": "DnsLookup"}]
    }
    control.generation = 2
    control.owner = "recovered"
    session.commit()
    recovered = Ownership(control.id, 2, "recovered")
    assert await effects(recovered).entity(request) == warning
    assert client.get(url).json() == before
    with pytest.raises(OwnershipLost):
        await effects().entity(request)
    control.cancellation_requested_at = get_utc_now()
    session.commit()
    with pytest.raises(OwnershipLost):
        await effects(recovered, "cancelled").entity(request)
    assert client.get(url).json() == before
