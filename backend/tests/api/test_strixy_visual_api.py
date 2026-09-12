"""Real visual preparation and authorization through upload and durable chat APIs."""

import io
import json

import pytest
from PIL import Image

from app.services.strixy_service import ProviderReply, StrixyService
from tests.api import test_strixy_attachments_api as fixtures
from tests.api.test_strixy_attachments_api import upload
from tests.api.test_strixy_sources_api import new_conversation, turn
from tests.attachment_fixtures import document, screenshot

assigned = fixtures.assigned
configured = fixtures.configured
session = fixtures.session
storage_root = fixtures.storage_root
strixy = fixtures.strixy


def test_mixed_pdf_supplies_text_and_real_page_images_with_validated_citations(
    client, assigned, configured, admin_token, analyst_token, engine, monkeypatch
):
    original = document()
    evidence = upload(
        client, assigned, admin_token, "mixed.pdf", original, "application/pdf"
    )
    seen = []

    def reply(self, messages, config, timeout):
        source = next(
            s
            for s in json.loads(messages[0].content)["sources"]
            if s["source_id"] == f"evidence:{evidence['id']}"
        )
        visuals = getattr(messages[0], "images", [])
        assert len(visuals) == 2
        assert [v.field for v in visuals] == [
            "attachment:page:1:image",
            "attachment:page:2:image",
        ]
        for visual in visuals:
            assert visual.source_id == f"evidence:{evidence['id']}"
            import base64

            with Image.open(io.BytesIO(base64.b64decode(visual.data))) as image:
                assert image.width > 500 and image.height > 500
        assert "Otherco" in source["fields"]["attachment:page:1:text"]
        assert not source["fields"].get("attachment:page:2:text")
        seen.append(source)
        return ProviderReply(
            "Employer accounts conflict; corroboration is missing.",
            citations=[
                {
                    "source_id": source["source_id"],
                    "field": "attachment:page:1:text",
                    "excerpt": "Otherco",
                },
                {
                    "source_id": source["source_id"],
                    "field": "attachment:page:2:image",
                    "excerpt": "",
                },
            ],
        )

    monkeypatch.setattr(StrixyService, "generate", reply)
    detail, owner = new_conversation(client, assigned, analyst_token)
    saved = turn(client, detail, owner, engine)
    assert saved["runs"][-1]["status"] == "completed", json.dumps(saved["runs"])
    assert seen
    answer = saved["messages"][-1]
    assert answer["coverage"]["attachments"] == "examined"
    assert answer["citations"][1]["kind"] == "visual"
    preview = client.get(answer["citations"][1]["url"], headers=owner)
    assert preview.status_code == 200
    assert preview.json()["images"][0]["field"] == "attachment:page:2:image"
    assert (
        client.get(f"/api/evidence/{evidence['id']}/download", headers=owner).content
        == original
    )
    assert client.get(detail, headers=owner).json() == saved


@pytest.mark.parametrize(
    "extension,format,mime",
    [
        ("png", "PNG", "image/png"),
        ("jpg", "JPEG", "image/jpeg"),
        ("webp", "WEBP", "image/webp"),
    ],
)
def test_images_reach_model_as_pixels_not_metadata(
    client,
    assigned,
    configured,
    admin_token,
    analyst_token,
    engine,
    monkeypatch,
    extension,
    format,
    mime,
):
    upload(
        client, assigned, admin_token, "screen." + extension, screenshot(format), mime
    )
    seen = []

    def reply(self, messages, config, timeout):
        visual = messages[0].images[0]
        seen.append(visual)
        return ProviderReply(
            "The screenshot links Ada to Acme, but identity is uncertain.",
            citations=[
                {"source_id": visual.source_id, "field": visual.field, "excerpt": ""},
            ],
        )

    monkeypatch.setattr(StrixyService, "generate", reply)
    detail, owner = new_conversation(client, assigned, analyst_token)
    saved = turn(client, detail, owner, engine)
    assert saved["runs"][-1]["status"] == "completed"
    assert len(seen) == 1 and seen[0].field == "attachment:image:1"
    assert saved["messages"][-1]["coverage"]["attachments"] == "examined"
    assert seen[0].data not in json.dumps(saved)


