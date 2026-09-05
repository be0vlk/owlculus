"""Authorized snapshot/replay observation with no worker-to-socket coupling."""

import asyncio
import json
import logging
import os
import time

from fastapi import HTTPException, WebSocket, WebSocketDisconnect
from fastapi.encoders import jsonable_encoder
from sqlmodel import Session, select

from app.core.exceptions import AuthorizationException, ResourceNotFoundException
from app.database.models import ExecutionControl, HuntExecution, PluginExecution, User
from app.executions.events import redis_client, stream_key
from app.services.case_access import CaseAccess

SEND_TIMEOUT = max(
    0.01, min(5, float(os.environ.get("EXECUTION_STREAM_SEND_SECONDS", "2")))
)
# Checking every iteration also bounds revocation during Redis interruption.
AUTH_SECONDS = min(
    10, max(0.1, float(os.environ.get("EXECUTION_STREAM_AUTH_SECONDS", "5")))
)


def readable_execution(db, user_id, kind, execution_id):
    user = db.get(User, user_id, populate_existing=True)
    if user is None or not user.is_active:
        raise HTTPException(403, "Observation access is no longer available")
    model = HuntExecution if kind == "hunt" else PluginExecution
    execution = db.get(model, execution_id, populate_existing=True)
    if execution is None:
        raise ResourceNotFoundException("Execution not found")
    CaseAccess(db).readable(user, execution.case_id)
    return execution


def snapshot(database_engine, user_id, kind, execution_id):
    with Session(database_engine) as db:
        association = (
            ExecutionControl.hunt_execution_id
            if kind == "hunt"
            else ExecutionControl.plugin_execution_id
        )
        # Writers lock the same row. All snapshot fields and its revision therefore
        # describe one commit; later commits have strictly newer replay cursors.
        control = db.exec(
            select(ExecutionControl)
            .where(association == execution_id)
            .with_for_update()
        ).first()
        execution = readable_execution(db, user_id, kind, execution_id)
        base = f"/api/{kind}s/executions/{execution_id}"
        revision = control.revision if control else 0
        return {
            "execution_id": execution_id,
            "kind": kind,
            "revision": revision,
            "cursor": f"{revision}-0",
            "state": {
                "id": execution_id,
                "case_id": execution.case_id,
                "status": execution.status,
                "revision": revision,
            },
            "links": {
                "detail": base,
                "results": (
                    f"{base}/results"
                    if kind == "plugin"
                    else f"{base}?include_steps=true"
                ),
            },
        }


def retained(client, key, cursor):
    first = client.xrange(key, count=1)
    last = client.xrevrange(key, count=1)
    if not first:
        return False
    revision = int(cursor.split("-")[0])
    return int(first[0][0].split("-")[0]) <= revision <= int(last[0][0].split("-")[0])


async def observe(websocket: WebSocket, database_engine, kind: str, execution_id: int):
    from app.core.security import ephemeral_token_manager

    token = websocket.query_params.get("token")
    cursor = websocket.query_params.get("cursor")
    try:
        if cursor is not None and (
            not cursor.endswith("-0") or not cursor[:-2].isdigit()
        ):
            raise ValueError("Invalid cursor")
        user_id = await asyncio.to_thread(
            ephemeral_token_manager.validate_token, token or "", execution_id, kind
        )
        if user_id is None:
            raise ValueError("Invalid token")
        initial = await asyncio.to_thread(
            snapshot, database_engine, user_id, kind, execution_id
        )
    except Exception:  # noqa: BLE001 - deny without token or transport details
        await websocket.close(code=1008, reason="Observation access unavailable")
        return

    await websocket.accept()
    last_cursor = initial["cursor"]
    authorized_at = time.monotonic()

    async def send(message):
        nonlocal authorized_at
        if time.monotonic() - authorized_at >= AUTH_SECONDS:
            await asyncio.to_thread(
                snapshot, database_engine, user_id, kind, execution_id
            )
            authorized_at = time.monotonic()
        await asyncio.wait_for(
            websocket.send_json(jsonable_encoder(message)), SEND_TIMEOUT
        )

    async def deliver():
        nonlocal last_cursor
        key = stream_key(kind, execution_id)
        with redis_client() as client:
            try:
                valid = cursor is None or await asyncio.to_thread(
                    retained, client, key, cursor
                )
            except Exception:  # noqa: BLE001 - snapshot survives Redis outage
                valid = False
            await send({"event_type": "snapshot" if valid else "resync", **initial})
            # The snapshot supersedes older replay, including a terminal commit
            # between submission and subscription. Updates after it use XREAD,
            # never consumer groups, so every API observer sees the same revisions.
            while True:
                current = await asyncio.to_thread(
                    snapshot, database_engine, user_id, kind, execution_id
                )
                try:
                    valid = await asyncio.to_thread(retained, client, key, last_cursor)
                    updates = await asyncio.to_thread(
                        client.xread, {key: last_cursor}, count=100
                    )
                    if (not valid or not updates) and current["revision"] > int(
                        last_cursor.split("-")[0]
                    ):
                        await send({"event_type": "resync", **current})
                        last_cursor = current["cursor"]
                    else:
                        for _, entries in updates:
                            for event_cursor, fields in entries:
                                revision = int(fields["revision"])
                                if revision > int(last_cursor.split("-")[0]):
                                    await send(
                                        {
                                            "event_type": "update",
                                            "execution_id": execution_id,
                                            "kind": kind,
                                            "revision": revision,
                                            "cursor": event_cursor,
                                            "links": current["links"],
                                        }
                                    )
                                    last_cursor = event_cursor
                except (
                    TimeoutError,
                    HTTPException,
                    AuthorizationException,
                    ResourceNotFoundException,
                ):
                    raise
                except Exception:  # noqa: BLE001 - recover from durable state
                    logging.getLogger(__name__).warning(
                        json.dumps(
                            {
                                "event": "observation_failure",
                                "kind": kind,
                                "execution_id": execution_id,
                                "cursor": last_cursor,
                            }
                        )
                    )
                    await send({"event_type": "resync", **current})
                    last_cursor = current["cursor"]
                if current["state"]["status"] in {
                    "completed",
                    "partial",
                    "failed",
                    "cancelled",
                }:
                    if current["cursor"] != last_cursor:
                        await send({"event_type": "snapshot", **current})
                        last_cursor = current["cursor"]
                    return
                await asyncio.sleep(AUTH_SECONDS)

    async def receive():
        while True:
            # Receive disconnects promptly; no unbounded application send queue.
            await websocket.receive_text()

    tasks = [asyncio.create_task(deliver()), asyncio.create_task(receive())]
    try:
        done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        for task in done:
            task.result()
        await websocket.close(code=1000)
    except (HTTPException, AuthorizationException, ResourceNotFoundException):
        await websocket.close(code=1008, reason="Observation access revoked")
    except TimeoutError:
        await websocket.close(code=1013, reason=f"Reconnect from {last_cursor}")
    except WebSocketDisconnect:
        pass
    except Exception:  # noqa: BLE001 - client can reopen durable results
        await websocket.close(code=1013, reason=f"Reconnect from {last_cursor}")
    finally:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
