"""
Pydantic models for entities.
"""

from datetime import datetime
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator, AnyHttpUrl
from ..core.utils import get_utc_now


class EntityData(BaseModel):
    """Base class for all entity data types"""

    pass


class Address(BaseModel):
    street: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    country: Optional[str] = None
    postal_code: Optional[str] = None


class SocialMedia(BaseModel):
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


class NetworkAssets(BaseModel):
    domains: Optional[List[str]] = None
    ip_addresses: Optional[List[str]] = None
    subdomains: Optional[List[str]] = None


class DomainData(EntityData):
    domain: str
    description: Optional[str] = None


class IpAddressData(EntityData):
    ip_address: str
    description: Optional[str] = None


class Associates(BaseModel):
    children: Optional[str] = None
    colleagues: Optional[str] = None
    father: Optional[str] = None
    friends: Optional[str] = None
    mother: Optional[str] = None
    partner_spouse: Optional[str] = Field(None, alias="partner/spouse")
    siblings: Optional[str] = None
    other: Optional[str] = None


class PersonData(EntityData):
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


class Executives(BaseModel):
    ceo: Optional[str] = None
    cfo: Optional[str] = None
    cto: Optional[str] = None
    cmo: Optional[str] = None
    coo: Optional[str] = None
    other: Optional[str] = None


class Affiliates(BaseModel):
    affiliated_companies: Optional[str] = Field(None, alias="Affiliated Companies")
    subsidiaries: Optional[str] = None
    parent_company: Optional[str] = Field(None, alias="Parent Company")


class CompanyData(EntityData):
    name: str
    address: Optional[Address] = None
    website: Optional[AnyHttpUrl] = None
    phone: Optional[str] = None
    social_media: Optional[SocialMedia] = None
    executives: Optional[Executives] = None
    affiliates: Optional[Affiliates] = None
    domains: Optional[List[str]] = None
    ip_addresses: Optional[List[str]] = None
    other: Optional[str] = None

    @model_validator(mode="before")
    def validate_urls(cls, values):
        if "website" in values and values["website"]:
            # Skip if it's already None or already has a protocol
            if isinstance(values["website"], str) and not values["website"].startswith(
                ("https://")
            ):
                values["website"] = f"https://{values['website']}"
        return values


# Map entity types to their respective data schemas
ENTITY_TYPE_SCHEMAS = {
    "person": PersonData,
    "company": CompanyData,
    "domain": DomainData,
    "ip_address": IpAddressData,
}


class Entity(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    case_id: int
    entity_type: str
    data: Dict[str, Any]
    id: Optional[int] = None
    created_at: Optional[datetime] = Field(default_factory=get_utc_now)
    updated_at: Optional[datetime] = Field(default_factory=get_utc_now)
    created_by_id: Optional[int] = None

    @model_validator(mode="after")
    def validate_data(self) -> "Entity":
        schema = ENTITY_TYPE_SCHEMAS.get(self.entity_type)
        if schema:
            try:
                self.data = schema(**self.data).model_dump()
            except Exception as e:
                raise ValueError(
                    f"Invalid data for entity type '{self.entity_type}': {str(e)}"
                )
        return self


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
            schema(**self.data)
        except Exception as e:
            raise ValueError(
                f"Invalid data for entity type {self.entity_type}: {str(e)}"
            )
        return self


class EntityUpdate(BaseModel):
    data: Dict[str, Any]
    updated_at: datetime = Field(default_factory=get_utc_now)

    @model_validator(mode="before")
    def validate_data(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        # This will be populated with the entity type during validation in the service layer
        entity_type = values.get("__entity_type")
        if entity_type:
            schema = ENTITY_TYPE_SCHEMAS.get(entity_type)
            if schema:
                try:
                    values["data"] = schema(**values["data"]).model_dump()
                except Exception as e:
                    raise ValueError(
                        f"Invalid data for entity type '{entity_type}': {str(e)}"
                    )
        return values
