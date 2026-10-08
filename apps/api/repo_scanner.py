import httpx
import base64
import re
import asyncio
import ast
import io
import tarfile
from typing import List, Dict, Any, Optional


async def fetch_repo_tarball(token: str, owner: str, repo: str, ref: str = "HEAD") -> Dict[str, str]:
    """
    Download repo as a tarball in a single HTTP request and extract relevant files to {path: content}.
    Avoids rate limits caused by per-file GitHub Contents API calls.
    """
    url = f"https://api.github.com/repos/{owner}/{repo}/tarball/{ref}"
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    files: Dict[str, str] = {}
    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=45.0) as client:
            res = await client.get(url, headers=headers)
            if res.status_code != 200:
                return {}
        with tarfile.open(fileobj=io.BytesIO(res.content), mode="r:gz") as tar:
            for member in tar.getmembers():
                if member.isfile():
                    parts = member.name.split("/")
                    # GitHub tarball root is {owner}-{repo}-{sha}/...
                    rel_path = "/".join(parts[1:]) if len(parts) > 1 else member.name
                    if is_relevant_file(rel_path):
                        f = tar.extractfile(member)
                        if f:
                            files[rel_path] = f.read().decode("utf-8", errors="ignore")
    except Exception:
        return {}
    return files


async def fetch_repo_tree(token: str, owner: str, repo: str) -> List[Dict]:
    """Get flat list of all files in the repo (fallback if tarball fails)."""
    url = f"https://api.github.com/repos/{owner}/{repo}/git/trees/HEAD?recursive=1"
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    async with httpx.AsyncClient(timeout=30.0) as client:
        res = await client.get(url, headers=headers)
        if res.status_code != 200:
            return []
        data = res.json()
        return [f for f in data.get("tree", []) if f.get("type") == "blob"]


async def fetch_file_content(token: str, owner: str, repo: str, path: str) -> str:
    """Fetch decoded content of a single file (fallback)."""
    url = f"https://api.github.com/repos/{owner}/{repo}/contents/{path}"
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    async with httpx.AsyncClient(timeout=20.0) as client:
        res = await client.get(url, headers=headers)
        if res.status_code != 200:
            return ""
        data = res.json()
        content = data.get("content", "")
        try:
            return base64.b64decode(content).decode("utf-8", errors="ignore")
        except Exception:
            return ""


def is_relevant_file(path: str) -> bool:
    """Only scan files likely to contain models, schemas, or routes."""
    skip_dirs = (
        "node_modules", ".git", "dist", "build", "__pycache__",
        ".next", "venv", ".venv", "migrations", "alembic", ".turbo", ".cache"
    )
    for skip in skip_dirs:
        if f"/{skip}/" in f"/{path}" or path.startswith(f"{skip}/"):
            return False
    relevant_extensions = (
        ".py", ".ts", ".js", ".tsx", ".jsx", ".prisma",
        ".html", ".htm", ".jinja", ".jinja2", ".vue", ".svelte", ".astro",
        ".ejs", ".hbs", ".handlebars", ".pug", ".jade", ".twig", ".blade.php", ".erb", ".mustache"
    )
    return any(path.endswith(ext) for ext in relevant_extensions)


def _get_node_name(node: Optional[ast.AST]) -> str:
    """Extract string identifier name from AST Name, Attribute, or Constant node."""
    if node is None:
        return ""
    if isinstance(node, ast.Name):
        return node.id
    elif isinstance(node, ast.Attribute):
        parent = _get_node_name(node.value)
        return f"{parent}.{node.attr}" if parent else node.attr
    elif isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return ""


def _normalize_type_name(raw_type: str) -> str:
    """Normalize raw type string to standard spec type."""
    t = raw_type.lower()
    if any(k in t for k in ("int", "serial", "bigint", "smallint", "autofield")):
        return "integer"
    if "text" in t:
        return "text"
    if any(k in t for k in ("str", "varchar", "char", "string", "slugfield", "emailfield", "urlfield")):
        return "string"
    if "bool" in t:
        return "boolean"
    if any(k in t for k in ("float", "double", "decimal", "numeric", "real")):
        return "float"
    if any(k in t for k in ("datetime", "timestamp")):
        return "datetime"
    if "date" in t:
        return "date"
    if "time" in t:
        return "time"
    if "uuid" in t:
        return "uuid"
    if any(k in t for k in ("json", "dict", "list")):
        return "json"
    if "enum" in t:
        return "enum"
    return "string"


# ============================================================================
# ORM / MODEL PARSERS (AST-BASED)
# ============================================================================

