"""
Plugin schemas for request/response validation
"""

from typing import Any, Dict, List

from pydantic import BaseModel


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
