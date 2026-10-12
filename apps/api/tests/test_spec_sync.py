import pytest
import models
import main

def test_serialize_project_spec_canonical_shape():
    p = models.Project(
        id=1,
        name="TestApp",
        repo_url="https://github.com/org/testapp",
        owner_id=1,
        is_ai_enabled=1,
        project_type="saas"
    )
    p.features = [models.Feature(name="Login", status="mvp", description="GitHub OAuth")]
    p.schemas = [models.DatabaseSchema(table_name="users", fields=[{"name": "id", "type": "uuid"}], code="// prisma code")]
    p.endpoints = [models.ApiEndpoint(method="GET", route="/users", request_schema={}, response_schema={"id": "string"}, code="// fastapi code")]
    p.ui_components = [models.UIComponent(name="Navbar", type="component", route="/", code="// react code")]
    p.prompts = [models.PromptTemplate(name="Prompt1", template="Hello {name}")]

    spec = main.serialize_project_spec(p)
    
    # Validate canonical structure
    assert spec["project"]["name"] == "TestApp"
    assert spec["structure"] == "monorepo"
    assert "api" in spec["apps"] and "web" in spec["apps"]
    assert len(spec["features"]) == 1
    assert spec["features"][0]["name"] == "Login"
    assert len(spec["database"]) == 1
    assert spec["database"][0]["table_name"] == "users"
    assert len(spec["endpoints"]) == 1
    assert spec["endpoints"][0]["route"] == "/users"
    assert spec["endpoints"][0]["response_schema"] == {"id": "string"}
    assert len(spec["ui_components"]) == 1
    assert spec["ui_components"][0]["name"] == "Navbar"
    assert len(spec["prompts"]) == 1
    assert spec["prompts"][0]["name"] == "Prompt1"
