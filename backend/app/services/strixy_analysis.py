"""Bounded source/model orchestration with durable provenance at every boundary."""

from dataclasses import replace

from sqlmodel import Session

from app.core.strixy_config import StrixyConfig
from app.core.utils import get_utc_now
from app.database.db_utils import transaction
from app.database.models import StrixyGrounding, User
from app.schemas.strixy_schema import ChatMessage, SourceQuery
from app.services.strixy_conversations import StrixyConversations
from app.services.strixy_service import ProviderReply, StrixyService
from app.services.strixy_sources import CaseSources, GroundedMaterial, encoded


class GroundingError(Exception):
    def __init__(self, code: str):
        self.code = code


def analyze(
    run_id: str, database_engine, config: StrixyConfig, deadline
) -> ProviderReply:
    from app.executions.strixy_worker import authorize, lock_run

    material = None
    input_tokens = output_tokens = 0
    for attempt in range(config.max_model_calls):
        with Session(database_engine) as db, transaction(db):
            selected = lock_run(db, run_id)
            if selected is None or selected[1].status != "running":
                raise GroundingError("access_revoked")
            conversation, run = selected
            authorize(db, conversation, run)
            human = db.get(User, conversation.owner_id)
            assert human is not None
            reader = CaseSources(db, human, conversation.case_id)
            ledger = db.get(StrixyGrounding, run_id)
            if ledger is None:
                ledger = StrixyGrounding(run_id=run_id)
            if material is None:
                if ledger.focus:
                    sources = [
                        reader.read(source_id)
                        for source_id in dict.fromkeys(ledger.focus)
                    ]
                    complete = (
                        True  # The selected set is enumerated, not the whole Case.
                    )
                else:
                    sources, complete = reader.catalog(config)
                material = GroundedMaterial(sources, complete, config, ledger.focus)
            elif not reader.validate_provenance(ledger.provenance, current=True):
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
            db.add(ledger)
            # Persist every source input before external I/O, even if no answer follows.
            messages = [
                ChatMessage(role="system", content=encoded(material.context()))
            ] + history
            remaining = (deadline - get_utc_now()).total_seconds()
            if remaining <= 0:
                raise GroundingError("runtime_limit")
            if (
                sum(len(m.content.encode()) + 32 for m in messages)
                + len(config.instructions.encode())
                > config.max_input_bytes
            ):
                return ProviderReply("", input_tokens, output_tokens, "input_limit")
            output_budget = config.max_output_tokens - output_tokens
            if output_budget < 16:
                return ProviderReply("", input_tokens, output_tokens, "output_limit")
            service = StrixyService(db)
        reply = service.generate(
            messages,
            config.model_copy(update={"max_output_tokens": output_budget}),
            remaining,
        )
        input_tokens += reply.input_tokens
        output_tokens += reply.output_tokens
        if not reply.tool_requests:
            try:
                citations = material.citations(reply.citations)
            except (ValueError, TypeError, KeyError):
                raise GroundingError("invalid_citation") from None
            with Session(database_engine) as db, transaction(db):
                selected = lock_run(db, run_id)
                if selected is None or selected[1].status != "running":
                    raise GroundingError("access_revoked")
                ledger = db.get(StrixyGrounding, run_id)
                assert ledger is not None
                ledger.citations = citations
                db.add(ledger)
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
