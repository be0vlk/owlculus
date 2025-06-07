"""
Plugin schemas for request/response validation
"""

from pydantic import BaseModel
from typing import Dict, Any, Optional


class PluginParameter(BaseModel):
    """Schema for plugin parameter metadata"""

    type: str
    description: str
    required: bool = False
    default: Any = None


class PluginExecuteRequest(BaseModel):
    """Schema for plugin execution request"""

    plugin_name: str
    params: Optional[Dict[str, Any]] = None


class PluginMetadata(BaseModel):
    """Schema for plugin metadata"""

    name: str  # Internal name (class name)
    display_name: str  # User-friendly name
    description: str
    enabled: bool = True  # Whether the plugin is enabled
    category: str = "Other"  # Plugin category
    parameters: Dict[str, Dict[str, Any]] = {}  # Plugin parameters


class PluginOutput(BaseModel):
    """Schema for standardized plugin output"""

    type: str = "data"  # data, error, or status
    data: Dict[str, Any]  # Structured output data
