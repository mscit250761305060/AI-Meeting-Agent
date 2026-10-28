"""
app/services/generator/specification.py

Data structures and validation schema for provider-independent project specifications.
"""

from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field


class FieldSpec(BaseModel):
    name: str
    type: str = "string"  # "string", "integer", "float", "boolean", "date", "text"
    label: str
    required: bool = True
    default: Optional[Any] = None
    options: Optional[List[str]] = None


class PageSpec(BaseModel):
    title: str
    slug: str
    type: str = "generic"  # "dashboard", "list", "form", "login", "analytics", "settings", "generic"
    description: Optional[str] = ""


class ApiEndpointSpec(BaseModel):
    method: str
    path: str
    description: str
    request_body: Optional[str] = None
    response_model: Optional[str] = None


class ProjectSpecification(BaseModel):
    project_name: str
    project_slug: str
    purpose: str
    industry: str = "General"
    entity_name: str  # e.g., "Product", "Task", "Patient", "Item"
    entity_plural: str  # e.g., "products", "tasks", "patients", "items"
    fields: List[FieldSpec] = Field(default_factory=list)
    pages: List[PageSpec] = Field(default_factory=list)
    features: List[str] = Field(default_factory=list)
    user_roles: List[str] = Field(default_factory=lambda: ["Admin", "User"])
    backend_framework: str = "FastAPI"
    database_type: str = "SQLite"
    api_endpoints: List[ApiEndpointSpec] = Field(default_factory=list)
    unsupported_requirements: List[str] = Field(default_factory=list)
    generation_notes: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
