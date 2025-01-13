import pytest
from sqlmodel import Session
from fastapi import HTTPException
from datetime import datetime

from app.database import models
from app import schemas
from app.services import case_service
from app.core.utils import get_utc_now


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
    with pytest.raises(HTTPException) as excinfo:
        await case_service_instance.create_case(case_data, current_user=test_user)
    assert excinfo.value.status_code == 403
    assert excinfo.value.detail == "Not authorized"


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
    with pytest.raises(HTTPException) as excinfo:
        await case_service_instance.create_case(case_data, current_user=test_analyst)
    assert excinfo.value.status_code == 403
    assert excinfo.value.detail == "Not authorized"


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
    with pytest.raises(HTTPException) as excinfo:
        await case_service_instance.get_case(sample_case.id, test_user)
    assert excinfo.value.status_code == 403
    assert excinfo.value.detail == "Not authorized"


@pytest.mark.asyncio
async def test_get_case_not_found(
    case_service_instance: case_service.CaseService, test_admin: models.User
):
    with pytest.raises(HTTPException) as excinfo:
        await case_service_instance.get_case(999, test_admin)
    assert excinfo.value.status_code == 404
    assert excinfo.value.detail == "Case not found"


@pytest.mark.asyncio
async def test_update_case_admin(
    case_service_instance: case_service.CaseService,
    sample_case: models.Case,
    test_admin: models.User,
):
    case_update = schemas.CaseUpdate(title="Updated Case", status="Closed")
    updated_case = await case_service_instance.update_case(
        sample_case.id, case_update, current_user=test_admin
    )
    assert updated_case.title == "Updated Case"
    assert updated_case.status == "Closed"


@pytest.mark.asyncio
async def test_update_case_non_admin_associated(
    case_service_instance: case_service.CaseService,
    sample_case: models.Case,
    test_user: models.User,
    sample_case_link: models.CaseUserLink,
):
    case_update = schemas.CaseUpdate(title="Updated Case", status="Closed")
    updated_case = await case_service_instance.update_case(
        sample_case.id, case_update, current_user=test_user
    )
    assert updated_case.title == "Updated Case"
    assert updated_case.status == "Closed"


@pytest.mark.asyncio
async def test_update_case_non_admin_not_associated(
    case_service_instance: case_service.CaseService,
    sample_case: models.Case,
    test_user: models.User,
):
    case_update = schemas.CaseUpdate(title="Updated Case", status="Closed")
    with pytest.raises(HTTPException) as excinfo:
        await case_service_instance.update_case(
            sample_case.id, case_update, current_user=test_user
        )
    assert excinfo.value.status_code == 403
    assert excinfo.value.detail == "You do not have permission to update this case"


@pytest.mark.asyncio
async def test_update_case_analyst(
    case_service_instance: case_service.CaseService,
    sample_case: models.Case,
    test_analyst: models.User,
):
    case_update = schemas.CaseUpdate(title="Updated Case", status="Closed")
    with pytest.raises(HTTPException) as excinfo:
        await case_service_instance.update_case(
            sample_case.id, case_update, current_user=test_analyst
        )
    assert excinfo.value.status_code == 403
    assert excinfo.value.detail == "Not authorized"


@pytest.mark.asyncio
async def test_update_case_not_found(
    case_service_instance: case_service.CaseService, test_admin: models.User
):
    case_update = schemas.CaseUpdate(title="Updated Case", status="Closed")
    with pytest.raises(HTTPException) as excinfo:
        await case_service_instance.update_case(
            999, case_update, current_user=test_admin
        )
    assert excinfo.value.status_code == 404
    assert excinfo.value.detail == "Case not found"


@pytest.mark.asyncio
async def test_update_case_number_unique(
    case_service_instance: case_service.CaseService,
    sample_case: models.Case,
    test_admin: models.User,
):
    case_update = schemas.CaseUpdate(case_number="2301-02")
    updated_case = await case_service_instance.update_case(
        sample_case.id, case_update, current_user=test_admin
    )
    assert updated_case.case_number == "2301-02"


