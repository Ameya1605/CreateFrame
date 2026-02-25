import httpx
import base64
import re
import asyncio
from typing import List, Dict, Any, Optional


async def fetch_repo_tree(token: str, owner: str, repo: str) -> List[Dict]:
    """Get flat list of all files in the repo."""
    url = f"https://api.github.com/repos/{owner}/{repo}/git/trees/HEAD?recursive=1"
    headers = {"Authorization": f"Bearer {token}"}
    async with httpx.AsyncClient() as client:
        res = await client.get(url, headers=headers)
        if res.status_code != 200:
            return []
        data = res.json()
        return [f for f in data.get("tree", []) if f.get("type") == "blob"]


async def fetch_file_content(token: str, owner: str, repo: str, path: str) -> str:
    """Fetch decoded content of a single file."""
    url = f"https://api.github.com/repos/{owner}/{repo}/contents/{path}"
    headers = {"Authorization": f"Bearer {token}"}
    async with httpx.AsyncClient() as client:
        res = await client.get(url, headers=headers)
        if res.status_code != 200:
            return ""
        data = res.json()
        content = data.get("content", "")
        try:
            return base64.b64decode(content).decode("utf-8", errors="ignore")
        except Exception:
            return ""


def parse_sqlalchemy_models(content: str) -> List[Dict]:
    """Extract table names and columns from SQLAlchemy model files."""
    tables = []
    class_pattern = re.compile(r"class\s+(\w+)\s*\(.*(?:Base|Model).*\):", re.MULTILINE)
    column_pattern = re.compile(r"(\w+)\s*=\s*(?:mapped_column|Column)\(([^)]+)\)")

    classes = list(class_pattern.finditer(content))
    for i, match in enumerate(classes):
        class_name = match.group(1)
        if class_name in ("Base", "BaseModel", "TimestampMixin"):
            continue
        start = match.end()
        end = classes[i + 1].start() if i + 1 < len(classes) else len(content)
        class_body = content[start:end]

        fields = []
        for col_match in column_pattern.finditer(class_body):
            field_name = col_match.group(1)
            col_args = col_match.group(2)
            type_match = re.search(r"(String|Integer|Boolean|Float|DateTime|Text|JSON|UUID|Enum)", col_args)
            field_type = type_match.group(1).lower() if type_match else "string"
            if not field_name.startswith("_"):
                fields.append({"name": field_name, "type": field_type})

        if fields:
            tables.append({"table_name": class_name, "fields": fields})

    return tables


def parse_prisma_schema(content: str) -> List[Dict]:
    """Extract models from a Prisma schema file."""
    tables = []
    model_pattern = re.compile(r"model\s+(\w+)\s*\{([^}]+)\}", re.MULTILINE)
    field_pattern = re.compile(r"^\s+(\w+)\s+(\w+)", re.MULTILINE)

    for model_match in model_pattern.finditer(content):
        model_name = model_match.group(1)
        model_body = model_match.group(2)
        fields = []
        for field_match in field_pattern.finditer(model_body):
            field_name = field_match.group(1)
            field_type = field_match.group(2).lower()
            if not field_name.startswith("@") and field_name not in ("//",):
                fields.append({"name": field_name, "type": field_type})
        if fields:
            tables.append({"table_name": model_name, "fields": fields})

    return tables


def parse_fastapi_router_prefixes(content: str) -> Dict[str, str]:
    """
    Extract router variable name -> prefix mapping from include_router calls.
    e.g. app.include_router(users.router, prefix="/users") -> {"router": "/users"}
    Also handles: router = APIRouter(prefix="/users")
    """
    prefixes = {}

    # Pattern 1: app.include_router(module.router, prefix="/prefix")
    include_pattern = re.compile(
        r'include_router\s*\(\s*(\w+)(?:\.(\w+))?\s*,.*?prefix\s*=\s*["\']([^"\']+)["\']',
        re.DOTALL
    )
    for match in include_pattern.finditer(content):
        module_or_var = match.group(1)
        attr = match.group(2)  # e.g. "router" in users.router
        prefix = match.group(3)
        # Key by module name (e.g. "users") and attr (e.g. "router")
        prefixes[module_or_var] = prefix
        if attr:
            prefixes[attr] = prefix

    # Pattern 2: router = APIRouter(prefix="/prefix")
    apirouter_pattern = re.compile(
        r'(\w+)\s*=\s*APIRouter\s*\(.*?prefix\s*=\s*["\']([^"\']+)["\']',
        re.DOTALL
    )
    for match in apirouter_pattern.finditer(content):
        var_name = match.group(1)
        prefix = match.group(2)
        prefixes[var_name] = prefix

    return prefixes


