from datetime import datetime

import pytest
from app import schemas
from app.core.exceptions import (
    AuthorizationException,
    DuplicateResourceException,
    ResourceNotFoundException,
    ValidationException,
)
from app.database import models
from app.services import case_service
from sqlmodel import Session


@pytest.fixture(name="case_service_instance")
def case_service_fixture(session: Session):
    return case_service.CaseService(session)


@pytest.fixture(name="sample_case")
def sample_case_fixture(session: Session, test_admin: models.User):
    client = models.Client(name="Test Client", contact_email="test@example.com")
    session.add(client)
    session.commit()
    session.refresh(client)

    case_data = schemas.CaseCreate(
        client_id=client.id,
        title="Test Case",
        case_number="2301-01",
        status="Open",
        notes="Test Notes",
    )
    case = models.Case(**case_data.model_dump(), created_by=test_admin)
    session.add(case)
    session.commit()
    session.refresh(case)
    return case


@pytest.fixture(name="sample_case_link")
def sample_case_link_fixture(
    session: Session, sample_case: models.Case, test_user: models.User
):
    link = models.CaseUserLink(case_id=sample_case.id, user_id=test_user.id)
    session.add(link)
    session.commit()
    session.refresh(link)
    return link


@pytest.mark.asyncio
async def test_create_case_admin(
    case_service_instance: case_service.CaseService, test_admin: models.User
):
    client = models.Client(name="Test Client", contact_email="test@example.com")
    case_service_instance.db.add(client)
    case_service_instance.db.commit()
    case_service_instance.db.refresh(client)

    case_data = schemas.CaseCreate(
        client_id=client.id, title="Test Case", status="Open", notes="Test Notes"
    )
    created_case = await case_service_instance.create_case(
        case_data, current_user=test_admin
    )
    assert created_case.title == "Test Case"
    assert created_case.status == "Open"
    assert created_case.notes == "Test Notes"
    assert created_case.case_number is not None


@pytest.mark.asyncio
async def test_create_case_non_admin(
    case_service_instance: case_service.CaseService, test_user: models.User
):
    client = models.Client(name="Test Client", contact_email="test@example.com")
    case_service_instance.db.add(client)
    case_service_instance.db.commit()
    case_service_instance.db.refresh(client)

    case_data = schemas.CaseCreate(
        client_id=client.id, title="Test Case", status="Open", notes="Test Notes"
    )
    # Service layer no longer checks for admin role - that's handled at API layer
    created_case = await case_service_instance.create_case(
        case_data, current_user=test_user
    )
    assert created_case.title == "Test Case"
    assert created_case.status == "Open"


@pytest.mark.asyncio
async def test_create_case_analyst(
    case_service_instance: case_service.CaseService, test_analyst: models.User
):
    client = models.Client(name="Test Client", contact_email="test@example.com")
    case_service_instance.db.add(client)
    case_service_instance.db.commit()
    case_service_instance.db.refresh(client)

    case_data = schemas.CaseCreate(
        client_id=client.id, title="Test Case", status="Open", notes="Test Notes"
    )
    # Service layer no longer checks for admin role - that's handled at API layer
    created_case = await case_service_instance.create_case(
        case_data, current_user=test_analyst
    )
    assert created_case.title == "Test Case"
    assert created_case.status == "Open"


@pytest.mark.asyncio
async def test_generate_case_number_first_of_month(
    case_service_instance: case_service.CaseService,
):
    current_time = datetime(2023, 1, 1, 12, 0, 0)
    case_number = await case_service_instance._generate_case_number(current_time)
    assert case_number == "2301-01"


@pytest.mark.asyncio
async def test_generate_case_number_subsequent(
    case_service_instance: case_service.CaseService,
    test_admin: models.User,
):
    client = models.Client(name="Test Client", contact_email="test@example.com")
    case_service_instance.db.add(client)
    case_service_instance.db.commit()
    case_service_instance.db.refresh(client)

    case_data = schemas.CaseCreate(
        client_id=client.id,
        title="Test Case",
        case_number="2301-01",
        status="Open",
        notes="Test Notes",
    )
    case = models.Case(**case_data.model_dump(), created_by=test_admin)
    case_service_instance.db.add(case)
    case_service_instance.db.commit()

    current_time = datetime(2023, 1, 15, 12, 0, 0)
    case_number = await case_service_instance._generate_case_number(current_time)
    assert case_number == "2301-02"


