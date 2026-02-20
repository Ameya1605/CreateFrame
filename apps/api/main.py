import json
from fastapi import FastAPI, Depends, HTTPException, status, Header
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any

import models, schemas, database, auth, github_utils, generator, repo_scanner, brain
from database import engine, get_db

models.Base.metadata.create_all(bind=engine)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
    return brain.suggest_initial_spec(req.description)

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
    spec = {
        "project": {"name": project.name, "repo_url": project.repo_url}, 
        "structure": "monorepo",
        "apps": ["api", "web"],
        "database": [], 
        "endpoints": [], 
        "features": []
    }
    
    # Push basic structure README and spec
    readme_content = f"# {project.name}\n\nBuilt with SpecOS - AI Architecture First.\n\n## Structure\n- `apps/api`: FastAPI Backend\n- `apps/web`: Next.js Frontend\n"
    await github_utils.push_spec_to_github(token, project.repo_url, json.dumps(spec, indent=2))
    await github_utils.push_file_to_github(token, project.repo_url, "README.md", readme_content)
    
    return project

@app.post("/generate-code")
async def generate_architectural_code(req: Dict[str, Any], user: models.User = Depends(get_user_from_header)):
    item_type = req.get("item_type", "")
    item_name = req.get("item_name", "")
    spec = req.get("spec", "")
    return {"code": brain.generate_code(item_type, item_name, spec)}

@app.get("/projects/{project_id}/progress")

async def get_project_progress(project_id: int, user: models.User = Depends(get_user_from_header), db: Session = Depends(get_db)):
    project = db.query(models.Project).filter(models.Project.id == project_id, models.Project.owner_id == user.id).first()
    if not project: raise HTTPException(status_code=404)
    
    token = auth.decrypt_token(user.encrypted_github_token)
    repo_parts = project.repo_url.rstrip("/").split("/")
    owner, repo = repo_parts[-2], repo_parts[-1]
    
    commits = await github_utils.get_github_commits(token, owner, repo)
    feature_names = [f.name for f in project.features]
    
    return brain.summarize_project_progress(commits, feature_names)

@app.post("/projects/{project_id}/commit")
async def commit_project_to_github(project_id: int, user: models.User = Depends(get_user_from_header), db: Session = Depends(get_db)):
    project = db.query(models.Project).filter(models.Project.id == project_id, models.Project.owner_id == user.id).first()
    if not project: raise HTTPException(status_code=404)
    
    token = auth.decrypt_token(user.encrypted_github_token)
    
    # 1. Update spec.json
    spec = {
        "project": {"name": project.name, "repo_url": project.repo_url},
        "features": [{"name": f.name, "status": f.status} for f in project.features],
        "database": [{"table": s.table_name, "fields": s.fields} for s in project.schemas],
        "endpoints": [{"method": e.method, "route": e.route} for e in project.endpoints],
    }
    await github_utils.push_spec_to_github(token, project.repo_url, json.dumps(spec, indent=2))
    
    # 2. Push Data Layer (Prisma/SQL)
    if project.schemas:
        schema_code = "\n\n".join([s.code or f"// Table {s.table_name}" for s in project.schemas])
        msg = brain.generate_commit_message("schemas", "Database Schema")
        await github_utils.push_file_to_github(token, project.repo_url, "packages/database/schema.prisma", schema_code, msg)

    # 3. Push Server Layer (FastAPI/Express)
    if project.endpoints:
        api_code = "from fastapi import APIRouter\n\nrouter = APIRouter()\n\n" + "\n\n".join([e.code or f"# Route {e.method} {e.route}" for e in project.endpoints])
        msg = brain.generate_commit_message("endpoints", "API Endpoints")
        await github_utils.push_file_to_github(token, project.repo_url, "apps/api/main.py", api_code, msg)

    # 4. Push UI Layer (React)
    for comp in project.ui_components:
        if comp.code:
            path = f"apps/web/app/{comp.name.lower().replace(' ', '-')}/page.tsx" if comp.type == 'page' else f"apps/web/components/{comp.name.replace(' ', '')}.tsx"
            msg = brain.generate_commit_message("ui-components", comp.name)
            await github_utils.push_file_to_github(token, project.repo_url, path, comp.code, msg)

    return {"status": "success", "message": "All architectural components committed to GitHub."}

