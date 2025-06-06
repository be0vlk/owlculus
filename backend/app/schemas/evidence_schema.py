"""
Evidence schemas for the application.
"""

from datetime import datetime
from typing import Optional, ClassVar, List
from pydantic import BaseModel, ConfigDict, Field, model_validator
from ..core.utils import get_utc_now


class EvidenceBase(BaseModel):
    """Base class for evidence schemas."""

    title: str
    description: Optional[str] = None
    evidence_type: str = Field(default="file")
    category: str = Field(
        description="Category of the evidence for organization purposes"
    )
    content: Optional[str] = None  # File path
    file_hash: Optional[str] = None  # SHA-256 hash of file content
    folder_path: Optional[str] = None
    is_folder: bool = Field(default=False)
    parent_folder_id: Optional[int] = None


class EvidenceCreate(EvidenceBase):
    """Schema for creating evidence."""

    case_id: int = Field(..., gt=0)  # Ensure case_id is provided and positive
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    created_by_id: Optional[int] = None

    VALID_CATEGORIES: ClassVar[List[str]] = [
        "Social Media",
        "Associates",
        "Network Assets",
        "Communications",
        "Documents",
        "Other"
    ]

    @model_validator(mode="after")
    def validate_fields(self) -> "EvidenceCreate":
        if self.evidence_type not in ["file", "text"]:
            raise ValueError("evidence_type must be either 'file' or 'text'")
        
        # Make category validation case-insensitive
        if self.category.lower() not in [cat.lower() for cat in self.VALID_CATEGORIES]:
            raise ValueError(f"category must be one of: {', '.join(self.VALID_CATEGORIES)}")
        
        # Ensure consistent casing with VALID_CATEGORIES
        self.category = next(cat for cat in self.VALID_CATEGORIES if cat.lower() == self.category.lower())
        
        return self


class FolderCreate(BaseModel):
    """Schema for creating folders."""
    
    case_id: int = Field(..., gt=0)
    title: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    parent_folder_id: Optional[int] = None
    folder_path: Optional[str] = Field(default=None, max_length=500)


class FolderUpdate(BaseModel):
    """Schema for updating folders."""
    
    title: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    parent_folder_id: Optional[int] = None
    updated_at: datetime = Field(default_factory=get_utc_now)


class EvidenceUpdate(BaseModel):
    """Schema for updating evidence."""

    title: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    content: Optional[str] = None  # File path
    file_hash: Optional[str] = None  # SHA-256 hash of file content
    folder_path: Optional[str] = None
    parent_folder_id: Optional[int] = None
    updated_at: datetime = Field(default_factory=get_utc_now)

    VALID_CATEGORIES: ClassVar[List[str]] = EvidenceCreate.VALID_CATEGORIES

    @model_validator(mode="after")
    def validate_category(self) -> "EvidenceUpdate":
        if self.category is not None and self.category.lower() not in [cat.lower() for cat in self.VALID_CATEGORIES]:
            raise ValueError(f"category must be one of: {', '.join(self.VALID_CATEGORIES)}")
        if self.category is not None:
            self.category = next(cat for cat in self.VALID_CATEGORIES if cat.lower() == self.category.lower())
        return self


class Evidence(EvidenceBase):
    """Schema for evidence responses."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    case_id: int
    created_at: datetime
    updated_at: datetime
    created_by_id: int
