"""Attachment bytes, locators and outcomes through real upload and Strixy APIs."""

import json

import pytest

from app.services.strixy_service import ProviderReply, StrixyService
from tests.api import test_strixy_conversations_api as fixtures
from tests.api.test_strixy_sources_api import new_conversation, turn

assigned = fixtures.assigned
configured = fixtures.configured
session = fixtures.session
strixy = fixtures.strixy


@pytest.mark.parametrize("first_format", ["unreadable", "office_warning"])
def test_continuation_passes_exhausted_attachment_gaps_to_later_records(
    client,
    assigned,
    configured,
    admin_token,
    analyst_token,
    engine,
    monkeypatch,
    first_format,
):
    from app.core.strixy_config import StrixyConfig
    from app.executions.strixy_worker import execute
    from tests.attachment_fixtures import office

    if first_format == "unreadable":
        name, data, mime = "broken.json", b'{"broken":', "application/json"
    else:
        name = "facts.xlsx"
        data, mime = office("xlsx")
    first = upload(client, assigned, admin_token, name, data, mime)
    later = upload(client, assigned, admin_token, "later.txt", b"Later witness found.")
    monkeypatch.setattr(
        "app.core.strixy_config.get_strixy_config",
        lambda _db: StrixyConfig(max_sources=3),
    )
    seen = []

    def reply(self, messages, config, timeout):
        seen.append(json.loads(messages[0].content))
        return ProviderReply("A permitted finding")

    monkeypatch.setattr(StrixyService, "generate", reply)
    detail, owner = new_conversation(client, assigned, analyst_token)
    saved = turn(client, detail, owner, engine)
    outcome = next(
        item
        for item in saved["runs"][-1]["source_coverage"]["attachment_outcomes"]
        if item["source_id"] == f"evidence:{first['id']}"
    )
    assert outcome["state"] == (
        "unavailable" if first_format == "unreadable" else "partly_read"
    )
    continued = client.post(
        f"{detail}/runs/{saved['runs'][-1]['id']}/continue", headers=owner
    )
    assert continued.status_code == 202, continued.text
    execute(continued.json()["id"], engine)
    assert any(
        source["source_id"] == f"evidence:{later['id']}"
        and source["fields"].get("attachment:line:1") == "Later witness found."
        for source in seen[-1]["sources"]
    )
    historical = client.get(detail, headers=owner).json()["runs"][0]
    assert (
        historical["source_coverage"]["attachment_outcomes"]
        == saved["runs"][0]["source_coverage"]["attachment_outcomes"]
    )


def test_retained_partial_marks_changed_attachment_without_rewriting_history(
    client, assigned, configured, admin_token, analyst_token, engine, monkeypatch
):
    from app.core import file_storage

    evidence = upload(
        client, assigned, admin_token, "witness.txt", b"Ada works at Acme."
    )

    def reply(self, messages, config, timeout):
        self.on_progress(
            ProviderReply(
                "The witness names Acme.",
                citations=[
                    {
                        "source_id": f"evidence:{evidence['id']}",
                        "field": "attachment:line:1",
                        "excerpt": "Ada works at Acme.",
                    }
                ],
            )
        )
        raise RuntimeError("Deterministic interrupted reply")

    monkeypatch.setattr(StrixyService, "generate", reply)
    detail, owner = new_conversation(client, assigned, analyst_token)
    saved = turn(client, detail, owner, engine)
    original = saved["runs"][0]["partial"]
    assert saved["runs"][0]["status"] == "failed"
    (file_storage.UPLOAD_DIR / evidence["content"]).write_bytes(
        b"Ada works at Otherco."
    )
    reopened = client.get(detail, headers=owner).json()["runs"][0]["partial"]
    assert reopened["content"] == original["content"]
    assert reopened["timestamp"] == original["timestamp"]
    assert reopened["citations"][0]["version"] == original["citations"][0]["version"]
    assert reopened["citations"][0].get("source_status") == "changed"
    assert client.get(reopened["citations"][0]["url"], headers=owner).status_code == 200


