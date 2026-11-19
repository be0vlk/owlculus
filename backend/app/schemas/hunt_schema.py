"""Hunt schemas."""

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
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


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

    hunt_display_name: Optional[str] = None
    hunt_category: Optional[str] = None


class HuntExecutionResponse(HuntExecutionListResponse):
    """Response model for hunt execution details"""

    context_data: Optional[Dict[str, Any]] = None
    kind: str = "hunt"
    revision: int = 0
    dispatch_state: str = "legacy"
    waiting_reason: str | None = None
    dispatch_attempts: int = 0
    last_dispatch_at: datetime | None = None
    next_dispatch_at: datetime | None = None
    links: dict[str, str] = Field(default_factory=dict)
    error: dict[str, Any] | None = None

    hunt: Optional[HuntResponse] = None
    steps: Optional[List[HuntStepResponse]] = None
    case: Optional[Dict[str, Any]] = None
    created_by: Optional[Dict[str, Any]] = None
