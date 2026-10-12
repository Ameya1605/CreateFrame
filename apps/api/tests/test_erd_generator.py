import pytest
import erd_generator


@pytest.fixture
def sample_spec():
    return {
        "version": "2.0",
        "project": {
            "name": "ECommerceStore",
            "description": "Store API and Models"
        },
        "database": [
            {
                "table_name": "users",
                "columns": [
                    {"name": "id", "type": "uuid", "primary_key": True},
                    {"name": "email", "type": "string", "unique": True},
                    {"name": "created_at", "type": "datetime"}
                ]
            },
            {
                "table_name": "orders",
                "columns": [
                    {"name": "id", "type": "integer", "primary_key": True},
                    {"name": "user_id", "type": "uuid", "foreign_key": True},
                    {"name": "total", "type": "float"},
                    {"name": "status", "type": "string", "default": "pending"}
                ]
            }
        ],
        "relations": [
            {
                "name": "UserOrders",
                "type": "1:N",
                "from_table": "orders",
                "from_field": "user_id",
                "to_table": "users",
                "to_field": "id"
            }
        ],
        "endpoints": [
            {
                "method": "GET",
                "route": "/orders",
                "linked_table": "orders",
                "summary": "List all orders"
            },
            {
                "method": "POST",
                "route": "/orders",
                "linked_table": "orders",
                "auth_required": True,
                "summary": "Create order"
            },
            {
                "method": "GET",
                "route": "/orders/:id",
                "linked_table": "orders",
                "summary": "Get order by ID"
            }
        ]
    }


def test_generate_mermaid_erd(sample_spec):
    mermaid = erd_generator.generate_mermaid_erd(sample_spec)
    assert mermaid.startswith("erDiagram")
    assert "users ||--o{ orders : \"UserOrders\"" in mermaid
    assert "users {" in mermaid
    assert "uuid id PK" in mermaid
    assert "string email UK" in mermaid
    assert "orders {" in mermaid
    assert "uuid user_id FK" in mermaid


def test_generate_dbml(sample_spec):
    dbml = erd_generator.generate_dbml(sample_spec)
    assert "Table users {" in dbml
    assert "id uuid [pk]" in dbml
    assert "email varchar [unique]" in dbml
    assert "Table orders {" in dbml
    assert "Ref: orders.user_id < users.id" in dbml


def test_generate_openapi_spec(sample_spec):
    openapi = erd_generator.generate_openapi_spec(sample_spec)
    assert openapi["openapi"] == "3.0.3"
    assert openapi["info"]["title"] == "ECommerceStore"
    assert "/orders" in openapi["paths"]
    assert "get" in openapi["paths"]["/orders"]
    assert "post" in openapi["paths"]["/orders"]
    # Path parameter converted from :id to {id}
    assert "/orders/{id}" in openapi["paths"]
    assert "get" in openapi["paths"]["/orders/{id}"]
    params = openapi["paths"]["/orders/{id}"]["get"]["parameters"]
    assert any(p["name"] == "id" for p in params)
    assert "users" in openapi["components"]["schemas"]
    assert "orders" in openapi["components"]["schemas"]
    # POST endpoint has request body
    assert "requestBody" in openapi["paths"]["/orders"]["post"]
    # Auth required endpoint has security scheme
    assert openapi["paths"]["/orders"]["post"]["security"] == [{"BearerAuth": []}]


def test_export_all_formats(sample_spec):
    exported = erd_generator.export_all_formats(sample_spec)
    assert "mermaid" in exported
    assert "dbml" in exported
    assert "openapi" in exported
    assert exported["stats"]["tables_count"] == 2
    assert exported["stats"]["relations_count"] == 1
    assert exported["stats"]["endpoints_count"] == 3


def test_inferred_relations_when_missing_explicit_relation():
    spec_without_relations = {
        "database": [
            {
                "table_name": "authors",
                "columns": [
                    {"name": "id", "type": "int", "primary_key": True},
                    {"name": "name", "type": "string"}
                ]
            },
            {
                "table_name": "books",
                "columns": [
                    {"name": "id", "type": "int", "primary_key": True},
                    {"name": "author_id", "type": "int", "foreign_key": True},
                    {"name": "title", "type": "string"}
                ]
            }
        ]
    }
    mermaid = erd_generator.generate_mermaid_erd(spec_without_relations)
    assert "authors ||--o{ books" in mermaid
    dbml = erd_generator.generate_dbml(spec_without_relations)
    assert "Ref: books.author_id < authors.id" in dbml


def test_get_project_erd_endpoint():
    from unittest.mock import MagicMock
    from fastapi.testclient import TestClient
    import models
    from database import get_db
    from main import app, get_user_from_header

    client = TestClient(app)
    test_user = models.User(id=999, github_id=999, username="erd_user")
    test_project = models.Project(
        id=555,
        name="ERD Store",
        repo_url="https://github.com/myorg/erd-store",
        owner_id=999,
        schemas=[
            models.DatabaseSchema(
                id=1,
                project_id=555,
                table_name="products",
                fields=[{"name": "id", "type": "int", "primary_key": True}, {"name": "title", "type": "string"}]
            )
        ],
        endpoints=[],
        features=[],
        ui_components=[],
        prompts=[]
    )

    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.first.return_value = test_project

    app.dependency_overrides[get_user_from_header] = lambda: test_user
    app.dependency_overrides[get_db] = lambda: mock_db

    # Test all formats
    res = client.get("/projects/555/erd")
    assert res.status_code == 200
    data = res.json()
    assert "mermaid" in data
    assert "dbml" in data
    assert "openapi" in data
    assert "products" in data["mermaid"]

    # Test mermaid format query param
    res_m = client.get("/projects/555/erd?format=mermaid")
    assert res_m.status_code == 200
    assert res_m.json()["format"] == "mermaid"
    assert "erDiagram" in res_m.json()["content"]

    app.dependency_overrides.clear()

