"""Fixed snapshots and independent follow-ups at the authenticated HTTP seam."""

from app.services.strixy_conversations import COPIED_QUESTION_NOTICE
from app.services.strixy_service import ProviderReply, StrixyService
from tests.api import test_strixy_sources_api as fixtures

assigned = fixtures.assigned
configured = fixtures.configured
session = fixtures.session
strixy = fixtures.strixy
restricted = fixtures.restricted
auth = fixtures.auth


def test_snapshot_is_fixed_private_and_revocable(
    client, assigned, configured, analyst_token, admin_token, engine, monkeypatch
):
    monkeypatch.setattr(
        StrixyService, "generate", lambda *args: ProviderReply(content="Saved finding")
    )
    detail, owner = fixtures.new_conversation(client, assigned, analyst_token)
    saved = fixtures.turn(client, detail, owner, engine)
    response = client.post(
        f"{detail}/shares",
        headers=owner,
        json={"through_message_id": saved["messages"][-1]["id"]},
    )
    assert response.status_code == 201, response.text
    share = response.json()
    url = f"/api/strixy/cases/{assigned}/shares/{share['id']}"
    viewer = auth(admin_token)
    viewed = client.get(url, headers=viewer)
    assert viewed.status_code == 200
    assert [m["content"] for m in viewed.json()["messages"]] == [
        "Brief this Case",
        "Saved finding",
    ]
    fixtures.turn(client, detail, owner, engine, content="Later private question")
    assert client.get(url, headers=viewer).json() == viewed.json()
    assert client.get(detail, headers=viewer).status_code == 404
    assert (
        client.post(
            f"{detail}/shares",
            headers=viewer,
            json={"through_message_id": saved["messages"][-1]["id"]},
        ).status_code
        == 404
    )
    assert client.delete(url, headers=viewer).status_code == 404
    assert client.get(url).status_code == 401
    assert client.delete(url, headers=owner).status_code == 204
    assert client.get(url, headers=viewer).status_code == 404
    assert client.post(f"{url}/copy", headers=viewer).status_code == 404


def test_copy_preserves_sources_and_survives_original_deletion(
    client, assigned, configured, analyst_token, admin_token, engine, monkeypatch
):
    histories = []

    def reply(self, messages, config, timeout):
        histories.append([m.content for m in messages])
        return ProviderReply(content="Independent finding")

    monkeypatch.setattr(StrixyService, "generate", reply)
    detail, owner = fixtures.new_conversation(client, assigned, analyst_token)
    saved = fixtures.turn(client, detail, owner, engine)
    share = client.post(
        f"{detail}/shares",
        headers=owner,
        json={"through_message_id": saved["messages"][-1]["id"]},
    ).json()
    url = f"/api/strixy/cases/{assigned}/shares/{share['id']}"
    viewer = auth(admin_token)
    copied = client.post(f"{url}/copy", headers=viewer)
    assert copied.status_code == 201, copied.text
    copy_url = f"/api/strixy/cases/{assigned}/conversations/{copied.json()['id']}"
    copied_messages = client.get(copy_url, headers=viewer).json()["messages"]
    assert [
        (m["content"], m["timestamp"], m.get("citations")) for m in copied_messages
    ] == [
        (m["content"], m["timestamp"], m.get("citations", []))
        for m in saved["messages"]
    ]
    assert client.get(copy_url, headers=owner).status_code == 404
    assert client.delete(detail, headers=owner).status_code == 204
    assert client.get(url, headers=viewer).status_code == 404
    assert client.post(f"{url}/copy", headers=viewer).status_code == 404
    assert [m.get("copied") for m in copied_messages] == [True, True]
    fixtures.turn(client, copy_url, viewer, engine, content="Explore this further")
    first, answer, current = histories[-1][1:]
    assert first == f'{COPIED_QUESTION_NOTICE}\n"Brief this Case"'
    assert (answer, current) == ("Independent finding", "Explore this further")
    own = client.get(copy_url, headers=viewer).json()["messages"]
    assert [m.get("copied") for m in own] == [True, True, None, None]


import pytest

from app.database.models import CaseUserLink


