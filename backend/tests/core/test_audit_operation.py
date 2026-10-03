"""Contract tests for the structured audit decorator."""

from types import SimpleNamespace
from unittest.mock import patch

import pytest

from app.core.exceptions import ResourceNotFoundException
from app.core.logging import audit_operation

ACTOR = SimpleNamespace(id=7)


class Service:
    @audit_operation("thing_update")
    async def update(self, thing_id: int, *, current_user, fail=None):
        if fail:
            raise fail
        return SimpleNamespace(id=thing_id)

    @audit_operation("thing_delete")
    async def delete(self, thing_id: int, current_user):
        return None


def _events(logger_factory) -> list[str]:
    return [
        call.kwargs["event_type"]
        for call in [
            logger_factory.call_args,
            *logger_factory.return_value.bind.call_args_list,
        ]
    ]


@pytest.mark.asyncio
async def test_success_records_attempt_and_success_with_actor_and_ids():
    with patch("app.core.logging.get_security_logger") as logger_factory:
        await Service().update(3, current_user=ACTOR)

    logger_factory.assert_called_once_with(
        action="thing_update",
        actor_user_id=7,
        thing_id=3,
        event_type="thing_update_attempt",
    )
    logger_factory.return_value.bind.assert_called_once_with(
        event_type="thing_update_success", result_id=3
    )


@pytest.mark.asyncio
async def test_actor_is_found_by_signature_not_position():
    with patch("app.core.logging.get_security_logger") as logger_factory:
        await Service().delete(current_user=ACTOR, thing_id=4)
        await Service().delete(5, ACTOR)

    assert [call.kwargs["actor_user_id"] for call in logger_factory.call_args_list] == [
        7,
        7,
    ]


@pytest.mark.asyncio
async def test_domain_error_is_recorded_as_failed_with_class_name():
    with patch("app.core.logging.get_security_logger") as logger_factory:
        with pytest.raises(ResourceNotFoundException):
            await Service().update(
                3, current_user=ACTOR, fail=ResourceNotFoundException("gone")
            )

    logger_factory.return_value.bind.assert_called_once_with(
        event_type="thing_update_failed", failure_reason="ResourceNotFoundException"
    )


@pytest.mark.asyncio
async def test_unexpected_error_is_recorded_as_error_and_propagates():
    with patch("app.core.logging.get_security_logger") as logger_factory:
        with pytest.raises(RuntimeError):
            await Service().update(3, current_user=ACTOR, fail=RuntimeError("boom"))

    assert _events(logger_factory) == ["thing_update_attempt", "thing_update_error"]
