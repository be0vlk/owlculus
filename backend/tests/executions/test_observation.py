"""Shared observation through independent APIs and real Redis/PostgreSQL workers."""

import json

from websockets.sync.client import connect

from tests.executions.conftest import eventually
from tests.executions.test_execution_system import finished, submit


def stream(client, execution, *, kind="plugin", cursor=None):
    response = client.post(
        "/api/auth/websocket-token",
        json={"execution_id": execution["id"], "kind": kind},
    )
    assert response.status_code == 200, response.text
    url = str(client.base_url).replace("http:", "ws:").rstrip("/")
    url += f"/api/{kind}s/executions/{execution['id']}/stream?token={response.json()['token']}"
    if cursor is not None:
        url += f"&cursor={cursor}"
    return url


def receive(ws):
    return json.loads(ws.recv(timeout=10))


def test_shared_tokens_and_completion_before_subscription(execution_system):
    system = execution_system
    _, first = system.api()
    _, second = system.api()
    system.worker()
    system.start("-m", "app.executions.dispatcher")
    accepted = submit(first, system)
    state = eventually(lambda: finished(second, accepted))
    url = stream(first, accepted).replace(
        str(first.base_url.port), str(second.base_url.port)
    )
    with connect(url) as ws:
        snapshot = receive(ws)
        assert snapshot["event_type"] == "snapshot"
        assert snapshot["state"]["status"] == "completed"
        assert snapshot["revision"] == state["revision"]
    assert [
        event["type"]
        for event in second.get(accepted["links"]["results"]).json()["items"]
    ] == ["data", "complete"]


def test_publication_failure_repairs_without_api_traffic_and_retention_recovers(
    execution_system,
):
    from redis import Redis

    from app.executions.events import stream_key

    system = execution_system
    system.env["EXECUTION_STREAM_LIMIT"] = "3"
    _, client = system.api()
    accepted = submit(client, system, mode="pages")
    key = stream_key("plugin", accepted["id"])
    redis = Redis.from_url(system.env["REDIS_URL"], decode_responses=True)
    redis.set("rate-limit:sentinel", "untouched")
    redis.set(key, "publication temporarily unavailable")
    system.worker()
    system.start("-m", "app.executions.dispatcher")
    state = eventually(lambda: finished(client, accepted))
    assert state["status"] == "completed"
    healthy = submit(client, system)
    healthy_state = eventually(lambda: finished(client, healthy))
    healthy_key = stream_key("plugin", healthy["id"])
    eventually(lambda: redis.xlen(healthy_key) > 0)
    assert healthy_state["status"] == "completed"
    redis.delete(key)
    # No HTTP requests drive event repair.
    eventually(
        lambda: redis.xlen(key) == 3
        and redis.xrevrange(key, count=1)[0][0] == f"{state['revision']}-0"
    )
    assert 0 < redis.ttl(key) <= 86400
    with connect(stream(client, accepted, cursor="1-0")) as ws:
        recovered = receive(ws)
        assert recovered["event_type"] == "resync"
        assert recovered["state"]["status"] == "completed"
    redis.delete(key)
    with connect(stream(client, accepted, cursor=recovered["cursor"])) as ws:
        assert receive(ws)["event_type"] == "resync"
    items, cursor = [], 0
    while True:
        page = client.get(
            accepted["links"]["results"], params={"cursor": cursor, "limit": 200}
        ).json()
        items.extend(page["items"])
        if not page["next_cursor"]:
            break
        cursor = page["next_cursor"]
    assert [
        event["data"]["index"] for event in items if event["type"] == "data"
    ] == list(range(205))
    assert redis.get("rate-limit:sentinel") == "untouched"


