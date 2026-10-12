import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import models
import database
from main import app
from auth import create_access_token
import ai_features


# Setup test database
SQLALCHEMY_DATABASE_URL = "sqlite:///./test_ai_features.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="module", autouse=True)
def setup_test_db():
    models.Base.metadata.drop_all(bind=engine)
    models.Base.metadata.create_all(bind=engine)
    
    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()
            
    app.dependency_overrides[database.get_db] = override_get_db

    db = TestingSessionLocal()
    user = models.User(
        id=99,
        github_id=99999,
        username="ai_tester",
        encrypted_github_token="dummy"
    )
    db.add(user)
    db.commit()

    project = models.Project(
        id=99,
        name="BillingApp",
        repo_url="https://github.com/ai_tester/BillingApp",
        owner_id=99
    )
    db.add(project)
    db.commit()

    # Add sample features, schemas, endpoints
    f1 = models.Feature(project_id=99, name="User Authentication", status="mvp")
    f2 = models.Feature(project_id=99, name="Subscription Billing", status="mvp")
    db.add_all([f1, f2])

    s1 = models.DatabaseSchema(
        project_id=99,
        table_name="users",
        fields=[
            {"name": "id", "type": "integer", "primary_key": True},
            {"name": "email", "type": "string", "unique": True},
            {"name": "password", "type": "string"}  # unhashed for security test
        ],
        relations=[]
    )
    s2 = models.DatabaseSchema(
        project_id=99,
        table_name="billing_invoices",
        fields=[
            {"name": "id", "type": "integer", "primary_key": True},
            {"name": "user_id", "type": "integer", "index": False}, # unindexed FK for scalability test
            {"name": "amount", "type": "integer"}
        ],
        relations=[
            {"from_table": "billing_invoices", "from_field": "user_id", "to_table": "users", "to_field": "id"}
        ]
    )
    db.add_all([s1, s2])

    ep1 = models.ApiEndpoint(
        project_id=99,
        method="POST",
        route="/auth/login",
        linked_table="users",
        auth_required=0, # public
        request_schema={"email": "string", "password": "string"},
        response_schema={"token": "string"}
    )
    ep2 = models.ApiEndpoint(
        project_id=99,
        method="GET",
        route="/billing/invoices",
        linked_table="billing_invoices",
        auth_required=1,
        request_schema={},
        response_schema={"items": "list"}
    )
    db.add_all([ep1, ep2])

    ui1 = models.UIComponent(project_id=99, name="LoginForm", type="component", route="/login")
    ui2 = models.UIComponent(project_id=99, name="BillingDashboard", type="page", route="/billing")
    db.add_all([ui1, ui2])

    db.commit()
    db.close()

    yield

    models.Base.metadata.drop_all(bind=engine)


@pytest.fixture
def auth_headers():
    token = create_access_token({"sub": "99"})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def client():
    return TestClient(app)


def test_impact_analysis_engine():
    spec = {
        "database": [
            {
                "table_name": "users",
                "fields": [{"name": "id", "primary_key": True}, {"name": "email"}],
                "relations": []
            },
            {
                "table_name": "invoices",
                "fields": [{"name": "id"}, {"name": "user_id"}],
                "relations": [{"from_table": "invoices", "from_field": "user_id", "to_table": "users", "to_field": "id"}]
            }
        ],
        "endpoints": [
            {
                "method": "POST",
                "route": "/login",
                "linked_table": "users",
                "request_schema": {"email": "string"}
            }
        ],
        "ui_components": [
            {"name": "UserProfile", "type": "page", "route": "/profile"}
        ],
        "features": [
            {"name": "User Management", "status": "mvp"}
        ]
    }

    res = ai_features.analyze_impact(spec, "what breaks if I rename users.email to email_address?")
    assert res["target"] == "users.email"
    assert res["action"] == "rename"
    assert len(res["breaking_routes"]) >= 1
    assert any("login" in r["identifier"].lower() for r in res["breaking_routes"])
    assert len(res["recommended_actions"]) > 0


