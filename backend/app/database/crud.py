from sqlmodel import Session, select, or_
from ..core.utils import get_utc_now
from fastapi import HTTPException
from typing import Optional

from ..schemas import (
    UserCreate,
    UserUpdate,
    ClientCreate,
    ClientUpdate,
    CaseCreate,
    CaseUpdate,
    EntityCreate,
    EntityUpdate,
)
from . import models

# --- User ---


async def get_user(db: Session, user_id: int):
    return db.get(models.User, user_id)


async def get_user_by_email(db: Session, email: str):
    return db.exec(select(models.User).where(models.User.email == email)).first()


async def get_user_by_username(db: Session, username: str):
    return db.exec(select(models.User).where(models.User.username == username)).first()


async def get_users(db: Session, skip: int = 0, limit: int = 100):
    return db.exec(select(models.User).offset(skip).limit(limit)).all()


async def create_user(db: Session, user: UserCreate):
    user_data = user.model_dump()
    from ..core.security import get_password_hash

    user_data["password_hash"] = get_password_hash(user_data.pop("password"))
    db_user = models.User(**user_data)
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user


async def update_user(db: Session, user_id: int, user: UserUpdate):
    db_user = db.get(models.User, user_id)
    if db_user is None:
        raise ValueError(f"User with id {user_id} not found")

    if user.username is not None:
        db_user.username = user.username
    if user.email is not None:
        db_user.email = user.email
    if user.role is not None:
        db_user.role = user.role
    if user.is_active is not None:
        db_user.is_active = user.is_active

    db_user.updated_at = user.updated_at
    db.commit()
    return db_user


async def change_user_password(
    db: Session, user: models.User, current_password: str, new_password: str
):
    from ..core.security import verify_password, get_password_hash

    if not verify_password(current_password, user.password_hash):
        raise ValueError("Current password is incorrect")

    user.password_hash = get_password_hash(new_password)
    user.updated_at = get_utc_now()
    db.commit()
    return user


async def admin_reset_password(db: Session, user: models.User, new_password: str):
    from ..core.security import get_password_hash

    user.password_hash = get_password_hash(new_password)
    user.updated_at = get_utc_now()
    db.commit()
    return user


# --- Client ---


async def get_client(db: Session, client_id: int):
    return db.get(models.Client, client_id)


async def get_client_by_email(db: Session, email: str):
    return db.exec(select(models.Client).where(models.Client.email == email)).first()


async def get_clients(db: Session, skip: int = 0, limit: int = 100):
    return db.exec(select(models.Client).offset(skip).limit(limit)).all()


async def create_client(db: Session, client: ClientCreate):
    client_data = client.model_dump()
    db_client = models.Client(**client_data)
    db.add(db_client)
    db.commit()
    db.refresh(db_client)
    return db_client


async def update_client(db: Session, client_id: int, client: ClientUpdate):
    db_client = db.get(models.Client, client_id)
    if db_client is None:
        raise ValueError(f"Client with id {client_id} not found")

    if client.name is not None:
        db_client.name = client.name
    if client.email is not None:
        db_client.email = client.email
    if client.phone is not None:
        db_client.phone = client.phone
    if client.address is not None:
        db_client.address = client.address

    db_client.updated_at = get_utc_now()
    db.commit()
    return db_client


async def delete_client(db: Session, client_id: int):
    db_client = db.get(models.Client, client_id)
    if db_client is None:
        raise ValueError(f"Client with id {client_id} not found")

    db.delete(db_client)
    db.commit()


# --- Case ---


async def get_case(db: Session, case_id: int):
    return db.get(models.Case, case_id)


async def get_case_by_number(db: Session, case_number: str):
    return db.exec(
        select(models.Case).where(models.Case.case_number == case_number)
    ).first()


async def get_cases(db: Session, skip: int = 0, limit: int = 100):
    result = db.exec(select(models.Case).offset(skip).limit(limit))
    return result.all()


async def create_case(
    db: Session, *, case: CaseCreate, current_user: models.User
) -> models.Case:
    case_data = case.model_dump()
    current_time = get_utc_now()

    db_case = models.Case(
        **case_data,
        created_by_id=current_user.id,
        created_at=current_time,
        updated_at=current_time,
    )
    db_case.users.append(current_user)
    db.add(db_case)
    db.flush()
    db.refresh(db_case)
    db.commit()
    return db_case


async def update_case(
    db: Session, *, case_id: int, case: CaseUpdate, current_user: models.User
) -> models.Case:
    db_case = db.get(models.Case, case_id)
    if db_case is None:
        raise ValueError(f"Case with id {case_id} not found")

    update_data = case.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_case, field, value)

    db_case.updated_at = get_utc_now()
    db.add(db_case)
    db.commit()
    db.refresh(db_case)
    return db_case