def upload(client, case_id, token, name, content, mime="text/plain"):
    folders = client.get(
        f"/api/evidence/case/{case_id}", headers=fixtures.auth(token)
    ).json()
    if not any(item["is_folder"] for item in folders):
        folder = client.post(
            "/api/evidence/folders",
            headers=fixtures.auth(token),
            json={"case_id": case_id, "title": "Documents"},
        )
        assert folder.status_code == 201, folder.text
    response = client.post(
        "/api/evidence/",
        params={"title": name, "case_id": case_id, "category": "Documents"},
        headers=fixtures.auth(token),
        data={"description": "Metadata only: employment unknown"},
        files={"files": (name, content, mime)},
    )
    assert response.status_code == 201, response.text
    assert not response.json()["failed"], response.text
    return response.json()["created"][0]


def test_uploaded_text_bytes_are_read_and_cited(
    client, assigned, configured, admin_token, analyst_token, engine, monkeypatch
):
    evidence = upload(
        client,
        assigned,
        admin_token,
        "witness.txt",
        b"Ada works at Acme.\nEmployer disputed.",
    )

    def reply(self, messages, config, timeout):
        context = json.loads(messages[0].content)
        source = next(
            s
            for s in context["sources"]
            if s["source_id"] == f"evidence:{evidence['id']}"
        )
        assert source["fields"]["attachment:line:1"] == "Ada works at Acme."
        assert source["attachment"]["state"] == "read"
        return ProviderReply(
            "Employment is disputed.",
            citations=[
                {
                    "source_id": source["source_id"],
                    "field": "attachment:line:2",
                    "excerpt": "Employer disputed.",
                }
            ],
        )

    monkeypatch.setattr(StrixyService, "generate", reply)
    detail, owner = new_conversation(client, assigned, analyst_token)
    saved = turn(client, detail, owner, engine)
    assert saved["runs"][-1]["status"] == "completed", saved
    answer = saved["messages"][-1]
    assert answer["coverage"]["attachments"] == "examined"
    assert answer["coverage"]["complete"]
    assert answer["citations"][0]["field"] == "attachment:line:2"
    assert client.get(answer["citations"][0]["url"], headers=owner).status_code == 200
    assert (
        client.get(f"/api/evidence/{evidence['id']}/download", headers=owner).content
        == b"Ada works at Acme.\nEmployer disputed."
    )


@pytest.mark.parametrize(
    "name,mime,data,locator,expected",
    [
        (
            "facts.json",
            "application/json",
            b'{"person":{"name":"Ada","employer":"Acme"}}',
            "attachment:json:/person/employer",
            '"Acme"',
        ),
        (
            "facts.csv",
            "text/csv",
            b"name,employer\nAda,Acme\n",
            "attachment:row:2",
            '["Ada", "Acme"]',
        ),
    ],
)
def test_structured_uploads_preserve_fields_and_rows(
    client,
    assigned,
    configured,
    admin_token,
    analyst_token,
    engine,
    monkeypatch,
    name,
    mime,
    data,
    locator,
    expected,
):
    evidence = upload(client, assigned, admin_token, name, data, mime)

    def reply(self, messages, config, timeout):
        source = next(
            s
            for s in json.loads(messages[0].content)["sources"]
            if s["source_id"] == f"evidence:{evidence['id']}"
        )
        assert source["fields"][locator] == expected
        return ProviderReply(
            "Known employer",
            citations=[
                {"source_id": source["source_id"], "field": locator, "excerpt": "Acme"}
            ],
        )

    monkeypatch.setattr(StrixyService, "generate", reply)
    detail, owner = new_conversation(client, assigned, analyst_token)
    saved = turn(client, detail, owner, engine)
    assert saved["runs"][-1]["status"] == "completed", saved
    assert saved["messages"][-1]["citations"][0]["field"] == locator