def parse_fastapi_routes(content: str, file_path: str = "", all_file_contents: Optional[Dict[str, str]] = None) -> List[Dict]:
    """
    Extract routes from FastAPI files, resolving router prefixes where possible.
    """
    routes = []

    # First, find any prefix defined in THIS file via APIRouter(prefix=...)
    local_prefixes = parse_fastapi_router_prefixes(content)

    # Also check the main app file for include_router calls that reference this module
    # We'll use the file path stem to match (e.g. "users" from "app/routers/users.py")
    file_stem = file_path.replace("\\", "/").split("/")[-1].replace(".py", "") if file_path else ""

    # Collect prefix from main file if available
    inherited_prefix = ""
    if all_file_contents:
        for fpath, fcontent in all_file_contents.items():
            if "include_router" in fcontent:
                main_prefixes = parse_fastapi_router_prefixes(fcontent)
                if file_stem in main_prefixes:
                    inherited_prefix = main_prefixes[file_stem]
                    break

    # Now extract route decorators
    # Supports @app.get("/"), @router.post(''), app.add_api_route("/", ...), etc.
    route_pattern = re.compile(
        r'(@\w+\.|(?:\w+\.)?add_api_route\s*\(\s*)(get|post|put|delete|patch|api_route)?\s*?["\']([^"\']*)["\']',
        re.MULTILINE | re.IGNORECASE
    )
    for match in route_pattern.finditer(content):
        var_name = match.group(1)   # e.g. "app", "router", "users_router"
        method = match.group(2).upper()
        route_path = match.group(3)

        # Determine prefix: check local APIRouter prefix first, then inherited
        prefix = ""
        if var_name in local_prefixes:
            prefix = local_prefixes[var_name]
        elif inherited_prefix:
            prefix = inherited_prefix

        # Combine prefix + route, avoid double slashes
        if prefix:
            full_route = prefix.rstrip("/") + "/" + route_path.lstrip("/")
        else:
            full_route = route_path

        # Normalize: ensure leading slash
        if not full_route.startswith("/"):
            full_route = "/" + full_route

        routes.append({"method": method, "route": full_route})

    return routes


def parse_express_routes(content: str) -> List[Dict]:
    """Extract routes from Express.js files."""
    routes = []
    # Use * to allow empty strings in routes, e.g. app.get('')
    route_pattern = re.compile(
        r'(?:router|app)\.(get|post|put|delete|patch|use)\s*\(\s*["\']([^"\']*)["\']',
        re.MULTILINE | re.IGNORECASE
    )
    for match in route_pattern.finditer(content):
        method = match.group(1).upper()
        route = match.group(2)
        if not route or route == "":
            route = "/"
        routes.append({"method": method, "route": route})
    return routes


def parse_nextjs_routes(files: List[str]) -> List[Dict]:
    """Infer API routes from Next.js file structure."""
    routes = []
    for path in files:
        if "/api/" in path and path.endswith(("route.ts", "route.js")):
            route = re.sub(r"^.*?/api", "/api", path)
            route = re.sub(r"/route\.(ts|js)$", "", route)
            route = re.sub(r"\[(\w+)\]", r":\1", route)
            if route:
                routes.append({"method": "GET", "route": route})
    return routes


def is_relevant_file(path: str) -> bool:
    """Only scan files likely to contain models or routes."""
    skip_dirs = ("node_modules", ".git", "dist", "build", "__pycache__", ".next", "venv", ".venv", "migrations", "alembic")
    for skip in skip_dirs:
        if f"/{skip}/" in f"/{path}" or path.startswith(f"{skip}/"):
            return False
    relevant_extensions = (".py", ".ts", ".js", ".tsx", ".jsx", ".prisma")
    return any(path.endswith(ext) for ext in relevant_extensions)


async def scan_repo(token: str, repo_full_name: str) -> Dict[str, Any]:
    """
    Main entry point. Scans a GitHub repo and returns detected tables and routes.
    repo_full_name: e.g. "tanishapritha/dpdp-audit"
    """
    owner, repo = repo_full_name.split("/", 1)
    all_files = await fetch_repo_tree(token, owner, repo)

    detected_tables = []
    detected_routes = []
    file_paths = [f["path"] for f in all_files]

    # First pass: fetch all relevant file contents (needed for prefix resolution)
    relevant_file_tasks = []
    relevant_paths = []
    for file_info in all_files:
        path = file_info["path"]
        if is_relevant_file(path):
            relevant_paths.append(path)
            relevant_file_tasks.append(fetch_file_content(token, owner, repo, path))
    
    contents = await asyncio.gather(*relevant_file_tasks)
    relevant_files = {path: content for path, content in zip(relevant_paths, contents) if content}

    # Second pass: parse each file
    for path, content in relevant_files.items():
        if path.endswith(".prisma"):
            detected_tables.extend(parse_prisma_schema(content))

        elif path.endswith(".py"):
            # SQLAlchemy models
            if "Column(" in content or "mapped_column(" in content:
                detected_tables.extend(parse_sqlalchemy_models(content))
            # FastAPI routes — pass all file contents for prefix resolution
            if "@app." in content or "@router." in content or "APIRouter" in content:
                detected_routes.extend(
                    parse_fastapi_routes(content, file_path=path, all_file_contents=relevant_files)
                )

        elif path.endswith((".ts", ".js", ".tsx", ".jsx")):
            if "router." in content or ("app." in content and "express" in content.lower()):
                detected_routes.extend(parse_express_routes(content))

    # Next.js file-based routes
    detected_routes.extend(parse_nextjs_routes(file_paths))

    # Deduplicate routes
    seen_routes = set()
    unique_routes = []
    for r in detected_routes:
        key = f"{r['method']}:{r['route']}"
        if key not in seen_routes:
            seen_routes.add(key)
            unique_routes.append(r)

    # Deduplicate tables
    seen_tables = set()
    unique_tables = []
    for t in detected_tables:
        if t["table_name"] not in seen_tables:
            seen_tables.add(t["table_name"])
            unique_tables.append(t)

    return {
        "tables": unique_tables,
        "routes": unique_routes,
        "files_scanned": len(relevant_files),
        "total_files": len(all_files),
    }
