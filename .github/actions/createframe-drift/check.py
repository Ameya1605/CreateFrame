#!/usr/bin/env python3
"""
CreateFrame PR Drift Checker
Scans checked-out repository code, diffs against spec.json, and posts an informative
comment on GitHub Pull Requests.
"""

import os
import sys
import json
import re
import ast
import httpx
from typing import List, Dict, Any, Optional


def is_relevant_file(path: str) -> bool:
    skip_dirs = (
        "node_modules", ".git", "dist", "build", "__pycache__",
        ".next", "venv", ".venv", "migrations", "alembic", ".turbo", ".cache"
    )
    for skip in skip_dirs:
        if f"/{skip}/" in f"/{path}" or path.startswith(f"{skip}/"):
            return False
    relevant_extensions = (".py", ".ts", ".js", ".tsx", ".jsx", ".prisma")
    return any(path.endswith(ext) for ext in relevant_extensions)


def scan_local_workspace(root_dir: str = ".") -> Dict[str, Any]:
    """Scans all relevant files in current workspace for models and routes."""
    files: Dict[str, str] = {}
    for dirpath, _, filenames in os.walk(root_dir):
        for fname in filenames:
            rel = os.path.relpath(os.path.join(dirpath, fname), root_dir).replace("\\", "/")
            if is_relevant_file(rel):
                try:
                    with open(os.path.join(dirpath, fname), "r", encoding="utf-8", errors="ignore") as f:
                        files[rel] = f.read()
                except Exception:
                    pass

    tables = []
    routes = []

    for path, content in files.items():
        # Prisma
        if path.endswith(".prisma"):
            for m in re.finditer(r"model\s+(\w+)\s*\{([^}]+)\}", content):
                tables.append({"table_name": m.group(1)})

        # Python
        elif path.endswith(".py"):
            try:
                tree = ast.parse(content)
                for node in ast.walk(tree):
                    if isinstance(node, ast.ClassDef):
                        # Detect SQLAlchemy / Django / SQLModel
                        has_orm = any(
                            base_id in ("Base", "Model", "db.Model", "SQLModel") or "models." in base_id
                            for base in node.bases
                            if (base_id := getattr(base, "id", None) or getattr(base, "attr", None) or "")
                        )
                        table_name = node.name
                        for item in node.body:
                            if isinstance(item, ast.Assign):
                                for target in item.targets:
                                    if getattr(target, "id", None) == "__tablename__":
                                        if isinstance(item.value, ast.Constant) and isinstance(item.value.value, str):
                                            table_name = item.value.value
                                            has_orm = True
                        if has_orm and node.name not in ("Base", "BaseModel", "TimestampMixin", "DeclarativeBase"):
                            tables.append({"table_name": table_name})

                    elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        for dec in node.decorator_list:
                            if isinstance(dec, ast.Call):
                                func_name = getattr(dec.func, "id", None) or getattr(dec.func, "attr", None) or ""
                                if func_name in ("get", "post", "put", "delete", "patch", "route"):
                                    method = func_name.upper() if func_name != "route" else "GET"
                                    rpath = "/"
                                    if dec.args and isinstance(dec.args[0], ast.Constant) and isinstance(dec.args[0].value, str):
                                        rpath = dec.args[0].value
                                    if not rpath.startswith("/"):
                                        rpath = "/" + rpath
                                    routes.append({"method": method, "route": rpath})
            except Exception:
                pass

        # TypeScript / Express / Next.js
        elif path.endswith((".ts", ".js", ".tsx", ".jsx")):
            # Express routes
            for match in re.finditer(r'(?:router|app)\.(get|post|put|delete|patch)\s*\(\s*["\']([^"\']*)["\']', content, re.IGNORECASE):
                routes.append({"method": match.group(1).upper(), "route": match.group(2) or "/"})

    # Next.js API routes
    for path in files.keys():
        if "/api/" in path and path.endswith(("route.ts", "route.js")):
            route = re.sub(r"^.*?/api", "/api", path)
            route = re.sub(r"/route\.(ts|js)$", "", route)
            route = re.sub(r"\[(\w+)\]", r":\1", route)
            if route:
                routes.append({"method": "GET", "route": route})

    # Deduplicate
    unique_tables = []
    seen_tables = set()
    for t in tables:
        if t["table_name"] not in seen_tables:
            seen_tables.add(t["table_name"])
            unique_tables.append(t)

    unique_routes = []
    seen_routes = set()
    for r in routes:
        key = f"{r['method']}:{r['route']}"
        if key not in seen_routes:
            seen_routes.add(key)
            unique_routes.append(r)

    return {"tables": unique_tables, "routes": unique_routes}


