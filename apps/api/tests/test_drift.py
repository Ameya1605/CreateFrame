import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from fastapi.testclient import TestClient

import drift
import models
from database import get_db
from main import app, get_user_from_header

client = TestClient(app)


def test_three_way_diff_in_sync():
    snapshot = {
        "spec_json": {
            "database": [{"table_name": "users", "columns": [{"name": "id", "type": "uuid"}]}],
            "endpoints": [{"method": "GET", "route": "/users"}],
        }
    }
    spec = {
        "database": [{"table_name": "users", "columns": [{"name": "id", "type": "uuid"}]}],
        "endpoints": [{"method": "GET", "route": "/users"}],
    }
    scan = {
        "tables": [{"table_name": "users", "fields": [{"name": "id", "type": "uuid"}]}],
        "routes": [{"method": "GET", "route": "/users"}],
    }

    result = drift.three_way_diff(snapshot, spec, scan)
    assert result["summary"]["is_clean"] is True
    assert result["summary"]["drift_count"] == 0
    assert result["summary"]["in_sync_count"] == 2


def test_three_way_diff_spec_only_and_scan_only():
    snapshot = None  # No prior snapshot
    spec = {
        "database": [{"table_name": "products", "columns": [{"name": "id", "type": "uuid"}]}],
        "endpoints": [{"method": "GET", "route": "/products"}],
    }
    scan = {
        "tables": [{"table_name": "customers", "fields": [{"name": "id", "type": "uuid"}]}],
        "routes": [{"method": "POST", "route": "/webhooks"}],
    }

    result = drift.three_way_diff(snapshot, spec, scan)
    assert result["summary"]["is_clean"] is False
    assert result["summary"]["spec_only_count"] == 2  # products table + GET /products
    assert result["summary"]["scan_only_count"] == 2  # customers table + POST /webhooks


def test_three_way_diff_code_deletion_and_conflict():
    snapshot = {
        "spec_json": {
            "database": [
                {
                    "table_name": "orders",
                    "columns": [
                        {"name": "id", "type": "uuid"},
                        {"name": "amount", "type": "float"},
                    ],
                }
            ],
            "endpoints": [{"method": "GET", "route": "/orders"}],
        }
    }
    # Spec added "status" column
    spec = {
        "database": [
            {
                "table_name": "orders",
                "columns": [
                    {"name": "id", "type": "uuid"},
                    {"name": "amount", "type": "float"},
                    {"name": "status", "type": "string"},
                ],
            }
        ],
        "endpoints": [{"method": "GET", "route": "/orders"}],
    }
    # Code added "tax" column instead, and deleted endpoint GET /orders
    scan = {
        "tables": [
            {
                "table_name": "orders",
                "fields": [
                    {"name": "id", "type": "uuid"},
                    {"name": "amount", "type": "float"},
                    {"name": "tax", "type": "float"},
                ],
            }
        ],
        "routes": [],
    }

    result = drift.three_way_diff(snapshot, spec, scan)
    assert result["summary"]["conflicts_count"] == 1
    assert result["summary"]["deleted_in_code_count"] == 1

    # Check conflict item details
    conflict_item = next(i for i in result["items"] if i["status"] == "conflict")
    assert conflict_item["key"] == "orders"
    assert "status" in conflict_item["details"]["columns_only_in_spec"]
    assert "tax" in conflict_item["details"]["columns_only_in_code"]


def test_drift_endpoints():
    test_user = models.User(
        id=888,
        github_id=888,
        username="drift_tester",
        encrypted_github_token="fake_token",
    )
    test_project = models.Project(
        id=777,
        name="drift-app",
        repo_url="https://github.com/myorg/drift-app",
        owner_id=888,
    )

    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.first.return_value = test_project
    mock_db.query.return_value.filter.return_value.order_by.return_value.first.return_value = None

    app.dependency_overrides[get_user_from_header] = lambda: test_user
    app.dependency_overrides[get_db] = lambda: mock_db

    mock_scan = {
        "tables": [{"table_name": "users", "fields": [{"name": "id", "type": "uuid"}]}],
        "routes": [{"method": "GET", "route": "/api/users"}],
        "relations": [],
        "files_scanned": 2,
        "total_files": 2,
    }

    with patch("auth.decrypt_token", return_value="token123"):
        with patch("repo_scanner.scan_repo", new_callable=AsyncMock, return_value=mock_scan):
            res = client.get("/projects/777/drift")
            assert res.status_code == 200
            data = res.json()
            assert "summary" in data
            assert "items" in data
            assert data["project_id"] == 777

    app.dependency_overrides.clear()
