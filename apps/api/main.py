import json
from fastapi import FastAPI, Depends, HTTPException, status, Header
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from typing import List, Optional

import models, schemas, database, auth, github_utils, generator, repo_scanner
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

# Authentication Dependency
def get_current_user(db: Session = Depends(get_db), token: str = None):
    # In a real app, we'd get this from the Authorization header
    # For MVP simplicity, we might pass it as a query param or header
    # Let's assume it's in the header: Authorization: Bearer <token>
    pass

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

# For simple MVP, we will use a naive user lookup from JWT in headers
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

@app.get("/github/repos")
async def get_user_repos(user: models.User = Depends(get_user_from_header)):
    token = auth.decrypt_token(user.encrypted_github_token)
    repos = await github_utils.get_github_repos(token)
    return repos

@app.get("/projects")
async def list_projects(user: models.User = Depends(get_user_from_header), db: Session = Depends(get_db)):
    return db.query(models.Project).filter(models.Project.owner_id == user.id).all()

@app.post("/projects")
async def create_project(req: schemas.ProjectCreate, user: models.User = Depends(get_user_from_header), db: Session = Depends(get_db)):
    project = models.Project(name=req.name, repo_url=req.repo_url, owner_id=user.id)
    db.add(project)
    db.commit()
    db.refresh(project)
    return project

