"""
Spec v2: Versioned JSON Schema specification for CreateFrame / SpecOS.
Defines rich columns, relations (1:N, M:N, onDelete), enums, and endpoints linked to tables with auth requirements.
"""

import json
from typing import Dict, Any, List, Optional, Tuple, Union
from pydantic import BaseModel, Field

SPEC_VERSION = "2.0"

# Formal JSON Schema definition (Draft 2020-12 / Draft 7 compatible)
SPEC_V2_JSON_SCHEMA: Dict[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "SpecOS Specification v2",
    "description": "Versioned specification schema defining data layer, relations, enums, API endpoints, UI components, and features.",
    "type": "object",
    "required": ["version", "project", "database", "endpoints"],
    "properties": {
        "version": {
            "type": "string",
            "enum": ["2.0"],
            "description": "Specification format version"
        },
        "project": {
            "type": "object",
            "required": ["name", "repo_url"],
            "properties": {
                "name": {"type": "string", "minLength": 1},
                "repo_url": {"type": "string"},
                "project_type": {"type": "string", "default": "saas"},
                "is_ai_enabled": {"type": "boolean", "default": True}
            }
        },
        "structure": {
            "type": "string",
            "default": "monorepo"
        },
        "apps": {
            "type": "array",
            "items": {"type": "string"},
            "default": ["api", "web"]
        },
        "enums": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["name", "values"],
                "properties": {
                    "name": {"type": "string"},
                    "values": {
                        "type": "array",
                        "items": {"type": "string"},
                        "minItems": 1
                    }
                }
            },
            "default": []
        },
        "relations": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["name", "type", "from_table", "from_field", "to_table", "to_field"],
                "properties": {
                    "name": {"type": "string"},
                    "type": {
                        "type": "string",
                        "enum": ["1:N", "N:1", "1:1", "M:N"]
                    },
                    "from_table": {"type": "string"},
                    "from_field": {"type": "string"},
                    "to_table": {"type": "string"},
                    "to_field": {"type": "string"},
                    "on_delete": {
                        "type": "string",
                        "enum": ["CASCADE", "SET_NULL", "RESTRICT", "NO_ACTION"],
                        "default": "CASCADE"
                    },
                    "on_update": {
                        "type": "string",
                        "enum": ["CASCADE", "SET_NULL", "RESTRICT", "NO_ACTION"],
                        "default": "CASCADE"
                    }
                }
            },
            "default": []
        },
        "database": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["table_name", "columns"],
                "properties": {
                    "table_name": {"type": "string", "minLength": 1},
                    "columns": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "required": ["name", "type"],
                            "properties": {
                                "name": {"type": "string"},
                                "type": {"type": "string"},
                                "primary_key": {"type": "boolean", "default": False},
                                "nullable": {"type": "boolean", "default": False},
                                "unique": {"type": "boolean", "default": False},
                                "default": {},
                                "index": {"type": "boolean", "default": False}
                            }
                        }
                    },
                    "relations": {
                        "type": "array",
                        "items": {"$ref": "#/properties/relations/items"},
                        "default": []
                    },
                    "code": {"type": ["string", "null"]}
                }
            }
        },
        "endpoints": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["method", "route"],
                "properties": {
                    "method": {
                        "type": "string",
                        "enum": ["GET", "POST", "PUT", "PATCH", "DELETE", "get", "post", "put", "patch", "delete"]
                    },
                    "route": {"type": "string"},
                    "linked_table": {"type": ["string", "null"]},
                    "auth_required": {"type": "boolean", "default": True},
                    "auth_type": {
                        "type": "string",
                        "enum": ["bearer", "api_key", "cookie", "none"],
                        "default": "bearer"
                    },
                    "roles": {
                        "type": "array",
                        "items": {"type": "string"},
                        "default": []
                    },
                    "request_schema": {"type": "object", "default": {}},
                    "response_schema": {"type": "object", "default": {}},
                    "code": {"type": ["string", "null"]}
                }
            }
        },
        "ui_components": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["name", "type"],
                "properties": {
                    "name": {"type": "string"},
                    "type": {"type": "string", "enum": ["page", "component", "layout"]},
                    "route": {"type": ["string", "null"]},
                    "code": {"type": ["string", "null"]}
                }
            },
            "default": []
        },
        "features": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["name"],
                "properties": {
                    "name": {"type": "string"},
                    "status": {"type": "string", "default": "mvp"},
                    "description": {"type": ["string", "null"]}
                }
            },
            "default": []
        },
        "prompts": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["name", "template"],
                "properties": {
                    "name": {"type": "string"},
                    "template": {"type": "string"}
                }
            },
            "default": []
        }
    }
}


# ─── Pydantic Models for Spec v2 ──────────────────────────────────────────────

class ColumnV2(BaseModel):
    name: str
    type: str
    primary_key: bool = False
    nullable: bool = False
    unique: bool = False
    default: Optional[Any] = None
    index: bool = False


