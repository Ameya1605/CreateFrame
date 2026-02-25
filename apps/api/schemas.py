from pydantic import BaseModel
from typing import List, Optional, Dict, Any

class DatabaseField(BaseModel):
    name: str
    type: str

class SchemaCreate(BaseModel):
    table_name: str
    fields: List[DatabaseField]
    code: Optional[str] = None

class EndpointCreate(BaseModel):
    method: str
    route: str
    request_schema: Dict[str, Any]
    response_schema: Dict[str, Any]
    code: Optional[str] = None

class FeatureCreate(BaseModel):
    name: str
    status: str = "mvp"
    description: Optional[str] = None

class UIComponentCreate(BaseModel):
    name: str
    type: str # page, layout, component
    route: Optional[str] = None
    code: Optional[str] = None

class PromptCreate(BaseModel):
    name: str
    template: str

class ProjectCreate(BaseModel):
    name: str
    repo_url: str

class ProjectBase(BaseModel):
    id: int
    name: str
    repo_url: str
    owner_id: int
    is_ai_enabled: bool = False

    class Config:
        from_attributes = True

class UserBase(BaseModel):
    id: int
    username: str
    github_id: int

    class Config:
        from_attributes = True

class GenerateComponentRequest(BaseModel):
    project_id: int
    component_name: str
    component_type: str # page, component, layout
    description: Optional[str] = None

class GitHubAuthRequest(BaseModel):
    code: str

class SpecPushRequest(BaseModel):
    project_id: int

class BrainstormRequest(BaseModel):
    description: str
