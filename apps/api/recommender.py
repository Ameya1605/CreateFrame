"""
CreateFrame Recommendation Engine
=============================
Context-aware, cross-layer recommendation engine that understands what
the user is building and makes specific, non-generic suggestions.

Pipeline:
  1. Context Assembly   — Build full project snapshot
  2. Project Classifier — Detect app archetype (saas/ecommerce/social/etc.)
  3. Gap Analyzer       — Deterministic cross-layer consistency checks
  4. Pattern Matcher    — Industry best practices per archetype
  5. Ranker             — Merge, dedupe, sort by severity + confidence
"""

import os
import json
import hashlib
import logging
from typing import List, Dict, Any, Optional
from difflib import SequenceMatcher

logging.basicConfig(level=logging.INFO, format="%(levelname)s:recommender: %(message)s")
log = logging.getLogger("recommender")

PATTERNS_DIR = os.path.join(os.path.dirname(__file__), "patterns")

# ─── Data Structures ──────────────────────────────────────────────────────────

class Recommendation:
    """A single, actionable recommendation."""

    def __init__(
        self,
        rule_id: str,
        layer: str,
        rec_type: str,
        severity: str,
        title: str,
        description: str,
        action: Optional[Dict[str, Any]] = None,
        confidence: float = 1.0,
    ):
        self.rule_id = rule_id
        self.layer = layer          # database | api | ui | features | cross-layer
        self.type = rec_type        # missing_item | improvement | best_practice | security
        self.severity = severity    # critical | recommended | nice_to_have
        self.title = title
        self.description = description
        self.action = action or {}
        self.confidence = confidence
        # Deterministic ID based on rule + context
        self.id = hashlib.md5(f"{rule_id}:{title}".encode()).hexdigest()[:12]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "rule_id": self.rule_id,
            "layer": self.layer,
            "type": self.type,
            "severity": self.severity,
            "title": self.title,
            "description": self.description,
            "action": self.action,
            "confidence": self.confidence,
        }


# ─── Pattern Loader ───────────────────────────────────────────────────────────

_pattern_cache: Dict[str, Any] = {}

def load_pattern(name: str) -> Dict[str, Any]:
    """Load a pattern JSON file from the patterns/ directory."""
    if name in _pattern_cache:
        return _pattern_cache[name]
    path = os.path.join(PATTERNS_DIR, f"{name}.json")
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    _pattern_cache[name] = data
    return data


# ─── Context Assembly ─────────────────────────────────────────────────────────

def assemble_context(project: Any, features: List[Any], schemas: List[Any],
                     endpoints: List[Any], ui_components: List[Any]) -> Dict[str, Any]:
    """Build a full project snapshot for the recommendation engine."""

    tables = []
    for s in schemas:
        fields = s.fields if isinstance(s.fields, list) else []
        tables.append({
            "id": s.id,
            "table_name": s.table_name,
            "fields": fields,
            "field_names": [f.get("name", "") if isinstance(f, dict) else "" for f in fields],
        })

    eps = []
    for e in endpoints:
        eps.append({
            "id": e.id,
            "method": e.method.upper() if e.method else "GET",
            "route": e.route or "/",
        })

    feats = []
    for f in features:
        feats.append({
            "id": f.id,
            "name": f.name,
            "status": getattr(f, "status", "planned"),
            "description": getattr(f, "description", "") or "",
        })

    ui = []
    for c in ui_components:
        ui.append({
            "id": c.id,
            "name": c.name,
            "type": getattr(c, "type", "component"),
        })

    # Cross-layer relationship detection
    orphan_tables = _find_orphan_tables(tables, eps)
    orphan_endpoints = _find_orphan_endpoints(eps, tables)
    missing_ui = _find_missing_ui(feats, ui)

    # Completeness scores
    scores = _compute_completeness(feats, tables, eps, ui)

    return {
        "project_name": project.name,
        "project_type": getattr(project, "project_type", None) or "unknown",
        "features": feats,
        "tables": tables,
        "endpoints": eps,
        "ui_components": ui,
        "relationships": {
            "orphan_tables": orphan_tables,
            "orphan_endpoints": orphan_endpoints,
            "missing_ui": missing_ui,
        },
        "completeness_scores": scores,
    }


