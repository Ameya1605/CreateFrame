from sqlalchemy import Column, Integer, String, Text, ForeignKey, JSON, UniqueConstraint
from sqlalchemy.orm import relationship
from database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    github_id = Column(Integer, unique=True, index=True)
    username = Column(String, unique=True, index=True)
    encrypted_github_token = Column(Text)

    projects = relationship("Project", back_populates="owner")

class Project(Base):
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    repo_url = Column(String)
    owner_id = Column(Integer, ForeignKey("users.id"))
    is_ai_enabled = Column(Integer, default=1) # AI enabled by default

    owner = relationship("User", back_populates="projects")
    features = relationship("Feature", back_populates="project", cascade="all, delete-orphan")
    schemas = relationship("DatabaseSchema", back_populates="project", cascade="all, delete-orphan")
    endpoints = relationship("ApiEndpoint", back_populates="project", cascade="all, delete-orphan")
    ui_components = relationship("UIComponent", back_populates="project", cascade="all, delete-orphan")
    prompts = relationship("PromptTemplate", back_populates="project", cascade="all, delete-orphan")

    __table_args__ = (UniqueConstraint('owner_id', 'name', name='_owner_project_uc'),)

class Feature(Base):
    __tablename__ = "features"
    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"))
    name = Column(String)
    status = Column(String, default="mvp") # mvp, v2, experimental
    description = Column(Text, nullable=True)

    project = relationship("Project", back_populates="features")
    
    __table_args__ = (UniqueConstraint('project_id', 'name', name='_project_feature_uc'),)

class DatabaseSchema(Base):
    __tablename__ = "database_schemas"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"))
    table_name = Column(String)
    fields = Column(JSON) # List of {name: str, type: str}
    code = Column(Text, nullable=True) # The actual Prisma/SQL code

    project = relationship("Project", back_populates="schemas")
    
    __table_args__ = (UniqueConstraint('project_id', 'table_name', name='_project_schema_uc'),)

class ApiEndpoint(Base):
    __tablename__ = "api_endpoints"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"))
    method = Column(String)
    route = Column(String)
    request_schema = Column(JSON)
    response_schema = Column(JSON)
    code = Column(Text, nullable=True) # The actual FastAPI/Express code

    project = relationship("Project", back_populates="endpoints")
    
    __table_args__ = (UniqueConstraint('project_id', 'method', 'route', name='_project_endpoint_uc'),)

class UIComponent(Base):
    __tablename__ = "ui_components"
    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"))
    name = Column(String)
    type = Column(String) # page, layout, component
    route = Column(String, nullable=True)
    code = Column(Text, nullable=True) # The actual React/Vue code

    project = relationship("Project", back_populates="ui_components")
    
    __table_args__ = (UniqueConstraint('project_id', 'name', name='_project_ui_uc'),)

class PromptTemplate(Base):
    __tablename__ = "prompt_templates"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"))
    name = Column(String)
    template = Column(Text)

    project = relationship("Project", back_populates="prompts")

    __table_args__ = (UniqueConstraint('project_id', 'name', name='_project_prompt_uc'),)
