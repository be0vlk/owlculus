"""Strixy upgrade preserves human sessions and memberships on PostgreSQL."""

from concurrent.futures import ThreadPoolExecutor

from sqlalchemy import text
from sqlmodel import Session, select

from app.database.init_db import initialize_database
from app.database.models import User
from app.database.upgrade_strixy import upgrade


def test_existing_human_collision_and_concurrent_repeatable_upgrade(execution_system):
    system = execution_system
    with Session(system.engine) as db:
        human = db.get(User, system.user_id)
        human.username = "strixy"
        human.email = "strixy@system.invalid"
        human.role = "Admin"
        db.commit()
        db.refresh(human)
        original = human.model_dump()
    with system.engine.begin() as connection:
        connection.execute(
            text('ALTER TABLE "user" DROP COLUMN system_identity CASCADE')
        )
    with ThreadPoolExecutor(2) as pool:
        list(pool.map(upgrade, [system.engine, system.engine]))
    with Session(system.engine) as db:
        strixy = db.exec(select(User).where(User.system_identity == "strixy")).one()
        strixy_id = strixy.id
        assert strixy.role == "Analyst"
        assert strixy.password_hash == "!"
        assert db.get(User, system.user_id).model_dump() == original
    initialize_database(system.engine)
    _, client = system.api()
    # The session issued before upgrade remains valid for the same human.
    me = client.get("/api/users/me")
    assert me.status_code == 200
    assert me.json()["id"] == system.user_id
    assert me.json()["system_identity"] is None
    login = client.post(
        "/api/auth/login",
        data={
            "username": "strixy",
            "password": "acceptance-password",
        },
    )
    assert login.status_code == 200
    users = client.get("/api/users/").json()
    assert [u["id"] for u in users if u["system_identity"] == "strixy"] == [strixy_id]
    case = client.get(f"/api/cases/{system.case_id}").json()
    assert system.user_id in [u["id"] for u in case["users"]]
    assert strixy_id not in [u["id"] for u in case["users"]]
