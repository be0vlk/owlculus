"""Display metadata stays behind the same record and copied-message policies."""

import pytest

from app.database.models import (
    CaseUserLink,
    Entity,
    Evidence,
    StrixyCopiedGrounding,
    StrixyMessage,
)
from app.services.strixy_sources import CaseSources
from tests.api import test_strixy_sources_api as fixtures

assigned = fixtures.assigned
session = fixtures.session
strixy = fixtures.strixy
restricted = fixtures.restricted
auth = fixtures.auth


def test_catalog_has_bounded_names_without_record_contents(
    client, assigned, analyst_token, session, test_analyst
):
    person = Entity(
        case_id=assigned,
        entity_type="person",
        data={"first_name": "Ada", "last_name": "Lovelace", "notes": "Private notes"},
        created_by_id=test_analyst.id,
    )
    company = Entity(
        case_id=assigned,
        entity_type="company",
        data={"name": "A" * 400},
        created_by_id=test_analyst.id,
    )
    evidence = Evidence(
        case_id=assigned,
        title="Registry extract.pdf",
        description="Contents should not be in the picker",
        evidence_type="file",
        content="private/storage/path.pdf",
        created_by_id=test_analyst.id,
    )
    session.add_all([person, company, evidence])
    session.commit()
    for record in (person, company, evidence):
        session.refresh(record)
    response = client.get(
        f"/api/strixy/cases/{assigned}/sources", headers=auth(analyst_token)
    )
    assert response.status_code == 200
    catalog = {item["source_id"]: item for item in response.json()["sources"]}
    assert catalog[f"entity:{person.id}"] == {
        "source_id": f"entity:{person.id}",
        "kind": "entity",
        "title": "Ada Lovelace",
        "subtitle": "Person",
    }
    assert len(catalog[f"entity:{company.id}"]["title"]) == 200
    assert catalog[f"evidence:{evidence.id}"]["title"] == "Registry extract.pdf"
    assert "Private notes" not in response.text
    assert "private/storage" not in response.text
    assert "Contents should not" not in response.text


@pytest.mark.parametrize("removed", ["human", "strixy"])
def test_catalog_never_names_a_record_after_either_reader_loses_access(
    client, assigned, analyst_token, session, test_analyst, strixy, restricted, removed
):
    url = f"/api/strixy/cases/{assigned}/sources"
    assert "Protected report" in client.get(url, headers=auth(analyst_token)).text
    user_id = test_analyst.id if removed == "human" else strixy.id
    session.delete(session.get(CaseUserLink, (restricted[0], user_id)))
    session.commit()
    response = client.get(url, headers=auth(analyst_token))
    assert response.status_code == 200
    assert "Protected report" not in response.text
    assert f"evidence:{restricted[1]}" not in response.text


def test_history_titles_use_the_first_owned_question_and_keep_empty_conversations(
    client, assigned, analyst_token, admin_token, session
):
    url = f"/api/strixy/cases/{assigned}/conversations"
    owner = auth(analyst_token)
    conversation = client.post(url, headers=owner).json()
    empty = client.post(url, headers=owner).json()
    session.add_all(
        [
            StrixyMessage(
                conversation_id=conversation["id"],
                position=0,
                role="user",
                content="  Who is\n  connected to Northstar?  ",
            ),
            StrixyMessage(
                conversation_id=conversation["id"],
                position=1,
                role="assistant",
                content="Never use an answer as a title",
            ),
            StrixyMessage(
                conversation_id=conversation["id"],
                position=2,
                role="user",
                content="Later question",
            ),
        ]
    )
    session.commit()
    history = {item["id"]: item for item in client.get(url, headers=owner).json()}
    assert history[conversation["id"]]["title"] == "Who is connected to Northstar?"
    assert history[empty["id"]]["title"] == "New conversation"
    assert client.get(url, headers=auth(admin_token)).json() == []


def test_copied_question_title_is_withheld_with_its_inherited_sources(
    client, assigned, analyst_token, session, test_analyst, strixy, restricted
):
    url = f"/api/strixy/cases/{assigned}/conversations"
    owner = auth(analyst_token)
    conversation = client.post(url, headers=owner).json()
    message = StrixyMessage(
        conversation_id=conversation["id"],
        position=0,
        role="user",
        content="Protected copied question about the report",
    )
    session.add(message)
    session.flush()
    source = CaseSources(session, test_analyst, assigned).read(
        f"evidence:{restricted[1]}"
    )
    session.add(
        StrixyCopiedGrounding(message_id=message.id, provenance=[source.reference()])
    )
    session.commit()
    assert client.get(url, headers=owner).json()[0]["title"] == message.content
    session.delete(session.get(CaseUserLink, (restricted[0], strixy.id)))
    session.commit()
    response = client.get(url, headers=owner)
    assert response.json()[0]["title"] == "Conversation unavailable"
    assert "Protected copied question" not in response.text