@app.get("/schemas")
async def list_schemas(project_id: int, user: models.User = Depends(get_user_from_header), db: Session = Depends(get_db)):
    project = db.query(models.Project).filter(models.Project.id == project_id, models.Project.owner_id == user.id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return db.query(models.DatabaseSchema).filter(models.DatabaseSchema.project_id == project_id).all()

@app.get("/endpoints")
async def list_endpoints(project_id: int, user: models.User = Depends(get_user_from_header), db: Session = Depends(get_db)):
    project = db.query(models.Project).filter(models.Project.id == project_id, models.Project.owner_id == user.id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return db.query(models.ApiEndpoint).filter(models.ApiEndpoint.project_id == project_id).all()

@app.get("/prompts")
async def list_prompts(project_id: int, user: models.User = Depends(get_user_from_header), db: Session = Depends(get_db)):
    project = db.query(models.Project).filter(models.Project.id == project_id, models.Project.owner_id == user.id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return db.query(models.PromptTemplate).filter(models.PromptTemplate.project_id == project_id).all()

@app.post("/schemas")
async def create_schema(req: schemas.SchemaCreate, project_id: int, user: models.User = Depends(get_user_from_header), db: Session = Depends(get_db)):
    # Verify ownership
    project = db.query(models.Project).filter(models.Project.id == project_id, models.Project.owner_id == user.id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    db_schema = models.DatabaseSchema(
        project_id=project_id,
        table_name=req.table_name,
        fields=[f.dict() for f in req.fields]
    )
    db.add(db_schema)
    db.commit()
    db.refresh(db_schema)
    return db_schema

@app.post("/endpoints")
async def create_endpoint(req: schemas.EndpointCreate, project_id: int, user: models.User = Depends(get_user_from_header), db: Session = Depends(get_db)):
    project = db.query(models.Project).filter(models.Project.id == project_id, models.Project.owner_id == user.id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    endpoint = models.ApiEndpoint(
        project_id=project_id,
        method=req.method,
        route=req.route,
        request_schema=req.request_schema,
        response_schema=req.response_schema
    )
    db.add(endpoint)
    db.commit()
    db.refresh(endpoint)
    return endpoint

@app.post("/prompts")
async def create_prompt(req: schemas.PromptCreate, project_id: int, user: models.User = Depends(get_user_from_header), db: Session = Depends(get_db)):
    project = db.query(models.Project).filter(models.Project.id == project_id, models.Project.owner_id == user.id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    prompt = models.PromptTemplate(
        project_id=project_id,
        name=req.name,
        template=req.template
    )
    db.add(prompt)
    db.commit()
    db.refresh(prompt)
    return prompt

@app.post("/import-from-repo")
async def import_from_repo(req: schemas.SpecPushRequest, user: models.User = Depends(get_user_from_header), db: Session = Depends(get_db)):
    project = db.query(models.Project).filter(models.Project.id == req.project_id, models.Project.owner_id == user.id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    github_token = auth.decrypt_token(user.encrypted_github_token)

    # repo_url is stored as "owner/repo" full_name from the dropdown
    repo_full_name = project.repo_url
    # Handle if stored as full URL
    if repo_full_name.startswith("http"):
        parts = repo_full_name.rstrip("/").split("/")
        repo_full_name = f"{parts[-2]}/{parts[-1]}"

    result = await repo_scanner.scan_repo(github_token, repo_full_name)

    # Clear existing specs for this project before importing
    db.query(models.DatabaseSchema).filter(models.DatabaseSchema.project_id == project.id).delete()
    db.query(models.ApiEndpoint).filter(models.ApiEndpoint.project_id == project.id).delete()
    db.commit()

    # Save detected tables
    for table in result["tables"]:
        db_schema = models.DatabaseSchema(
            project_id=project.id,
            table_name=table["table_name"],
            fields=table["fields"]
        )
        db.add(db_schema)

    # Save detected routes
    for route in result["routes"]:
        endpoint = models.ApiEndpoint(
            project_id=project.id,
            method=route["method"],
            route=route["route"],
            request_schema={},
            response_schema={}
        )
        db.add(endpoint)

    db.commit()

    return {
        "message": "Import complete",
        "tables_found": len(result["tables"]),
        "routes_found": len(result["routes"]),
        "files_scanned": result["files_scanned"],
        "total_files": result["total_files"],
    }

@app.post("/push-to-github")
async def push_to_github(req: schemas.SpecPushRequest, user: models.User = Depends(get_user_from_header), db: Session = Depends(get_db)):
    project = db.query(models.Project).filter(models.Project.id == req.project_id, models.Project.owner_id == user.id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # Collect all specs
    schemas_data = db.query(models.DatabaseSchema).filter(models.DatabaseSchema.project_id == project.id).all()
    endpoints_data = db.query(models.ApiEndpoint).filter(models.ApiEndpoint.project_id == project.id).all()
    prompts_data = db.query(models.PromptTemplate).filter(models.PromptTemplate.project_id == project.id).all()
    
    spec = {
        "project": {
            "name": project.name,
            "repo_url": project.repo_url
        },
        "database": [
            {"table": s.table_name, "fields": s.fields} for s in schemas_data
        ],
        "endpoints": [
            {
                "method": e.method,
                "route": e.route,
                "request": e.request_schema,
                "response": e.response_schema
            } for e in endpoints_data
        ],
        "prompts": [
            {"name": p.name, "template": p.template} for p in prompts_data
        ]
    }
    
    github_token = auth.decrypt_token(user.encrypted_github_token)
    res = await github_utils.push_spec_to_github(github_token, project.repo_url, json.dumps(spec, indent=2))
    
    return {"message": "Spec pushed successfully", "github_response": res}

@app.post("/generate/prisma")
async def generate_prisma(req: schemas.SpecPushRequest, user: models.User = Depends(get_user_from_header), db: Session = Depends(get_db)):
    project = db.query(models.Project).filter(models.Project.id == req.project_id, models.Project.owner_id == user.id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    schemas_data = db.query(models.DatabaseSchema).filter(models.DatabaseSchema.project_id == project.id).all()
    
    spec = {
        "database": [
            {"table_name": s.table_name, "fields": s.fields} for s in schemas_data
        ]
    }
    
    code = generator.generate_prisma_schema(spec)
    return {"code": code}

@app.post("/generate/fastapi")
async def generate_fastapi(req: schemas.SpecPushRequest, user: models.User = Depends(get_user_from_header), db: Session = Depends(get_db)):
    project = db.query(models.Project).filter(models.Project.id == req.project_id, models.Project.owner_id == user.id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    endpoints_data = db.query(models.ApiEndpoint).filter(models.ApiEndpoint.project_id == project.id).all()
    
    spec = {
        "endpoints": [
            {
                "method": e.method,
                "route": e.route,
                "request_schema": e.request_schema,
                "response_schema": e.response_schema
            } for e in endpoints_data
        ]
    }
    
    code = generator.generate_fastapi_code(spec)
    return {"code": code}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
