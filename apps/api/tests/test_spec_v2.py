import pytest
from fastapi.testclient import TestClient
import spec_v2
import generator
import models
import main

client = TestClient(main.app)

def test_spec_v2_json_schema_structure():
    schema = spec_v2.SPEC_V2_JSON_SCHEMA
    assert schema["type"] == "object"
    assert "version" in schema["properties"]
    assert "enums" in schema["properties"]
    assert "relations" in schema["properties"]
    assert "database" in schema["properties"]
    assert "endpoints" in schema["properties"]
    
    # Check column properties
    col_props = schema["properties"]["database"]["items"]["properties"]["columns"]["items"]["properties"]
    for field in ["name", "type", "primary_key", "nullable", "unique", "default", "index"]:
        assert field in col_props

    # Check relation properties
    rel_props = schema["properties"]["relations"]["items"]["properties"]
    for field in ["name", "type", "from_table", "from_field", "to_table", "to_field", "on_delete", "on_update"]:
        assert field in rel_props

    # Check endpoint properties
    ep_props = schema["properties"]["endpoints"]["items"]["properties"]
    for field in ["method", "route", "linked_table", "auth_required", "auth_type", "roles"]:
        assert field in ep_props


def test_validate_spec_v2_success():
    sample_spec = {
        "version": "2.0",
        "project": {
            "name": "SpecApp",
            "repo_url": "https://github.com/example/specapp"
        },
        "enums": [
            {"name": "Role", "values": ["ADMIN", "USER"]}
        ],
        "relations": [
            {
                "name": "UserPosts",
                "type": "1:N",
                "from_table": "Post",
                "from_field": "author_id",
                "to_table": "User",
                "to_field": "id",
                "on_delete": "CASCADE"
            }
        ],
        "database": [
            {
                "table_name": "User",
                "columns": [
                    {"name": "id", "type": "uuid", "primary_key": True},
                    {"name": "email", "type": "string", "unique": True},
                    {"name": "role", "type": "Role", "default": "USER"}
                ]
            },
            {
                "table_name": "Post",
                "columns": [
                    {"name": "id", "type": "uuid", "primary_key": True},
                    {"name": "title", "type": "string"},
                    {"name": "author_id", "type": "uuid", "index": True}
                ]
            }
        ],
        "endpoints": [
            {
                "method": "GET",
                "route": "/users",
                "linked_table": "User",
                "auth_required": True,
                "auth_type": "bearer"
            }
        ]
    }
    is_valid, errors = spec_v2.validate_spec_v2(sample_spec)
    assert is_valid is True
    assert errors == []


def test_validate_spec_v2_catches_invalid_spec():
    invalid_spec = {
        "version": "1.0",  # invalid version
        "project": {},     # missing name
        "database": [
            {
                "table_name": "User",
                "columns": [
                    {"name": "username", "type": "string"} # no primary key
                ]
            }
        ],
        "relations": [
            {
                "name": "BogusRel",
                "from_table": "NonExistent",
                "to_table": "User"
            }
        ],
        "endpoints": [
            {"method": "GET", "route": "/users"},
            {"method": "GET", "route": "/users"} # duplicate endpoint
        ]
    }
    is_valid, errors = spec_v2.validate_spec_v2(invalid_spec)
    assert is_valid is False
    assert any("version" in err.lower() for err in errors)
    assert any("primary key" in err.lower() for err in errors)
    assert any("non-existent" in err.lower() for err in errors)
    assert any("duplicate endpoint" in err.lower() for err in errors)


def test_normalize_v1_to_v2_backward_compatibility():
    legacy_spec = {
        "project": {"name": "OldApp"},
        "database": [
            {
                "table_name": "items",
                "fields": [
                    {"name": "title", "type": "string"},
                    {"name": "price", "type": "integer"}
                ]
            }
        ],
        "endpoints": [
            {"method": "get", "route": "/items"}
        ]
    }
    normalized = spec_v2.normalize_v1_to_v2(legacy_spec)
    assert normalized["version"] == "2.0"
    assert len(normalized["database"]) == 1
    table = normalized["database"][0]
    
    # Both columns and fields aliases must be present
    assert "columns" in table
    assert "fields" in table
    assert table["columns"] == table["fields"]

    # Automatically injected primary key
    col_names = [c["name"] for c in table["columns"]]
    assert "id" in col_names
    id_col = next(c for c in table["columns"] if c["name"] == "id")
    assert id_col["primary_key"] is True

    # Endpoints normalized and linked_table inferred
    ep = normalized["endpoints"][0]
    assert ep["method"] == "GET"
    assert ep["linked_table"] == "items"
    assert ep["auth_required"] is True