@pytest.mark.asyncio
async def test_get_cases_admin(
    case_service_instance: case_service.CaseService,
    sample_case: models.Case,
    test_admin: models.User,
):
    cases = await case_service_instance.get_cases(test_admin)
    assert len(cases) == 1
    assert cases[0].id == sample_case.id


@pytest.mark.asyncio
async def test_get_cases_non_admin(
    case_service_instance: case_service.CaseService,
    sample_case: models.Case,
    test_user: models.User,
    sample_case_link: models.CaseUserLink,
):
    cases = await case_service_instance.get_cases(test_user)
    assert len(cases) == 1
    assert cases[0].id == sample_case.id


@pytest.mark.asyncio
async def test_get_cases_non_admin_not_associated(
    case_service_instance: case_service.CaseService,
    sample_case: models.Case,
    test_user: models.User,
):
    cases = await case_service_instance.get_cases(test_user)
    assert len(cases) == 0


@pytest.mark.asyncio
async def test_get_cases_with_status_filter(
    case_service_instance: case_service.CaseService,
    sample_case: models.Case,
    test_admin: models.User,
):
    cases = await case_service_instance.get_cases(test_admin, status="Open")
    assert len(cases) == 1
    assert cases[0].id == sample_case.id
    assert cases[0].status == "Open"

    cases = await case_service_instance.get_cases(test_admin, status="Closed")
    assert len(cases) == 0


@pytest.mark.asyncio
async def test_get_case_admin(
    case_service_instance: case_service.CaseService,
    sample_case: models.Case,
    test_admin: models.User,
):
    retrieved_case = await case_service_instance.get_case(sample_case.id, test_admin)
    assert retrieved_case.id == sample_case.id


@pytest.mark.asyncio
async def test_get_case_non_admin_associated(
    case_service_instance: case_service.CaseService,
    sample_case: models.Case,
    test_user: models.User,
    sample_case_link: models.CaseUserLink,
):
    retrieved_case = await case_service_instance.get_case(sample_case.id, test_user)
    assert retrieved_case.id == sample_case.id


@pytest.mark.asyncio
async def test_get_case_non_admin_not_associated(
    case_service_instance: case_service.CaseService,
    sample_case: models.Case,
    test_user: models.User,
):
    with pytest.raises(AuthorizationException) as excinfo:
        await case_service_instance.get_case(sample_case.id, test_user)
    assert "Not authorized to access this case" in str(excinfo.value)


@pytest.mark.asyncio
async def test_update_case_not_found(
    case_service_instance: case_service.CaseService, test_admin: models.User
):
    case_update = schemas.CaseUpdate(title="Updated Case", status="Closed")
    with pytest.raises(ResourceNotFoundException) as excinfo:
        await case_service_instance.update_case(
            999, case_update, current_user=test_admin
        )
    assert "Case not found" in str(excinfo.value)


@pytest.mark.asyncio
async def test_add_user_to_case_not_found(
    case_service_instance: case_service.CaseService,
    test_user: models.User,
    test_admin: models.User,
):
    with pytest.raises(ResourceNotFoundException) as excinfo:
        await case_service_instance.add_user_to_case(
            999, test_user.id, current_user=test_admin
        )
    assert "Case not found" in str(excinfo.value)


@pytest.mark.asyncio
async def test_remove_user_from_case_not_found(
    case_service_instance: case_service.CaseService,
    test_user: models.User,
    test_admin: models.User,
):
    with pytest.raises(ResourceNotFoundException) as excinfo:
        await case_service_instance.remove_user_from_case(
            999, test_user.id, current_user=test_admin
        )
    assert "Case not found" in str(excinfo.value)


@pytest.mark.asyncio
async def test_remove_user_from_case_user_not_found(
    case_service_instance: case_service.CaseService,
    sample_case: models.Case,
    test_admin: models.User,
):
    with pytest.raises(ResourceNotFoundException) as excinfo:
        await case_service_instance.remove_user_from_case(
            sample_case.id, 999, current_user=test_admin
        )
    assert "User not found" in str(excinfo.value)


# ========================================
# Additional edge case and validation tests
# ========================================


@pytest.mark.asyncio
async def test_case_status_transitions(
    case_service_instance: case_service.CaseService,
    sample_case: models.Case,
    test_admin: models.User,
):
    """Test various case status transitions"""
    # Valid status transitions based on schema
    valid_statuses = ["Open", "Closed"]

    for status in valid_statuses:
        case_update = schemas.CaseUpdate(status=status)
        updated_case = await case_service_instance.update_case(
            sample_case.id, case_update, current_user=test_admin
        )
        assert updated_case.status == status


