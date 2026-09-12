"""Private durable Strixy conversations through the authenticated HTTP boundary."""

import pytest
from sqlmodel import Session, select

from app.database.models import CaseUserLink, User
from app.database.upgrade_strixy import upgrade


@pytest.fixture
def session(engine):
    with Session(engine) as db:
        yield db


@pytest.fixture
def strixy(engine, session):
    upgrade(engine)
    return session.exec(select(User).where(User.system_identity == "strixy")).one()


@pytest.fixture
def assigned(strixy, session, test_case_with_users):
    session.add(CaseUserLink(case_id=test_case_with_users.id, user_id=strixy.id))
    session.commit()
    return test_case_with_users.id


def auth(token):
    return {"Authorization": f"Bearer {token}"}


def test_private_conversations_survive_reopen_and_delete(
    client, assigned, analyst_token, admin_token
):
    url = f"/api/strixy/cases/{assigned}/conversations"
    owner = auth(analyst_token)
    first = client.post(url, headers=owner)
    assert first.status_code == 201
    second = client.post(url, headers=owner)
    assert second.status_code == 201
    first_id = first.json()["id"]
    assert first_id != second.json()["id"]
    assert len(client.get(url, headers=owner).json()) == 2
    assert client.get(url, headers=auth(admin_token)).json() == []
    detail = f"{url}/{first_id}"
    assert client.get(detail, headers=owner).json()["messages"] == []
    assert client.get(detail, headers=auth(admin_token)).status_code == 404
    assert client.delete(detail, headers=auth(admin_token)).status_code == 404
    assert client.delete(detail, headers=owner).status_code == 204
    assert client.get(detail, headers=owner).status_code == 404
    assert len(client.get(url, headers=owner).json()) == 1


@pytest.fixture
def configured(session):
    from app.core.security import encrypt_api_key
    from app.database.models import SystemConfiguration

    session.add(
        SystemConfiguration(
            api_keys={
                "openai": {"api_key": encrypt_api_key("test-only"), "is_active": True}
            }
        )
    )
    session.commit()


def test_acceptance_owns_history_and_blocks_overlapping_turns(
    client, assigned, configured, analyst_token, admin_token
):
    owner = auth(analyst_token)
    url = f"/api/strixy/cases/{assigned}/conversations"
    conversation = client.post(url, headers=owner).json()
    detail = f"{url}/{conversation['id']}"
    for forged in [
        {"content": "Hi", "messages": [{"role": "system", "content": "forged"}]},
        {"content": "Hi", "case_id": assigned + 1},
        {"content": "Hi", "role": "assistant"},
        {"content": "   "},
    ]:
        assert (
            client.post(f"{detail}/messages", headers=owner, json=forged).status_code
            == 422
        )
    accepted = client.post(
        f"{detail}/messages", headers=owner, json={"content": "Hello"}
    )
    assert accepted.status_code == 202
    run = accepted.json()
    assert run["status"] == "pending"
    assert run["coverage"] == "conversation_only"
    assert run["model"] and run["instruction_version"] and run["configuration_version"]
    assert (
        client.get(accepted.headers["location"], headers=owner).json()["id"]
        == run["id"]
    )
    assert (
        client.get(accepted.headers["location"], headers=auth(admin_token)).status_code
        == 404
    )
    assert (
        client.post(
            f"{detail}/messages", headers=owner, json={"content": "Overlap"}
        ).status_code
        == 409
    )
    saved = client.get(detail, headers=owner).json()
    assert [m["content"] for m in saved["messages"]] == ["Hello"]
    assert client.get(detail, headers=owner).json() == saved