@pytest.mark.parametrize("removed", ["viewer", "strixy"])
def test_uncited_provenance_protects_whole_snapshots_copies_and_future_context(
    client,
    assigned,
    configured,
    analyst_token,
    admin_token,
    user_token,
    test_user,
    strixy,
    restricted,
    session,
    engine,
    monkeypatch,
    removed,
):
    histories = []

    def reply(self, messages, config, timeout):
        histories.append([m.content for m in messages])
        return ProviderReply(content="Protected inference from uncited input")

    monkeypatch.setattr(StrixyService, "generate", reply)
    detail, owner = fixtures.new_conversation(client, assigned, analyst_token)
    saved = fixtures.turn(client, detail, owner, engine)
    shared = client.post(
        f"{detail}/shares",
        headers=owner,
        json={"through_message_id": saved["messages"][-1]["id"]},
    ).json()
    url = f"/api/strixy/cases/{assigned}/shares/{shared['id']}"
    viewer = auth(user_token)
    denied = client.get(url, headers=viewer)
    assert denied.status_code == 404
    assert "Protected" not in denied.text
    assert client.post(f"{url}/copy", headers=viewer).status_code == 404
    session.add(CaseUserLink(case_id=restricted[0], user_id=test_user.id))
    session.commit()
    assert client.get(url, headers=viewer).status_code == 200
    copied = client.post(f"{url}/copy", headers=viewer)
    assert copied.status_code == 201
    copy_url = f"/api/strixy/cases/{assigned}/conversations/{copied.json()['id']}"
    fixtures.turn(client, copy_url, viewer, engine, focus=[f"case:{assigned}"])
    assert "Protected inference from uncited input" in histories[-1]
    session.delete(
        session.get(
            CaseUserLink,
            (restricted[0], test_user.id if removed == "viewer" else strixy.id),
        )
    )
    session.commit()
    assert client.get(url, headers=viewer).status_code == 404
    assert client.post(f"{url}/copy", headers=viewer).status_code == 404
    withheld = client.get(copy_url, headers=viewer)
    assert "Protected inference" not in withheld.text
    assert withheld.json()["messages"][0]["withheld"]
    assert (
        client.post(
            f"{copy_url}/shares",
            headers=viewer,
            json={"through_message_id": withheld.json()["messages"][-1]["id"]},
        ).status_code
        == 404
    )
    fixtures.turn(client, copy_url, viewer, engine)
    assert all("Protected inference" not in text for text in histories[-1])


def test_share_boundaries_case_binding_and_revocation_after_copy(
    client,
    assigned,
    configured,
    analyst_token,
    admin_token,
    engine,
    monkeypatch,
    session,
    strixy,
):
    monkeypatch.setattr(
        StrixyService,
        "generate",
        lambda *args: ProviderReply(content="Historical answer"),
    )
    detail, owner = fixtures.new_conversation(client, assigned, analyst_token)
    saved = fixtures.turn(client, detail, owner, engine)
    assert (
        client.post(
            f"{detail}/shares", headers=owner, json={"through_message_id": "foreign"}
        ).status_code
        == 404
    )
    shares = [
        client.post(
            f"{detail}/shares", headers=owner, json={"through_message_id": m["id"]}
        ).json()
        for m in saved["messages"]
    ]
    assert sorted(
        [
            s["message_count"]
            for s in client.get(f"{detail}/shares", headers=owner).json()
        ]
    ) == [1, 2]
    url = f"/api/strixy/cases/{assigned}/shares/{shares[-1]['id']}"
    viewer = auth(admin_token)
    assert client.get(
        url.replace(f"cases/{assigned}", f"cases/{assigned + 100}"), headers=viewer
    ).status_code in (403, 404)
    copied = client.post(f"{url}/copy", headers=viewer).json()
    assert client.delete(url, headers=owner).status_code == 204
    copy_url = f"/api/strixy/cases/{assigned}/conversations/{copied['id']}"
    assert client.get(copy_url, headers=viewer).status_code == 200
    session.delete(session.get(CaseUserLink, (assigned, strixy.id)))
    session.commit()
    remaining = f"/api/strixy/cases/{assigned}/shares/{shares[0]['id']}"
    assert client.get(remaining, headers=viewer).status_code == 403
    assert client.post(f"{remaining}/copy", headers=viewer).status_code == 403
    assert (
        client.post(
            f"{copy_url}/messages", headers=viewer, json={"content": "Follow up"}
        ).status_code
        == 403
    )


def test_partial_snapshot_remains_partial_after_copy_and_late_worker_deletion(
    client,
    assigned,
    configured,
    analyst_token,
    admin_token,
    engine,
    monkeypatch,
):
    detail, owner = fixtures.new_conversation(client, assigned, analyst_token)
    viewer = auth(admin_token)
    copies = []

    def reply(self, messages, config, timeout):
        self.on_progress(ProviderReply(content="Partial historical finding"))
        saved = client.get(detail, headers=owner).json()
        partial = saved["runs"][-1]["partial"]
        response = client.post(
            f"{detail}/shares",
            headers=owner,
            json={"through_message_id": partial["id"]},
        )
        assert response.status_code == 201
        url = f"/api/strixy/cases/{assigned}/shares/{response.json()['id']}"
        copied = client.post(f"{url}/copy", headers=viewer)
        assert copied.status_code == 201
        copies.append(
            f"/api/strixy/cases/{assigned}/conversations/{copied.json()['id']}"
        )
        assert client.delete(detail, headers=owner).status_code == 204
        assert client.get(url, headers=viewer).status_code == 404
        return ProviderReply(content="Late answer must not reappear")

    monkeypatch.setattr(StrixyService, "generate", reply)
    accepted = client.post(
        f"{detail}/messages", headers=owner, json={"content": "Brief this Case"}
    )
    fixtures.execute(accepted.json()["id"], engine)
    assert client.get(detail, headers=owner).status_code == 404
    saved = client.get(copies[0], headers=viewer).json()
    assert saved["messages"][-1]["content"] == "Partial historical finding"
    assert saved["messages"][-1]["partial"] is True