@pytest.mark.parametrize(
    "extension,locator",
    [
        ("docx", "attachment:document:paragraph:1"),
        ("xlsx", "attachment:sheet:Witnesses:row:1"),
        ("pptx", "attachment:slide:1:paragraph:1"),
    ],
)
def test_office_bytes_preserve_document_sheet_and_slide_locators(
    client,
    assigned,
    configured,
    admin_token,
    analyst_token,
    engine,
    monkeypatch,
    extension,
    locator,
):
    from tests.attachment_fixtures import office

    data, mime = office(extension)
    evidence = upload(client, assigned, admin_token, "witness." + extension, data, mime)
    seen = []

    def reply(self, messages, config, timeout):
        source = next(
            s
            for s in json.loads(messages[0].content)["sources"]
            if s["source_id"] == f"evidence:{evidence['id']}"
        )
        seen.append(source)
        assert "Acme" in source["fields"][locator]
        return ProviderReply(
            "Employer recorded",
            citations=[
                {"source_id": source["source_id"], "field": locator, "excerpt": "Acme"}
            ],
        )

    monkeypatch.setattr(StrixyService, "generate", reply)
    detail, owner = new_conversation(client, assigned, analyst_token)
    saved = turn(client, detail, owner, engine)
    assert saved["runs"][-1]["status"] == "completed", saved
    assert saved["messages"][-1]["citations"][0]["field"] == locator
    if extension == "xlsx":
        assert (
            "formula (not evaluated)"
            in seen[0]["fields"]["attachment:sheet:Witnesses:row:2"]
        )


@pytest.mark.parametrize(
    "name,data,reason",
    [
        ("bad.json", b'{"missing":', "unreadable_file"),
        ("duplicate.json", b'{"key":1,"key":2}', "unreadable_file"),
        ("bad.csv", b'a,b\n"unterminated', "unreadable_file"),
        ("big.txt", b"A" * 101, "attachment_size_limit"),
        ("partial.txt", b"first\nsecond\nthird", "attachment_unit_limit"),
        ("unsupported.html", b"<p>Unexamined</p>", "unsupported_format"),
    ],
)
def test_preparation_failures_are_explicit_and_metadata_remains_available(
    client,
    assigned,
    configured,
    admin_token,
    analyst_token,
    engine,
    monkeypatch,
    name,
    data,
    reason,
):
    from app.core.strixy_config import StrixyConfig

    monkeypatch.setattr(
        "app.core.strixy_config.get_strixy_config",
        lambda _db: StrixyConfig(attachment_max_bytes=100, attachment_max_units=2),
    )
    evidence = upload(client, assigned, admin_token, name, data)
    contexts = []

    def reply(self, messages, config, timeout):
        contexts.append(json.loads(messages[0].content))
        return ProviderReply("Some material could not be examined")

    monkeypatch.setattr(StrixyService, "generate", reply)
    detail, owner = new_conversation(client, assigned, analyst_token)
    saved = turn(client, detail, owner, engine)
    assert saved["runs"][-1]["status"] == "completed", saved
    outcome = saved["messages"][-1]["coverage"]["attachment_outcomes"][0]
    assert outcome["reason"] == reason
    assert not saved["messages"][-1]["coverage"]["complete"]
    source = next(
        s
        for s in contexts[0]["sources"]
        if s["source_id"] == f"evidence:{evidence['id']}"
    )
    assert "Metadata only" in source["fields"]["description"]
    if name == "partial.txt":
        assert source["fields"]["attachment:line:2"] == "second"
        assert "attachment:line:3" not in source["fields"]
    else:
        assert not any(key.startswith("attachment:") for key in source["fields"])


