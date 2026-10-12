from sqlalchemy import Column, Integer, String, Text, ForeignKey, JSON, UniqueConstraint, DateTime
from sqlalchemy.orm import relationship
from datetime import datetime
from database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    github_id = Column(Integer, unique=True, index=True)
    username = Column(String, unique=True, index=True)
    encrypted_github_token = Column(Text)
    llm_provider = Column(String, default="groq", nullable=True)
    llm_model = Column(String, nullable=True)
    encrypted_llm_api_key = Column(Text, nullable=True)

    projects = relationship("Project", back_populates="owner")

class Project(Base):
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    repo_url = Column(String)
    owner_id = Column(Integer, ForeignKey("users.id"))
    is_ai_enabled = Column(Integer, default=1) # AI enabled by default
    project_type = Column(String, nullable=True)  # saas, ecommerce, social, internal_tool, api_only
    database_enums = Column(JSON, default=list, nullable=True) # Spec v2 enums
    database_relations = Column(JSON, default=list, nullable=True) # Spec v2 project-level relations
    target_branch = Column(String, default="main", nullable=True)
    governance_mode = Column(String, default="direct", nullable=True) # "direct" | "pr"

    owner = relationship("User", back_populates="projects")
    features = relationship("Feature", back_populates="project", cascade="all, delete-orphan")
    schemas = relationship("DatabaseSchema", back_populates="project", cascade="all, delete-orphan")
    endpoints = relationship("ApiEndpoint", back_populates="project", cascade="all, delete-orphan")
    ui_components = relationship("UIComponent", back_populates="project", cascade="all, delete-orphan")
    prompts = relationship("PromptTemplate", back_populates="project", cascade="all, delete-orphan")
    dismissed_recommendations = relationship("DismissedRecommendation", back_populates="project", cascade="all, delete-orphan")
    snapshots = relationship("SpecSnapshot", back_populates="project", cascade="all, delete-orphan", order_by="desc(SpecSnapshot.id)")
    decision_records = relationship("DecisionRecord", back_populates="project", cascade="all, delete-orphan", order_by="desc(DecisionRecord.id)")

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
    fields = Column(JSON) # List of ColumnV2 dicts
    relations = Column(JSON, default=list, nullable=True) # List of RelationV2 dicts
    code = Column(Text, nullable=True) # The actual Prisma/SQL code

    project = relationship("Project", back_populates="schemas")
    
    __table_args__ = (UniqueConstraint('project_id', 'table_name', name='_project_schema_uc'),)

class ApiEndpoint(Base):
    __tablename__ = "api_endpoints"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"))
    method = Column(String)
    route = Column(String)
    linked_table = Column(String, nullable=True) # Linked database table
    auth_required = Column(Integer, default=1) # 1 = True, 0 = False
    auth_type = Column(String, default="bearer") # bearer, api_key, etc.
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

class DismissedRecommendation(Base):
    __tablename__ = "dismissed_recommendations"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"))
    recommendation_id = Column(String, index=True)  # e.g., hash ID from recommender

    project = relationship("Project", back_populates="dismissed_recommendations")

    __table_args__ = (UniqueConstraint('project_id', 'recommendation_id', name='_project_dismissed_uc'),)

class SpecSnapshot(Base):
    __tablename__ = "spec_snapshots"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), index=True)
    spec_json = Column(JSON)           # Full spec at sync time
    scan_json = Column(JSON)           # Scanner output at sync time
    created_at = Column(DateTime, default=datetime.utcnow)
    source = Column(String, default="sync") # "push" | "pull" | "initial" | "sync"

    project = relationship("Project", back_populates="snapshots")


class DecisionRecord(Base):
    __tablename__ = "decision_records"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), index=True)
    title = Column(String)
    status = Column(String, default="accepted") # proposed, accepted, rejected, superseded
    content = Column(Text) # Markdown content
    file_path = Column(String) # e.g. "docs/adr/0001-add-billing.md"
    committed = Column(Integer, default=0) # 1 = committed to git, 0 = draft
    created_at = Column(DateTime, default=datetime.utcnow)

    project = relationship("Project", back_populates="decision_records")