def test_two_api_observers_receive_hunt_progress_and_revocation(execution_system):
    import pytest
    from sqlmodel import Session, select
    from websockets.exceptions import ConnectionClosed

    from app.database.models import CaseUserLink, User
    from tests.executions.test_hunt_execution_system import step, submit_hunt, terminal

    system = execution_system
    system.env["EXECUTION_STREAM_AUTH_SECONDS"] = "0.1"
    _, first = system.api()
    _, second = system.api()
    accepted = submit_hunt(
        system, first, [step("first", static_parameters={"barrier": "release"})]
    )
    system.start("-m", "tests.executions.runtime", "hunt-worker")
    system.start("-m", "app.executions.dispatcher")
    eventually(lambda: (system.root / "provider-starts").exists())
    with Session(system.engine) as db:
        user = db.get(User, system.user_id)
        user.role = "Analyst"
        db.commit()
    with connect(stream(first, accepted, kind="hunt")) as left, connect(
        stream(second, accepted, kind="hunt")
    ) as right:
        a, b = receive(left), receive(right)
        assert a["revision"] == b["revision"]
        assert a["state"]["status"] == b["state"]["status"] == "running"
        # Analyst readers may observe; removing membership closes both APIs.
        with Session(system.engine) as db:
            db.delete(db.exec(select(CaseUserLink)).one())
            db.commit()
        for ws in (left, right):
            with pytest.raises(ConnectionClosed) as closed:
                while True:
                    receive(ws)
            assert closed.value.rcvd.code == 1008
    assert (
        first.post(
            "/api/auth/websocket-token", json={"execution_id": accepted["id"]}
        ).status_code
        == 403
    )
    with Session(system.engine) as db:
        user = db.get(User, system.user_id)
        user.role = "Investigator"
        db.add(CaseUserLink(case_id=system.case_id, user_id=system.user_id))
        db.commit()
    (system.root / "release").touch()
    assert eventually(lambda: terminal(first, accepted))["status"] == "completed"


def test_tokens_expire_are_single_use_and_bind_kind_id_and_current_user(
    execution_system,
):
    from concurrent.futures import ThreadPoolExecutor

    import pytest
    from redis import Redis
    from sqlmodel import Session
    from websockets.exceptions import InvalidStatus

    from app.database.models import User
    from tests.executions.test_hunt_execution_system import step, submit_hunt

    system = execution_system
    _, first = system.api()
    _, second = system.api()
    accepted = submit(first, system)
    hunt = submit_hunt(system, first, [step("first")])
    assert hunt["id"] == accepted["id"]
    from app.core.security import create_access_token

    with Session(system.engine) as db:
        db.add(
            User(
                username="outsider",
                email="outsider@example.org",
                password_hash="unused",
                role="Investigator",
                is_active=True,
            )
        )
        db.commit()
    denied = first.post(
        "/api/auth/websocket-token",
        json={"execution_id": accepted["id"], "kind": "plugin"},
        headers={
            "Authorization": "Bearer " + create_access_token(data={"sub": "outsider"})
        },
    )
    assert denied.status_code == 403
    url = stream(first, accepted)
    wrong_kind = url.replace("/plugins/", "/hunts/")
    with pytest.raises(InvalidStatus):
        connect(wrong_kind)
    url = stream(first, accepted)
    with pytest.raises(InvalidStatus):
        connect(url.replace(f"/{accepted['id']}/stream", "/99999/stream"))
    url = stream(first, accepted)
    redis = Redis.from_url(system.env["REDIS_URL"])
    key = "owlculus:tokens:" + url.split("token=")[1]
    assert 0 < redis.ttl(key) <= 30
    redis.pexpire(key, 1)
    eventually(lambda: not redis.exists(key))
    with pytest.raises(InvalidStatus):
        connect(url)
    url = stream(first, accepted)
    other_url = url.replace(str(first.base_url.port), str(second.base_url.port))

    def consume(target):
        try:
            with connect(target) as ws:
                return receive(ws)["state"]["status"] == "queued"
        except InvalidStatus:
            return False

    with ThreadPoolExecutor(2) as pool:
        assert sorted(pool.map(consume, [url, other_url])) == [False, True]
    url = stream(first, accepted)
    with Session(system.engine) as db:
        user = db.get(User, system.user_id)
        user.is_active = False
        db.commit()
    with pytest.raises(InvalidStatus):
        connect(url)
    assert first.post(
        "/api/auth/websocket-token",
        json={"execution_id": accepted["id"], "kind": "plugin"},
    ).status_code in {401, 403}