def test_attachment_unit_limit_continues_at_next_line(
    client, assigned, configured, admin_token, analyst_token, engine, monkeypatch
):
    from app.core.strixy_config import StrixyConfig
    from app.executions.strixy_worker import execute

    monkeypatch.setattr(
        "app.core.strixy_config.get_strixy_config",
        lambda _db: StrixyConfig(attachment_max_units=2),
    )
    evidence = upload(
        client, assigned, admin_token, "long.txt", b"first\nsecond\nthird\nfourth"
    )
    contexts = []

    def reply(self, messages, config, timeout):
        contexts.append(json.loads(messages[0].content))
        return ProviderReply("Bounded findings")

    monkeypatch.setattr(StrixyService, "generate", reply)
    detail, owner = new_conversation(client, assigned, analyst_token)
    first = turn(client, detail, owner, engine)
    continued = client.post(
        f"{detail}/runs/{first['runs'][-1]['id']}/continue", headers=owner
    )
    assert continued.status_code == 202, continued.text
    execute(continued.json()["id"], engine)
    saved = client.get(detail, headers=owner).json()
    assert saved["runs"][-1]["status"] == "completed", saved
    fields = next(
        s["fields"]
        for s in contexts[-1]["sources"]
        if s["source_id"] == f"evidence:{evidence['id']}"
    )
    assert fields["attachment:line:3"] == "third"
    assert "attachment:line:1" not in fields
    assert saved["messages"][1]["content"] == first["messages"][1]["content"]


def test_legacy_doc_text_is_read_with_extraction_locators(
    client, assigned, configured, admin_token, analyst_token, engine, monkeypatch
):
    from pathlib import Path

    data = (Path(__file__).parents[1] / "fixtures/strixy/witness.doc").read_bytes()
    evidence = upload(
        client, assigned, admin_token, "witness.doc", data, "application/msword"
    )

    def reply(self, messages, config, timeout):
        source = next(
            s
            for s in json.loads(messages[0].content)["sources"]
            if s["source_id"] == f"evidence:{evidence['id']}"
        )
        locator, _text = next(
            (key, value)
            for key, value in source["fields"].items()
            if key.startswith("attachment:") and "Acme" in value
        )
        assert locator.startswith("attachment:extracted-line:")
        return ProviderReply(
            "Employer recorded",
            citations=[
                {"source_id": source["source_id"], "field": locator, "excerpt": "Acme"}
            ],
        )

    monkeypatch.setattr(StrixyService, "generate", reply)
    detail, owner = new_conversation(client, assigned, analyst_token)
    saved = turn(client, detail, owner, engine)
    assert saved["runs"][-1]["status"] == "completed", saved
    assert saved["messages"][-1]["coverage"]["attachment_outcomes"][0]["warnings"] == [
        "legacy_layout_and_visuals_unexamined"
    ]


@pytest.mark.parametrize(
    "race", ["changed_bytes", "delete_conversation", "revoke_membership"]
)
def test_attachment_output_is_fenced_and_temporary_resources_are_cleaned(
    client,
    assigned,
    configured,
    admin_token,
    analyst_token,
    engine,
    session,
    strixy,
    monkeypatch,
    tmp_path,
    race,
):
    from app.core import file_storage
    from app.database.models import CaseUserLink

    temporary = tmp_path / "preparation"
    temporary.mkdir()
    monkeypatch.setattr("tempfile.tempdir", str(temporary))
    evidence = upload(
        client, assigned, admin_token, "witness.txt", b"Secret attachment finding"
    )
    detail, owner = new_conversation(client, assigned, analyst_token)

    def reply(self, messages, config, timeout):
        assert "Secret attachment finding" in messages[0].content
        assert list(temporary.iterdir()) == []
        if race == "changed_bytes":
            (file_storage.UPLOAD_DIR / evidence["content"]).write_bytes(
                b"Changed attachment finding"
            )
        elif race == "delete_conversation":
            assert client.delete(detail, headers=owner).status_code == 204
        else:
            session.delete(session.get(CaseUserLink, (assigned, strixy.id)))
            session.commit()
        return ProviderReply("Late secret inference")

    monkeypatch.setattr(StrixyService, "generate", reply)
    from app.executions.strixy_worker import execute

    accepted = client.post(
        f"{detail}/messages", headers=owner, json={"content": "Read the attachments"}
    )
    assert accepted.status_code == 202
    execute(accepted.json()["id"], engine)
    saved = client.get(detail, headers=owner)
    assert "Late secret inference" not in saved.text
    assert list(temporary.iterdir()) == []
    assert (file_storage.UPLOAD_DIR / evidence["content"]).exists()