@pytest.mark.asyncio
async def test_update_case_number_duplicate(
    case_service_instance: case_service.CaseService,
    sample_case: models.Case,
    test_admin: models.User,
):
    # Create another case with the same case number
    case_data = schemas.CaseCreate(
        client_id=sample_case.client_id,
        title="Another Case",
        case_number="2301-02",
        status="Open",
        notes="Test Notes",
    )
    another_case = models.Case(**case_data.model_dump(), created_by=test_admin)
    case_service_instance.db.add(another_case)
    case_service_instance.db.commit()

    case_update = schemas.CaseUpdate(case_number="2301-02")
    with pytest.raises(HTTPException) as excinfo:
        await case_service_instance.update_case(
            sample_case.id, case_update, current_user=test_admin
        )
    assert excinfo.value.status_code == 400
    assert excinfo.value.detail == "Case number already exists"


@pytest.mark.asyncio
async def test_add_user_to_case_admin(
    case_service_instance: case_service.CaseService,
    sample_case: models.Case,
    test_user: models.User,
    test_admin: models.User,
):
    updated_case = await case_service_instance.add_user_to_case(
        sample_case.id, test_user.id, current_user=test_admin
    )
    assert test_user in updated_case.users


@pytest.mark.asyncio
async def test_add_user_to_case_non_admin(
    case_service_instance: case_service.CaseService,
    sample_case: models.Case,
    test_user: models.User,
    test_analyst: models.User,
):
    with pytest.raises(HTTPException) as excinfo:
        await case_service_instance.add_user_to_case(
            sample_case.id, test_user.id, current_user=test_analyst
        )
    assert excinfo.value.status_code == 403
    assert excinfo.value.detail == "Not authorized"


@pytest.mark.asyncio
async def test_add_user_to_case_not_found(
    case_service_instance: case_service.CaseService,
    test_user: models.User,
    test_admin: models.User,
):
    with pytest.raises(HTTPException) as excinfo:
        await case_service_instance.add_user_to_case(
            999, test_user.id, current_user=test_admin
        )
    assert excinfo.value.status_code == 404
    assert excinfo.value.detail == "Case not found"


@pytest.mark.asyncio
async def test_add_user_to_case_user_not_found(
    case_service_instance: case_service.CaseService,
    sample_case: models.Case,
    test_admin: models.User,
):
    with pytest.raises(HTTPException) as excinfo:
        await case_service_instance.add_user_to_case(
            sample_case.id, 999, current_user=test_admin
        )
    assert excinfo.value.status_code == 404
    assert excinfo.value.detail == "User not found"


@pytest.mark.asyncio
async def test_remove_user_from_case_admin(
    case_service_instance: case_service.CaseService,
    sample_case: models.Case,
    test_user: models.User,
    test_admin: models.User,
    sample_case_link: models.CaseUserLink,
):
    updated_case = await case_service_instance.remove_user_from_case(
        sample_case.id, test_user.id, current_user=test_admin
    )
    assert test_user not in updated_case.users


@pytest.mark.asyncio
async def test_remove_user_from_case_non_admin(
    case_service_instance: case_service.CaseService,
    sample_case: models.Case,
    test_user: models.User,
    test_analyst: models.User,
    sample_case_link: models.CaseUserLink,
):
    with pytest.raises(HTTPException) as excinfo:
        await case_service_instance.remove_user_from_case(
            sample_case.id, test_user.id, current_user=test_analyst
        )
    assert excinfo.value.status_code == 403
    assert excinfo.value.detail == "Not authorized"


@pytest.mark.asyncio
async def test_remove_user_from_case_not_found(
    case_service_instance: case_service.CaseService,
    test_user: models.User,
    test_admin: models.User,
):
    with pytest.raises(HTTPException) as excinfo:
        await case_service_instance.remove_user_from_case(
            999, test_user.id, current_user=test_admin
        )
    assert excinfo.value.status_code == 404
    assert excinfo.value.detail == "Case not found"


@pytest.mark.asyncio
async def test_remove_user_from_case_user_not_found(
    case_service_instance: case_service.CaseService,
    sample_case: models.Case,
    test_admin: models.User,
):
    with pytest.raises(HTTPException) as excinfo:
        await case_service_instance.remove_user_from_case(
            sample_case.id, 999, current_user=test_admin
        )
    assert excinfo.value.status_code == 404
    assert excinfo.value.detail == "User not found"
