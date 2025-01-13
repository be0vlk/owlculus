import pytest
from sqlmodel import Session
from fastapi import HTTPException

from app.database import models, crud
from app import schemas
from app.services.client_service import ClientService


# Helper function to create a client
async def create_client_helper(db: Session, client_data: dict) -> models.Client:
    client_create = schemas.ClientCreate(**client_data)
    return await crud.create_client(db, client=client_create)


@pytest.mark.asyncio
class TestClientService:

    async def test_get_clients_success(self, session, test_user, test_admin):
        # Create some clients
        await create_client_helper(
            session, {"name": "Client 1", "email": "client1@test.com"}
        )
        await create_client_helper(
            session, {"name": "Client 2", "email": "client2@test.com"}
        )

        # Test with admin user
        client_service = ClientService(session)
        clients = await client_service.get_clients(current_user=test_admin)
        assert len(clients) == 2
        assert clients[0].name == "Client 1"
        assert clients[1].name == "Client 2"

        # Test with regular user
        clients = await client_service.get_clients(current_user=test_user)
        assert len(clients) == 2

    async def test_get_clients_pagination(self, session, test_user):
        # Create some clients
        await create_client_helper(
            session, {"name": "Client 1", "email": "client1@test.com"}
        )
        await create_client_helper(
            session, {"name": "Client 2", "email": "client2@test.com"}
        )
        await create_client_helper(
            session, {"name": "Client 3", "email": "client3@test.com"}
        )

        # Test pagination
        client_service = ClientService(session)
        clients = await client_service.get_clients(
            skip=1, limit=1, current_user=test_user
        )
        assert len(clients) == 1
        assert clients[0].name == "Client 2"

    async def test_get_clients_negative_skip_limit(self, session, test_user):
        client_service = ClientService(session)
        with pytest.raises(ValueError):
            await client_service.get_clients(skip=-1, limit=10, current_user=test_user)
        with pytest.raises(ValueError):
            await client_service.get_clients(skip=0, limit=-5, current_user=test_user)

    async def test_get_clients_analyst_forbidden(self, session, test_analyst):
        client_service = ClientService(session)
        with pytest.raises(HTTPException) as excinfo:
            await client_service.get_clients(current_user=test_analyst)
        assert excinfo.value.status_code == 403
        assert "Not authorized" in excinfo.value.detail

    async def test_get_clients_unauthorized(self, session):
        client_service = ClientService(session)
        with pytest.raises(HTTPException) as excinfo:
            await client_service.get_clients(current_user=None)
        assert excinfo.value.status_code == 401
        assert "Not authorized" in excinfo.value.detail

    async def test_create_client_success(self, session, test_admin):
        client_data = {"name": "New Client", "email": "newclient@test.com"}
        client_create = schemas.ClientCreate(**client_data)
        client_service = ClientService(session)
        created_client = await client_service.create_client(
            client_create, current_user=test_admin
        )
        assert created_client.name == "New Client"
        assert created_client.email == "newclient@test.com"

    async def test_create_client_duplicate_email(self, session, test_admin):
        await create_client_helper(
            session, {"name": "Client 1", "email": "client1@test.com"}
        )
        client_data = {"name": "Client 2", "email": "client1@test.com"}
        client_create = schemas.ClientCreate(**client_data)
        client_service = ClientService(session)
        with pytest.raises(HTTPException) as excinfo:
            await client_service.create_client(client_create, current_user=test_admin)
        assert excinfo.value.status_code == 400
        assert "Email already registered" in excinfo.value.detail

    async def test_create_client_not_admin(self, session, test_user):
        client_data = {"name": "New Client", "email": "newclient@test.com"}
        client_create = schemas.ClientCreate(**client_data)
        client_service = ClientService(session)
        with pytest.raises(HTTPException) as excinfo:
            await client_service.create_client(client_create, current_user=test_user)
        assert excinfo.value.status_code == 403
        assert "Not authorized" in excinfo.value.detail

    async def test_create_client_unauthorized(self, session):
        client_data = {"name": "New Client", "email": "newclient@test.com"}
        client_create = schemas.ClientCreate(**client_data)
        client_service = ClientService(session)
        with pytest.raises(HTTPException) as excinfo:
            await client_service.create_client(client_create, current_user=None)
        assert excinfo.value.status_code == 401
        assert "Not authorized" in excinfo.value.detail

    async def test_get_client_success(self, session, test_user):
        created_client = await create_client_helper(
            session, {"name": "Client 1", "email": "client1@test.com"}
        )
        client_service = ClientService(session)
        retrieved_client = await client_service.get_client(
            created_client.id, current_user=test_user
        )
        assert retrieved_client.id == created_client.id
        assert retrieved_client.name == "Client 1"

    async def test_get_client_not_found(self, session, test_user):
        client_service = ClientService(session)
        with pytest.raises(HTTPException) as excinfo:
            await client_service.get_client(999, current_user=test_user)
        assert excinfo.value.status_code == 404
        assert "Client not found" in excinfo.value.detail

    async def test_get_client_analyst_forbidden(self, session, test_analyst):
        created_client = await create_client_helper(
            session, {"name": "Client 1", "email": "client1@test.com"}
        )
        client_service = ClientService(session)
        with pytest.raises(HTTPException) as excinfo:
            await client_service.get_client(
                created_client.id, current_user=test_analyst
            )
        assert excinfo.value.status_code == 403
        assert "Not authorized" in excinfo.value.detail

    async def test_get_client_unauthorized(self, session):
        created_client = await create_client_helper(
            session, {"name": "Test Client", "email": "test@test.com"}
        )
        client_service = ClientService(session)
        with pytest.raises(HTTPException) as excinfo:
            await client_service.get_client(created_client.id, current_user=None)
        assert excinfo.value.status_code == 401
        assert "Not authorized" in excinfo.value.detail

    async def test_update_client_success(self, session, test_admin):
        created_client = await create_client_helper(
            session, {"name": "Client 1", "email": "client1@test.com"}
        )
        client_update_data = {"name": "Updated Client", "email": "updated@test.com"}
        client_update = schemas.ClientUpdate(**client_update_data)
        client_service = ClientService(session)
        updated_client = await client_service.update_client(
            created_client.id, client_update, current_user=test_admin
        )
        assert updated_client.name == "Updated Client"
        assert updated_client.email == "updated@test.com"

    async def test_update_client_duplicate_email(self, session, test_admin):
        await create_client_helper(
            session, {"name": "Client 1", "email": "client1@test.com"}
        )
        created_client2 = await create_client_helper(
            session, {"name": "Client 2", "email": "client2@test.com"}
        )
        client_update_data = {"email": "client1@test.com"}
        client_update = schemas.ClientUpdate(**client_update_data)
        client_service = ClientService(session)
        with pytest.raises(HTTPException) as excinfo:
            await client_service.update_client(
                created_client2.id, client_update, current_user=test_admin
            )
        assert excinfo.value.status_code == 400
        assert "Email already registered" in excinfo.value.detail

    async def test_update_client_not_found(self, session, test_admin):
        client_update_data = {"name": "Updated Client"}
        client_update = schemas.ClientUpdate(**client_update_data)
        client_service = ClientService(session)
        with pytest.raises(HTTPException) as excinfo:
            await client_service.update_client(
                999, client_update, current_user=test_admin
            )
        assert excinfo.value.status_code == 404
        assert "Client not found" in excinfo.value.detail

    async def test_update_client_not_admin(self, session, test_user):
        created_client = await create_client_helper(
            session, {"name": "Client 1", "email": "client1@test.com"}
        )
        client_update_data = {"name": "Updated Client"}
        client_update = schemas.ClientUpdate(**client_update_data)
        client_service = ClientService(session)
        with pytest.raises(HTTPException) as excinfo:
            await client_service.update_client(
                created_client.id, client_update, current_user=test_user
            )
        assert excinfo.value.status_code == 403
        assert "Not authorized" in excinfo.value.detail

    async def test_update_client_unauthorized(self, session):
        created_client = await create_client_helper(
            session, {"name": "Test Client", "email": "test@test.com"}
        )
        client_update = schemas.ClientUpdate(name="Updated Client")
        client_service = ClientService(session)
        with pytest.raises(HTTPException) as excinfo:
            await client_service.update_client(
                created_client.id, client_update, current_user=None
            )
        assert excinfo.value.status_code == 401
        assert "Not authorized" in excinfo.value.detail
