"""
Comprehensive test suite for EntityService
"""

import pytest
from app.core.exceptions import (
    AuthorizationException,
    DuplicateResourceException,
    ResourceNotFoundException,
    ValidationException,
)
from app.database import models
from app.schemas.entity_schema import EntityCreate, EntityUpdate
from app.services.entity_service import EntityService
from sqlmodel import Session


@pytest.mark.asyncio
class TestEntityService:
    """Test suite for EntityService class"""

    @pytest.fixture(autouse=True)
    def setup_method(self, db_session: Session):
        """Setup test data before each test"""
        self.service = EntityService(db_session)
        self.db = db_session

    # =========================
    # get_case_entities tests
    # =========================

    async def test_get_case_entities_success(self, test_case, test_admin):
        """Test retrieving entities for a case"""
        # Create test entities
        entity1 = models.Entity(
            case_id=test_case.id,
            entity_type="person",
            data={"first_name": "John", "last_name": "Doe"},
            created_by_id=test_admin.id,
        )
        entity2 = models.Entity(
            case_id=test_case.id,
            entity_type="company",
            data={"name": "Test Company"},
            created_by_id=test_admin.id,
        )
        self.db.add(entity1)
        self.db.add(entity2)
        self.db.commit()

        entities = await self.service.get_case_entities(
            test_case.id, current_user=test_admin
        )
        assert len(entities) == 2
        assert entities[0].entity_type in ["person", "company"]
        assert entities[1].entity_type in ["person", "company"]

    async def test_get_case_entities_with_pagination(self, test_case, test_admin):
        """Test pagination of entity results"""
        # Create 5 test entities
        for i in range(5):
            entity = models.Entity(
                case_id=test_case.id,
                entity_type="person",
                data={"first_name": f"Person{i}", "last_name": "Test"},
                created_by_id=test_admin.id,
            )
            self.db.add(entity)
        self.db.commit()

        # Test pagination
        page1 = await self.service.get_case_entities(
            test_case.id, current_user=test_admin, skip=0, limit=2
        )
        assert len(page1) == 2

        page2 = await self.service.get_case_entities(
            test_case.id, current_user=test_admin, skip=2, limit=2
        )
        assert len(page2) == 2

        page3 = await self.service.get_case_entities(
            test_case.id, current_user=test_admin, skip=4, limit=2
        )
        assert len(page3) == 1

    async def test_get_case_entities_by_type_filter(self, test_case, test_admin):
        """Test filtering entities by type"""
        # Create entities of different types
        person_entity = models.Entity(
            case_id=test_case.id,
            entity_type="person",
            data={"first_name": "John", "last_name": "Doe"},
            created_by_id=test_admin.id,
        )
        company_entity = models.Entity(
            case_id=test_case.id,
            entity_type="company",
            data={"name": "Test Company"},
            created_by_id=test_admin.id,
        )
        domain_entity = models.Entity(
            case_id=test_case.id,
            entity_type="domain",
            data={"domain": "example.com"},
            created_by_id=test_admin.id,
        )
        self.db.add(person_entity)
        self.db.add(company_entity)
        self.db.add(domain_entity)
        self.db.commit()

        # Test filtering by person type
        persons = await self.service.get_case_entities(
            test_case.id, current_user=test_admin, entity_type="person"
        )
        assert len(persons) == 1
        assert persons[0].entity_type == "person"

        # Test filtering by company type
        companies = await self.service.get_case_entities(
            test_case.id, current_user=test_admin, entity_type="company"
        )
        assert len(companies) == 1
        assert companies[0].entity_type == "company"

    async def test_get_case_entities_case_not_found(self, test_admin):
        """Test retrieving entities for non-existent case"""
        with pytest.raises(ResourceNotFoundException) as exc_info:
            await self.service.get_case_entities(99999, current_user=test_admin)
        assert "Case not found" in str(exc_info.value)

    async def test_get_case_entities_empty_list(self, test_case, test_admin):
        """Test retrieving entities when none exist"""
        entities = await self.service.get_case_entities(test_case.id, test_admin)
        assert entities == []

    # =========================
    # create_entity tests
    # =========================

    async def test_create_entity_person_success(self, test_case_with_users, test_user):
        """Test creating a person entity"""
        entity_data = EntityCreate(
            entity_type="person",
            data={
                "first_name": "Jane",
                "last_name": "Smith",
                "email": "jane@example.com",
                "phone": "+1234567890",
            },
        )

        entity = await self.service.create_entity(
            test_case_with_users.id, entity_data, current_user=test_user
        )
        assert entity.entity_type == "person"
        assert entity.data["first_name"] == "Jane"
        assert entity.data["last_name"] == "Smith"
        assert entity.data["email"] == "jane@example.com"
        assert entity.case_id == test_case_with_users.id
        assert entity.created_by_id == test_user.id

    async def test_create_entity_company_success(self, test_case_with_users, test_user):
        """Test creating a company entity"""
        entity_data = EntityCreate(
            entity_type="company",
            data={
                "name": "Tech Corp",
                "website": "techcorp.com",
                "phone": "+1234567890",
                "domains": ["techcorp.com", "techcorp.io"],
            },
        )

        entity = await self.service.create_entity(
            test_case_with_users.id, entity_data, current_user=test_user
        )
        assert entity.entity_type == "company"
        assert entity.data["name"] == "Tech Corp"
        assert (
            entity.data["website"] == "techcorp.com"
        )  # No auto-prepending in current implementation
        assert entity.data["domains"] == ["techcorp.com", "techcorp.io"]

    async def test_create_entity_domain_success(self, test_case_with_users, test_user):
        """Test creating a domain entity"""
        entity_data = EntityCreate(
            entity_type="domain",
            data={
                "domain": "malicious.com",
                "description": "Suspected phishing domain",
            },
        )

        entity = await self.service.create_entity(
            test_case_with_users.id, entity_data, current_user=test_user
        )
        assert entity.entity_type == "domain"
        assert entity.data["domain"] == "malicious.com"
        assert entity.data["description"] == "Suspected phishing domain"

    async def test_create_entity_ip_address_success(self, test_case_with_users, test_user):
        """Test creating an IP address entity"""
        entity_data = EntityCreate(
            entity_type="ip_address",
            data={"ip_address": "192.168.1.1", "description": "Suspicious IP"},
        )

        entity = await self.service.create_entity(
            test_case_with_users.id, entity_data, current_user=test_user
        )
        assert entity.entity_type == "ip_address"
        assert entity.data["ip_address"] == "192.168.1.1"

    async def test_create_entity_duplicate_person(self, test_case_with_users, test_user):
        """Test creating duplicate person entity"""
        # Create first person
        entity_data = EntityCreate(
            entity_type="person", data={"first_name": "John", "last_name": "Doe"}
        )
        await self.service.create_entity(
            test_case_with_users.id, entity_data, current_user=test_user
        )

        # Try to create duplicate
        with pytest.raises(DuplicateResourceException) as exc_info:
            await self.service.create_entity(
                test_case_with_users.id, entity_data, current_user=test_user
            )
        assert "already exists" in str(exc_info.value)

    async def test_create_entity_duplicate_company(self, test_case_with_users, test_user):
        """Test creating duplicate company entity"""
        # Create first company
        entity_data = EntityCreate(
            entity_type="company", data={"name": "Duplicate Corp"}
        )
        await self.service.create_entity(
            test_case_with_users.id, entity_data, current_user=test_user
        )

        # Try to create duplicate (case-insensitive)
        duplicate_data = EntityCreate(
            entity_type="company", data={"name": "duplicate corp"}  # lowercase
        )
        with pytest.raises(DuplicateResourceException) as exc_info:
            await self.service.create_entity(
                test_case_with_users.id, duplicate_data, current_user=test_user
            )
        assert "already exists" in str(exc_info.value)

    async def test_create_entity_analyst_can_read_but_api_prevents_write(self, test_case_with_users, test_analyst):
        """Test that service layer allows analyst to create (API layer will block)"""
        entity_data = EntityCreate(
            entity_type="person", data={"first_name": "Test", "last_name": "User"}
        )

        # Service layer should not block analysts - that's the API's job
        entity = await self.service.create_entity(
            test_case_with_users.id, entity_data, current_user=test_analyst
        )
        assert entity.entity_type == "person"
        assert entity.data["first_name"] == "Test"

    async def test_update_entity_analyst_can_read_but_api_prevents_write(self, test_case_with_users, test_analyst):
        """Test that service layer allows analyst to update (API layer will block)"""
        # Create entity
        entity = models.Entity(
            case_id=test_case_with_users.id,
            entity_type="person",
            data={"first_name": "Test", "last_name": "User"},
            created_by_id=test_analyst.id,
        )
        self.db.add(entity)
        self.db.commit()

        update_data = EntityUpdate(data={"first_name": "Updated", "last_name": "User"})

        # Service layer should not block analysts - that's the API's job
        updated = await self.service.update_entity(
            entity.id, update_data, current_user=test_analyst
        )
        assert updated.data["first_name"] == "Updated"

    async def test_delete_entity_analyst_can_read_but_api_prevents_write(self, test_case_with_users, test_analyst):
        """Test that service layer allows analyst to delete (API layer will block)"""
        # Create entity  
        entity = models.Entity(
            case_id=test_case_with_users.id,
            entity_type="person",
            data={"first_name": "Test", "last_name": "User"},
            created_by_id=test_analyst.id,
        )
        self.db.add(entity)
        self.db.commit()
        entity_id = entity.id

        # Service layer should not block analysts - that's the API's job
        await self.service.delete_entity(entity_id, current_user=test_analyst)

        # Verify entity was deleted
        deleted_entity = self.db.get(models.Entity, entity_id)
        assert deleted_entity is None

    async def test_delete_entity_multiple_in_case(self, test_case_with_users, test_user):
        """Test deleting one entity doesn't affect others in same case"""
        # Create multiple entities
        entity1 = models.Entity(
            case_id=test_case_with_users.id,
            entity_type="person",
            data={"first_name": "Person", "last_name": "One"},
            created_by_id=test_user.id,
        )
        entity2 = models.Entity(
            case_id=test_case_with_users.id,
            entity_type="person",
            data={"first_name": "Person", "last_name": "Two"},
            created_by_id=test_user.id,
        )
        self.db.add(entity1)
        self.db.add(entity2)
        self.db.commit()

        # Delete only entity1
        await self.service.delete_entity(entity1.id, current_user=test_user)

        # Verify entity2 still exists
        remaining = self.db.get(models.Entity, entity2.id)
        assert remaining is not None
        assert remaining.data["last_name"] == "Two"

    # =========================
    # Edge cases and performance tests
    # =========================

    async def test_concurrent_entity_creation(self, test_case_with_users, test_user, test_admin):
        """Test handling concurrent entity creation"""
        # This test simulates what happens when two users try to create
        # the same entity at nearly the same time
        entity_data = EntityCreate(
            entity_type="company", data={"name": "Concurrent Corp"}
        )

        # Create entity as first user
        entity1 = await self.service.create_entity(
            test_case_with_users.id, entity_data, current_user=test_user
        )
        assert entity1.data["name"] == "Concurrent Corp"

        # Second creation should fail
        with pytest.raises(DuplicateResourceException) as exc_info:
            await self.service.create_entity(
                test_case_with_users.id, entity_data, current_user=test_admin
            )
        assert "already exists" in str(exc_info.value)

    async def test_entity_with_very_long_data(self, test_case_with_users, test_user):
        """Test creating entity with very long text fields"""
        long_text = "A" * 10000  # 10k characters
        entity_data = EntityCreate(
            entity_type="person",
            data={"first_name": "Test", "last_name": "User", "other": long_text},
        )

        entity = await self.service.create_entity(
            test_case_with_users.id, entity_data, current_user=test_user
        )
        assert len(entity.data["other"]) == 10000

    async def test_entity_with_unicode_and_special_chars(self, test_case_with_users, test_user):
        """Test entity creation with unicode and special characters"""
        entity_data = EntityCreate(
            entity_type="person",
            data={
                "first_name": "José",
                "last_name": "O'Connor-Smith",
                "other": "K€(7 <™ <script>alert('xss')</script>",
            },
        )

        entity = await self.service.create_entity(
            test_case_with_users.id, entity_data, current_user=test_user
        )
        assert entity.data["first_name"] == "José"
        assert entity.data["last_name"] == "O'Connor-Smith"
        assert "K€(7" in entity.data["other"]
        assert "<™" in entity.data["other"]
        assert "<script>" in entity.data["other"]  # Should be stored as-is

    async def test_bulk_entity_retrieval_performance(self, test_case, test_admin):
        """Test performance with large number of entities"""
        # Create 100 entities
        for i in range(100):
            entity = models.Entity(
                case_id=test_case.id,
                entity_type="person" if i % 2 == 0 else "company",
                data=(
                    {"first_name": f"Person{i}", "last_name": "Test"}
                    if i % 2 == 0
                    else {"name": f"Company{i}"}
                ),
                created_by_id=test_admin.id,
            )
            self.db.add(entity)
        self.db.commit()

        # Test retrieval with pagination
        import time

        start_time = time.time()

        entities = await self.service.get_case_entities(
            test_case.id, current_user=test_admin, skip=0, limit=50
        )

        elapsed_time = time.time() - start_time

        assert len(entities) == 50
        assert elapsed_time < 1.0  # Should complete within 1 second

    # =========================
    # Entity lookup tests
    # =========================

    async def test_find_entity_by_ip_address_success(self, test_case_with_users, test_user):
        """Test finding an existing IP address entity"""
        # Create IP entity
        entity_data = EntityCreate(
            entity_type="ip_address",
            data={"ip_address": "10.0.0.1", "description": "Test IP"},
        )
        created_entity = await self.service.create_entity(
            test_case_with_users.id, entity_data, current_user=test_user
        )

        # Find the entity
        found_entity = await self.service.find_entity_by_ip_address(
            test_case_with_users.id, "10.0.0.1", test_user
        )

        assert found_entity is not None
        assert found_entity.id == created_entity.id
        assert found_entity.data["ip_address"] == "10.0.0.1"

    async def test_find_entity_by_ip_address_not_found(self, test_case_with_users, test_user):
        """Test finding non-existent IP address entity"""
        found_entity = await self.service.find_entity_by_ip_address(
            test_case_with_users.id, "192.168.99.99", test_user
        )
        assert found_entity is None

    async def test_find_entity_by_ip_address_case_not_found(self, test_user):
        """Test finding IP entity in non-existent case"""
        with pytest.raises(ResourceNotFoundException) as exc_info:
            await self.service.find_entity_by_ip_address(99999, "192.168.1.1", test_user)
        assert "Case not found" in str(exc_info.value)

    async def test_find_entity_by_domain_success(self, test_case_with_users, test_user):
        """Test finding an existing domain entity"""
        # Create domain entity
        entity_data = EntityCreate(
            entity_type="domain",
            data={"domain": "TestDomain.Com", "description": "Test domain"},
        )
        created_entity = await self.service.create_entity(
            test_case_with_users.id, entity_data, current_user=test_user
        )

        # Find the entity (case-insensitive)
        found_entity = await self.service.find_entity_by_domain(
            test_case_with_users.id, "testdomain.com", test_user
        )

        assert found_entity is not None
        assert found_entity.id == created_entity.id
        assert found_entity.data["domain"] == "TestDomain.Com"

    async def test_find_entity_by_domain_not_found(self, test_case_with_users, test_user):
        """Test finding non-existent domain entity"""
        found_entity = await self.service.find_entity_by_domain(
            test_case_with_users.id, "nonexistent.com", test_user
        )
        assert found_entity is None

    async def test_find_entity_by_domain_case_not_found(self, test_user):
        """Test finding domain entity in non-existent case"""
        with pytest.raises(ResourceNotFoundException) as exc_info:
            await self.service.find_entity_by_domain(99999, "example.com", test_user)
        assert "Case not found" in str(exc_info.value)

    # =========================
    # Entity enrichment tests
    # =========================

    async def test_enrich_entity_description_new_description(
            self, test_case_with_users, test_user
    ):
        """Test enriching entity with new description"""
        # Create entity without description
        entity_data = EntityCreate(
            entity_type="ip_address", data={"ip_address": "172.16.0.1"}
        )
        created_entity = await self.service.create_entity(
            test_case_with_users.id, entity_data, current_user=test_user
        )

        # Store original state
        original_created_at = created_entity.created_at
        assert "description" not in created_entity.data  # Verify no description initially

        # Enrich with description
        enriched_entity = await self.service.enrich_entity_description(
            created_entity.id,
            "Discovered via Shodan: Apache server on port 80",
            current_user=test_user,
        )

        # Verify enrichment worked
        assert (
            enriched_entity.data["description"]
            == "Discovered via Shodan: Apache server on port 80"
        )
        # Verify it's the same entity
        assert enriched_entity.id == created_entity.id
        # Created_at should remain the same
        assert enriched_entity.created_at == original_created_at
        # Updated_at should be set (at least equal to or after created_at)
        assert enriched_entity.updated_at >= enriched_entity.created_at

    async def test_enrich_entity_description_append_to_existing(
            self, test_case_with_users, test_user
    ):
        """Test enriching entity that already has a description"""
        # Create entity with existing description
        entity_data = EntityCreate(
            entity_type="ip_address",
            data={
                "ip_address": "172.16.0.2",
                "description": "Original description from manual entry",
            },
        )
        created_entity = await self.service.create_entity(
            test_case_with_users.id, entity_data, current_user=test_user
        )

        # Enrich with additional description
        enriched_entity = await self.service.enrich_entity_description(
            created_entity.id,
            "Additional info from Shodan scan",
            current_user=test_user,
        )

        expected_description = "Original description from manual entry\n\n--- Additional Info ---\nAdditional info from Shodan scan"
        assert enriched_entity.data["description"] == expected_description

    async def test_enrich_entity_description_not_found(self, test_user):
        """Test enriching non-existent entity"""
        with pytest.raises(ResourceNotFoundException) as exc_info:
            await self.service.enrich_entity_description(
                99999, "Some description", current_user=test_user
            )
        assert "Entity not found" in str(exc_info.value)

    async def test_enrich_entity_description_analyst_can_read_but_api_prevents_write(
            self, test_case_with_users, test_analyst
    ):
        """Test that service layer allows analyst to enrich (API layer will block)"""
        # Create entity
        entity = models.Entity(
            case_id=test_case_with_users.id,
            entity_type="ip_address",
            data={"ip_address": "172.16.0.3"},
            created_by_id=test_analyst.id,
        )
        self.db.add(entity)
        self.db.commit()

        # Service layer should not block analysts - that's the API's job
        enriched = await self.service.enrich_entity_description(
            entity.id, "Some enrichment", current_user=test_analyst
        )
        assert enriched.data["description"] == "Some enrichment"