def test_changed_attachment_invalidates_history_and_discovers_new_uploads(
    client, assigned, configured, admin_token, analyst_token, engine, monkeypatch
):
    from app.core import file_storage

    evidence = upload(
        client, assigned, admin_token, "witness.txt", b"Earlier employer: Acme"
    )
    contexts = []

    def reply(self, messages, config, timeout):
        contexts.append([m.content for m in messages])
        source = next(
            s
            for s in json.loads(messages[0].content)["sources"]
            if s["source_id"] == f"evidence:{evidence['id']}"
        )
        text = source["fields"]["attachment:line:1"]
        return ProviderReply(
            "Historical inference",
            citations=[
                {
                    "source_id": source["source_id"],
                    "field": "attachment:line:1",
                    "excerpt": text,
                }
            ],
        )

    monkeypatch.setattr(StrixyService, "generate", reply)
    detail, owner = new_conversation(client, assigned, analyst_token)
    first = turn(client, detail, owner, engine)["messages"][-1]
    (file_storage.UPLOAD_DIR / evidence["content"]).write_bytes(
        b"Current employer: Other"
    )
    upload(
        client, assigned, admin_token, "new.txt", b"New witness contradicts employer"
    )
    saved = client.get(detail, headers=owner).json()["messages"][-1]
    assert (
        saved["content"] == first["content"]
        and saved["timestamp"] == first["timestamp"]
    )
    assert saved["citations"][0]["source_status"] == "changed"
    turn(client, detail, owner, engine)
    assert "Historical inference" not in contexts[-1]
    assert "Current employer: Other" in contexts[-1][0]
    assert "New witness contradicts employer" in contexts[-1][0]


@pytest.mark.parametrize("removed", ["human", "strixy"])
def test_uncited_attachment_bytes_keep_protected_evidence_scope(
    client,
    assigned,
    configured,
    admin_token,
    analyst_token,
    engine,
    session,
    test_analyst,
    strixy,
    monkeypatch,
    removed,
):
    from app.database.models import Case, CaseUserLink, CorrelationEvidence

    other = Case(case_number="SECRET-ATTACHMENT", title="Protected")
    session.add(other)
    session.flush()
    for user in (strixy, test_analyst):
        session.add(CaseUserLink(case_id=other.id, user_id=user.id))
    evidence = upload(
        client,
        assigned,
        admin_token,
        "protected.txt",
        b"Protected uncited attachment input",
    )
    session.add(
        CorrelationEvidence(evidence_id=evidence["id"], case_ids=[assigned, other.id])
    )
    session.commit()
    contexts = []

    def reply(self, messages, config, timeout):
        contexts.append([m.content for m in messages])
        return ProviderReply(
            "Protected deduction" if len(contexts) == 1 else "Permitted findings"
        )

    monkeypatch.setattr(StrixyService, "generate", reply)
    detail, owner = new_conversation(client, assigned, analyst_token)
    first = turn(client, detail, owner, engine)
    assert "Protected uncited attachment input" in contexts[0][0]
    session.delete(
        session.get(
            CaseUserLink,
            (other.id, test_analyst.id if removed == "human" else strixy.id),
        )
    )
    session.commit()
    saved = client.get(detail, headers=owner)
    assert "Protected deduction" not in saved.text
    assert "attachment_outcomes" not in json.dumps(saved.json()["messages"][-1])
    observed = client.get(f"{detail}/runs/{first['runs'][-1]['id']}", headers=owner)
    assert "evidence:" not in observed.text
    turn(client, detail, owner, engine)
    assert "Protected uncited attachment input" not in contexts[-1][0]
    assert "Protected deduction" not in contexts[-1]