class RelationV2(BaseModel):
    name: str
    type: str = "1:N"  # "1:N", "N:1", "1:1", "M:N"
    from_table: str
    from_field: str
    to_table: str
    to_field: str
    on_delete: str = "CASCADE"  # "CASCADE", "SET_NULL", "RESTRICT", "NO_ACTION"
    on_update: Optional[str] = "CASCADE"


class EnumV2(BaseModel):
    name: str
    values: List[str]


class TableV2(BaseModel):
    table_name: str
    columns: List[ColumnV2]
    relations: List[RelationV2] = Field(default_factory=list)
    code: Optional[str] = None


class EndpointV2(BaseModel):
    method: str
    route: str
    linked_table: Optional[str] = None
    auth_required: bool = True
    auth_type: str = "bearer"
    roles: List[str] = Field(default_factory=list)
    request_schema: Dict[str, Any] = Field(default_factory=dict)
    response_schema: Dict[str, Any] = Field(default_factory=dict)
    code: Optional[str] = None


class UIComponentV2(BaseModel):
    name: str
    type: str = "component"
    route: Optional[str] = None
    code: Optional[str] = None


class FeatureV2(BaseModel):
    name: str
    status: str = "mvp"
    description: Optional[str] = None


class PromptV2(BaseModel):
    name: str
    template: str


class ProjectMetaV2(BaseModel):
    name: str
    repo_url: str
    project_type: str = "saas"
    is_ai_enabled: bool = True


class SpecV2(BaseModel):
    version: str = SPEC_VERSION
    project: ProjectMetaV2
    structure: str = "monorepo"
    apps: List[str] = Field(default_factory=lambda: ["api", "web"])
    enums: List[EnumV2] = Field(default_factory=list)
    relations: List[RelationV2] = Field(default_factory=list)
    database: List[TableV2] = Field(default_factory=list)
    endpoints: List[EndpointV2] = Field(default_factory=list)
    ui_components: List[UIComponentV2] = Field(default_factory=list)
    features: List[FeatureV2] = Field(default_factory=list)
    prompts: List[PromptV2] = Field(default_factory=list)


# ─── Normalizer & Validator Functions ─────────────────────────────────────────

def normalize_column_dict(col: Dict[str, Any]) -> Dict[str, Any]:
    """Ensures a field/column dictionary conforms to ColumnV2 schema."""
    name = col.get("name", "unnamed")
    col_type = col.get("type", "string")
    is_pk = bool(col.get("primary_key") or col.get("is_primary") or name == "id")
    
    default_val = col.get("default")
    if default_val is None and is_pk:
        if col_type.lower() in ("integer", "int"):
            default_val = "autoincrement()"
        elif col_type.lower() == "uuid":
            default_val = "uuid()"

    return {
        "name": name,
        "type": col_type,
        "primary_key": is_pk,
        "nullable": bool(col.get("nullable", False)),
        "unique": bool(col.get("unique", False)),
        "default": default_val,
        "index": bool(col.get("index", False))
    }


def normalize_endpoint_dict(ep: Dict[str, Any], known_tables: Optional[List[str]] = None) -> Dict[str, Any]:
    """Ensures an endpoint dictionary conforms to EndpointV2 schema."""
    method = ep.get("method", "GET").upper()
    route = ep.get("route", "/")
    
    linked_table = ep.get("linked_table")
    if not linked_table and known_tables:
        # Infer linked table from route, e.g. /users -> User or users
        clean_parts = [p.strip("{}") for p in route.split("/") if p]
        for part in clean_parts:
            match = next((t for t in known_tables if t.lower() in (part.lower(), part.rstrip("s").lower())), None)
            if match:
                linked_table = match
                break

    auth_required = ep.get("auth_required")
    if auth_required is None:
        # Defaults to true unless public route like health or auth
        auth_required = False if any(p in route.lower() for p in ["/auth", "/health", "/public", "/webhook"]) else True

    req_schema = ep.get("request_schema")
    if isinstance(req_schema, str) and req_schema.strip():
        try: req_schema = json.loads(req_schema)
        except Exception: req_schema = {}
    elif not isinstance(req_schema, dict):
        req_schema = {}

    res_schema = ep.get("response_schema")
    if isinstance(res_schema, str) and res_schema.strip():
        try: res_schema = json.loads(res_schema)
        except Exception: res_schema = {}
    elif not isinstance(res_schema, dict):
        res_schema = {}

    return {
        "method": method,
        "route": route,
        "linked_table": linked_table,
        "auth_required": bool(auth_required),
        "auth_type": ep.get("auth_type", "bearer"),
        "roles": ep.get("roles", []),
        "request_schema": req_schema,
        "response_schema": res_schema,
        "code": ep.get("code")
    }