def test_prisma_generation_with_enums_relations_and_indexes():
    spec = {
        "enums": [
            {"name": "SubscriptionTier", "values": ["FREE", "PRO", "ENTERPRISE"]}
        ],
        "relations": [
            {
                "name": "OrgMembers",
                "type": "1:N",
                "from_table": "Member",
                "from_field": "org_id",
                "to_table": "Organization",
                "to_field": "id",
                "on_delete": "CASCADE"
            }
        ],
        "database": [
            {
                "table_name": "Organization",
                "columns": [
                    {"name": "id", "type": "uuid", "primary_key": True},
                    {"name": "name", "type": "string"},
                    {"name": "tier", "type": "SubscriptionTier", "default": "FREE"}
                ]
            },
            {
                "table_name": "Member",
                "columns": [
                    {"name": "id", "type": "uuid", "primary_key": True},
                    {"name": "email", "type": "string", "unique": True, "nullable": False},
                    {"name": "org_id", "type": "uuid", "index": True}
                ]
            }
        ]
    }
    prisma_code = generator.generate_prisma_schema(spec)
    
    # Enums
    assert "enum SubscriptionTier {" in prisma_code
    assert "FREE" in prisma_code and "PRO" in prisma_code

    # Modifiers
    assert "tier SubscriptionTier @default(\"FREE\")" in prisma_code
    assert "email String @unique" in prisma_code

    # Indexes
    assert "@@index([org_id])" in prisma_code

    # Relations
    assert "organization Organization @relation(fields: [org_id], references: [id], onDelete: Cascade)" in prisma_code
    assert "members Member[]" in prisma_code


def test_fastapi_generation_with_auth_and_linked_tables():
    spec = {
        "endpoints": [
            {
                "method": "get",
                "route": "/public/health",
                "auth_required": False
            },
            {
                "method": "post",
                "route": "/organizations/{id}/members",
                "linked_table": "Member",
                "auth_required": True,
                "request_schema": {"email": "string", "role": "string"},
                "response_schema": {"id": "string", "email": "string"}
            }
        ]
    }
    fastapi_code = generator.generate_fastapi_code(spec)
    
    # Compiles without syntax errors
    compiled = compile(fastapi_code, "<test_fastapi>", "exec")
    assert compiled is not None

    # Public endpoint has no auth dependency
    assert "async def get_public_health():" in fastapi_code

    # Protected endpoint with linked table has both current_user and db dependencies
    assert "current_user: Any = Depends(get_current_user)" in fastapi_code
    assert "db: Any = Depends(get_db)" in fastapi_code
    assert "# Target Entity: Member" in fastapi_code


def test_spec_schema_and_validate_api_routes():
    # GET /spec/schema
    res_schema = client.get("/spec/schema")
    assert res_schema.status_code == 200
    data = res_schema.json()
    assert data.get("title") == "SpecOS Specification v2"
    assert data.get("version", {}).get("enum") == ["2.0"] or "2.0" in str(data)

    # POST /spec/validate - valid
    valid_payload = {
        "version": "2.0",
        "project": {"name": "Test", "repo_url": "https://github.com/a/b"},
        "database": [
            {
                "table_name": "Task",
                "columns": [{"name": "id", "type": "uuid", "primary_key": True}]
            }
        ],
        "endpoints": [
            {"method": "GET", "route": "/tasks"}
        ]
    }
    res_val_ok = client.post("/spec/validate", json=valid_payload)
    assert res_val_ok.status_code == 200
    assert res_val_ok.json()["valid"] is True
    assert res_val_ok.json()["errors"] == []

    # POST /spec/validate - invalid
    invalid_payload = {
        "version": "1.0",
        "database": "not a list"
    }
    res_val_bad = client.post("/spec/validate", json=invalid_payload)
    assert res_val_bad.status_code == 200
    assert res_val_bad.json()["valid"] is False
    assert len(res_val_bad.json()["errors"]) > 0


def test_serialize_project_spec_produces_spec_v2():
    p = models.Project(
        id=99,
        name="UnifiedSerializerApp",
        repo_url="https://github.com/org/unified",
        owner_id=1,
        is_ai_enabled=1,
        project_type="saas"
    )
    p.database_enums = [{"name": "Status", "values": ["OPEN", "CLOSED"]}]
    p.database_relations = [
        {
            "name": "UserTasks",
            "type": "1:N",
            "from_table": "tasks",
            "from_field": "user_id",
            "to_table": "users",
            "to_field": "id",
            "on_delete": "CASCADE"
        }
    ]
    p.schemas = [
        models.DatabaseSchema(
            table_name="users",
            fields=[
                {"name": "id", "type": "uuid", "primary_key": True},
                {"name": "email", "type": "string"}
            ]
        ),
        models.DatabaseSchema(
            table_name="tasks",
            fields=[
                {"name": "id", "type": "uuid", "primary_key": True},
                {"name": "title", "type": "string", "nullable": False},
                {"name": "status", "type": "Status", "default": "OPEN"}
            ]
        )
    ]
    p.endpoints = [
        models.ApiEndpoint(
            method="GET",
            route="/tasks",
            linked_table="tasks",
            auth_required=True,
            auth_type="bearer"
        )
    ]
    p.features = []
    p.ui_components = []
    p.prompts = []

    spec = main.serialize_project_spec(p)
    
    assert spec["version"] == "2.0"
    assert spec["enums"] == [{"name": "Status", "values": ["OPEN", "CLOSED"]}]
    assert len(spec["relations"]) == 1
    assert spec["relations"][0]["name"] == "UserTasks"
    assert spec["database"][0]["columns"][0]["primary_key"] is True
    assert spec["database"][0]["fields"][0]["primary_key"] is True
    assert spec["endpoints"][0]["linked_table"] == "tasks"
    assert spec["endpoints"][0]["auth_required"] is True

    # Ensure output passes spec v2 validation
    is_valid, errors = spec_v2.validate_spec_v2(spec)
    assert is_valid is True
    assert errors == []
