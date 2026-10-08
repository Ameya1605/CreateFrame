"""
ERD & Export Generator for CreateFrame / SpecOS.
Supports:
1. Mermaid ER Diagrams (erDiagram)
2. DBML (Database Markup Language for dbdiagram.io)
3. OpenAPI 3.0.3 API Specification (JSON / YAML compatible)
"""

import re
import json
from typing import Dict, Any, List, Optional


def _clean_ident(name: str) -> str:
    """Ensure identifier is safe for Mermaid and DBML."""
    if not name:
        return "unnamed"
    cleaned = re.sub(r"[^a-zA-Z0-9_]", "_", str(name).strip())
    if cleaned and cleaned[0].isdigit():
        cleaned = "t_" + cleaned
    return cleaned or "unnamed"


def _mermaid_type(raw_type: str) -> str:
    """Map arbitrary SQL/ORM types to clean Mermaid ERD types."""
    t = str(raw_type or "string").lower().strip()
    if any(k in t for k in ("int", "serial", "bigint", "smallint")):
        return "int"
    if any(k in t for k in ("float", "double", "decimal", "numeric", "real")):
        return "float"
    if "bool" in t:
        return "boolean"
    if any(k in t for k in ("datetime", "timestamp")):
        return "datetime"
    if "date" in t:
        return "date"
    if "time" in t:
        return "time"
    if "uuid" in t:
        return "uuid"
    if "json" in t:
        return "json"
    if any(k in t for k in ("text", "longtext")):
        return "text"
    return "string"


def _dbml_type(raw_type: str) -> str:
    """Map arbitrary SQL/ORM types to DBML types."""
    t = str(raw_type or "varchar").lower().strip()
    if any(k in t for k in ("int", "serial", "bigint", "smallint")):
        return "integer"
    if any(k in t for k in ("float", "double", "decimal", "numeric", "real")):
        return "decimal"
    if "bool" in t:
        return "boolean"
    if any(k in t for k in ("datetime", "timestamp")):
        return "timestamp"
    if "date" in t:
        return "date"
    if "uuid" in t:
        return "uuid"
    if "json" in t:
        return "json"
    if "text" in t:
        return "text"
    return "varchar"


def _openapi_type(raw_type: str) -> Dict[str, str]:
    """Map SQL/ORM types to OpenAPI 3.0 schema type & format."""
    t = str(raw_type or "string").lower().strip()
    if any(k in t for k in ("int", "serial", "bigint", "smallint")):
        return {"type": "integer"}
    if any(k in t for k in ("float", "double", "decimal", "numeric", "real")):
        return {"type": "number", "format": "float"}
    if "bool" in t:
        return {"type": "boolean"}
    if any(k in t for k in ("datetime", "timestamp")):
        return {"type": "string", "format": "date-time"}
    if "date" in t:
        return {"type": "string", "format": "date"}
    if "uuid" in t:
        return {"type": "string", "format": "uuid"}
    if "json" in t:
        return {"type": "object"}
    return {"type": "string"}