def test_commit_between_snapshot_and_subscription_is_replayed(execution_system):
    from concurrent.futures import ThreadPoolExecutor

    from redis import Redis

    from app.executions.events import stream_key

    system = execution_system
    system.env["EXECUTION_TEST_SNAPSHOT_BARRIER"] = "1"
    system.env["EXECUTION_STREAM_AUTH_SECONDS"] = "0.1"
    _, client = system.api()
    accepted = submit(client, system, barrier="release-provider")
    system.worker()
    system.start("-m", "app.executions.dispatcher")
    eventually(lambda: client.get(accepted["links"]["results"]).json()["items"])
    url = stream(client, accepted)

    def observe_completion():
        with connect(url) as ws:
            initial = receive(ws)
            messages = [initial]
            while messages[-1]["revision"] <= initial["revision"]:
                messages.append(receive(ws))
            return messages

    with ThreadPoolExecutor(1) as pool:
        pending = pool.submit(observe_completion)
        eventually(lambda: (system.root / "snapshot-read").exists())
        (system.root / "release-provider").touch()
        terminal = eventually(lambda: finished(client, accepted))
        redis = Redis.from_url(system.env["REDIS_URL"], decode_responses=True)
        key = stream_key("plugin", accepted["id"])
        eventually(
            lambda: redis.xrevrange(key, count=1)[0][0] == f"{terminal['revision']}-0"
        )
        (system.root / "release-snapshot").touch()
        messages = pending.result(timeout=10)
    assert messages[0]["state"]["status"] == "running"
    assert messages[-1]["revision"] > messages[0]["revision"]
    assert messages[-1]["event_type"] == "update"


def test_slow_socket_has_bounded_sends_and_does_not_block_worker_or_other_api(
    execution_system, monkeypatch
):
    import asyncio

    from app.core.security import ephemeral_token_manager
    from app.executions import observation

    system = execution_system
    monkeypatch.setenv("REDIS_URL", system.env["REDIS_URL"])
    monkeypatch.setattr(observation, "SEND_TIMEOUT", 0.02)
    _, client = system.api()
    accepted = submit(client, system, barrier="release")
    token = ephemeral_token_manager.create_token(
        system.user_id, accepted["id"], "plugin"
    )

    class SlowSocket:
        def __init__(self):
            self.query_params = {"token": token}
            self.sends = 0
            self.closed = None

        async def accept(self):
            pass

        async def send_json(self, message):
            self.sends += 1
            await asyncio.Event().wait()

        async def receive_text(self):
            await asyncio.Event().wait()

        async def close(self, code, reason=""):
            self.closed = (code, reason)

    slow = SlowSocket()
    asyncio.run(
        asyncio.wait_for(
            observation.observe(slow, system.engine, "plugin", accepted["id"]), 2
        )
    )
    assert slow.sends == 1
    assert slow.closed == (1013, "Reconnect from 1-0")
    system.worker()
    system.start("-m", "app.executions.dispatcher")
    (system.root / "release").touch()
    state = eventually(lambda: finished(client, accepted))
    with connect(stream(client, accepted)) as ws:
        assert receive(ws)["revision"] == state["revision"]
    assert len(client.get(accepted["links"]["results"]).json()["items"]) == 2


def test_more_than_default_retention_preserves_complete_durable_output(
    execution_system,
):
    from redis import Redis

    from app.executions.events import stream_key

    system = execution_system
    _, client = system.api()
    accepted = submit(client, system, mode="sized", count=10005, bytes=40)
    system.worker()
    system.start("-m", "app.executions.dispatcher")
    state = eventually(lambda: finished(client, accepted), timeout=120)
    assert state["status"] == "completed", state
    redis = Redis.from_url(system.env["REDIS_URL"], decode_responses=True)
    key = stream_key("plugin", accepted["id"])
    eventually(
        lambda: redis.xrevrange(key, count=1)[0][0] == f"{state['revision']}-0",
        timeout=120,
    )
    assert redis.xlen(key) == 10000
    assert all(set(fields) == {"revision"} for _, fields in redis.xrange(key, count=10))
    count, cursor = 0, 0
    while True:
        page = client.get(
            accepted["links"]["results"], params={"cursor": cursor, "limit": 200}
        ).json()
        count += sum(event["type"] == "data" for event in page["items"])
        if page["next_cursor"] is None:
            break
        cursor = page["next_cursor"]
    assert count == 10005
    with connect(stream(client, accepted, cursor="1-0")) as ws:
        assert receive(ws)["event_type"] == "resync"