def parse_sqlalchemy_models(content: str) -> List[Dict]:
    """
    Extract table names, columns, and foreign key relations from SQLAlchemy model files using Python AST.
    Handles traditional Column(...) as well as SQLAlchemy 2.0 mapped_column(...) and Mapped[...] annotations.
    """
    tables = []

    try:
        tree = ast.parse(content)
    except SyntaxError:
        return _parse_sqlalchemy_models_regex_fallback(content)

    class SQLAlchemyVisitor(ast.NodeVisitor):
        def __init__(self):
            self.extracted_tables = []

        def visit_ClassDef(self, node: ast.ClassDef):
            # Exclude base classes and mixins
            if node.name in ("Base", "BaseModel", "TimestampMixin", "DeclarativeBase"):
                return

            base_names = [_get_node_name(b) for b in node.bases]
            has_orm_base = any(b in ("Base", "Model", "db.Model", "DeclarativeBase") or b.endswith(".Base") or b.endswith(".Model") for b in base_names if b)

            # Inspect class body for __tablename__, Column, mapped_column
            table_name = node.name
            fields = []
            relations = []
            has_orm_attrs = False

            for item in node.body:
                # Check for explicit __tablename__ = "..."
                if isinstance(item, ast.Assign):
                    for target in item.targets:
                        if isinstance(target, ast.Name) and target.id == "__tablename__":
                            if isinstance(item.value, ast.Constant) and isinstance(item.value.value, str):
                                table_name = item.value.value
                                has_orm_base = True

                # Check for column assignments (Assign or AnnAssign)
                col_name = None
                call_node: Optional[ast.Call] = None
                annotation_node = None

                if isinstance(item, ast.Assign):
                    for target in item.targets:
                        if isinstance(target, ast.Name) and not target.id.startswith("_"):
                            col_name = target.id
                            if isinstance(item.value, ast.Call):
                                call_node = item.value

                elif isinstance(item, ast.AnnAssign):
                    if isinstance(item.target, ast.Name) and not item.target.id.startswith("_"):
                        col_name = item.target.id
                        annotation_node = item.annotation
                        if isinstance(item.value, ast.Call):
                            call_node = item.value

                if col_name and (call_node or annotation_node):
                    func_name = _get_node_name(call_node.func) if call_node else ""
                    is_column = (
                        "Column" in func_name
                        or "mapped_column" in func_name
                        or "relationship" in func_name
                        or (annotation_node and "Mapped" in _get_node_name(annotation_node))
                    )

                    if not is_column:
                        continue

                    has_orm_attrs = True

                    # Handle relationship(...)
                    if "relationship" in func_name:
                        target_model = ""
                        if call_node and call_node.args:
                            target_model = _get_node_name(call_node.args[0])
                        if target_model:
                            relations.append({
                                "name": f"{table_name}_{col_name}_rel",
                                "type": "1:N",
                                "from_table": table_name,
                                "from_field": col_name,
                                "to_table": target_model,
                                "to_field": "id"
                            })
                        continue

                    # Determine column type
                    col_type = "string"
                    is_pk = False
                    fk_target = None

                    # Check call args & keywords
                    if call_node:
                        # Scan args for SQL type (Integer, String, etc.) and ForeignKey
                        for arg in call_node.args:
                            arg_name = _get_node_name(arg)
                            if isinstance(arg, ast.Call):
                                func_name = _get_node_name(arg.func)
                                if "ForeignKey" in func_name and arg.args:
                                    fk_target = _get_node_name(arg.args[0])
                                elif func_name:
                                    norm = _normalize_type_name(func_name)
                                    if norm != "string" or "str" in func_name.lower():
                                        col_type = norm
                            elif "ForeignKey" in arg_name and isinstance(arg, ast.Call) and arg.args:
                                fk_target = _get_node_name(arg.args[0])
                            elif arg_name and not fk_target:
                                norm = _normalize_type_name(arg_name)
                                if norm != "string" or "str" in arg_name.lower():
                                    col_type = norm

                        # Scan keywords for primary_key and foreign_key
                        for kw in call_node.keywords:
                            if kw.arg == "primary_key":
                                if isinstance(kw.value, ast.Constant) and kw.value.value is True:
                                    is_pk = True
                            elif kw.arg == "foreign_key" and isinstance(kw.value, (ast.Constant, ast.Call)):
                                if isinstance(kw.value, ast.Constant):
                                    fk_target = str(kw.value.value)
                                elif isinstance(kw.value, ast.Call) and kw.value.args:
                                    fk_target = _get_node_name(kw.value.args[0])

                    # Check annotation if type still default
                    if annotation_node:
                        ann_str = _get_node_name(annotation_node)
                        if isinstance(annotation_node, ast.Subscript):
                            ann_str = _get_node_name(annotation_node.slice)
                        ann_norm = _normalize_type_name(ann_str)
                        if col_type == "string" and (ann_norm != "string" or "str" in ann_str.lower()):
                            col_type = ann_norm

                    field_entry: Dict[str, Any] = {"name": col_name, "type": col_type}
                    if is_pk:
                        field_entry["is_primary_key"] = True

                    if fk_target:
                        target_parts = fk_target.split(".")
                        to_table = target_parts[0]
                        to_field = target_parts[1] if len(target_parts) > 1 else "id"
                        field_entry["foreign_key"] = fk_target
                        relations.append({
                            "name": f"{table_name}_{col_name}_fk",
                            "type": "N:1",
                            "from_table": table_name,
                            "from_field": col_name,
                            "to_table": to_table,
                            "to_field": to_field
                        })

                    fields.append(field_entry)

            if (has_orm_base or has_orm_attrs) and fields:
                self.extracted_tables.append({
                    "table_name": table_name,
                    "fields": fields,
                    "relations": relations
                })

    visitor = SQLAlchemyVisitor()
    visitor.visit(tree)
    return visitor.extracted_tables


