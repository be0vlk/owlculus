"""Plugin schemas."""

from typing import Any, Dict, List

from pydantic import BaseModel


class PluginMetadata(BaseModel):
    """Schema for plugin metadata"""

    name: str  # Internal name (class name)
    display_name: str
    description: str
    enabled: bool = True
    category: str = "Other"
    parameters: Dict[str, Dict[str, Any]] = {}
    api_key_requirements: List[str] = []
    api_key_status: Dict[str, bool] = {}
