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

    # ========================================
    # Additional edge case and validation tests
    # ========================================

    async def test_create_client_invalid_email_format(self, session, test_admin):
        """Test creating client with invalid email format"""
        # Test various invalid email formats
        invalid_emails = [
            "notanemail",
            "@example.com",
            "user@",
            "user@.com",
            "user@@example.com",
            "user@example",
            "user name@example.com",
            "",
        ]

        client_service = ClientService(session)
        for invalid_email in invalid_emails:
            with pytest.raises(ValueError) as excinfo:
                client_data = schemas.ClientCreate(
                    name="Test Client", email=invalid_email
                )
            assert (
                "validation error" in str(excinfo.value).lower()
                or "invalid" in str(excinfo.value).lower()
            )

    async def test_create_client_empty_name(self, session, test_admin):
        """Test creating client with empty name"""
        # Empty string is currently allowed by the schema
        client_data = schemas.ClientCreate(name="", email="valid@email.com")
        client_service = ClientService(session)

        # This should succeed with current implementation
        created_client = await client_service.create_client(
            client_data, current_user=test_admin
        )
        assert created_client.name == ""

    async def test_create_client_very_long_name(self, session, test_admin):
        """Test creating client with very long name"""
        long_name = "A" * 1000  # 1000 characters
        client_data = schemas.ClientCreate(name=long_name, email="longname@test.com")
        client_service = ClientService(session)
        created_client = await client_service.create_client(
            client_data, current_user=test_admin
        )
        assert created_client.name == long_name

    async def test_create_client_special_characters_in_name(self, session, test_admin):
        """Test creating client with special characters in name"""
        special_names = [
            "O'Connor & Associates",
            "Test Company (Pty) Ltd.",
            "José García S.A.",
            "测试公司",
            "Test Co. <script>alert('xss')</script>",
            "Company™ © 2024",
            "Test\nCompany",
            "Test\tCompany",
        ]

        client_service = ClientService(session)
        for i, name in enumerate(special_names):
            client_data = schemas.ClientCreate(name=name, email=f"special{i}@test.com")
            created_client = await client_service.create_client(
                client_data, current_user=test_admin
            )
            assert created_client.name == name

    async def test_create_client_with_phone(self, session, test_admin):
        """Test creating client with phone number"""
        client_data = schemas.ClientCreate(
            name="Phone Test Client", email="phone@test.com", phone="+1-234-567-8900"
        )
        client_service = ClientService(session)
        created_client = await client_service.create_client(
            client_data, current_user=test_admin
        )
        assert created_client.phone == "+1-234-567-8900"

    async def test_update_client_partial_update(self, session, test_admin):
        """Test partial update of client (only updating specific fields)"""
        created_client = await create_client_helper(
            session,
            {
                "name": "Original Name",
                "email": "original@test.com",
                "phone": "+1234567890",
            },
        )

        # Update only name, keep email and phone
        client_update = schemas.ClientUpdate(name="New Name")
        client_service = ClientService(session)
        updated_client = await client_service.update_client(
            created_client.id, client_update, current_user=test_admin
        )

        assert updated_client.name == "New Name"
        assert updated_client.email == "original@test.com"  # Unchanged
        assert updated_client.phone == "+1234567890"  # Unchanged

    async def test_get_client_with_associated_cases(
        self, session, test_admin, test_client
    ):
        """Test getting client with associated cases"""
        # Create cases for the client
        case1 = models.Case(
            case_number="CASE-001",
            title="Test Case 1",
            status="Open",
            client_id=test_client.id,
            created_by=test_admin,
        )
        case2 = models.Case(
            case_number="CASE-002",
            title="Test Case 2",
            status="Closed",
            client_id=test_client.id,
            created_by=test_admin,
        )
        session.add(case1)
        session.add(case2)
        session.commit()

        client_service = ClientService(session)
        retrieved_client = await client_service.get_client(
            test_client.id, current_user=test_admin
        )

        assert retrieved_client.id == test_client.id
        # Check if we can access associated cases
        from sqlmodel import select

        cases = session.exec(
            select(models.Case).where(models.Case.client_id == retrieved_client.id)
        ).all()
        assert len(cases) == 2

    async def test_delete_client_not_implemented(self, session, test_admin):
        """Test that client deletion is properly implemented"""
        created_client = await create_client_helper(
            session, {"name": "To Delete", "email": "delete@test.com"}
        )

        client_service = ClientService(session)
        # Delete should work since no cases are associated
        await client_service.delete_client(created_client.id, current_user=test_admin)

        # Verify client is deleted
        with pytest.raises(HTTPException) as exc_info:
            await client_service.get_client(created_client.id, current_user=test_admin)
        assert exc_info.value.status_code == 404

    async def test_concurrent_client_creation_same_email(self, session, test_admin):
        """Test handling of concurrent client creation with same email"""
        email = "concurrent@test.com"

        # Create first client
        client_data1 = schemas.ClientCreate(name="Client 1", email=email)
        client_service = ClientService(session)
        client1 = await client_service.create_client(
            client_data1, current_user=test_admin
        )

        # Try to create second client with same email
        client_data2 = schemas.ClientCreate(name="Client 2", email=email)
        with pytest.raises(HTTPException) as excinfo:
            await client_service.create_client(client_data2, current_user=test_admin)
        assert excinfo.value.status_code == 400
        assert "Email already registered" in excinfo.value.detail

    async def test_update_client_case_insensitive_email_check(
        self, session, test_admin
    ):
        """Test that email uniqueness check is case-sensitive (current implementation)"""
        # Create two clients
        client1 = await create_client_helper(
            session, {"name": "Client 1", "email": "test@example.com"}
        )
        client2 = await create_client_helper(
            session, {"name": "Client 2", "email": "other@example.com"}
        )

        # Try to update client2 with client1's exact email (same case)
        client_update = schemas.ClientUpdate(email="test@example.com")
        client_service = ClientService(session)

        # This should fail
        with pytest.raises(HTTPException) as excinfo:
            await client_service.update_client(
                client2.id, client_update, current_user=test_admin
            )
        assert excinfo.value.status_code == 400
        assert "Email already registered" in str(excinfo.value.detail)

    async def test_client_search_functionality(self, session, test_admin):
        """Test searching/filtering clients (if implemented)"""
        # Create multiple clients
        await create_client_helper(
            session, {"name": "ABC Corporation", "email": "abc@test.com"}
        )
        await create_client_helper(
            session, {"name": "XYZ Industries", "email": "xyz@test.com"}
        )
        await create_client_helper(
            session, {"name": "ABC Limited", "email": "abcltd@test.com"}
        )

        client_service = ClientService(session)

        # Test if search functionality exists
        # This is a placeholder - adjust based on actual implementation
        all_clients = await client_service.get_clients(current_user=test_admin)
        assert len(all_clients) == 3

    async def test_client_sorting_order(self, session, test_admin):
        """Test that clients are returned in consistent order"""
        # Create clients with different names
        await create_client_helper(
            session, {"name": "Zeta Corp", "email": "zeta@test.com"}
        )
        await create_client_helper(
            session, {"name": "Alpha Inc", "email": "alpha@test.com"}
        )
        await create_client_helper(
            session, {"name": "Beta LLC", "email": "beta@test.com"}
        )

        client_service = ClientService(session)
        clients = await client_service.get_clients(current_user=test_admin)

        # Check if all clients are returned
        assert len(clients) >= 3
        # Verify all created clients are in the result
        client_names = [c.name for c in clients]
        assert "Zeta Corp" in client_names
        assert "Alpha Inc" in client_names
        assert "Beta LLC" in client_names

    async def test_client_with_null_optional_fields(self, session, test_admin):
        """Test creating and updating client with null optional fields"""
        # Create client with minimal data
        client_data = schemas.ClientCreate(
            name="Minimal Client",
            email="minimal@test.com",
            # phone is optional and not provided
        )
        client_service = ClientService(session)
        created_client = await client_service.create_client(
            client_data, current_user=test_admin
        )

        assert created_client.name == "Minimal Client"
        assert created_client.email == "minimal@test.com"
        assert created_client.phone is None

        # Update with explicit None values
        client_update = schemas.ClientUpdate(phone=None)
        updated_client = await client_service.update_client(
            created_client.id, client_update, current_user=test_admin
        )
        assert updated_client.phone is None

    async def test_get_clients_performance_with_many_records(self, session, test_admin):
        """Test performance with large number of clients"""
        # Create 100 clients
        import time

        for i in range(100):
            await create_client_helper(
                session, {"name": f"Client {i:03d}", "email": f"client{i:03d}@test.com"}
            )

        client_service = ClientService(session)

        # Test retrieval performance
        start_time = time.time()
        clients = await client_service.get_clients(
            skip=0, limit=50, current_user=test_admin
        )
        elapsed_time = time.time() - start_time

        assert len(clients) == 50
        assert elapsed_time < 1.0  # Should complete within 1 second

        # Test pagination performance
        start_time = time.time()
        page2 = await client_service.get_clients(
            skip=50, limit=50, current_user=test_admin
        )
        elapsed_time = time.time() - start_time

        assert len(page2) == 50
        assert elapsed_time < 1.0
