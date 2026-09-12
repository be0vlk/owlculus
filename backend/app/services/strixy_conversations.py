"""Owner-scoped persistence and atomic turn acceptance for Strixy."""

import builtins

from fastapi import HTTPException
from sqlalchemy import delete
from sqlmodel import Session, col, select

from app.core.utils import get_utc_now
from app.database.db_utils import transaction
from app.database.models import (
    StrixyConversation,
    StrixyCopiedGrounding,
    StrixyGrounding,
    StrixyMessage,
    StrixyProgress,
    StrixyRun,
    StrixyShare,
    User,
)
from app.services.strixy_access import require_strixy_access


class StrixyConversations:
    def __init__(self, db: Session, human: User, case_id: int):
        self.db, self.human, self.case_id = db, human, case_id

    def authorized(self):
        return require_strixy_access(self.db, self.human, self.case_id)

    def owned(self, conversation_id: str) -> StrixyConversation:
        self.authorized()
        conversation = self.db.exec(
            select(StrixyConversation)
            .where(
                StrixyConversation.id == conversation_id,
                StrixyConversation.case_id == self.case_id,
                StrixyConversation.owner_id == self.human.id,
                col(StrixyConversation.deleted_at).is_(None),
            )
            .with_for_update()
            .execution_options(populate_existing=True)
        ).first()
        if conversation is None:
            raise HTTPException(404, "Conversation not found")
        return conversation

    def list(self):
        self.authorized()
        return self.db.exec(
            select(StrixyConversation)
            .where(
                StrixyConversation.case_id == self.case_id,
                StrixyConversation.owner_id == self.human.id,
                col(StrixyConversation.deleted_at).is_(None),
            )
            .order_by(col(StrixyConversation.created_at).desc(), StrixyConversation.id)
        ).all()

    def create(self):
        with transaction(self.db):
            self.authorized()
            assert self.human.id is not None
            conversation = StrixyConversation(
                case_id=self.case_id, owner_id=self.human.id
            )
            self.db.add(conversation)
        self.db.refresh(conversation)
        return conversation.model_dump(exclude={"owner_id", "deleted_at"})

    def read(self, conversation_id: str):
        conversation = self.owned(conversation_id)
        return {
            **conversation.model_dump(exclude={"owner_id", "deleted_at"}),
            "messages": [
                self.message_view(message)
                for message in self.db.exec(
                    select(StrixyMessage)
                    .where(StrixyMessage.conversation_id == conversation_id)
                    .order_by(col(StrixyMessage.position))
                ).all()
            ],
            "runs": [
                self.run_view(run)
                for run in self.db.exec(
                    select(StrixyRun)
                    .where(StrixyRun.conversation_id == conversation_id)
                    .order_by(col(StrixyRun.position))
                ).all()
            ],
        }

    def grounding_for(self, message: StrixyMessage):
        copied = self.db.get(StrixyCopiedGrounding, message.id)
        if copied:
            return copied
        if message.role != "assistant":
            return None
        return self.db.exec(
            select(StrixyGrounding)
            .join(StrixyRun)
            .where(
                StrixyRun.conversation_id == message.conversation_id,
                StrixyRun.position == message.position - 1,
            )
        ).first()

    def authorized_history(self, conversation_id: str):
        from app.schemas.strixy_schema import ChatMessage
        from app.services.strixy_sources import CaseSources

        reader = CaseSources(self.db, self.human, self.case_id)
        history, inherited = [], []
        for message in self.db.exec(
            select(StrixyMessage)
            .where(StrixyMessage.conversation_id == conversation_id)
            .order_by(col(StrixyMessage.position))
        ).all():
            grounding = self.grounding_for(message)
            if grounding:
                if not reader.validate_provenance(grounding.provenance, current=True):
                    continue
                inherited.extend(grounding.provenance)
            history.append(ChatMessage(role=message.role, content=message.content))
            if message.role == "user":
                prior = self.db.exec(
                    select(StrixyRun).where(
                        StrixyRun.conversation_id == conversation_id,
                        StrixyRun.position == message.position,
                    )
                ).first()
                progress = self.db.get(StrixyProgress, prior.id) if prior else None
                ledger = self.db.get(StrixyGrounding, prior.id) if prior else None
                if (
                    progress
                    and progress.content
                    and ledger
                    and reader.validate_provenance(ledger.provenance, current=True)
                ):
                    history.append(
                        ChatMessage(role="assistant", content=progress.content)
                    )
                    inherited.extend(ledger.provenance)
        return history, inherited

    def message_view(self, message: StrixyMessage):
        data = message.model_dump()
        grounding = self.grounding_for(message)
        if grounding is None:
            return data
        if isinstance(grounding, StrixyCopiedGrounding) and grounding.partial:
            data["partial"] = True
        return self.grounded_view(
            data, grounding.provenance, grounding.citations, grounding.coverage
        )

    def grounded_view(self, data, provenance, saved_citations, coverage):
        from app.services.strixy_sources import CaseSources

        reader = CaseSources(self.db, self.human, self.case_id)
        if not reader.validate_provenance(provenance):
            return data | {
                "content": "",
                "withheld": True,
                "citations": [],
                "coverage": None,
            }
        citations = []
        for citation in saved_citations:
            source = reader.read(citation["source_id"])
            parts = citation["field"].split(":")
            page_query = (
                f"?unit={int(parts[2])}"
                if len(parts) == 4
                and parts[:2] == ["attachment", "page"]
                and parts[2].isdigit()
                else ""
            )
            citations.append(
                citation
                | {
                    "source_status": (
                        "current"
                        if source.version == citation["version"]
                        else "changed"
                    ),
                    "url": f"/api/strixy/cases/{self.case_id}/sources/{citation['source_id']}{page_query}",
                }
            )
        return data | {"citations": citations, "coverage": coverage or None}

    def run_view(self, run: StrixyRun):
        data = run.model_dump(
            exclude={
                "configuration",
                "strixy_id",
                "dispatch_at",
                "dispatch_attempts",
                "deadline",
            }
        ) | {
            "model": run.configuration.get("model"),
            "configuration_version": run.configuration.get("version"),
            "instruction_version": run.configuration.get("instruction_version"),
        }

        from app.services.strixy_sources import CaseSources

        progress = self.db.get(StrixyProgress, run.id)
        ledger = self.db.get(StrixyGrounding, run.id)
        data.update(
            progress=progress.phase if progress else "locating_records",
            partial=None,
            source_coverage=None,
            model_calls=progress.model_calls if progress else 0,
        )
        if ledger and CaseSources(
            self.db, self.human, self.case_id
        ).validate_provenance(ledger.provenance):
            data["source_coverage"] = ledger.coverage or None
            if progress and progress.content:
                data["partial"] = self.grounded_view(
                    {
                        "id": run.id,
                        "role": "assistant",
                        "content": progress.content,
                        "timestamp": progress.updated_at,
                        "partial": True,
                    },
                    ledger.provenance,
                    ledger.citations,
                    ledger.coverage,
                )
        return data

    def observe(self, conversation_id: str, run_id: str):
        self.owned(conversation_id)
        run = self.db.get(StrixyRun, run_id)
        if run is None or run.conversation_id != conversation_id:
            raise HTTPException(404, "Run not found")
        return self.run_view(run)

    def restart(self, conversation_id: str, run_id: str, action: str):
        with transaction(self.db):
            self.owned(conversation_id)
            prior = self.db.get(StrixyRun, run_id)
            if prior is None or prior.conversation_id != conversation_id:
                raise HTTPException(404, "Run not found")
            latest = self.db.exec(
                select(StrixyRun)
                .where(StrixyRun.conversation_id == conversation_id)
                .order_by(col(StrixyRun.position).desc())
            ).first()
            if (
                latest is None
                or latest.id != run_id
                or prior.status in {"pending", "running"}
            ):
                raise HTTPException(
                    409, "Only the latest finished run can be continued or retried"
                )
            ledger = self.db.get(StrixyGrounding, run_id)
            if action == "continue" and not (
                prior.limit_code
                or prior.status == "cancelled"
                or (ledger and ledger.coverage and not ledger.coverage.get("complete"))
            ):
                raise HTTPException(409, "This run has no unfinished analysis")
            if action == "retry" and prior.status != "failed":
                raise HTTPException(409, "Only failed runs can be retried")
            question = self.db.exec(
                select(StrixyMessage).where(
                    StrixyMessage.conversation_id == conversation_id,
                    StrixyMessage.position == prior.position,
                )
            ).one()
            content = (
                "Continue the previous analysis using retained findings and remaining material."
                if action == "continue"
                else question.content
            )
            accepted = self.submit(
                conversation_id, content, ledger.focus if ledger else []
            )
            if action == "continue":
                self.db.add(StrixyProgress(run_id=accepted["id"], resume_from=run_id))
        return accepted

    def cancel(self, conversation_id: str, run_id: str):
        from app.executions.strixy_worker import finish

        with transaction(self.db):
            self.owned(conversation_id)
            run = self.db.get(StrixyRun, run_id)
            if run is None or run.conversation_id != conversation_id:
                raise HTTPException(404, "Run not found")
            if run.status in {"pending", "running"}:
                finish(run, "cancelled")
                self.db.add(run)
        self.db.refresh(run)
        return self.run_view(run)

    def delete(self, conversation_id: str):
        with transaction(self.db):
            conversation = self.owned(conversation_id)
            conversation.deleted_at = get_utc_now()
            self.db.add(conversation)
            self.db.execute(
                delete(StrixyShare).where(
                    col(StrixyShare.conversation_id) == conversation_id
                )
            )
            message_ids = select(StrixyMessage.id).where(
                StrixyMessage.conversation_id == conversation_id
            )
            self.db.execute(
                delete(StrixyCopiedGrounding).where(
                    col(StrixyCopiedGrounding.message_id).in_(message_ids)
                )
            )
            self.db.execute(
                delete(StrixyMessage).where(
                    col(StrixyMessage.conversation_id) == conversation_id
                )
            )
            run_ids = select(StrixyRun.id).where(
                StrixyRun.conversation_id == conversation_id
            )
            self.db.execute(
                delete(StrixyProgress).where(col(StrixyProgress.run_id).in_(run_ids))
            )
            self.db.execute(
                delete(StrixyGrounding).where(col(StrixyGrounding.run_id).in_(run_ids))
            )
            self.db.execute(
                delete(StrixyRun).where(
                    col(StrixyRun.conversation_id) == conversation_id
                )
            )

    def submit(
        self,
        conversation_id: str,
        content: str,
        focus: builtins.list[str] | None = None,
    ):
        from app.core.strixy_config import get_strixy_config
        from app.services.api_key_vault import ConfigurationApiKeyVault, Provider

        with transaction(self.db):
            self.owned(conversation_id)
            strixy = self.authorized()
            active = self.db.exec(
                select(StrixyRun).where(
                    StrixyRun.conversation_id == conversation_id,
                    col(StrixyRun.status).in_(["pending", "running"]),
                )
            ).first()
            if active:
                raise HTTPException(
                    409, "Wait for the current reply before sending another message"
                )
            if not ConfigurationApiKeyVault(self.db).get_key(Provider.OPENAI):
                raise HTTPException(
                    422,
                    "OpenAI API key not configured. Ask an administrator to configure it.",
                )
            config = get_strixy_config()
            if focus:
                from app.services.strixy_sources import CaseSources

                reader = CaseSources(self.db, self.human, self.case_id)
                for source_id in focus:
                    reader.read(source_id)
            messages = self.db.exec(
                select(StrixyMessage)
                .where(StrixyMessage.conversation_id == conversation_id)
                .order_by(col(StrixyMessage.position))
            ).all()
            assert strixy.id is not None
            run = StrixyRun(
                conversation_id=conversation_id,
                strixy_id=strixy.id,
                position=len(messages),
                configuration=config.model_dump(),
            )
            self.db.add(
                StrixyMessage(
                    conversation_id=conversation_id,
                    position=len(messages),
                    role="user",
                    content=content,
                )
            )
            # UTF-8 bytes conservatively bound input tokens without truncating history.
            size = (
                sum(len(m.content.encode("utf-8")) + 32 for m in messages)
                + len(content.encode("utf-8"))
                + len(config.instructions.encode("utf-8"))
                + 32
            )
            if len(messages) + 1 > config.max_messages or size > config.max_input_bytes:
                run.status = "completed"
                run.limit_code = "input_limit"
                run.finished_at = get_utc_now()
            self.db.add(run)
            self.db.flush()
            self.db.add(StrixyGrounding(run_id=run.id, focus=focus or []))
        self.db.refresh(run)
        return self.run_view(run)
