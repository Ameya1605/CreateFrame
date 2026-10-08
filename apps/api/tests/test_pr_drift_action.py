import pytest
import os
import sys
import json
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

import importlib.util
action_check_path = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..", ".github", "actions", "createframe-drift", "check.py")
)
spec = importlib.util.spec_from_file_location("drift_action", action_check_path)
drift_action = importlib.util.module_from_spec(spec)
spec.loader.exec_module(drift_action)
import models
from database import get_db
from main import app, get_user_from_header

client = TestClient(app)


def test_action_scan_local_workspace(tmp_path):
    # Create sample Python file
    py_code = """
from sqlalchemy import Column, Integer, String
from database import Base

class Product(Base):
    __tablename__ = "products"
    id = Column(Integer, primary_key=True)
    name = Column(String)
"""
    file_path = tmp_path / "models.py"
    file_path.write_text(py_code, encoding="utf-8")

    result = drift_action.scan_local_workspace(root_dir=str(tmp_path))
    tables = [t["table_name"] for t in result["tables"]]
    assert "products" in tables


def test_action_run_check_with_drift(tmp_path, monkeypatch):
    spec_data = {
        "database": [{"table_name": "users"}],
        "endpoints": [{"method": "GET", "route": "/users"}],
    }
    spec_file = tmp_path / "spec.json"
    spec_file.write_text(json.dumps(spec_data), encoding="utf-8")

    monkeypatch.setenv("SPEC_PATH", str(spec_file))
    monkeypatch.delenv("GITHUB_EVENT_PATH", raising=False)
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)

    # Mock scan_local_workspace to return a new route not in spec
    mock_scan = {
        "tables": [{"table_name": "users"}],
        "routes": [{"method": "POST", "route": "/payments/webhook"}],
    }

    with patch.object(drift_action, "scan_local_workspace", return_value=mock_scan):
        code = drift_action.run_check()
        assert code == 0


def test_project_settings_and_check_pr():
    test_user = models.User(
        id=666,
        github_id=666,
        username="pr_tester",
        encrypted_github_token="fake_token",
    )
    test_project = models.Project(
        id=555,
        name="pr-project",
        repo_url="https://github.com/myorg/pr-project",
        owner_id=666,
        target_branch="main",
        governance_mode="direct",
    )

    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.first.return_value = test_project
    mock_db.query.return_value.filter.return_value.order_by.return_value.first.return_value = None

    app.dependency_overrides[get_user_from_header] = lambda: test_user
    app.dependency_overrides[get_db] = lambda: mock_db

    # GET settings
    get_res = client.get("/projects/555/settings")
    assert get_res.status_code == 200
    assert get_res.json()["governance_mode"] == "direct"
    assert get_res.json()["target_branch"] == "main"

    # PUT settings
    put_res = client.put(
        "/projects/555/settings",
        json={"target_branch": "develop", "governance_mode": "pr"}
    )
    assert put_res.status_code == 200
    assert test_project.target_branch == "develop"
    assert test_project.governance_mode == "pr"

    # POST check-pr
    with patch("auth.decrypt_token", return_value="tok"):
        with patch("repo_scanner.scan_repo", return_value={"tables": [], "routes": []}):
            check_res = client.post("/projects/555/check-pr")
            assert check_res.status_code == 200
            data = check_res.json()
            assert "comment_markdown" in data
            assert "drift_report" in data

    app.dependency_overrides.clear()


def test_github_webhook_pr_merged():
    test_project = models.Project(
        id=444,
        name="hooked-project",
        repo_url="https://github.com/myorg/hooked-project",
        owner_id=1,
    )

    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.first.return_value = test_project

    app.dependency_overrides[get_db] = lambda: mock_db

    payload = {
        "action": "closed",
        "pull_request": {
            "number": 42,
            "merged": True,
            "head": {"ref": "createframe/proposed-123"}
        },
        "repository": {
            "full_name": "myorg/hooked-project",
            "html_url": "https://github.com/myorg/hooked-project"
        }
    }

    res = client.post("/webhooks/github", json=payload)
    assert res.status_code == 200
    assert res.json()["status"] == "ok"
    assert "PR #42" in res.json()["message"]

    app.dependency_overrides.clear()