def run_check():
    spec_path = os.environ.get("SPEC_PATH", "spec.json")
    github_token = os.environ.get("GITHUB_TOKEN")
    fail_on_drift = os.environ.get("FAIL_ON_DRIFT", "false").lower() == "true"

    if not os.path.exists(spec_path):
        print(f"⚠️ Spec file '{spec_path}' not found. Skipping drift check.")
        return 0

    try:
        with open(spec_path, "r", encoding="utf-8") as f:
            spec = json.load(f)
    except Exception as e:
        print(f"❌ Could not parse '{spec_path}': {e}")
        return 1

    spec_tables = {t.get("table_name") or t.get("table") for t in (spec.get("database") or spec.get("schemas") or [])}
    spec_routes = {
        f"{(e.get('method') or 'GET').upper()} {e.get('route', '/')}"
        for e in spec.get("endpoints", [])
    }

    scan = scan_local_workspace()
    code_tables = {t["table_name"] for t in scan["tables"]}
    code_routes = {f"{r['method'].upper()} {r['route']}" for r in scan["routes"]}

    # Compute drift
    routes_added_in_code = sorted(code_routes - spec_routes)
    tables_added_in_code = sorted(code_tables - spec_tables)
    routes_missing_in_code = sorted(spec_routes - code_routes)
    tables_missing_in_code = sorted(spec_tables - code_tables)

    has_drift = bool(routes_added_in_code or tables_added_in_code or routes_missing_in_code or tables_missing_in_code)

    print("=================== CREATEFRAME DRIFT REPORT ===================")
    print(f"Routes in Code: {len(code_routes)} | Routes in Spec: {len(spec_routes)}")
    print(f"Tables in Code: {len(code_tables)} | Tables in Spec: {len(spec_tables)}")
    if routes_added_in_code:
        print(f"⚠️ New routes not in spec: {routes_added_in_code}")
    if tables_added_in_code:
        print(f"⚠️ New tables not in spec: {tables_added_in_code}")

    # Build Markdown comment
    if has_drift:
        rows = []
        for r in routes_added_in_code:
            rows.append(f"| `{r}` | Route | ⚠️ Not in `spec.json` |")
        for t in tables_added_in_code:
            rows.append(f"| `{t}` | Table | ⚠️ Not in `spec.json` |")
        for r in routes_missing_in_code:
            rows.append(f"| `{r}` | Route | ℹ️ Planned in spec (not implemented) |")
        for t in tables_missing_in_code:
            rows.append(f"| `{t}` | Table | ℹ️ Planned in spec (not implemented) |")

        table_body = "\n".join(rows)
        comment_body = f"""<!-- createframe-drift-report -->
## 🔍 CreateFrame Drift Report

This PR introduces architecture changes differing from `{spec_path}`:

| Item | Layer | Status |
|------|-------|--------|
{table_body}

> 💡 **Next Steps**: Merge the PR and run CreateFrame Sync to keep `{spec_path}` up to date, or update `{spec_path}` directly in this PR.
"""
    else:
        comment_body = f"""<!-- createframe-drift-report -->
## ✅ CreateFrame Drift Check Passed

All routes and models in this PR match `{spec_path}`. No drift detected!
"""

    # Post or update PR comment if running in GitHub Actions PR context
    event_path = os.environ.get("GITHUB_EVENT_PATH")
    repo = os.environ.get("GITHUB_REPOSITORY")

    if event_path and repo and github_token and os.path.exists(event_path):
        try:
            with open(event_path, "r", encoding="utf-8") as f:
                event = json.load(f)

            pr_number = event.get("pull_request", {}).get("number")
            if pr_number:
                post_github_pr_comment(github_token, repo, pr_number, comment_body)
        except Exception as e:
            print(f"⚠️ Could not post comment to PR: {e}")

    if has_drift and fail_on_drift:
        print("❌ Failing workflow due to fail-on-drift input.")
        return 1

    print("✅ Drift check finished.")
    return 0


def post_github_pr_comment(token: str, repo: str, pr_number: int, body: str):
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github.v3+json",
    }
    url = f"https://api.github.com/repos/{repo}/issues/{pr_number}/comments"

    # Check for existing CreateFrame comment to update instead of creating noise
    with httpx.Client(timeout=30.0) as client:
        list_res = client.get(url, headers=headers)
        existing_id = None
        if list_res.status_code == 200:
            for c in list_res.json():
                if "<!-- createframe-drift-report -->" in c.get("body", ""):
                    existing_id = c["id"]
                    break

        if existing_id:
            patch_url = f"https://api.github.com/repos/{repo}/issues/comments/{existing_id}"
            res = client.patch(patch_url, headers=headers, json={"body": body})
            print(f"Updated existing drift comment #{existing_id} on PR #{pr_number}")
        else:
            res = client.post(url, headers=headers, json={"body": body})
            print(f"Posted new drift comment on PR #{pr_number}")


if __name__ == "__main__":
    sys.exit(run_check())
