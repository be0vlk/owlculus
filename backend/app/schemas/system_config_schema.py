from pydantic import BaseModel, validator
from typing import Optional
from datetime import datetime


class SystemConfigurationBase(BaseModel):
    case_number_template: str
    case_number_prefix: Optional[str] = None


class SystemConfigurationCreate(SystemConfigurationBase):
    @validator('case_number_template')
    def validate_template(cls, v):
        if v not in ["YYMM-NN", "PREFIX-YYMM-NN"]:
            raise ValueError('Template must be either "YYMM-NN" or "PREFIX-YYMM-NN"')
        return v

    @validator('case_number_prefix')
    def validate_prefix(cls, v, values):
        template = values.get('case_number_template')
        if template == "PREFIX-YYMM-NN":
            if not v:
                raise ValueError('Prefix is required for PREFIX-YYMM-NN template')
            if not v.isalnum() or len(v) < 2 or len(v) > 8:
                raise ValueError('Prefix must be 2-8 alphanumeric characters')
        return v


class SystemConfigurationUpdate(SystemConfigurationCreate):
    pass


class SystemConfigurationResponse(SystemConfigurationBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class SystemConfigurationPreview(BaseModel):
    template: str
    prefix: Optional[str] = None
    example_case_number: str
    display_name: str