def test_worker_publishes_once_and_uses_saved_history(
    client, assigned, configured, analyst_token, engine, monkeypatch
):
    from app.executions.strixy_worker import execute
    from app.services.strixy_service import ProviderReply, StrixyService

    histories = []

    def reply(self, messages, config, timeout):
        histories.append([(m.role, m.content) for m in messages if m.role != "system"])
        return ProviderReply(content="A saved answer", input_tokens=12, output_tokens=8)

    monkeypatch.setattr(StrixyService, "generate", reply)
    owner = auth(analyst_token)
    url = f"/api/strixy/cases/{assigned}/conversations"
    detail = f"{url}/{client.post(url, headers=owner).json()['id']}"
    accepted = client.post(
        f"{detail}/messages", headers=owner, json={"content": "First"}
    ).json()
    execute(accepted["id"], engine)
    execute(accepted["id"], engine)
    saved = client.get(detail, headers=owner).json()
    assert [m["content"] for m in saved["messages"]] == ["First", "A saved answer"]
    assert saved["runs"][0]["status"] == "completed"
    assert saved["runs"][0]["output_tokens"] == 8
    assert (
        client.post(f"{detail}/runs/{accepted['id']}/cancel", headers=owner).json()[
            "status"
        ]
        == "completed"
    )
    assert client.get(detail, headers=owner).json() == saved
    second = client.post(
        f"{detail}/messages", headers=owner, json={"content": "Follow up"}
    ).json()
    execute(second["id"], engine)
    assert histories == [
        [("user", "First")],
        [("user", "First"), ("assistant", "A saved answer"), ("user", "Follow up")],
    ]
    reopened = client.get(detail, headers=owner).json()
    assert reopened["messages"][:2] == saved["messages"]


@pytest.mark.parametrize(
    "race",
    [
        "delete",
        "strixy_membership",
        "human_membership",
        "human_inactive",
        "provider_failure",
    ],
)
def test_late_worker_cannot_publish_after_deletion_or_revocation(
    client, assigned, configured, analyst_token, engine, monkeypatch, race, test_analyst
):
    from app.database.models import StrixyConversation
    from app.executions.strixy_worker import execute
    from app.services.strixy_service import ProviderReply, StrixyService

    owner = auth(analyst_token)
    url = f"/api/strixy/cases/{assigned}/conversations"
    cid = client.post(url, headers=owner).json()["id"]
    detail = f"{url}/{cid}"
    accepted = client.post(
        f"{detail}/messages", headers=owner, json={"content": "Question"}
    ).json()

    def reply(self, messages, config, timeout):
        if race == "provider_failure":
            raise RuntimeError("sensitive provider detail")
        if race == "delete":
            assert client.delete(detail, headers=owner).status_code == 204
        else:
            with Session(engine) as db:
                human = db.get(StrixyConversation, cid).owner_id
                strixy_id = (
                    db.exec(select(User).where(User.system_identity == "strixy"))
                    .one()
                    .id
                )
                if race == "human_inactive":
                    user = db.get(User, human)
                    user.is_active = False
                    db.add(user)
                else:
                    db.delete(
                        db.get(
                            CaseUserLink,
                            (
                                assigned,
                                strixy_id if race == "strixy_membership" else human,
                            ),
                        )
                    )
                db.commit()
        return ProviderReply(content="Late private output")

    monkeypatch.setattr(StrixyService, "generate", reply)
    execute(accepted["id"], engine)
    execute(accepted["id"], engine)
    response = client.get(detail, headers=owner)
    if race == "provider_failure":
        assert response.status_code == 200
        assert [m["content"] for m in response.json()["messages"]] == ["Question"]
        assert response.json()["runs"][0]["error_code"] == "provider_failed"
        assert "sensitive" not in response.text
        assert (
            client.post(
                f"{detail}/messages", headers=owner, json={"content": "Try again"}
            ).status_code
            == 202
        )
    else:
        assert response.status_code in {401, 403, 404}
        assert "Late private output" not in response.text


def test_missing_configuration_preserves_conversation(client, assigned, analyst_token):
    owner = auth(analyst_token)
    url = f"/api/strixy/cases/{assigned}/conversations"
    detail = f"{url}/{client.post(url, headers=owner).json()['id']}"
    response = client.post(
        f"{detail}/messages", headers=owner, json={"content": "Question"}
    )
    assert response.status_code == 422
    assert "API key not configured" in response.json()["detail"]
    assert client.get(detail, headers=owner).json()["messages"] == []


