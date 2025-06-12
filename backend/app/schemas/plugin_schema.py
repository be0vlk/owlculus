"""
Plugin schemas for request/response validation
"""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel


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
    api_key_requirements: List[str] = []  # List of required API key providers
    api_key_status: Dict[str, bool] = {}  # Status of required API keys


class PluginOutput(BaseModel):
    """Schema for standardized plugin output"""

    type: str = "data"  # data, error, or status
    data: Dict[str, Any]  # Structured output data
