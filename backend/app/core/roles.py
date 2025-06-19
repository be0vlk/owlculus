"""
User role definitions and constants
"""

from enum import Enum


class UserRole(str, Enum):
    ADMIN = "Admin"
    INVESTIGATOR = "Investigator"
    ANALYST = "Analyst"