def _parse_sqlalchemy_models_regex_fallback(content: str) -> List[Dict]:
    """Regex fallback for SQLAlchemy model parsing if AST syntax parsing fails."""
    tables = []
    class_pattern = re.compile(r"class\s+(\w+)\s*\(.*(?:Base|Model).*\):", re.MULTILINE)
    column_pattern = re.compile(r"(\w+)\s*=\s*(?:mapped_column|Column)\(([^)]+)\)")

    classes = list(class_pattern.finditer(content))
    for i, match in enumerate(classes):
        class_name = match.group(1)
        if class_name in ("Base", "BaseModel", "TimestampMixin", "DeclarativeBase"):
            continue
        start = match.end()
        end = classes[i + 1].start() if i + 1 < len(classes) else len(content)
        class_body = content[start:end]

        fields = []
        relations = []
        for col_match in column_pattern.finditer(class_body):
            field_name = col_match.group(1)
            col_args = col_match.group(2)
            type_match = re.search(r"(String|Integer|Boolean|Float|DateTime|Text|JSON|UUID|Enum)", col_args)
            field_type = type_match.group(1).lower() if type_match else "string"

            # Detect foreign key in args
            fk_match = re.search(r"ForeignKey\(['\"]([^'\"]+)['\"]\)", col_args)
            if fk_match:
                fk_target = fk_match.group(1)
                parts = fk_target.split(".")
                relations.append({
                    "name": f"{class_name}_{field_name}_fk",
                    "type": "N:1",
                    "from_table": class_name,
                    "from_field": field_name,
                    "to_table": parts[0],
                    "to_field": parts[1] if len(parts) > 1 else "id"
                })

            if not field_name.startswith("_"):
                fields.append({"name": field_name, "type": field_type})

        if fields:
            tables.append({"table_name": class_name, "fields": fields, "relations": relations})

    return tables


def parse_django_models(content: str) -> List[Dict]:
    """Extract table names, fields, and relations from Django model files using Python AST."""
    tables = []
    try:
        tree = ast.parse(content)
    except Exception:
        return []

    for node in tree.body:
        if not isinstance(node, ast.ClassDef):
            continue

        base_names = [_get_node_name(b) for b in node.bases]
        is_django_model = any(b in ("models.Model", "Model") or b.endswith(".Model") for b in base_names if b)
        if not is_django_model:
            continue

        table_name = node.name.lower()
        fields = []
        relations = []

        # Check for inner class Meta: db_table = "..."
        for item in node.body:
            if isinstance(item, ast.ClassDef) and item.name == "Meta":
                for meta_item in item.body:
                    if isinstance(meta_item, ast.Assign):
                        for target in meta_item.targets:
                            if isinstance(target, ast.Name) and target.id == "db_table":
                                if isinstance(meta_item.value, ast.Constant) and isinstance(meta_item.value.value, str):
                                    table_name = meta_item.value.value

        for item in node.body:
            field_name = None
            call_node = None

            if isinstance(item, ast.Assign):
                for target in item.targets:
                    if isinstance(target, ast.Name) and not target.id.startswith("_"):
                        field_name = target.id
                        if isinstance(item.value, ast.Call):
                            call_node = item.value

            elif isinstance(item, ast.AnnAssign):
                if isinstance(item.target, ast.Name) and not item.target.id.startswith("_"):
                    field_name = item.target.id
                    if isinstance(item.value, ast.Call):
                        call_node = item.value

            if not field_name or not call_node:
                continue

            func_name = _get_node_name(call_node.func)
            if not ("models." in func_name or func_name.endswith("Field") or func_name in ("ForeignKey", "ManyToManyField", "OneToOneField")):
                continue

            # Relation fields
            if "ForeignKey" in func_name or "OneToOneField" in func_name or "ManyToManyField" in func_name:
                rel_type = "N:1"
                if "OneToOneField" in func_name:
                    rel_type = "1:1"
                elif "ManyToManyField" in func_name:
                    rel_type = "M:N"

                target_model = ""
                if call_node.args:
                    target_model = _get_node_name(call_node.args[0]).strip("'\"")

                if target_model:
                    relations.append({
                        "name": f"{table_name}_{field_name}_rel",
                        "type": rel_type,
                        "from_table": table_name,
                        "from_field": field_name,
                        "to_table": target_model,
                        "to_field": "id"
                    })

                fields.append({"name": field_name, "type": "integer"})
            else:
                field_type = _normalize_type_name(func_name)
                fields.append({"name": field_name, "type": field_type})

        if fields:
            tables.append({"table_name": table_name, "fields": fields, "relations": relations})

    return tables


