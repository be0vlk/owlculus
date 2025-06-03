"""
Comprehensive test suite for EntityService
"""

import pytest
from fastapi import HTTPException
from sqlmodel import Session

from app.services.entity_service import EntityService
from app.schemas.entity_schema import EntityCreate, EntityUpdate
from app.database import models


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
            created_by_id=test_admin.id
        )
        entity2 = models.Entity(
            case_id=test_case.id,
            entity_type="company",
            data={"name": "Test Company"},
            created_by_id=test_admin.id
        )
        self.db.add(entity1)
        self.db.add(entity2)
        self.db.commit()

        entities = await self.service.get_case_entities(test_case.id, current_user=test_admin)
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
                created_by_id=test_admin.id
            )
            self.db.add(entity)
        self.db.commit()

        # Test pagination
        page1 = await self.service.get_case_entities(test_case.id, current_user=test_admin, skip=0, limit=2)
        assert len(page1) == 2

        page2 = await self.service.get_case_entities(test_case.id, current_user=test_admin, skip=2, limit=2)
        assert len(page2) == 2

        page3 = await self.service.get_case_entities(test_case.id, current_user=test_admin, skip=4, limit=2)
        assert len(page3) == 1

    async def test_get_case_entities_by_type_filter(self, test_case, test_admin):
        """Test filtering entities by type"""
        # Create entities of different types
        person_entity = models.Entity(
            case_id=test_case.id,
            entity_type="person",
            data={"first_name": "John", "last_name": "Doe"},
            created_by_id=test_admin.id
        )
        company_entity = models.Entity(
            case_id=test_case.id,
            entity_type="company",
            data={"name": "Test Company"},
            created_by_id=test_admin.id
        )
        domain_entity = models.Entity(
            case_id=test_case.id,
            entity_type="domain",
            data={"domain": "example.com"},
            created_by_id=test_admin.id
        )
        self.db.add(person_entity)
        self.db.add(company_entity)
        self.db.add(domain_entity)
        self.db.commit()

        # Test filtering by person type
        persons = await self.service.get_case_entities(test_case.id, current_user=test_admin, entity_type="person")
        assert len(persons) == 1
        assert persons[0].entity_type == "person"

        # Test filtering by company type
        companies = await self.service.get_case_entities(test_case.id, current_user=test_admin, entity_type="company")
        assert len(companies) == 1
        assert companies[0].entity_type == "company"

    async def test_get_case_entities_case_not_found(self, test_admin):
        """Test retrieving entities for non-existent case"""
        with pytest.raises(HTTPException) as exc_info:
            await self.service.get_case_entities(99999, current_user=test_admin)
        assert exc_info.value.status_code == 404
        assert "Case not found" in str(exc_info.value.detail)

    async def test_get_case_entities_empty_list(self, test_case, test_admin):
        """Test retrieving entities when none exist"""
        entities = await self.service.get_case_entities(test_case.id, test_admin)
        assert entities == []

    # =========================
    # create_entity tests
    # =========================

    async def test_create_entity_person_success(self, test_case, test_user):
        """Test creating a person entity"""
        entity_data = EntityCreate(
            entity_type="person",
            data={
                "first_name": "Jane",
                "last_name": "Smith",
                "email": "jane@example.com",
                "phone": "+1234567890"
            }
        )

        entity = await self.service.create_entity(test_case.id, entity_data, current_user=test_user)
        assert entity.entity_type == "person"
        assert entity.data["first_name"] == "Jane"
        assert entity.data["last_name"] == "Smith"
        assert entity.data["email"] == "jane@example.com"
        assert entity.case_id == test_case.id
        assert entity.created_by_id == test_user.id

    async def test_create_entity_company_success(self, test_case, test_user):
        """Test creating a company entity"""
        entity_data = EntityCreate(
            entity_type="company",
            data={
                "name": "Tech Corp",
                "website": "techcorp.com",
                "phone": "+1234567890",
                "domains": ["techcorp.com", "techcorp.io"]
            }
        )

        entity = await self.service.create_entity(test_case.id, entity_data, current_user=test_user)
        assert entity.entity_type == "company"
        assert entity.data["name"] == "Tech Corp"
        assert entity.data["website"] == "techcorp.com"  # No auto-prepending in current implementation
        assert entity.data["domains"] == ["techcorp.com", "techcorp.io"]

    async def test_create_entity_domain_success(self, test_case, test_user):
        """Test creating a domain entity"""
        entity_data = EntityCreate(
            entity_type="domain",
            data={
                "domain": "malicious.com",
                "description": "Suspected phishing domain"
            }
        )

        entity = await self.service.create_entity(test_case.id, entity_data, current_user=test_user)
        assert entity.entity_type == "domain"
        assert entity.data["domain"] == "malicious.com"
        assert entity.data["description"] == "Suspected phishing domain"

    async def test_create_entity_ip_address_success(self, test_case, test_user):
        """Test creating an IP address entity"""
        entity_data = EntityCreate(
            entity_type="ip_address",
            data={
                "ip_address": "192.168.1.1",
                "description": "Suspicious IP"
            }
        )

        entity = await self.service.create_entity(test_case.id, entity_data, current_user=test_user)
        assert entity.entity_type == "ip_address"
        assert entity.data["ip_address"] == "192.168.1.1"

    async def test_create_entity_duplicate_person(self, test_case, test_user):
        """Test creating duplicate person entity"""
        # Create first person
        entity_data = EntityCreate(
            entity_type="person",
            data={"first_name": "John", "last_name": "Doe"}
        )
        await self.service.create_entity(test_case.id, entity_data, current_user=test_user)

        # Try to create duplicate
        with pytest.raises(HTTPException) as exc_info:
            await self.service.create_entity(test_case.id, entity_data, current_user=test_user)
        assert exc_info.value.status_code == 400
        assert "already exists" in str(exc_info.value.detail)

    async def test_create_entity_duplicate_company(self, test_case, test_user):
        """Test creating duplicate company entity"""
        # Create first company
        entity_data = EntityCreate(
            entity_type="company",
            data={"name": "Duplicate Corp"}
        )
        await self.service.create_entity(test_case.id, entity_data, current_user=test_user)

        # Try to create duplicate (case-insensitive)
        duplicate_data = EntityCreate(
            entity_type="company",
            data={"name": "duplicate corp"}  # lowercase
        )
        with pytest.raises(HTTPException) as exc_info:
            await self.service.create_entity(test_case.id, duplicate_data, current_user=test_user)
        assert exc_info.value.status_code == 400
        assert "already exists" in str(exc_info.value.detail)

    async def test_create_entity_case_not_found(self, test_user):
        """Test creating entity for non-existent case"""
        entity_data = EntityCreate(
            entity_type="person",
            data={"first_name": "Test", "last_name": "User"}
        )
        
        with pytest.raises(HTTPException) as exc_info:
            await self.service.create_entity(99999, entity_data, current_user=test_user)
        assert exc_info.value.status_code == 404
        assert "Case not found" in str(exc_info.value.detail)

    async def test_create_entity_analyst_forbidden(self, test_case, test_analyst):
        """Test analyst cannot create entities"""
        entity_data = EntityCreate(
            entity_type="person",
            data={"first_name": "Test", "last_name": "User"}
        )
        
        with pytest.raises(HTTPException) as exc_info:
            await self.service.create_entity(test_case.id, entity_data, current_user=test_analyst)
        assert exc_info.value.status_code == 403

    async def test_create_entity_invalid_type(self, test_case, test_user):
        """Test creating entity with invalid type"""
        with pytest.raises(ValueError) as exc_info:
            EntityCreate(
                entity_type="invalid_type",
                data={"some": "data"}
            )
        assert "Invalid entity type" in str(exc_info.value)

    async def test_create_entity_missing_required_fields(self, test_case, test_user):
        """Test creating entity with missing required fields"""
        # Company without name
        with pytest.raises(ValueError) as exc_info:
            EntityCreate(
                entity_type="company",
                data={"website": "example.com"}  # Missing required "name"
            )
        assert "Invalid data" in str(exc_info.value)

        # Domain without domain field
        with pytest.raises(ValueError) as exc_info:
            EntityCreate(
                entity_type="domain",
                data={"description": "Some description"}  # Missing required "domain"
            )
        assert "Invalid data" in str(exc_info.value)

    async def test_create_entity_invalid_email_format(self, test_case, test_user):
        """Test creating person with invalid email"""
        with pytest.raises(ValueError) as exc_info:
            EntityCreate(
                entity_type="person",
                data={
                    "first_name": "Test",
                    "last_name": "User",
                    "email": "invalid-email"  # Invalid email format
                }
            )
        assert "Invalid data" in str(exc_info.value)

    async def test_create_entity_with_nested_structures(self, test_case, test_user):
        """Test creating entity with complex nested data"""
        entity_data = EntityCreate(
            entity_type="person",
            data={
                "first_name": "John",
                "last_name": "Complex",
                "address": {
                    "street": "123 Main St",
                    "city": "New York",
                    "state": "NY",
                    "country": "USA",
                    "postal_code": "10001"
                },
                "social_media": {
                    "linkedin": "john-complex",
                    "x": "@johncmplx"
                },
                "associates": {
                    "colleagues": "Jane Doe, Bob Smith",
                    "partner/spouse": "Mary Complex"
                }
            }
        )

        entity = await self.service.create_entity(test_case.id, entity_data, current_user=test_user)
        assert entity.data["address"]["city"] == "New York"
        assert entity.data["social_media"]["linkedin"] == "john-complex"
        assert entity.data["associates"]["partner/spouse"] == "Mary Complex"

    # =========================
    # update_entity tests
    # =========================

    async def test_update_entity_success(self, test_case, test_user):
        """Test updating an entity"""
        # Create entity
        entity = models.Entity(
            case_id=test_case.id,
            entity_type="person",
            data={"first_name": "Original", "last_name": "Name"},
            created_by_id=test_user.id
        )
        self.db.add(entity)
        self.db.commit()

        # Update entity
        update_data = EntityUpdate(
            data={
                "first_name": "Updated",
                "last_name": "Name",
                "email": "updated@example.com"
            }
        )

        updated = await self.service.update_entity(entity.id, update_data, current_user=test_user)
        assert updated.data["first_name"] == "Updated"
        assert updated.data["email"] == "updated@example.com"
        assert updated.updated_at >= entity.created_at

    async def test_update_entity_duplicate_check(self, test_case, test_user):
        """Test updating entity to create a duplicate person"""
        # Create two persons with different names
        person1_data = EntityCreate(
            entity_type="person",
            data={"first_name": "John", "last_name": "Doe"}
        )
        person1 = await self.service.create_entity(test_case.id, person1_data, current_user=test_user)
        
        person2_data = EntityCreate(
            entity_type="person", 
            data={"first_name": "Jane", "last_name": "Smith"}
        )
        person2 = await self.service.create_entity(test_case.id, person2_data, current_user=test_user)

        # Try to update person2 to have the same name as person1 - this should fail
        update_data = EntityUpdate(
            data={"first_name": "John", "last_name": "Doe"}
        )

        with pytest.raises(HTTPException) as exc_info:
            await self.service.update_entity(person2.id, update_data, current_user=test_user)
        
        assert exc_info.value.status_code == 400
        assert "already exists" in str(exc_info.value.detail)

    async def test_update_entity_not_found(self, test_user):
        """Test updating non-existent entity"""
        update_data = EntityUpdate(
            data={"first_name": "Test", "last_name": "User"}
        )

        with pytest.raises(HTTPException) as exc_info:
            await self.service.update_entity(99999, update_data, current_user=test_user)
        assert exc_info.value.status_code == 404
        assert "Entity not found" in str(exc_info.value.detail)

    async def test_update_entity_analyst_forbidden(self, test_case, test_analyst):
        """Test analyst cannot update entities"""
        # Create entity
        entity = models.Entity(
            case_id=test_case.id,
            entity_type="person",
            data={"first_name": "Test", "last_name": "User"},
            created_by_id=test_analyst.id
        )
        self.db.add(entity)
        self.db.commit()

        update_data = EntityUpdate(
            data={"first_name": "Updated", "last_name": "User"}
        )

        with pytest.raises(HTTPException) as exc_info:
            await self.service.update_entity(entity.id, update_data, current_user=test_analyst)
        assert exc_info.value.status_code == 403

    async def test_update_entity_type_validation(self, test_case, test_user):
        """Test updating entity validates against its type"""
        # Create company entity
        entity = models.Entity(
            case_id=test_case.id,
            entity_type="company",
            data={"name": "Test Corp"},
            created_by_id=test_user.id
        )
        self.db.add(entity)
        self.db.commit()

        # Try to update with invalid data for company type
        update_data = EntityUpdate(
            data={"invalid_field": "value"}  # name is required for company
        )

        with pytest.raises(HTTPException) as exc_info:
            await self.service.update_entity(entity.id, update_data, current_user=test_user)
        assert exc_info.value.status_code == 400

    async def test_update_entity_preserves_type(self, test_case, test_user):
        """Test entity type cannot be changed during update"""
        # Create person entity
        entity = models.Entity(
            case_id=test_case.id,
            entity_type="person",
            data={"first_name": "John", "last_name": "Doe"},
            created_by_id=test_user.id
        )
        self.db.add(entity)
        self.db.commit()

        # Update with valid person data
        update_data = EntityUpdate(
            data={"first_name": "Jane", "last_name": "Doe"}
        )

        updated = await self.service.update_entity(entity.id, update_data, current_user=test_user)
        assert updated.entity_type == "person"  # Type should not change

    # =========================
    # delete_entity tests
    # =========================

    async def test_delete_entity_success(self, test_case, test_user):
        """Test deleting an entity"""
        # Create entity
        entity = models.Entity(
            case_id=test_case.id,
            entity_type="person",
            data={"first_name": "To", "last_name": "Delete"},
            created_by_id=test_user.id
        )
        self.db.add(entity)
        self.db.commit()
        entity_id = entity.id

        # Delete entity
        await self.service.delete_entity(entity_id, current_user=test_user)

        # Verify deletion
        deleted = self.db.get(models.Entity, entity_id)
        assert deleted is None

    async def test_delete_entity_not_found(self, test_user):
        """Test deleting non-existent entity"""
        with pytest.raises(HTTPException) as exc_info:
            await self.service.delete_entity(99999, current_user=test_user)
        assert exc_info.value.status_code == 404
        assert "Entity not found" in str(exc_info.value.detail)

    async def test_delete_entity_analyst_forbidden(self, test_case, test_analyst):
        """Test analyst cannot delete entities"""
        # Create entity
        entity = models.Entity(
            case_id=test_case.id,
            entity_type="person",
            data={"first_name": "Test", "last_name": "User"},
            created_by_id=test_analyst.id
        )
        self.db.add(entity)
        self.db.commit()

        with pytest.raises(HTTPException) as exc_info:
            await self.service.delete_entity(entity.id, current_user=test_analyst)
        assert exc_info.value.status_code == 403

    async def test_delete_entity_multiple_in_case(self, test_case, test_user):
        """Test deleting one entity doesn't affect others in same case"""
        # Create multiple entities
        entity1 = models.Entity(
            case_id=test_case.id,
            entity_type="person",
            data={"first_name": "Person", "last_name": "One"},
            created_by_id=test_user.id
        )
        entity2 = models.Entity(
            case_id=test_case.id,
            entity_type="person",
            data={"first_name": "Person", "last_name": "Two"},
            created_by_id=test_user.id
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

    async def test_concurrent_entity_creation(self, test_case, test_user, test_admin):
        """Test handling concurrent entity creation"""
        # This test simulates what happens when two users try to create
        # the same entity at nearly the same time
        entity_data = EntityCreate(
            entity_type="company",
            data={"name": "Concurrent Corp"}
        )

        # Create entity as first user
        entity1 = await self.service.create_entity(test_case.id, entity_data, current_user=test_user)
        assert entity1.data["name"] == "Concurrent Corp"

        # Second creation should fail
        with pytest.raises(HTTPException) as exc_info:
            await self.service.create_entity(test_case.id, entity_data, current_user=test_admin)
        assert exc_info.value.status_code == 400

    async def test_entity_with_very_long_data(self, test_case, test_user):
        """Test creating entity with very long text fields"""
        long_text = "A" * 10000  # 10k characters
        entity_data = EntityCreate(
            entity_type="person",
            data={
                "first_name": "Test",
                "last_name": "User",
                "other": long_text
            }
        )

        entity = await self.service.create_entity(test_case.id, entity_data, current_user=test_user)
        assert len(entity.data["other"]) == 10000

    async def test_entity_with_unicode_and_special_chars(self, test_case, test_user):
        """Test entity creation with unicode and special characters"""
        entity_data = EntityCreate(
            entity_type="person",
            data={
                "first_name": "José",
                "last_name": "O'Connor-Smith",
                "other": "K€(7 <™ <script>alert('xss')</script>"
            }
        )

        entity = await self.service.create_entity(test_case.id, entity_data, current_user=test_user)
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
                data={
                    "first_name": f"Person{i}",
                    "last_name": "Test"
                } if i % 2 == 0 else {
                    "name": f"Company{i}"
                },
                created_by_id=test_admin.id
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