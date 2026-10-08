import os
import json
import time
from collections import defaultdict
from fastapi import FastAPI, Depends, HTTPException, status, Header
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any

import models, schemas, database, auth, github_utils, generator, repo_scanner, brain, recommender, spec_v2, drift, erd_generator, ai_features
from database import engine, get_db

models.Base.metadata.create_all(bind=engine)

app = FastAPI()

allowed_origins_raw = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000")
ALLOWED_ORIGINS = [orig.strip() for orig in allowed_origins_raw.split(",") if orig.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class UserRateLimiter:
    def __init__(self, max_requests: int = 15, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests = defaultdict(list)

    def check(self, user_id: int):
        now = time.time()
        cutoff = now - self.window_seconds
        valid_timestamps = [t for t in self.requests[user_id] if t > cutoff]
        if len(valid_timestamps) >= self.max_requests:
            retry_after = int(self.window_seconds - (now - valid_timestamps[0])) + 1
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Rate limit exceeded. Please wait {max(1, retry_after)} seconds before requesting more AI generations.",
                headers={"Retry-After": str(max(1, retry_after))}
            )
        valid_timestamps.append(now)
        self.requests[user_id] = valid_timestamps

ai_rate_limiter = UserRateLimiter(max_requests=15, window_seconds=60)


async def get_user_from_header(authorization: Optional[str] = Header(None), db: Session = Depends(get_db)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Unauthorized")
    token = authorization.split(" ")[1]
    payload = auth.decode_access_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid token")
    user_id = payload.get("sub")
    user = db.query(models.User).filter(models.User.id == int(user_id)).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user

@app.post("/auth/github")
async def github_login(req: schemas.GitHubAuthRequest, db: Session = Depends(get_db)):
    token_data = await github_utils.get_github_access_token(req.code)
    access_token = token_data.get("access_token")
    if not access_token:
        raise HTTPException(status_code=400, detail="Invalid code")
    
    github_user = await github_utils.get_github_user(access_token)
    github_id = github_user.get("id")
    username = github_user.get("login")
    
    user = db.query(models.User).filter(models.User.github_id == github_id).first()
    encrypted_token = auth.encrypt_token(access_token)
    
    if not user:
        user = models.User(
            github_id=github_id,
            username=username,
            encrypted_github_token=encrypted_token
        )
        db.add(user)
    else:
        user.encrypted_github_token = encrypted_token
    
    db.commit()
    db.refresh(user)
    
    jwt_token = auth.create_access_token(data={"sub": str(user.id)})
    return {"access_token": jwt_token, "token_type": "bearer", "username": username}

@app.get("/users/me/llm-config", response_model=schemas.LLMConfigResponse)
async def get_llm_config(user: models.User = Depends(get_user_from_header)):
    return schemas.LLMConfigResponse(
        provider=user.llm_provider or "groq",
        model=user.llm_model,
        has_api_key=bool(user.encrypted_llm_api_key)
    )

@app.put("/users/me/llm-config")
async def update_llm_config(
    req: schemas.LLMConfigUpdate,
    user: models.User = Depends(get_user_from_header),
    db: Session = Depends(get_db)
):
    valid_providers = {"groq", "openai", "anthropic", "ollama"}
    if req.provider.lower() not in valid_providers:
        raise HTTPException(status_code=400, detail=f"Invalid provider. Supported: {', '.join(valid_providers)}")

    db_user = db.query(models.User).filter(models.User.id == user.id).first()
    target_user = db_user if db_user else user

    target_user.llm_provider = req.provider.lower()
    if req.model is not None:
        target_user.llm_model = req.model.strip() if req.model else None

    if req.api_key is not None:
        if req.api_key.strip():
            target_user.encrypted_llm_api_key = auth.encrypt_token(req.api_key.strip())
        else:
            target_user.encrypted_llm_api_key = None

    if not db_user:
        db.add(target_user)
    db.commit()

    return {
        "message": "LLM configuration updated successfully",
        "provider": target_user.llm_provider,
        "model": target_user.llm_model,
        "has_api_key": bool(target_user.encrypted_llm_api_key)
    }

@app.get("/github/repos")
async def get_user_repos(user: models.User = Depends(get_user_from_header)):
    token = auth.decrypt_token(user.encrypted_github_token)
    repos = await github_utils.get_github_repos(token)
    return repos

@app.post("/github/create-repo")
async def create_user_repo(name: str, private: bool = False, user: models.User = Depends(get_user_from_header)):
    token = auth.decrypt_token(user.encrypted_github_token)
    repo = await github_utils.create_github_repo(token, name, private)
    if "html_url" not in repo:
        raise HTTPException(status_code=400, detail=repo.get("message", "Failed to create repo"))
    return repo

@app.get("/projects")
async def list_projects(user: models.User = Depends(get_user_from_header), db: Session = Depends(get_db)):
    return db.query(models.Project).filter(models.Project.owner_id == user.id).all()

@app.post("/projects")
async def create_project(req: schemas.ProjectCreate, user: models.User = Depends(get_user_from_header), db: Session = Depends(get_db)):
    existing = db.query(models.Project).filter(models.Project.owner_id == user.id, models.Project.name == req.name).first()
    if existing:
        raise HTTPException(status_code=400, detail="Project with this name already exists")
    
    project = models.Project(name=req.name, repo_url=req.repo_url, owner_id=user.id)
    db.add(project)
    db.commit()
    db.refresh(project)

    # Automatically scan repository upon creation
    if getattr(user, "encrypted_github_token", None) and req.repo_url:
        try:
            await import_from_repo(schemas.SpecPushRequest(project_id=project.id), user=user, db=db)
        except Exception:
            pass

    return project

@app.delete("/projects/{project_id}")
async def delete_project(project_id: int, user: models.User = Depends(get_user_from_header), db: Session = Depends(get_db)):
    project = db.query(models.Project).filter(models.Project.id == project_id, models.Project.owner_id == user.id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # Delete children explicitly if cascade is not set (SQLAlchemy usually needs it or cascade delete at DB level)
    # Our models use relationships, let's ensure they are handled
    db.delete(project)
    db.commit()
    return {"ok": True}

@app.post("/brainstorm-architecture")
async def brainstorm_architecture(req: schemas.BrainstormRequest, user: models.User = Depends(get_user_from_header)):
    ai_rate_limiter.check(user.id)
    return brain.suggest_initial_spec(req.description, user=user)

def serialize_project_spec(project: models.Project) -> Dict[str, Any]:
    # Extract enums and relations from project
    enums = getattr(project, "database_enums", None) or []
    relations = getattr(project, "database_relations", None) or []
    
    # Collect all table names to infer linked_table if not set
    table_names = [s.table_name for s in project.schemas]

    # Database schemas to Spec v2 tables
    database_tables = []
    for s in project.schemas:
        raw_cols = s.fields or []
        normalized_cols = [spec_v2.normalize_column_dict(c) for c in raw_cols if isinstance(c, dict)]
        if not any(c.get("primary_key") for c in normalized_cols):
            normalized_cols.insert(0, {
                "name": "id",
                "type": "uuid",
                "primary_key": True,
                "nullable": False,
                "unique": False,
                "default": "uuid()",
                "index": False,
            })
        
        tbl_relations = getattr(s, "relations", None) or []
        for r in tbl_relations:
            if r not in relations:
                relations.append(r)

        database_tables.append({
            "table_name": s.table_name,
            "columns": normalized_cols,
            "fields": normalized_cols,  # alias for 100% backward compatibility
            "relations": tbl_relations,
            "code": s.code,
        })

    # Endpoints to Spec v2 endpoints
    endpoints_list = []
    for e in project.endpoints:
        ep_dict = {
            "method": e.method,
            "route": e.route,
            "linked_table": getattr(e, "linked_table", None),
            "auth_required": bool(getattr(e, "auth_required", 1)),
            "auth_type": getattr(e, "auth_type", "bearer") or "bearer",
            "request_schema": e.request_schema or {},
            "response_schema": e.response_schema or {},
            "code": e.code,
        }
        endpoints_list.append(spec_v2.normalize_endpoint_dict(ep_dict, known_tables=table_names))

    return {
        "version": spec_v2.SPEC_VERSION,
        "project": {
            "name": project.name,
            "repo_url": project.repo_url,
            "project_type": project.project_type or "saas",
            "is_ai_enabled": bool(project.is_ai_enabled),
        },
        "structure": "monorepo",
        "apps": ["api", "web"],
        "enums": enums,
        "relations": relations,
        "database": database_tables,
        "endpoints": endpoints_list,
        "ui_components": [
            {
                "name": c.name,
                "type": c.type,
                "route": c.route,
                "code": c.code,
            }
            for c in project.ui_components
        ],
        "features": [
            {
                "id": f.id,
                "name": f.name,
                "status": f.status,
                "description": f.description,
            }
            for f in project.features
        ],
        "prompts": [
            {
                "name": p.name,
                "template": p.template,
            }
            for p in project.prompts
        ],
    }

@app.post("/projects/initialize")
async def initialize_full_project(req: schemas.ProjectCreate, user: models.User = Depends(get_user_from_header), db: Session = Depends(get_db)):
    # Check for existing
    existing = db.query(models.Project).filter(models.Project.owner_id == user.id, models.Project.name == req.name).first()
    if existing:
        raise HTTPException(status_code=400, detail="Project with this name already exists")

    # Create project in DB
    project = models.Project(name=req.name, repo_url=req.repo_url, owner_id=user.id)
    db.add(project)
    db.commit()
    db.refresh(project)

    # Initial Spec Push (Monorepo Boilerplate)
    token = auth.decrypt_token(user.encrypted_github_token)
    spec = serialize_project_spec(project)
    
    # Push basic structure README and spec
    readme_content = f"# {project.name}\n\nBuilt with CreateFrame - AI Architecture First.\n"
    
    api_main = """from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="CreateFrame Generated API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    return {"message": "API is online"}

# Routers will be injected below
"""
    
    requirements = "fastapi\nuvicorn\npydantic\nsqlalchemy\npsycopg2-binary\npython-dotenv\n"
    
    await github_utils.push_spec_to_github(token, project.repo_url, json.dumps(spec, indent=2))
    await github_utils.push_file_to_github(token, project.repo_url, "README.md", readme_content)
    await github_utils.push_file_to_github(token, project.repo_url, "apps/api/main.py", api_main)
    await github_utils.push_file_to_github(token, project.repo_url, "apps/api/requirements.txt", requirements)
    
    return project

@app.post("/generate-code")
async def generate_architectural_code(req: Dict[str, Any], user: models.User = Depends(get_user_from_header)):
    ai_rate_limiter.check(user.id)
    item_type = req.get("item_type", "")
    item_name = req.get("item_name", "")
    spec = req.get("spec", "")
    return {"code": brain.generate_code(item_type, item_name, spec, user=user)}

@app.get("/projects/{project_id}/progress")

async def get_project_progress(project_id: int, user: models.User = Depends(get_user_from_header), db: Session = Depends(get_db)):
    project = db.query(models.Project).filter(models.Project.id == project_id, models.Project.owner_id == user.id).first()
    if not project: raise HTTPException(status_code=404)
    
    token = auth.decrypt_token(user.encrypted_github_token)
    repo_parts = project.repo_url.rstrip("/").split("/")
    owner, repo = repo_parts[-2], repo_parts[-1]
    
    commits = await github_utils.get_github_commits(token, owner, repo)
    feature_names = [f.name for f in project.features]
    
    return brain.summarize_project_progress(commits, feature_names, user=user)

@app.post("/projects/{project_id}/commit")
async def commit_project_to_github(project_id: int, user: models.User = Depends(get_user_from_header), db: Session = Depends(get_db)):
    project = db.query(models.Project).filter(models.Project.id == project_id, models.Project.owner_id == user.id).first()
    if not project: raise HTTPException(status_code=404)
    
    token = auth.decrypt_token(user.encrypted_github_token)
    
    files_to_commit = {}
    spec = serialize_project_spec(project)
    files_to_commit["spec.json"] = json.dumps(spec, indent=2)
    
    # 2. Push Data Layer (Prisma/SQL)
    if project.schemas:
        has_custom_code = any(bool(s.code and s.code.strip()) for s in project.schemas)
        if has_custom_code:
            schema_code = "\n\n".join([s.code for s in project.schemas if s.code and s.code.strip()])
        else:
            schema_code = generator.generate_prisma_schema(spec)
        files_to_commit["packages/database/schema.prisma"] = schema_code

    # 3. Push Server Layer (FastAPI/Express)
    if project.endpoints:
        for entry in project.endpoints:
            if not entry.code: continue
            safe_name = entry.route.strip("/").replace("/", "_").replace("-", "_") or "root"
            files_to_commit[f"apps/api/routes/{safe_name}.py"] = entry.code

    # 4. Push UI Layer (React)
    for comp in project.ui_components:
        if comp.code:
            if comp.type == 'page':
                path = f"apps/web/app/{comp.name.lower().replace(' ', '-')}/page.tsx"
            else:
                path = f"apps/web/components/{comp.name.replace(' ', '')}.tsx"
            files_to_commit[path] = comp.code

    governance_mode = getattr(project, "governance_mode", "direct") or "direct"
    target_branch = getattr(project, "target_branch", "main") or "main"

    if governance_mode == "pr":
        proposed_branch = f"createframe/proposed-{int(time.time())}"
        try:
            await github_utils.create_branch(token, project.repo_url, proposed_branch, from_branch=target_branch)
            commit_res = await github_utils.create_atomic_commit(
                token=token,
                repo_url=project.repo_url,
                files=files_to_commit,
                message=f"feat(spec): proposed architecture updates for {project.name}",
                branch=proposed_branch
            )
            pr_res = await github_utils.create_pull_request(
                token=token,
                repo_url=project.repo_url,
                head=proposed_branch,
                base=target_branch,
                title=f"CreateFrame Proposed Architecture Updates ({project.name})",
                body=f"Automated PR created by CreateFrame with updated spec, schemas, endpoints, and components.\n\n- Proposed Branch: `{proposed_branch}`\n- Base Branch: `{target_branch}`\n- Files Modified: {len(files_to_commit)}"
            )

            snapshot = models.SpecSnapshot(
                project_id=project.id,
                spec_json=spec,
                scan_json={},
                source="pr"
            )
            db.add(snapshot)
            db.commit()

            return {
                "status": "success",
                "governance_mode": "pr",
                "message": f"PR #{pr_res['pr_number']} opened successfully.",
                "pr_number": pr_res["pr_number"],
                "pr_url": pr_res["pr_url"],
                "branch": proposed_branch,
                "commit_sha": commit_res.get("commit_sha")
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to create PR: {str(e)}")

    try:
        commit_res = await github_utils.create_atomic_commit(
            token=token,
            repo_url=project.repo_url,
            files=files_to_commit,
            message=f"feat(spec): architectural sync for {project.name}",
            branch=target_branch
        )
        snapshot = models.SpecSnapshot(
            project_id=project.id,
            spec_json=spec,
            scan_json={},
            source="commit"
        )
        db.add(snapshot)
        db.commit()

        return {
            "status": "success",
            "governance_mode": "direct",
            "message": "All architectural components committed atomically to GitHub.",
            "commit_sha": commit_res.get("commit_sha"),
            "branch": commit_res.get("branch")
        }
    except Exception:
        # Fallback to per-file commits if repository has no commits or Git Data API fails
        await github_utils.push_spec_to_github(token, project.repo_url, files_to_commit["spec.json"])
        for path, content in files_to_commit.items():
            if path == "spec.json": continue
            await github_utils.push_file_to_github(token, project.repo_url, path, content)
        return {"status": "success", "governance_mode": "direct", "message": "All architectural components committed to GitHub (fallback mode)."}

@app.get("/projects/{project_id}/settings", response_model=schemas.ProjectSettingsResponse)
async def get_project_settings(project_id: int, user: models.User = Depends(get_user_from_header), db: Session = Depends(get_db)):
    project = get_user_project(project_id, user.id, db)
    return schemas.ProjectSettingsResponse(
        target_branch=project.target_branch or "main",
        governance_mode=project.governance_mode or "direct"
    )

@app.put("/projects/{project_id}/settings")
async def update_project_settings(
    project_id: int,
    req: schemas.ProjectSettingsUpdate,
    user: models.User = Depends(get_user_from_header),
    db: Session = Depends(get_db)
):
    project = get_user_project(project_id, user.id, db)
    if req.target_branch is not None:
        project.target_branch = req.target_branch.strip()
    if req.governance_mode is not None:
        mode = req.governance_mode.lower().strip()
        if mode not in ("direct", "pr"):
            raise HTTPException(status_code=400, detail="governance_mode must be 'direct' or 'pr'")
        project.governance_mode = mode

    db.commit()
    db.refresh(project)
    return {
        "message": "Project settings updated",
        "target_branch": project.target_branch,
        "governance_mode": project.governance_mode
    }

@app.post("/projects/{project_id}/check-pr")
async def check_pr_drift(
    project_id: int,
    user: models.User = Depends(get_user_from_header),
    db: Session = Depends(get_db)
):
    project = get_user_project(project_id, user.id, db)
    github_token = auth.decrypt_token(user.encrypted_github_token)
    repo_parts = project.repo_url.rstrip("/").split("/")
    repo_full_name = f"{repo_parts[-2]}/{repo_parts[-1]}"

    scan_result = await repo_scanner.scan_repo(github_token, repo_full_name)
    current_spec = serialize_project_spec(project)
    latest_snapshot = db.query(models.SpecSnapshot).filter(
        models.SpecSnapshot.project_id == project.id
    ).order_by(models.SpecSnapshot.id.desc()).first()

    snapshot_data = {
        "spec_json": latest_snapshot.spec_json if latest_snapshot else {},
        "scan_json": latest_snapshot.scan_json if latest_snapshot else {},
    } if latest_snapshot else None

    report = drift.three_way_diff(snapshot=snapshot_data, current_spec=current_spec, current_scan=scan_result)

    drift_items = [item for item in report.get("items", []) if item["status"] in ("scan_only", "conflict", "deleted_in_code")]
    if drift_items:
        lines = [
            "## 🔍 CreateFrame Drift Report",
            "",
            "This PR introduces changes not reflected in `spec.json`:",
            "",
            "| Item | Layer | Status |",
            "|------|-------|--------|",
        ]
        for it in drift_items:
            status_badge = "⚠️ Not in spec" if it["status"] == "scan_only" else ("⚔️ Conflict" if it["status"] == "conflict" else "🗑️ Deleted in code")
            lines.append(f"| `{it['key']}` | {it['layer'].capitalize()} | {status_badge} |")
        lines.append("")
        lines.append("> Run `createframe sync` or sync from CreateFrame dashboard to update `spec.json`.")
        comment_markdown = "\n".join(lines)
    else:
        comment_markdown = "## ✅ CreateFrame Drift Check Passed\n\nAll routes, schemas, and components match `spec.json`."

    return {
        "drift_report": report,
        "comment_markdown": comment_markdown,
        "is_clean": report["summary"]["is_clean"]
    }

@app.post("/webhooks/github")
async def github_webhook(payload: Dict[str, Any], db: Session = Depends(get_db)):
    action = payload.get("action")
    pull_request = payload.get("pull_request")

    if action == "closed" and pull_request and pull_request.get("merged") is True:
        repo_data = payload.get("repository", {})
        project = db.query(models.Project).filter(
            models.Project.repo_url.like(f"%{repo_data.get('full_name', '')}%")
        ).first()

        if project:
            spec = serialize_project_spec(project)
            snapshot = models.SpecSnapshot(
                project_id=project.id,
                spec_json=spec,
                scan_json={},
                source="webhook_merge"
            )
            db.add(snapshot)
            db.commit()
            return {"status": "ok", "message": f"Recorded merge snapshot for PR #{pull_request.get('number')}"}

    return {"status": "ignored"}

@app.post("/projects/{project_id}/toggle-ai")
async def toggle_project_ai(project_id: int, user: models.User = Depends(get_user_from_header), db: Session = Depends(get_db)):
    project = db.query(models.Project).filter(models.Project.id == project_id, models.Project.owner_id == user.id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    project.is_ai_enabled = 1 if project.is_ai_enabled == 0 else 0
    db.commit()
    return {"is_ai_enabled": bool(project.is_ai_enabled)}

def get_user_project(project_id: int, user_id: int, db: Session) -> models.Project:
    project = db.query(models.Project).filter(models.Project.id == project_id, models.Project.owner_id == user_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project

@app.get("/features")
async def list_features(project_id: int, user: models.User = Depends(get_user_from_header), db: Session = Depends(get_db)):
    get_user_project(project_id, user.id, db)
    return db.query(models.Feature).filter(models.Feature.project_id == project_id).all()

@app.post("/features")
async def create_feature(req: schemas.FeatureCreate, project_id: int, user: models.User = Depends(get_user_from_header), db: Session = Depends(get_db)):
    get_user_project(project_id, user.id, db)
    existing = db.query(models.Feature).filter(models.Feature.project_id == project_id, models.Feature.name == req.name).first()
    if existing:
        raise HTTPException(status_code=400, detail="Feature with this name already exists")
        
    feature = models.Feature(project_id=project_id, name=req.name, status=req.status, description=req.description)
    db.add(feature)
    db.commit()
    db.refresh(feature)
    return feature

@app.delete("/features/{feature_id}")
async def delete_feature(feature_id: int, user: models.User = Depends(get_user_from_header), db: Session = Depends(get_db)):
    feature = db.query(models.Feature).join(models.Project).filter(
        models.Feature.id == feature_id,
        models.Project.owner_id == user.id
    ).first()
    if not feature: raise HTTPException(status_code=404, detail="Feature not found")
    db.delete(feature)
    db.commit()
    return {"ok": True}

@app.get("/schemas")
async def list_schemas(project_id: int, user: models.User = Depends(get_user_from_header), db: Session = Depends(get_db)):
    get_user_project(project_id, user.id, db)
    return db.query(models.DatabaseSchema).filter(models.DatabaseSchema.project_id == project_id).all()

@app.post("/schemas")
async def create_schema(req: schemas.SchemaCreate, project_id: int, user: models.User = Depends(get_user_from_header), db: Session = Depends(get_db)):
    get_user_project(project_id, user.id, db)
    existing = db.query(models.DatabaseSchema).filter(models.DatabaseSchema.project_id == project_id, models.DatabaseSchema.table_name == req.table_name).first()
    if existing:
        existing.fields = [f.dict() for f in req.fields]
        if req.relations is not None:
            existing.relations = [r.dict() for r in req.relations]
        if req.code: existing.code = req.code
        db.commit()
        return existing

    db_schema = models.DatabaseSchema(
        project_id=project_id,
        table_name=req.table_name,
        fields=[f.dict() for f in req.fields],
        relations=[r.dict() for r in req.relations] if req.relations else [],
        code=req.code
    )
    db.add(db_schema)
    db.commit()
    db.refresh(db_schema)
    return db_schema

@app.delete("/schemas/{schema_id}")
async def delete_schema(schema_id: int, user: models.User = Depends(get_user_from_header), db: Session = Depends(get_db)):
    schema = db.query(models.DatabaseSchema).join(models.Project).filter(
        models.DatabaseSchema.id == schema_id,
        models.Project.owner_id == user.id
    ).first()
    if not schema: raise HTTPException(status_code=404, detail="Schema not found")
    db.delete(schema)
    db.commit()
    return {"ok": True}

@app.get("/endpoints")
async def list_endpoints(project_id: int, user: models.User = Depends(get_user_from_header), db: Session = Depends(get_db)):
    get_user_project(project_id, user.id, db)
    return db.query(models.ApiEndpoint).filter(models.ApiEndpoint.project_id == project_id).all()

@app.post("/endpoints")
async def create_endpoint(req: schemas.EndpointCreate, project_id: int, user: models.User = Depends(get_user_from_header), db: Session = Depends(get_db)):
    get_user_project(project_id, user.id, db)
    existing = db.query(models.ApiEndpoint).filter(
        models.ApiEndpoint.project_id == project_id, 
        models.ApiEndpoint.method == req.method, 
        models.ApiEndpoint.route == req.route
    ).first()
    if existing:
        existing.request_schema = req.request_schema
        existing.response_schema = req.response_schema
        if req.linked_table is not None: existing.linked_table = req.linked_table
        if req.auth_required is not None: existing.auth_required = req.auth_required
        if req.auth_type is not None: existing.auth_type = req.auth_type
        if req.code: existing.code = req.code
        db.commit()
        return existing

    endpoint = models.ApiEndpoint(
        project_id=project_id,
        method=req.method,
        route=req.route,
        request_schema=req.request_schema,
        response_schema=req.response_schema,
        linked_table=req.linked_table,
        auth_required=req.auth_required if req.auth_required is not None else True,
        auth_type=req.auth_type or "bearer",
        code=req.code
    )
    db.add(endpoint)
    db.commit()
    db.refresh(endpoint)
    return endpoint

@app.delete("/endpoints/{endpoint_id}")
async def delete_endpoint(endpoint_id: int, user: models.User = Depends(get_user_from_header), db: Session = Depends(get_db)):
    endpoint = db.query(models.ApiEndpoint).join(models.Project).filter(
        models.ApiEndpoint.id == endpoint_id,
        models.Project.owner_id == user.id
    ).first()
    if not endpoint: raise HTTPException(status_code=404, detail="Endpoint not found")
    db.delete(endpoint)
    db.commit()
    return {"ok": True}

@app.get("/ui-components")
async def list_ui_components(project_id: int, user: models.User = Depends(get_user_from_header), db: Session = Depends(get_db)):
    get_user_project(project_id, user.id, db)
    return db.query(models.UIComponent).filter(models.UIComponent.project_id == project_id).all()

@app.post("/ui-components")
async def create_ui_component(req: schemas.UIComponentCreate, project_id: int, user: models.User = Depends(get_user_from_header), db: Session = Depends(get_db)):
    get_user_project(project_id, user.id, db)
    existing = db.query(models.UIComponent).filter(models.UIComponent.project_id == project_id, models.UIComponent.name == req.name).first()
    if existing:
        existing.type = req.type
        existing.route = req.route
        if req.code: existing.code = req.code
        db.commit()
        return existing
        
    comp = models.UIComponent(project_id=project_id, name=req.name, type=req.type, route=req.route, code=req.code)
    db.add(comp)
    db.commit()
    db.refresh(comp)
    return comp

@app.delete("/ui-components/{id}")
async def delete_ui_component(id: int, user: models.User = Depends(get_user_from_header), db: Session = Depends(get_db)):
    comp = db.query(models.UIComponent).join(models.Project).filter(
        models.UIComponent.id == id,
        models.Project.owner_id == user.id
    ).first()
    if not comp: raise HTTPException(status_code=404, detail="UI Component not found")
    db.delete(comp)
    db.commit()
    return {"ok": True}

@app.get("/prompts")
async def list_prompts(project_id: int, user: models.User = Depends(get_user_from_header), db: Session = Depends(get_db)):
    get_user_project(project_id, user.id, db)
    return db.query(models.PromptTemplate).filter(models.PromptTemplate.project_id == project_id).all()

@app.post("/prompts")
async def create_prompt(req: schemas.PromptCreate, project_id: int, user: models.User = Depends(get_user_from_header), db: Session = Depends(get_db)):
    get_user_project(project_id, user.id, db)
    prompt = models.PromptTemplate(project_id=project_id, name=req.name, template=req.template)
    db.add(prompt)
    db.commit()
    db.refresh(prompt)
    return prompt

@app.delete("/prompts/{prompt_id}")
async def delete_prompt(prompt_id: int, user: models.User = Depends(get_user_from_header), db: Session = Depends(get_db)):
    prompt = db.query(models.PromptTemplate).join(models.Project).filter(
        models.PromptTemplate.id == prompt_id,
        models.Project.owner_id == user.id
    ).first()
    if not prompt: raise HTTPException(status_code=404, detail="Prompt not found")
    db.delete(prompt)
    db.commit()
    return {"ok": True}

@app.post("/suggestions/{layer}")
async def get_layer_suggestions(layer: str, project_id: int, user: models.User = Depends(get_user_from_header), db: Session = Depends(get_db)):
    project = db.query(models.Project).filter(models.Project.id == project_id, models.Project.owner_id == user.id).first()
    if not project: raise HTTPException(status_code=404)
    context = f"Project: {project.name}. Layer: {layer}."
    items = []
    if layer == "database": items = [{"table": s.table_name} for s in project.schemas]
    elif layer == "api": items = [{"route": e.route, "method": e.method} for e in project.endpoints]
    elif layer == "ui": items = [{"name": c.name, "type": c.type} for c in project.ui_components]
    suggestions = brain.analyze_spec_and_suggest(layer, items, context, user=user)
    return {"suggestions": suggestions}

@app.post("/import-from-repo")
async def import_from_repo(req: schemas.SpecPushRequest, user: models.User = Depends(get_user_from_header), db: Session = Depends(get_db)):
    project = db.query(models.Project).filter(models.Project.id == req.project_id, models.Project.owner_id == user.id).first()
    if not project: raise HTTPException(status_code=404)
    github_token = auth.decrypt_token(user.encrypted_github_token)

    # 1. Attempt to fetch remote spec.json first for true two-way sync
    remote_spec = await github_utils.fetch_spec_from_github(github_token, project.repo_url)
    
    has_spec_content = bool(
        remote_spec and (
            len(remote_spec.get("database", [])) > 0 or
            len(remote_spec.get("endpoints", [])) > 0 or
            len(remote_spec.get("features", [])) > 0
        )
    )

    if has_spec_content:
        # 1. Normalize remote spec to standard Spec v2
        remote_spec = spec_v2.normalize_v1_to_v2(remote_spec)

        # Reconcile enums & relations at project level
        if remote_spec.get("enums"):
            project.database_enums = remote_spec.get("enums")
        if remote_spec.get("relations"):
            project.database_relations = remote_spec.get("relations")

        # Reconcile features
        existing_features = {f.name: f for f in project.features}
        for feat in remote_spec.get("features", []):
            fname = feat.get("name")
            if not fname: continue
            if fname in existing_features:
                existing_features[fname].status = feat.get("status", existing_features[fname].status)
                if feat.get("description"):
                    existing_features[fname].description = feat.get("description")
            else:
                db.add(models.Feature(
                    project_id=project.id,
                    name=fname,
                    status=feat.get("status", "mvp"),
                    description=feat.get("description")
                ))

        # Reconcile database schemas
        existing_schemas = {s.table_name: s for s in project.schemas}
        for sch in remote_spec.get("database", []):
            tname = sch.get("table_name") or sch.get("table")
            if not tname: continue
            raw_cols = sch.get("columns") or sch.get("fields") or []
            rel_list = sch.get("relations", [])
            if tname in existing_schemas:
                if raw_cols:
                    existing_schemas[tname].fields = raw_cols
                if rel_list:
                    existing_schemas[tname].relations = rel_list
                if sch.get("code"):
                    existing_schemas[tname].code = sch.get("code")
            else:
                db.add(models.DatabaseSchema(
                    project_id=project.id,
                    table_name=tname,
                    fields=raw_cols,
                    relations=rel_list,
                    code=sch.get("code")
                ))

        # Reconcile endpoints
        existing_endpoints = {(e.method.upper(), e.route): e for e in project.endpoints}
        for ep in remote_spec.get("endpoints", []):
            m = ep.get("method", "GET").upper()
            r = ep.get("route", "/")
            key = (m, r)
            if key in existing_endpoints:
                if ep.get("request_schema") is not None:
                    existing_endpoints[key].request_schema = ep.get("request_schema")
                if ep.get("response_schema") is not None:
                    existing_endpoints[key].response_schema = ep.get("response_schema")
                if ep.get("linked_table") is not None:
                    existing_endpoints[key].linked_table = ep.get("linked_table")
                if ep.get("auth_required") is not None:
                    existing_endpoints[key].auth_required = ep.get("auth_required")
                if ep.get("auth_type") is not None:
                    existing_endpoints[key].auth_type = ep.get("auth_type")
                if ep.get("code"):
                    existing_endpoints[key].code = ep.get("code")
            else:
                db.add(models.ApiEndpoint(
                    project_id=project.id,
                    method=m,
                    route=r,
                    request_schema=ep.get("request_schema", {}),
                    response_schema=ep.get("response_schema", {}),
                    linked_table=ep.get("linked_table"),
                    auth_required=ep.get("auth_required", True),
                    auth_type=ep.get("auth_type", "bearer"),
                    code=ep.get("code")
                ))

        # Reconcile UI components from remote spec
        existing_components = {c.name.lower(): c for c in project.ui_components}
        for comp in remote_spec.get("ui_components", []):
            cname = comp.get("name")
            if not cname: continue
            if cname.lower() in existing_components:
                if comp.get("type"):
                    existing_components[cname.lower()].type = comp.get("type")
                if comp.get("route"):
                    existing_components[cname.lower()].route = comp.get("route")
                if comp.get("code"):
                    existing_components[cname.lower()].code = comp.get("code")
            else:
                new_c = models.UIComponent(
                    project_id=project.id,
                    name=cname,
                    type=comp.get("type", "component"),
                    route=comp.get("route"),
                    code=comp.get("code")
                )
                db.add(new_c)
                existing_components[cname.lower()] = new_c

        # Scan repository code to discover any UI views, templates (HTML, Jinja, EJS, Blade, etc.), or components
        repo_full_name = project.repo_url
        if repo_full_name.startswith("http"):
            parts = repo_full_name.rstrip("/").split("/")
            repo_full_name = f"{parts[-2]}/{parts[-1]}"

        try:
            scan_res = await repo_scanner.scan_repo(github_token, repo_full_name)
            for comp in scan_res.get("ui_components", []):
                cname = comp.get("name")
                if not cname: continue
                if cname.lower() in existing_components:
                    if comp.get("code") and not existing_components[cname.lower()].code:
                        existing_components[cname.lower()].code = comp.get("code")
                    if comp.get("route") and not existing_components[cname.lower()].route:
                        existing_components[cname.lower()].route = comp.get("route")
                else:
                    new_c = models.UIComponent(
                        project_id=project.id,
                        name=cname,
                        type=comp.get("type", "template"),
                        route=comp.get("route", "/"),
                        code=comp.get("code")
                    )
                    db.add(new_c)
                    existing_components[cname.lower()] = new_c
        except Exception as scan_err:
            print(f"Notice: UI scan from repo encountered: {scan_err}")

        # Reconcile prompts
        existing_prompts = {p.name: p for p in project.prompts}
        for pr in remote_spec.get("prompts", []):
            pname = pr.get("name")
            if not pname: continue
            if pname in existing_prompts:
                if pr.get("template"):
                    existing_prompts[pname].template = pr.get("template")
            else:
                db.add(models.PromptTemplate(
                    project_id=project.id,
                    name=pname,
                    template=pr.get("template", "")
                ))

        db.commit()
        return {
            "message": "Spec synced successfully from repository spec.json and codebase",
            "source": "spec.json",
            "tables_found": len(remote_spec.get("database", [])),
            "routes_found": len(remote_spec.get("endpoints", [])),
            "components_found": len(project.ui_components)
        }

    # 2. Fallback to code scanner if spec.json doesn't exist or is empty
    repo_full_name = project.repo_url
    if repo_full_name.startswith("http"):
        parts = repo_full_name.rstrip("/").split("/")
        repo_full_name = f"{parts[-2]}/{parts[-1]}"

    result = await repo_scanner.scan_repo(github_token, repo_full_name)
    existing_schemas = {s.table_name: s for s in project.schemas}
    for table in result["tables"]:
        tname = table["table_name"]
        if tname in existing_schemas:
            existing_schemas[tname].fields = table["fields"]
            if "relations" in table:
                existing_schemas[tname].relations = table.get("relations", [])
        else:
            db.add(models.DatabaseSchema(
                project_id=project.id,
                table_name=tname,
                fields=table["fields"],
                relations=table.get("relations", [])
            ))

    existing_endpoints = {(e.method.upper(), e.route): e for e in project.endpoints}
    for route in result["routes"]:
        m = route["method"].upper()
        r = route["route"]
        key = (m, r)
        if key not in existing_endpoints:
            db.add(models.ApiEndpoint(project_id=project.id, method=m, route=r, request_schema={}, response_schema={}))

    # 3. Auto-seed starter features if project has no features
    existing_feature_names = {f.name.lower() for f in project.features}
    route_groups = set()
    for route in result.get("routes", []):
        path = [seg for seg in route["route"].strip("/").split("/") if seg and seg != "api"]
        if path:
            group_name = path[0].replace("_", " ").title()
            if group_name and group_name.lower() not in existing_feature_names:
                route_groups.add(group_name)

    for gname in sorted(route_groups):
        db.add(models.Feature(
            project_id=project.id,
            name=f"{gname} Feature",
            status="planned",
            description=f"Auto-discovered feature from repository API routes."
        ))

    if not route_groups:
        for table in result.get("tables", []):
            tname = table["table_name"]
            feat_name = f"{tname.title()} Management"
            if feat_name.lower() not in existing_feature_names:
                db.add(models.Feature(
                    project_id=project.id,
                    name=feat_name,
                    status="planned",
                    description=f"Auto-discovered data management feature for {tname}."
                ))

    # 4. Populate UI Components from code scanner
    existing_ui_names = {u.name.lower(): u for u in project.ui_components}
    for comp in result.get("ui_components", []):
        cname = comp.get("name")
        if not cname:
            continue
        if cname.lower() in existing_ui_names:
            if comp.get("code") and not existing_ui_names[cname.lower()].code:
                existing_ui_names[cname.lower()].code = comp.get("code")
            if comp.get("route"):
                existing_ui_names[cname.lower()].route = comp.get("route")
        else:
            db.add(models.UIComponent(
                project_id=project.id,
                name=cname,
                type=comp.get("type", "page"),
                route=comp.get("route", "/"),
                code=comp.get("code")
            ))

    db.commit()
    return {
        "message": "Repository code scanned and architectural components populated",
        "source": "repo_scanner",
        "tables_found": len(result["tables"]),
        "routes_found": len(result["routes"]),
        "ui_components_found": len(result.get("ui_components", [])),
        "relations_found": len(result.get("relations", [])),
        "features_created": len(route_groups)
    }

@app.post("/push-to-github")
async def push_to_github(req: schemas.SpecPushRequest, user: models.User = Depends(get_user_from_header), db: Session = Depends(get_db)):
    project = db.query(models.Project).filter(models.Project.id == req.project_id, models.Project.owner_id == user.id).first()
    if not project: raise HTTPException(status_code=404)
    spec = serialize_project_spec(project)
    github_token = auth.decrypt_token(user.encrypted_github_token)
    res = await github_utils.push_spec_to_github(github_token, project.repo_url, json.dumps(spec, indent=2))

    snapshot = models.SpecSnapshot(
        project_id=project.id,
        spec_json=spec,
        scan_json={},
        source="push"
    )
    db.add(snapshot)
    db.commit()
    return {"message": "Spec pushed successfully"}

@app.get("/projects/{project_id}/drift")
async def get_project_drift(project_id: int, user: models.User = Depends(get_user_from_header), db: Session = Depends(get_db)):
    project = db.query(models.Project).filter(models.Project.id == project_id, models.Project.owner_id == user.id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    github_token = auth.decrypt_token(user.encrypted_github_token)
    repo_full_name = project.repo_url
    if repo_full_name.startswith("http"):
        parts = repo_full_name.rstrip("/").split("/")
        repo_full_name = f"{parts[-2]}/{parts[-1]}"

    # 1. Fresh AST scan from codebase
    scan_result = await repo_scanner.scan_repo(github_token, repo_full_name)

    # 2. Latest sync snapshot ancestor
    latest_snapshot = db.query(models.SpecSnapshot).filter(
        models.SpecSnapshot.project_id == project.id
    ).order_by(models.SpecSnapshot.id.desc()).first()

    snapshot_data = {
        "spec_json": latest_snapshot.spec_json if latest_snapshot else {},
        "scan_json": latest_snapshot.scan_json if latest_snapshot else {},
    } if latest_snapshot else None

    # 3. Active database spec
    current_spec = serialize_project_spec(project)

    # 4. Compute three-way diff
    report = drift.three_way_diff(
        snapshot=snapshot_data,
        current_spec=current_spec,
        current_scan=scan_result
    )

    report["project_id"] = project.id
    report["snapshot_id"] = latest_snapshot.id if latest_snapshot else None
    report["last_synced_at"] = latest_snapshot.created_at.isoformat() if latest_snapshot and latest_snapshot.created_at else None
    return report

@app.post("/projects/{project_id}/sync")
async def sync_project_drift(
    project_id: int,
    req: schemas.SyncProjectRequest,
    user: models.User = Depends(get_user_from_header),
    db: Session = Depends(get_db)
):
    project = db.query(models.Project).filter(models.Project.id == project_id, models.Project.owner_id == user.id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    github_token = auth.decrypt_token(user.encrypted_github_token)
    repo_full_name = project.repo_url
    if repo_full_name.startswith("http"):
        parts = repo_full_name.rstrip("/").split("/")
        repo_full_name = f"{parts[-2]}/{parts[-1]}"

    scan_result = await repo_scanner.scan_repo(github_token, repo_full_name)
    existing_schemas = {s.table_name: s for s in project.schemas}
    existing_endpoints = {(e.method.upper(), e.route): e for e in project.endpoints}

    scanned_tables_by_name = {t["table_name"]: t for t in scan_result.get("tables", [])}
    scanned_routes_by_key = {f"{r['method'].upper()} {r['route']}": r for r in scan_result.get("routes", [])}

    applied_resolutions = []

    if req.resolutions:
        for res in req.resolutions:
            if res.layer == "table":
                tname = res.key
                if res.action == "accept_code" and tname in scanned_tables_by_name:
                    table_info = scanned_tables_by_name[tname]
                    if tname in existing_schemas:
                        existing_schemas[tname].fields = table_info["fields"]
                        if "relations" in table_info:
                            existing_schemas[tname].relations = table_info.get("relations", [])
                    else:
                        db.add(models.DatabaseSchema(
                            project_id=project.id,
                            table_name=tname,
                            fields=table_info["fields"],
                            relations=table_info.get("relations", [])
                        ))
                    applied_resolutions.append(f"Accepted code table '{tname}'")
                elif res.action == "delete" and tname in existing_schemas:
                    db.delete(existing_schemas[tname])
                    applied_resolutions.append(f"Deleted spec table '{tname}'")

            elif res.layer == "route":
                rkey = res.key
                if res.action == "accept_code" and rkey in scanned_routes_by_key:
                    rinfo = scanned_routes_by_key[rkey]
                    m = rinfo["method"].upper()
                    r = rinfo["route"]
                    if (m, r) not in existing_endpoints:
                        db.add(models.ApiEndpoint(
                            project_id=project.id,
                            method=m,
                            route=r,
                            request_schema={},
                            response_schema={}
                        ))
                    applied_resolutions.append(f"Accepted code route '{rkey}'")
                elif res.action == "delete":
                    parts = rkey.split(" ", 1)
                    if len(parts) == 2:
                        m, r = parts[0].upper(), parts[1]
                        if (m, r) in existing_endpoints:
                            db.delete(existing_endpoints[(m, r)])
                            applied_resolutions.append(f"Deleted spec route '{rkey}'")
    else:
        for tname, table_info in scanned_tables_by_name.items():
            if tname not in existing_schemas:
                db.add(models.DatabaseSchema(
                    project_id=project.id,
                    table_name=tname,
                    fields=table_info["fields"],
                    relations=table_info.get("relations", [])
                ))
                applied_resolutions.append(f"Auto-merged code table '{tname}'")

        for rkey, rinfo in scanned_routes_by_key.items():
            m = rinfo["method"].upper()
            r = rinfo["route"]
            if (m, r) not in existing_endpoints:
                db.add(models.ApiEndpoint(
                    project_id=project.id,
                    method=m,
                    route=r,
                    request_schema={},
                    response_schema={}
                ))
                applied_resolutions.append(f"Auto-merged code route '{rkey}'")

    db.commit()

    fresh_spec = serialize_project_spec(project)
    new_snapshot = models.SpecSnapshot(
        project_id=project.id,
        spec_json=fresh_spec,
        scan_json=scan_result,
        source="sync"
    )
    db.add(new_snapshot)
    db.commit()
    db.refresh(new_snapshot)

    return {
        "status": "success",
        "message": f"Sync completed successfully. {len(applied_resolutions)} items resolved.",
        "applied": applied_resolutions,
        "snapshot_id": new_snapshot.id
    }

@app.post("/generate/prisma")
async def generate_prisma(req: schemas.SpecPushRequest, user: models.User = Depends(get_user_from_header), db: Session = Depends(get_db)):
    project = db.query(models.Project).filter(models.Project.id == req.project_id, models.Project.owner_id == user.id).first()
    if not project: raise HTTPException(status_code=404)
    spec = serialize_project_spec(project)
    code = generator.generate_prisma_schema(spec)
    return {"code": code}

@app.post("/generate/fastapi")
async def generate_fastapi(req: schemas.SpecPushRequest, user: models.User = Depends(get_user_from_header), db: Session = Depends(get_db)):
    project = db.query(models.Project).filter(models.Project.id == req.project_id, models.Project.owner_id == user.id).first()
    if not project: raise HTTPException(status_code=404)
    spec = serialize_project_spec(project)
    code = generator.generate_fastapi_code(spec)
    return {"code": code}

@app.get("/projects/{project_id}/erd")
async def get_project_erd(
    project_id: int,
    format: Optional[str] = None,
    user: models.User = Depends(get_user_from_header),
    db: Session = Depends(get_db)
):
    project = get_user_project(project_id, user.id, db)
    spec = serialize_project_spec(project)

    if format == "mermaid":
        return {"format": "mermaid", "content": erd_generator.generate_mermaid_erd(spec)}
    elif format == "dbml":
        return {"format": "dbml", "content": erd_generator.generate_dbml(spec)}
    elif format == "openapi":
        return {"format": "openapi", "content": erd_generator.generate_openapi_spec(spec)}

    return erd_generator.export_all_formats(spec)

@app.get("/spec/schema")
def get_spec_schema():
    """Returns the formal SpecOS v2 JSON Schema definition."""
    return spec_v2.SPEC_V2_JSON_SCHEMA

@app.post("/spec/validate")
def validate_spec_payload(payload: Dict[str, Any]):
    """Validates an arbitrary spec against SpecOS v2 rules."""
    is_valid, errors = spec_v2.validate_spec_v2(payload)
    return {"valid": is_valid, "errors": errors}

@app.post("/generate/component")
def generate_component_code(req: schemas.GenerateComponentRequest, user: models.User = Depends(get_user_from_header), db: Session = Depends(get_db)):
    project = db.query(models.Project).filter(models.Project.id == req.project_id, models.Project.owner_id == user.id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # Check if AI mode is enabled
    if not project.is_ai_enabled:
        raise HTTPException(status_code=400, detail="AI features are disabled for this project")

    # Build context from project data
    context = f"Project: {project.name}\n"
    # Safely format fields
    tables_desc = []
    for s in project.schemas:
        fields_str = ", ".join([f"{f.get('name', 'unknown')}:{f.get('type', 'unknown')}" for f in s.fields])
        tables_desc.append(f"- {s.table_name}: {fields_str}")
    
    context += "Database Tables:\n" + "\n".join(tables_desc)
    context += "\nAPI Endpoints:\n" + "\n".join([f"- {e.method} {e.route}" for e in project.endpoints])
    
    code = brain.generate_react_component(req.component_name, req.component_type, context, user=user)
    return {"code": code}

# ─── Recommendation Engine Endpoints ──────────────────────────────────────────

@app.get("/projects/{project_id}/recommendations")
async def get_project_recommendations(project_id: int, user: models.User = Depends(get_user_from_header), db: Session = Depends(get_db)):
    project = db.query(models.Project).filter(models.Project.id == project_id, models.Project.owner_id == user.id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # Get dismissed recommendation IDs
    dismissed = db.query(models.DismissedRecommendation).filter(
        models.DismissedRecommendation.project_id == project_id
    ).all()
    dismissed_ids = [d.recommendation_id for d in dismissed]
    
    result = recommender.get_recommendations(
        project=project,
        features=project.features,
        schemas=project.schemas,
        endpoints=project.endpoints,
        ui_components=project.ui_components,
        dismissed_ids=dismissed_ids,
    )
    
    # Auto-update project_type if newly classified
    detected_type = result.get("project_type", "unknown")
    if detected_type != "unknown" and project.project_type != detected_type:
        project.project_type = detected_type
        db.commit()
    
    return result


@app.post("/projects/{project_id}/recommendations/{rec_id}/apply")
async def apply_recommendation(project_id: int, rec_id: str, user: models.User = Depends(get_user_from_header), db: Session = Depends(get_db)):
    project = db.query(models.Project).filter(models.Project.id == project_id, models.Project.owner_id == user.id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # Get the full recommendation to find its action
    dismissed = db.query(models.DismissedRecommendation).filter(
        models.DismissedRecommendation.project_id == project_id
    ).all()
    dismissed_ids = [d.recommendation_id for d in dismissed]
    
    result = recommender.get_recommendations(
        project=project,
        features=project.features,
        schemas=project.schemas,
        endpoints=project.endpoints,
        ui_components=project.ui_components,
        dismissed_ids=dismissed_ids,
    )
    
    rec = next((r for r in result.get("all", []) if r["id"] == rec_id), None)
    if not rec:
        raise HTTPException(status_code=404, detail="Recommendation not found or already dismissed")
    
    action = rec.get("action", {})
    action_type = action.get("type", "")
    payload = action.get("payload", {})
    
    try:
        if action_type == "add_endpoint":
            endpoint = models.ApiEndpoint(
                project_id=project_id,
                method=payload.get("method", "GET"),
                route=payload.get("route", "/"),
                request_schema=payload.get("request_schema", {}),
                response_schema=payload.get("response_schema", {}),
            )
            db.add(endpoint)
        elif action_type == "add_schema":
            schema = models.DatabaseSchema(
                project_id=project_id,
                table_name=payload.get("table_name", "unnamed"),
                fields=payload.get("fields", []),
            )
            db.add(schema)
        elif action_type == "add_fields":
            table_name = payload.get("table_name")
            new_fields = payload.get("fields", [])
            existing = db.query(models.DatabaseSchema).filter(
                models.DatabaseSchema.project_id == project_id,
                models.DatabaseSchema.table_name == table_name
            ).first()
            if existing:
                current_fields = existing.fields or []
                existing_names = {f.get("name") for f in current_fields if isinstance(f, dict)}
                for nf in new_fields:
                    if nf.get("name") not in existing_names:
                        current_fields.append(nf)
                existing.fields = current_fields
        elif action_type == "add_feature":
            feature = models.Feature(
                project_id=project_id,
                name=payload.get("name", "Unnamed"),
                status=payload.get("status", "planned"),
            )
            db.add(feature)
        elif action_type == "add_ui_component":
            comp = models.UIComponent(
                project_id=project_id,
                name=payload.get("name", "Unnamed"),
                type=payload.get("type", "component"),
            )
            db.add(comp)
        elif action_type in ("navigate", "info"):
            pass  # UI-only actions, no DB change needed
        else:
            raise HTTPException(status_code=400, detail=f"Unknown action type: {action_type}")
        
        db.commit()
        return {"ok": True, "action_type": action_type, "applied": rec["title"]}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to apply: {str(e)}")


@app.post("/projects/{project_id}/recommendations/{rec_id}/dismiss")
async def dismiss_recommendation(project_id: int, rec_id: str, user: models.User = Depends(get_user_from_header), db: Session = Depends(get_db)):
    project = db.query(models.Project).filter(models.Project.id == project_id, models.Project.owner_id == user.id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    existing = db.query(models.DismissedRecommendation).filter(
        models.DismissedRecommendation.project_id == project_id,
        models.DismissedRecommendation.recommendation_id == rec_id
    ).first()
    
    if not existing:
        dismissed = models.DismissedRecommendation(
            project_id=project_id,
            recommendation_id=rec_id,
        )
        db.add(dismissed)
        db.commit()
    
    return {"ok": True, "dismissed": rec_id}


@app.get("/recommendations/field-hints")
async def get_field_hints(table_name: str, user: models.User = Depends(get_user_from_header)):
    hints = recommender.get_field_hints(table_name)
    return {"table_name": table_name, "suggested_fields": hints}


# ─── Smarter AI Endpoints ──────────────────────────────────────────────────────

@app.post("/projects/{project_id}/impact-analysis", response_model=schemas.ImpactAnalysisResponse)
async def impact_analysis_endpoint(
    project_id: int,
    req: schemas.ImpactAnalysisRequest,
    user: models.User = Depends(get_user_from_header),
    db: Session = Depends(get_db)
):
    project = db.query(models.Project).filter(models.Project.id == project_id, models.Project.owner_id == user.id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    spec = serialize_project_spec(project)
    result = ai_features.analyze_impact(
        spec=spec,
        query=req.query,
        target_type=req.target_type,
        table=req.table,
        field=req.field,
        action=req.action,
        new_name=req.new_name,
        user=user
    )
    return result


@app.post("/projects/{project_id}/chat", response_model=schemas.ArchitectureChatResponse)
async def architecture_chat_endpoint(
    project_id: int,
    req: schemas.ArchitectureChatRequest,
    user: models.User = Depends(get_user_from_header),
    db: Session = Depends(get_db)
):
    project = db.query(models.Project).filter(models.Project.id == project_id, models.Project.owner_id == user.id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    spec = serialize_project_spec(project)
    latest_snapshot = db.query(models.SpecSnapshot).filter(
        models.SpecSnapshot.project_id == project_id
    ).order_by(models.SpecSnapshot.id.desc()).first()
    scan_data = latest_snapshot.scan_json if latest_snapshot else None

    github_token = None
    if getattr(user, "encrypted_github_token", None):
        try:
            github_token = auth.decrypt_token(user.encrypted_github_token)
        except Exception:
            github_token = None
    result = await ai_features.chat_with_architecture(
        spec=spec,
        scan_data=scan_data,
        message=req.message,
        history=[h.dict() for h in (req.history or [])],
        user=user,
        project=project,
        github_token=github_token
    )
    return result


@app.get("/projects/{project_id}/features/{feature_id}/build-prompt", response_model=schemas.BuildPromptResponse)
async def get_feature_build_prompt(
    project_id: int,
    feature_id: int,
    target: str = "cursor",
    user: models.User = Depends(get_user_from_header),
    db: Session = Depends(get_db)
):
    project = db.query(models.Project).filter(models.Project.id == project_id, models.Project.owner_id == user.id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    feature = db.query(models.Feature).filter(models.Feature.id == feature_id, models.Feature.project_id == project_id).first()
    if not feature:
        raise HTTPException(status_code=404, detail="Feature not found")

    spec = serialize_project_spec(project)
    result = ai_features.generate_feature_build_prompt(spec, feature_id, target=target, user=user)

    # Check if a custom template is stored
    tmpl_name = f"{feature.name} [{target}]"
    existing_tmpl = db.query(models.PromptTemplate).filter(
        models.PromptTemplate.project_id == project_id,
        models.PromptTemplate.name == tmpl_name
    ).first()
    if existing_tmpl:
        result["prompt"] = existing_tmpl.template
        result["template_id"] = existing_tmpl.id

    return result


@app.post("/projects/{project_id}/features/{feature_id}/build-prompt", response_model=schemas.BuildPromptResponse)
async def save_or_generate_feature_build_prompt(
    project_id: int,
    feature_id: int,
    req: schemas.BuildPromptRequest,
    user: models.User = Depends(get_user_from_header),
    db: Session = Depends(get_db)
):
    project = db.query(models.Project).filter(models.Project.id == project_id, models.Project.owner_id == user.id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    feature = db.query(models.Feature).filter(models.Feature.id == feature_id, models.Feature.project_id == project_id).first()
    if not feature:
        raise HTTPException(status_code=404, detail="Feature not found")

    spec = serialize_project_spec(project)
    target = req.target or "cursor"
    result = ai_features.generate_feature_build_prompt(spec, feature_id, target=target, user=user)

    if req.save_as_template:
        tmpl_name = f"{feature.name} [{target}]"
        existing = db.query(models.PromptTemplate).filter(
            models.PromptTemplate.project_id == project_id,
            models.PromptTemplate.name == tmpl_name
        ).first()
        if existing:
            existing.template = result["prompt"]
            db.commit()
            result["template_id"] = existing.id
        else:
            new_tmpl = models.PromptTemplate(
                project_id=project_id,
                name=tmpl_name,
                template=result["prompt"]
            )
            db.add(new_tmpl)
            db.commit()
            db.refresh(new_tmpl)
            result["template_id"] = new_tmpl.id

    return result


@app.get("/projects/{project_id}/critique", response_model=schemas.DesignCritiqueResponse)
async def get_design_critique(
    project_id: int,
    user: models.User = Depends(get_user_from_header),
    db: Session = Depends(get_db)
):
    project = db.query(models.Project).filter(models.Project.id == project_id, models.Project.owner_id == user.id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    spec = serialize_project_spec(project)
    result = ai_features.critique_architecture(spec, user=user)
    return result


@app.post("/projects/{project_id}/spec-from-doc", response_model=schemas.SpecFromDocResponse)
async def spec_from_doc_endpoint(
    project_id: int,
    req: schemas.SpecFromDocRequest,
    user: models.User = Depends(get_user_from_header),
    db: Session = Depends(get_db)
):
    project = db.query(models.Project).filter(models.Project.id == project_id, models.Project.owner_id == user.id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    result = ai_features.extract_spec_from_prd(req.content, user=user)
    return result


@app.post("/projects/{project_id}/spec-from-wireframe", response_model=schemas.SpecFromDocResponse)
async def spec_from_wireframe_endpoint(
    project_id: int,
    req: schemas.SpecFromWireframeRequest,
    user: models.User = Depends(get_user_from_header),
    db: Session = Depends(get_db)
):
    project = db.query(models.Project).filter(models.Project.id == project_id, models.Project.owner_id == user.id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    result = ai_features.extract_spec_from_wireframe(
        image_base64=req.image_base64,
        screen_name=req.screen_name or "Screen",
        mime_type=req.mime_type or "image/png",
        user=user
    )
    return result


@app.post("/projects/{project_id}/spec-from-doc/apply")
async def apply_extracted_spec(
    project_id: int,
    req: schemas.ApplyExtractedSpecRequest,
    user: models.User = Depends(get_user_from_header),
    db: Session = Depends(get_db)
):
    project = db.query(models.Project).filter(models.Project.id == project_id, models.Project.owner_id == user.id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    applied_counts = {"features": 0, "schemas": 0, "endpoints": 0, "ui_components": 0}

    # Non-destructive merge of features
    existing_feat_names = {f.name.lower() for f in project.features}
    for f in req.extracted.features:
        name = f.get("name", "").strip()
        if name and name.lower() not in existing_feat_names:
            db.add(models.Feature(project_id=project_id, name=name, status=f.get("status", "mvp"), description=f.get("description")))
            existing_feat_names.add(name.lower())
            applied_counts["features"] += 1

    # Non-destructive merge of schemas
    existing_schema_names = {s.table_name.lower() for s in project.schemas}
    for s in req.extracted.schemas:
        tname = s.get("table_name", "").strip()
        if tname and tname.lower() not in existing_schema_names:
            db.add(models.DatabaseSchema(
                project_id=project_id,
                table_name=tname,
                fields=s.get("fields", []),
                relations=s.get("relations", [])
            ))
            existing_schema_names.add(tname.lower())
            applied_counts["schemas"] += 1

    # Non-destructive merge of endpoints
    existing_ep_keys = {f"{e.method}:{e.route}" for e in project.endpoints}
    for e in req.extracted.endpoints:
        key = f"{e.get('method')}:{e.get('route')}"
        if key not in existing_ep_keys:
            db.add(models.ApiEndpoint(
                project_id=project_id,
                method=e.get("method", "GET"),
                route=e.get("route", "/"),
                linked_table=e.get("linked_table"),
                auth_required=1 if e.get("auth_required", True) else 0,
                request_schema=e.get("request_schema", {}),
                response_schema=e.get("response_schema", {})
            ))
            existing_ep_keys.add(key)
            applied_counts["endpoints"] += 1

    # Non-destructive merge of ui components
    existing_ui_names = {u.name.lower() for u in project.ui_components}
    for u in req.extracted.ui_components:
        uname = u.get("name", "").strip()
        if uname and uname.lower() not in existing_ui_names:
            db.add(models.UIComponent(
                project_id=project_id,
                name=uname,
                type=u.get("type", "page"),
                route=u.get("route")
            ))
            existing_ui_names.add(uname.lower())
            applied_counts["ui_components"] += 1

    db.commit()
    return {"ok": True, "applied": applied_counts}


@app.get("/projects/{project_id}/adrs", response_model=List[schemas.ADRResponse])
async def list_project_adrs(
    project_id: int,
    user: models.User = Depends(get_user_from_header),
    db: Session = Depends(get_db)
):
    project = db.query(models.Project).filter(models.Project.id == project_id, models.Project.owner_id == user.id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    adrs = db.query(models.DecisionRecord).filter(
        models.DecisionRecord.project_id == project_id
    ).order_by(models.DecisionRecord.id.desc()).all()

    return [
        schemas.ADRResponse(
            id=a.id,
            title=a.title,
            status=a.status,
            file_path=a.file_path,
            content=a.content,
            committed=bool(a.committed),
            created_at=a.created_at.isoformat() if a.created_at else None
        )
        for a in adrs
    ]


@app.post("/projects/{project_id}/adrs/generate", response_model=schemas.ADRResponse)
async def generate_project_adr(
    project_id: int,
    req: schemas.ADRGenerateRequest,
    user: models.User = Depends(get_user_from_header),
    db: Session = Depends(get_db)
):
    project = db.query(models.Project).filter(models.Project.id == project_id, models.Project.owner_id == user.id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    current_spec = serialize_project_spec(project)
    snapshots = db.query(models.SpecSnapshot).filter(
        models.SpecSnapshot.project_id == project_id
    ).order_by(models.SpecSnapshot.id.desc()).limit(2).all()

    prev_spec = snapshots[1].spec_json if len(snapshots) > 1 else (snapshots[0].spec_json if snapshots else None)
    adr_count = db.query(models.DecisionRecord).filter(models.DecisionRecord.project_id == project_id).count()

    generated = ai_features.generate_adr(
        current_spec=current_spec,
        previous_spec=prev_spec,
        title=req.title,
        context_note=req.context_note,
        adr_number=adr_count + 1,
        user=user
    )

    record = models.DecisionRecord(
        project_id=project_id,
        title=generated["title"],
        status=generated["status"],
        content=generated["content"],
        file_path=generated["file_path"],
        committed=0
    )
    db.add(record)
    db.commit()
    db.refresh(record)

    return schemas.ADRResponse(
        id=record.id,
        title=record.title,
        status=record.status,
        file_path=record.file_path,
        content=record.content,
        committed=bool(record.committed),
        created_at=record.created_at.isoformat() if record.created_at else None
    )


@app.post("/projects/{project_id}/adrs/commit")
async def commit_project_adr(
    project_id: int,
    req: schemas.ADRCommitRequest,
    user: models.User = Depends(get_user_from_header),
    db: Session = Depends(get_db)
):
    project = db.query(models.Project).filter(models.Project.id == project_id, models.Project.owner_id == user.id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    adr = db.query(models.DecisionRecord).filter(
        models.DecisionRecord.id == req.adr_id,
        models.DecisionRecord.project_id == project_id
    ).first()
    if not adr:
        raise HTTPException(status_code=404, detail="Decision record not found")

    token = auth.decrypt_token(user.encrypted_github_token)
    repo_parts = project.repo_url.replace("https://github.com/", "").strip("/").split("/")
    if len(repo_parts) < 2:
        raise HTTPException(status_code=400, detail="Invalid repository URL")
    owner, repo = repo_parts[0], repo_parts[1]

    branch = project.target_branch or "main"
    commit_res = await github_utils.create_atomic_commit(
        token=token,
        owner=owner,
        repo=repo,
        branch=branch,
        files_to_commit=[{
            "path": adr.file_path,
            "content": adr.content
        }],
        commit_message=f"docs(adr): record architecture decision {adr.title}"
    )

    adr.committed = 1
    db.commit()

    return {
        "ok": True,
        "adr_id": adr.id,
        "file_path": adr.file_path,
        "commit": commit_res
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