def parse_sqlmodel_models(content: str) -> List[Dict]:
    """Extract table names, fields, and relations from SQLModel model files using Python AST."""
    tables = []
    try:
        tree = ast.parse(content)
    except Exception:
        return []

    for node in tree.body:
        if not isinstance(node, ast.ClassDef):
            continue

        base_names = [_get_node_name(b) for b in node.bases]
        is_sqlmodel = any("SQLModel" in b for b in base_names if b)

        # Check keyword table=True in class definition: class Hero(SQLModel, table=True)
        has_table_kw = any(
            kw.arg == "table" and isinstance(kw.value, ast.Constant) and kw.value.value is True
            for kw in node.keywords
        )

        if not (is_sqlmodel and (has_table_kw or len(base_names) > 0)):
            continue

        table_name = node.name.lower()
        fields = []
        relations = []

        # Check explicit __tablename__
        for item in node.body:
            if isinstance(item, ast.Assign):
                for target in item.targets:
                    if isinstance(target, ast.Name) and target.id == "__tablename__":
                        if isinstance(item.value, ast.Constant) and isinstance(item.value.value, str):
                            table_name = item.value.value

        for item in node.body:
            field_name = None
            annotation_node = None
            call_node = None

            if isinstance(item, ast.AnnAssign):
                if isinstance(item.target, ast.Name) and not item.target.id.startswith("_"):
                    field_name = item.target.id
                    annotation_node = item.annotation
                    if isinstance(item.value, ast.Call):
                        call_node = item.value
            elif isinstance(item, ast.Assign):
                for target in item.targets:
                    if isinstance(target, ast.Name) and not target.id.startswith("_"):
                        field_name = target.id
                        if isinstance(item.value, ast.Call):
                            call_node = item.value

            if not field_name:
                continue

            # Determine type from annotation
            field_type = "string"
            if annotation_node:
                ann_str = _get_node_name(annotation_node)
                if isinstance(annotation_node, ast.Subscript):
                    ann_str = _get_node_name(annotation_node.slice)
                field_type = _normalize_type_name(ann_str)

            is_pk = False
            fk_target = None

            if call_node:
                func_name = _get_node_name(call_node.func)
                if "Relationship" in func_name:
                    # SQLModel relationship
                    continue
                for kw in call_node.keywords:
                    if kw.arg == "primary_key" and isinstance(kw.value, ast.Constant) and kw.value.value is True:
                        is_pk = True
                    elif kw.arg == "foreign_key" and isinstance(kw.value, ast.Constant):
                        fk_target = str(kw.value.value)

            field_dict: Dict[str, Any] = {"name": field_name, "type": field_type}
            if is_pk:
                field_dict["is_primary_key"] = True

            if fk_target:
                parts = fk_target.split(".")
                to_table = parts[0]
                to_field = parts[1] if len(parts) > 1 else "id"
                field_dict["foreign_key"] = fk_target
                relations.append({
                    "name": f"{table_name}_{field_name}_fk",
                    "type": "N:1",
                    "from_table": table_name,
                    "from_field": field_name,
                    "to_table": to_table,
                    "to_field": to_field
                })

            fields.append(field_dict)

        if fields:
            tables.append({"table_name": table_name, "fields": fields, "relations": relations})

    return tables


def parse_prisma_schema(content: str) -> List[Dict]:
    """Extract models, fields, and relations from a Prisma schema file."""
    tables = []
    model_pattern = re.compile(r"model\s+(\w+)\s*\{([^}]+)\}", re.MULTILINE)
    field_pattern = re.compile(r"^\s+(\w+)\s+(\w+)(.*?)$", re.MULTILINE)

    for model_match in model_pattern.finditer(content):
        model_name = model_match.group(1)
        model_body = model_match.group(2)
        fields = []
        relations = []

        for field_match in field_pattern.finditer(model_body):
            field_name = field_match.group(1)
            raw_field_type = field_match.group(2)
            attributes = field_match.group(3)

            if field_name.startswith("@") or field_name.startswith("//"):
                continue

            field_type = _normalize_type_name(raw_field_type)

            # Check relation attribute: @relation(fields: [authorId], references: [id])
            rel_match = re.search(r"@relation\s*\([^)]*fields:\s*\[(\w+)\],[^)]*references:\s*\[(\w+)\][^)]*\)", attributes)
            if rel_match:
                from_field = rel_match.group(1)
                to_field = rel_match.group(2)
                relations.append({
                    "name": f"{model_name}_{from_field}_fkey",
                    "type": "N:1",
                    "from_table": model_name,
                    "from_field": from_field,
                    "to_table": raw_field_type,
                    "to_field": to_field
                })

            # Ignore relation fields that reference another model without being scalar columns
            is_scalar = raw_field_type.lower() in (
                "string", "int", "boolean", "float", "datetime", "json", "bytes", "decimal", "bigint"
            ) or "@id" in attributes or "@default" in attributes

            if is_scalar:
                field_entry: Dict[str, Any] = {"name": field_name, "type": field_type}
                if "@id" in attributes:
                    field_entry["is_primary_key"] = True
                fields.append(field_entry)

        if fields:
            tables.append({"table_name": model_name, "fields": fields, "relations": relations})

    return tables


def parse_drizzle_schema(content: str) -> List[Dict]:
    """Extract table definitions, columns, and foreign key relations from Drizzle ORM TypeScript files."""
    tables = []
    # Match pgTable("users", { ... }), mysqlTable(...), sqliteTable(...)
    table_pattern = re.compile(
        r'(?:(?:export\s+)?const\s+(\w+)\s*=\s*)?(pgTable|mysqlTable|sqliteTable)\s*\(\s*["\']([^"\']+)["\']\s*,\s*\{',
        re.MULTILINE
    )

    for match in table_pattern.finditer(content):
        table_name = match.group(3)
        start_pos = match.end() - 1

        # Balanced brace extraction for table body
        brace_count = 0
        end_pos = start_pos
        for idx in range(start_pos, len(content)):
            if content[idx] == "{":
                brace_count += 1
            elif content[idx] == "}":
                brace_count -= 1
                if brace_count == 0:
                    end_pos = idx
                    break

        body = content[start_pos + 1:end_pos]
        fields = []
        relations = []

        # Match columns: field_name: columnType("db_col_name", ...).modifiers()
        col_pattern = re.compile(r'(\w+)\s*:\s*(\w+)\s*\(([^)]*)\)(.*?)(?:,|$)', re.MULTILINE)
        for col_match in col_pattern.finditer(body):
            col_name = col_match.group(1)
            col_type_fn = col_match.group(2)
            modifiers = col_match.group(4)

            field_type = _normalize_type_name(col_type_fn)
            field_entry: Dict[str, Any] = {"name": col_name, "type": field_type}

            if ".primaryKey()" in modifiers:
                field_entry["is_primary_key"] = True

            # Match .references(() => targetTable.targetCol)
            ref_match = re.search(r'\.references\s*\(\s*\(\)\s*=>\s*(\w+)\.(\w+)\s*\)', modifiers)
            if ref_match:
                to_table = ref_match.group(1)
                to_field = ref_match.group(2)
                relations.append({
                    "name": f"{table_name}_{col_name}_fk",
                    "type": "N:1",
                    "from_table": table_name,
                    "from_field": col_name,
                    "to_table": to_table,
                    "to_field": to_field
                })
                field_entry["foreign_key"] = f"{to_table}.{to_field}"

            fields.append(field_entry)

        if fields:
            tables.append({"table_name": table_name, "fields": fields, "relations": relations})

    return tables