@pytest.mark.parametrize(
    "scenario,reason",
    [
        ("pages", "attachment_unit_limit"),
        ("bytes", "visual_input_limit"),
        ("pixels", "visual_pixel_limit"),
        ("encrypted", "encrypted_file"),
        ("damaged", "unreadable_file"),
        ("disabled", "vision_unavailable"),
        ("resize", "visual_resolution_reduced"),
    ],
)
def test_visual_processing_reports_actual_page_coverage(
    client,
    assigned,
    configured,
    admin_token,
    analyst_token,
    engine,
    monkeypatch,
    scenario,
    reason,
):
    from pypdf import PdfReader, PdfWriter

    from app.core.strixy_config import StrixyConfig

    data = document(("text", "scan", "text"))
    overrides = {}
    if scenario == "pages":
        overrides = {"visual_max_images": 1}
    if scenario == "bytes":
        overrides = {"visual_max_input_bytes": 20}
    if scenario == "pixels":
        overrides = {"visual_max_pixels": 100}
    if scenario == "disabled":
        overrides = {"supports_vision": False}
    if scenario == "resize":
        overrides = {"visual_max_dimension": 256}
    if scenario == "damaged":
        data = b"%PDF-1.7\nDamaged file"
    if scenario == "encrypted":
        writer = PdfWriter(clone_from=PdfReader(io.BytesIO(data)))
        writer.encrypt("private")
        output = io.BytesIO()
        writer.write(output)
        data = output.getvalue()
    monkeypatch.setattr(
        "app.core.strixy_config.get_strixy_config", lambda: StrixyConfig(**overrides)
    )
    upload(client, assigned, admin_token, "pages.pdf", data, "application/pdf")
    images = []

    def reply(self, messages, config, timeout):
        images.extend(messages[0].images)
        return ProviderReply("Some material could not be examined.")

    monkeypatch.setattr(StrixyService, "generate", reply)
    detail, owner = new_conversation(client, assigned, analyst_token)
    saved = turn(client, detail, owner, engine)
    assert saved["runs"][-1]["status"] == "completed"
    outcome = saved["messages"][-1]["coverage"]["attachment_outcomes"][0]
    assert outcome["state"] != "read" and outcome["reason"] == reason
    assert not saved["messages"][-1]["coverage"]["complete"]
    if scenario == "pages":
        assert len(images) == 1
        assert outcome["pages"] == [{"unit": 1, "state": "read", "reason": None}]
        assert outcome["unexamined_from"] == 2 and outcome["total_units"] == 3
        from app.executions.strixy_worker import execute

        response = client.post(
            f"{detail}/runs/{saved['runs'][-1]['id']}/continue", headers=owner
        )
        assert response.status_code == 202, response.text
        execute(response.json()["id"], engine)
        assert images[-1].field == "attachment:page:2:image"
    elif scenario != "resize":
        assert images == []


@pytest.mark.parametrize(
    "field,excerpt",
    [
        ("attachment:page:99:image", ""),
        ("attachment:page:1:image", "Invented OCR"),
        ("attachment:page:2:image", ""),
    ],
)
def test_visual_citations_require_a_supplied_page_and_never_verify_ocr(
    client,
    assigned,
    configured,
    admin_token,
    analyst_token,
    engine,
    monkeypatch,
    field,
    excerpt,
):
    from app.core.strixy_config import StrixyConfig

    monkeypatch.setattr(
        "app.core.strixy_config.get_strixy_config",
        lambda: StrixyConfig(visual_max_images=1),
    )
    evidence = upload(
        client, assigned, admin_token, "pages.pdf", document(), "application/pdf"
    )
    monkeypatch.setattr(
        StrixyService,
        "generate",
        lambda *args: ProviderReply(
            "Invented finding",
            citations=[
                {
                    "source_id": f"evidence:{evidence['id']}",
                    "field": field,
                    "excerpt": excerpt,
                },
            ],
        ),
    )
    detail, owner = new_conversation(client, assigned, analyst_token)
    saved = turn(client, detail, owner, engine)
    assert saved["runs"][-1]["error_code"] == "invalid_citation"
    assert all(m["role"] == "user" for m in saved["messages"])