def test_both_observers_receive_same_updates_and_active_retention_expires_only_after_completion(
    execution_system,
):
    import time

    from redis import Redis
    from websockets.exceptions import ConnectionClosedOK

    from app.executions.events import stream_key

    system = execution_system
    system.env["EXECUTION_STREAM_TTL_SECONDS"] = "3"
    system.env["EXECUTION_STREAM_AUTH_SECONDS"] = "0.1"
    _, first = system.api()
    _, second = system.api()
    accepted = submit(first, system, barrier="release")
    system.worker()
    system.start("-m", "app.executions.dispatcher")
    redis = Redis.from_url(system.env["REDIS_URL"], decode_responses=True)
    key = stream_key("plugin", accepted["id"])
    eventually(lambda: first.get(accepted["links"]["results"]).json()["items"])
    revision = first.get(accepted["links"]["detail"]).json()["revision"]
    eventually(lambda: redis.xrevrange(key, count=1)[0][0] == f"{revision}-0")
    with connect(stream(first, accepted)) as left, connect(
        stream(second, accepted)
    ) as right:
        assert receive(left)["revision"] == receive(right)["revision"] == revision
        time.sleep(4)  # Longer than the configured TTL; provider has no new events.
        assert redis.exists(key)
        (system.root / "release").touch()

        def revisions(ws):
            seen = []
            try:
                while True:
                    message = receive(ws)
                    if message["revision"] > revision:
                        seen.append(message["revision"])
            except ConnectionClosedOK:
                return seen

        a, b = revisions(left), revisions(right)
        assert a == b and a
    state = eventually(lambda: finished(first, accepted))
    assert a[-1] == state["revision"]
    eventually(lambda: not redis.exists(key), timeout=8)
    with connect(stream(second, accepted, cursor=f"{state['revision']}-0")) as ws:
        assert receive(ws)["event_type"] == "resync"
    assert len(second.get(accepted["links"]["results"]).json()["items"]) == 2


def test_lost_event_acknowledgment_retries_without_duplicate_revision(
    execution_system, monkeypatch
):
    from datetime import timedelta

    from redis import Redis
    from redis.exceptions import ConnectionError

    from app.executions import events

    system = execution_system
    _, client = system.api()
    accepted = submit(client, system)
    redis = Redis.from_url(system.env["REDIS_URL"], decode_responses=True)
    from sqlalchemy import text

    from app.database.upgrade_executions import upgrade

    # Recreate the ticket 06 schema, preserving accepted execution identity.
    with system.engine.begin() as connection:
        connection.execute(text("DROP TABLE executionevent"))
        connection.execute(
            text("ALTER TABLE executioncontrol DROP COLUMN event_publish_after")
        )
        connection.execute(
            text("DELETE FROM schema_upgrade WHERE version='007_shared_observation'")
        )
    upgrade(system.engine)
    upgrade(system.engine)

    class LostAcknowledgment:
        def eval(self, *args):
            redis.eval(*args)
            raise ConnectionError("acknowledgment lost")

    assert not events.publish_once(system.engine, LostAcknowledgment())
    now = events.get_utc_now() + timedelta(seconds=3)
    monkeypatch.setattr(events, "get_utc_now", lambda: now)
    assert events.publish_once(system.engine, redis)
    key = events.stream_key("plugin", accepted["id"])
    assert redis.xrange(key) == [("1-0", {"revision": "1"})]
    assert client.get(accepted["links"]["detail"]).json()["status"] == "queued"