@pytest.mark.parametrize(
    "variant",
    ["expansion", "doc_expansion", "encrypted", "entity", "visual", "invalid_locator"],
)
def test_office_processing_limits_and_untrusted_contents(
    client,
    assigned,
    configured,
    admin_token,
    analyst_token,
    engine,
    monkeypatch,
    variant,
):
    from pathlib import Path

    from app.core.strixy_config import StrixyConfig
    from tests.attachment_fixtures import office

    if variant == "doc_expansion":
        data = (Path(__file__).parents[1] / "fixtures/strixy/witness.doc").read_bytes()
        mime, extension = "application/msword", "doc"
        monkeypatch.setattr(
            "app.core.strixy_config.get_strixy_config",
            lambda _db: StrixyConfig(attachment_max_expanded_bytes=100),
        )
    elif variant == "encrypted":
        import io

        import olefile

        stream = io.BytesIO(
            (Path(__file__).parents[1] / "fixtures/strixy/witness.doc").read_bytes()
        )
        with olefile.OleFileIO(stream, write_mode=True) as compound:
            word = bytearray(compound.openstream("WordDocument").read())
            word[11] |= 1
            compound.write_stream("WordDocument", bytes(word))
        data, mime, extension = stream.getvalue(), "application/msword", "doc"
    else:
        extra = {}
        if variant == "expansion":
            extra["word/media/oversized.bin"] = b"A" * 5000
            monkeypatch.setattr(
                "app.core.strixy_config.get_strixy_config",
                lambda _db: StrixyConfig(attachment_max_expanded_bytes=4000),
            )
        elif variant == "entity":
            extra["word/document.xml"] = (
                '<!DOCTYPE document [<!ENTITY secret SYSTEM "file:///etc/passwd">]><document>&secret;</document>'
            )
        elif variant == "visual":
            extra["word/media/image.png"] = b"synthetic-unexamined-visual"
        data, mime = office("docx", extra=extra)
        extension = "docx"
    evidence = upload(client, assigned, admin_token, "test." + extension, data, mime)
    seen = []

    def reply(self, messages, config, timeout):
        seen.append(json.loads(messages[0].content))
        citations = []
        if variant == "invalid_locator":
            citations = [
                {
                    "source_id": f"evidence:{evidence['id']}",
                    "field": "attachment:document:paragraph:999",
                    "excerpt": "Acme",
                }
            ]
        return ProviderReply("Permitted partial findings", citations=citations)

    monkeypatch.setattr(StrixyService, "generate", reply)
    detail, owner = new_conversation(client, assigned, analyst_token)
    saved = turn(client, detail, owner, engine)
    if variant == "invalid_locator":
        assert saved["messages"][-1]["citations"] == []
        assert saved["messages"][-1]["coverage"]["unverified_citations"] == 1
        return
    assert saved["runs"][-1]["status"] == "completed", saved
    outcome = saved["messages"][-1]["coverage"]["attachment_outcomes"][0]
    assert (
        outcome["reason"]
        == {
            "expansion": "attachment_expansion_limit",
            "doc_expansion": "attachment_expansion_limit",
            "encrypted": "encrypted_file",
            "entity": "unreadable_file",
            "visual": "content_unexamined",
        }[variant]
    )
    assert "root:" not in json.dumps(seen)
    if variant == "visual":
        assert outcome["state"] == "partly_read"
        assert "visual_or_embedded_content_unexamined" in outcome["warnings"]