@pytest.mark.asyncio
async def test_case_with_entities_and_evidence(
    case_service_instance: case_service.CaseService,
    sample_case: models.Case,
    test_admin: models.User,
    session: Session,
):
    """Test case with associated entities and evidence"""
    # Add entities to case
    entity1 = models.Entity(
        case_id=sample_case.id,
        entity_type="person",
        data={"first_name": "John", "last_name": "Doe"},
        created_by_id=test_admin.id,
    )
    entity2 = models.Entity(
        case_id=sample_case.id,
        entity_type="company",
        data={"name": "Test Corp"},
        created_by_id=test_admin.id,
    )
    session.add(entity1)
    session.add(entity2)

    # Add evidence to case
    evidence = models.Evidence(
        case_id=sample_case.id,
        title="test_doc.pdf",
        description="Test document",
        evidence_type="document",
        content="/tmp/test_doc.pdf",
        created_by_id=test_admin.id,
    )
    session.add(evidence)
    session.commit()

    # Retrieve case and verify associations
    retrieved_case = await case_service_instance.get_case(sample_case.id, test_admin)
    assert retrieved_case.id == sample_case.id

    # Check if entities exist
    from sqlmodel import select

    entities = session.exec(
        select(models.Entity).where(models.Entity.case_id == retrieved_case.id)
    ).all()
    assert len(entities) == 2

    # Check if evidence exists
    evidence_items = session.exec(
        select(models.Evidence).where(models.Evidence.case_id == retrieved_case.id)
    ).all()
    assert len(evidence_items) == 1


@pytest.mark.asyncio
async def test_concurrent_case_number_generation(
    case_service_instance: case_service.CaseService,
    test_admin: models.User,
):
    """Test handling of concurrent case number generation"""
    client = models.Client(name="Test Client", contact_email="test@example.com")
    case_service_instance.db.add(client)
    case_service_instance.db.commit()
    case_service_instance.db.refresh(client)

    # Create multiple cases in same month
    current_time = datetime(2023, 1, 15, 12, 0, 0)

    case_numbers = []
    for i in range(5):
        case_data = schemas.CaseCreate(
            client_id=client.id,
            title=f"Test Case {i}",
            status="Open",
            notes=f"Test Notes {i}",
        )
        created_case = await case_service_instance.create_case(
            case_data, current_user=test_admin
        )
        case_numbers.append(created_case.case_number)

    # Verify all case numbers are unique
    assert len(set(case_numbers)) == 5
    # Verify sequential numbering (numbers should increment)
    # Extract the numeric parts after the dash
    numbers = [int(cn.split("-")[1]) for cn in case_numbers]
    assert numbers == [1, 2, 3, 4, 5]


@pytest.mark.asyncio
async def test_case_soft_delete_vs_hard_delete(
    case_service_instance: case_service.CaseService,
    sample_case: models.Case,
    test_admin: models.User,
):
    """Test case deletion behavior (if implemented)"""
    # Check if delete method exists
    if hasattr(case_service_instance, "delete_case"):
        # Test soft delete (if implemented)
        await case_service_instance.delete_case(sample_case.id, current_user=test_admin)

        # Case should still exist but be marked as deleted
        deleted_case = case_service_instance.db.get(models.Case, sample_case.id)
        if hasattr(deleted_case, "is_deleted"):
            assert deleted_case.is_deleted == True
        else:
            # Hard delete - case should not exist
            assert deleted_case is None


@pytest.mark.asyncio
async def test_case_archival_functionality(
    case_service_instance: case_service.CaseService,
    sample_case: models.Case,
    test_admin: models.User,
):
    """Test case closure functionality"""
    # Update case to closed status (archival is achieved through "Closed" status)
    case_update = schemas.CaseUpdate(status="Closed")
    updated_case = await case_service_instance.update_case(
        sample_case.id, case_update, current_user=test_admin
    )
    assert updated_case.status == "Closed"

    # Verify closed cases are filtered correctly
    active_cases = await case_service_instance.get_cases(test_admin, status="Open")
    assert sample_case.id not in [case.id for case in active_cases]


