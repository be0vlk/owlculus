"""
Pydantic models for entities.
"""

from collections.abc import Callable
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    field_validator,
    model_validator,
)

from ..core.hostname import canonical_hostname, normalize_website
from ..core.utils import get_utc_now


class EntityData(BaseModel):
    """Base class for all entity data types"""

    model_config = ConfigDict(extra="allow")


class Address(EntityData):
    street: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    country: Optional[str] = None
    postal_code: Optional[str] = None


class SocialMedia(EntityData):
    bluesky: Optional[str] = None
    discord: Optional[str] = None
    facebook: Optional[str] = None
    instagram: Optional[str] = None
    linkedin: Optional[str] = None
    reddit: Optional[str] = None
    telegram: Optional[str] = None
    tiktok: Optional[str] = None
    twitch: Optional[str] = None
    x: Optional[str] = None
    youtube: Optional[str] = None
    other: Optional[str] = None


class NetworkAssets(EntityData):
    domains: Optional[List[str]] = None
    ip_addresses: Optional[List[str]] = None
    subdomains: Optional[List[str]] = None


class DomainData(EntityData):
    domain: str

    _normalize_domain = field_validator("domain")(canonical_hostname)
    description: Optional[str] = None
    notes: Optional[str] = None
    sources: Optional[Dict[str, str]] = None
    subdomains: Optional[List[Dict[str, Any]]] = None


class IpAddressData(EntityData):
    ip_address: str
    description: Optional[str] = None
    notes: Optional[str] = None
    sources: Optional[Dict[str, str]] = None


class Associates(EntityData):
    children: Optional[str] = None
    colleagues: Optional[str] = None
    father: Optional[str] = None
    friends: Optional[str] = None
    mother: Optional[str] = None
    partner_spouse: Optional[str] = Field(None, alias="partner/spouse")
    siblings: Optional[str] = None
    other: Optional[str] = None


class PersonData(EntityData):
    @field_validator("email", mode="before")
    @classmethod
    def normalize_email_host(cls, value: Any) -> Any:
        if isinstance(value, str) and "@" in value:
            local, host = value.strip().rsplit("@", 1)
            return f"{local}@{canonical_hostname(host)}"
        return value

    first_name: Optional[str] = None
    last_name: Optional[str] = None
    dob: Optional[str] = None
    nationality: Optional[str] = None
    address: Optional[Address] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    employer: Optional[str] = None
    social_media: Optional[SocialMedia] = None
    usernames: Optional[list[str]] = None
    associates: Optional[Associates] = None
    other: Optional[str] = None
    notes: Optional[str] = None
    sources: Optional[Dict[str, str]] = None


class Executives(EntityData):
    ceo: Optional[str] = None
    cfo: Optional[str] = None
    cto: Optional[str] = None
    cmo: Optional[str] = None
    coo: Optional[str] = None
    other: Optional[str] = None


class Affiliates(EntityData):
    affiliated_companies: Optional[str] = Field(None, alias="Affiliated Companies")
    subsidiaries: Optional[str] = None
    parent_company: Optional[str] = Field(None, alias="Parent Company")


class CompanyData(EntityData):
    name: str
    address: Optional[Address] = None
    website: Optional[str] = None
    phone: Optional[str] = None
    social_media: Optional[SocialMedia] = None
    executives: Optional[Executives] = None
    affiliates: Optional[Affiliates] = None
    ip_addresses: Optional[List[str]] = None
    other: Optional[str] = None
    notes: Optional[str] = None
    sources: Optional[Dict[str, str]] = None

    @field_validator("website")
    @classmethod
    def validate_website(cls, value: str | None) -> str | None:
        return normalize_website(value) if value is not None else None


class VehicleData(EntityData):
    make: Optional[str] = None
    model: Optional[str] = None
    year: Optional[int] = None
    vin: Optional[str] = None
    license_plate: Optional[str] = None
    color: Optional[str] = None
    owner: Optional[str] = None
    registration_state: Optional[str] = None
    description: Optional[str] = None
    notes: Optional[str] = None
    sources: Optional[Dict[str, str]] = None


# Map entity types to their respective data schemas
ENTITY_TYPE_SCHEMAS = {
    "person": PersonData,
    "company": CompanyData,
    "domain": DomainData,
    "ip_address": IpAddressData,
    "vehicle": VehicleData,
}


def _joined_display_name(*fields: str) -> Callable[[dict[str, Any]], str]:
    return lambda data: " ".join(
        str(data[field]) for field in fields if data.get(field) not in (None, "")
    )


def _field_display_name(field: str) -> Callable[[dict[str, Any]], str]:
    return lambda data: str(data.get(field) or "")


def _network_assets_display_name(data: dict[str, Any]) -> str:
    assets = data.get("domains") or data.get("subdomains") or []
    return str(assets[0]) if assets else ""


_DISPLAY_NAME_BY_ENTITY_TYPE: dict[str, Callable[[dict[str, Any]], str]] = {
    "person": _joined_display_name("first_name", "last_name"),
    "company": _field_display_name("name"),
    "domain": _field_display_name("domain"),
    "ip_address": _field_display_name("ip_address"),
    "vehicle": _joined_display_name("year", "make", "model"),
    "network_assets": _network_assets_display_name,
}


def entity_display_name(entity_type: str, data: dict[str, Any]) -> str:
    """Return the display label owned by an entity's schema vocabulary."""
    formatter = _DISPLAY_NAME_BY_ENTITY_TYPE.get(entity_type)
    return formatter(data) if formatter else ""


class Entity(BaseModel):
    """Return stored data faithfully, including historical values and unknown fields."""

    model_config = ConfigDict(from_attributes=True)

    case_id: int
    entity_type: str
    data: Dict[str, Any]
    id: Optional[int] = None
    created_at: Optional[datetime] = Field(default_factory=get_utc_now)
    updated_at: Optional[datetime] = Field(default_factory=get_utc_now)
    created_by_id: Optional[int] = None


class EntityCreate(BaseModel):
    entity_type: str
    data: Dict[str, Any]
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    created_by_id: Optional[int] = None

    @model_validator(mode="after")
    def validate_data(self) -> "EntityCreate":
        schema = ENTITY_TYPE_SCHEMAS.get(self.entity_type)
        if not schema:
            raise ValueError(f"Invalid entity type: {self.entity_type}")
        try:
            self.data = schema(**self.data).model_dump(mode="json", by_alias=True)
        except Exception as e:
            raise ValueError(
                f"Invalid data for entity type {self.entity_type}: {str(e)}"
            )
        return self


class EntityUpdate(BaseModel):
    data: Dict[str, Any]
    updated_at: datetime = Field(default_factory=get_utc_now)
    entity_type_hint: Optional[str] = Field(None, alias="__entity_type")

    @model_validator(mode="before")
    def validate_data(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        # This will be populated with the entity type during validation in the service layer
        entity_type = values.get("__entity_type")
        if entity_type:
            schema = ENTITY_TYPE_SCHEMAS.get(entity_type)
            if schema:
                try:
                    values["data"] = schema(**values["data"]).model_dump(
                        mode="json", by_alias=True
                    )
                except Exception as e:
                    raise ValueError(
                        f"Invalid data for entity type '{entity_type}': {str(e)}"
                    )
        return values