# ============================================================================
# ROUTE PARSERS
# ============================================================================

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
        attr = match.group(2)
        prefix = match.group(3)
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
    """Extract routes from FastAPI files, resolving router prefixes where possible using AST."""
    routes = []
    local_prefixes = parse_fastapi_router_prefixes(content)

    file_stem = file_path.replace("\\", "/").split("/")[-1].replace(".py", "") if file_path else ""

    inherited_prefix = ""
    if all_file_contents:
        for fpath, fcontent in all_file_contents.items():
            if "include_router" in fcontent:
                main_prefixes = parse_fastapi_router_prefixes(fcontent)
                if file_stem in main_prefixes:
                    inherited_prefix = main_prefixes[file_stem]
                    break

    # 1. AST-based parser
    try:
        tree = ast.parse(content)
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                for dec in node.decorator_list:
                    if isinstance(dec, ast.Call):
                        method = None
                        var_prefix = ""
                        if isinstance(dec.func, ast.Attribute) and dec.func.attr.lower() in ("get", "post", "put", "delete", "patch"):
                            method = dec.func.attr.upper()
                            var_prefix = _get_node_name(dec.func.value)
                        elif isinstance(dec.func, ast.Name) and dec.func.id.lower() in ("get", "post", "put", "delete", "patch"):
                            method = dec.func.id.upper()

                        if method and dec.args and isinstance(dec.args[0], ast.Constant) and isinstance(dec.args[0].value, str):
                            route_path = dec.args[0].value
                            prefix = local_prefixes.get(var_prefix, "") or inherited_prefix
                            full_route = f"{prefix.rstrip('/')}/{route_path.lstrip('/')}" if prefix else route_path
                            if not full_route.startswith("/"):
                                full_route = "/" + full_route
                            routes.append({"method": method, "route": full_route})
    except Exception:
        pass

    # 2. Regex fallback
    if not routes:
        route_pattern = re.compile(
            r'@(\w+)\.(get|post|put|delete|patch|api_route)\s*\(\s*["\']([^"\']*)["\']',
            re.IGNORECASE
        )
        for match in route_pattern.finditer(content):
            var_prefix = match.group(1)
            method = match.group(2).upper()
            route_path = match.group(3)
            prefix = local_prefixes.get(var_prefix, "") or inherited_prefix
            full_route = f"{prefix.rstrip('/')}/{route_path.lstrip('/')}" if prefix else route_path
            if not full_route.startswith("/"):
                full_route = "/" + full_route
            routes.append({"method": method, "route": full_route})

    return routes


def parse_flask_routes(content: str) -> List[Dict]:
    """Extract routes from Flask application or Blueprint files using Python AST."""
    routes = []
    try:
        tree = ast.parse(content)
    except Exception:
        # Regex fallback
        pattern = re.compile(r'@(\w+)\.route\s*\(\s*["\']([^"\']+)["\'](?:.*?methods\s*=\s*\[([^\]]+)\])?', re.DOTALL)
        for match in pattern.finditer(content):
            path = match.group(2)
            raw_methods = match.group(3)
            methods = ["GET"]
            if raw_methods:
                methods = [m.strip(" '\"").upper() for m in raw_methods.split(",") if m.strip(" '\"")]
            for m in methods:
                routes.append({"method": m, "route": path if path.startswith("/") else "/" + path})
        return routes

    for node in tree.body:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue

        for decorator in node.decorator_list:
            if not isinstance(decorator, ast.Call):
                continue

            dec_name = _get_node_name(decorator.func)
            if not (".route" in dec_name or any(f".{m}" in dec_name for m in ("get", "post", "put", "delete", "patch"))):
                continue

            route_path = ""
            if decorator.args and isinstance(decorator.args[0], ast.Constant) and isinstance(decorator.args[0].value, str):
                route_path = decorator.args[0].value

            if not route_path:
                continue

            methods = []
            if ".route" in dec_name:
                for kw in decorator.keywords:
                    if kw.arg == "methods" and isinstance(kw.value, (ast.List, ast.Tuple)):
                        for elt in kw.value.elts:
                            if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                                methods.append(elt.value.upper())
                if not methods:
                    methods = ["GET"]
            else:
                method_part = dec_name.split(".")[-1].upper()
                methods = [method_part]

            norm_path = route_path if route_path.startswith("/") else "/" + route_path
            for m in methods:
                routes.append({"method": m, "route": norm_path})

    return routes


