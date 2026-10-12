import pytest
import io
import tarfile
from unittest.mock import AsyncMock, patch, MagicMock
import repo_scanner


# ============================================================================
# FIXTURES
# ============================================================================

SQLALCHEMY_TRADITIONAL = """
from sqlalchemy import Column, Integer, String, Text, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from database import Base

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    name = Column(String(50))
    email = Column(String, unique=True)
    is_active = Column(Boolean, default=True)

class Post(Base):
    __tablename__ = "posts"
    id = Column(Integer, primary_key=True)
    title = Column(String(200))
    content = Column(Text)
    author_id = Column(Integer, ForeignKey("users.id"))
    author = relationship("User", back_populates="posts")
"""

SQLALCHEMY_20_MAPPED = """
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import String, ForeignKey
from datetime import datetime

class Base(DeclarativeBase):
    pass

class Organization(Base):
    __tablename__ = "organizations"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))

class Member(Base):
    __tablename__ = "members"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    org_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"))
    joined_at: Mapped[datetime] = mapped_column()
"""

DJANGO_MODELS = """
from django.db import models

class Author(models.Model):
    name = models.CharField(max_length=100)
    bio = models.TextField()

    class Meta:
        db_table = "authors"

class Book(models.Model):
    title = models.CharField(max_length=200)
    pages = models.IntegerField()
    author = models.ForeignKey(Author, on_delete=models.CASCADE)
    published_date = models.DateField()

    class Meta:
        db_table = "books"
"""

SQLMODEL_CODE = """
from typing import Optional
from sqlmodel import Field, SQLModel

class Team(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    headquarters: str

class Hero(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    secret_name: str
    age: Optional[int] = None
    team_id: Optional[int] = Field(default=None, foreign_key="team.id")
"""

DRIZZLE_SCHEMA = """
import { pgTable, serial, text, integer, timestamp, boolean } from "drizzle-orm/pg-core";

export const users = pgTable("users", {
  id: serial("id").primaryKey(),
  name: text("name"),
  email: text("email"),
  isActive: boolean("is_active"),
});

export const comments = pgTable("comments", {
  id: serial("id").primaryKey(),
  body: text("body"),
  userId: integer("user_id").references(() => users.id),
  createdAt: timestamp("created_at"),
});
"""

PRISMA_SCHEMA = """
datasource db {
  provider = "postgresql"
  url      = env("DATABASE_URL")
}

model Customer {
  id        Int      @id @default(autoincrement())
  email     String   @unique
  name      String?
  orders    Order[]
}

model Order {
  id          Int      @id @default(autoincrement())
  amount      Float
  customerId  Int
  customer    Customer @relation(fields: [customerId], references: [id])
}
"""

FLASK_ROUTES = """
from flask import Flask, Blueprint, jsonify, request

app = Flask(__name__)
auth_bp = Blueprint("auth", __name__, url_prefix="/auth")

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})

@app.route("/items", methods=["GET", "POST"])
def manage_items():
    return jsonify([])

@auth_bp.route("/login", methods=["POST"])
def login():
    return jsonify({"token": "xyz"})
"""

NESTJS_CONTROLLER = """
import { Controller, Get, Post, Put, Delete, Body, Param } from '@nestjs/common';

@Controller('products')
export class ProductsController {
  @Get()
  findAll() {
    return [];
  }

  @Get(':id')
  findOne(@Param('id') id: string) {
    return { id };
  }

  @Post()
  create(@Body() body: any) {
    return body;
  }

  @Put(':id')
  update(@Param('id') id: string) {
    return {};
  }

  @Delete(':id')
  remove(@Param('id') id: string) {
    return {};
  }
}
"""


# ============================================================================
# TESTS
# ============================================================================

