from pydantic import BaseModel
from typing import List, Optional, Dict, Any

class DatabaseField(BaseModel):
    name: str
    type: str

class SchemaCreate(BaseModel):
    table_name: str
    fields: List[DatabaseField]

class EndpointCreate(BaseModel):
    method: str
    route: str
    request_schema: Dict[str, Any]
    response_schema: Dict[str, Any]

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

    class Config:
        orm_mode = True

class UserBase(BaseModel):
    id: int
    username: str
    github_id: int

    class Config:
        orm_mode = True

class GitHubAuthRequest(BaseModel):
    code: str

class SpecPushRequest(BaseModel):
    project_id: int