def _fuzzy_match(a: str, b: str, threshold: float = 0.5) -> bool:
    """Check if two strings are similar enough."""
    a, b = a.lower().strip(), b.lower().strip()
    if a in b or b in a:
        return True
    # Check word overlap
    a_words = set(a.replace("-", " ").replace("_", " ").split())
    b_words = set(b.replace("-", " ").replace("_", " ").split())
    if a_words & b_words:
        return True
    return SequenceMatcher(None, a, b).ratio() >= threshold


def _route_references_table(route: str, table_name: str) -> bool:
    """Check if an API route references a table (fuzzy)."""
    table_lower = table_name.lower().rstrip("s")  # Singularize rough
    route_lower = route.lower()
    # /users -> user, /products/:id -> product
    route_parts = [p for p in route_lower.split("/") if p and not p.startswith(":")]
    for part in route_parts:
        part_singular = part.rstrip("s")
        if part_singular == table_lower or part == table_name.lower():
            return True
    return False


def _find_orphan_tables(tables: List[Dict], endpoints: List[Dict]) -> List[str]:
    """Tables with no API endpoints referencing them."""
    orphans = []
    for t in tables:
        has_route = any(_route_references_table(e["route"], t["table_name"]) for e in endpoints)
        if not has_route:
            orphans.append(t["table_name"])
    return orphans


def _find_orphan_endpoints(endpoints: List[Dict], tables: List[Dict]) -> List[str]:
    """Endpoints that don't seem to map to any table (less critical)."""
    orphans = []
    skip_routes = {"/", "/health", "/auth", "/login", "/register", "/me"}
    for e in endpoints:
        route = e["route"].lower()
        if route in skip_routes or "/auth/" in route:
            continue
        has_table = any(_route_references_table(e["route"], t["table_name"]) for t in tables)
        if not has_table:
            orphans.append(f"{e['method']} {e['route']}")
    return orphans


def _find_missing_ui(features: List[Dict], ui_components: List[Dict]) -> List[str]:
    """Features with no matching UI component."""
    missing = []
    ui_names = [c["name"].lower() for c in ui_components]
    for f in features:
        name_lower = f["name"].lower()
        has_ui = any(_fuzzy_match(name_lower, ui_name) for ui_name in ui_names)
        if not has_ui:
            missing.append(f["name"])
    return missing


def _compute_completeness(features: List[Dict], tables: List[Dict],
                          endpoints: List[Dict], ui_components: List[Dict]) -> Dict[str, float]:
    """Rough completeness scores per layer (0.0 - 1.0)."""
    # Feature score: just based on count
    feat_score = min(1.0, len(features) / 5.0) if features else 0.0

    # Database score: tables exist + have fields + have timestamps
    if not tables:
        db_score = 0.0
    else:
        table_scores = []
        for t in tables:
            field_count = len(t.get("fields", []))
            has_timestamps = any(f in t.get("field_names", []) for f in ["created_at", "updated_at"])
            score = min(1.0, field_count / 4.0) * (1.0 if has_timestamps else 0.7)
            table_scores.append(score)
        db_score = sum(table_scores) / len(table_scores)

    # API score: endpoints exist per table
    if not endpoints:
        api_score = 0.0
    elif not tables:
        api_score = min(1.0, len(endpoints) / 5.0)
    else:
        covered = sum(1 for t in tables if any(
            _route_references_table(e["route"], t["table_name"]) for e in endpoints
        ))
        api_score = covered / len(tables)

    # UI score: components exist per feature
    if not ui_components:
        ui_score = 0.0
    elif not features:
        ui_score = min(1.0, len(ui_components) / 3.0)
    else:
        covered = sum(1 for f in features if any(
            _fuzzy_match(f["name"], c["name"]) for c in ui_components
        ))
        ui_score = covered / len(features)

    return {
        "features": round(feat_score, 2),
        "database": round(db_score, 2),
        "api": round(api_score, 2),
        "ui": round(ui_score, 2),
    }


# ─── Project Classifier ──────────────────────────────────────────────────────

PROJECT_TYPES = ["saas", "ecommerce", "social"]