def test_parse_sqlalchemy_traditional():
    tables = repo_scanner.parse_sqlalchemy_models(SQLALCHEMY_TRADITIONAL)
    table_map = {t["table_name"]: t for t in tables}

    assert "users" in table_map
    assert "posts" in table_map

    user_fields = {f["name"]: f["type"] for f in table_map["users"]["fields"]}
    assert user_fields["id"] == "integer"
    assert user_fields["name"] == "string"
    assert user_fields["email"] == "string"
    assert user_fields["is_active"] == "boolean"

    post_fields = {f["name"]: f["type"] for f in table_map["posts"]["fields"]}
    assert post_fields["id"] == "integer"
    assert post_fields["title"] == "string"
    assert post_fields["content"] == "text"
    assert post_fields["author_id"] == "integer"

    # Check relation
    post_rels = table_map["posts"]["relations"]
    assert any(
        r["from_field"] == "author_id" and r["to_table"] == "users" and r["to_field"] == "id"
        for r in post_rels
    )


def test_parse_sqlalchemy_20_mapped():
    tables = repo_scanner.parse_sqlalchemy_models(SQLALCHEMY_20_MAPPED)
    table_map = {t["table_name"]: t for t in tables}

    assert "organizations" in table_map
    assert "members" in table_map

    member_fields = {f["name"]: f["type"] for f in table_map["members"]["fields"]}
    assert member_fields["id"] == "integer"
    assert member_fields["user_id"] == "integer"
    assert member_fields["org_id"] == "integer"

    member_rels = table_map["members"]["relations"]
    assert any(r["from_field"] == "user_id" and r["to_table"] == "users" for r in member_rels)
    assert any(r["from_field"] == "org_id" and r["to_table"] == "organizations" for r in member_rels)


def test_parse_django_models():
    tables = repo_scanner.parse_django_models(DJANGO_MODELS)
    table_map = {t["table_name"]: t for t in tables}

    assert "authors" in table_map
    assert "books" in table_map

    author_fields = {f["name"]: f["type"] for f in table_map["authors"]["fields"]}
    assert author_fields["name"] == "string"
    assert author_fields["bio"] == "text"

    book_fields = {f["name"]: f["type"] for f in table_map["books"]["fields"]}
    assert book_fields["title"] == "string"
    assert book_fields["pages"] == "integer"
    assert book_fields["author"] == "integer"

    book_rels = table_map["books"]["relations"]
    assert any(r["from_field"] == "author" and r["to_table"] == "Author" for r in book_rels)


def test_parse_sqlmodel_models():
    tables = repo_scanner.parse_sqlmodel_models(SQLMODEL_CODE)
    table_map = {t["table_name"]: t for t in tables}

    assert "team" in table_map
    assert "hero" in table_map

    hero_fields = {f["name"]: f["type"] for f in table_map["hero"]["fields"]}
    assert hero_fields["id"] == "integer"
    assert hero_fields["name"] == "string"
    assert hero_fields["secret_name"] == "string"
    assert hero_fields["team_id"] == "integer"

    hero_rels = table_map["hero"]["relations"]
    assert any(r["from_field"] == "team_id" and r["to_table"] == "team" for r in hero_rels)


def test_parse_drizzle_schema():
    tables = repo_scanner.parse_drizzle_schema(DRIZZLE_SCHEMA)
    table_map = {t["table_name"]: t for t in tables}

    assert "users" in table_map
    assert "comments" in table_map

    user_fields = {f["name"]: f["type"] for f in table_map["users"]["fields"]}
    assert user_fields["id"] == "integer"
    assert user_fields["name"] in ("string", "text")
    assert user_fields["isActive"] == "boolean"

    comment_fields = {f["name"]: f["type"] for f in table_map["comments"]["fields"]}
    assert comment_fields["id"] == "integer"
    assert comment_fields["body"] == "text"
    assert comment_fields["userId"] == "integer"
    assert comment_fields["createdAt"] == "datetime"

    comment_rels = table_map["comments"]["relations"]
    assert any(r["from_field"] == "userId" and r["to_table"] == "users" and r["to_field"] == "id" for r in comment_rels)


def test_parse_prisma_schema_relations():
    tables = repo_scanner.parse_prisma_schema(PRISMA_SCHEMA)
    table_map = {t["table_name"]: t for t in tables}

    assert "Customer" in table_map
    assert "Order" in table_map

    order_fields = {f["name"]: f["type"] for f in table_map["Order"]["fields"]}
    assert order_fields["id"] == "integer"
    assert order_fields["amount"] == "float"
    assert order_fields["customerId"] == "integer"

    order_rels = table_map["Order"]["relations"]
    assert any(r["from_field"] == "customerId" and r["to_table"] == "Customer" and r["to_field"] == "id" for r in order_rels)