def test_run_limits_are_distinct_from_execution_failure(
    client, assigned, configured, analyst_token, engine, monkeypatch
):
    from app.core.strixy_config import StrixyConfig
    from app.executions.strixy_worker import execute
    from app.services.strixy_service import ProviderReply, StrixyService

    owner = auth(analyst_token)
    url = f"/api/strixy/cases/{assigned}/conversations"
    detail = f"{url}/{client.post(url, headers=owner).json()['id']}"
    monkeypatch.setattr(
        StrixyService,
        "generate",
        lambda *args: ProviderReply(
            content="Partial finding", limit_code="output_limit"
        ),
    )
    accepted = client.post(
        f"{detail}/messages", headers=owner, json={"content": "Question"}
    ).json()
    execute(accepted["id"], engine)
    saved = client.get(detail, headers=owner).json()
    assert saved["runs"][0]["status"] == "completed"
    assert saved["runs"][0]["limit_code"] == "output_limit"
    assert saved["messages"][-1]["content"] == "Partial finding"
    monkeypatch.setattr(
        "app.core.strixy_config.get_strixy_config", lambda: StrixyConfig(max_messages=1)
    )
    limited = client.post(
        f"{detail}/messages", headers=owner, json={"content": "More"}
    ).json()
    assert limited["status"] == "completed"
    assert limited["limit_code"] == "input_limit"
    execute(limited["id"], engine)
    assert len(client.get(detail, headers=owner).json()["messages"]) == 3


def test_transport_loss_reports_uncertain_completion(
    client, assigned, configured, analyst_token, engine, monkeypatch
):
    import httpx
    from openai import APIConnectionError

    from app.executions.strixy_worker import execute
    from app.services.strixy_service import StrixyService

    def uncertain(*args):
        raise APIConnectionError(
            request=httpx.Request("POST", "https://api.openai.com/v1/responses")
        )

    monkeypatch.setattr(StrixyService, "generate", uncertain)
    owner = auth(analyst_token)
    url = f"/api/strixy/cases/{assigned}/conversations"
    detail = f"{url}/{client.post(url, headers=owner).json()['id']}"
    accepted = client.post(
        f"{detail}/messages", headers=owner, json={"content": "Question"}
    ).json()
    execute(accepted["id"], engine)
    result = client.get(detail, headers=owner).json()
    assert result["runs"][0]["error_code"] == "completion_uncertain"
    assert len(result["messages"]) == 1


def test_identifiers_cannot_move_conversations_between_cases(
    client, assigned, configured, analyst_token, session, test_analyst, strixy
):
    from app.database.models import Case

    owner = auth(analyst_token)
    url = f"/api/strixy/cases/{assigned}/conversations"
    detail = f"{url}/{client.post(url, headers=owner).json()['id']}"
    first = client.post(
        f"{detail}/messages", headers=owner, json={"content": "Original Case"}
    ).json()
    original = session.get(Case, assigned)
    other = Case(
        case_number="OTHER-STRIXY", title="Other", client_id=original.client_id
    )
    session.add(other)
    session.flush()
    session.add_all(
        [
            CaseUserLink(case_id=other.id, user_id=test_analyst.id),
            CaseUserLink(case_id=other.id, user_id=strixy.id),
        ]
    )
    session.commit()
    foreign = detail.replace(f"/cases/{assigned}/", f"/cases/{other.id}/")
    for response in [
        client.get(foreign, headers=owner),
        client.delete(foreign, headers=owner),
        client.post(f"{foreign}/messages", headers=owner, json={"content": "Moved"}),
        client.get(f"{foreign}/runs/{first['id']}", headers=owner),
        client.post(f"{foreign}/runs/{first['id']}/cancel", headers=owner),
        client.post(f"{foreign}/runs/{first['id']}/continue", headers=owner),
        client.post(f"{foreign}/runs/{first['id']}/retry", headers=owner),
        client.post(f"{foreign}/runs/{first['id']}/reanalyze", headers=owner),
    ]:
        assert response.status_code == 404
    assert client.get(detail, headers=owner).json()["case_id"] == assigned


def test_owner_can_cancel_pending_run_idempotently(
    client, assigned, configured, analyst_token, admin_token, engine, monkeypatch
):
    from app.executions.strixy_worker import execute
    from app.services.strixy_service import StrixyService

    def unexpected(*args):
        pytest.fail("Cancelled work must never call the provider")

    monkeypatch.setattr(StrixyService, "generate", unexpected)
    owner = auth(analyst_token)
    url = f"/api/strixy/cases/{assigned}/conversations"
    detail = f"{url}/{client.post(url, headers=owner).json()['id']}"
    accepted = client.post(
        f"{detail}/messages", headers=owner, json={"content": "Stop me"}
    )
    cancel = accepted.headers["location"] + "/cancel"
    assert client.post(cancel, headers=auth(admin_token)).status_code == 404
    first = client.post(cancel, headers=owner)
    assert first.status_code == 200
    assert first.json()["status"] == "cancelled"
    assert client.post(cancel, headers=owner).json() == first.json()
    execute(accepted.json()["id"], engine)
    assert len(client.get(detail, headers=owner).json()["messages"]) == 1