def test_attachment_path_cannot_escape_its_case(
    client,
    assigned,
    configured,
    analyst_token,
    admin_token,
    session,
    engine,
    monkeypatch,
    tmp_path,
):
    from app.database.models import Evidence

    outside = tmp_path / "outside.txt"
    outside.write_text("Foreign file secret")
    evidence = upload(client, assigned, admin_token, "witness.txt", b"Original content")
    row = session.get(Evidence, evidence["id"])
    row.content = str(outside)
    session.add(row)
    session.commit()
    contexts = []

    def reply(self, messages, config, timeout):
        contexts.append(messages[0].content)
        return ProviderReply("Metadata only")

    monkeypatch.setattr(StrixyService, "generate", reply)
    detail, owner = new_conversation(client, assigned, analyst_token)
    saved = turn(client, detail, owner, engine)
    assert "Foreign file secret" not in contexts[0]
    assert (
        saved["messages"][-1]["coverage"]["attachment_outcomes"][0]["reason"]
        == "file_unavailable"
    )


def test_json_container_types_and_inherited_slide_coverage_are_preserved(
    client, assigned, configured, admin_token, analyst_token, engine, monkeypatch
):
    from tests.attachment_fixtures import office

    upload(
        client,
        assigned,
        admin_token,
        "containers.json",
        b'{"object":{"0":"x"},"array":["x"]}',
        "application/json",
    )
    data, mime = office(
        "pptx",
        extra={
            "ppt/slides/_rels/slide1.xml.rels": '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="layout" Target="../slideLayouts/slideLayout1.xml"/></Relationships>',
            "ppt/slideLayouts/slideLayout1.xml": "<layout>Inherited unexamined text</layout>",
        },
    )
    upload(client, assigned, admin_token, "inherited.pptx", data, mime)
    contexts = []

    def reply(self, messages, config, timeout):
        contexts.append(json.loads(messages[0].content))
        return ProviderReply("Structured findings")

    monkeypatch.setattr(StrixyService, "generate", reply)
    detail, owner = new_conversation(client, assigned, analyst_token)
    saved = turn(client, detail, owner, engine)
    assert saved["runs"][-1]["status"] == "completed", saved
    structured = next(
        s
        for s in contexts[0]["sources"]
        if "attachment:json-type:/object" in s["fields"]
    )
    assert structured["fields"]["attachment:json-type:/object"] == "object"
    assert structured["fields"]["attachment:json-type:/array"] == "array"
    outcomes = saved["messages"][-1]["coverage"]["attachment_outcomes"]
    assert any(
        "inherited_slide_content_unexamined" in o.get("warnings", []) for o in outcomes
    )
    assert not saved["messages"][-1]["coverage"]["complete"]


def test_preparation_timeout_is_bounded_and_cleans_parser_snapshots(
    client,
    assigned,
    configured,
    admin_token,
    analyst_token,
    engine,
    monkeypatch,
    tmp_path,
):
    from app.core.strixy_config import StrixyConfig

    temporary = tmp_path / "parser-temporary"
    temporary.mkdir()
    monkeypatch.setattr("tempfile.tempdir", str(temporary))
    monkeypatch.setattr(
        "app.core.strixy_config.get_strixy_config",
        lambda _db: StrixyConfig(
            attachment_seconds=1, attachment_max_expanded_bytes=200_000_000
        ),
    )
    # Valid JSON forces real parsing/traversal well beyond the one-second budget.
    # No parser, clock, permission or storage fake is installed.
    data = b"[" + b"0," * 3_999_999 + b"0]"
    upload(client, assigned, admin_token, "slow.json", data, "application/json")
    upload(client, assigned, admin_token, "later.txt", b"Later input")
    monkeypatch.setattr(
        StrixyService,
        "generate",
        lambda *args: ProviderReply("Preparation was incomplete"),
    )
    detail, owner = new_conversation(client, assigned, analyst_token)
    saved = turn(client, detail, owner, engine)
    assert saved["runs"][-1]["status"] == "completed", saved
    outcomes = saved["messages"][-1]["coverage"]["attachment_outcomes"]
    assert outcomes[0]["reason"] == "attachment_time_limit"
    assert outcomes[1]["reason"] == "attachment_time_limit"
    assert list(temporary.iterdir()) == []