def classify_project(ctx: Dict[str, Any]) -> str:
    """Classify the project type based on heuristics. Returns best match or 'unknown'."""
    if ctx.get("project_type") and ctx["project_type"] != "unknown":
        return ctx["project_type"]

    scores: Dict[str, float] = {}
    table_names = [t["table_name"].lower() for t in ctx.get("tables", [])]
    feature_names = [f["name"].lower() for f in ctx.get("features", [])]
    route_parts = []
    for e in ctx.get("endpoints", []):
        route_parts.extend([p for p in e["route"].lower().split("/") if p and not p.startswith(":")])

    all_text = table_names + feature_names + route_parts

    for ptype in PROJECT_TYPES:
        pattern = load_pattern(ptype)
        signals = pattern.get("signals", {})
        score = 0.0

        for sig_table in signals.get("table_names", []):
            if any(sig_table in t for t in table_names):
                score += 2.0

        for sig_feat in signals.get("feature_keywords", []):
            if any(sig_feat in f for f in feature_names):
                score += 1.5

        for sig_route in signals.get("route_keywords", []):
            if any(sig_route in r for r in route_parts):
                score += 1.0

        scores[ptype] = score

    if not scores:
        return "unknown"

    best = max(scores, key=scores.get)
    if scores[best] < 2.0:
        # Not enough signal
        if not ctx.get("ui_components"):
            return "api_only"
        return "unknown"

    return best


# ─── Gap Analyzer ─────────────────────────────────────────────────────────────

