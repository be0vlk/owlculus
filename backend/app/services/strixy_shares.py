"""Fixed, authorized snapshots and independently owned conversation copies."""

from copy import deepcopy

from fastapi import HTTPException
from sqlmodel import col, select

from app.database.db_utils import transaction
from app.database.models import StrixyConversation, StrixyMessage, StrixyShare
from app.services.strixy_conversations import StrixyConversations
from app.services.strixy_sources import CaseSources, encoded


class StrixyShares:
    def __init__(self, conversations: StrixyConversations):
        self.conversations = conversations
        self.db = conversations.db

    def metadata(self, share: StrixyShare):
        return share.model_dump(
            exclude={"messages", "provenance", "conversation_id"}
        ) | {
            "case_id": self.conversations.case_id,
            "message_count": len(share.messages),
        }

    def create(self, conversation_id: str, through_message_id: str):
        with transaction(self.db):
            self.conversations.owned(conversation_id)
            saved = self.conversations.read(conversation_id)
            messages = saved["messages"]
            # Progress is visible application content, but never a live share.
            messages += [
                run["partial"] | {"position": run["position"] + 0.5}
                for run in saved["runs"]
                if run["partial"]
            ]
            messages.sort(key=lambda message: message["position"])
            boundary = next(
                (i for i, m in enumerate(messages) if m["id"] == through_message_id),
                None,
            )
            if boundary is None:
                raise HTTPException(404, "Message not found")
            messages = messages[: boundary + 1]
            provenance: list[dict] = []
            from app.database.models import StrixyGrounding

            for message in messages:
                if message.get("withheld"):
                    raise HTTPException(404, "Snapshot unavailable")
                original = self.db.get(StrixyMessage, message["id"])
                grounding = (
                    self.conversations.grounding_for(original)
                    if original is not None
                    else self.db.get(StrixyGrounding, message["id"])
                )
                if grounding:
                    provenance.extend(grounding.provenance)
            provenance = list({encoded(ref): ref for ref in provenance}.values())
            if not CaseSources(
                self.db, self.conversations.human, self.conversations.case_id
            ).validate_provenance(provenance):
                raise HTTPException(404, "Snapshot unavailable")
            share = StrixyShare(
                conversation_id=conversation_id,
                through_message_id=through_message_id,
                messages=deepcopy(messages),
                provenance=deepcopy(provenance),
            )
            # JSON storage preserves timestamps independently of the original rows.
            from fastapi.encoders import jsonable_encoder

            share.messages = jsonable_encoder(share.messages)
            self.db.add(share)
            self.db.flush()
            result = self.metadata(share)
        return result

    def list(self, conversation_id: str):
        self.conversations.owned(conversation_id)
        return [
            self.metadata(s)
            for s in self.db.exec(
                select(StrixyShare)
                .where(StrixyShare.conversation_id == conversation_id)
                .order_by(col(StrixyShare.created_at), StrixyShare.id)
            ).all()
        ]

    def locked(self, share_id: str, *, owner: bool = False):
        self.conversations.authorized()
        # Lock order matches workers and deletion: conversation, then share.
        conversation = self.db.exec(
            select(StrixyConversation)
            .join(StrixyShare)
            .where(
                StrixyShare.id == share_id,
                StrixyConversation.case_id == self.conversations.case_id,
                col(StrixyConversation.deleted_at).is_(None),
            )
            .with_for_update(of=StrixyConversation)
            .execution_options(populate_existing=True)
        ).first()
        if conversation is None or (
            owner and conversation.owner_id != self.conversations.human.id
        ):
            raise HTTPException(404, "Snapshot unavailable")
        share = self.db.exec(
            select(StrixyShare)
            .where(StrixyShare.id == share_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        ).first()
        if share is None:
            raise HTTPException(404, "Snapshot unavailable")
        return share

    def authorized(self, share_id: str):
        share = self.locked(share_id)
        if not CaseSources(
            self.db, self.conversations.human, self.conversations.case_id
        ).validate_provenance(share.provenance):
            raise HTTPException(404, "Snapshot unavailable")
        return share

    def read(self, share_id: str):
        share = self.authorized(share_id)
        messages = [
            self.conversations.grounded_view(
                message,
                share.provenance,
                message.get("citations", []),
                message.get("coverage"),
            )
            for message in share.messages
        ]
        if any(message.get("withheld") for message in messages):
            raise HTTPException(404, "Snapshot unavailable")
        return self.metadata(share) | {"messages": messages}

    def revoke(self, share_id: str):
        with transaction(self.db):
            self.db.delete(self.locked(share_id, owner=True))

    def copy(self, share_id: str):
        from datetime import datetime

        from app.database.models import StrixyCopiedGrounding

        with transaction(self.db):
            share = self.authorized(share_id)
            created = self.conversations.create()
            for position, saved in enumerate(share.messages):
                message = StrixyMessage(
                    conversation_id=created["id"],
                    position=position,
                    role=saved["role"],
                    content=saved["content"],
                    timestamp=datetime.fromisoformat(saved["timestamp"]),
                )
                self.db.add(message)
                self.db.flush()
                self.db.add(
                    StrixyCopiedGrounding(
                        message_id=message.id,
                        partial=bool(saved.get("partial")),
                        provenance=deepcopy(share.provenance),
                        citations=deepcopy(saved.get("citations", [])),
                        coverage=deepcopy(saved.get("coverage") or {}),
                    )
                )
        return created
