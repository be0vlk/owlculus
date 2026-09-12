"""Owner-scoped persistence and atomic turn acceptance for Strixy."""

from fastapi import HTTPException
from sqlalchemy import delete
from sqlmodel import Session, col, select

from app.core.utils import get_utc_now
from app.database.db_utils import transaction
from app.database.models import StrixyConversation, StrixyMessage, StrixyRun, User
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
            "messages": self.db.exec(
                select(StrixyMessage)
                .where(StrixyMessage.conversation_id == conversation_id)
                .order_by(col(StrixyMessage.position))
            ).all(),
            "runs": [
                self.run_view(run)
                for run in self.db.exec(
                    select(StrixyRun)
                    .where(StrixyRun.conversation_id == conversation_id)
                    .order_by(col(StrixyRun.position))
                ).all()
            ],
        }

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
            self.db.execute(
                delete(StrixyRun).where(
                    col(StrixyRun.conversation_id) == conversation_id
                )
            )

    def submit(self, conversation_id: str, content: str):
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
        self.db.refresh(run)
        return self.run_view(run)
