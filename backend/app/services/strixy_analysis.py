"""Bounded source/model orchestration with durable provenance at every boundary."""

from contextlib import contextmanager

from sqlmodel import Session

from app.core.strixy_config import StrixyConfig
from app.core.utils import get_utc_now
from app.database.db_utils import transaction
from app.database.models import StrixyGrounding, StrixyProgress, StrixyRun, User
from app.schemas.strixy_schema import ModelMessage
from app.services.api_key_vault import strixy_key
from app.services.strixy_conversations import StrixyConversations
from app.services.strixy_service import ProviderReply, StrixyService
from app.services.strixy_sources import (
    CaseSources,
    GroundedMaterial,
    MaterialCheckpoint,
    SourceCatalog,
    encoded,
)


class GroundingError(Exception):
    def __init__(self, code: str):
        self.code = code


def analyze(
    run_id: str, database_engine, config: StrixyConfig, deadline
) -> ProviderReply:
    from app.executions.strixy_worker import authorize, lock_run

    material: GroundedMaterial | None = None

    @contextmanager
    def fenced(cancel_reason: str = "cancelled"):
        with Session(database_engine) as db, transaction(db):
            selected = lock_run(db, run_id)
            if selected is None or selected[1].status != "running":
                raise GroundingError(cancel_reason)
            conversation, run = selected
            authorize(db, conversation, run)
            if get_utc_now() >= deadline:
                raise GroundingError("runtime_limit")
            human = db.get(User, conversation.owner_id)
            assert human is not None
            yield db, run, CaseSources(db, human, conversation.case_id)

    def before_attachment(source):
        with fenced() as (_, _, reader):
            if not reader.validate_provenance([source.reference()], current=True):
                raise GroundingError("sources_changed")

    def checkpoint(reply: ProviderReply):
        with fenced() as (db, _, reader):
            ledger = db.get(StrixyGrounding, run_id)
            assert ledger is not None and material is not None
            if not reader.validate_provenance(ledger.provenance, current=True):
                raise GroundingError("sources_changed")
            citations, unverified = material.citations(reply.citations)
            if reply.content:
                ledger.citations = citations
                ledger.coverage = {
                    **(ledger.coverage or {}),
                    "unverified_citations": unverified,
                }
            progress = db.get(StrixyProgress, run_id)
            assert progress is not None
            if reply.content:
                progress.content, progress.updated_at = reply.content, get_utc_now()
            progress.phase = "preparing_findings"
            db.add(progress)
            db.add(ledger)

    with fenced("access_revoked") as (db, run, reader):
        progress = db.get(StrixyProgress, run_id) or StrixyProgress(run_id=run_id)
        progress.phase = "examining_inputs"
        db.add(progress)
        ledger = db.get(StrixyGrounding, run_id) or StrixyGrounding(run_id=run_id)
        previous = None
        if progress.resume_from:
            prior_run = db.get(StrixyRun, progress.resume_from)
            prior_ledger = db.get(StrixyGrounding, progress.resume_from)
            prior_progress = db.get(StrixyProgress, progress.resume_from)
            if (
                prior_run
                and prior_ledger
                and prior_progress
                and prior_progress.material
                and prior_run.configuration == run.configuration
                and reader.validate_provenance(prior_ledger.provenance, current=True)
            ):
                previous = MaterialCheckpoint.model_validate(prior_progress.material)
        cursor = {}
        if previous:
            cursor = (
                previous.next_cursor
                if not previous.enumeration_complete and previous.batch_exhausted()
                else previous.cursor
            )
        if ledger.focus:
            catalog = SourceCatalog(
                [reader.read(source_id) for source_id in dict.fromkeys(ledger.focus)],
                True,
            )
        else:
            catalog = reader.catalog(config, cursor)
        focus = list(ledger.focus)
    # Parsing is local but may be expensive. Release lifecycle locks so owners
    # can cancel/delete while it runs, then fence all inputs before provider I/O.
    material = GroundedMaterial(
        catalog,
        config,
        focus,
        previous,
        cursor,
        preparation_timeout=(deadline - get_utc_now()).total_seconds(),
        before_attachment=before_attachment,
    )
    with fenced() as (db, run, reader):
        ledger = db.get(StrixyGrounding, run_id) or StrixyGrounding(run_id=run_id)
        progress = db.get(StrixyProgress, run_id)
        assert progress is not None
        if not reader.validate_provenance(
            material.provenance() + ledger.provenance, current=True
        ):
            raise GroundingError("sources_changed")
        history, inherited = StrixyConversations(
            db, reader.human, reader.case_id
        ).authorized_history(run.conversation_id)
        ledger.provenance = list(
            {encoded(ref): ref for ref in material.provenance() + inherited}.values()
        )
        ledger.coverage = material.coverage() | {"supplied_to_model": False}
        db.add(ledger)
        # Persist every source input before external I/O, even if no answer follows.
        messages = [
            ModelMessage(
                role="user",
                content=encoded(material.context()),
                images=material.images,
            )
        ] + history
        remaining = (deadline - get_utc_now()).total_seconds()
        if remaining <= 0:
            raise GroundingError("runtime_limit")
        input_bytes = sum(len(m.content.encode()) + 32 for m in messages) + len(
            config.instructions.encode()
        )
        if input_bytes > config.max_input_bytes:
            return ProviderReply("", 0, 0, "input_limit")
        # UTF-8 bytes conservatively reserve input tokens before external I/O.
        visual_tokens = len(material.images) * config.visual_input_token_reserve
        if input_bytes + visual_tokens > config.max_total_input_tokens:
            return ProviderReply("", 0, 0, "model_input_limit")
        progress.material = material.checkpoint()
        ledger.coverage = material.coverage() | {"supplied_to_model": True}
        db.add(ledger)
        progress.model_calls += 1
        db.add(progress)
        service = StrixyService(
            strixy_key(db, config.provider, config.base_url), on_progress=checkpoint
        )
    reply = service.generate(messages, config, remaining)
    with Session(database_engine) as db, transaction(db):
        selected = lock_run(db, run_id)
        if selected is None or selected[1].status != "running":
            raise GroundingError("cancelled")
        _, run = selected
        run.input_tokens, run.output_tokens = reply.input_tokens, reply.output_tokens
        db.add(run)
    checkpoint(reply)
    return reply