def test_cancel_preserves_streamed_findings_and_fences_late_output(
    client, assigned, configured, analyst_token, engine, monkeypatch
):
    import json

    from app.executions.strixy_worker import execute
    from app.services.strixy_service import ProviderReply, StrixyService

    owner = auth(analyst_token)
    url = f"/api/strixy/cases/{assigned}/conversations"
    detail = f"{url}/{client.post(url, headers=owner).json()['id']}"
    accepted = client.post(
        f"{detail}/messages", headers=owner, json={"content": "Analyze"}
    )

    def reply(self, messages, config, timeout):
        source = json.loads(messages[0].content)["sources"][0]
        self.on_progress(
            ProviderReply(
                "Permitted partial finding",
                citations=[
                    {
                        "source_id": source["source_id"],
                        "field": "case_number",
                        "excerpt": source["fields"]["case_number"],
                    }
                ],
            )
        )
        during = client.get(detail, headers=owner).json()["runs"][0]
        assert during["progress"] == "preparing_findings"
        assert during["partial"]["content"] == "Permitted partial finding"
        assert during["partial"]["citations"]
        assert during["source_coverage"]["counts"]["read"] >= 1
        assert (
            client.post(
                accepted.headers["location"] + "/cancel", headers=owner
            ).status_code
            == 200
        )
        return ProviderReply("Late output that must not appear")

    monkeypatch.setattr(StrixyService, "generate", reply)
    execute(accepted.json()["id"], engine)
    execute(accepted.json()["id"], engine)
    saved = client.get(detail, headers=owner).json()
    assert saved["runs"][0]["status"] == "cancelled"
    assert saved["runs"][0]["partial"]["content"] == "Permitted partial finding"
    assert "Late output" not in str(saved)


def test_explicit_continuation_reuses_progress_and_reanalysis_reads_current_sources(
    client, assigned, configured, analyst_token, engine, monkeypatch
):
    import json

    from app.core.strixy_config import StrixyConfig
    from app.database.models import Case
    from app.executions.strixy_worker import execute
    from app.services.strixy_service import ProviderReply, StrixyService

    monkeypatch.setattr(
        "app.core.strixy_config.get_strixy_config",
        lambda: StrixyConfig(max_model_calls=1),
    )
    contexts = []

    def reply(self, messages, config, timeout):
        contexts.append(json.loads(messages[0].content))
        return ProviderReply(
            "Partial supported observation",
            tool_requests=[
                {
                    "name": "read_case_sources",
                    "arguments": {"action": "list", "source_id": None, "query": None},
                }
            ],
        )

    monkeypatch.setattr(StrixyService, "generate", reply)
    owner = auth(analyst_token)
    url = f"/api/strixy/cases/{assigned}/conversations"
    detail = f"{url}/{client.post(url, headers=owner).json()['id']}"
    first = client.post(
        f"{detail}/messages", headers=owner, json={"content": "Analyze"}
    ).json()
    execute(first["id"], engine)
    saved = client.get(detail, headers=owner).json()
    assert saved["runs"][0]["limit_code"] == "model_call_limit"
    assert saved["runs"][0]["partial"]["content"] == "Partial supported observation"
    continued = client.post(f"{detail}/runs/{first['id']}/continue", headers=owner)
    assert continued.status_code == 202
    assert continued.json()["id"] != first["id"]
    assert (
        client.post(f"{detail}/runs/{first['id']}/retry", headers=owner).status_code
        == 409
    )
    execute(continued.json()["id"], engine)
    assert contexts[-1]["reused_progress"] is True
    assert client.get(detail, headers=owner).json()["runs"][0] == saved["runs"][0]
    with Session(engine) as db:
        case = db.get(Case, assigned)
        case.title = "Changed current title"
        db.add(case)
        db.commit()
    reanalysis = client.post(
        f"{detail}/runs/{continued.json()['id']}/reanalyze", headers=owner
    )
    assert reanalysis.status_code == 202
    execute(reanalysis.json()["id"], engine)
    assert "Changed current title" in json.dumps(contexts[-1])
    assert contexts[-1].get("reused_progress", False) is False