async def add_user_to_case(
    db: Session, case: models.Case, user: models.User
) -> models.Case:
    """Add a user to a case"""
    case.users.append(user)
    case.updated_at = get_utc_now()
    db.add(case)
    db.commit()
    db.refresh(case)
    return case


async def remove_user_from_case(
    db: Session, case: models.Case, user: models.User
) -> models.Case:
    """Remove a user from a case"""
    case.users.remove(user)
    case.updated_at = get_utc_now()
    db.add(case)
    db.commit()
    db.refresh(case)
    return case


# --- Entitys ---
async def check_entity_duplicates(
    db: Session,
    case_id: int,
    entity: EntityCreate | EntityUpdate,
    entity_id: Optional[int] = None,
):
    """Consolidated function to check for entity duplicates"""

    # Get entity type either directly or from validation dict
    entity_dict = entity.model_dump()
    entity_type = (
        getattr(entity, "entity_type", None)
        or getattr(entity, "__entity_type", None)
        or getattr(entity, "entity_type_hint", None)
        or entity_dict.get("__entity_type")
    )

    if entity_type == "company":
        company_name = entity.data.get("name")
        if company_name:
            query = select(models.Entity).where(
                models.Entity.case_id == case_id,
                models.Entity.entity_type == "company",
                models.Entity.data["name"].as_string().ilike(company_name),
            )
            if entity_id:
                query = query.where(models.Entity.id != entity_id)

            if db.exec(query).first():
                raise HTTPException(
                    status_code=400,
                    detail=f"A company with the name '{company_name}' already exists in this case",
                )

    elif entity_type == "person":
        first_name = entity.data.get("first_name")
        last_name = entity.data.get("last_name")
        if first_name and last_name:
            query = select(models.Entity).where(
                models.Entity.case_id == case_id,
                models.Entity.entity_type == "person",
                models.Entity.data["first_name"].as_string().ilike(first_name),
                models.Entity.data["last_name"].as_string().ilike(last_name),
            )
            if entity_id:
                query = query.where(models.Entity.id != entity_id)

            if db.exec(query).first():
                raise HTTPException(
                    status_code=400,
                    detail=f"A person with the name '{first_name} {last_name}' already exists in this case",
                )

    elif entity_type == "network_assets":
        domains = entity.data.get("domains", [])
        ip_addresses = entity.data.get("ip_addresses", [])
        subdomains = entity.data.get("subdomains", [])

        if domains or ip_addresses or subdomains:
            conditions = []
            if domains:
                conditions.append(
                    or_(
                        *[
                            models.Entity.data["domains"].as_array().any(d.lower())
                            for d in domains
                        ]
                    )
                )
            if ip_addresses:
                conditions.append(
                    or_(
                        *[
                            models.Entity.data["ip_addresses"]
                            .as_array()
                            .any(ip.lower())
                            for ip in ip_addresses
                        ]
                    )
                )
            if subdomains:
                conditions.append(
                    or_(
                        *[
                            models.Entity.data["subdomains"].as_array().any(s.lower())
                            for s in subdomains
                        ]
                    )
                )

            query = select(models.Entity).where(
                models.Entity.case_id == case_id,
                models.Entity.entity_type == "network_assets",
                or_(*conditions),
            )

            if entity_id:
                query = query.where(models.Entity.id != entity_id)

            if db.exec(query).first():
                raise HTTPException(
                    status_code=400,
                    detail="Network assets with overlapping domains, IP addresses, or subdomains already exist in this case",
                )


def get_entity(db: Session, entity_id: int):
    return db.get(models.PersonEntity, entity_id)


def get_case_entities(db: Session, case_id: int, skip: int = 0, limit: int = 100):
    return db.exec(
        select(models.PersonEntity)
        .where(models.PersonEntity.case_id == case_id)
        .offset(skip)
        .limit(limit)
    ).all()


def create_person_entity(db: Session, case_id: int, user_id: int, person_data: dict):
    db_entity = models.PersonEntity(
        case_id=case_id, created_by_id=user_id, **person_data
    )
    db.add(db_entity)
    db.commit()
    db.refresh(db_entity)
    return db_entity


def update_person_entity(db: Session, entity_id: int, person_data: dict):
    db_entity = db.get(models.PersonEntity, entity_id)
    if db_entity is None:
        raise ValueError(f"Entity with id {entity_id} not found")

    for key, value in person_data.items():
        setattr(db_entity, key, value)

    db_entity.updated_at = get_utc_now()
    db.add(db_entity)
    db.commit()
    db.refresh(db_entity)
    return db_entity


def delete_component(db: Session, component_id: int):
    db_entity = db.get(models.PersonEntity, component_id)
    if db_entity is None:
        raise ValueError(f"Entity with id {component_id} not found")

    db.delete(db_entity)
    db.commit()
    return True