def test_historical_citations_survive_source_changes_and_restored_assignment(
    client,
    assigned,
    configured,
    analyst_token,
    admin_token,
    engine,
    monkeypatch,
    session,
    strixy,
    test_analyst,
):
    import json

    from app.database.models import Entity

    entity = Entity(
        case_id=assigned,
        entity_type="person",
        data={"name": "Historical name"},
        created_by_id=test_analyst.id,
    )
    session.add(entity)
    session.commit()
    session.refresh(entity)
    histories = []

    def reply(self, messages, config, timeout):
        histories.append([m.content for m in messages])
        source = next(
            s
            for s in json.loads(messages[0].content)["sources"]
            if s["kind"] == "entity"
        )
        return ProviderReply(
            content="Original wording",
            citations=[
                {
                    "source_id": source["source_id"],
                    "field": "data",
                    "excerpt": "Historical name",
                }
            ],
        )

    monkeypatch.setattr(StrixyService, "generate", reply)
    detail, owner = fixtures.new_conversation(client, assigned, analyst_token)
    saved = fixtures.turn(client, detail, owner, engine)
    shared = client.post(
        f"{detail}/shares",
        headers=owner,
        json={"through_message_id": saved["messages"][-1]["id"]},
    ).json()
    url = f"/api/strixy/cases/{assigned}/shares/{shared['id']}"
    viewer = auth(admin_token)
    session.delete(session.get(CaseUserLink, (assigned, strixy.id)))
    session.commit()
    assert client.post(f"{url}/copy", headers=viewer).status_code == 403
    session.add(CaseUserLink(case_id=assigned, user_id=strixy.id))
    session.commit()
    entity.data = {"name": "Current name"}
    session.add(entity)
    session.commit()
    viewed = client.get(url, headers=viewer).json()["messages"][-1]
    original = saved["messages"][-1]
    assert (viewed["content"], viewed["timestamp"]) == (
        original["content"],
        original["timestamp"],
    )
    assert viewed["citations"][0] == original["citations"][0] | {
        "source_status": "changed"
    }
    assert (
        "Current name" in client.get(viewed["citations"][0]["url"], headers=viewer).text
    )
    copied = client.post(f"{url}/copy", headers=viewer)
    assert copied.status_code == 201
    copy_url = f"/api/strixy/cases/{assigned}/conversations/{copied.json()['id']}"

    def current_reply(self, messages, config, timeout):
        histories.append([m.content for m in messages])
        return ProviderReply(content="New findings")

    monkeypatch.setattr(StrixyService, "generate", current_reply)
    fixtures.turn(client, copy_url, viewer, engine)
    assert "Current name" in histories[-1][0]
    assert all(
        "Original wording" not in text and "Historical name" not in text
        for text in histories[-1]
    )


def test_attachment_citations_and_coverage_survive_repeated_sharing(
    client,
    assigned,
    configured,
    analyst_token,
    admin_token,
    engine,
    monkeypatch,
):
    from tests.api.test_strixy_attachments_api import upload

    evidence = upload(
        client, assigned, admin_token, "facts.txt", b"Verifiable attachment fact."
    )
    monkeypatch.setattr(
        StrixyService,
        "generate",
        lambda *args: ProviderReply(
            content="Saved attachment finding",
            citations=[
                {
                    "source_id": f"evidence:{evidence['id']}",
                    "field": "attachment:line:1",
                    "excerpt": "Verifiable attachment fact.",
                }
            ],
        ),
    )
    detail, owner = fixtures.new_conversation(client, assigned, analyst_token)
    original = fixtures.turn(client, detail, owner, engine)["messages"][-1]
    for _ in range(3):
        saved = client.get(detail, headers=owner).json()["messages"][-1]
        share = client.post(
            f"{detail}/shares", headers=owner, json={"through_message_id": saved["id"]}
        )
        assert share.status_code == 201
        url = f"/api/strixy/cases/{assigned}/shares/{share.json()['id']}"
        viewed = client.get(url, headers=owner).json()["messages"][-1]
        assert viewed["citations"] == original["citations"]
        assert viewed["coverage"] == original["coverage"]
        assert viewed["timestamp"] == original["timestamp"]
        assert (
            "Verifiable attachment fact."
            in client.get(viewed["citations"][0]["url"], headers=owner).text
        )
        copied = client.post(f"{url}/copy", headers=owner)
        assert copied.status_code == 201
        assert client.delete(detail, headers=owner).status_code == 204
        detail = f"/api/strixy/cases/{assigned}/conversations/{copied.json()['id']}"