def test_continuation_advances_beyond_bounded_catalog(
    client,
    assigned,
    configured,
    analyst_token,
    engine,
    monkeypatch,
    session,
    test_analyst,
):
    import json

    from app.core.strixy_config import StrixyConfig
    from app.database.models import Entity
    from app.executions.strixy_worker import execute
    from app.services.strixy_service import ProviderReply, StrixyService

    entities = [
        Entity(
            case_id=assigned,
            created_by_id=test_analyst.id,
            entity_type="person",
            data={"name": name},
        )
        for name in ["First", "Second"]
    ]
    session.add_all(entities)
    session.commit()
    monkeypatch.setattr(
        "app.core.strixy_config.get_strixy_config", lambda: StrixyConfig(max_sources=1)
    )
    seen = []

    def reply(self, messages, config, timeout):
        context = json.loads(messages[0].content)
        seen.extend(source["source_id"] for source in context["sources"])
        return ProviderReply("A finding")

    monkeypatch.setattr(StrixyService, "generate", reply)
    owner = auth(analyst_token)
    url = f"/api/strixy/cases/{assigned}/conversations"
    detail = f"{url}/{client.post(url, headers=owner).json()['id']}"
    run = client.post(
        f"{detail}/messages", headers=owner, json={"content": "Analyze all records"}
    ).json()
    execute(run["id"], engine)
    saved = client.get(detail, headers=owner).json()
    assert "source_count_limit" in saved["runs"][0]["source_coverage"]["limits"]
    for _ in range(2):
        response = client.post(f"{detail}/runs/{run['id']}/continue", headers=owner)
        assert response.status_code == 202
        run = response.json()
        execute(run["id"], engine)
    assert seen == [f"case:{assigned}", *[f"entity:{item.id}" for item in entities]]


@pytest.mark.parametrize(
    "limit", ["runtime_limit", "output_limit", "model_input_limit"]
)
def test_limits_across_steps_preserve_findings_and_usage(
    client, assigned, configured, analyst_token, engine, monkeypatch, limit
):
    from datetime import timedelta

    from app.core.strixy_config import StrixyConfig
    from app.core.utils import get_utc_now
    from app.executions.strixy_worker import execute
    from app.services.strixy_service import ProviderReply, StrixyService

    monkeypatch.setattr(
        "app.core.strixy_config.get_strixy_config",
        lambda: StrixyConfig(max_output_tokens=16, max_total_input_tokens=5000),
    )
    calls = []

    def reply(self, messages, config, timeout):
        calls.append(True)
        self.on_progress(ProviderReply("Saved partial finding"))
        if limit == "runtime_limit":
            later = get_utc_now() + timedelta(seconds=1000)
            monkeypatch.setattr(
                "app.services.strixy_analysis.get_utc_now", lambda: later
            )
        return ProviderReply(
            "",
            input_tokens=5000 if limit == "model_input_limit" else 10,
            output_tokens=16 if limit == "output_limit" else 1,
            tool_requests=[
                {
                    "name": "read_case_sources",
                    "arguments": {"action": "list", "source_id": None, "query": None},
                }
            ],
        )

    monkeypatch.setattr(StrixyService, "generate", reply)
    owner = auth(analyst_token)
    url = f"/api/strixy/cases/{assigned}/conversations"
    detail = f"{url}/{client.post(url, headers=owner).json()['id']}"
    run = client.post(
        f"{detail}/messages", headers=owner, json={"content": "Analyze"}
    ).json()
    execute(run["id"], engine)
    saved = client.get(detail, headers=owner).json()["runs"][0]
    assert saved["limit_code"] == limit
    assert saved["status"] == "completed"
    assert saved["error_code"] is None
    assert saved["partial"]["content"] == "Saved partial finding"
    assert saved["model_calls"] == 1
    assert saved["source_coverage"]["supplied_to_model"] is True
    assert len(calls) == 1


