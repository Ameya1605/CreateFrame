from sqlalchemy import Column, Integer, String, Text, ForeignKey, JSON
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

    owner = relationship("User", back_populates="projects")
    schemas = relationship("DatabaseSchema", back_populates="project", cascade="all, delete-orphan")
    endpoints = relationship("ApiEndpoint", back_populates="project", cascade="all, delete-orphan")
    prompts = relationship("PromptTemplate", back_populates="project", cascade="all, delete-orphan")

class DatabaseSchema(Base):
    __tablename__ = "database_schemas"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"))
    table_name = Column(String)
    fields = Column(JSON) # List of {name: str, type: str}

    project = relationship("Project", back_populates="schemas")

class ApiEndpoint(Base):
    __tablename__ = "api_endpoints"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"))
    method = Column(String)
    route = Column(String)
    request_schema = Column(JSON)
    response_schema = Column(JSON)

    project = relationship("Project", back_populates="endpoints")

class PromptTemplate(Base):
    __tablename__ = "prompt_templates"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"))
    name = Column(String)
    template = Column(Text)

    project = relationship("Project", back_populates="prompts")