def test_parse_flask_routes():
    routes = repo_scanner.parse_flask_routes(FLASK_ROUTES)
    route_keys = {(r["method"], r["route"]) for r in routes}

    assert ("GET", "/health") in route_keys
    assert ("GET", "/items") in route_keys
    assert ("POST", "/items") in route_keys
    assert ("POST", "/login") in route_keys


def test_parse_nestjs_controllers():
    routes = repo_scanner.parse_nestjs_controllers(NESTJS_CONTROLLER)
    route_keys = {(r["method"], r["route"]) for r in routes}

    assert ("GET", "/products") in route_keys
    assert ("GET", "/products/:id") in route_keys
    assert ("POST", "/products") in route_keys
    assert ("PUT", "/products/:id") in route_keys
    assert ("DELETE", "/products/:id") in route_keys


@pytest.mark.anyio
async def test_tarball_extraction_mocked():
    # Build in-memory tar.gz archive
    tar_buffer = io.BytesIO()
    with tarfile.open(fileobj=tar_buffer, mode="w:gz") as tar:
        # File 1: Python model
        py_data = SQLALCHEMY_TRADITIONAL.encode("utf-8")
        tarinfo1 = tarfile.TarInfo(name="repo-main/models/user.py")
        tarinfo1.size = len(py_data)
        tar.addfile(tarinfo1, io.BytesIO(py_data))

        # File 2: Flask routes
        flask_data = FLASK_ROUTES.encode("utf-8")
        tarinfo2 = tarfile.TarInfo(name="repo-main/routes/app.py")
        tarinfo2.size = len(flask_data)
        tar.addfile(tarinfo2, io.BytesIO(flask_data))

        # File 3: Irrelevant file (.md)
        md_data = b"# Readme"
        tarinfo3 = tarfile.TarInfo(name="repo-main/README.md")
        tarinfo3.size = len(md_data)
        tar.addfile(tarinfo3, io.BytesIO(md_data))

    tar_bytes = tar_buffer.getvalue()

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.content = tar_bytes

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_response

        files = await repo_scanner.fetch_repo_tarball("fake_token", "owner", "repo")
        assert "models/user.py" in files
        assert "routes/app.py" in files
        assert "README.md" not in files  # skipped as not relevant


@pytest.mark.anyio
async def test_scan_repo_end_to_end_mocked():
    # Mock fetch_repo_tarball to return multiple frameworks in one repo
    mock_files = {
        "models/db.py": SQLALCHEMY_TRADITIONAL,
        "api/flask_app.py": FLASK_ROUTES,
        "src/schema.prisma": PRISMA_SCHEMA,
    }

    with patch("repo_scanner.fetch_repo_tarball", new_callable=AsyncMock) as mock_tarball:
        mock_tarball.return_value = mock_files

        result = await repo_scanner.scan_repo("dummy_token", "owner/sample-repo")

        assert "tables" in result
        assert "routes" in result
        assert "relations" in result
        assert result["files_scanned"] == 3
        assert result["total_files"] == 3

        table_names = [t["table_name"] for t in result["tables"]]
        assert "users" in table_names
        assert "posts" in table_names
        assert "Customer" in table_names
        assert "Order" in table_names

        routes = {(r["method"], r["route"]) for r in result["routes"]}
        assert ("GET", "/health") in routes
        assert ("POST", "/login") in routes

        assert len(result["relations"]) > 0


def test_parse_fastapi_routes():
    code = """
from fastapi import FastAPI, APIRouter

app = FastAPI()

@app.get("/")
async def root():
    return {"message": "ok"}

@app.get("/api/health")
async def health():
    return {"status": "healthy"}

@app.post("/api/analyze")
async def analyze_doc(file: bytes):
    return {}

@app.post("/api/report/pdf")
async def get_pdf(data: dict):
    return {}
"""
    routes = repo_scanner.parse_fastapi_routes(code)
    route_set = {(r["method"], r["route"]) for r in routes}
    assert ("GET", "/") in route_set
    assert ("GET", "/api/health") in route_set
    assert ("POST", "/api/analyze") in route_set
    assert ("POST", "/api/report/pdf") in route_set

