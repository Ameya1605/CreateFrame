import re
import json
from typing import Dict, Any, List, Optional

def _format_default_value(val: Any, prisma_type: str) -> str:
    if val is None:
        return ""
    str_val = str(val).strip()
    if str_val in ("uuid()", "autoincrement()", "now()", "cuid()"):
        return f" @default({str_val})"
    if prisma_type == "Boolean":
        return f" @default({'true' if str_val.lower() in ('true', '1') else 'false'})"
    if prisma_type in ("Int", "Float"):
        return f" @default({str_val})"
    # String or Enum
    return f' @default("{str_val}")'


def generate_prisma_schema(spec: Dict[str, Any]) -> str:
    schema = """// This is your Prisma schema file,
// learn more about it in the docs: https://pris.ly/d/prisma-schema

generator client {
  provider = "prisma-client-js"
}

datasource db {
  provider = "postgresql"
  url      = env("DATABASE_URL")
}
"""
    
    # Simple mapping from CreateFrame types to Prisma types
    type_mapping = {
        "string": "String",
        "text": "String",
        "integer": "Int",
        "int": "Int",
        "boolean": "Boolean",
        "bool": "Boolean",
        "json": "Json",
        "uuid": "String",
        "datetime": "DateTime",
        "date": "DateTime",
        "float": "Float",
        "decimal": "Decimal",
    }

    # 1. Generate Enums
    enums = spec.get("enums", [])
    known_enums = set()
    for enum_def in enums:
        ename = enum_def.get("name")
        evalues = enum_def.get("values", [])
        if ename and evalues:
            known_enums.add(ename)
            schema += f"\nenum {ename} {{\n"
            for v in evalues:
                schema += f"  {v}\n"
            schema += "}\n"

    # Gather all relations across spec
    all_relations = list(spec.get("relations", []))
    for tbl in spec.get("database", []):
        all_relations.extend(tbl.get("relations", []))

    # 2. Generate Models
    for table in spec.get("database", []):
        table_name = table.get("table_name") or table.get("table") or "Unnamed"
        schema += f"\nmodel {table_name} {{\n"
        
        has_id = False
        columns = table.get("columns") or table.get("fields") or []
        indexes = []

        for field in columns:
            field_name = field["name"]
            raw_type = str(field.get("type", "string"))
            field_type_lower = raw_type.lower()
            
            # Check if type is an enum
            if raw_type in known_enums:
                prisma_type = raw_type
            else:
                prisma_type = type_mapping.get(field_type_lower, "String")
            
            is_pk = bool(field.get("primary_key") or field.get("is_primary") or field_name == "id")
            is_nullable = bool(field.get("nullable", False))
            is_unique = bool(field.get("unique", False))
            default_val = field.get("default")
            is_index = bool(field.get("index", False))

            modifiers = ""
            if is_pk:
                has_id = True
                if field_type_lower in ("integer", "int"):
                    modifiers += " @id @default(autoincrement())"
                elif field_type_lower == "uuid":
                    modifiers += " @id @default(uuid())"
                else:
                    modifiers += " @id @default(uuid())"
            else:
                if is_nullable:
                    prisma_type += "?"
                if is_unique:
                    modifiers += " @unique"
                if default_val is not None:
                    modifiers += _format_default_value(default_val, prisma_type.rstrip("?"))

            if is_index and not is_pk:
                indexes.append(field_name)

            schema += f"  {field_name} {prisma_type}{modifiers}\n"
        
        if not has_id:
            # Fallback ID if no primary key specified
            schema += "  id String @id @default(uuid())\n"

        # Generate relation fields on this model
        for rel in all_relations:
            rel_name = rel.get("name", "relation")
            rel_type = rel.get("type", "1:N")
            from_t = rel.get("from_table")
            to_t = rel.get("to_table")
            from_f = rel.get("from_field", "id")
            to_f = rel.get("to_field", "id")
            on_del = rel.get("on_delete", "CASCADE").capitalize()
            if on_del == "Set_null": on_del = "SetNull"
            elif on_del == "No_action": on_del = "NoAction"

            if from_t == table_name:
                # This model has the foreign key (child in 1:N)
                field_rel_name = to_t.lower()
                schema += f"  {field_rel_name} {to_t} @relation(fields: [{from_f}], references: [{to_f}], onDelete: {on_del})\n"
            elif to_t == table_name:
                # This model is the referenced parent
                if rel_type in ("1:N", "M:N"):
                    schema += f"  {from_t.lower()}s {from_t}[]\n"
                elif rel_type in ("1:1", "N:1"):
                    schema += f"  {from_t.lower()} {from_t}?\n"

        for idx_col in indexes:
            schema += f"  @@index([{idx_col}])\n"

        schema += "}\n"

    return schema