def test_impact_analysis_endpoint(client, auth_headers):
    res = client.post(
        "/projects/99/impact-analysis",
        json={"query": "what breaks if I rename users.email to email_address?"},
        headers=auth_headers
    )
    assert res.status_code == 200
    data = res.json()
    assert data["target"] == "users.email"
    assert len(data["breaking_routes"]) >= 1
    assert data["breaking_routes"][0]["identifier"] == "POST /auth/login"


def test_architecture_chat_endpoint(client, auth_headers):
    res = client.post(
        "/projects/99/chat",
        json={"message": "where is billing handled?"},
        headers=auth_headers
    )
    assert res.status_code == 200
    data = res.json()
    assert "answer" in data
    assert len(data["references"]) >= 1
    # Should reference invoices or billing feature/endpoint
    titles = [r["title"].lower() for r in data["references"]]
    assert any("billing" in t or "invoice" in t for t in titles)


def test_feature_build_prompt_endpoint(client, auth_headers):
    # Fetch feature id
    f_res = client.get("/features?project_id=99", headers=auth_headers)
    feat_id = f_res.json()[0]["id"]

    # Test Cursor target
    res_cursor = client.get(f"/projects/99/features/{feat_id}/build-prompt?target=cursor", headers=auth_headers)
    assert res_cursor.status_code == 200
    data_cursor = res_cursor.json()
    assert data_cursor["target"] == "cursor"
    assert "Cursor Composer" in data_cursor["prompt"]
    assert "Architecture Slice" in data_cursor["prompt"]

    # Test Claude Code target and save template
    res_save = client.post(
        f"/projects/99/features/{feat_id}/build-prompt",
        json={"target": "claude_code", "save_as_template": True},
        headers=auth_headers
    )
    assert res_save.status_code == 200
    data_save = res_save.json()
    assert data_save["target"] == "claude_code"
    assert data_save["template_id"] is not None


def test_design_critique_endpoint(client, auth_headers):
    res = client.get("/projects/99/critique", headers=auth_headers)
    assert res.status_code == 200
    data = res.json()
    assert 0 <= data["overall_score"] <= 100
    assert 0 <= data["security_score"] <= 100
    assert 0 <= data["scalability_score"] <= 100
    assert len(data["critiques"]) > 0
    # Should catch unauth endpoint /auth/login and unindexed user_id
    cat_names = [c["category"] for c in data["critiques"]]
    assert "security" in cat_names or "scalability" in cat_names


def test_spec_from_doc_and_apply(client, auth_headers):
    prd_text = """
    # Project Nexus

    ## Features
    - Notifications Center
    - Audit Logging

    ## Data Models
    Users receive notifications. Notifications have title, read boolean, timestamp.
    """
    res = client.post(
        "/projects/99/spec-from-doc",
        json={"content": prd_text, "doc_type": "prd"},
        headers=auth_headers
    )
    assert res.status_code == 200
    extracted = res.json()["extracted"]
    assert len(extracted["features"]) > 0

    # Apply extracted spec to project
    apply_res = client.post(
        "/projects/99/spec-from-doc/apply",
        json={"extracted": extracted},
        headers=auth_headers
    )
    assert apply_res.status_code == 200
    assert apply_res.json()["ok"] is True


def test_spec_from_wireframe_endpoint(client, auth_headers):
    res = client.post(
        "/projects/99/spec-from-wireframe",
        json={"image_base64": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=", "screen_name": "Analytics"},
        headers=auth_headers
    )
    assert res.status_code == 200
    extracted = res.json()["extracted"]
    assert len(extracted["ui_components"]) >= 1
    assert any("Analytics" in c["name"] for c in extracted["ui_components"])


def test_adr_generate_and_list(client, auth_headers):
    # Generate ADR
    res = client.post(
        "/projects/99/adrs/generate",
        json={"title": "Adopt Stripe Payment Infrastructure", "context_note": "Migrating to Stripe billing engine."},
        headers=auth_headers
    )
    assert res.status_code == 200
    data = res.json()
    assert "Adopt Stripe Payment Infrastructure" in data["title"]
    assert "docs/adr/" in data["file_path"]
    assert "# 0001." in data["content"] or "Status" in data["content"]

    # List ADRs
    list_res = client.get("/projects/99/adrs", headers=auth_headers)
    assert list_res.status_code == 200
    adrs = list_res.json()
    assert len(adrs) >= 1
    assert adrs[0]["title"] == data["title"]
