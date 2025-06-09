from pydantic import BaseModel, validator
from typing import Optional, List, Dict
from datetime import datetime


class SystemConfigurationBase(BaseModel):
    case_number_template: str
    case_number_prefix: Optional[str] = None


class SystemConfigurationCreate(SystemConfigurationBase):
    @validator("case_number_template")
    def validate_template(cls, v):
        if v not in ["YYMM-NN", "PREFIX-YYMM-NN"]:
            raise ValueError('Template must be either "YYMM-NN" or "PREFIX-YYMM-NN"')
        return v

    @validator("case_number_prefix")
    def validate_prefix(cls, v, values):
        template = values.get("case_number_template")
        if template == "PREFIX-YYMM-NN":
            if not v:
                raise ValueError("Prefix is required for PREFIX-YYMM-NN template")
            if not v.isalnum() or len(v) < 2 or len(v) > 8:
                raise ValueError("Prefix must be 2-8 alphanumeric characters")
        return v


class SystemConfigurationUpdate(SystemConfigurationCreate):
    pass


class APIKeyUpdate(BaseModel):
    api_key: Optional[str] = None
    name: Optional[str] = None


class APIKeyResponse(BaseModel):
    provider: str
    name: str
    is_configured: bool
    created_at: Optional[str] = None


class APIKeyStatusResponse(BaseModel):
    provider: str
    is_configured: bool


class SystemConfigurationResponse(BaseModel):
    id: int
    case_number_template: str
    case_number_prefix: Optional[str] = None
    api_keys_configured: List[str] = []
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

    @classmethod
    def from_model(cls, config):
        """Create response from SystemConfiguration model."""
        api_keys_configured = []
        if config.api_keys:
            api_keys_configured = [
                provider
                for provider, key_data in config.api_keys.items()
                if key_data.get("is_active", True)
            ]

        config_dict = {
            "id": config.id,
            "case_number_template": config.case_number_template,
            "case_number_prefix": config.case_number_prefix,
            "api_keys_configured": api_keys_configured,
            "created_at": config.created_at,
            "updated_at": config.updated_at,
        }
        return cls(**config_dict)


class SystemConfigurationPreview(BaseModel):
    template: str
    prefix: Optional[str] = None
    example_case_number: str
    display_name: str


class EvidenceFolderTemplateFolder(BaseModel):
    name: str
    description: Optional[str] = None
    subfolders: Optional[List["EvidenceFolderTemplateFolder"]] = []


class EvidenceFolderTemplate(BaseModel):
    name: str
    description: str
    folders: List[EvidenceFolderTemplateFolder]


class EvidenceFolderTemplatesUpdate(BaseModel):
    templates: Dict[str, EvidenceFolderTemplate]


class EvidenceFolderTemplatesResponse(BaseModel):
    templates: Dict[str, Dict]