@pytest.mark.parametrize(
    "race", ["changed_bytes", "delete_conversation", "revoke_membership"]
)
def test_visual_work_cannot_publish_after_revocation_change_or_deletion(
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
    from app.executions.strixy_worker import execute

    temporary = tmp_path / "preparation"
    temporary.mkdir()
    monkeypatch.setattr("tempfile.tempdir", str(temporary))
    evidence = upload(
        client, assigned, admin_token, "screen.png", screenshot(), "image/png"
    )
    detail, owner = new_conversation(client, assigned, analyst_token)
    seen = []

    def reply(self, messages, config, timeout):
        seen.extend(messages[0].images)
        assert list(temporary.iterdir()) == []
        if race == "changed_bytes":
            (file_storage.UPLOAD_DIR / evidence["content"]).write_bytes(
                screenshot("JPEG")
            )
        elif race == "delete_conversation":
            assert client.delete(detail, headers=owner).status_code == 204
        else:
            session.delete(session.get(CaseUserLink, (assigned, strixy.id)))
            session.commit()
        return ProviderReply("Late visual finding")

    monkeypatch.setattr(StrixyService, "generate", reply)
    accepted = client.post(
        f"{detail}/messages", headers=owner, json={"content": "Read the image"}
    )
    execute(accepted.json()["id"], engine)
    assert seen
    assert "Late visual finding" not in client.get(detail, headers=owner).text
    assert list(temporary.iterdir()) == []
    assert (file_storage.UPLOAD_DIR / evidence["content"]).exists()


@pytest.mark.parametrize("removed", ["human", "strixy"])
def test_uncited_visual_input_protects_saved_output_and_followup_context(
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

    other = Case(case_number="VISUAL-PROTECTED", title="Protected")
    session.add(other)
    session.flush()
    for user in (strixy, test_analyst):
        session.add(CaseUserLink(case_id=other.id, user_id=user.id))
    evidence = upload(
        client, assigned, admin_token, "protected.png", screenshot(), "image/png"
    )
    session.add(
        CorrelationEvidence(evidence_id=evidence["id"], case_ids=[assigned, other.id])
    )
    session.commit()
    contexts = []

    def reply(self, messages, config, timeout):
        contexts.append(messages)
        return ProviderReply(
            "Protected visual inference" if len(contexts) == 1 else "Permitted findings"
        )

    monkeypatch.setattr(StrixyService, "generate", reply)
    detail, owner = new_conversation(client, assigned, analyst_token)
    saved = turn(client, detail, owner, engine)
    assert len(contexts[0][0].images) == 1
    session.delete(
        session.get(
            CaseUserLink,
            (other.id, test_analyst.id if removed == "human" else strixy.id),
        )
    )
    session.commit()
    assert "Protected visual inference" not in client.get(detail, headers=owner).text
    preview = client.get(
        f"/api/strixy/cases/{assigned}/sources/evidence:{evidence['id']}", headers=owner
    )
    assert preview.status_code == 403
    assert contexts[0][0].images[0].data not in preview.text
    observed = client.get(f"{detail}/runs/{saved['runs'][-1]['id']}", headers=owner)
    assert "evidence:" not in observed.text
    turn(client, detail, owner, engine)
    assert contexts[-1][0].images == []
    assert all("Protected visual inference" not in m.content for m in contexts[-1])


def test_visual_byte_limit_continuation_advances_without_repeating_first_page(
    client,
    assigned,
    configured,
    admin_token,
    analyst_token,
    engine,
    monkeypatch,
):
    from app.core.strixy_config import StrixyConfig
    from app.executions.strixy_worker import execute

    monkeypatch.setattr(
        "app.core.strixy_config.get_strixy_config",
        lambda: StrixyConfig(visual_max_input_bytes=40000),
    )
    upload(client, assigned, admin_token, "mixed.pdf", document(), "application/pdf")
    seen = []

    def reply(self, messages, config, timeout):
        seen.append([v.field for v in messages[0].images])
        return ProviderReply("Partial visual findings.")

    monkeypatch.setattr(StrixyService, "generate", reply)
    detail, owner = new_conversation(client, assigned, analyst_token)
    first = turn(client, detail, owner, engine)
    outcome = first["messages"][-1]["coverage"]["attachment_outcomes"][0]
    assert outcome["reason"] == "visual_input_limit"
    assert outcome["unexamined_from"] == 2
    accepted = client.post(
        f"{detail}/runs/{first['runs'][-1]['id']}/continue", headers=owner
    )
    assert accepted.status_code == 202
    execute(accepted.json()["id"], engine)
    assert seen == [["attachment:page:1:image"], ["attachment:page:2:image"]]


def test_completed_visual_answers_keep_history_but_new_questions_use_current_pixels(
    client,
    assigned,
    configured,
    admin_token,
    analyst_token,
    engine,
    monkeypatch,
):
    from app.core import file_storage

    evidence = upload(
        client, assigned, admin_token, "screen.png", screenshot(), "image/png"
    )
    seen = []

    def reply(self, messages, config, timeout):
        visuals = messages[0].images
        seen.append(visuals)
        return ProviderReply(
            "Visual interpretation " + str(len(seen)),
            citations=[
                {"source_id": v.source_id, "field": v.field, "excerpt": ""}
                for v in visuals
            ],
        )

    monkeypatch.setattr(StrixyService, "generate", reply)
    detail, owner = new_conversation(client, assigned, analyst_token)
    first = turn(client, detail, owner, engine)["messages"][-1]
    path = file_storage.UPLOAD_DIR / evidence["content"]
    path.write_bytes(screenshot(label="Ada -> Otherco"))
    historical = client.get(detail, headers=owner).json()["messages"][-1]
    assert historical["content"] == first["content"]
    assert historical["timestamp"] == first["timestamp"]
    assert (
        historical["citations"][0]["inspected_at"]
        == first["citations"][0]["inspected_at"]
    )
    assert historical["citations"][0]["source_status"] == "changed"
    upload(
        client, assigned, admin_token, "new.pdf", document(("text",)), "application/pdf"
    )
    second = turn(client, detail, owner, engine)
    assert seen[0][0].data != seen[1][0].data
    assert len(seen[1]) == 2
    assert second["messages"][1] == historical
    path.unlink()
    third = turn(client, detail, owner, engine)
    assert len(seen[2]) == 1
    assert any(
        o["reason"] == "file_unavailable"
        for o in third["messages"][-1]["coverage"]["attachment_outcomes"]
    )


@pytest.mark.parametrize("limit", ["count", "tokens"])
def test_multiple_images_share_run_budgets(
    client,
    assigned,
    configured,
    admin_token,
    analyst_token,
    engine,
    monkeypatch,
    limit,
):
    from app.core.strixy_config import StrixyConfig

    config = (
        StrixyConfig(visual_max_images=1)
        if limit == "count"
        else StrixyConfig(max_total_input_tokens=8000)
    )
    monkeypatch.setattr("app.core.strixy_config.get_strixy_config", lambda: config)
    for name in ("one.png", "two.png"):
        upload(client, assigned, admin_token, name, screenshot(), "image/png")
    seen = []

    def reply(self, messages, config, timeout):
        seen.extend(messages[0].images)
        return ProviderReply("Bounded visual findings")

    monkeypatch.setattr(StrixyService, "generate", reply)
    detail, owner = new_conversation(client, assigned, analyst_token)
    saved = turn(client, detail, owner, engine)
    if limit == "count":
        assert len(seen) == 1
        outcomes = saved["messages"][-1]["coverage"]["attachment_outcomes"]
        assert [o["state"] for o in outcomes] == ["read", "unavailable"]
        assert outcomes[1]["reason"] == "attachment_unit_limit"
    else:
        assert seen == []
        assert saved["runs"][-1]["limit_code"] == "model_input_limit"


def test_unprocessable_page_does_not_hide_later_readable_pages(
    client,
    assigned,
    configured,
    admin_token,
    analyst_token,
    engine,
    monkeypatch,
):
    from pypdf import PdfReader, PdfWriter
    from pypdf.generic import RectangleObject

    from app.core.strixy_config import StrixyConfig

    writer = PdfWriter(clone_from=PdfReader(io.BytesIO(document())))
    writer.pages[1].mediabox = RectangleObject((0, 0, 100, 100))
    output = io.BytesIO()
    writer.write(output)
    monkeypatch.setattr(
        "app.core.strixy_config.get_strixy_config",
        lambda: StrixyConfig(visual_max_pixels=100000),
    )
    upload(
        client,
        assigned,
        admin_token,
        "partly-readable.pdf",
        output.getvalue(),
        "application/pdf",
    )
    seen = []

    def reply(self, messages, config, timeout):
        seen.extend(messages[0].images)
        return ProviderReply(
            "Only the second page was supplied; other content is missing."
        )

    monkeypatch.setattr(StrixyService, "generate", reply)
    detail, owner = new_conversation(client, assigned, analyst_token)
    saved = turn(client, detail, owner, engine)
    assert [v.field for v in seen] == ["attachment:page:2:image"]
    pages = saved["messages"][-1]["coverage"]["attachment_outcomes"][0]["pages"]
    assert pages == [
        {"unit": 1, "state": "unavailable", "reason": "visual_pixel_limit"},
        {"unit": 2, "state": "read", "reason": None},
    ]