def parse_nestjs_controllers(content: str) -> List[Dict]:
    """Extract API routes from NestJS TypeScript controller files."""
    routes = []
    # Match @Controller('prefix') or @Controller()
    controller_match = re.search(r'@Controller\s*\(\s*(?:[\'"`]([^\'"`]*)[\'"`])?\s*\)', content)
    base_prefix = controller_match.group(1).strip("/") if controller_match and controller_match.group(1) else ""

    # Match @Get('path'), @Post('path'), etc.
    method_pattern = re.compile(
        r'@(Get|Post|Put|Delete|Patch|All|Options|Head)\s*\(\s*(?:[\'"`]([^\'"`]*)[\'"`])?\s*\)',
        re.MULTILINE
    )

    for match in method_pattern.finditer(content):
        http_method = match.group(1).upper()
        if http_method == "ALL":
            http_method = "ANY"
        sub_path = match.group(2).strip("/") if match.group(2) else ""

        if base_prefix and sub_path:
            full_route = f"/{base_prefix}/{sub_path}"
        elif base_prefix:
            full_route = f"/{base_prefix}"
        elif sub_path:
            full_route = f"/{sub_path}"
        else:
            full_route = "/"

        routes.append({"method": http_method, "route": full_route})

    return routes


def parse_express_routes(content: str) -> List[Dict]:
    """Extract routes from Express.js files."""
    routes = []
    route_pattern = re.compile(
        r'(?:router|app)\.(get|post|put|delete|patch|use)\s*\(\s*["\']([^"\']*)["\']',
        re.MULTILINE | re.IGNORECASE
    )
    for match in route_pattern.finditer(content):
        method = match.group(1).upper()
        route = match.group(2) or "/"
        if not route.startswith("/"):
            route = "/" + route
        routes.append({"method": method, "route": route})
    return routes


def parse_nextjs_routes(files: List[str]) -> List[Dict]:
    """Infer API routes from Next.js file structure."""
    routes = []
    for path in files:
        clean_path = path.replace("\\", "/")
        if "/api/" in clean_path and clean_path.endswith(("route.ts", "route.js")):
            route = re.sub(r"^.*?/api", "/api", clean_path)
            route = re.sub(r"/route\.(ts|js)$", "", route)
            route = re.sub(r"\[(\w+)\]", r":\1", route)
            if route:
                routes.append({"method": "GET", "route": route})
    return routes


