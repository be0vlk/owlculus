"""Owner-scoped persistence and atomic turn acceptance for Strixy."""

import builtins

from fastapi import HTTPException
from sqlalchemy import delete
from sqlmodel import Session, col, select

from app.core.utils import get_utc_now
from app.database.db_utils import transaction
from app.database.models import (
    StrixyConversation,
    StrixyGrounding,
    StrixyMessage,
    StrixyRun,
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
        return history, inherited

    def message_view(self, message: StrixyMessage):
        from app.services.strixy_sources import CaseSources

        data = message.model_dump()
        if message.role != "assistant":
            return data
        grounding = self.grounding_for(message)
        if grounding is None:
            return data
        reader = CaseSources(self.db, self.human, self.case_id)
        if not reader.validate_provenance(grounding.provenance):
            return data | {
                "content": "",
                "withheld": True,
                "citations": [],
                "coverage": None,
            }
        citations = []
        for citation in grounding.citations:
            source = reader.read(citation["source_id"])
            citations.append(
                citation
                | {
                    "source_status": (
                        "current"
                        if source.version == citation["version"]
                        else "changed"
                    ),
                    "url": f"/api/strixy/cases/{self.case_id}/sources/{citation['source_id']}",
                }
            )
        return data | {"citations": citations, "coverage": grounding.coverage}

    @staticmethod
    def run_view(run: StrixyRun):
        return run.model_dump(
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

    def observe(self, conversation_id: str, run_id: str):
        self.owned(conversation_id)
        run = self.db.get(StrixyRun, run_id)
        if run is None or run.conversation_id != conversation_id:
            raise HTTPException(404, "Run not found")
        return self.run_view(run)

    def delete(self, conversation_id: str):
        with transaction(self.db):
            conversation = self.owned(conversation_id)
            conversation.deleted_at = get_utc_now()
            self.db.add(conversation)
            self.db.execute(
                delete(StrixyMessage).where(
                    col(StrixyMessage.conversation_id) == conversation_id
                )
            )
            run_ids = select(StrixyRun.id).where(
                StrixyRun.conversation_id == conversation_id
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