def analyze_gaps(ctx: Dict[str, Any]) -> List[Recommendation]:
    """Run deterministic gap analysis rules. Returns recommendations."""
    recs: List[Recommendation] = []

    tables = ctx.get("tables", [])
    endpoints = ctx.get("endpoints", [])
    features = ctx.get("features", [])
    ui_components = ctx.get("ui_components", [])
    relationships = ctx.get("relationships", {})

    # ── Rule: MISSING_CRUD_ENDPOINTS ──
    crud_methods = ["GET", "POST", "PUT", "DELETE"]
    for table in tables:
        tname = table["table_name"]
        tname_lower = tname.lower()
        existing_methods = set()
        for ep in endpoints:
            if _route_references_table(ep["route"], tname):
                existing_methods.add(ep["method"].upper())

        missing = [m for m in crud_methods if m not in existing_methods]
        if missing:
            for method in missing:
                route = f"/{tname_lower}"
                if method in ("GET", "PUT", "DELETE") and method != "GET":
                    route = f"/{tname_lower}/{{id}}"
                # For GET, suggest both list and detail
                if method == "GET" and "GET" not in existing_methods:
                    recs.append(Recommendation(
                        rule_id="missing_crud",
                        layer="api",
                        rec_type="missing_item",
                        severity="critical" if method == "POST" else "recommended",
                        title=f"Add {method} /{tname_lower}",
                        description=f"Table '{tname}' needs a {method} endpoint for {'creating' if method == 'POST' else 'reading'} records.",
                        action={
                            "type": "add_endpoint",
                            "payload": {"method": method, "route": f"/{tname_lower}", "request_schema": {}, "response_schema": {}}
                        },
                        confidence=0.95,
                    ))
                elif method != "GET":
                    recs.append(Recommendation(
                        rule_id="missing_crud",
                        layer="api",
                        rec_type="missing_item",
                        severity="recommended",
                        title=f"Add {method} /{tname_lower}/{{id}}",
                        description=f"Table '{tname}' needs a {method} endpoint for {'updating' if method == 'PUT' else 'deleting'} individual records.",
                        action={
                            "type": "add_endpoint",
                            "payload": {"method": method, "route": route, "request_schema": {}, "response_schema": {}}
                        },
                        confidence=0.9,
                    ))

    # ── Rule: ORPHAN_TABLE ──
    for tname in relationships.get("orphan_tables", []):
        recs.append(Recommendation(
            rule_id="orphan_table",
            layer="cross-layer",
            rec_type="missing_item",
            severity="critical",
            title=f"Table '{tname}' has no API routes",
            description=f"'{tname}' is defined but unreachable. Add endpoints to expose its data.",
            action={
                "type": "add_endpoint",
                "payload": {"method": "GET", "route": f"/{tname.lower()}", "request_schema": {}, "response_schema": {}}
            },
            confidence=0.95,
        ))

    # ── Rule: MISSING_TIMESTAMPS ──
    for table in tables:
        field_names = [fn.lower() for fn in table.get("field_names", [])]
        missing_ts = []
        if "created_at" not in field_names:
            missing_ts.append("created_at")
        if "updated_at" not in field_names:
            missing_ts.append("updated_at")
        if missing_ts:
            recs.append(Recommendation(
                rule_id="missing_timestamps",
                layer="database",
                rec_type="improvement",
                severity="recommended",
                title=f"Add {', '.join(missing_ts)} to '{table['table_name']}'",
                description="Timestamp fields are essential for audit trails, debugging, and data synchronization.",
                action={
                    "type": "add_fields",
                    "payload": {
                        "table_name": table["table_name"],
                        "fields": [{"name": f, "type": "datetime"} for f in missing_ts]
                    }
                },
                confidence=0.98,
            ))

    # ── Rule: MISSING_AUTH_TABLE ──
    auth_keywords = ["auth", "login", "register", "signup", "sign-up", "sign_up", "authentication"]
    has_auth_feature = any(
        any(kw in f["name"].lower() for kw in auth_keywords)
        for f in features
    )
    has_auth_endpoint = any(
        any(kw in e["route"].lower() for kw in auth_keywords)
        for e in endpoints
    )
    table_names_lower = [t["table_name"].lower() for t in tables]
    has_users_table = any(t in table_names_lower for t in ["users", "user", "accounts", "account"])

    if (has_auth_feature or has_auth_endpoint) and not has_users_table:
        recs.append(Recommendation(
            rule_id="missing_auth_table",
            layer="database",
            rec_type="missing_item",
            severity="critical",
            title="Missing users table for authentication",
            description="You have auth-related features but no users/accounts table. Add one with email, password_hash, and role.",
            action={
                "type": "add_schema",
                "payload": {
                    "table_name": "users",
                    "fields": [
                        {"name": "id", "type": "integer"},
                        {"name": "email", "type": "string"},
                        {"name": "password_hash", "type": "string"},
                        {"name": "role", "type": "string"},
                        {"name": "created_at", "type": "datetime"},
                        {"name": "updated_at", "type": "datetime"},
                    ]
                }
            },
            confidence=0.99,
        ))

    # ── Rule: MISSING_ID_FIELD ──
    for table in tables:
        field_names = [fn.lower() for fn in table.get("field_names", [])]
        if "id" not in field_names:
            recs.append(Recommendation(
                rule_id="missing_id",
                layer="database",
                rec_type="improvement",
                severity="critical",
                title=f"Table '{table['table_name']}' has no primary key (id)",
                description="Every table should have a primary key. Add an 'id' field.",
                action={
                    "type": "add_fields",
                    "payload": {
                        "table_name": table["table_name"],
                        "fields": [{"name": "id", "type": "integer"}]
                    }
                },
                confidence=1.0,
            ))

    # ── Rule: MISSING_FOREIGN_KEYS ──
    for table in tables:
        tname = table["table_name"].lower()
        field_names_lower = [fn.lower() for fn in table.get("field_names", [])]
        for other_table in tables:
            if other_table["table_name"] == table["table_name"]:
                continue
            other_lower = other_table["table_name"].lower()
            # If other table is "users" and this table doesn't have "user_id"
            expected_fk = f"{other_lower.rstrip('s')}_id"
            # Only suggest if the relationship is likely (tables are related by naming convention)
            if expected_fk not in field_names_lower:
                # Only suggest for common parent tables
                parent_names = ["users", "user", "organizations", "organization"]
                if other_lower in parent_names and tname not in parent_names:
                    recs.append(Recommendation(
                        rule_id="missing_fk",
                        layer="database",
                        rec_type="improvement",
                        severity="recommended",
                        title=f"Add {expected_fk} to '{table['table_name']}'",
                        description=f"Link '{table['table_name']}' to '{other_table['table_name']}' with a foreign key for proper relationships.",
                        action={
                            "type": "add_fields",
                            "payload": {
                                "table_name": table["table_name"],
                                "fields": [{"name": expected_fk, "type": "integer"}]
                            }
                        },
                        confidence=0.75,
                    ))

    # ── Rule: UI_COVERAGE ──
    for feat_name in relationships.get("missing_ui", []):
        recs.append(Recommendation(
            rule_id="missing_ui",
            layer="ui",
            rec_type="missing_item",
            severity="recommended",
            title=f"No UI page for '{feat_name}'",
            description=f"Feature '{feat_name}' has no corresponding UI component. Add a page to make it accessible.",
            action={
                "type": "add_ui_component",
                "payload": {"name": feat_name, "type": "page"}
            },
            confidence=0.85,
        ))

    # ── Rule: MISSING_SEARCH ──
    if len(tables) >= 3:
        has_search = any(
            "search" in e["route"].lower() or "filter" in e["route"].lower()
            for e in endpoints
        )
        if not has_search:
            recs.append(Recommendation(
                rule_id="missing_search",
                layer="api",
                rec_type="best_practice",
                severity="nice_to_have",
                title="Add a search/filter endpoint",
                description=f"With {len(tables)} data tables, users will need to search across them. Add a search endpoint.",
                action={
                    "type": "add_endpoint",
                    "payload": {"method": "GET", "route": "/search", "request_schema": {}, "response_schema": {}}
                },
                confidence=0.7,
            ))

    # ── Rule: EMPTY_LAYERS ──
    if not tables and (features or endpoints):
        recs.append(Recommendation(
            rule_id="empty_database",
            layer="database",
            rec_type="missing_item",
            severity="critical",
            title="No database tables defined",
            description="You have features and/or endpoints but no data layer. Define your database schema first.",
            action={"type": "navigate", "payload": {"tab": "database"}},
            confidence=1.0,
        ))

    if not endpoints and tables:
        recs.append(Recommendation(
            rule_id="empty_api",
            layer="api",
            rec_type="missing_item",
            severity="critical",
            title="No API endpoints defined",
            description="You have database tables but no way to access them. Add API endpoints.",
            action={"type": "navigate", "payload": {"tab": "api"}},
            confidence=1.0,
        ))

    return recs