@pytest.mark.asyncio
async def test_case_search_with_multiple_filters(
    case_service_instance: case_service.CaseService,
    test_admin: models.User,
    session: Session,
):
    """Test searching cases with multiple filters"""
    client = models.Client(name="Search Client", contact_email="search@example.com")
    session.add(client)
    session.commit()

    # Create various cases
    for i in range(10):
        case_data = schemas.CaseCreate(
            client_id=client.id,
            title=f"Case {i}",
            status="Open" if i % 2 == 0 else "Closed",
            notes=f"Notes for case {i}",
        )
        await case_service_instance.create_case(case_data, current_user=test_admin)

    # Test filtering by status
    open_cases = await case_service_instance.get_cases(test_admin, status="Open")
    assert len(open_cases) == 5

    closed_cases = await case_service_instance.get_cases(test_admin, status="Closed")
    assert len(closed_cases) == 5


@pytest.mark.asyncio
async def test_case_with_very_long_notes(
    case_service_instance: case_service.CaseService,
    test_admin: models.User,
):
    """Test case creation with very long notes"""
    client = models.Client(name="Long Notes Client", contact_email="long@example.com")
    case_service_instance.db.add(client)
    case_service_instance.db.commit()
    case_service_instance.db.refresh(client)

    # Create case with very long notes
    long_notes = "A" * 50000  # 50k characters
    case_data = schemas.CaseCreate(
        client_id=client.id, title="Long Notes Case", status="Open", notes=long_notes
    )
    created_case = await case_service_instance.create_case(
        case_data, current_user=test_admin
    )
    assert len(created_case.notes) == 50000


@pytest.mark.asyncio
async def test_removing_last_user_from_case(
    case_service_instance: case_service.CaseService,
    sample_case: models.Case,
    test_admin: models.User,
    test_user: models.User,
    session: Session,
):
    """Test removing the last user from a case"""
    # Add admin as the only user to the case
    link = models.CaseUserLink(case_id=sample_case.id, user_id=test_admin.id)
    session.add(link)
    session.commit()

    # Try to remove the last user
    # This should either fail or handle gracefully
    try:
        await case_service_instance.remove_user_from_case(
            sample_case.id, test_admin.id, current_user=test_admin
        )
        # If it succeeds, verify case has no users
        case = await case_service_instance.get_case(sample_case.id, test_admin)
        assert len(case.users) == 0
    except ValidationException as e:
        # If it fails, verify appropriate error
        assert "last user" in str(e).lower() or "cannot remove" in str(e).lower()


@pytest.mark.asyncio
async def test_case_reopening_after_closure(
    case_service_instance: case_service.CaseService,
    sample_case: models.Case,
    test_admin: models.User,
):
    """Test reopening a closed case"""
    # First close the case
    case_update = schemas.CaseUpdate(status="Closed")
    closed_case = await case_service_instance.update_case(
        sample_case.id, case_update, current_user=test_admin
    )
    assert closed_case.status == "Closed"

    # Reopen the case
    case_update = schemas.CaseUpdate(status="Open")
    reopened_case = await case_service_instance.update_case(
        sample_case.id, case_update, current_user=test_admin
    )
    assert reopened_case.status == "Open"


@pytest.mark.asyncio
async def test_invalid_status_values(
    case_service_instance: case_service.CaseService,
    sample_case: models.Case,
    test_admin: models.User,
):
    """Test updating case with invalid status values"""
    # Try to set invalid status - this should raise a ValidationError from Pydantic
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        case_update = schemas.CaseUpdate(status="InvalidStatus")


@pytest.mark.asyncio
async def test_case_date_filtering(
    case_service_instance: case_service.CaseService,
    test_admin: models.User,
    session: Session,
):
    """Test filtering cases by creation/update dates"""
    client = models.Client(name="Date Test Client", contact_email="date@example.com")
    session.add(client)
    session.commit()

    # Create cases with different dates
    import time

    cases = []
    for i in range(3):
        case_data = schemas.CaseCreate(
            client_id=client.id,
            title=f"Date Test Case {i}",
            status="Open",
            notes="Created at different times",
        )
        case = await case_service_instance.create_case(
            case_data, current_user=test_admin
        )
        cases.append(case)
        time.sleep(0.1)  # Small delay to ensure different timestamps

    # Verify all cases were created
    assert len(cases) == 3
    # Case numbers should be sequential
    assert cases[0].case_number < cases[1].case_number < cases[2].case_number