def parse_ui_components(files: Dict[str, str], all_paths: List[str]) -> List[Dict[str, Any]]:
    """
    Detects all UI components, pages, templates, and views across:
    - Flask/Django/Jinja HTML templates (templates/*.html, *.jinja, *.jinja2)
    - Node / Express / PHP template engines (EJS, Handlebars, Pug, Blade, ERB, Twig)
    - Next.js App Router (app/**/page.tsx, layout.tsx) & Pages Router (pages/**/*.tsx)
    - React components & views (components/*.tsx, views/*.tsx)
    - Vue components & views (*.vue)
    - Svelte components & SvelteKit routes (*.svelte, routes/**/+page.svelte)
    - Angular components (*.component.ts, *.component.html)
    - Astro pages & components (*.astro)
    - Static HTML views (*.html)
    """
    ui_components = []
    seen_names = set()

    # Pre-scan route handlers for template rendering calls (Flask render_template, Express res.render, etc.)
    template_routes: Dict[str, str] = {}
    for src_path, src_content in files.items():
        if not src_content:
            continue
        # Flask render_template per function
        # Split functions or match route definition
        flask_blocks = re.split(r"(?=@\w+\.route)", src_content)
        for block in flask_blocks:
            r_match = re.search(r"""@\w+\.route\(\s*['"]([^'"]+)['"]""", block)
            if not r_match:
                continue
            r_path = r_match.group(1)
            for t_match in re.finditer(r"""render_template\(\s*['"]([^'"]+)['"]""", block):
                t_name = t_match.group(1).split("/")[-1].lower()
                base_t_name = re.sub(r"\.[a-zA-Z0-9]+$", "", t_name)
                # If template not yet recorded, or if this is the root / route for home/index, assign it
                if t_name not in template_routes or (r_path == "/" and "index" in t_name):
                    template_routes[t_name] = r_path
                    template_routes[base_t_name] = r_path

        # Express res.render: router.get('/profile', ... res.render('profile'))
        for m in re.finditer(r"""\.(?:get|post|put|delete|all)\(\s*['"]([^'"]+)['"][\s\S]*?res\.render\(\s*['"]([^'"]+)['"]""", src_content):
            r_path, t_name = m.group(1), m.group(2).split("/")[-1].lower()
            base_t_name = re.sub(r"\.[a-zA-Z0-9]+$", "", t_name)
            if t_name not in template_routes or (r_path == "/" and "index" in t_name):
                template_routes[t_name] = r_path
                template_routes[base_t_name] = r_path

    for path in all_paths:
        clean = path.replace("\\", "/")
        lower = clean.lower()
        parts = clean.split("/")
        filename = parts[-1]
        name_no_ext = re.sub(r"\.[a-zA-Z0-9._]+$", "", filename)
        content = files.get(path, "")

        # 1. HTML / Jinja / Flask / Django / EJS / Handlebars / Blade / ERB / Pug Templates
        template_exts = (
            ".html", ".htm", ".jinja", ".jinja2", ".ejs", ".hbs",
            ".handlebars", ".pug", ".jade", ".twig", ".blade.php", ".erb", ".mustache"
        )
        if lower.endswith(template_exts):
            clean_title = name_no_ext.replace('_', ' ').replace('-', ' ').title()
            if not clean_title.lower().endswith(("template", "view", "page")):
                cname = f"{clean_title} Template"
            else:
                cname = clean_title

            if cname not in seen_names:
                seen_names.add(cname)
                # Resolve route: check template_routes mapping first
                lookup_key = filename.lower()
                base_lookup = name_no_ext.lower()
                if lookup_key in template_routes:
                    route = template_routes[lookup_key]
                elif base_lookup in template_routes:
                    route = template_routes[base_lookup]
                elif "result" in lower or "predict" in lower:
                    route = "/predict"
                elif "index" in lower or "home" in lower:
                    route = "/"
                elif "login" in lower:
                    route = "/login"
                elif "register" in lower or "signup" in lower:
                    route = "/register"
                else:
                    route = f"/{name_no_ext.lower()}"

                ui_components.append({
                    "name": cname,
                    "type": "template",
                    "route": route,
                    "code": content[:50000] if content else f"<!-- UI Template: {clean} -->"
                })

        # 2. Next.js App Router (app/**/page.tsx or app/**/layout.tsx)
        elif "/app/" in lower and any(lower.endswith(p) for p in ("page.tsx", "page.jsx", "page.js", "page.ts")):
            route_part = re.sub(r"^.*?/app", "", clean)
            route = re.sub(r"/page\.(tsx|jsx|js|ts)$", "", route_part) or "/"
            route = re.sub(r"\[(\w+)\]", r":\1", route)
            route = "/" + route.strip("/") if route != "/" else "/"
            seg = [s for s in route.split("/") if s]
            cname = f"{seg[-1].replace(':', '').title()} Page" if seg else "Home Page"
            if cname not in seen_names:
                seen_names.add(cname)
                ui_components.append({
                    "name": cname,
                    "type": "page",
                    "route": route,
                    "code": content[:50000] if content else f"// Next.js Page: {clean}"
                })

        elif "/app/" in lower and any(lower.endswith(p) for p in ("layout.tsx", "layout.jsx", "layout.js", "layout.ts")):
            route_part = re.sub(r"^.*?/app", "", clean)
            route = re.sub(r"/layout\.(tsx|jsx|js|ts)$", "", route_part) or "/"
            route = re.sub(r"\[(\w+)\]", r":\1", route)
            route = "/" + route.strip("/") if route != "/" else "/"
            seg = [s for s in route.split("/") if s]
            cname = f"{seg[-1].replace(':', '').title()} Layout" if seg else "Root Layout"
            if cname not in seen_names:
                seen_names.add(cname)
                ui_components.append({
                    "name": cname,
                    "type": "layout",
                    "route": route,
                    "code": content[:50000] if content else f"// Next.js Layout: {clean}"
                })

        # 3. Next.js / React Pages Router (pages/**/*.tsx)
        elif "/pages/" in lower and lower.endswith((".tsx", ".jsx", ".js")) and not ("/api/" in lower):
            route_part = re.sub(r"^.*?/pages", "", clean)
            route = re.sub(r"\.(tsx|jsx|js)$", "", route_part)
            route = re.sub(r"/index$", "", route) or "/"
            route = re.sub(r"\[(\w+)\]", r":\1", route)
            seg = [s for s in route.split("/") if s]
            cname = f"{seg[-1].replace(':', '').title()} View" if seg else "Index View"
            if cname not in seen_names:
                seen_names.add(cname)
                ui_components.append({
                    "name": cname,
                    "type": "page",
                    "route": route,
                    "code": content[:50000] if content else f"// React Page: {clean}"
                })

        # 4. React / Vue / Svelte / Astro Component or View Files
        elif any(k in lower for k in ("/components/", "/views/", "/widgets/", "/ui/", "/screens/")) and lower.endswith((".tsx", ".jsx", ".vue", ".svelte", ".astro")):
            cname = name_no_ext.replace('_', ' ').replace('-', ' ').title()
            if "_" not in name_no_ext and "-" not in name_no_ext:
                cname = name_no_ext
            ctype = "page" if any(k in lower for k in ("/views/", "/screens/")) else "component"
            if cname not in seen_names and len(cname) > 1 and not cname.startswith("Test"):
                seen_names.add(cname)
                ui_components.append({
                    "name": cname,
                    "type": ctype,
                    "route": f"/{name_no_ext.lower()}" if ctype == "page" else "/",
                    "code": content[:50000] if content else f"// UI Component: {clean}"
                })

        # 5. Vue single file components (*.vue) anywhere
        elif lower.endswith(".vue"):
            cname = name_no_ext
            ctype = "page" if "view" in lower or "page" in lower else "component"
            if cname not in seen_names:
                seen_names.add(cname)
                ui_components.append({
                    "name": cname,
                    "type": ctype,
                    "route": f"/{cname.lower()}",
                    "code": content[:50000] if content else f"<!-- Vue Component: {clean} -->"
                })

        # 6. Svelte components (*.svelte) anywhere
        elif lower.endswith(".svelte"):
            cname = name_no_ext
            ctype = "page" if "routes/" in lower else "component"
            if cname not in seen_names:
                seen_names.add(cname)
                ui_components.append({
                    "name": cname,
                    "type": ctype,
                    "route": f"/{cname.lower()}",
                    "code": content[:50000] if content else f"<!-- Svelte Component: {clean} -->"
                })

        # 7. Angular components (*.component.ts, *.component.html)
        elif lower.endswith((".component.ts", ".component.html")):
            clean_name = re.sub(r"\.component\.(ts|html)$", "", filename).replace('-', ' ').title()
            cname = f"{clean_name} Component"
            if cname not in seen_names:
                seen_names.add(cname)
                ui_components.append({
                    "name": cname,
                    "type": "component",
                    "route": "/",
                    "code": content[:50000] if content else f"// Angular Component: {clean}"
                })

        # 8. Astro pages & components (*.astro)
        elif lower.endswith(".astro"):
            cname = name_no_ext.title()
            ctype = "page" if "/pages/" in lower else "component"
            if cname not in seen_names:
                seen_names.add(cname)
                ui_components.append({
                    "name": cname,
                    "type": ctype,
                    "route": f"/{name_no_ext.lower()}" if ctype == "page" else "/",
                    "code": content[:50000] if content else f"--- Astro Component: {clean} ---"
                })

    return ui_components