# ─── Pattern Matcher ──────────────────────────────────────────────────────────

def match_patterns(ctx: Dict[str, Any], project_type: str) -> List[Recommendation]:
    """Suggest missing items based on the project type's archetype pattern."""
    recs: List[Recommendation] = []

    if project_type in ("unknown", "api_only"):
        return recs

    pattern = load_pattern(project_type)
    if not pattern:
        return recs

    table_names_lower = set(t["table_name"].lower() for t in ctx.get("tables", []))
    feature_names_lower = set(f["name"].lower() for f in ctx.get("features", []))
    existing_routes = set(f"{e['method'].upper()} {e['route'].lower()}" for e in ctx.get("endpoints", []))
    ui_names_lower = set(c["name"].lower() for c in ctx.get("ui_components", []))

    # Missing essential tables
    for et in pattern.get("essential_tables", []):
        et_name = et["table_name"].lower()
        if et_name not in table_names_lower:
            recs.append(Recommendation(
                rule_id=f"pattern_{project_type}_table",
                layer="database",
                rec_type="best_practice",
                severity="recommended",
                title=f"Add '{et['table_name']}' table ({project_type} standard)",
                description=f"Most {project_type} applications need a '{et['table_name']}' table.",
                action={
                    "type": "add_schema",
                    "payload": {"table_name": et["table_name"], "fields": et.get("fields", [])}
                },
                confidence=0.8,
            ))

    # Missing essential endpoints
    for ee in pattern.get("essential_endpoints", []):
        route_key = f"{ee['method'].upper()} {ee['route'].lower()}"
        if route_key not in existing_routes:
            # Fuzzy check too
            route_words = set(ee["route"].lower().replace("/", " ").split())
            has_similar = any(
                route_words & set(er.lower().replace("/", " ").split())
                for er in existing_routes
            )
            if not has_similar:
                recs.append(Recommendation(
                    rule_id=f"pattern_{project_type}_endpoint",
                    layer="api",
                    rec_type="best_practice",
                    severity="recommended",
                    title=f"Add {ee['method']} {ee['route']} ({project_type} standard)",
                    description=f"Standard {project_type} apps typically have this endpoint.",
                    action={
                        "type": "add_endpoint",
                        "payload": {"method": ee["method"], "route": ee["route"], "request_schema": {}, "response_schema": {}}
                    },
                    confidence=0.7,
                ))

    # Missing essential features
    for ef in pattern.get("essential_features", []):
        ef_lower = ef.lower()
        has_feature = any(_fuzzy_match(ef_lower, fn) for fn in feature_names_lower)
        if not has_feature:
            recs.append(Recommendation(
                rule_id=f"pattern_{project_type}_feature",
                layer="features",
                rec_type="best_practice",
                severity="nice_to_have",
                title=f"Consider adding '{ef}' feature",
                description=f"'{ef}' is a common feature in {project_type} applications.",
                action={
                    "type": "add_feature",
                    "payload": {"name": ef, "status": "planned"}
                },
                confidence=0.6,
            ))

    # Missing essential UI
    for eu in pattern.get("essential_ui", []):
        eu_lower = eu["name"].lower()
        has_ui = any(_fuzzy_match(eu_lower, un) for un in ui_names_lower)
        if not has_ui:
            recs.append(Recommendation(
                rule_id=f"pattern_{project_type}_ui",
                layer="ui",
                rec_type="best_practice",
                severity="nice_to_have",
                title=f"Add '{eu['name']}' {eu['type']}",
                description=f"Most {project_type} apps include a '{eu['name']}' {eu['type']}.",
                action={
                    "type": "add_ui_component",
                    "payload": {"name": eu["name"], "type": eu["type"]}
                },
                confidence=0.55,
            ))

    # Security checklist
    for sec_item in pattern.get("security_checklist", []):
        recs.append(Recommendation(
            rule_id=f"pattern_{project_type}_security",
            layer="cross-layer",
            rec_type="security",
            severity="recommended",
            title=sec_item,
            description=f"Security best practice for {project_type} applications.",
            action={"type": "info", "payload": {"note": sec_item}},
            confidence=0.6,
        ))

    return recs