def _sanitize_name(name: str) -> str:
    cleaned = re.sub(r'[^a-zA-Z0-9_]', '_', name)
    return re.sub(r'_+', '_', cleaned).strip('_')


def _build_model_name(route: str, method: str) -> str:
    clean_route = re.sub(r'\{(\w+)\}', r'by_\1', route)
    parts = [re.sub(r'[^a-zA-Z0-9]', '', p) for p in clean_route.split('/') if p]
    base = "".join([p.capitalize() for p in parts if p]) or "Root"
    return f"{base}{method.capitalize()}"


def _build_fn_name(route: str, method: str) -> str:
    clean_route = re.sub(r'\{(\w+)\}', r'\1', route)
    clean_parts = [_sanitize_name(p) for p in clean_route.split('/') if p]
    fn_body = "_".join([p for p in clean_parts if p]) or "root"
    return f"{method.lower()}_{fn_body}"


def _map_pydantic_type(val: Any) -> str:
    if isinstance(val, str):
        v = val.lower()
        if v in ("string", "str", "text"): return "str"
        if v in ("integer", "int"): return "int"
        if v in ("boolean", "bool"): return "bool"
        if v in ("float", "number"): return "float"
        if v in ("list", "array"): return "List[Any]"
        if v in ("dict", "object", "json"): return "Dict[str, Any]"
    elif isinstance(val, dict):
        return _map_pydantic_type(val.get("type", "Any"))
    return "Any"


def _parse_schema(raw_schema: Any) -> Dict[str, Any]:
    if isinstance(raw_schema, dict):
        return raw_schema
    if isinstance(raw_schema, str) and raw_schema.strip():
        try:
            parsed = json.loads(raw_schema)
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            pass
    return {}


def generate_fastapi_code(spec: Dict[str, Any]) -> str:
    code = """from fastapi import FastAPI, HTTPException, Depends, status
from pydantic import BaseModel
from typing import List, Optional, Any, Dict

app = FastAPI()

# Placeholder dependencies
async def get_current_user():
    # Enforces authentication when auth_required is enabled
    return {"id": 1, "username": "authenticated_user"}

async def get_db():
    yield None

# Pydantic Models
"""
    
    defined_models = set()
    endpoints = spec.get("endpoints", [])

    # First pass: generate models
    for endpoint in endpoints:
        method = endpoint.get("method", "get").lower()
        route = endpoint.get("route", "/")
        model_name = _build_model_name(route, method)
        
        req_schema = _parse_schema(endpoint.get("request_schema"))
        if req_schema and f"{model_name}Request" not in defined_models:
            code += f"\nclass {model_name}Request(BaseModel):\n"
            for k, v in req_schema.items():
                py_type = _map_pydantic_type(v)
                code += f"    {_sanitize_name(k)}: {py_type}\n"
            defined_models.add(f"{model_name}Request")
        
        res_schema = _parse_schema(endpoint.get("response_schema"))
        if res_schema and f"{model_name}Response" not in defined_models:
            code += f"\nclass {model_name}Response(BaseModel):\n"
            for k, v in res_schema.items():
                py_type = _map_pydantic_type(v)
                code += f"    {_sanitize_name(k)}: {py_type}\n"
            defined_models.add(f"{model_name}Response")

    code += "\n# API Routes\n"

    # Second pass: generate route handlers
    used_fn_names = set()
    for endpoint in endpoints:
        method = endpoint.get("method", "get").lower()
        route = endpoint.get("route", "/")
        linked_table = endpoint.get("linked_table")
        auth_required = bool(endpoint.get("auth_required", True))
        
        model_name = _build_model_name(route, method)
        base_fn_name = _build_fn_name(route, method)
        
        fn_name = base_fn_name
        counter = 1
        while fn_name in used_fn_names:
            fn_name = f"{base_fn_name}_{counter}"
            counter += 1
        used_fn_names.add(fn_name)

        # Arguments list
        path_params = re.findall(r'\{(\w+)\}', route)
        args = [f"{p}: str" for p in path_params]
        
        req_schema = _parse_schema(endpoint.get("request_schema"))
        if req_schema:
            args.append(f"body: {model_name}Request")
        
        if auth_required:
            args.append("current_user: Any = Depends(get_current_user)")
        
        if linked_table:
            args.append("db: Any = Depends(get_db)")

        res_schema = _parse_schema(endpoint.get("response_schema"))
        res_type = f", response_model={model_name}Response" if res_schema else ""

        args_str = ", ".join(args)

        code += f"\n@app.{method}('{route}'{res_type})\n"
        code += f"async def {fn_name}({args_str}):\n"
        if linked_table:
            code += f"    # Target Entity: {linked_table}\n"
        code += f"    # TODO: Implement logic for {route}\n"
        code += f"    return {{}}\n"

    return code