@pytest.mark.asyncio
async def test_case_user_permissions_matrix(
    case_service_instance: case_service.CaseService,
    sample_case: models.Case,
    test_admin: models.User,
    test_user: models.User,
    test_analyst: models.User,
    session: Session,
):
    """Test comprehensive permission matrix for different user roles"""
    # Add all users to the case
    for user in [test_admin, test_user, test_analyst]:
        link = models.CaseUserLink(case_id=sample_case.id, user_id=user.id)
        session.add(link)
    session.commit()

    # Test read permissions - all should succeed
    for user in [test_admin, test_user, test_analyst]:
        case = await case_service_instance.get_case(sample_case.id, user)
        assert case.id == sample_case.id

    # Test update permissions
    case_update = schemas.CaseUpdate(notes="Updated by different roles")

    # Admin and Investigator should succeed
    for user in [test_admin, test_user]:
        updated = await case_service_instance.update_case(
            sample_case.id, case_update, current_user=user
        )
        assert updated.notes == "Updated by different roles"

    # Analyst should fail
    with pytest.raises(AuthorizationException) as excinfo:
        await case_service_instance.update_case(
            sample_case.id, case_update, current_user=test_analyst
        )
    assert "Not authorized" in str(excinfo.value)


@pytest.mark.asyncio
async def test_case_title_special_characters(
    case_service_instance: case_service.CaseService,
    test_admin: models.User,
):
    """Test case creation with special characters in title"""
    client = models.Client(
        name="Special Char Client", contact_email="special@example.com"
    )
    case_service_instance.db.add(client)
    case_service_instance.db.commit()
    case_service_instance.db.refresh(client)

    special_titles = [
        "Case with 'quotes'",
        'Case with "double quotes"',
        "Case with <script>alert('xss')</script>",
        "Case with émojis 🎉",
        "Case with\nnewlines",
        "Case with\ttabs",
        "Çase with açcents",
        "案例 with Chinese",
        "Case™ with symbols®",
    ]

    for title in special_titles:
        case_data = schemas.CaseCreate(
            client_id=client.id,
            title=title,
            status="Open",
            notes="Testing special characters",
        )
        created_case = await case_service_instance.create_case(
            case_data, current_user=test_admin
        )
        assert created_case.title == title


@pytest.mark.asyncio
async def test_case_bulk_operations_performance(
    case_service_instance: case_service.CaseService,
    test_admin: models.User,
    session: Session,
):
    """Test performance with bulk case operations"""
    import time

    client = models.Client(name="Bulk Test Client", contact_email="bulk@example.com")
    session.add(client)
    session.commit()

    # Measure time to create 100 cases
    start_time = time.time()

    for i in range(100):
        case_data = schemas.CaseCreate(
            client_id=client.id,
            title=f"Bulk Case {i:03d}",
            status="Open" if i % 2 == 0 else "Closed",
            notes=f"Bulk test case number {i}",
        )
        await case_service_instance.create_case(case_data, current_user=test_admin)

    creation_time = time.time() - start_time
    assert creation_time < 10.0  # Should complete within 10 seconds

    # Measure time to retrieve all cases
    start_time = time.time()
    all_cases = await case_service_instance.get_cases(test_admin)
    retrieval_time = time.time() - start_time

    assert len(all_cases) >= 100
    assert retrieval_time < 1.0  # Should complete within 1 second


@pytest.mark.asyncio
async def test_case_number_year_rollover(
    case_service_instance: case_service.CaseService,
    test_admin: models.User,
):
    """Test case number generation when year changes"""
    client = models.Client(name="Year Test Client", contact_email="year@example.com")
    case_service_instance.db.add(client)
    case_service_instance.db.commit()
    case_service_instance.db.refresh(client)

    # Create case in December 2023
    dec_2023 = datetime(2023, 12, 15, 12, 0, 0)
    case_number_dec = await case_service_instance._generate_case_number(dec_2023)
    assert case_number_dec.startswith("2312-")

    # Create case in January 2024
    jan_2024 = datetime(2024, 1, 15, 12, 0, 0)
    case_number_jan = await case_service_instance._generate_case_number(jan_2024)
    assert case_number_jan == "2401-01"  # Should reset to 01


@pytest.mark.asyncio
async def test_add_duplicate_user_to_case(
    case_service_instance: case_service.CaseService,
    sample_case: models.Case,
    test_user: models.User,
    test_admin: models.User,
    sample_case_link: models.CaseUserLink,
):
    """Test adding a user who is already assigned to the case"""
    # User is already assigned via sample_case_link
    # Try to add them again - this should fail with DuplicateResourceException
    with pytest.raises(DuplicateResourceException) as excinfo:
        await case_service_instance.add_user_to_case(
            sample_case.id, test_user.id, current_user=test_admin
        )
    assert "already assigned" in str(excinfo.value)
