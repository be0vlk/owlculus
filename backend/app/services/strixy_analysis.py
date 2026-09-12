"""Bounded source/model orchestration with durable provenance at every boundary."""

from dataclasses import replace

from sqlmodel import Session

from app.core.strixy_config import StrixyConfig
from app.core.utils import get_utc_now
from app.database.db_utils import transaction
from app.database.models import StrixyGrounding, StrixyProgress, User
from app.schemas.strixy_schema import ModelMessage, SourceQuery
from app.services.strixy_conversations import StrixyConversations
from app.services.strixy_service import ProviderReply, StrixyService
from app.services.strixy_sources import (
    CaseSources,
    GroundedMaterial,
    MaterialCheckpoint,
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

    def before_attachment(source):
        with Session(database_engine) as db, transaction(db):
            selected = lock_run(db, run_id)
            if selected is None or selected[1].status != "running":
                raise GroundingError("cancelled")
            conversation, run = selected
            authorize(db, conversation, run)
            if get_utc_now() >= deadline:
                raise GroundingError("runtime_limit")
            human = db.get(User, conversation.owner_id)
            assert human is not None
            if not CaseSources(db, human, conversation.case_id).validate_provenance(
                [source.reference()], current=True
            ):
                raise GroundingError("sources_changed")

    def checkpoint(reply: ProviderReply):
        from app.services.strixy_sources import CaseSources

        with Session(database_engine) as db, transaction(db):
            selected = lock_run(db, run_id)
            if selected is None or selected[1].status != "running":
                raise GroundingError("cancelled")
            conversation, run = selected
            authorize(db, conversation, run)
            if get_utc_now() >= deadline:
                raise GroundingError("runtime_limit")
            human = db.get(User, conversation.owner_id)
            assert human is not None
            ledger = db.get(StrixyGrounding, run_id)
            assert ledger is not None and material is not None
            if not CaseSources(db, human, conversation.case_id).validate_provenance(
                ledger.provenance, current=True
            ):
                raise GroundingError("sources_changed")
            try:
                citations = material.citations(reply.citations)
                if reply.content:
                    ledger.citations = citations
            except (ValueError, TypeError, KeyError):
                raise GroundingError("invalid_citation") from None
            progress = db.get(StrixyProgress, run_id)
            assert progress is not None
            if reply.content:
                progress.content, progress.updated_at = reply.content, get_utc_now()
            progress.phase = "preparing_findings"
            db.add(progress)
            db.add(ledger)

    input_tokens = output_tokens = 0
    for attempt in range(config.max_model_calls):
        with Session(database_engine) as db, transaction(db):
            selected = lock_run(db, run_id)
            if selected is None or selected[1].status != "running":
                raise GroundingError("access_revoked")
            conversation, run = selected
            authorize(db, conversation, run)
            if get_utc_now() >= deadline:
                raise GroundingError("runtime_limit")
            progress = db.get(StrixyProgress, run_id) or StrixyProgress(run_id=run_id)
            progress.phase = "examining_inputs"
            db.add(progress)
            human = db.get(User, conversation.owner_id)
            assert human is not None
            reader = CaseSources(db, human, conversation.case_id)
            ledger = db.get(StrixyGrounding, run_id)
            if ledger is None:
                ledger = StrixyGrounding(run_id=run_id)
            if material is None:
                previous = None
                if progress.resume_from:
                    from app.database.models import StrixyRun

                    prior_run = db.get(StrixyRun, progress.resume_from)
                    prior_ledger = db.get(StrixyGrounding, progress.resume_from)
                    prior_progress = db.get(StrixyProgress, progress.resume_from)
                    if (
                        prior_run
                        and prior_ledger
                        and prior_progress
                        and prior_progress.material
                        and prior_run.configuration == run.configuration
                        and reader.validate_provenance(
                            prior_ledger.provenance, current=True
                        )
                    ):
                        previous = MaterialCheckpoint.model_validate(
                            prior_progress.material
                        )
                cursor = {}
                if previous:
                    cursor = (
                        previous.next_cursor
                        if not previous.enumeration_complete
                        and all(state == "read" for state in previous.states.values())
                        else previous.cursor
                    )
                catalog = None
                if ledger.focus:
                    sources = [
                        reader.read(source_id)
                        for source_id in dict.fromkeys(ledger.focus)
                    ]
                    complete = True
                else:
                    catalog = reader.catalog(config, cursor)
                    sources, complete = catalog.sources, catalog.complete
                focus = list(ledger.focus)
        # Parsing is local but may be expensive. Release lifecycle locks so owners
        # can cancel/delete while it runs, then fence all inputs before provider I/O.
        if material is None:
            material = GroundedMaterial(
                sources,
                complete,
                config,
                focus,
                previous,
                catalog,
                cursor,
                preparation_timeout=(deadline - get_utc_now()).total_seconds(),
                before_attachment=before_attachment,
            )
        with Session(database_engine) as db, transaction(db):
            selected = lock_run(db, run_id)
            if selected is None or selected[1].status != "running":
                raise GroundingError("cancelled")
            conversation, run = selected
            authorize(db, conversation, run)
            human = db.get(User, conversation.owner_id)
            assert human is not None
            reader = CaseSources(db, human, conversation.case_id)
            ledger = db.get(StrixyGrounding, run_id) or StrixyGrounding(run_id=run_id)
            saved_progress = db.get(StrixyProgress, run_id)
            assert saved_progress is not None
            progress = saved_progress
            if not reader.validate_provenance(
                material.provenance() + ledger.provenance, current=True
            ):
                raise GroundingError("sources_changed")
            history, inherited = StrixyConversations(
                db, human, conversation.case_id
            ).authorized_history(conversation.id)
            ledger.provenance = list(
                {
                    encoded(ref): ref for ref in material.provenance() + inherited
                }.values()
            )
            ledger.coverage = material.coverage()
            ledger.coverage["supplied_to_model"] = progress.model_calls > 0
            db.add(ledger)
            # Persist every source input before external I/O, even if no answer follows.
            messages = [
                ModelMessage(
                    role="system",
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
                return ProviderReply("", input_tokens, output_tokens, "input_limit")
            # UTF-8 bytes conservatively reserve input tokens before external I/O.
            visual_tokens = len(material.images) * config.visual_input_token_reserve
            if (
                input_tokens + input_bytes + visual_tokens
                > config.max_total_input_tokens
            ):
                return ProviderReply(
                    "", input_tokens, output_tokens, "model_input_limit"
                )
            output_budget = config.max_output_tokens - output_tokens
            if output_budget < 16:
                return ProviderReply("", input_tokens, output_tokens, "output_limit")
            progress.material = material.checkpoint()
            ledger.coverage = material.coverage() | {"supplied_to_model": True}
            db.add(ledger)
            progress.model_calls += 1
            db.add(progress)
            service = StrixyService(db, on_progress=checkpoint)
        reply = service.generate(
            messages,
            config.model_copy(update={"max_output_tokens": output_budget}),
            remaining,
        )
        input_tokens += reply.input_tokens
        output_tokens += reply.output_tokens
        with Session(database_engine) as db, transaction(db):
            selected = lock_run(db, run_id)
            if selected is None or selected[1].status != "running":
                raise GroundingError("cancelled")
            _, run = selected
            run.input_tokens, run.output_tokens = input_tokens, output_tokens
            db.add(run)
        checkpoint(reply)
        if not reply.tool_requests:
            return replace(
                reply, input_tokens=input_tokens, output_tokens=output_tokens
            )
        if attempt + 1 == config.max_model_calls:
            return ProviderReply("", input_tokens, output_tokens, "model_call_limit")
        if len(reply.tool_requests) != 1:
            raise GroundingError("invalid_tool_request")
        request = reply.tool_requests[0]
        try:
            if (
                set(request) != {"name", "arguments"}
                or request["name"] != "read_case_sources"
            ):
                raise ValueError
            query = SourceQuery.model_validate(request["arguments"])
            # All tools operate only on this run's bounded authorized inventory.
            if query.action == "read":
                if query.source_id is None or query.query is not None:
                    raise ValueError
                material.lookup(query.source_id)
            elif query.action == "search":
                if not query.query or query.source_id is not None:
                    raise ValueError
                material.search(query.query)
            else:
                if query.query is not None or query.source_id is not None:
                    raise ValueError
                material.list_sources()
        except (ValueError, KeyError, TypeError):
            raise GroundingError("invalid_tool_request") from None
    raise GroundingError("model_call_limit")
