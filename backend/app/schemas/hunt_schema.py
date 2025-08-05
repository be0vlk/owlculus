"""
Pydantic schemas for hunt operations
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class HuntResponse(BaseModel):
    """Response model for hunt listings"""

    id: int
    name: str
    display_name: str
    description: str
    category: str
    version: str
    is_active: bool
    initial_parameters: Dict[str, Dict[str, Any]]
    step_count: Optional[int] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        orm_mode = True


class HuntExecuteRequest(BaseModel):
    """Request model for starting a hunt"""

    case_id: int = Field(..., description="ID of the case to run the hunt for")
    parameters: Dict[str, Any] = Field(
        default_factory=dict, description="Initial parameters for the hunt"
    )


class HuntStepResponse(BaseModel):
    """Response model for hunt step details"""

    id: int
    execution_id: int
    step_id: str
    plugin_name: str
    status: str
    parameters: Dict[str, Any]
    output: Optional[Dict[str, Any]] = None
    error_details: Optional[str] = None
    retry_count: int
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    class Config:
        orm_mode = True


class HuntExecutionResponse(BaseModel):
    """Response model for hunt execution details"""

    id: int
    hunt_id: int
    case_id: int
    status: str
    progress: float
    initial_parameters: Dict[str, Any]
    context_data: Optional[Dict[str, Any]] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: datetime
    created_by_id: int

    # Related data
    hunt: Optional[HuntResponse] = None
    steps: Optional[List[HuntStepResponse]] = None
    case: Optional[Dict[str, Any]] = None  # Simple case info
    created_by: Optional[Dict[str, Any]] = None  # Simple user info

    class Config:
        orm_mode = True


class HuntExecutionListResponse(BaseModel):
    """Response model for listing hunt executions"""

    id: int
    hunt_id: int
    case_id: int
    status: str
    progress: float
    initial_parameters: Dict[str, Any]
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: datetime
    created_by_id: int

    # Basic hunt info
    hunt_display_name: Optional[str] = None
    hunt_category: Optional[str] = None

    class Config:
        orm_mode = True


class HuntProgressEvent(BaseModel):
    """WebSocket event for hunt progress updates"""

    execution_id: int
    event_type: str  # started, step_complete, step_failed, complete, error
    step_id: Optional[str] = None
    progress: float
    message: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    data: Optional[Dict[str, Any]] = None