def _extract_tables(spec: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Extract and normalize tables list from spec."""
    raw_tables = spec.get("database", [])
    normalized = []
    for tbl in raw_tables:
        tname = tbl.get("table_name") or tbl.get("table") or tbl.get("name") or "Unnamed"
        cols = tbl.get("columns") or tbl.get("fields") or []
        normalized_cols = []
        for col in cols:
            col_name = col.get("name") or col.get("column_name") or "col"
            col_type = col.get("type") or "string"
            is_pk = bool(col.get("primary_key") or col.get("pk") or col_name == "id")
            is_fk = bool(col.get("foreign_key") or col.get("fk") or col_name.endswith("_id"))
            is_uk = bool(col.get("unique") or col.get("unique_key") or col.get("uk"))
            is_nullable = bool(col.get("nullable", not is_pk))
            default_val = col.get("default")
            normalized_cols.append({
                "name": col_name,
                "type": col_type,
                "primary_key": is_pk,
                "foreign_key": is_fk,
                "unique": is_uk,
                "nullable": is_nullable,
                "default": default_val,
                "references": col.get("references") or col.get("ref")
            })
        normalized.append({
            "name": tname,
            "columns": normalized_cols,
            "relations": tbl.get("relations", [])
        })
    return normalized


def _extract_relations(spec: Dict[str, Any], tables: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Extract and deduce relations across top-level relations and table definitions."""
    relations = list(spec.get("relations", []))
    seen = set()

    normalized_rels = []
    for rel in relations:
        from_tbl = rel.get("from_table") or rel.get("from") or ""
        to_tbl = rel.get("to_table") or rel.get("to") or ""
        from_f = rel.get("from_field") or rel.get("from_column") or ""
        to_f = rel.get("to_field") or rel.get("to_column") or "id"
        rel_type = str(rel.get("type", "1:N")).upper()
        name = rel.get("name") or f"{from_tbl}_{to_tbl}"

        key = (from_tbl.lower(), to_tbl.lower(), from_f.lower())
        if key not in seen and from_tbl and to_tbl:
            seen.add(key)
            normalized_rels.append({
                "name": name,
                "type": rel_type,
                "from_table": from_tbl,
                "to_table": to_tbl,
                "from_field": from_f,
                "to_field": to_f
            })

    # Deduce from table foreign keys or column references
    known_table_names = {t["name"].lower(): t["name"] for t in tables}
    for tbl in tables:
        tname = tbl["name"]
        for col in tbl["columns"]:
            ref = col.get("references")
            if ref and isinstance(ref, str) and "." in ref:
                target_tbl, target_col = ref.split(".", 1)
                key = (tname.lower(), target_tbl.lower(), col["name"].lower())
                if key not in seen:
                    seen.add(key)
                    normalized_rels.append({
                        "name": f"{tname}_{target_tbl}",
                        "type": "1:N",
                        "from_table": tname,
                        "to_table": target_tbl,
                        "from_field": col["name"],
                        "to_field": target_col
                    })
            elif col["foreign_key"] or (col["name"].endswith("_id") and not col["primary_key"]):
                # Try infer target table name: user_id -> users or user
                target_guess = col["name"][:-3]
                matched_target = None
                for candidate in (target_guess, target_guess + "s", target_guess + "es"):
                    if candidate.lower() in known_table_names:
                        matched_target = known_table_names[candidate.lower()]
                        break
                if matched_target and matched_target.lower() != tname.lower():
                    key = (tname.lower(), matched_target.lower(), col["name"].lower())
                    if key not in seen:
                        seen.add(key)
                        normalized_rels.append({
                            "name": f"{tname}_{matched_target}",
                            "type": "1:N",
                            "from_table": tname,
                            "to_table": matched_target,
                            "from_field": col["name"],
                            "to_field": "id"
                        })

    return normalized_rels


def generate_mermaid_erd(spec: Dict[str, Any]) -> str:
    """
    Generate Mermaid erDiagram representation from spec.
    """
    tables = _extract_tables(spec)
    relations = _extract_relations(spec, tables)

    lines = ["erDiagram"]

    # Relations first
    for rel in relations:
        f_tbl = _clean_ident(rel["to_table"])  # One side (parent)
        t_tbl = _clean_ident(rel["from_table"])  # Many side (child)
        rel_type = rel["type"]
        rel_label = _clean_ident(rel.get("name") or "references")

        if "1:1" in rel_type or "ONE_TO_ONE" in rel_type:
            connector = "||--||"
        elif "N:M" in rel_type or "MANY_TO_MANY" in rel_type:
            connector = "}o--o{"
        else:
            # Default 1:N (One parent has zero-or-more children)
            connector = "||--o{"

        lines.append(f'    {f_tbl} {connector} {t_tbl} : "{rel_label}"')

    # Tables and columns
    for tbl in tables:
        tname = _clean_ident(tbl["name"])
        lines.append(f"    {tname} {{")
        for col in tbl["columns"]:
            cname = _clean_ident(col["name"])
            ctype = _mermaid_type(col["type"])
            flags = []
            if col["primary_key"]:
                flags.append("PK")
            elif col["foreign_key"]:
                flags.append("FK")
            elif col["unique"]:
                flags.append("UK")
            
            flag_str = f" {','.join(flags)}" if flags else ""
            lines.append(f"        {ctype} {cname}{flag_str}")
        lines.append("    }")

    return "\n".join(lines)


def generate_dbml(spec: Dict[str, Any]) -> str:
    """
    Generate DBML (Database Markup Language) representation from spec.
    """
    tables = _extract_tables(spec)
    relations = _extract_relations(spec, tables)

    lines = [
        "// DBML Specification generated by CreateFrame / SpecOS",
        f"// Project: {spec.get('project', {}).get('name', 'CreateFrame App')}",
        ""
    ]

    # Tables
    for tbl in tables:
        tname = _clean_ident(tbl["name"])
        lines.append(f"Table {tname} {{")
        for col in tbl["columns"]:
            cname = _clean_ident(col["name"])
            ctype = _dbml_type(col["type"])
            settings = []
            if col["primary_key"]:
                settings.append("pk")
                if ctype == "integer" and col["name"] == "id":
                    settings.append("increment")
            if col["unique"] and not col["primary_key"]:
                settings.append("unique")
            if not col["nullable"] and not col["primary_key"]:
                settings.append("not null")
            if col["default"] is not None:
                dval = str(col["default"]).strip()
                settings.append(f"default: `{dval}`")

            setting_str = f" [{', '.join(settings)}]" if settings else ""
            lines.append(f"  {cname} {ctype}{setting_str}")
        lines.append("}\n")

    # References
    if relations:
        lines.append("// Relationships")
        for rel in relations:
            parent = _clean_ident(rel["to_table"])
            parent_f = _clean_ident(rel.get("to_field") or "id")
            child = _clean_ident(rel["from_table"])
            child_f = _clean_ident(rel.get("from_field") or f"{parent}_id")

            rel_type = rel["type"]
            if "1:1" in rel_type:
                rel_op = "-"
            else:
                rel_op = "<"

            lines.append(f"Ref: {child}.{child_f} {rel_op} {parent}.{parent_f}")
        lines.append("")

    return "\n".join(lines)


def generate_openapi_spec(spec: Dict[str, Any]) -> Dict[str, Any]:
    """
    Generate an OpenAPI 3.0.3 specification dict from spec endpoints and database tables.
    """
    project_info = spec.get("project", {})
    title = project_info.get("name") or "CreateFrame API"
    description = project_info.get("description") or "API Specification generated by CreateFrame"
    version = str(spec.get("version") or "1.0.0")

    tables = _extract_tables(spec)
    endpoints = spec.get("endpoints", [])

    schemas = {}
    for tbl in tables:
        tname = tbl["name"]
        props = {}
        required = []
        for col in tbl["columns"]:
            col_name = col["name"]
            type_info = _openapi_type(col["type"])
            props[col_name] = type_info
            if not col["nullable"]:
                required.append(col_name)

        schemas[tname] = {
            "type": "object",
            "properties": props,
            "required": required if required else None
        }
        # Clean None values
        if schemas[tname]["required"] is None:
            del schemas[tname]["required"]

    paths: Dict[str, Any] = {}
    for ep in endpoints:
        route = ep.get("route") or ep.get("path") or "/"
        method = str(ep.get("method") or "GET").lower()
        if not route.startswith("/"):
            route = "/" + route

        # Convert path parameters like :id or <id> to {id}
        norm_route = re.sub(r":([a-zA-Z_][a-zA-Z0-9_]*)", r"{\1}", route)
        norm_route = re.sub(r"<(?:\w+:)?([a-zA-Z_][a-zA-Z0-9_]*)>", r"{\1}", norm_route)

        if norm_route not in paths:
            paths[norm_route] = {}

        # Extract parameters from route
        path_params = re.findall(r"\{([a-zA-Z0-9_]+)\}", norm_route)
        parameters = []
        for p in path_params:
            parameters.append({
                "name": p,
                "in": "path",
                "required": True,
                "schema": {"type": "string" if not p.endswith("id") else "integer"}
            })

        summary = ep.get("summary") or ep.get("description") or f"{method.upper()} {norm_route}"
        linked_table = ep.get("linked_table")

        op_def: Dict[str, Any] = {
            "summary": summary,
            "operationId": f"{method}_{norm_route.strip('/').replace('/', '_') or 'root'}",
            "responses": {
                "200": {
                    "description": "Successful operation"
                }
            }
        }

        if parameters:
            op_def["parameters"] = parameters

        if linked_table and linked_table in schemas:
            if method in ("post", "put", "patch"):
                op_def["requestBody"] = {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {"$ref": f"#/components/schemas/{linked_table}"}
                        }
                    }
                }
            op_def["responses"]["200"]["content"] = {
                "application/json": {
                    "schema": {
                        "type": "array",
                        "items": {"$ref": f"#/components/schemas/{linked_table}"}
                    } if method == "get" and "{" not in norm_route else {
                        "$ref": f"#/components/schemas/{linked_table}"
                    }
                }
            }

        if ep.get("auth_required"):
            op_def["security"] = [{"BearerAuth": []}]

        paths[norm_route][method] = op_def

    openapi_doc = {
        "openapi": "3.0.3",
        "info": {
            "title": title,
            "description": description,
            "version": version
        },
        "paths": paths,
        "components": {
            "schemas": schemas,
            "securitySchemes": {
                "BearerAuth": {
                    "type": "http",
                    "scheme": "bearer",
                    "bearerFormat": "JWT"
                }
            }
        }
    }

    return openapi_doc


def export_all_formats(spec: Dict[str, Any]) -> Dict[str, Any]:
    """
    Generate Mermaid, DBML, and OpenAPI export objects along with summary statistics.
    """
    tables = _extract_tables(spec)
    relations = _extract_relations(spec, tables)
    endpoints = spec.get("endpoints", [])

    return {
        "mermaid": generate_mermaid_erd(spec),
        "dbml": generate_dbml(spec),
        "openapi": generate_openapi_spec(spec),
        "stats": {
            "tables_count": len(tables),
            "relations_count": len(relations),
            "endpoints_count": len(endpoints),
        }
    }
