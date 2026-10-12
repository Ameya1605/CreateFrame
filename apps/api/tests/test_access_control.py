import os
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

os.environ["TESTING"] = "1"
os.environ["ENVIRONMENT"] = "test"
os.environ["DATABASE_URL"] = "sqlite:///:memory:"

import models, auth, main
from database import Base, get_db

SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base.metadata.create_all(bind=engine)

def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

main.app.dependency_overrides[get_db] = override_get_db
client = TestClient(main.app)

@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield

def test_access_control_cross_user_isolation():
    db = TestingSessionLocal()
    # Create user 1 and user 2
    u1 = models.User(github_id=101, username="alice", encrypted_github_token="tok1")
    u2 = models.User(github_id=102, username="bob", encrypted_github_token="tok2")
    db.add_all([u1, u2])
    db.commit()
    db.refresh(u1)
    db.refresh(u2)

    # User 1 creates a project
    p1 = models.Project(name="AliceProject", repo_url="https://github.com/alice/p1", owner_id=u1.id)
    db.add(p1)
    db.commit()
    db.refresh(p1)

    # Add items to Alice's project
    feat = models.Feature(project_id=p1.id, name="Auth", status="mvp")
    sch = models.DatabaseSchema(project_id=p1.id, table_name="users", fields=[{"name": "id", "type": "uuid"}])
    ep = models.ApiEndpoint(project_id=p1.id, method="GET", route="/users", request_schema={}, response_schema={})
    comp = models.UIComponent(project_id=p1.id, name="Header", type="component")
    prompt = models.PromptTemplate(project_id=p1.id, name="Architect", template="Hello")
    db.add_all([feat, sch, ep, comp, prompt])
    db.commit()
    db.refresh(feat)
    db.refresh(sch)
    db.refresh(ep)
    db.refresh(comp)
    db.refresh(prompt)

    # Store IDs
    p1_id = p1.id
    feat_id = feat.id
    sch_id = sch.id
    ep_id = ep.id
    comp_id = comp.id
    prompt_id = prompt.id
    u1_id = u1.id
    u2_id = u2.id

    # Generate tokens
    alice_token = auth.create_access_token({"sub": str(u1_id)})
    bob_token = auth.create_access_token({"sub": str(u2_id)})
    db.close()

    alice_headers = {"Authorization": f"Bearer {alice_token}"}
    bob_headers = {"Authorization": f"Bearer {bob_token}"}

    # 1. Alice can list and access her items
    assert client.get(f"/features?project_id={p1_id}", headers=alice_headers).status_code == 200
    assert client.get(f"/schemas?project_id={p1_id}", headers=alice_headers).status_code == 200
    assert client.get(f"/endpoints?project_id={p1_id}", headers=alice_headers).status_code == 200
    assert client.get(f"/ui-components?project_id={p1_id}", headers=alice_headers).status_code == 200
    assert client.get(f"/prompts?project_id={p1_id}", headers=alice_headers).status_code == 200

    # 2. Bob CANNOT list Alice's items (returns 404)
    assert client.get(f"/features?project_id={p1_id}", headers=bob_headers).status_code == 404
    assert client.get(f"/schemas?project_id={p1_id}", headers=bob_headers).status_code == 404
    assert client.get(f"/endpoints?project_id={p1_id}", headers=bob_headers).status_code == 404
    assert client.get(f"/ui-components?project_id={p1_id}", headers=bob_headers).status_code == 404
    assert client.get(f"/prompts?project_id={p1_id}", headers=bob_headers).status_code == 404

    # 3. Bob CANNOT create items in Alice's project (returns 404)
    assert client.post(f"/features?project_id={p1_id}", json={"name": "Hacked", "status": "mvp"}, headers=bob_headers).status_code == 404
    assert client.post(f"/schemas?project_id={p1_id}", json={"table_name": "secrets", "fields": []}, headers=bob_headers).status_code == 404
    assert client.post(f"/endpoints?project_id={p1_id}", json={"method": "GET", "route": "/secrets"}, headers=bob_headers).status_code == 404
    assert client.post(f"/ui-components?project_id={p1_id}", json={"name": "Malicious", "type": "component"}, headers=bob_headers).status_code == 404
    assert client.post(f"/prompts?project_id={p1_id}", json={"name": "Malicious", "template": "pwn"}, headers=bob_headers).status_code == 404

    # 4. Bob CANNOT delete Alice's items (returns 404)
    assert client.delete(f"/features/{feat_id}", headers=bob_headers).status_code == 404
    assert client.delete(f"/schemas/{sch_id}", headers=bob_headers).status_code == 404
    assert client.delete(f"/endpoints/{ep_id}", headers=bob_headers).status_code == 404
    assert client.delete(f"/ui-components/{comp_id}", headers=bob_headers).status_code == 404
    assert client.delete(f"/prompts/{prompt_id}", headers=bob_headers).status_code == 404

    # 5. Alice CAN delete her items
    assert client.delete(f"/features/{feat_id}", headers=alice_headers).status_code == 200
    assert client.delete(f"/schemas/{sch_id}", headers=alice_headers).status_code == 200
    assert client.delete(f"/endpoints/{ep_id}", headers=alice_headers).status_code == 200
    assert client.delete(f"/ui-components/{comp_id}", headers=alice_headers).status_code == 200
    assert client.delete(f"/prompts/{prompt_id}", headers=alice_headers).status_code == 200