# ============================================================================
# MAIN SCAN ENTRYPOINT
# ============================================================================

async def scan_repo(token: str, repo_full_name: str, ref: str = "HEAD") -> Dict[str, Any]:
    """
    Main entry point. Scans a GitHub repo and returns detected tables, routes, and relations.
    Uses a single tarball download first to avoid GitHub API rate limits on larger repos,
    falling back to Git Trees + individual file contents if tarball download fails.
    """
    owner, repo = repo_full_name.split("/", 1)

    # 1. Try single tarball download first
    relevant_files = await fetch_repo_tarball(token, owner, repo, ref)
    all_paths = list(relevant_files.keys())
    total_files = len(all_paths)

    # 2. Fallback to tree + individual fetch if tarball was empty or failed
    if not relevant_files:
        all_tree = await fetch_repo_tree(token, owner, repo)
        all_paths = [f["path"] for f in all_tree]
        total_files = len(all_tree)

        relevant_paths = [p for p in all_paths if is_relevant_file(p)]
        tasks = [fetch_file_content(token, owner, repo, p) for p in relevant_paths]
        contents = await asyncio.gather(*tasks) if tasks else []
        relevant_files = {p: c for p, c in zip(relevant_paths, contents) if c}

    detected_tables = []
    detected_routes = []

    # 3. Parse relevant files
    for path, content in relevant_files.items():
        lower_path = path.lower()

        # Prisma
        if lower_path.endswith(".prisma"):
            detected_tables.extend(parse_prisma_schema(content))

        # Python
        elif lower_path.endswith(".py"):
            # SQLAlchemy
            if "Column(" in content or "mapped_column(" in content or "DeclarativeBase" in content:
                detected_tables.extend(parse_sqlalchemy_models(content))

            # Django
            if "models.Model" in content or "from django.db import models" in content:
                detected_tables.extend(parse_django_models(content))

            # SQLModel
            if "SQLModel" in content:
                detected_tables.extend(parse_sqlmodel_models(content))

            # FastAPI
            if "@app." in content or "@router." in content or "APIRouter" in content:
                detected_routes.extend(
                    parse_fastapi_routes(content, file_path=path, all_file_contents=relevant_files)
                )

            # Flask
            if ".route(" in content or "from flask import" in content or "Blueprint(" in content:
                detected_routes.extend(parse_flask_routes(content))

        # TypeScript / JavaScript
        elif lower_path.endswith((".ts", ".js", ".tsx", ".jsx")):
            # Drizzle ORM
            if any(k in content for k in ("pgTable", "mysqlTable", "sqliteTable")):
                detected_tables.extend(parse_drizzle_schema(content))

            # NestJS Controllers
            if "@Controller" in content:
                detected_routes.extend(parse_nestjs_controllers(content))

            # Express.js
            if "router." in content or ("app." in content and "express" in content.lower()):
                detected_routes.extend(parse_express_routes(content))

    # Next.js file-based routes
    detected_routes.extend(parse_nextjs_routes(all_paths))

    # Deduplicate routes
    seen_routes = set()
    unique_routes = []
    for r in detected_routes:
        key = f"{r['method']}:{r['route']}"
        if key not in seen_routes:
            seen_routes.add(key)
            unique_routes.append(r)

    # Deduplicate tables and merge fields/relations
    tables_by_name: Dict[str, Dict[str, Any]] = {}
    for t in detected_tables:
        tname = t["table_name"]
        if tname not in tables_by_name:
            tables_by_name[tname] = {
                "table_name": tname,
                "fields": list(t.get("fields", [])),
                "relations": list(t.get("relations", []))
            }
        else:
            # Merge fields
            existing_fields = {f["name"] for f in tables_by_name[tname]["fields"]}
            for f in t.get("fields", []):
                if f["name"] not in existing_fields:
                    tables_by_name[tname]["fields"].append(f)
                    existing_fields.add(f["name"])
            # Merge relations
            existing_rels = {r.get("name") for r in tables_by_name[tname]["relations"]}
            for r in t.get("relations", []):
                if r.get("name") not in existing_rels:
                    tables_by_name[tname]["relations"].append(r)
                    existing_rels.add(r.get("name"))

    unique_tables = list(tables_by_name.values())

    # Aggregate all unique relations
    all_relations = []
    seen_rel_names = set()
    for t in unique_tables:
        for r in t.get("relations", []):
            rname = r.get("name")
            if rname not in seen_rel_names:
                seen_rel_names.add(rname)
                all_relations.append(r)

    # Detect UI components across all templates and frontend frameworks
    detected_ui = parse_ui_components(relevant_files, all_paths)

    return {
        "tables": unique_tables,
        "routes": unique_routes,
        "relations": all_relations,
        "ui_components": detected_ui,
        "files_scanned": len(relevant_files),
        "total_files": total_files,
        "files": {p: c for p, c in relevant_files.items() if len(c) < 100000},
    }