@app.post("/projects/{project_id}/toggle-ai")
async def toggle_project_ai(project_id: int, user: models.User = Depends(get_user_from_header), db: Session = Depends(get_db)):
    project = db.query(models.Project).filter(models.Project.id == project_id, models.Project.owner_id == user.id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    project.is_ai_enabled = 1 if project.is_ai_enabled == 0 else 0
    db.commit()
    return {"is_ai_enabled": bool(project.is_ai_enabled)}

@app.get("/features")
async def list_features(project_id: int, user: models.User = Depends(get_user_from_header), db: Session = Depends(get_db)):
    return db.query(models.Feature).filter(models.Feature.project_id == project_id).all()

@app.post("/features")
async def create_feature(req: schemas.FeatureCreate, project_id: int, user: models.User = Depends(get_user_from_header), db: Session = Depends(get_db)):
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
    feature = db.query(models.Feature).filter(models.Feature.id == feature_id).first()
    if not feature: raise HTTPException(status_code=404)
    db.delete(feature)
    db.commit()
    return {"ok": True}

@app.get("/schemas")
async def list_schemas(project_id: int, user: models.User = Depends(get_user_from_header), db: Session = Depends(get_db)):
    return db.query(models.DatabaseSchema).filter(models.DatabaseSchema.project_id == project_id).all()

@app.post("/schemas")
async def create_schema(req: schemas.SchemaCreate, project_id: int, user: models.User = Depends(get_user_from_header), db: Session = Depends(get_db)):
    existing = db.query(models.DatabaseSchema).filter(models.DatabaseSchema.project_id == project_id, models.DatabaseSchema.table_name == req.table_name).first()
    if existing:
        existing.fields = [f.dict() for f in req.fields]
        if req.code: existing.code = req.code
        db.commit()
        return existing

    db_schema = models.DatabaseSchema(
        project_id=project_id,
        table_name=req.table_name,
        fields=[f.dict() for f in req.fields],
        code=req.code
    )
    db.add(db_schema)
    db.commit()
    db.refresh(db_schema)
    return db_schema

@app.delete("/schemas/{schema_id}")
async def delete_schema(schema_id: int, user: models.User = Depends(get_user_from_header), db: Session = Depends(get_db)):
    schema = db.query(models.DatabaseSchema).filter(models.DatabaseSchema.id == schema_id).first()
    if not schema: raise HTTPException(status_code=404)
    db.delete(schema)
    db.commit()
    return {"ok": True}

@app.get("/endpoints")
async def list_endpoints(project_id: int, user: models.User = Depends(get_user_from_header), db: Session = Depends(get_db)):
    return db.query(models.ApiEndpoint).filter(models.ApiEndpoint.project_id == project_id).all()

@app.post("/endpoints")
async def create_endpoint(req: schemas.EndpointCreate, project_id: int, user: models.User = Depends(get_user_from_header), db: Session = Depends(get_db)):
    existing = db.query(models.ApiEndpoint).filter(
        models.ApiEndpoint.project_id == project_id, 
        models.ApiEndpoint.method == req.method, 
        models.ApiEndpoint.route == req.route
    ).first()
    if existing:
        existing.request_schema = req.request_schema
        existing.response_schema = req.response_schema
        if req.code: existing.code = req.code
        db.commit()
        return existing

    endpoint = models.ApiEndpoint(
        project_id=project_id,
        method=req.method,
        route=req.route,
        request_schema=req.request_schema,
        response_schema=req.response_schema,
        code=req.code
    )
    db.add(endpoint)
    db.commit()
    db.refresh(endpoint)
    return endpoint

@app.delete("/endpoints/{endpoint_id}")
async def delete_endpoint(endpoint_id: int, user: models.User = Depends(get_user_from_header), db: Session = Depends(get_db)):
    endpoint = db.query(models.ApiEndpoint).filter(models.ApiEndpoint.id == endpoint_id).first()
    if not endpoint: raise HTTPException(status_code=404)
    db.delete(endpoint)
    db.commit()
    return {"ok": True}

@app.get("/ui-components")
async def list_ui_components(project_id: int, user: models.User = Depends(get_user_from_header), db: Session = Depends(get_db)):
    return db.query(models.UIComponent).filter(models.UIComponent.project_id == project_id).all()

@app.post("/ui-components")
async def create_ui_component(req: schemas.UIComponentCreate, project_id: int, user: models.User = Depends(get_user_from_header), db: Session = Depends(get_db)):
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
    comp = db.query(models.UIComponent).filter(models.UIComponent.id == id).first()
    if not comp: raise HTTPException(status_code=404)
    db.delete(comp)
    db.commit()
    return {"ok": True}

@app.get("/prompts")
async def list_prompts(project_id: int, user: models.User = Depends(get_user_from_header), db: Session = Depends(get_db)):
    return db.query(models.PromptTemplate).filter(models.PromptTemplate.project_id == project_id).all()

@app.post("/prompts")
async def create_prompt(req: schemas.PromptCreate, project_id: int, user: models.User = Depends(get_user_from_header), db: Session = Depends(get_db)):
    prompt = models.PromptTemplate(project_id=project_id, name=req.name, template=req.template)
    db.add(prompt)
    db.commit()
    db.refresh(prompt)
    return prompt

@app.delete("/prompts/{prompt_id}")
async def delete_prompt(prompt_id: int, user: models.User = Depends(get_user_from_header), db: Session = Depends(get_db)):
    prompt = db.query(models.PromptTemplate).filter(models.PromptTemplate.id == prompt_id).first()
    if not prompt: raise HTTPException(status_code=404)
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
    suggestions = brain.analyze_spec_and_suggest(layer, items, context)
    return {"suggestions": suggestions}

@app.post("/import-from-repo")
async def import_from_repo(req: schemas.SpecPushRequest, user: models.User = Depends(get_user_from_header), db: Session = Depends(get_db)):
    project = db.query(models.Project).filter(models.Project.id == req.project_id, models.Project.owner_id == user.id).first()
    if not project: raise HTTPException(status_code=404)
    github_token = auth.decrypt_token(user.encrypted_github_token)
    repo_full_name = project.repo_url
    if repo_full_name.startswith("http"):
        parts = repo_full_name.rstrip("/").split("/")
        repo_full_name = f"{parts[-2]}/{parts[-1]}"

    result = await repo_scanner.scan_repo(github_token, repo_full_name)
    db.query(models.DatabaseSchema).filter(models.DatabaseSchema.project_id == project.id).delete()
    db.query(models.ApiEndpoint).filter(models.ApiEndpoint.project_id == project.id).delete()
    db.query(models.UIComponent).filter(models.UIComponent.project_id == project.id).delete()
    db.commit()

    for table in result["tables"]:
        db.add(models.DatabaseSchema(project_id=project.id, table_name=table["table_name"], fields=table["fields"]))
    for route in result["routes"]:
        db.add(models.ApiEndpoint(project_id=project.id, method=route["method"], route=route["route"], request_schema={}, response_schema={}))
    
    db.commit()
    return {"message": "Import complete", "tables_found": len(result["tables"]), "routes_found": len(result["routes"])}

@app.post("/push-to-github")
async def push_to_github(req: schemas.SpecPushRequest, user: models.User = Depends(get_user_from_header), db: Session = Depends(get_db)):
    project = db.query(models.Project).filter(models.Project.id == req.project_id, models.Project.owner_id == user.id).first()
    if not project: raise HTTPException(status_code=404)
    schemas_data = db.query(models.DatabaseSchema).filter(models.DatabaseSchema.project_id == project.id).all()
    endpoints_data = db.query(models.ApiEndpoint).filter(models.ApiEndpoint.project_id == project.id).all()
    prompts_data = db.query(models.PromptTemplate).filter(models.PromptTemplate.project_id == project.id).all()
    spec = {
        "project": {"name": project.name, "repo_url": project.repo_url},
        "database": [{"table": s.table_name, "fields": s.fields} for s in schemas_data],
        "endpoints": [{"method": e.method, "route": e.route} for e in endpoints_data],
        "prompts": [{"name": p.name} for p in prompts_data]
    }
    github_token = auth.decrypt_token(user.encrypted_github_token)
    res = await github_utils.push_spec_to_github(github_token, project.repo_url, json.dumps(spec, indent=2))
    return {"message": "Spec pushed successfully"}

@app.post("/generate/prisma")
async def generate_prisma(req: schemas.SpecPushRequest, user: models.User = Depends(get_user_from_header), db: Session = Depends(get_db)):
    project = db.query(models.Project).filter(models.Project.id == req.project_id, models.Project.owner_id == user.id).first()
    if not project: raise HTTPException(status_code=404)
    schemas_data = db.query(models.DatabaseSchema).filter(models.DatabaseSchema.project_id == project.id).all()
    code = generator.generate_prisma_schema({"database": [{"table_name": s.table_name, "fields": s.fields} for s in schemas_data]})
    return {"code": code}

@app.post("/generate/fastapi")
async def generate_fastapi(req: schemas.SpecPushRequest, user: models.User = Depends(get_user_from_header), db: Session = Depends(get_db)):
    project = db.query(models.Project).filter(models.Project.id == req.project_id, models.Project.owner_id == user.id).first()
    if not project: raise HTTPException(status_code=404)
    endpoints_data = db.query(models.ApiEndpoint).filter(models.ApiEndpoint.project_id == project.id).all()
    code = generator.generate_fastapi_code({"endpoints": [{"method": e.method, "route": e.route} for e in endpoints_data]})
    return {"code": code}

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
    
    code = brain.generate_react_component(req.component_name, req.component_type, context)
    return {"code": code}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
