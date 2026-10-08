from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field, asdict


@dataclass
class DriftItem:
    layer: str          # "table" | "route" | "component"
    key: str            # e.g. "GET /users" or "users"
    status: str         # "spec_only" | "scan_only" | "conflict" | "deleted_in_code" | "deleted_in_spec" | "in_sync"
    title: str
    description: str
    spec_value: Optional[Any] = None
    scan_value: Optional[Any] = None
    snapshot_value: Optional[Any] = None
    details: Dict[str, Any] = field(default_factory=dict)


def _normalize_route_key(method: str, route: str) -> str:
    m = (method or "GET").upper().strip()
    r = route.strip()
    if not r.startswith("/"):
        r = "/" + r
    return f"{m} {r}"


def _get_table_fields_dict(table_dict: Optional[Dict[str, Any]]) -> Dict[str, str]:
    if not table_dict:
        return {}
    cols = table_dict.get("columns") or table_dict.get("fields") or []
    result = {}
    for c in cols:
        if isinstance(c, dict) and "name" in c:
            result[c["name"]] = c.get("type", "string").lower()
    return result


def three_way_diff(
    snapshot: Optional[Dict[str, Any]],
    current_spec: Dict[str, Any],
    current_scan: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Performs a three-way diff between:
      1. snapshot: last-synced common ancestor (can be None for first-time repos)
      2. current_spec: active specification in database
      3. current_scan: fresh scan from the codebase (AST scanner)

    Returns categorized drift items and summary statistics.
    """
    snapshot_spec = (snapshot or {}).get("spec_json") or (snapshot or {}).get("spec") or {}
    snapshot_scan = (snapshot or {}).get("scan_json") or (snapshot or {}).get("scan") or {}

    # Extract tables from all 3 sources
    spec_tables_list = current_spec.get("database") or current_spec.get("schemas") or []
    spec_tables = {t.get("table_name") or t.get("table"): t for t in spec_tables_list if t.get("table_name") or t.get("table")}

    scan_tables_list = current_scan.get("tables", [])
    scan_tables = {t.get("table_name"): t for t in scan_tables_list if t.get("table_name")}

    snap_tables_list = snapshot_spec.get("database") or snapshot_spec.get("schemas") or snapshot_scan.get("tables") or []
    snap_tables = {t.get("table_name") or t.get("table"): t for t in snap_tables_list if t.get("table_name") or t.get("table")}

    drift_items: List[DriftItem] = []

    # ──────────────────────────────────────────────────────────────────────────
    # 1. DATABASE TABLES
    # ──────────────────────────────────────────────────────────────────────────
    all_table_names = sorted(set(spec_tables.keys()) | set(scan_tables.keys()) | set(snap_tables.keys()))

    for name in all_table_names:
        in_spec = name in spec_tables
        in_scan = name in scan_tables
        in_snap = name in snap_tables

        if in_spec and in_scan:
            # Compare columns
            spec_fields = _get_table_fields_dict(spec_tables[name])
            scan_fields = _get_table_fields_dict(scan_tables[name])
            snap_fields = _get_table_fields_dict(snap_tables.get(name))

            only_in_spec = sorted(set(spec_fields.keys()) - set(scan_fields.keys()))
            only_in_scan = sorted(set(scan_fields.keys()) - set(spec_fields.keys()))
            type_mismatches = []
            for col in set(spec_fields.keys()) & set(scan_fields.keys()):
                if spec_fields[col] != scan_fields[col]:
                    type_mismatches.append({
                        "field": col,
                        "spec_type": spec_fields[col],
                        "code_type": scan_fields[col],
                    })

            if not only_in_spec and not only_in_scan and not type_mismatches:
                drift_items.append(DriftItem(
                    layer="table",
                    key=name,
                    status="in_sync",
                    title=f"Table `{name}` is in sync",
                    description="Database model matches specification columns exactly.",
                    spec_value=spec_tables[name],
                    scan_value=scan_tables[name],
                    snapshot_value=snap_tables.get(name),
                ))
            else:
                # Check if it's a conflict or one-sided modification
                spec_changed = set(spec_fields.items()) != set(snap_fields.items()) if in_snap else True
                scan_changed = set(scan_fields.items()) != set(snap_fields.items()) if in_snap else True

                status = "conflict" if (spec_changed and scan_changed and (only_in_spec or only_in_scan or type_mismatches)) else (
                    "spec_only" if only_in_spec and not only_in_scan else "scan_only"
                )

                drift_items.append(DriftItem(
                    layer="table",
                    key=name,
                    status=status,
                    title=f"Table `{name}` schema drift detected",
                    description=f"{len(only_in_spec)} column(s) only in spec, {len(only_in_scan)} column(s) only in code.",
                    spec_value=spec_tables[name],
                    scan_value=scan_tables[name],
                    snapshot_value=snap_tables.get(name),
                    details={
                        "columns_only_in_spec": only_in_spec,
                        "columns_only_in_code": only_in_scan,
                        "type_mismatches": type_mismatches,
                    }
                ))

        elif in_spec and not in_scan:
            if in_snap:
                drift_items.append(DriftItem(
                    layer="table",
                    key=name,
                    status="deleted_in_code",
                    title=f"Table `{name}` was removed in code",
                    description=f"Model exists in spec and last snapshot, but was deleted from codebase.",
                    spec_value=spec_tables[name],
                    snapshot_value=snap_tables.get(name),
                ))
            else:
                drift_items.append(DriftItem(
                    layer="table",
                    key=name,
                    status="spec_only",
                    title=f"Table `{name}` added to specification",
                    description="Created in CreateFrame spec, not yet implemented in codebase.",
                    spec_value=spec_tables[name],
                ))

        elif in_scan and not in_spec:
            if in_snap:
                drift_items.append(DriftItem(
                    layer="table",
                    key=name,
                    status="deleted_in_spec",
                    title=f"Table `{name}` was removed from specification",
                    description="Table exists in codebase, but was removed from active specification.",
                    scan_value=scan_tables[name],
                    snapshot_value=snap_tables.get(name),
                ))
            else:
                drift_items.append(DriftItem(
                    layer="table",
                    key=name,
                    status="scan_only",
                    title=f"Table `{name}` detected in codebase",
                    description="Found by AST scanner in code, not yet documented in specification.",
                    scan_value=scan_tables[name],
                ))

    # ──────────────────────────────────────────────────────────────────────────
    # 2. API ENDPOINTS / ROUTES
    # ──────────────────────────────────────────────────────────────────────────
    spec_routes_list = current_spec.get("endpoints", [])
    spec_routes = {_normalize_route_key(e.get("method"), e.get("route")): e for e in spec_routes_list if e.get("route")}

    scan_routes_list = current_scan.get("routes", [])
    scan_routes = {_normalize_route_key(r.get("method"), r.get("route")): r for r in scan_routes_list if r.get("route")}

    snap_routes_list = snapshot_spec.get("endpoints") or snapshot_scan.get("routes") or []
    snap_routes = {_normalize_route_key(r.get("method"), r.get("route")): r for r in snap_routes_list if r.get("route")}

    all_routes = sorted(set(spec_routes.keys()) | set(scan_routes.keys()) | set(snap_routes.keys()))

    for route_key in all_routes:
        in_spec = route_key in spec_routes
        in_scan = route_key in scan_routes
        in_snap = route_key in snap_routes

        if in_spec and in_scan:
            drift_items.append(DriftItem(
                layer="route",
                key=route_key,
                status="in_sync",
                title=f"Endpoint `{route_key}` matches code",
                description="Endpoint exists in both specification and repository code.",
                spec_value=spec_routes[route_key],
                scan_value=scan_routes[route_key],
                snapshot_value=snap_routes.get(route_key),
            ))
        elif in_spec and not in_scan:
            if in_snap:
                drift_items.append(DriftItem(
                    layer="route",
                    key=route_key,
                    status="deleted_in_code",
                    title=f"Endpoint `{route_key}` deleted in code",
                    description="Route documented in spec was deleted from repository.",
                    spec_value=spec_routes[route_key],
                    snapshot_value=snap_routes.get(route_key),
                ))
            else:
                drift_items.append(DriftItem(
                    layer="route",
                    key=route_key,
                    status="spec_only",
                    title=f"Endpoint `{route_key}` planned in spec",
                    description="Endpoint exists in spec, awaiting route implementation.",
                    spec_value=spec_routes[route_key],
                ))
        elif in_scan and not in_spec:
            if in_snap:
                drift_items.append(DriftItem(
                    layer="route",
                    key=route_key,
                    status="deleted_in_spec",
                    title=f"Endpoint `{route_key}` removed from spec",
                    description="Endpoint exists in code, but was removed from specification.",
                    scan_value=scan_routes[route_key],
                    snapshot_value=snap_routes.get(route_key),
                ))
            else:
                drift_items.append(DriftItem(
                    layer="route",
                    key=route_key,
                    status="scan_only",
                    title=f"New endpoint `{route_key}` in code",
                    description="Codebase adds an API route not currently documented in spec.json.",
                    scan_value=scan_routes[route_key],
                ))

    # ──────────────────────────────────────────────────────────────────────────
    # 3. UI COMPONENTS
    # ──────────────────────────────────────────────────────────────────────────
    spec_comps = {c.get("name"): c for c in current_spec.get("ui_components", []) if c.get("name")}
    snap_comps = {c.get("name"): c for c in snapshot_spec.get("ui_components", []) if c.get("name")}

    for cname in sorted(set(spec_comps.keys()) | set(snap_comps.keys())):
        if cname in spec_comps and cname not in snap_comps:
            drift_items.append(DriftItem(
                layer="component",
                key=cname,
                status="spec_only",
                title=f"Component `{cname}` added in spec",
                description="UI Component planned in spec.",
                spec_value=spec_comps[cname],
            ))
        elif cname in spec_comps:
            drift_items.append(DriftItem(
                layer="component",
                key=cname,
                status="in_sync",
                title=f"Component `{cname}`",
                description="UI Component present in specification.",
                spec_value=spec_comps[cname],
            ))

    # Calculate statistics
    total_items = len(drift_items)
    conflicts = sum(1 for d in drift_items if d.status == "conflict")
    spec_only = sum(1 for d in drift_items if d.status == "spec_only")
    scan_only = sum(1 for d in drift_items if d.status == "scan_only")
    deleted_code = sum(1 for d in drift_items if d.status == "deleted_in_code")
    deleted_spec = sum(1 for d in drift_items if d.status == "deleted_in_spec")
    in_sync = sum(1 for d in drift_items if d.status == "in_sync")

    drift_count = total_items - in_sync

    return {
        "summary": {
            "total_items": total_items,
            "drift_count": drift_count,
            "in_sync_count": in_sync,
            "conflicts_count": conflicts,
            "spec_only_count": spec_only,
            "scan_only_count": scan_only,
            "deleted_in_code_count": deleted_code,
            "deleted_in_spec_count": deleted_spec,
            "is_clean": drift_count == 0,
        },
        "items": [asdict(d) for d in drift_items],
    }
