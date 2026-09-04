"""
Comprehensive tests for users API endpoints
"""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest.mock import AsyncMock, patch

import pytest
from app.api import auth as auth_api
from app.api import users as users_api
from app.core import rate_limiting, setup
from app.core.config import settings
from app.core.dependencies import (
    get_current_user,
    get_db,
    get_optional_current_user,
)
from app.core.exception_handler import handle_domain_exception
from app.core.exceptions import BaseException as DomainException
from app.core.security import get_password_hash
from app.database.models import User
from app.main import app
from fastapi import FastAPI, status
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient
from loguru import logger
from sqlmodel import Session, select



@pytest.fixture
def test_admin(session: Session) -> User:
    admin = User(
        username="admin",
        email="admin@example.com",
        password_hash="dummy_hash",
        is_active=True,
        role="Admin",
    )
    session.add(admin)
    session.commit()
    session.refresh(admin)
    return admin


@pytest.fixture
def test_user(session: Session) -> User:
    user = User(
        username="testuser",
        email="testuser@example.com",
        password_hash="dummy_hash",
        is_active=True,
        role="Investigator",
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


@pytest.fixture
def test_analyst(session: Session) -> User:
    analyst = User(
        username="analyst",
        email="analyst@example.com",
        password_hash="dummy_hash",
        is_active=True,
        role="Analyst",
    )
    session.add(analyst)
    session.commit()
    session.refresh(analyst)
    return analyst


def override_get_db_factory(session: Session):
    def override_get_db():
        return session

    return override_get_db


def override_get_current_user_factory(user: User):
    def override_get_current_user():
        return user

    return override_get_current_user


def bootstrap_test_app(session: Session) -> FastAPI:
    """Build the API seam without running the production lifespan."""

    async def override_get_db():
        return session

    test_app = FastAPI()
    test_app.add_exception_handler(DomainException, handle_domain_exception)
    test_app.state.bootstrap_rate_limiter = rate_limiting.InMemoryClientRateLimiter(
        max_attempts=3, window_seconds=60 * 60
    )
    test_app.include_router(auth_api.router, prefix="/api/auth")
    test_app.include_router(users_api.router, prefix="/api/users")
    test_app.dependency_overrides[get_db] = override_get_db
    return test_app


async def submit_bootstrap_attempts(
    test_app: FastAPI,
    payload: dict,
    client_address: str,
    *,
    count: int = 4,
    headers_for_attempt=None,
):
    """Submit repeated bootstrap attempts from one observable client address."""
    transport = ASGITransport(app=test_app, client=(client_address, 41000))
    async with AsyncClient(
        transport=transport, base_url="http://testserver"
    ) as async_client:
        return [
            await async_client.post(
                "/api/users/",
                json=payload,
                headers=headers_for_attempt(index) if headers_for_attempt else None,
            )
            for index in range(count)
        ]


@pytest.fixture
def pending_setup_token(tmp_path, monkeypatch) -> str:
    """Persist a pending token behind the setup store's public boundary."""
    monkeypatch.setattr(setup, "SETUP_TOKEN_FILE", tmp_path / ".setup_token")
    return setup.generate_setup_token()


@pytest.fixture
def invalid_bootstrap_payload() -> dict:
    """Return a valid-shaped bootstrap submission carrying the wrong token."""
    return {
        "username": "first_admin",
        "email": "first_admin@example.com",
        "password": "secure-passphrase",
        "setup_token": "wrong-token",
    }


class TestUsersAPI:
    """Test cases for users API endpoints"""

    # POST /api/users/ tests

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "privilege_fields",
        [
            {},
            {"role": "Analyst", "is_active": False, "is_superadmin": False},
            {"role": "Owner", "is_active": "not-a-bool", "is_superadmin": {}},
        ],
        ids=[
            "account-fields-only",
            "client-privileges-ignored",
            "invalid-client-privileges-ignored",
        ],
    )
    async def test_bootstrap_creates_forced_first_administrator(
        self, session: Session, pending_setup_token: str, privilege_fields
    ):
        """A pending setup token creates exactly the privileged first account."""
        test_app = bootstrap_test_app(session)

        with patch("app.services.user_service.get_security_logger") as get_logger:
            async with AsyncClient(
                transport=ASGITransport(app=test_app), base_url="http://testserver"
            ) as async_client:
                response = await async_client.post(
                    "/api/users/",
                    json={
                        "username": "first_admin",
                        "email": "first_admin@example.com",
                        "password": "secure-passphrase",
                        "setup_token": pending_setup_token,
                        **privilege_fields,
                    },
                )

        assert response.status_code == status.HTTP_201_CREATED
        assert response.json() == {
            "id": response.json()["id"],
            "username": "first_admin",
            "email": "first_admin@example.com",
            "role": "Admin",
            "is_active": True,
            "is_superadmin": True,
            "created_at": response.json()["created_at"],
            "updated_at": response.json()["updated_at"],
        }
        persisted_user = session.get(User, response.json()["id"])
        assert persisted_user.role == "Admin"
        assert persisted_user.is_active is True
        assert persisted_user.is_superadmin is True
        assert setup.get_setup_token() is None

        assert setup.is_setup_required(session) is False
        assert "setup_token" not in response.text
        assert pending_setup_token not in response.text
        get_logger.assert_called_once_with(
            action="create_user",
            target_username="first_admin",
            event_type="user_creation_attempt",
            is_bootstrap=True,
        )
        get_logger.return_value.bind.assert_called_once_with(
            user_id=response.json()["id"],
            role="Admin",
            event_type="user_creation_success",
        )

    @pytest.mark.asyncio
    @pytest.mark.parametrize("submitted_token", [None, "wrong-token"])
    async def test_bootstrap_rejects_invalid_token_without_consuming_it(
        self, session: Session, pending_setup_token: str, submitted_token
    ):
        """Missing and invalid setup tokens are logged safely and remain retryable."""
        payload = {
            "username": "first_admin",
            "email": "not-an-email",
            "password": "secure-passphrase",
            "role": "Owner",
        }
        if submitted_token is not None:
            payload["setup_token"] = submitted_token

        with patch("app.services.user_service.get_security_logger") as get_logger:
            response = await self._post_bootstrap(session, payload)

        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert response.json() == {"detail": "Invalid setup token"}
        assert setup.validate_setup_token(pending_setup_token) is True
        assert setup.is_setup_required(session) is True
        assert "user_creation_failed" in str(get_logger.mock_calls)
        assert "invalid_setup_token" in str(get_logger.mock_calls)
        assert pending_setup_token not in str(get_logger.mock_calls)
        assert "secure-passphrase" not in str(get_logger.mock_calls)
        if submitted_token is not None:
            assert submitted_token not in str(get_logger.mock_calls)

    @pytest.mark.asyncio
    async def test_bootstrap_limits_each_client_to_three_attempts_per_hour(
        self,
        session: Session,
        pending_setup_token: str,
        invalid_bootstrap_payload: dict,
    ):
        """A client's fourth anonymous attempt is throttled without affecting peers."""
        test_app = bootstrap_test_app(session)
        responses = await submit_bootstrap_attempts(
            test_app, invalid_bootstrap_payload, "198.51.100.10"
        )

        assert [response.status_code for response in responses] == [403, 403, 403, 429]

        other_response = await submit_bootstrap_attempts(
            test_app,
            invalid_bootstrap_payload,
            "198.51.100.11",
            count=1,
        )
        assert other_response[0].status_code == status.HTTP_403_FORBIDDEN

    @pytest.mark.asyncio
    async def test_bootstrap_uses_atomic_persistent_redis_limit(
        self,
        session: Session,
        pending_setup_token: str,
        invalid_bootstrap_payload: dict,
    ):
        """The deployed limiter atomically prunes, counts, stores, and expires attempts."""
        redis_client = AsyncMock()
        redis_client.eval.side_effect = [1, 1, 1, 0]
        test_app = bootstrap_test_app(session)
        test_app.state.bootstrap_rate_limiter = rate_limiting.RedisClientRateLimiter(
            redis_client, max_attempts=3, window_seconds=60 * 60
        )

        responses = await submit_bootstrap_attempts(
            test_app, invalid_bootstrap_payload, "198.51.100.12"
        )

        assert [response.status_code for response in responses] == [403, 403, 403, 429]
        assert redis_client.eval.await_count == 4
        eval_calls = redis_client.eval.await_args_list
        script = eval_calls[0].args[0]
        assert "redis.call('TIME')" in script
        assert "ZREMRANGEBYSCORE" in script
        assert "ZCARD" in script
        assert "ZADD" in script
        assert "PEXPIRE" in script
        assert {call.args[2] for call in eval_calls} == {
            "owlculus:bootstrap-rate-limit:198.51.100.12"
        }
        assert {call.args[3:5] for call in eval_calls} == {(3_600_000, 3)}
        assert len({call.args[5] for call in eval_calls}) == 4

    @pytest.mark.asyncio
    async def test_untrusted_peer_cannot_spoof_rate_limit_or_security_log_address(
        self,
        session: Session,
        pending_setup_token: str,
        invalid_bootstrap_payload: dict,
    ):
        """Forwarded headers from an untrusted socket peer never identify the client."""
        test_app = bootstrap_test_app(session)
        peer_address = "198.51.100.20"
        records = []
        sink_id = logger.add(lambda message: records.append(message.record))

        try:
            responses = await submit_bootstrap_attempts(
                test_app,
                invalid_bootstrap_payload,
                peer_address,
                headers_for_attempt=lambda index: {
                    "X-Forwarded-For": f"203.0.113.{index + 1}"
                },
            )
        finally:
            logger.remove(sink_id)

        assert [response.status_code for response in responses] == [403, 403, 403, 429]
        rate_limit_records = [
            record
            for record in records
            if record["extra"].get("event_type") == "rate_limit_exceeded"
        ]
        assert len(rate_limit_records) == 1
        assert rate_limit_records[0]["extra"]["client_ip"] == peer_address

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "forwarded_headers",
        [
            {"X-Forwarded-For": "203.0.113.40"},
            {"X-Real-IP": "203.0.113.40"},
        ],
        ids=["forwarded-for", "real-ip"],
    )
    async def test_trusted_proxy_uses_forwarded_address_for_limit_and_logs(
        self,
        session: Session,
        pending_setup_token: str,
        invalid_bootstrap_payload: dict,
        monkeypatch,
        forwarded_headers: dict[str, str],
    ):
        """A trusted gateway's forwarded address identifies the submitting client."""
        proxy_address = "192.0.2.10"
        forwarded_address = "203.0.113.40"
        monkeypatch.setattr(settings, "FORWARDED_ALLOW_IPS", proxy_address)
        test_app = bootstrap_test_app(session)
        records = []
        sink_id = logger.add(lambda message: records.append(message.record))

        try:
            responses = await submit_bootstrap_attempts(
                test_app,
                invalid_bootstrap_payload,
                proxy_address,
                headers_for_attempt=lambda _index: forwarded_headers,
            )
        finally:
            logger.remove(sink_id)

        assert [response.status_code for response in responses] == [403, 403, 403, 429]
        rate_limit_records = [
            record
            for record in records
            if record["extra"].get("event_type") == "rate_limit_exceeded"
        ]
        assert len(rate_limit_records) == 1
        assert rate_limit_records[0]["extra"]["client_ip"] == forwarded_address

    @pytest.mark.asyncio
    async def test_bootstrap_limit_resets_after_one_hour(
        self,
        session: Session,
        pending_setup_token: str,
        invalid_bootstrap_payload: dict,
        monkeypatch,
    ):
        """A client may retry once its one-hour attempt window has elapsed."""
        current_time = [1000.0]
        monkeypatch.setattr(rate_limiting, "monotonic", lambda: current_time[0])
        test_app = bootstrap_test_app(session)
        initial_responses = await submit_bootstrap_attempts(
            test_app, invalid_bootstrap_payload, "198.51.100.30"
        )
        current_time[0] += 3601
        response_after_window = await submit_bootstrap_attempts(
            test_app,
            invalid_bootstrap_payload,
            "198.51.100.30",
            count=1,
        )

        assert [response.status_code for response in initial_responses] == [
            403,
            403,
            403,
            429,
        ]
        assert response_after_window[0].status_code == status.HTTP_403_FORBIDDEN

    @pytest.mark.asyncio
    async def test_authenticated_admin_creation_is_not_rate_limited(
        self, session: Session, test_admin: User
    ):
        """The bootstrap throttle does not reduce authenticated Admin availability."""
        test_app = bootstrap_test_app(session)

        async def override_get_optional_current_user():
            return test_admin

        test_app.dependency_overrides[get_optional_current_user] = (
            override_get_optional_current_user
        )
        transport = ASGITransport(app=test_app, client=("198.51.100.50", 41000))

        async with AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as async_client:
            responses = [
                await async_client.post(
                    "/api/users/",
                    json={
                        "username": f"managed_user_{index}",
                        "email": f"managed_user_{index}@example.com",
                        "password": "password123",
                        "role": "Investigator",
                        "is_active": True,
                    },
                )
                for index in range(4)
            ]

        assert [response.status_code for response in responses] == [201, 201, 201, 201]

    @pytest.mark.asyncio
    async def test_anonymous_creation_stays_unauthorized_after_setup(
        self, session: Session, test_user: User, pending_setup_token: str
    ):
        """A stale-looking setup token never reopens anonymous user creation."""
        response = await self._post_bootstrap(
            session,
            {
                "username": "another_user",
                "email": "not-an-email",
                "password": "secure-passphrase",
                "role": "Owner",
                "setup_token": pending_setup_token,
            },
        )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert response.json() == {"detail": "Authentication required"}
        assert setup.validate_setup_token(pending_setup_token) is True

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("field", "value", "expected_status"),
        [
            ("username", "ab", status.HTTP_422_UNPROCESSABLE_ENTITY),
            ("username", "invalid-name", status.HTTP_422_UNPROCESSABLE_ENTITY),
            ("username", "a" * 51, status.HTTP_422_UNPROCESSABLE_ENTITY),
            ("password", "short", status.HTTP_422_UNPROCESSABLE_ENTITY),
            ("email", "admin@owlculus.local", status.HTTP_422_UNPROCESSABLE_ENTITY),
        ],
    )
    async def test_bootstrap_validation_preserves_token(
        self, session: Session, pending_setup_token: str, field, value, expected_status
    ):
        """Invalid first-administrator credentials leave setup retryable."""
        payload = {
            "username": "first_admin",
            "email": "first_admin@example.com",
            "password": "secure-passphrase",
            "setup_token": pending_setup_token,
        }
        payload[field] = value

        response = await self._post_bootstrap(session, payload)

        assert response.status_code == expected_status
        assert setup.validate_setup_token(pending_setup_token) is True
        assert setup.is_setup_required(session) is True

    @pytest.mark.asyncio
    async def test_bootstrap_validation_response_never_echoes_secrets(
        self, session: Session, pending_setup_token: str
    ):
        """A schema error does not copy request-only secrets into its response."""
        password = "secure-passphrase"

        response = await self._post_bootstrap(
            session,
            {
                "email": "first_admin@example.com",
                "password": password,
                "setup_token": pending_setup_token,
            },
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        assert pending_setup_token not in response.text
        assert password not in response.text

    @pytest.mark.asyncio
    async def test_bootstrap_database_error_preserves_token(
        self, session: Session, pending_setup_token: str
    ):
        """An insert failure does not consume the setup token."""
        with patch(
            "app.services.user_service.crud.create_user",
            side_effect=RuntimeError("simulated insert failure"),
        ):
            response = await self._post_bootstrap(
                session,
                {
                    "username": "first_admin",
                    "email": "first_admin@example.com",
                    "password": "secure-passphrase",
                    "setup_token": pending_setup_token,
                },
            )

        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert setup.validate_setup_token(pending_setup_token) is True
        assert setup.is_setup_required(session) is True

    def test_concurrent_bootstrap_requests_create_one_user(
        self, engine, pending_setup_token: str, monkeypatch
    ):
        """Two valid contenders serialize, and the loser cannot create a user."""
        validation_barrier = Barrier(2)
        validate_setup_token = setup.validate_setup_token

        def synchronize_after_validation(submitted_token):
            is_valid = validate_setup_token(submitted_token)
            validation_barrier.wait(timeout=5)
            return is_valid

        monkeypatch.setattr(setup, "validate_setup_token", synchronize_after_validation)

        async def submit(index: int):
            with Session(engine) as thread_session:
                return await self._post_bootstrap(
                    thread_session,
                    {
                        "username": f"admin_{index}",
                        "email": f"admin_{index}@example.com",
                        "password": "secure-passphrase",
                        "setup_token": pending_setup_token,
                    },
                )

        with ThreadPoolExecutor(max_workers=2) as executor:
            responses = list(
                executor.map(lambda index: asyncio.run(submit(index)), range(2))
            )

        assert sorted(response.status_code for response in responses) == [201, 403]
        losing_response = next(
            response for response in responses if response.status_code == 403
        )
        assert losing_response.json() == {"detail": "Setup already completed"}
        with Session(engine) as verification_session:
            users = verification_session.exec(select(User)).all()
        assert len(users) == 1
        assert setup.get_setup_token() is None

    @pytest.mark.asyncio
    async def test_authenticated_admin_creation_remains_available(
        self, session: Session, test_admin: User
    ):
        """Bootstrap support leaves ordinary Admin-managed creation unchanged."""
        response = await self._post_as_user(
            session,
            test_admin,
            {
                "username": "managed_user",
                "email": "managed_user@example.com",
                "password": "password123",
                "role": "Investigator",
                "is_active": True,
            },
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert response.json()["role"] == "Investigator"
        assert response.json()["is_superadmin"] is False

    @pytest.mark.asyncio
    async def test_authenticated_admin_creation_still_requires_active_state(
        self, session: Session, test_admin: User
    ):
        """The ordinary request schema still requires an explicit active state."""
        response = await self._post_as_user(
            session,
            test_admin,
            {
                "username": "managed_user",
                "email": "managed_user@example.com",
                "password": "password123",
                "role": "Investigator",
            },
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    @pytest.mark.asyncio
    async def test_authenticated_non_admin_creation_remains_forbidden(
        self, session: Session, test_user: User
    ):
        """The anonymous exception does not weaken steady-state authorization."""
        response = await self._post_as_user(
            session,
            test_user,
            {
                "username": "managed_user",
                "email": "managed_user@example.com",
                "password": "password123",
                "role": "Investigator",
                "is_active": True,
            },
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert response.json() == {"detail": "Not authorized"}

    @pytest.mark.asyncio
    async def test_authenticated_admin_still_cannot_create_superadmin(
        self, session: Session, test_admin: User
    ):
        """Only a superadmin may grant superadmin on the ordinary path."""
        response = await self._post_as_user(
            session,
            test_admin,
            {
                "username": "managed_admin",
                "email": "managed_admin@example.com",
                "password": "password123",
                "role": "Admin",
                "is_active": True,
                "is_superadmin": True,
            },
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert response.json() == {
            "detail": "Only superadmin can create superadmin users"
        }

    @staticmethod
    async def _post_bootstrap(session: Session, payload: dict):
        test_app = bootstrap_test_app(session)
        async with AsyncClient(
            transport=ASGITransport(app=test_app), base_url="http://testserver"
        ) as async_client:
            return await async_client.post("/api/users/", json=payload)

    @staticmethod
    async def _post_as_user(session: Session, user: User, payload: dict):
        test_app = bootstrap_test_app(session)

        async def override_get_optional_current_user():
            return user

        test_app.dependency_overrides[get_optional_current_user] = (
            override_get_optional_current_user
        )
        async with AsyncClient(
            transport=ASGITransport(app=test_app), base_url="http://testserver"
        ) as async_client:
            return await async_client.post("/api/users/", json=payload)

    def test_create_user_success_admin(self, session: Session, test_admin: User, client: TestClient):
        """Test successful user creation by admin"""
        app.dependency_overrides[get_optional_current_user] = (
            override_get_current_user_factory(test_admin)
        )
        app.dependency_overrides[get_db] = override_get_db_factory(session)

        user_data = {
            "username": "newuser",
            "email": "newuser@example.com",
            "password": "password123",
            "role": "Investigator",
            "is_active": True,
        }

        try:
            with patch(
                "app.services.user_service.UserService.create_user"
            ) as mock_create:
                mock_user = User(
                    id=1,
                    username=user_data["username"],
                    email=user_data["email"],
                    password_hash="hashed_password",
                    role=user_data["role"],
                    is_active=user_data["is_active"],
                )
                mock_create.return_value = mock_user

                response = client.post("/api/users/", json=user_data)
                assert response.status_code == status.HTTP_201_CREATED
                data = response.json()
                assert data["username"] == user_data["username"]
                assert data["email"] == user_data["email"]
                assert data["role"] == user_data["role"]
        finally:
            app.dependency_overrides.clear()

    def test_create_user_forbidden_non_admin(self, session: Session, test_user: User, client: TestClient):
        """Test user creation forbidden for non-admin"""
        app.dependency_overrides[get_optional_current_user] = (
            override_get_current_user_factory(test_user)
        )
        app.dependency_overrides[get_db] = override_get_db_factory(session)

        user_data = {
            "username": "newuser",
            "email": "newuser@example.com",
            "password": "password123",
            "role": "Investigator",
            "is_active": True,
        }

        try:
            with patch(
                "app.services.user_service.UserService.create_user"
            ) as mock_create:
                from fastapi import HTTPException

                mock_create.side_effect = HTTPException(
                    status_code=403, detail="Permission denied"
                )

                response = client.post("/api/users/", json=user_data)
                assert response.status_code == status.HTTP_403_FORBIDDEN
        finally:
            app.dependency_overrides.clear()

    def test_create_user_invalid_data(self, session: Session, test_admin: User, client: TestClient):
        """Test user creation with invalid data"""
        app.dependency_overrides[get_optional_current_user] = (
            override_get_current_user_factory(test_admin)
        )
        app.dependency_overrides[get_db] = override_get_db_factory(session)

        # Missing required fields
        user_data = {"username": "newuser"}

        try:
            response = client.post("/api/users/", json=user_data)
            assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        finally:
            app.dependency_overrides.clear()

    def test_create_user_duplicate_username(self, session: Session, test_admin: User, client: TestClient):
        """Test user creation with duplicate username"""
        app.dependency_overrides[get_optional_current_user] = (
            override_get_current_user_factory(test_admin)
        )
        app.dependency_overrides[get_db] = override_get_db_factory(session)

        user_data = {
            "username": "admin",  # Duplicate username
            "email": "newadmin@example.com",
            "password": "password123",
            "role": "Admin",
            "is_active": True,
        }

        try:
            with patch(
                "app.services.user_service.UserService.create_user"
            ) as mock_create:
                from fastapi import HTTPException

                mock_create.side_effect = HTTPException(
                    status_code=400, detail="Username already registered"
                )

                response = client.post("/api/users/", json=user_data)
                assert response.status_code == status.HTTP_400_BAD_REQUEST
        finally:
            app.dependency_overrides.clear()

    # GET /api/users/me tests

    def test_read_self_success(self, session: Session, test_user: User, client: TestClient):
        """Test successful self profile retrieval"""
        app.dependency_overrides[get_current_user] = override_get_current_user_factory(
            test_user
        )

        try:
            response = client.get("/api/users/me")
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["id"] == test_user.id
            assert data["username"] == test_user.username
            assert data["email"] == test_user.email
        finally:
            app.dependency_overrides.clear()

    def test_legacy_local_email_user_can_log_in_and_read_self(self, session: Session, client: TestClient):
        """Persisted legacy emails remain readable through authenticated APIs."""
        legacy_user = User(
            username="legacyadmin",
            email="admin@owlculus.local",
            password_hash=get_password_hash("legacy-password"),
            is_active=True,
            role="Admin",
            is_superadmin=True,
        )
        session.add(legacy_user)
        session.commit()
        session.refresh(legacy_user)
        app.dependency_overrides[get_db] = override_get_db_factory(session)

        try:
            login_response = client.post(
                "/api/auth/login",
                data={"username": "legacyadmin", "password": "legacy-password"},
            )
            assert login_response.status_code == status.HTTP_200_OK

            response = client.get(
                "/api/users/me",
                headers={
                    "Authorization": f"Bearer {login_response.json()['access_token']}"
                },
            )

            assert response.status_code == status.HTTP_200_OK
            assert response.json() == {
                "id": legacy_user.id,
                "username": "legacyadmin",
                "email": "admin@owlculus.local",
                "role": "Admin",
                "is_active": True,
                "is_superadmin": True,
                "created_at": legacy_user.created_at.isoformat(),
                "updated_at": legacy_user.updated_at.isoformat(),
            }
        finally:
            app.dependency_overrides.clear()

    def test_read_self_unauthorized(self, client: TestClient):
        """Test self profile retrieval without authentication"""
        response = client.get("/api/users/me")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    # GET /api/users/ tests

    def test_get_users_success_admin(
        self, session: Session, test_admin: User, test_user: User,
    client: TestClient,
    ):
        """Test successful users listing by admin"""
        app.dependency_overrides[get_current_user] = override_get_current_user_factory(
            test_admin
        )
        app.dependency_overrides[get_db] = override_get_db_factory(session)

        try:
            with patch("app.services.user_service.UserService.get_users") as mock_get:
                mock_get.return_value = [test_admin, test_user]

                response = client.get("/api/users/")
                assert response.status_code == status.HTTP_200_OK
                data = response.json()
                assert len(data) == 2
                assert any(user["username"] == "admin" for user in data)
                assert any(user["username"] == "testuser" for user in data)
        finally:
            app.dependency_overrides.clear()

    def test_get_users_with_pagination(self, session: Session, test_admin: User, client: TestClient):
        """Test users listing with pagination"""
        app.dependency_overrides[get_current_user] = override_get_current_user_factory(
            test_admin
        )
        app.dependency_overrides[get_db] = override_get_db_factory(session)

        try:
            with patch("app.services.user_service.UserService.get_users") as mock_get:
                mock_get.return_value = []

                response = client.get("/api/users/?skip=10&limit=5")
                assert response.status_code == status.HTTP_200_OK
        finally:
            app.dependency_overrides.clear()

    def test_get_users_serializes_legacy_local_email(
        self, session: Session, test_admin: User,
    client: TestClient,
    ):
        """User listings retain persisted legacy email addresses."""
        legacy_user = User(
            username="legacyuser",
            email="user@owlculus.local",
            password_hash="dummy_hash",
            is_active=True,
            role="Investigator",
        )
        session.add(legacy_user)
        session.commit()
        session.refresh(legacy_user)
        app.dependency_overrides[get_current_user] = override_get_current_user_factory(
            test_admin
        )
        app.dependency_overrides[get_db] = override_get_db_factory(session)

        try:
            response = client.get("/api/users/")

            assert response.status_code == status.HTTP_200_OK
            serialized_user = next(
                user for user in response.json() if user["id"] == legacy_user.id
            )
            assert serialized_user["email"] == "user@owlculus.local"
            assert set(serialized_user) == {
                "id",
                "username",
                "email",
                "role",
                "is_active",
                "is_superadmin",
                "created_at",
                "updated_at",
            }
        finally:
            app.dependency_overrides.clear()

    def test_get_users_forbidden_non_admin(self, session: Session, test_user: User, client: TestClient):
        """Test users listing forbidden for non-admin"""
        app.dependency_overrides[get_current_user] = override_get_current_user_factory(
            test_user
        )
        app.dependency_overrides[get_db] = override_get_db_factory(session)

        try:
            with patch("app.services.user_service.UserService.get_users") as mock_get:
                from fastapi import HTTPException

                mock_get.side_effect = HTTPException(
                    status_code=403, detail="Permission denied"
                )

                response = client.get("/api/users/")
                assert response.status_code == status.HTTP_403_FORBIDDEN
        finally:
            app.dependency_overrides.clear()

    # PUT /api/users/{user_id} tests

    def test_update_user_success_admin(
        self, session: Session, test_admin: User, test_user: User,
    client: TestClient,
    ):
        """Test successful user update by admin"""
        app.dependency_overrides[get_current_user] = override_get_current_user_factory(
            test_admin
        )
        app.dependency_overrides[get_db] = override_get_db_factory(session)

        update_data = {
            "username": "updateduser",
            "email": "updated@example.com",
            "role": "Admin",
        }

        try:
            with patch(
                "app.services.user_service.UserService.update_user"
            ) as mock_update:
                updated_user = User(**test_user.model_dump())
                updated_user.username = update_data["username"]
                updated_user.email = update_data["email"]
                updated_user.role = update_data["role"]
                mock_update.return_value = updated_user

                response = client.put(f"/api/users/{test_user.id}", json=update_data)
                assert response.status_code == status.HTTP_200_OK
                data = response.json()
                assert data["username"] == update_data["username"]
                assert data["email"] == update_data["email"]
                assert data["role"] == update_data["role"]
        finally:
            app.dependency_overrides.clear()

    def test_update_user_self(self, session: Session, test_user: User, client: TestClient):
        """Test user updating their own profile"""
        app.dependency_overrides[get_current_user] = override_get_current_user_factory(
            test_user
        )
        app.dependency_overrides[get_db] = override_get_db_factory(session)

        update_data = {"username": "updatedself", "email": "updatedself@example.com"}

        try:
            with patch(
                "app.services.user_service.UserService.update_user"
            ) as mock_update:
                updated_user = User(**test_user.model_dump())
                updated_user.username = update_data["username"]
                updated_user.email = update_data["email"]
                mock_update.return_value = updated_user

                response = client.put(f"/api/users/{test_user.id}", json=update_data)
                assert response.status_code == status.HTTP_200_OK
                data = response.json()
                assert data["username"] == update_data["username"]
        finally:
            app.dependency_overrides.clear()

    def test_update_user_not_found(self, session: Session, test_admin: User, client: TestClient):
        """Test user update with non-existent ID"""
        app.dependency_overrides[get_current_user] = override_get_current_user_factory(
            test_admin
        )
        app.dependency_overrides[get_db] = override_get_db_factory(session)

        update_data = {"username": "nonexistent"}

        try:
            with patch(
                "app.services.user_service.UserService.update_user"
            ) as mock_update:
                from fastapi import HTTPException

                mock_update.side_effect = HTTPException(
                    status_code=404, detail="User not found"
                )

                response = client.put("/api/users/999", json=update_data)
                assert response.status_code == status.HTTP_404_NOT_FOUND
        finally:
            app.dependency_overrides.clear()

    def test_update_user_forbidden_other_user(
        self, session: Session, test_user: User, test_analyst: User,
    client: TestClient,
    ):
        """Test user update forbidden for other users"""
        app.dependency_overrides[get_current_user] = override_get_current_user_factory(
            test_user
        )
        app.dependency_overrides[get_db] = override_get_db_factory(session)

        update_data = {"username": "hacker"}

        try:
            with patch(
                "app.services.user_service.UserService.update_user"
            ) as mock_update:
                from fastapi import HTTPException

                mock_update.side_effect = HTTPException(
                    status_code=403, detail="Permission denied"
                )

                response = client.put(f"/api/users/{test_analyst.id}", json=update_data)
                assert response.status_code == status.HTTP_403_FORBIDDEN
        finally:
            app.dependency_overrides.clear()

    # PUT /api/users/me/password tests

    def test_change_password_success(self, session: Session, test_user: User, client: TestClient):
        """Test successful password change"""
        app.dependency_overrides[get_current_user] = override_get_current_user_factory(
            test_user
        )
        app.dependency_overrides[get_db] = override_get_db_factory(session)

        password_data = {
            "current_password": "oldpassword",
            "new_password": "newpassword123",
        }

        try:
            with patch(
                "app.services.user_service.UserService.change_password"
            ) as mock_change:
                mock_change.return_value = test_user

                response = client.put("/api/users/me/password", json=password_data)
                assert response.status_code == status.HTTP_200_OK
                data = response.json()
                assert data["id"] == test_user.id
        finally:
            app.dependency_overrides.clear()

    def test_change_password_wrong_current(self, session: Session, test_user: User, client: TestClient):
        """Test password change with wrong current password"""
        app.dependency_overrides[get_current_user] = override_get_current_user_factory(
            test_user
        )
        app.dependency_overrides[get_db] = override_get_db_factory(session)

        password_data = {
            "current_password": "wrongpassword",
            "new_password": "newpassword123",
        }

        try:
            with patch(
                "app.services.user_service.UserService.change_password"
            ) as mock_change:
                from fastapi import HTTPException

                mock_change.side_effect = HTTPException(
                    status_code=400, detail="Current password is incorrect"
                )

                response = client.put("/api/users/me/password", json=password_data)
                assert response.status_code == status.HTTP_400_BAD_REQUEST
        finally:
            app.dependency_overrides.clear()

    def test_change_password_weak_password(self, session: Session, test_user: User, client: TestClient):
        """Test password change with weak password"""
        app.dependency_overrides[get_current_user] = override_get_current_user_factory(
            test_user
        )
        app.dependency_overrides[get_db] = override_get_db_factory(session)

        password_data = {
            "current_password": "oldpassword",
            "new_password": "123",  # Weak password
        }

        try:
            with patch(
                "app.services.user_service.UserService.change_password"
            ) as mock_change:
                from fastapi import HTTPException

                mock_change.side_effect = HTTPException(
                    status_code=400, detail="Password too weak"
                )

                response = client.put("/api/users/me/password", json=password_data)
                assert response.status_code == status.HTTP_400_BAD_REQUEST
        finally:
            app.dependency_overrides.clear()

    # PUT /api/users/{user_id}/password tests

    def test_admin_reset_password_success(
        self, session: Session, test_admin: User, test_user: User,
    client: TestClient,
    ):
        """Test successful admin password reset"""
        app.dependency_overrides[get_current_user] = override_get_current_user_factory(
            test_admin
        )
        app.dependency_overrides[get_db] = override_get_db_factory(session)

        password_data = {"new_password": "resetpassword123"}

        try:
            with patch(
                "app.services.user_service.UserService.admin_reset_password"
            ) as mock_reset:
                mock_reset.return_value = test_user

                response = client.put(
                    f"/api/users/{test_user.id}/password", json=password_data
                )
                assert response.status_code == status.HTTP_200_OK
                data = response.json()
                assert data["id"] == test_user.id
        finally:
            app.dependency_overrides.clear()

    def test_admin_reset_password_forbidden_non_admin(
        self, session: Session, test_user: User, test_analyst: User,
    client: TestClient,
    ):
        """Test admin password reset forbidden for non-admin"""
        app.dependency_overrides[get_current_user] = override_get_current_user_factory(
            test_user
        )
        app.dependency_overrides[get_db] = override_get_db_factory(session)

        password_data = {"new_password": "resetpassword123"}

        try:
            with patch(
                "app.services.user_service.UserService.admin_reset_password"
            ) as mock_reset:
                from fastapi import HTTPException

                mock_reset.side_effect = HTTPException(
                    status_code=403, detail="Permission denied"
                )

                response = client.put(
                    f"/api/users/{test_analyst.id}/password", json=password_data
                )
                assert response.status_code == status.HTTP_403_FORBIDDEN
        finally:
            app.dependency_overrides.clear()

    def test_admin_reset_password_user_not_found(
        self, session: Session, test_admin: User,
    client: TestClient,
    ):
        """Test admin password reset with non-existent user"""
        app.dependency_overrides[get_current_user] = override_get_current_user_factory(
            test_admin
        )
        app.dependency_overrides[get_db] = override_get_db_factory(session)

        password_data = {"new_password": "resetpassword123"}

        try:
            with patch(
                "app.services.user_service.UserService.admin_reset_password"
            ) as mock_reset:
                from fastapi import HTTPException

                mock_reset.side_effect = HTTPException(
                    status_code=404, detail="User not found"
                )

                response = client.put("/api/users/999/password", json=password_data)
                assert response.status_code == status.HTTP_404_NOT_FOUND
        finally:
            app.dependency_overrides.clear()

    # Authentication and authorization tests

    def test_users_api_unauthorized(self, client: TestClient):
        """Test users API endpoints without authentication"""
        endpoints = [
            ("GET", "/api/users/"),
            ("PUT", "/api/users/1", {"username": "updated"}),
            (
                "PUT",
                "/api/users/me/password",
                {"current_password": "old", "new_password": "new"},
            ),
            ("PUT", "/api/users/1/password", {"new_password": "new"}),
        ]

        for method, endpoint, *data in endpoints:
            json_data = data[0] if data else {}

            if method == "GET":
                response = client.get(endpoint)
            elif method == "POST":
                response = client.post(endpoint, json=json_data)
            elif method == "PUT":
                response = client.put(endpoint, json=json_data)

            assert response.status_code == status.HTTP_401_UNAUTHORIZED

    # Edge cases and validation tests

    def test_users_api_pagination_edge_cases(self, session: Session, test_admin: User, client: TestClient):
        """Test pagination with edge case values"""
        app.dependency_overrides[get_current_user] = override_get_current_user_factory(
            test_admin
        )
        app.dependency_overrides[get_db] = override_get_db_factory(session)

        try:
            with patch("app.services.user_service.UserService.get_users") as mock_get:
                mock_get.return_value = []

                # Test with very large values
                response = client.get("/api/users/?skip=999999&limit=999999")
                assert response.status_code == status.HTTP_200_OK

                # Test with zero limit
                response = client.get("/api/users/?skip=0&limit=0")
                assert response.status_code == status.HTTP_200_OK
        finally:
            app.dependency_overrides.clear()

    def test_users_api_invalid_role(self, session: Session, test_admin: User, client: TestClient):
        """Test user creation with invalid role"""
        app.dependency_overrides[get_optional_current_user] = (
            override_get_current_user_factory(test_admin)
        )
        app.dependency_overrides[get_db] = override_get_db_factory(session)

        user_data = {
            "username": "newuser",
            "email": "newuser@example.com",
            "password": "password123",
            "role": "InvalidRole",  # Invalid role
            "is_active": True,
        }

        try:
            response = client.post("/api/users/", json=user_data)
            assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        finally:
            app.dependency_overrides.clear()

    def test_users_api_invalid_email_format(self, session: Session, test_admin: User, client: TestClient):
        """Test user creation with invalid email format"""
        app.dependency_overrides[get_optional_current_user] = (
            override_get_current_user_factory(test_admin)
        )
        app.dependency_overrides[get_db] = override_get_db_factory(session)

        user_data = {
            "username": "newuser",
            "email": "invalid-email",  # Invalid email format
            "password": "password123",
            "role": "Analyst",
            "is_active": True,
        }

        try:
            response = client.post("/api/users/", json=user_data)
            assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.parametrize(
        ("method", "path", "payload"),
        [
            (
                "post",
                "/api/users/",
                {
                    "username": "newuser",
                    "email": "newuser@owlculus.local",
                    "password": "password123",
                    "role": "Analyst",
                    "is_active": True,
                },
            ),
            ("put", "/api/users/{user_id}", {"email": "newuser@owlculus.local"}),
        ],
    )
    def test_user_writes_reject_local_email(
        self,
        session: Session,
        test_admin: User,
        test_user: User,
        method: str,
        path: str,
        payload: dict,
    client: TestClient,
    ):
        """User input validation continues to reject reserved email suffixes."""
        app.dependency_overrides[get_current_user] = override_get_current_user_factory(
            test_admin
        )
        if method == "post":
            app.dependency_overrides[get_optional_current_user] = (
                override_get_current_user_factory(test_admin)
            )
        app.dependency_overrides[get_db] = override_get_db_factory(session)

        try:
            response = getattr(client, method)(
                path.format(user_id=test_user.id), json=payload
            )

            assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        finally:
            app.dependency_overrides.clear()

    def test_users_api_error_format_consistency(
        self, session: Session, test_admin: User,
    client: TestClient,
    ):
        """Test consistent error response format"""
        app.dependency_overrides[get_current_user] = override_get_current_user_factory(
            test_admin
        )
        app.dependency_overrides[get_db] = override_get_db_factory(session)

        try:
            with patch(
                "app.services.user_service.UserService.update_user"
            ) as mock_update:
                from fastapi import HTTPException

                mock_update.side_effect = HTTPException(
                    status_code=404, detail="User not found"
                )

                response = client.put("/api/users/999", json={"username": "test"})
                assert response.status_code == status.HTTP_404_NOT_FOUND
                error_data = response.json()
                assert "detail" in error_data
                assert isinstance(error_data["detail"], str)
        finally:
            app.dependency_overrides.clear()

    def test_users_api_response_time(self, session: Session, test_admin: User, client: TestClient):
        """Test API response time performance"""
        import time

        app.dependency_overrides[get_current_user] = override_get_current_user_factory(
            test_admin
        )
        app.dependency_overrides[get_db] = override_get_db_factory(session)

        try:
            with patch("app.services.user_service.UserService.get_users") as mock_get:
                mock_get.return_value = []

                start_time = time.time()
                response = client.get("/api/users/")
                end_time = time.time()

                response_time = end_time - start_time

                assert response.status_code == status.HTTP_200_OK
                # Response should be reasonably fast (under 1 second for simple operations)
                assert response_time < 1.0
        finally:
            app.dependency_overrides.clear()
