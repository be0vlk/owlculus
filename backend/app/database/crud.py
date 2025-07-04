from typing import Optional

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload
from sqlmodel import Session, or_, select

from . import models
from ..core.exceptions import DuplicateResourceException
from ..core.roles import UserRole
from ..core.utils import get_utc_now
from ..schemas import (
    CaseCreate,
    CaseUpdate,
    ClientCreate,
    ClientUpdate,
    EntityCreate,
    EntityUpdate,
    UserCreate,
    UserUpdate,
)


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

    if (
        user_data.get("is_superadmin", False)
        and user_data.get("role") != UserRole.ADMIN.value
    ):
        raise ValueError("Only users with Admin role can be superadmin")

    user_data["password_hash"] = get_password_hash(user_data.pop("password"))
    db_user = models.User(**user_data)
    db.add(db_user)

    try:
        db.commit()
        db.refresh(db_user)
        return db_user
    except IntegrityError as e:
        db.rollback()
        if "username" in str(e.orig).lower():
            raise ValueError("Username already exists")
        elif "email" in str(e.orig).lower():
            raise ValueError("Email already exists")
        else:
            raise ValueError("Database constraint violation")


async def update_user(db: Session, user_id: int, user: UserUpdate):
    db_user = db.get(models.User, user_id)
    if db_user is None:
        raise ValueError(f"User with id {user_id} not found")

    if (
        user.role is not None
        and user.role != UserRole.ADMIN.value
        and db_user.is_superadmin
    ):
        raise ValueError("Cannot change role of superadmin user away from Admin")

    if user.username is not None:
        db_user.username = user.username
    if user.email is not None:
        db_user.email = user.email
    if user.role is not None:
        db_user.role = user.role
    if user.is_active is not None:
        db_user.is_active = user.is_active
    if user.is_superadmin is not None:
        final_role = user.role if user.role is not None else db_user.role
        if user.is_superadmin and final_role != UserRole.ADMIN.value:
            raise ValueError("Only users with Admin role can be superadmin")
        db_user.is_superadmin = user.is_superadmin

    db_user.updated_at = user.updated_at

    try:
        db.commit()
        return db_user
    except IntegrityError as e:
        db.rollback()
        if "username" in str(e.orig).lower():
            raise ValueError("Username already exists")
        elif "email" in str(e.orig).lower():
            raise ValueError("Email already exists")
        else:
            raise ValueError("Database constraint violation")


async def change_user_password(
    db: Session, user: models.User, current_password: str, new_password: str
):
    from ..core.security import get_password_hash, verify_password

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


async def delete_user(db: Session, user_id: int):
    db_user = db.get(models.User, user_id)
    if db_user is None:
        raise ValueError(f"User with id {user_id} not found")

    db.delete(db_user)
    db.commit()
    return True


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
    case.users.append(user)
    case.updated_at = get_utc_now()
    db.add(case)
    db.commit()
    db.refresh(case)
    return case


async def remove_user_from_case(
    db: Session, case: models.Case, user: models.User
) -> models.Case:
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
                raise DuplicateResourceException(
                    f"A company with the name '{company_name}' already exists in this case"
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
                raise DuplicateResourceException(
                    f"A person with the name '{first_name} {last_name}' already exists in this case"
                )

    elif entity_type == "ip_address":
        ip_address = entity.data.get("ip_address")
        if ip_address:
            query = select(models.Entity).where(
                models.Entity.case_id == case_id,
                models.Entity.entity_type == "ip_address",
                models.Entity.data["ip_address"].as_string() == ip_address,
            )
            if entity_id:
                query = query.where(models.Entity.id != entity_id)

            if db.exec(query).first():
                raise DuplicateResourceException(
                    f"An IP address '{ip_address}' already exists in this case"
                )

    elif entity_type == "domain":
        domain = entity.data.get("domain")
        if domain:
            query = select(models.Entity).where(
                models.Entity.case_id == case_id,
                models.Entity.entity_type == "domain",
                models.Entity.data["domain"].as_string().ilike(domain),
            )
            if entity_id:
                query = query.where(models.Entity.id != entity_id)

            if db.exec(query).first():
                raise DuplicateResourceException(
                    f"A domain '{domain}' already exists in this case"
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
                raise DuplicateResourceException(
                    "Network assets with overlapping domains, IP addresses, or subdomains already exist in this case"
                )

    elif entity_type == "vehicle":
        vin = entity.data.get("vin")
        license_plate = entity.data.get("license_plate")

        if vin:
            query = select(models.Entity).where(
                models.Entity.case_id == case_id,
                models.Entity.entity_type == "vehicle",
                models.Entity.data["vin"].as_string().ilike(vin),
            )
            if entity_id:
                query = query.where(models.Entity.id != entity_id)

            if db.exec(query).first():
                raise DuplicateResourceException(
                    f"A vehicle with VIN '{vin}' already exists in this case"
                )

        if license_plate:
            query = select(models.Entity).where(
                models.Entity.case_id == case_id,
                models.Entity.entity_type == "vehicle",
                models.Entity.data["license_plate"].as_string().ilike(license_plate),
            )
            if entity_id:
                query = query.where(models.Entity.id != entity_id)

            if db.exec(query).first():
                raise DuplicateResourceException(
                    f"A vehicle with license plate '{license_plate}' already exists in this case"
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


# --- Invite ---
async def create_invite(
    db: Session, token: str, role: str, expires_at, created_by_id: int
):
    db_invite = models.Invite(
        token=token,
        role=role,
        expires_at=expires_at,
        created_by_id=created_by_id,
    )
    db.add(db_invite)
    db.commit()
    db.refresh(db_invite)
    return db_invite


async def get_invite_by_token(db: Session, token: str):
    return db.exec(select(models.Invite).where(models.Invite.token == token)).first()


async def get_invites_by_creator(
    db: Session, creator_id: int, skip: int = 0, limit: int = 100
):
    return db.exec(
        select(models.Invite)
        .where(models.Invite.created_by_id == creator_id)
        .order_by(models.Invite.created_at.desc())
        .offset(skip)
        .limit(limit)
    ).all()


async def get_all_invites(db: Session, skip: int = 0, limit: int = 100):
    statement = (
        select(models.Invite)
        .options(selectinload(models.Invite.creator))
        .order_by(models.Invite.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    return db.exec(statement).all()


async def mark_invite_used(db: Session, invite: models.Invite):
    invite.used_at = get_utc_now()
    db.commit()
    return invite


async def delete_invite(db: Session, invite_id: int):
    db_invite = db.get(models.Invite, invite_id)
    if db_invite is None:
        raise ValueError(f"Invite with id {invite_id} not found")

    db.delete(db_invite)
    db.commit()
    return True


async def delete_expired_invites(db: Session):

    now = get_utc_now()
    expired_invites = db.exec(
        select(models.Invite).where(
            models.Invite.expires_at < now, models.Invite.used_at.is_(None)
        )
    ).all()

    for invite in expired_invites:
        db.delete(invite)

    db.commit()
    return len(expired_invites)


async def create_user_from_invite(
    db: Session, username: str, email: str, password: str, role: str
):
    from ..core.security import get_password_hash

    user_data = {
        "username": username,
        "email": email,
        "password_hash": get_password_hash(password),
        "role": role,
        "is_superadmin": False,  # Invites cannot create superadmin users
    }
    db_user = models.User(**user_data)
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user