@pytest.mark.parametrize("change", ["source", "configuration"])
def test_continuation_invalidates_changed_preparation(
    client, assigned, configured, analyst_token, engine, monkeypatch, change
):
    import json

    from app.core.strixy_config import StrixyConfig
    from app.database.models import Case
    from app.executions.strixy_worker import execute
    from app.services.strixy_service import ProviderReply, StrixyService

    seen = []

    def reply(self, messages, config, timeout):
        seen.append(json.loads(messages[0].content))
        return ProviderReply("A finding", limit_code="output_limit")

    monkeypatch.setattr(StrixyService, "generate", reply)
    owner = auth(analyst_token)
    url = f"/api/strixy/cases/{assigned}/conversations"
    detail = f"{url}/{client.post(url, headers=owner).json()['id']}"
    first = client.post(
        f"{detail}/messages", headers=owner, json={"content": "Analyze"}
    ).json()
    execute(first["id"], engine)
    historical = client.get(detail, headers=owner).json()["messages"]
    if change == "configuration":
        monkeypatch.setattr(
            "app.core.strixy_config.get_strixy_config",
            lambda: StrixyConfig(max_source_field_bytes=1000),
        )
    else:
        with Session(engine) as db:
            case = db.get(Case, assigned)
            case.title = "Fresh material"
            db.add(case)
            db.commit()
    continued = client.post(
        f"{detail}/runs/{first['id']}/continue", headers=owner
    ).json()
    execute(continued["id"], engine)
    assert seen[-1]["reused_progress"] is False
    assert (
        client.get(detail, headers=owner).json()["messages"][: len(historical)]
        == historical
    )


def test_continuation_does_not_skip_material_rejected_before_model_admission(
    client,
    assigned,
    configured,
    analyst_token,
    engine,
    monkeypatch,
    test_analyst,
    session,
):
    from app.core.strixy_config import StrixyConfig
    from app.database.models import Entity
    from app.executions.strixy_worker import execute
    from app.services.strixy_service import StrixyService

    session.add(
        Entity(
            case_id=assigned,
            created_by_id=test_analyst.id,
            entity_type="person",
            data={"name": "Later record"},
        )
    )
    session.commit()
    monkeypatch.setattr(
        "app.core.strixy_config.get_strixy_config",
        lambda: StrixyConfig(max_sources=1, max_total_input_tokens=100),
    )

    def unexpected(*args):
        pytest.fail("Model admission must fail before the provider")

    monkeypatch.setattr(StrixyService, "generate", unexpected)
    owner = auth(analyst_token)
    url = f"/api/strixy/cases/{assigned}/conversations"
    detail = f"{url}/{client.post(url, headers=owner).json()['id']}"
    run = client.post(
        f"{detail}/messages", headers=owner, json={"content": "Analyze"}
    ).json()
    for _ in range(2):
        execute(run["id"], engine)
        saved = client.get(f"{detail}/runs/{run['id']}", headers=owner).json()
        assert saved["model_calls"] == 0
        assert saved["source_coverage"]["supplied_to_model"] is False
        assert [
            source["source_id"] for source in saved["source_coverage"]["sources"]
        ] == [f"case:{assigned}"]
        run = client.post(f"{detail}/runs/{run['id']}/continue", headers=owner).json()


def test_continuation_reads_next_record_chunk_without_repeating_preparation(
    client,
    assigned,
    configured,
    analyst_token,
    engine,
    monkeypatch,
    session,
    test_analyst,
):
    import json

    from app.core.strixy_config import StrixyConfig
    from app.database.models import Evidence
    from app.executions.strixy_worker import execute
    from app.services.strixy_service import ProviderReply, StrixyService

    evidence = Evidence(
        case_id=assigned,
        created_by_id=test_analyst.id,
        title="Chunked",
        description="A" * 200 + "B" * 200,
        evidence_type="text",
        content="",
    )
    session.add(evidence)
    session.commit()
    source_id = f"evidence:{evidence.id}"
    monkeypatch.setattr(
        "app.core.strixy_config.get_strixy_config",
        lambda: StrixyConfig(max_source_field_bytes=100),
    )
    chunks = []

    def reply(self, messages, config, timeout):
        source = json.loads(messages[0].content)["sources"][0]
        chunks.append(source["fields"]["description"])
        return ProviderReply("Partial interpretation", limit_code="output_limit")

    monkeypatch.setattr(StrixyService, "generate", reply)
    owner = auth(analyst_token)
    url = f"/api/strixy/cases/{assigned}/conversations"
    detail = f"{url}/{client.post(url, headers=owner).json()['id']}"
    run = client.post(
        f"{detail}/messages",
        headers=owner,
        json={"content": "Analyze", "focus": [source_id]},
    ).json()
    for _ in range(5):
        execute(run["id"], engine)
        run = client.post(f"{detail}/runs/{run['id']}/continue", headers=owner).json()
    assert "".join(chunks) == evidence.description