def normalize_v1_to_v2(spec: Dict[str, Any]) -> Dict[str, Any]:
    """
    Upgrades an older or partial spec dict to standard Spec v2 format.
    Maintains 100% backward compatibility for all fields.
    """
    proj = spec.get("project", {})
    if not isinstance(proj, dict):
        proj = {"name": "App", "repo_url": ""}

    tables_input = spec.get("database") or spec.get("tables") or []
    table_names = [t.get("table_name") or t.get("table", "") for t in tables_input if isinstance(t, dict)]
    table_names = [t for t in table_names if t]

    normalized_tables = []
    database_relations = list(spec.get("relations", []))

    for t in tables_input:
        if not isinstance(t, dict): continue
        tname = t.get("table_name") or t.get("table") or "Unnamed"
        raw_cols = t.get("columns") or t.get("fields") or []
        cols = [normalize_column_dict(c) for c in raw_cols if isinstance(c, dict)]
        
        # Ensure at least one primary key exists
        if not any(c["primary_key"] for c in cols):
            cols.insert(0, {
                "name": "id",
                "type": "uuid",
                "primary_key": True,
                "nullable": False,
                "unique": False,
                "default": "uuid()",
                "index": False
            })

        tbl_relations = list(t.get("relations", []))
        normalized_tables.append({
            "table_name": tname,
            "columns": cols,
            "fields": cols, # alias for backward compatibility
            "relations": tbl_relations,
            "code": t.get("code")
        })

    endpoints_input = spec.get("endpoints", [])
    normalized_endpoints = [
        normalize_endpoint_dict(ep, known_tables=table_names)
        for ep in endpoints_input if isinstance(ep, dict)
    ]

    return {
        "version": SPEC_VERSION,
        "project": {
            "name": proj.get("name", "Unnamed"),
            "repo_url": proj.get("repo_url", ""),
            "project_type": proj.get("project_type", "saas"),
            "is_ai_enabled": bool(proj.get("is_ai_enabled", True))
        },
        "structure": spec.get("structure", "monorepo"),
        "apps": spec.get("apps", ["api", "web"]),
        "enums": spec.get("enums", []),
        "relations": database_relations,
        "database": normalized_tables,
        "endpoints": normalized_endpoints,
        "ui_components": spec.get("ui_components", []),
        "features": spec.get("features", []),
        "prompts": spec.get("prompts", [])
    }


def validate_spec_v2(spec: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """
    Validates a spec dictionary against Spec v2 rules.
    Returns (is_valid, list_of_error_messages).
    """
    errors = []

    if not isinstance(spec, dict):
        return False, ["Specification must be a JSON object"]

    if spec.get("version") != "2.0":
        errors.append(f"Invalid version '{spec.get('version')}'. Expected '2.0'")

    proj = spec.get("project")
    if not isinstance(proj, dict) or not proj.get("name"):
        errors.append("Field 'project.name' is required")

    database = spec.get("database")
    if not isinstance(database, list):
        errors.append("Field 'database' must be a list of tables")
    else:
        table_names = set()
        for idx, table in enumerate(database):
            if not isinstance(table, dict):
                errors.append(f"database[{idx}] must be an object")
                continue
            tname = table.get("table_name")
            if not tname:
                errors.append(f"database[{idx}] missing 'table_name'")
                continue
            if tname in table_names:
                errors.append(f"Duplicate table name '{tname}'")
            table_names.add(tname)

            columns = table.get("columns") or table.get("fields")
            if not isinstance(columns, list) or len(columns) == 0:
                errors.append(f"Table '{tname}' must define at least one column")
            else:
                pks = [c for c in columns if isinstance(c, dict) and c.get("primary_key")]
                if len(pks) == 0:
                    errors.append(f"Table '{tname}' must have at least one primary key")
                elif len(pks) > 1:
                    errors.append(f"Table '{tname}' has multiple primary keys: {[c.get('name') for c in pks]}")

    endpoints = spec.get("endpoints")
    if not isinstance(endpoints, list):
        errors.append("Field 'endpoints' must be a list")
    else:
        routes_seen = set()
        for idx, ep in enumerate(endpoints):
            if not isinstance(ep, dict):
                errors.append(f"endpoints[{idx}] must be an object")
                continue
            method = str(ep.get("method", "")).upper()
            route = ep.get("route")
            if not method or not route:
                errors.append(f"endpoints[{idx}] missing method or route")
                continue
            key = (method, route)
            if key in routes_seen:
                errors.append(f"Duplicate endpoint '{method} {route}'")
            routes_seen.add(key)

    relations = spec.get("relations", [])
    if isinstance(relations, list):
        tbl_names = {t.get("table_name") for t in (database or []) if isinstance(t, dict)}
        for idx, rel in enumerate(relations):
            if not isinstance(rel, dict): continue
            from_t = rel.get("from_table")
            to_t = rel.get("to_table")
            if from_t and from_t not in tbl_names:
                errors.append(f"Relation '{rel.get('name', idx)}' references non-existent from_table '{from_t}'")
            if to_t and to_t not in tbl_names:
                errors.append(f"Relation '{rel.get('name', idx)}' references non-existent to_table '{to_t}'")

    return (len(errors) == 0, errors)