# ─── Field Hints ──────────────────────────────────────────────────────────────

def get_field_hints(table_name: str) -> List[Dict[str, str]]:
    """Get recommended fields for a given table name."""
    common = load_pattern("common")
    field_recs = common.get("field_recommendations", {})
    universal = common.get("universal_fields", {}).get("_always", [])

    # Find matching keyword
    table_lower = table_name.lower().rstrip("s")  # Rough singularize
    matched_fields: List[Dict[str, str]] = []

    for keyword, fields in field_recs.items():
        if keyword in table_lower or table_lower in keyword:
            matched_fields.extend(fields)
            break

    # Always add universal fields if not already present
    existing_names = {f["name"] for f in matched_fields}
    for uf in universal:
        if uf["name"] not in existing_names:
            matched_fields.insert(0 if uf["name"] == "id" else len(matched_fields), uf)

    return matched_fields


# ─── Ranker & Main Entry Point ────────────────────────────────────────────────

SEVERITY_ORDER = {"critical": 0, "recommended": 1, "nice_to_have": 2}

def get_recommendations(
    project: Any,
    features: List[Any],
    schemas: List[Any],
    endpoints: List[Any],
    ui_components: List[Any],
    dismissed_ids: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Main entry point. Returns all recommendations for a project,
    sorted by severity and confidence.
    """
    dismissed = set(dismissed_ids or [])

    # 1. Assemble context
    ctx = assemble_context(project, features, schemas, endpoints, ui_components)

    # 2. Classify project
    project_type = classify_project(ctx)
    ctx["project_type"] = project_type

    # 3. Gap analysis (deterministic)
    gap_recs = analyze_gaps(ctx)

    # 4. Pattern matching
    pattern_recs = match_patterns(ctx, project_type)

    # 5. Merge and deduplicate
    all_recs = gap_recs + pattern_recs
    seen_titles: set = set()
    unique_recs: List[Recommendation] = []
    for r in all_recs:
        if r.id in dismissed:
            continue
        # Dedup by similar title
        title_key = r.title.lower().strip()
        if title_key not in seen_titles:
            seen_titles.add(title_key)
            unique_recs.append(r)

    # 6. Sort by severity, then confidence
    unique_recs.sort(key=lambda r: (SEVERITY_ORDER.get(r.severity, 99), -r.confidence))

    # Group by severity
    grouped = {"critical": [], "recommended": [], "nice_to_have": []}
    for r in unique_recs:
        grouped.setdefault(r.severity, []).append(r.to_dict())

    return {
        "project_type": project_type,
        "completeness_scores": ctx["completeness_scores"],
        "total_count": len(unique_recs),
        "critical_count": len(grouped.get("critical", [])),
        "recommendations": {
            "critical": grouped.get("critical", []),
            "recommended": grouped.get("recommended", []),
            "nice_to_have": grouped.get("nice_to_have", []),
        },
        "all": [r.to_dict() for r in unique_recs],
    }
