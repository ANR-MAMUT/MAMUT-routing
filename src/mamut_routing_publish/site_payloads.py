from __future__ import annotations

from collections import Counter
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime, timezone
from enum import Enum
import os
from pathlib import Path
import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from mamut_routing_lib.artifacts import (
    AnyBenchmarkInstance,
    discover_benchmark_instances,
    load_bks,
)
from mamut_routing_lib.enums import BenchmarkName, MetricVariant, ObjectiveFunction, ProblemType
from mamut_routing_lib.json_utils import load_json_from_file, save_json_to_file
from mamut_routing_lib import has_structured_metadata

from .progress import ProgressReporter
from .road_cache import enforce_full_road_cache


SITE_PAYLOAD_SCHEMA_VERSION = "1.0.0"
DEFAULT_SITE_OUTPUT_DIR = Path("dist")
DEFAULT_SITE_PAYLOAD_ROOT_DIR = Path("site-payloads")
DEFAULT_FAMILY_CONTEXT_REPORT_PATH = Path(__file__).with_name("site_assets") / "texts" / "mamut-routing_benchmark_families.md"

ViewerRenderMode = Literal["straight_line", "cached_road"]
RoadCacheStatus = Literal["not_applicable", "none", "partial", "complete"]


class SitePayloadKind(str, Enum):
    HOME_PAGE = "home_page"
    SITE_SNAPSHOT = "site_snapshot"
    SITE_HISTORY = "site_history"
    HISTORY_DETAIL = "history_detail"
    PROJECT_PAGE = "project_page"
    BENCHMARKS_INDEX = "benchmarks_index"
    PROBLEM_INDEX = "problem_index"
    FAMILY_INDEX = "family_index"
    VARIANT_INDEX = "variant_index"
    PLACE_INDEX = "place_index"
    SIZE_INDEX = "size_index"
    SUBSET_INDEX = "subset_index"
    INSTANCE_PAGE = "instance_page"
    OBJECTIVES_PAGE = "objectives_page"
    FAMILY_CONTEXT_PAGE = "family_context_page"


class SnapshotRef(BaseModel):
    model_config = ConfigDict(extra="forbid")

    snapshot_id: str
    published_at: str
    source_commit: str
    source_branch: str | None = None


class SitePayloadBase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    payload_kind: SitePayloadKind
    schema_version: str = SITE_PAYLOAD_SCHEMA_VERSION
    generated_at: str
    snapshot: SnapshotRef


class SiteCounts(BaseModel):
    model_config = ConfigDict(extra="forbid")

    problem_count: int
    family_count: int
    variant_count: int
    place_count: int
    size_bucket_count: int
    instance_count: int
    bks_count: int


class ObjectiveAvailability(BaseModel):
    model_config = ConfigDict(extra="forbid")

    objective_function: ObjectiveFunction
    cost: int | float | None = None
    num_routes: int | None = None
    artifact_path: str


class BreadcrumbItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: str
    route_path: str


class FilterOption(BaseModel):
    model_config = ConfigDict(extra="forbid")

    value: str
    label: str
    count: int


class FilterFacet(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str
    label: str
    options: list[FilterOption]


class BenchmarkLocator(BaseModel):
    model_config = ConfigDict(extra="forbid")

    problem_type: ProblemType
    benchmark_name: BenchmarkName
    metric_variant: MetricVariant | None = None
    place_slug: str | None = None
    size_bucket: str
    instance_identifier: str
    subset: str | None = None


class ProblemSummaryCard(BaseModel):
    model_config = ConfigDict(extra="forbid")

    problem_type: ProblemType
    route_path: str
    benchmark_names: list[BenchmarkName]
    family_count: int
    instance_count: int
    bks_count: int
    supported_objective_functions: list[ObjectiveFunction]


class FamilySummaryCard(BaseModel):
    model_config = ConfigDict(extra="forbid")

    benchmark_name: BenchmarkName
    route_path: str
    context_route_path: str | None = None
    metric_variants: list[MetricVariant]
    instance_count: int
    bks_count: int
    supported_objective_functions: list[ObjectiveFunction]


class SubrouteEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str
    label: str
    route_path: str
    instance_count: int
    bks_count: int


class ObjectiveExplainer(BaseModel):
    model_config = ConfigDict(extra="forbid")

    objective_function: ObjectiveFunction
    short_label: str
    title: str
    description: str
    interpretation_notes: list[str]
    related_routes: list[SubrouteEntry] = Field(default_factory=list)


class CatalogSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    instance_count: int
    bks_count: int
    place_count: int
    size_bucket_count: int
    supported_objective_functions: list[ObjectiveFunction]


class InstanceListItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    locator: BenchmarkLocator
    display_name: str
    instance_id: str
    num_customers: int
    route_path: str
    artifact_vrp_json_path: str
    place_slug: str | None = None
    historical_topology_type: str | None = None
    historical_tw_type: str | None = None
    bks_count: int
    viewer_render_mode: ViewerRenderMode = "straight_line"
    road_cache_status: RoadCacheStatus = "not_applicable"
    objective_availability: list[ObjectiveAvailability]


class SiteArtifactLinks(BaseModel):
    model_config = ConfigDict(extra="forbid")

    vrp_json_path: str
    vrp_path: str | None = None
    meta_path: str | None = None
    manifest_path: str | None = None


class BKSPageEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    objective_function: ObjectiveFunction
    artifact_path: str
    num_routes: int
    cost: int | float | None = None
    authors: str | None = None
    source: str | None = None
    method: str | None = None
    validated_num_routes: int | None = None
    license: str | None = None
    license_url: str | None = None


class InstancePageSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    display_name: str
    problem_type: ProblemType
    benchmark_name: BenchmarkName
    metric_variant: MetricVariant | None = None
    place_slug: str | None = None
    size_bucket: str
    num_customers: int
    historical_topology_type: str | None = None
    historical_tw_type: str | None = None
    num_vehicles: int | None = None
    num_vehicles_lb: int | None = None
    vehicle_capacity: int
    authors: str | None = None
    generated_at: str | None = None
    source_city: str | None = None
    has_geometry_sidecar: bool = False
    viewer_render_mode: ViewerRenderMode = "straight_line"
    road_cache_status: RoadCacheStatus = "not_applicable"
    road_cache_metrics: list[str] = Field(default_factory=list)
    road_cache_entry_count: int = 0
    road_cache_expected_entry_count: int | None = None
    supported_objective_functions: list[ObjectiveFunction]
    subset: str | None = None
    license: str | None = None
    license_url: str | None = None
    instance_provider: str | None = None


class BksValue(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cost: int | float | None = None
    num_routes: int | None = None
    authors: str | None = None
    method: str | None = None


class FamilyChange(BaseModel):
    model_config = ConfigDict(extra="forbid")

    problem_type: ProblemType
    benchmark_name: BenchmarkName
    kind: Literal["added", "removed"]


class InstanceChange(BaseModel):
    model_config = ConfigDict(extra="forbid")

    instance_id: str
    problem_type: ProblemType
    benchmark_name: BenchmarkName
    metric_variant: MetricVariant | None = None
    place_slug: str | None = None
    num_customers: int
    instance_name: str
    kind: Literal["added", "removed"]


class BksChange(BaseModel):
    model_config = ConfigDict(extra="forbid")

    instance_id: str
    problem_type: ProblemType
    benchmark_name: BenchmarkName
    metric_variant: MetricVariant | None = None
    place_slug: str | None = None
    num_customers: int
    instance_name: str
    objective_function: ObjectiveFunction
    kind: Literal["added", "removed", "improved", "regressed"]
    prev: BksValue | None = None
    new: BksValue | None = None
    cost_delta: int | float | None = None
    cost_pct: float | None = None
    routes_delta: int | None = None
    routes_pct: float | None = None


class ChangeCounts(BaseModel):
    model_config = ConfigDict(extra="forbid")

    families_added: int = 0
    families_removed: int = 0
    instances_added: int = 0
    instances_removed: int = 0
    bks_added: int = 0
    bks_removed: int = 0
    bks_improved: int = 0
    bks_regressed: int = 0


class SnapshotChangeLog(BaseModel):
    model_config = ConfigDict(extra="forbid")

    is_initial: bool
    counts: ChangeCounts
    family_changes: list[FamilyChange] = Field(default_factory=list)
    instance_changes: list[InstanceChange] = Field(default_factory=list)
    bks_changes: list[BksChange] = Field(default_factory=list)


class SiteSnapshotManifest(SitePayloadBase):
    payload_kind: Literal[SitePayloadKind.SITE_SNAPSHOT] = SitePayloadKind.SITE_SNAPSHOT

    summary: str
    counts: SiteCounts
    benchmark_index_path: str
    history_path: str
    history_detail_path: str


class SiteHistoryEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    snapshot: SnapshotRef
    summary: str
    detail_route_path: str
    affected_problem_types: list[ProblemType] = Field(default_factory=list)
    affected_benchmark_names: list[BenchmarkName] = Field(default_factory=list)
    affected_objective_functions: list[ObjectiveFunction] = Field(default_factory=list)
    change_counts: ChangeCounts = Field(default_factory=ChangeCounts)


class SiteHistoryLedger(SitePayloadBase):
    payload_kind: Literal[SitePayloadKind.SITE_HISTORY] = SitePayloadKind.SITE_HISTORY

    current_snapshot_id: str
    entries: list[SiteHistoryEntry]


class HomePagePayload(SitePayloadBase):
    payload_kind: Literal[SitePayloadKind.HOME_PAGE] = SitePayloadKind.HOME_PAGE

    route_path: str = "/"
    title: str
    subtitle: str
    hero_summary: str
    latest_publication_summary: str
    counts: SiteCounts
    problems: list[ProblemSummaryCard]
    benchmarks_route_path: str = "/benchmarks/"
    project_route_path: str = "/project/"
    objectives_route_path: str = "/objectives/"
    history_route_path: str = "/history/"
    workbench_route_path: str = "/workbench/"


class ProjectFact(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: str
    value: str
    href: str | None = None


class ProjectNarrativeBlock(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str
    body: str
    tags: list[str] = Field(default_factory=list)


class ProjectPagePayload(SitePayloadBase):
    payload_kind: Literal[SitePayloadKind.PROJECT_PAGE] = SitePayloadKind.PROJECT_PAGE

    route_path: str = "/project/"
    title: str
    subtitle: str
    breadcrumbs: list[BreadcrumbItem]
    anr_project_code: str
    anr_project_url: str
    anr_project_title: str
    anr_context: str
    facts: list[ProjectFact]
    research_threads: list[ProjectNarrativeBlock]
    collaboration_note: str


class HistoryDetailPayload(SitePayloadBase):
    payload_kind: Literal[SitePayloadKind.HISTORY_DETAIL] = SitePayloadKind.HISTORY_DETAIL

    route_path: str
    title: str
    breadcrumbs: list[BreadcrumbItem]
    summary: str
    counts: SiteCounts
    benchmark_index_path: str
    history_path: str
    affected_problem_types: list[ProblemType] = Field(default_factory=list)
    affected_benchmark_names: list[BenchmarkName] = Field(default_factory=list)
    affected_objective_functions: list[ObjectiveFunction] = Field(default_factory=list)
    change_log: SnapshotChangeLog


class BenchmarksIndexPayload(SitePayloadBase):
    payload_kind: Literal[SitePayloadKind.BENCHMARKS_INDEX] = SitePayloadKind.BENCHMARKS_INDEX

    route_path: str
    breadcrumbs: list[BreadcrumbItem] = Field(default_factory=list)
    problems: list[ProblemSummaryCard]


class ProblemIndexPayload(SitePayloadBase):
    payload_kind: Literal[SitePayloadKind.PROBLEM_INDEX] = SitePayloadKind.PROBLEM_INDEX

    route_path: str
    title: str
    breadcrumbs: list[BreadcrumbItem]
    problem_type: ProblemType
    summary: CatalogSummary
    families: list[FamilySummaryCard]


class CatalogIndexPayload(SitePayloadBase):
    payload_kind: SitePayloadKind

    route_path: str
    title: str
    description: str | None = None
    context_route_path: str | None = None
    context_summary: str | None = None
    breadcrumbs: list[BreadcrumbItem]
    problem_type: ProblemType
    benchmark_name: BenchmarkName
    metric_variant: MetricVariant | None = None
    place_slug: str | None = None
    size_bucket: str | None = None
    subset: str | None = None
    summary: CatalogSummary
    filter_facets: list[FilterFacet] = Field(default_factory=list)
    variant_routes: list[SubrouteEntry] = Field(default_factory=list)
    place_routes: list[SubrouteEntry] = Field(default_factory=list)
    size_routes: list[SubrouteEntry] = Field(default_factory=list)
    subset_routes: list[SubrouteEntry] = Field(default_factory=list)
    items: list[InstanceListItem] = Field(default_factory=list)


class InstancePagePayload(SitePayloadBase):
    payload_kind: Literal[SitePayloadKind.INSTANCE_PAGE] = SitePayloadKind.INSTANCE_PAGE

    route_path: str
    title: str
    breadcrumbs: list[BreadcrumbItem]
    locator: BenchmarkLocator
    summary: InstancePageSummary
    artifact_links: SiteArtifactLinks
    sibling_variant_routes: dict[str, str] = Field(default_factory=dict)
    derived_problem_routes: dict[str, str] = Field(default_factory=dict)
    source_problem_routes: dict[str, str] = Field(default_factory=dict)
    bks_entries: list[BKSPageEntry] = Field(default_factory=list)
    workbench_route_path: str = "/workbench/"


class ObjectivesPagePayload(SitePayloadBase):
    payload_kind: Literal[SitePayloadKind.OBJECTIVES_PAGE] = SitePayloadKind.OBJECTIVES_PAGE

    route_path: str
    title: str
    breadcrumbs: list[BreadcrumbItem]
    explainers: list[ObjectiveExplainer]


class FamilyContextPagePayload(SitePayloadBase):
    payload_kind: Literal[SitePayloadKind.FAMILY_CONTEXT_PAGE] = SitePayloadKind.FAMILY_CONTEXT_PAGE

    route_path: str
    title: str
    breadcrumbs: list[BreadcrumbItem]
    problem_type: ProblemType
    benchmark_name: BenchmarkName
    markdown: str
    family_route_path: str
    license_spdx_id: str | None = None
    license_markdown: str | None = None


class SitePayloadGenerationSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    snapshot_id: str
    source_commit: str
    published_at: str
    payload_files_written: int
    benchmark_pages_written: int
    instance_pages_written: int
    history_entries: int
    payload_paths: list[str] | None = None


class _ResolvedInstanceSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    num_customers: int
    num_vehicles: int | None = None
    vehicle_capacity: int | float | None = None
    authors: str | None = None
    generated_at: str | None = None
    source_city: str | None = None
    num_vehicles_lb: int | None = None
    subset: str | None = None
    license: str | None = None
    license_url: str | None = None
    instance_provider: str | None = None


class _ResolvedSiteInstance(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    locator: BenchmarkLocator
    display_name: str
    instance_id: str
    route_path: str
    instance_summary: _ResolvedInstanceSummary
    artifact_links: SiteArtifactLinks
    historical_topology_type: str | None = None
    historical_tw_type: str | None = None
    has_geometry_sidecar: bool = False
    viewer_render_mode: ViewerRenderMode = "straight_line"
    road_cache_status: RoadCacheStatus = "not_applicable"
    road_cache_metrics: list[str] = Field(default_factory=list)
    road_cache_entry_count: int = 0
    road_cache_expected_entry_count: int | None = None
    sibling_variant_routes: dict[str, str] = Field(default_factory=dict)
    derived_problem_routes: dict[str, str] = Field(default_factory=dict)
    source_problem_routes: dict[str, str] = Field(default_factory=dict)
    bks_entries: list[BKSPageEntry] = Field(default_factory=list)


def _now_utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _normalize_benchmark_name(value: BenchmarkName | str) -> BenchmarkName:
    return value if isinstance(value, BenchmarkName) else BenchmarkName(value)


def _route_segment(value: str) -> str:
    return value.lower()


def _problem_route_path(problem_type: ProblemType) -> str:
    return f"/benchmarks/{_route_segment(problem_type.value)}/"


def _family_route_path(problem_type: ProblemType, benchmark_name: BenchmarkName) -> str:
    return f"{_problem_route_path(problem_type)}{_route_segment(benchmark_name.value)}/"


def _family_context_route_path(problem_type: ProblemType, benchmark_name: BenchmarkName) -> str:
    return f"{_family_route_path(problem_type, benchmark_name)}context/"


def _subset_route_path(
    problem_type: ProblemType,
    benchmark_name: BenchmarkName,
    subset: str,
) -> str:
    return f"{_family_route_path(problem_type, benchmark_name)}{_route_segment(subset)}/"


def _variant_route_path(
    problem_type: ProblemType,
    benchmark_name: BenchmarkName,
    metric_variant: MetricVariant,
) -> str:
    return f"{_family_route_path(problem_type, benchmark_name)}{metric_variant.value}/"


def _place_route_path(
    problem_type: ProblemType,
    benchmark_name: BenchmarkName,
    metric_variant: MetricVariant,
    place_slug: str,
) -> str:
    return f"{_variant_route_path(problem_type, benchmark_name, metric_variant)}{place_slug}/"


def _size_route_path(
    problem_type: ProblemType,
    benchmark_name: BenchmarkName,
    size_bucket: str,
    metric_variant: MetricVariant | None = None,
    place_slug: str | None = None,
    subset: str | None = None,
) -> str:
    if metric_variant is not None and place_slug is not None:
        return f"{_place_route_path(problem_type, benchmark_name, metric_variant, place_slug)}{size_bucket}/"
    if subset is not None:
        return f"{_subset_route_path(problem_type, benchmark_name, subset)}{size_bucket}/"
    return f"{_family_route_path(problem_type, benchmark_name)}{size_bucket}/"


def _instance_route_path(
    problem_type: ProblemType,
    benchmark_name: BenchmarkName,
    instance_identifier: str,
    size_bucket: str,
    metric_variant: MetricVariant | None = None,
    place_slug: str | None = None,
    subset: str | None = None,
) -> str:
    return f"{_size_route_path(problem_type, benchmark_name, size_bucket, metric_variant=metric_variant, place_slug=place_slug, subset=subset)}{instance_identifier}/"


def _route_payload_path(
    site_output_dir: Path,
    route_path: str,
    payload_root_dir: str | Path = DEFAULT_SITE_PAYLOAD_ROOT_DIR,
) -> Path:
    payload_root = Path(payload_root_dir)
    if payload_root.is_absolute():
        raise ValueError(f"Site payload root must be repository-relative, got: {payload_root}")
    if route_path == "/":
        return site_output_dir / payload_root / "index.json"
    return site_output_dir / payload_root / route_path.strip("/") / "index.json"


def _history_detail_route_path(snapshot_id: str) -> str:
    return f"/history/{snapshot_id}/"


def _history_detail_payload_path(
    site_output_dir: Path,
    snapshot_id: str,
    payload_root_dir: str | Path = DEFAULT_SITE_PAYLOAD_ROOT_DIR,
) -> Path:
    return _route_payload_path(site_output_dir, _history_detail_route_path(snapshot_id), payload_root_dir)


def _infer_snapshot_id(published_at: str, source_commit: str) -> str:
    date_part = published_at.split("T", maxsplit=1)[0]
    short_commit = source_commit[:7] if source_commit else "unknown"
    return f"{date_part}-{short_commit}"


def _objective_sort_key(value: ObjectiveFunction) -> tuple[int, str]:
    order = {
        ObjectiveFunction.HIERARCHICAL_VEHICLE_COST: 0,
        ObjectiveFunction.MONO_COST: 1,
    }
    return (order.get(value, 99), value.value)


def _metric_variant_sort_key(value: MetricVariant) -> tuple[int, str]:
    order = {
        MetricVariant.FASTEST: 0,
        MetricVariant.SHORTEST: 1,
        MetricVariant.EUCLIDEAN: 2,
    }
    return (order.get(value, 99), value.value)


def _metric_name_sort_key(value: str) -> tuple[int, str]:
    order = {
        MetricVariant.FASTEST.value: 0,
        MetricVariant.SHORTEST.value: 1,
        MetricVariant.EUCLIDEAN.value: 2,
    }
    return (order.get(value, 99), value)


def _expected_bks_route_edges(meta_payload: dict | None, bks_paths: list[Path] | None) -> set[tuple[int, int]] | None:
    if not isinstance(meta_payload, dict) or not bks_paths:
        return None

    nodes = meta_payload.get("nodes")
    if not isinstance(nodes, list):
        return None
    node_ids = [
        int(node["instance_node_id"])
        for node in nodes
        if isinstance(node, dict) and "instance_node_id" in node
    ]
    if not node_ids:
        return None

    node_offset = 0 if min(node_ids) == 0 else 1
    depot_node_id = int(meta_payload.get("depot_instance_node_id", 0 if node_offset == 0 else 1))
    route_edges: set[tuple[int, int]] = set()
    for bks_path in bks_paths:
        bks_payload = load_json_from_file(bks_path)
        routes = bks_payload.get("routes") if isinstance(bks_payload, dict) else None
        if not isinstance(routes, list):
            continue
        for route in routes:
            if not isinstance(route, list):
                continue
            full_route = [depot_node_id, *[int(stop) + node_offset for stop in route], depot_node_id]
            route_edges.update(zip(full_route, full_route[1:]))

    return route_edges or None


def _expected_bks_route_edge_count(meta_payload: dict | None, bks_paths: list[Path] | None) -> int | None:
    route_edges = _expected_bks_route_edges(meta_payload, bks_paths)
    return len(route_edges) if route_edges is not None else None


def _metric_cache_covers_bks_edges(metric_cache: object, route_edges: set[tuple[int, int]] | None) -> bool | None:
    if route_edges is None:
        return None
    if not isinstance(metric_cache, dict):
        return False
    for from_node, to_node in route_edges:
        direct_key = f"node:{from_node}_{to_node}"
        reverse_key = f"node:{to_node}_{from_node}"
        if direct_key not in metric_cache and reverse_key not in metric_cache:
            return False
    return True


def _expected_road_cache_entry_count(
    instance: AnyBenchmarkInstance,
    meta_payload: dict | None,
    bks_paths: list[Path] | None = None,
) -> int | None:
    route_edge_count = _expected_bks_route_edge_count(meta_payload, bks_paths)
    if route_edge_count is not None:
        return route_edge_count

    node_count: int | None = None
    if isinstance(meta_payload, dict):
        nodes = meta_payload.get("nodes")
        if isinstance(nodes, list):
            node_count = len(nodes)
    if node_count is None:
        coordinates = getattr(instance, "coordinates", None)
        if isinstance(coordinates, list):
            node_count = len(coordinates)
    if node_count is None or node_count < 2:
        return None
    return node_count * (node_count - 1)


def _build_geometry_summary(
    output_repo_dir: Path,
    instance: AnyBenchmarkInstance,
    metric_variant: MetricVariant | None,
    artifact_links: SiteArtifactLinks,
    bks_paths: list[Path] | None = None,
) -> dict[str, object]:
    default_summary = {
        "has_geometry_sidecar": False,
        "viewer_render_mode": "straight_line",
        "road_cache_status": "not_applicable",
        "road_cache_metrics": [],
        "road_cache_entry_count": 0,
        "road_cache_expected_entry_count": None,
    }

    if artifact_links.meta_path is None:
        if metric_variant in {MetricVariant.FASTEST, MetricVariant.SHORTEST}:
            default_summary["road_cache_status"] = "none"
            default_summary["road_cache_expected_entry_count"] = _expected_road_cache_entry_count(instance, None, bks_paths)
        return default_summary

    meta_path = output_repo_dir / artifact_links.meta_path
    if not meta_path.is_file():
        summary = dict(default_summary)
        if metric_variant in {MetricVariant.FASTEST, MetricVariant.SHORTEST}:
            summary["road_cache_status"] = "none"
            summary["road_cache_expected_entry_count"] = _expected_road_cache_entry_count(instance, None, bks_paths)
        return summary

    meta_payload = load_json_from_file(meta_path)
    if not isinstance(meta_payload, dict):
        return dict(default_summary)

    road_cache = meta_payload.get("road_cache")
    metrics = sorted(
        [str(metric_name) for metric_name in road_cache.keys()] if isinstance(road_cache, dict) else [],
        key=_metric_name_sort_key,
    )
    summary = {
        "has_geometry_sidecar": True,
        "viewer_render_mode": "straight_line",
        "road_cache_status": "not_applicable",
        "road_cache_metrics": metrics,
        "road_cache_entry_count": 0,
        "road_cache_expected_entry_count": None,
    }

    if metric_variant not in {MetricVariant.FASTEST, MetricVariant.SHORTEST}:
        return summary

    metric_name = metric_variant.value if metric_variant is not None else ""
    metric_cache = road_cache.get(metric_name) if isinstance(road_cache, dict) else None
    entry_count = len(metric_cache) if isinstance(metric_cache, dict) else 0
    expected_route_edges = _expected_bks_route_edges(meta_payload, bks_paths)
    expected_entry_count = _expected_road_cache_entry_count(instance, meta_payload, bks_paths)
    covers_expected_edges = _metric_cache_covers_bks_edges(metric_cache, expected_route_edges)

    if covers_expected_edges is True or (
        covers_expected_edges is None and expected_entry_count is not None and entry_count >= expected_entry_count > 0
    ):
        status: RoadCacheStatus = "complete"
    elif entry_count > 0:
        status = "partial"
    else:
        status = "none"

    summary["viewer_render_mode"] = "cached_road" if status == "complete" else "straight_line"
    summary["road_cache_status"] = status
    summary["road_cache_entry_count"] = entry_count
    summary["road_cache_expected_entry_count"] = expected_entry_count
    return summary


def derive_historical_taxonomy(instance_identifier: str) -> tuple[str | None, str | None]:
    if instance_identifier.startswith("RC") and len(instance_identifier) >= 3 and instance_identifier[2] in {"1", "2"}:
        return ("RC", instance_identifier[2])
    if instance_identifier.startswith(("R", "C")) and len(instance_identifier) >= 2 and instance_identifier[1] in {"1", "2"}:
        return (instance_identifier[0], instance_identifier[1])
    return (None, None)


def _discover_bks_paths(instance_path: Path) -> list[Path]:
    base_name = instance_path.name.removesuffix(".vrp.json")
    return sorted(instance_path.parent.glob(f"{base_name}.bks.*.json"))


def _artifact_path_to_route_path(output_repo_dir: Path, artifact_path_str: str) -> str | None:
    if not artifact_path_str.endswith(".vrp.json"):
        return None

    benchmarks_root = output_repo_dir / "benchmarks"
    relative_path = Path(artifact_path_str)
    if relative_path.parts[:1] == ("benchmarks",):
        relative_path = Path(*relative_path.parts[1:])

    parts = relative_path.parts
    if len(parts) == 4:
        problem_type = ProblemType(parts[0])
        benchmark_name = BenchmarkName(parts[1])
        size_bucket = parts[2]
        instance_identifier = Path(parts[3]).stem.removesuffix(".vrp")
        return _instance_route_path(problem_type, benchmark_name, instance_identifier, size_bucket)

    if len(parts) == 7:
        problem_type = ProblemType(parts[0])
        benchmark_name = BenchmarkName(parts[1])
        metric_variant = MetricVariant(parts[2])
        place_slug = parts[3]
        size_bucket = parts[4]
        instance_identifier = parts[5]
        return _instance_route_path(
            problem_type,
            benchmark_name,
            instance_identifier,
            size_bucket,
            metric_variant=metric_variant,
            place_slug=place_slug,
        )

    raise ValueError(f"Unsupported artifact path for route derivation: {artifact_path_str}")


def _build_artifact_links(output_repo_dir: Path, instance_path: Path, instance: AnyBenchmarkInstance) -> SiteArtifactLinks:
    if has_structured_metadata(instance):
        artifact_paths = instance.metadata.artifact_paths
        return SiteArtifactLinks(
            vrp_json_path=artifact_paths.vrp_json,
            vrp_path=artifact_paths.vrp,
            meta_path=artifact_paths.meta,
            manifest_path=artifact_paths.manifest,
        )

    raw_vrp_path = instance_path.with_suffix("")
    relative_raw_path = (
        raw_vrp_path.relative_to(output_repo_dir).as_posix() if raw_vrp_path.exists() else None
    )
    return SiteArtifactLinks(
        vrp_json_path=instance_path.relative_to(output_repo_dir).as_posix(),
        vrp_path=relative_raw_path,
    )


def _build_related_routes(output_repo_dir: Path, path_map: dict[str, str]) -> dict[str, str]:
    routes: dict[str, str] = {}
    for key, value in path_map.items():
        route_path = _artifact_path_to_route_path(output_repo_dir, value)
        if route_path is not None:
            routes[key] = route_path
    return routes


def _build_bks_entries(output_repo_dir: Path, instance_path: Path, bks_paths: list[Path] | None = None) -> list[BKSPageEntry]:
    entries: list[BKSPageEntry] = []
    for bks_path in (bks_paths if bks_paths is not None else _discover_bks_paths(instance_path)):
        bks = load_bks(bks_path)
        license_value = bks.metadata.get("license") if isinstance(bks.metadata, dict) else None
        license_url_value = bks.metadata.get("license_url") if isinstance(bks.metadata, dict) else None
        entries.append(
            BKSPageEntry(
                objective_function=bks.objective_function,
                artifact_path=bks_path.relative_to(output_repo_dir).as_posix(),
                num_routes=bks.num_routes,
                cost=bks.cost,
                authors=bks.metadata.get("authors"),
                source=bks.metadata.get("source"),
                method=bks.metadata.get("method"),
                validated_num_routes=bks.metadata.get("validated_num_routes"),
                license=license_value,
                license_url=license_url_value,
            )
        )
    return sorted(entries, key=lambda entry: _objective_sort_key(entry.objective_function))


def _resolve_instance(output_repo_dir: Path, discovered_item) -> _ResolvedSiteInstance:
    instance = discovered_item.load()
    problem_type = discovered_item.problem_type
    benchmark_name = _normalize_benchmark_name(discovered_item.benchmark_name)
    # The size bucket is path-derived (catalogue facet), not the per-instance
    # ``num_customers``. For historical/Mamut2026 the two are identical; for
    # Ortec2022 they intentionally diverge (bucket=200, instance=212) so the
    # site groups instances by bucket while the JSON preserves the exact value.
    bucket_n = discovered_item.num_customers if discovered_item.num_customers is not None else instance.num_customers
    size_bucket = f"n={bucket_n}"
    instance_identifier = instance.instance_name
    subset_segment = getattr(discovered_item, "subset", None)
    route_path = _instance_route_path(
        problem_type,
        benchmark_name,
        instance_identifier,
        size_bucket,
        metric_variant=discovered_item.metric_variant,
        place_slug=discovered_item.place_slug,
        subset=subset_segment,
    )
    topology_type, tw_type = (None, None)
    if discovered_item.metric_variant is None:
        topology_type, tw_type = derive_historical_taxonomy(instance_identifier)

    sibling_variant_routes: dict[str, str] = {}
    derived_problem_routes: dict[str, str] = {}
    source_problem_routes: dict[str, str] = {}
    authors = None
    generated_instance_at = None
    source_city = None
    num_vehicles_lb = None
    license_value: str | None = None
    license_url_value: str | None = None
    instance_provider_value: str | None = None
    if has_structured_metadata(instance):
        authors = instance.metadata.authors
        generated_instance_at = instance.metadata.generated_at
        source_city = instance.metadata.source_city
        num_vehicles_lb = instance.metadata.num_vehicles_lb
        license_value = instance.metadata.license
        license_url_value = instance.metadata.license_url
        sibling_variant_routes = _build_related_routes(output_repo_dir, instance.metadata.sibling_variant_paths)
        derived_problem_routes = _build_related_routes(output_repo_dir, instance.metadata.derived_problem_paths)
        source_problem_routes = _build_related_routes(output_repo_dir, instance.metadata.source_problem_paths)
    elif isinstance(getattr(instance, "metadata", None), dict):
        meta_dict = instance.metadata
        authors = meta_dict.get("authors")
        generated_instance_at = meta_dict.get("generated_at")
        source_city = meta_dict.get("source_city")
        num_vehicles_lb = meta_dict.get("num_vehicles_lb")
        license_value = meta_dict.get("license")
        license_url_value = meta_dict.get("license_url")
        instance_provider_value = meta_dict.get("instance_provider")
    subset_value = getattr(discovered_item, "subset", None)
    # ``subset`` is path-derived (5-part layout). Fall back to metadata for
    # tooling that constructs ``_ResolvedSiteInstance`` outside path discovery.
    if subset_value is None and isinstance(getattr(instance, "metadata", None), dict):
        subset_value = instance.metadata.get("subset")

    artifact_links = _build_artifact_links(output_repo_dir, discovered_item.instance_path, instance)
    bks_paths = _discover_bks_paths(discovered_item.instance_path)
    geometry_summary = _build_geometry_summary(
        output_repo_dir,
        instance,
        discovered_item.metric_variant,
        artifact_links,
        bks_paths,
    )
    bks_entries = _build_bks_entries(output_repo_dir, discovered_item.instance_path, bks_paths)

    return _ResolvedSiteInstance(
        locator=BenchmarkLocator(
            problem_type=problem_type,
            benchmark_name=benchmark_name,
            metric_variant=discovered_item.metric_variant,
            place_slug=discovered_item.place_slug,
            size_bucket=size_bucket,
            instance_identifier=instance_identifier,
            subset=subset_segment,
        ),
        display_name=instance_identifier,
        instance_id=discovered_item.instance_id,
        route_path=route_path,
        instance_summary=_ResolvedInstanceSummary(
            num_customers=instance.num_customers,
            num_vehicles=getattr(instance, "num_vehicles", None),
            vehicle_capacity=getattr(instance, "vehicle_capacity", None),
            authors=authors,
            generated_at=generated_instance_at,
            source_city=source_city,
            num_vehicles_lb=num_vehicles_lb,
            subset=subset_value,
            license=license_value,
            license_url=license_url_value,
            instance_provider=instance_provider_value,
        ),
        artifact_links=artifact_links,
        historical_topology_type=topology_type,
        historical_tw_type=tw_type,
        has_geometry_sidecar=bool(geometry_summary["has_geometry_sidecar"]),
        viewer_render_mode=geometry_summary["viewer_render_mode"],
        road_cache_status=geometry_summary["road_cache_status"],
        road_cache_metrics=list(geometry_summary["road_cache_metrics"]),
        road_cache_entry_count=int(geometry_summary["road_cache_entry_count"]),
        road_cache_expected_entry_count=geometry_summary["road_cache_expected_entry_count"],
        sibling_variant_routes=sibling_variant_routes,
        derived_problem_routes=derived_problem_routes,
        source_problem_routes=source_problem_routes,
        bks_entries=bks_entries,
    )


def _objective_availability(entries: list[BKSPageEntry]) -> list[ObjectiveAvailability]:
    by_objective: dict[ObjectiveFunction, BKSPageEntry] = {}
    for entry in entries:
        if entry.objective_function in by_objective:
            raise ValueError(
                f"Multiple BKS entries for objective {entry.objective_function} on the same instance — "
                "this violates the one-BKS-per-(instance, objective) invariant."
            )
        by_objective[entry.objective_function] = entry

    availability: list[ObjectiveAvailability] = []
    for objective in sorted(by_objective, key=_objective_sort_key):
        entry = by_objective[objective]
        if objective is ObjectiveFunction.HIERARCHICAL_VEHICLE_COST:
            num_routes = entry.validated_num_routes if entry.validated_num_routes is not None else entry.num_routes
        else:
            num_routes = None
        availability.append(
            ObjectiveAvailability(
                objective_function=objective,
                cost=entry.cost,
                num_routes=num_routes,
                artifact_path=entry.artifact_path,
            )
        )
    return availability


def _build_instance_list_item(resolved: _ResolvedSiteInstance) -> InstanceListItem:
    return InstanceListItem(
        locator=resolved.locator,
        display_name=resolved.display_name,
        instance_id=resolved.instance_id,
        num_customers=resolved.instance_summary.num_customers,
        route_path=resolved.route_path,
        artifact_vrp_json_path=resolved.artifact_links.vrp_json_path,
        place_slug=resolved.locator.place_slug,
        historical_topology_type=resolved.historical_topology_type,
        historical_tw_type=resolved.historical_tw_type,
        bks_count=len(resolved.bks_entries),
        viewer_render_mode=resolved.viewer_render_mode,
        road_cache_status=resolved.road_cache_status,
        objective_availability=_objective_availability(resolved.bks_entries),
    )


def _build_catalog_summary(items: list[_ResolvedSiteInstance]) -> CatalogSummary:
    place_count = len({item.locator.place_slug for item in items if item.locator.place_slug})
    size_bucket_count = len({item.locator.size_bucket for item in items})
    supported_objectives = sorted(
        {entry.objective_function for item in items for entry in item.bks_entries},
        key=_objective_sort_key,
    )
    return CatalogSummary(
        instance_count=len(items),
        bks_count=sum(len(item.bks_entries) for item in items),
        place_count=place_count,
        size_bucket_count=size_bucket_count,
        supported_objective_functions=supported_objectives,
    )


def _build_filter_facets(items: list[_ResolvedSiteInstance]) -> list[FilterFacet]:
    facets: list[FilterFacet] = []

    size_counts = Counter(item.locator.size_bucket for item in items)
    if size_counts:
        facets.append(
            FilterFacet(
                key="size_bucket",
                label="Size",
                options=[
                    FilterOption(value=size_bucket, label=size_bucket, count=count)
                    for size_bucket, count in sorted(size_counts.items())
                ],
            )
        )

    topology_counts = Counter(item.historical_topology_type for item in items if item.historical_topology_type)
    if topology_counts:
        facets.append(
            FilterFacet(
                key="historical_topology_type",
                label="Topology Type",
                options=[
                    FilterOption(value=topology_type, label=topology_type, count=count)
                    for topology_type, count in sorted(topology_counts.items())
                ],
            )
        )

    tw_counts = Counter(item.historical_tw_type for item in items if item.historical_tw_type)
    if tw_counts:
        facets.append(
            FilterFacet(
                key="historical_tw_type",
                label="TW Type",
                options=[
                    FilterOption(value=tw_type, label=tw_type, count=count)
                    for tw_type, count in sorted(tw_counts.items())
                ],
            )
        )

    place_counts = Counter(item.locator.place_slug for item in items if item.locator.place_slug)
    if place_counts:
        facets.append(
            FilterFacet(
                key="place_slug",
                label="Place",
                options=[
                    FilterOption(value=place_slug, label=place_slug.title(), count=count)
                    for place_slug, count in sorted(place_counts.items())
                ],
            )
        )

    objective_counts = Counter(
        entry.objective_function.value
        for item in items
        for entry in item.bks_entries
    )
    if objective_counts:
        facets.append(
            FilterFacet(
                key="objective_function",
                label="Objective",
                options=[
                    FilterOption(value=objective, label=objective, count=count)
                    for objective, count in sorted(objective_counts.items())
                ],
            )
        )

    has_bks_counts = Counter("yes" if item.bks_entries else "no" for item in items)
    facets.append(
        FilterFacet(
            key="has_bks",
            label="BKS Availability",
            options=[
                FilterOption(value=value, label=value.title(), count=count)
                for value, count in sorted(has_bks_counts.items())
            ],
        )
    )

    return facets


def _build_breadcrumbs(*pairs: tuple[str, str]) -> list[BreadcrumbItem]:
    return [BreadcrumbItem(label=label, route_path=route_path) for label, route_path in pairs]


_FAMILY_CONTEXT_HEADING_RE = re.compile(r"^###\s+`(?P<benchmark>[^`]+)`\s+\((?P<problem>[^)]+)\)\s*$")


class _FamilyContextSection(BaseModel):
    model_config = ConfigDict(frozen=True)

    title: str
    markdown: str


class _FamilyLicenseSection(BaseModel):
    model_config = ConfigDict(frozen=True)

    spdx_id: str | None = None
    markdown: str | None = None


def _resolve_family_context_report_path(output_repo_dir: Path, report_path: str | Path | None = None) -> Path:
    if report_path is not None:
        candidate = Path(report_path)
        return candidate if candidate.is_absolute() else output_repo_dir / candidate
    return DEFAULT_FAMILY_CONTEXT_REPORT_PATH


def _load_family_context_sections(
    output_repo_dir: Path,
    report_path: str | Path | None = None,
) -> dict[tuple[ProblemType, BenchmarkName], _FamilyContextSection]:
    path = _resolve_family_context_report_path(output_repo_dir, report_path)
    if not path.is_file():
        return {}

    sections: dict[tuple[ProblemType, BenchmarkName], _FamilyContextSection] = {}
    active_key: tuple[ProblemType, BenchmarkName] | None = None
    active_title: str | None = None
    active_lines: list[str] = []

    def flush() -> None:
        nonlocal active_key, active_title, active_lines
        if active_key is not None and active_title is not None:
            markdown = "\n".join(active_lines).strip()
            if markdown:
                sections[active_key] = _FamilyContextSection(title=active_title, markdown=markdown)
        active_key = None
        active_title = None
        active_lines = []

    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("### "):
            flush()
            match = _FAMILY_CONTEXT_HEADING_RE.match(line)
            if match is None:
                continue
            try:
                problem_type = ProblemType(match.group("problem"))
                benchmark_name = BenchmarkName(match.group("benchmark"))
            except ValueError:
                continue
            active_key = (problem_type, benchmark_name)
            active_title = f"{benchmark_name.value} ({problem_type.value})"
            continue
        if active_key is not None:
            active_lines.append(line)

    flush()
    return sections


def _context_summary_from_markdown(markdown: str) -> str:
    paragraphs = [paragraph.strip() for paragraph in re.split(r"\n\s*\n", markdown) if paragraph.strip()]
    if not paragraphs:
        return ""
    return re.sub(r"\s+", " ", paragraphs[0])


_SPDX_LICENSE_RE = re.compile(r"^SPDX-License-Identifier:\s*(?P<id>\S+)\s*$")
_STANDALONE_URL_RE = re.compile(r"^https?://\S+$")


def _license_file_path(output_repo_dir: Path, problem_type: ProblemType, benchmark_name: BenchmarkName) -> Path:
    return output_repo_dir / "benchmarks" / problem_type.value / benchmark_name.value / "LICENSE"


def _markdown_link_for_url(url: str) -> str:
    return f"[{url}]({url})"


def _load_family_license_section(
    output_repo_dir: Path,
    problem_type: ProblemType,
    benchmark_name: BenchmarkName,
) -> _FamilyLicenseSection:
    path = _license_file_path(output_repo_dir, problem_type, benchmark_name)
    if not path.is_file():
        return _FamilyLicenseSection()

    lines = path.read_text(encoding="utf-8").splitlines()
    spdx_id: str | None = None
    if lines:
        match = _SPDX_LICENSE_RE.match(lines[0].strip())
        if match is not None:
            spdx_id = match.group("id")
            lines = lines[1:]

    while lines and not lines[0].strip():
        lines = lines[1:]
    while lines and not lines[-1].strip():
        lines = lines[:-1]

    markdown_lines = []
    for line in lines:
        stripped = line.strip()
        markdown_lines.append(_markdown_link_for_url(stripped) if _STANDALONE_URL_RE.match(stripped) else line.rstrip())
    markdown = "\n".join(markdown_lines).strip() or None
    if spdx_id is None and markdown is None:
        return _FamilyLicenseSection()
    return _FamilyLicenseSection(spdx_id=spdx_id, markdown=markdown)


def _write_payload(
    site_output_dir: Path,
    route_path: str,
    payload: BaseModel,
    payload_root_dir: str | Path = DEFAULT_SITE_PAYLOAD_ROOT_DIR,
) -> Path:
    payload_path = _route_payload_path(site_output_dir, route_path, payload_root_dir)
    save_json_to_file(payload.model_dump(mode="json"), payload_path)
    return payload_path


def _resolve_site_output_dir(output_repo_dir: Path, site_output_dir: str | Path | None) -> Path:
    if site_output_dir is None:
        return output_repo_dir / DEFAULT_SITE_OUTPUT_DIR
    candidate = Path(site_output_dir)
    return candidate if candidate.is_absolute() else output_repo_dir / candidate


def _make_subroute_entries(
    grouped_items: dict[str, list[_ResolvedSiteInstance]],
    route_builder,
) -> list[SubrouteEntry]:
    entries: list[SubrouteEntry] = []
    for key, items in sorted(grouped_items.items()):
        entries.append(
            SubrouteEntry(
                key=key,
                label=key,
                route_path=route_builder(key),
                instance_count=len(items),
                bks_count=sum(len(item.bks_entries) for item in items),
            )
        )
    return entries


def _build_instance_page_payload(
    resolved: _ResolvedSiteInstance,
    generated_at: str,
    snapshot: SnapshotRef,
) -> InstancePagePayload:
    supported_objectives = [entry.objective_function for entry in resolved.bks_entries]

    breadcrumbs = _build_breadcrumbs(
        ("benchmarks", "/benchmarks/"),
        (resolved.locator.problem_type.value, _problem_route_path(resolved.locator.problem_type)),
        (
            resolved.locator.benchmark_name.value,
            _family_route_path(resolved.locator.problem_type, resolved.locator.benchmark_name),
        ),
    )
    if resolved.locator.metric_variant is not None:
        breadcrumbs.append(
            BreadcrumbItem(
                label=resolved.locator.metric_variant.value,
                route_path=_variant_route_path(
                    resolved.locator.problem_type,
                    resolved.locator.benchmark_name,
                    resolved.locator.metric_variant,
                ),
            )
        )
    if resolved.locator.place_slug is not None and resolved.locator.metric_variant is not None:
        breadcrumbs.append(
            BreadcrumbItem(
                label=resolved.locator.place_slug,
                route_path=_place_route_path(
                    resolved.locator.problem_type,
                    resolved.locator.benchmark_name,
                    resolved.locator.metric_variant,
                    resolved.locator.place_slug,
                ),
            )
        )
    if resolved.locator.subset is not None:
        breadcrumbs.append(
            BreadcrumbItem(
                label=resolved.locator.subset,
                route_path=_subset_route_path(
                    resolved.locator.problem_type,
                    resolved.locator.benchmark_name,
                    resolved.locator.subset,
                ),
            )
        )
    breadcrumbs.append(
        BreadcrumbItem(
            label=resolved.locator.size_bucket,
            route_path=_size_route_path(
                resolved.locator.problem_type,
                resolved.locator.benchmark_name,
                resolved.locator.size_bucket,
                metric_variant=resolved.locator.metric_variant,
                place_slug=resolved.locator.place_slug,
                subset=resolved.locator.subset,
            ),
        )
    )
    breadcrumbs.append(BreadcrumbItem(label=resolved.display_name, route_path=resolved.route_path))

    return InstancePagePayload(
        generated_at=generated_at,
        snapshot=snapshot,
        route_path=resolved.route_path,
        title=resolved.display_name,
        breadcrumbs=breadcrumbs,
        locator=resolved.locator,
        summary=InstancePageSummary(
            display_name=resolved.display_name,
            problem_type=resolved.locator.problem_type,
            benchmark_name=resolved.locator.benchmark_name,
            metric_variant=resolved.locator.metric_variant,
            place_slug=resolved.locator.place_slug,
            size_bucket=resolved.locator.size_bucket,
            num_customers=resolved.instance_summary.num_customers,
            historical_topology_type=resolved.historical_topology_type,
            historical_tw_type=resolved.historical_tw_type,
            num_vehicles=resolved.instance_summary.num_vehicles,
            num_vehicles_lb=resolved.instance_summary.num_vehicles_lb,
            vehicle_capacity=resolved.instance_summary.vehicle_capacity,
            authors=resolved.instance_summary.authors,
            generated_at=resolved.instance_summary.generated_at,
            source_city=resolved.instance_summary.source_city,
            has_geometry_sidecar=resolved.has_geometry_sidecar,
            viewer_render_mode=resolved.viewer_render_mode,
            road_cache_status=resolved.road_cache_status,
            road_cache_metrics=resolved.road_cache_metrics,
            road_cache_entry_count=resolved.road_cache_entry_count,
            road_cache_expected_entry_count=resolved.road_cache_expected_entry_count,
            supported_objective_functions=supported_objectives,
            subset=resolved.instance_summary.subset,
            license=resolved.instance_summary.license,
            license_url=resolved.instance_summary.license_url,
            instance_provider=resolved.instance_summary.instance_provider,
        ),
        artifact_links=resolved.artifact_links,
        sibling_variant_routes=resolved.sibling_variant_routes,
        derived_problem_routes=resolved.derived_problem_routes,
        source_problem_routes=resolved.source_problem_routes,
        bks_entries=resolved.bks_entries,
    )


def _sorted_problem_types(items: list[_ResolvedSiteInstance]) -> list[ProblemType]:
    order = {ProblemType.CVRP: 0, ProblemType.VRPTW: 1}
    return sorted({item.locator.problem_type for item in items}, key=lambda value: (order.get(value, 99), value.value))


def _sorted_benchmark_names(items: list[_ResolvedSiteInstance]) -> list[BenchmarkName]:
    order = {
        BenchmarkName.SINTEF_2008: 0,
        BenchmarkName.DIMACS_2021: 1,
        BenchmarkName.ORTEC_2022: 2,
        BenchmarkName.MAMUT_2026: 3,
    }
    return sorted({item.locator.benchmark_name for item in items}, key=lambda value: (order.get(value, 99), value.value))


def _build_root_benchmarks_index(
    items: list[_ResolvedSiteInstance],
    generated_at: str,
    snapshot: SnapshotRef,
) -> BenchmarksIndexPayload:
    problem_cards: list[ProblemSummaryCard] = []
    for problem_type in _sorted_problem_types(items):
        problem_items = [item for item in items if item.locator.problem_type == problem_type]
        benchmark_names = _sorted_benchmark_names(problem_items)
        objectives = sorted(
            {entry.objective_function for item in problem_items for entry in item.bks_entries},
            key=_objective_sort_key,
        )
        problem_cards.append(
            ProblemSummaryCard(
                problem_type=problem_type,
                route_path=_problem_route_path(problem_type),
                benchmark_names=benchmark_names,
                family_count=len(benchmark_names),
                instance_count=len(problem_items),
                bks_count=sum(len(item.bks_entries) for item in problem_items),
                supported_objective_functions=objectives,
            )
        )

    return BenchmarksIndexPayload(
        generated_at=generated_at,
        snapshot=snapshot,
        route_path="/benchmarks/",
        breadcrumbs=_build_breadcrumbs(("benchmarks", "/benchmarks/")),
        problems=problem_cards,
    )


def _build_home_page_payload(
    site_counts: SiteCounts,
    root_payload: BenchmarksIndexPayload,
    generated_at: str,
    snapshot: SnapshotRef,
    history_summary: str,
) -> HomePagePayload:
    return HomePagePayload(
        generated_at=generated_at,
        snapshot=snapshot,
        title="MAMUT-routing",
        subtitle="Benchmark distribution, provenance, and routing workbench.",
        hero_summary=(
            "Explore curated CVRP and VRPTW benchmark families, inspect instance artifacts, and open the same instances in the shared workbench shell."
        ),
        latest_publication_summary=history_summary,
        counts=site_counts,
        problems=root_payload.problems,
    )


def _build_project_page_payload(
    generated_at: str,
    snapshot: SnapshotRef,
) -> ProjectPagePayload:
    return ProjectPagePayload(
        generated_at=generated_at,
        snapshot=snapshot,
        title="ANR MAMUT Project",
        subtitle="Research context for the MAMUT-routing benchmark and instance-generation work.",
        breadcrumbs=[],
        anr_project_code="ANR-22-CE22-0016",
        anr_project_url="https://anr.fr/Projet-ANR-22-CE22-0016",
        anr_project_title="Machine learning et matheuristiques pour le transport urbain - MAMUT",
        anr_context=(
            "MAMUT is ANR-funded research project regrouping several French public laboratories and teams alongside private entities on the study of vehicle-routing problems in urban logistics. "
            "The project frames routing as a meeting point between Operation Research, Data Science, Applied Algorithmics and Artificial Intelligence "
            "and aims to advance resolution methods while pushing forward modern software and data management practices on experimental evaluation."
        ),
        facts=[
            ProjectFact(label="Funding call", value="CE22 - Transports et mobilites, constructions dans les territoires urbains et peri-urbains 2022"),
            ProjectFact(label="Coordinator", value="Marc Sevaux, Universite Bretagne Sud"),
            ProjectFact(label="Partners", value="CITI EA3720, Mapotempo, LAB-STICC IMT Atlantique, LAB-STICC Universite Bretagne Sud"),
            ProjectFact(label="ANR support", value="497,722 euros"),
            ProjectFact(label="Scientific period", value="2023 - 2026"),
            ProjectFact(label="Official record", value="ANR project page", href="https://anr.fr/Projet-ANR-22-CE22-0016"),
        ],
        research_threads=[
            ProjectNarrativeBlock(
                title="Shared project frame",
                body=(
                    "The ANR project aims to make urban vehicle-routing research more reusable: characterize problem classes, "
                    "design hybrid OR/AI solvers, and expose problems, instances, and algorithms through a collaborative platform. "
                    "This website fits that last objective by turning benchmark artifacts, provenance, and visualization into a browsable publication."
                ),
                tags=["open benchmark", "urban logistics", "collaborative platform"],
            ),
            ProjectNarrativeBlock(
                title="Onyr's benchmark thread",
                body=(
                    "Onyr's doctoral work focuses on the benchmark side: organizing CVRP and VRPTW families, preserving objective semantics, "
                    "tracking best-known solutions, and making instance artifacts inspectable and comparable. "
                    "The MAMUT-routing site is the public surface for that reproducibility work."
                ),
                tags=["benchmarks", "BKS", "provenance"],
            ),
            ProjectNarrativeBlock(
                title="A. Pichon's instance-generation thread",
                body=(
                    "A. Pichon's doctoral work complements it from the generation side: producing realistic OSM-backed instances and routes "
                    "that can stress the same solvers under urban geography, travel-time metrics, and time-window constraints. "
                    "The workbench connects this generation flow back to the benchmark catalog."
                ),
                tags=["instance generation", "OSM", "VRPTW"],
            ),
        ],
        collaboration_note=(
            "Together, these two doctoral tracks explain how this work came to be: the benchmark library needs realistic, documented inputs, "
            "and the generator needs a benchmark contract where generated instances can be stored, viewed, compared, and reused."
        ),
    )


def _build_objective_related_routes(
    items: list[_ResolvedSiteInstance],
    objective_function: ObjectiveFunction,
) -> list[SubrouteEntry]:
    grouped_items: dict[tuple[ProblemType, BenchmarkName], list[_ResolvedSiteInstance]] = {}
    for item in items:
        grouped_items.setdefault((item.locator.problem_type, item.locator.benchmark_name), []).append(item)

    problem_order = {ProblemType.CVRP: 0, ProblemType.VRPTW: 1}
    benchmark_order = {
        BenchmarkName.SINTEF_2008: 0,
        BenchmarkName.DIMACS_2021: 1,
        BenchmarkName.ORTEC_2022: 2,
        BenchmarkName.MAMUT_2026: 3,
    }
    entries: list[SubrouteEntry] = []
    for problem_type, benchmark_name in sorted(
        grouped_items,
        key=lambda key: (
            problem_order.get(key[0], 99),
            benchmark_order.get(key[1], 99),
            key[0].value,
            key[1].value,
        ),
    ):
        family_items = grouped_items[(problem_type, benchmark_name)]
        matching_items = [
            item
            for item in family_items
            if any(entry.objective_function == objective_function for entry in item.bks_entries)
        ]
        if not matching_items:
            continue
        entries.append(
            SubrouteEntry(
                key=f"{problem_type.value}:{benchmark_name.value}:{objective_function.value}",
                label=f"{problem_type.value} / {benchmark_name.value}",
                route_path=_family_route_path(problem_type, benchmark_name),
                instance_count=len(matching_items),
                bks_count=sum(
                    1
                    for item in family_items
                    for entry in item.bks_entries
                    if entry.objective_function == objective_function
                ),
            )
        )
    return entries


def _build_objectives_page_payload(
    items: list[_ResolvedSiteInstance],
    generated_at: str,
    snapshot: SnapshotRef,
) -> ObjectivesPagePayload:
    explainers = [
        ObjectiveExplainer(
            objective_function=ObjectiveFunction.HIERARCHICAL_VEHICLE_COST,
            short_label="HVC",
            title="HierarchicalVehicleCost",
            description="Lexicographic VRPTW objective: minimize the number of vehicles first, then minimize total cost.",
            interpretation_notes=[
                "Compare HVC results as fleet-first solutions rather than pure distance optimizers.",
                "Historical SINTEF-style references and some VRPTW Mamut2026 BKS entries use this objective.",
            ],
            related_routes=_build_objective_related_routes(items, ObjectiveFunction.HIERARCHICAL_VEHICLE_COST),
        ),
        ObjectiveExplainer(
            objective_function=ObjectiveFunction.MONO_COST,
            short_label="MC",
            title="MonoCost",
            description="Single-objective cost minimization where total routing cost is optimized directly.",
            interpretation_notes=[
                "Compare MonoCost results as cost-first solutions even when they use more vehicles than HVC references.",
                "DIMACS-style references, the Ortec2022 (EURO Meets NeurIPS 2022) family, and all current CVRP Mamut2026 BKS entries use this objective.",
            ],
            related_routes=_build_objective_related_routes(items, ObjectiveFunction.MONO_COST),
        ),
    ]
    return ObjectivesPagePayload(
        generated_at=generated_at,
        snapshot=snapshot,
        route_path="/objectives/",
        title="Objectives",
        breadcrumbs=[],
        explainers=explainers,
    )


def _build_history_detail_payload(
    snapshot_manifest: SiteSnapshotManifest,
    history_entry: SiteHistoryEntry,
    change_log: SnapshotChangeLog,
    generated_at: str,
    snapshot: SnapshotRef,
) -> HistoryDetailPayload:
    route_path = _history_detail_route_path(snapshot.snapshot_id)
    return HistoryDetailPayload(
        generated_at=generated_at,
        snapshot=snapshot,
        route_path=route_path,
        title=f"Snapshot {snapshot.snapshot_id}",
        breadcrumbs=_build_breadcrumbs(("History", "/history/"), (snapshot.snapshot_id, route_path)),
        summary=history_entry.summary,
        counts=snapshot_manifest.counts,
        benchmark_index_path=snapshot_manifest.benchmark_index_path,
        history_path=snapshot_manifest.history_path,
        affected_problem_types=history_entry.affected_problem_types,
        affected_benchmark_names=history_entry.affected_benchmark_names,
        affected_objective_functions=history_entry.affected_objective_functions,
        change_log=change_log,
    )


SNAPSHOTS_DIR_NAME = "snapshots"


def _inventory_path(site_output: Path, snapshot_id: str) -> Path:
    return site_output / "site" / SNAPSHOTS_DIR_NAME / f"{snapshot_id}.inventory.json"


def _build_inventory(resolved_items: list[_ResolvedSiteInstance]) -> dict:
    """Build the diff-source-of-truth inventory for the current snapshot."""
    instances: dict[str, dict] = {}
    for item in resolved_items:
        bks: dict[str, dict] = {}
        for entry in item.bks_entries:
            num_routes = (
                entry.validated_num_routes
                if entry.objective_function is ObjectiveFunction.HIERARCHICAL_VEHICLE_COST and entry.validated_num_routes is not None
                else entry.num_routes
            )
            bks[entry.objective_function.value] = {
                "cost": entry.cost,
                "num_routes": num_routes,
                "authors": entry.authors,
                "method": entry.method,
            }
        metric_variant = item.locator.metric_variant.value if item.locator.metric_variant is not None else None
        instances[item.instance_id] = {
            "problem_type": item.locator.problem_type.value,
            "benchmark_name": item.locator.benchmark_name.value,
            "metric_variant": metric_variant,
            "place_slug": item.locator.place_slug,
            "num_customers": item.instance_summary.num_customers,
            "instance_name": item.display_name,
            "bks": bks,
        }
    return {"instances": instances}


def _save_inventory(site_output: Path, snapshot_id: str, generated_at: str, inventory: dict) -> Path:
    payload = {
        "snapshot_id": snapshot_id,
        "generated_at": generated_at,
        "instances": inventory["instances"],
    }
    path = _inventory_path(site_output, snapshot_id)
    save_json_to_file(payload, path)
    return path


def _load_previous_inventory(
    site_output: Path,
    existing_ledger: SiteHistoryLedger | None,
    current_snapshot_id: str,
) -> dict | None:
    """Load the inventory of the most recent snapshot that is NOT the current one.

    Returns None if no prior inventory file exists (treated as initial mode).
    """
    if existing_ledger is None:
        return None
    for entry in existing_ledger.entries:
        prior_id = entry.snapshot.snapshot_id
        if prior_id == current_snapshot_id:
            continue
        path = _inventory_path(site_output, prior_id)
        if path.exists():
            payload = load_json_from_file(path)
            return {"instances": payload.get("instances", {})}
        # If the file is missing for some reason (manual cleanup), keep walking older entries.
    return None


def _instance_change_payload_from_inventory(
    instance_id: str,
    record: dict,
    kind: Literal["added", "removed"],
) -> InstanceChange:
    metric_variant_value = record.get("metric_variant")
    return InstanceChange(
        instance_id=instance_id,
        problem_type=ProblemType(record["problem_type"]),
        benchmark_name=BenchmarkName(record["benchmark_name"]),
        metric_variant=MetricVariant(metric_variant_value) if metric_variant_value else None,
        place_slug=record.get("place_slug"),
        num_customers=record["num_customers"],
        instance_name=record["instance_name"],
        kind=kind,
    )


def _bks_change_from_inventory(
    instance_id: str,
    record: dict,
    objective_function_value: str,
    *,
    kind: Literal["added", "removed", "improved", "regressed"],
    prev: BksValue | None,
    new: BksValue | None,
    cost_delta: int | float | None = None,
    cost_pct: float | None = None,
    routes_delta: int | None = None,
    routes_pct: float | None = None,
) -> BksChange:
    metric_variant_value = record.get("metric_variant")
    return BksChange(
        instance_id=instance_id,
        problem_type=ProblemType(record["problem_type"]),
        benchmark_name=BenchmarkName(record["benchmark_name"]),
        metric_variant=MetricVariant(metric_variant_value) if metric_variant_value else None,
        place_slug=record.get("place_slug"),
        num_customers=record["num_customers"],
        instance_name=record["instance_name"],
        objective_function=ObjectiveFunction(objective_function_value),
        kind=kind,
        prev=prev,
        new=new,
        cost_delta=cost_delta,
        cost_pct=cost_pct,
        routes_delta=routes_delta,
        routes_pct=routes_pct,
    )


def _bks_value_from_record(record: dict) -> BksValue:
    return BksValue(
        cost=record.get("cost"),
        num_routes=record.get("num_routes"),
        authors=record.get("authors"),
        method=record.get("method"),
    )


def _classify_bks_pair(
    objective_function_value: str,
    prev_record: dict,
    new_record: dict,
) -> tuple[Literal["improved", "regressed"] | None, int | float | None, float | None, int | None, float | None]:
    """Return (kind, cost_delta, cost_pct, routes_delta, routes_pct) for a BKS pair.

    kind is None when the pair is exactly equal (no change). All deltas are
    new − prev so a negative delta == improvement when sense matches.
    """
    prev_cost = prev_record.get("cost")
    new_cost = new_record.get("cost")
    prev_routes = prev_record.get("num_routes")
    new_routes = new_record.get("num_routes")

    cost_delta: int | float | None
    if prev_cost is None or new_cost is None:
        cost_delta = None
        cost_pct = None
    else:
        cost_delta = new_cost - prev_cost
        cost_pct = (cost_delta / prev_cost * 100.0) if prev_cost not in (0, 0.0) else None

    routes_delta: int | None
    if prev_routes is None or new_routes is None:
        routes_delta = None
        routes_pct = None
    else:
        routes_delta = new_routes - prev_routes
        routes_pct = (routes_delta / prev_routes * 100.0) if prev_routes not in (0, 0.0) else None

    objective = ObjectiveFunction(objective_function_value)
    if objective is ObjectiveFunction.HIERARCHICAL_VEHICLE_COST:
        prev_key = (prev_routes if prev_routes is not None else 0, prev_cost if prev_cost is not None else 0)
        new_key = (new_routes if new_routes is not None else 0, new_cost if new_cost is not None else 0)
        if new_key == prev_key:
            return (None, cost_delta, cost_pct, routes_delta, routes_pct)
        kind = "improved" if new_key < prev_key else "regressed"
        return (kind, cost_delta, cost_pct, routes_delta, routes_pct)

    # MonoCost: compare cost only.
    if prev_cost is None or new_cost is None or new_cost == prev_cost:
        return (None, cost_delta, cost_pct, routes_delta, routes_pct)
    kind = "improved" if new_cost < prev_cost else "regressed"
    return (kind, cost_delta, cost_pct, routes_delta, routes_pct)


def _instance_sort_key(record: dict) -> tuple:
    return (
        record["problem_type"],
        record["benchmark_name"],
        record.get("metric_variant") or "",
        record.get("place_slug") or "",
        record["num_customers"],
        record["instance_name"],
    )


def _compute_change_log(
    prev_inventory: dict | None,
    new_inventory: dict,
) -> SnapshotChangeLog:
    is_initial = prev_inventory is None
    prev_instances: dict[str, dict] = (prev_inventory or {}).get("instances", {})
    new_instances: dict[str, dict] = new_inventory.get("instances", {})

    prev_families = {(rec["problem_type"], rec["benchmark_name"]) for rec in prev_instances.values()}
    new_families = {(rec["problem_type"], rec["benchmark_name"]) for rec in new_instances.values()}

    family_changes: list[FamilyChange] = []
    for problem_type_value, benchmark_name_value in sorted(new_families - prev_families):
        family_changes.append(
            FamilyChange(
                problem_type=ProblemType(problem_type_value),
                benchmark_name=BenchmarkName(benchmark_name_value),
                kind="added",
            )
        )
    for problem_type_value, benchmark_name_value in sorted(prev_families - new_families):
        family_changes.append(
            FamilyChange(
                problem_type=ProblemType(problem_type_value),
                benchmark_name=BenchmarkName(benchmark_name_value),
                kind="removed",
            )
        )

    instance_changes: list[InstanceChange] = []
    bks_changes: list[BksChange] = []

    added_instance_ids = sorted(set(new_instances) - set(prev_instances), key=lambda iid: _instance_sort_key(new_instances[iid]))
    removed_instance_ids = sorted(set(prev_instances) - set(new_instances), key=lambda iid: _instance_sort_key(prev_instances[iid]))
    common_instance_ids = sorted(set(new_instances) & set(prev_instances), key=lambda iid: _instance_sort_key(new_instances[iid]))

    for instance_id in added_instance_ids:
        record = new_instances[instance_id]
        instance_changes.append(_instance_change_payload_from_inventory(instance_id, record, "added"))
        for objective_value in sorted(record["bks"], key=lambda v: _objective_sort_key(ObjectiveFunction(v))):
            bks_value = _bks_value_from_record(record["bks"][objective_value])
            bks_changes.append(
                _bks_change_from_inventory(
                    instance_id,
                    record,
                    objective_value,
                    kind="added",
                    prev=None,
                    new=bks_value,
                )
            )

    for instance_id in removed_instance_ids:
        record = prev_instances[instance_id]
        instance_changes.append(_instance_change_payload_from_inventory(instance_id, record, "removed"))
        for objective_value in sorted(record["bks"], key=lambda v: _objective_sort_key(ObjectiveFunction(v))):
            bks_value = _bks_value_from_record(record["bks"][objective_value])
            bks_changes.append(
                _bks_change_from_inventory(
                    instance_id,
                    record,
                    objective_value,
                    kind="removed",
                    prev=bks_value,
                    new=None,
                )
            )

    for instance_id in common_instance_ids:
        prev_record = prev_instances[instance_id]
        new_record = new_instances[instance_id]
        prev_bks: dict = prev_record.get("bks", {})
        new_bks: dict = new_record.get("bks", {})

        for objective_value in sorted(set(new_bks) - set(prev_bks), key=lambda v: _objective_sort_key(ObjectiveFunction(v))):
            bks_changes.append(
                _bks_change_from_inventory(
                    instance_id,
                    new_record,
                    objective_value,
                    kind="added",
                    prev=None,
                    new=_bks_value_from_record(new_bks[objective_value]),
                )
            )
        for objective_value in sorted(set(prev_bks) - set(new_bks), key=lambda v: _objective_sort_key(ObjectiveFunction(v))):
            bks_changes.append(
                _bks_change_from_inventory(
                    instance_id,
                    new_record,  # use the still-existing instance record for locator info
                    objective_value,
                    kind="removed",
                    prev=_bks_value_from_record(prev_bks[objective_value]),
                    new=None,
                )
            )
        for objective_value in sorted(set(prev_bks) & set(new_bks), key=lambda v: _objective_sort_key(ObjectiveFunction(v))):
            kind, cost_delta, cost_pct, routes_delta, routes_pct = _classify_bks_pair(
                objective_value, prev_bks[objective_value], new_bks[objective_value]
            )
            if kind is None:
                continue
            bks_changes.append(
                _bks_change_from_inventory(
                    instance_id,
                    new_record,
                    objective_value,
                    kind=kind,
                    prev=_bks_value_from_record(prev_bks[objective_value]),
                    new=_bks_value_from_record(new_bks[objective_value]),
                    cost_delta=cost_delta,
                    cost_pct=cost_pct,
                    routes_delta=routes_delta,
                    routes_pct=routes_pct,
                )
            )

    counts = ChangeCounts(
        families_added=sum(1 for c in family_changes if c.kind == "added"),
        families_removed=sum(1 for c in family_changes if c.kind == "removed"),
        instances_added=sum(1 for c in instance_changes if c.kind == "added"),
        instances_removed=sum(1 for c in instance_changes if c.kind == "removed"),
        bks_added=sum(1 for c in bks_changes if c.kind == "added"),
        bks_removed=sum(1 for c in bks_changes if c.kind == "removed"),
        bks_improved=sum(1 for c in bks_changes if c.kind == "improved"),
        bks_regressed=sum(1 for c in bks_changes if c.kind == "regressed"),
    )

    return SnapshotChangeLog(
        is_initial=is_initial,
        counts=counts,
        family_changes=family_changes,
        instance_changes=instance_changes,
        bks_changes=bks_changes,
    )


def _build_problem_index(
    items: list[_ResolvedSiteInstance],
    problem_type: ProblemType,
    generated_at: str,
    snapshot: SnapshotRef,
    family_context_sections: dict[tuple[ProblemType, BenchmarkName], _FamilyContextSection] | None = None,
) -> ProblemIndexPayload:
    family_context_sections = family_context_sections or {}
    problem_items = [item for item in items if item.locator.problem_type == problem_type]
    family_cards: list[FamilySummaryCard] = []
    for benchmark_name in _sorted_benchmark_names(problem_items):
        family_items = [item for item in problem_items if item.locator.benchmark_name == benchmark_name]
        variants = sorted(
            {item.locator.metric_variant for item in family_items if item.locator.metric_variant is not None},
            key=_metric_variant_sort_key,
        )
        objectives = sorted(
            {entry.objective_function for item in family_items for entry in item.bks_entries},
            key=_objective_sort_key,
        )
        family_cards.append(
            FamilySummaryCard(
                benchmark_name=benchmark_name,
                route_path=_family_route_path(problem_type, benchmark_name),
                context_route_path=(
                    _family_context_route_path(problem_type, benchmark_name)
                    if (problem_type, benchmark_name) in family_context_sections
                    else None
                ),
                metric_variants=variants,
                instance_count=len(family_items),
                bks_count=sum(len(item.bks_entries) for item in family_items),
                supported_objective_functions=objectives,
            )
        )

    return ProblemIndexPayload(
        generated_at=generated_at,
        snapshot=snapshot,
        route_path=_problem_route_path(problem_type),
        title=problem_type.value,
        breadcrumbs=_build_breadcrumbs(("benchmarks", "/benchmarks/"), (problem_type.value, _problem_route_path(problem_type))),
        problem_type=problem_type,
        summary=_build_catalog_summary(problem_items),
        families=family_cards,
    )


def _build_catalog_index(
    *,
    payload_kind: SitePayloadKind,
    route_path: str,
    title: str,
    breadcrumbs: list[BreadcrumbItem],
    items: list[_ResolvedSiteInstance],
    problem_type: ProblemType,
    benchmark_name: BenchmarkName,
    metric_variant: MetricVariant | None,
    place_slug: str | None,
    size_bucket: str | None,
    variant_routes: list[SubrouteEntry],
    place_routes: list[SubrouteEntry],
    size_routes: list[SubrouteEntry],
    generated_at: str,
    snapshot: SnapshotRef,
    description: str | None = None,
    context_route_path: str | None = None,
    context_summary: str | None = None,
    subset: str | None = None,
    subset_routes: list[SubrouteEntry] | None = None,
) -> CatalogIndexPayload:
    return CatalogIndexPayload(
        payload_kind=payload_kind,
        generated_at=generated_at,
        snapshot=snapshot,
        route_path=route_path,
        title=title,
        description=description,
        context_route_path=context_route_path,
        context_summary=context_summary,
        breadcrumbs=breadcrumbs,
        problem_type=problem_type,
        benchmark_name=benchmark_name,
        metric_variant=metric_variant,
        place_slug=place_slug,
        size_bucket=size_bucket,
        subset=subset,
        summary=_build_catalog_summary(items),
        filter_facets=_build_filter_facets(items),
        variant_routes=variant_routes,
        place_routes=place_routes,
        size_routes=size_routes,
        subset_routes=subset_routes or [],
        items=[
            _build_instance_list_item(item)
            for item in sorted(items, key=lambda current: (current.instance_summary.num_customers, current.display_name))
        ],
    )


def _build_family_context_page_payload(
    *,
    output_repo_dir: Path,
    problem_type: ProblemType,
    benchmark_name: BenchmarkName,
    context_section: _FamilyContextSection,
    generated_at: str,
    snapshot: SnapshotRef,
) -> FamilyContextPagePayload:
    route_path = _family_context_route_path(problem_type, benchmark_name)
    family_route_path = _family_route_path(problem_type, benchmark_name)
    license_section = _load_family_license_section(output_repo_dir, problem_type, benchmark_name)
    return FamilyContextPagePayload(
        generated_at=generated_at,
        snapshot=snapshot,
        route_path=route_path,
        title=f"{context_section.title} Context",
        breadcrumbs=_build_breadcrumbs(
            ("benchmarks", "/benchmarks/"),
            (problem_type.value, _problem_route_path(problem_type)),
            (benchmark_name.value, family_route_path),
            ("context", route_path),
        ),
        problem_type=problem_type,
        benchmark_name=benchmark_name,
        markdown=context_section.markdown,
        family_route_path=family_route_path,
        license_spdx_id=license_section.spdx_id,
        license_markdown=license_section.markdown,
    )


def resolve_site_build_jobs(jobs: str | int, item_count: int | None = None) -> int:
    if isinstance(jobs, str):
        if jobs == "auto":
            resolved = max(1, (os.cpu_count() or 1) - 2)
        else:
            try:
                resolved = int(jobs)
            except ValueError as exc:
                raise ValueError("--jobs must be 'auto' or an integer >= 1") from exc
    else:
        resolved = int(jobs)
    if resolved < 1:
        raise ValueError("--jobs must be 'auto' or an integer >= 1")
    if item_count is not None:
        return min(resolved, max(1, item_count))
    return resolved


def _paths_for_summary(site_output: Path, paths: list[Path]) -> list[str]:
    values: list[str] = []
    for path in paths:
        try:
            values.append(path.relative_to(site_output).as_posix())
        except ValueError:
            values.append(path.as_posix())
    return sorted(values)


def _resolve_instances(
    output_repo: Path,
    discovered_instances,
    *,
    jobs: str | int,
    reporter: ProgressReporter | None = None,
) -> list[_ResolvedSiteInstance]:
    resolved_jobs = resolve_site_build_jobs(jobs, len(discovered_instances))
    if reporter is not None:
        reporter.phase(
            "resolving instances",
            instances=len(discovered_instances),
            jobs=resolved_jobs,
        )
    if not discovered_instances:
        return []

    resolved_items: list[_ResolvedSiteInstance | None] = [None] * len(discovered_instances)
    with (reporter.task("resolve instances", len(discovered_instances)) if reporter else _NullProgressTask()) as task:
        if resolved_jobs == 1:
            for index, item in enumerate(discovered_instances):
                resolved_items[index] = _resolve_instance(output_repo, item)
                task.update(detail=getattr(item, "instance_name", None))
        else:
            with ProcessPoolExecutor(max_workers=resolved_jobs) as executor:
                futures = {
                    executor.submit(_resolve_instance, output_repo, item): (index, item)
                    for index, item in enumerate(discovered_instances)
                }
                for future in as_completed(futures):
                    index, item = futures[future]
                    resolved_items[index] = future.result()
                    task.update(detail=getattr(item, "instance_name", None))
    return [item for item in resolved_items if item is not None]


class _NullProgressTask:
    def __enter__(self) -> "_NullProgressTask":
        return self

    def __exit__(self, *args) -> None:
        return None

    def update(self, *args, **kwargs) -> None:
        return None


def generate_site_payloads(
    output_repo_dir: str | Path,
    *,
    source_commit: str,
    published_at: str | None = None,
    snapshot_id: str | None = None,
    history_summary: str = "Generated site payload snapshot.",
    source_branch: str | None = None,
    schema_version: str = SITE_PAYLOAD_SCHEMA_VERSION,
    payload_root_dir: str | Path = DEFAULT_SITE_PAYLOAD_ROOT_DIR,
    site_output_dir: str | Path | None = None,
    enforce_road_cache: bool = True,
    reporter: ProgressReporter | None = None,
    jobs: str | int = 1,
    list_files: bool = False,
    family_context_report_path: str | Path | None = None,
) -> SitePayloadGenerationSummary:
    output_repo = Path(output_repo_dir)
    site_output = _resolve_site_output_dir(output_repo, site_output_dir)
    payload_root = Path(payload_root_dir)
    if payload_root.is_absolute():
        raise ValueError(f"Site payload root must be repository-relative, got: {payload_root}")
    benchmarks_root = output_repo / "benchmarks"
    if not benchmarks_root.exists():
        raise FileNotFoundError(f"Benchmark root does not exist: {benchmarks_root}")

    if enforce_road_cache:
        enforce_full_road_cache(output_repo, reporter=reporter)

    if reporter is not None:
        reporter.phase("discovering benchmark instances", root=benchmarks_root)
    generated_at = _now_utc_iso()
    published_at_value = published_at or generated_at
    snapshot_id_value = snapshot_id or _infer_snapshot_id(published_at_value, source_commit)
    snapshot = SnapshotRef(
        snapshot_id=snapshot_id_value,
        published_at=published_at_value,
        source_commit=source_commit,
        source_branch=source_branch,
    )

    discovered_instances = discover_benchmark_instances(benchmarks_root=benchmarks_root)
    if reporter is not None:
        reporter.phase("discovered benchmark instances", instances=len(discovered_instances))
    resolved_items = _resolve_instances(output_repo, discovered_instances, jobs=jobs, reporter=reporter)
    family_context_sections = _load_family_context_sections(output_repo, family_context_report_path)

    site_counts = SiteCounts(
        problem_count=len({item.locator.problem_type for item in resolved_items}),
        family_count=len({(item.locator.problem_type, item.locator.benchmark_name) for item in resolved_items}),
        variant_count=len({(item.locator.problem_type, item.locator.benchmark_name, item.locator.metric_variant) for item in resolved_items if item.locator.metric_variant is not None}),
        place_count=len({item.locator.place_slug for item in resolved_items if item.locator.place_slug}),
        size_bucket_count=len({(item.locator.problem_type, item.locator.benchmark_name, item.locator.metric_variant, item.locator.place_slug, item.locator.size_bucket) for item in resolved_items}),
        instance_count=len(resolved_items),
        bks_count=sum(len(item.bks_entries) for item in resolved_items),
    )

    written_paths: list[Path] = []

    if reporter is not None:
        reporter.phase("building snapshot history")
    current_inventory = _build_inventory(resolved_items)
    history_path = site_output / "site" / "history.json"
    if history_path.exists():
        existing_ledger: SiteHistoryLedger | None = SiteHistoryLedger(**load_json_from_file(history_path))
    else:
        existing_ledger = None
    prev_inventory = _load_previous_inventory(site_output, existing_ledger, snapshot.snapshot_id)
    change_log = _compute_change_log(prev_inventory, current_inventory)
    inventory_path = _save_inventory(site_output, snapshot.snapshot_id, generated_at, current_inventory)
    written_paths.append(inventory_path)

    snapshot_manifest = SiteSnapshotManifest(
        generated_at=generated_at,
        snapshot=snapshot,
        schema_version=schema_version,
        summary=history_summary,
        counts=site_counts,
        benchmark_index_path=f"/{(payload_root / 'benchmarks' / 'index.json').as_posix()}",
        history_path="/site/history.json",
        history_detail_path=f"/{(payload_root / 'history' / snapshot.snapshot_id / 'index.json').as_posix()}",
    )
    snapshot_path = site_output / "site" / "snapshot.json"
    save_json_to_file(snapshot_manifest.model_dump(mode="json"), snapshot_path)
    written_paths.append(snapshot_path)

    history_entry = SiteHistoryEntry(
        snapshot=snapshot,
        summary=history_summary,
        detail_route_path=_history_detail_route_path(snapshot.snapshot_id),
        affected_problem_types=_sorted_problem_types(resolved_items),
        affected_benchmark_names=_sorted_benchmark_names(resolved_items),
        affected_objective_functions=sorted(
            {entry.objective_function for item in resolved_items for entry in item.bks_entries},
            key=_objective_sort_key,
        ),
        change_counts=change_log.counts,
    )
    if existing_ledger is not None:
        entries = [entry for entry in existing_ledger.entries if entry.snapshot.snapshot_id != snapshot.snapshot_id]
    else:
        entries = []
    entries.insert(0, history_entry)
    history_ledger = SiteHistoryLedger(
        generated_at=generated_at,
        snapshot=snapshot,
        schema_version=schema_version,
        current_snapshot_id=snapshot.snapshot_id,
        entries=entries,
    )
    save_json_to_file(history_ledger.model_dump(mode="json"), history_path)
    written_paths.append(history_path)

    history_detail_path = _history_detail_payload_path(site_output, snapshot.snapshot_id, payload_root)
    history_detail_payload = _build_history_detail_payload(
        snapshot_manifest,
        history_entry,
        change_log,
        generated_at,
        snapshot,
    )
    save_json_to_file(history_detail_payload.model_dump(mode="json"), history_detail_path)
    written_paths.append(history_detail_path)

    root_payload = _build_root_benchmarks_index(resolved_items, generated_at, snapshot)
    home_payload = _build_home_page_payload(site_counts, root_payload, generated_at, snapshot, history_summary)
    static_payloads: list[tuple[str, BaseModel]] = []
    static_payloads.append((home_payload.route_path, home_payload))
    project_payload = _build_project_page_payload(generated_at, snapshot)
    static_payloads.append((project_payload.route_path, project_payload))
    objectives_payload = _build_objectives_page_payload(resolved_items, generated_at, snapshot)
    static_payloads.append((objectives_payload.route_path, objectives_payload))
    static_payloads.append((root_payload.route_path, root_payload))

    if reporter is not None:
        reporter.phase("writing catalog payloads")
    for route_path, payload in static_payloads:
        written_paths.append(_write_payload(site_output, route_path, payload, payload_root))

    benchmark_pages_written = 1
    instance_pages_written = 0

    for problem_type in _sorted_problem_types(resolved_items):
        problem_payload = _build_problem_index(
            resolved_items,
            problem_type,
            generated_at,
            snapshot,
            family_context_sections,
        )
        written_paths.append(_write_payload(site_output, problem_payload.route_path, problem_payload, payload_root))
        benchmark_pages_written += 1

        problem_items = [item for item in resolved_items if item.locator.problem_type == problem_type]
        for benchmark_name in _sorted_benchmark_names(problem_items):
            family_items = [item for item in problem_items if item.locator.benchmark_name == benchmark_name]
            metric_variants = sorted(
                {item.locator.metric_variant for item in family_items if item.locator.metric_variant is not None},
                key=_metric_variant_sort_key,
            )
            family_subsets = sorted(
                {item.locator.subset for item in family_items if item.locator.subset is not None}
            )

            family_variant_groups = {
                variant.value: [item for item in family_items if item.locator.metric_variant == variant]
                for variant in metric_variants
            }
            family_subset_groups = {
                subset: [item for item in family_items if item.locator.subset == subset]
                for subset in family_subsets
            }
            family_size_groups = {
                size_bucket: [item for item in family_items if item.locator.size_bucket == size_bucket]
                for size_bucket in sorted({item.locator.size_bucket for item in family_items})
            }
            context_section = family_context_sections.get((problem_type, benchmark_name))
            context_route_path = (
                _family_context_route_path(problem_type, benchmark_name)
                if context_section is not None
                else None
            )
            context_summary = (
                _context_summary_from_markdown(context_section.markdown)
                if context_section is not None
                else None
            )
            family_payload = _build_catalog_index(
                payload_kind=SitePayloadKind.FAMILY_INDEX,
                route_path=_family_route_path(problem_type, benchmark_name),
                title=f"{benchmark_name.value} ({problem_type.value})",
                breadcrumbs=_build_breadcrumbs(
                    ("benchmarks", "/benchmarks/"),
                    (problem_type.value, _problem_route_path(problem_type)),
                    (benchmark_name.value, _family_route_path(problem_type, benchmark_name)),
                ),
                items=family_items,
                problem_type=problem_type,
                benchmark_name=benchmark_name,
                metric_variant=None,
                place_slug=None,
                size_bucket=None,
                variant_routes=_make_subroute_entries(
                    family_variant_groups,
                    lambda key: _variant_route_path(problem_type, benchmark_name, MetricVariant(key)),
                ),
                place_routes=[],
                # Size shortcuts at the family level only when neither metric
                # variants nor subsets partition the family further; otherwise
                # users drill down through the partitioning facet first.
                size_routes=_make_subroute_entries(
                    family_size_groups,
                    lambda key: _size_route_path(problem_type, benchmark_name, key),
                ) if not metric_variants and not family_subsets else [],
                subset_routes=_make_subroute_entries(
                    family_subset_groups,
                    lambda key: _subset_route_path(problem_type, benchmark_name, key),
                ),
                generated_at=generated_at,
                snapshot=snapshot,
                context_route_path=context_route_path,
                context_summary=context_summary,
            )
            written_paths.append(_write_payload(site_output, family_payload.route_path, family_payload, payload_root))
            benchmark_pages_written += 1

            if context_section is not None:
                context_payload = _build_family_context_page_payload(
                    output_repo_dir=output_repo,
                    problem_type=problem_type,
                    benchmark_name=benchmark_name,
                    context_section=context_section,
                    generated_at=generated_at,
                    snapshot=snapshot,
                )
                written_paths.append(_write_payload(site_output, context_payload.route_path, context_payload, payload_root))
                benchmark_pages_written += 1

            # Size pages directly under the family — only when no further partitioning.
            for size_bucket, size_items in family_size_groups.items():
                if metric_variants or family_subsets:
                    continue
                size_payload = _build_catalog_index(
                    payload_kind=SitePayloadKind.SIZE_INDEX,
                    route_path=_size_route_path(problem_type, benchmark_name, size_bucket),
                    title=f"{benchmark_name.value} {size_bucket}",
                    breadcrumbs=_build_breadcrumbs(
                        ("benchmarks", "/benchmarks/"),
                        (problem_type.value, _problem_route_path(problem_type)),
                        (benchmark_name.value, _family_route_path(problem_type, benchmark_name)),
                        (size_bucket, _size_route_path(problem_type, benchmark_name, size_bucket)),
                    ),
                    items=size_items,
                    problem_type=problem_type,
                    benchmark_name=benchmark_name,
                    metric_variant=None,
                    place_slug=None,
                    size_bucket=size_bucket,
                    variant_routes=[],
                    place_routes=[],
                    size_routes=[],
                    generated_at=generated_at,
                    snapshot=snapshot,
                    context_route_path=context_route_path,
                    context_summary=context_summary,
                )
                written_paths.append(_write_payload(site_output, size_payload.route_path, size_payload, payload_root))
                benchmark_pages_written += 1

            # Subset pages (e.g. Ortec2022 final/public). Each subset gets its
            # own catalog index plus per-(subset, size) size pages, mirroring
            # the metric-variant branch below.
            for subset_value, subset_items in family_subset_groups.items():
                subset_size_groups = {
                    size_bucket: [item for item in subset_items if item.locator.size_bucket == size_bucket]
                    for size_bucket in sorted({item.locator.size_bucket for item in subset_items})
                }
                subset_payload = _build_catalog_index(
                    payload_kind=SitePayloadKind.SUBSET_INDEX,
                    route_path=_subset_route_path(problem_type, benchmark_name, subset_value),
                    title=f"{benchmark_name.value} {subset_value} ({problem_type.value})",
                    breadcrumbs=_build_breadcrumbs(
                        ("benchmarks", "/benchmarks/"),
                        (problem_type.value, _problem_route_path(problem_type)),
                        (benchmark_name.value, _family_route_path(problem_type, benchmark_name)),
                        (subset_value, _subset_route_path(problem_type, benchmark_name, subset_value)),
                    ),
                    items=subset_items,
                    problem_type=problem_type,
                    benchmark_name=benchmark_name,
                    metric_variant=None,
                    place_slug=None,
                    size_bucket=None,
                    subset=subset_value,
                    variant_routes=[],
                    place_routes=[],
                    size_routes=_make_subroute_entries(
                        subset_size_groups,
                        lambda key, _subset=subset_value: _size_route_path(
                            problem_type, benchmark_name, key, subset=_subset
                        ),
                    ),
                    generated_at=generated_at,
                    snapshot=snapshot,
                    context_route_path=context_route_path,
                    context_summary=context_summary,
                )
                written_paths.append(_write_payload(site_output, subset_payload.route_path, subset_payload, payload_root))
                benchmark_pages_written += 1

                for size_bucket, size_items in subset_size_groups.items():
                    size_payload = _build_catalog_index(
                        payload_kind=SitePayloadKind.SIZE_INDEX,
                        route_path=_size_route_path(
                            problem_type, benchmark_name, size_bucket, subset=subset_value
                        ),
                        title=f"{benchmark_name.value} {subset_value} {size_bucket}",
                        breadcrumbs=_build_breadcrumbs(
                            ("benchmarks", "/benchmarks/"),
                            (problem_type.value, _problem_route_path(problem_type)),
                            (benchmark_name.value, _family_route_path(problem_type, benchmark_name)),
                            (subset_value, _subset_route_path(problem_type, benchmark_name, subset_value)),
                            (size_bucket, _size_route_path(
                                problem_type, benchmark_name, size_bucket, subset=subset_value
                            )),
                        ),
                        items=size_items,
                        problem_type=problem_type,
                        benchmark_name=benchmark_name,
                        metric_variant=None,
                        place_slug=None,
                        size_bucket=size_bucket,
                        subset=subset_value,
                        variant_routes=[],
                        place_routes=[],
                        size_routes=[],
                        generated_at=generated_at,
                        snapshot=snapshot,
                        context_route_path=context_route_path,
                        context_summary=context_summary,
                    )
                    written_paths.append(_write_payload(site_output, size_payload.route_path, size_payload, payload_root))
                    benchmark_pages_written += 1

            for metric_variant in metric_variants:
                variant_items = family_variant_groups[metric_variant.value]
                place_groups = {
                    place_slug: [item for item in variant_items if item.locator.place_slug == place_slug]
                    for place_slug in sorted({item.locator.place_slug for item in variant_items if item.locator.place_slug is not None})
                }
                size_groups = {
                    size_bucket: [item for item in variant_items if item.locator.size_bucket == size_bucket]
                    for size_bucket in sorted({item.locator.size_bucket for item in variant_items})
                }
                variant_payload = _build_catalog_index(
                    payload_kind=SitePayloadKind.VARIANT_INDEX,
                    route_path=_variant_route_path(problem_type, benchmark_name, metric_variant),
                    title=f"{benchmark_name.value} {metric_variant.value} ({problem_type.value})",
                    breadcrumbs=_build_breadcrumbs(
                        ("benchmarks", "/benchmarks/"),
                        (problem_type.value, _problem_route_path(problem_type)),
                        (benchmark_name.value, _family_route_path(problem_type, benchmark_name)),
                        (metric_variant.value, _variant_route_path(problem_type, benchmark_name, metric_variant)),
                    ),
                    items=variant_items,
                    problem_type=problem_type,
                    benchmark_name=benchmark_name,
                    metric_variant=metric_variant,
                    place_slug=None,
                    size_bucket=None,
                    variant_routes=[],
                    place_routes=_make_subroute_entries(
                        place_groups,
                        lambda key: _place_route_path(problem_type, benchmark_name, metric_variant, key),
                    ),
                    size_routes=_make_subroute_entries(
                        size_groups,
                        lambda key: _size_route_path(problem_type, benchmark_name, key, metric_variant=metric_variant, place_slug=variant_items[0].locator.place_slug or ""),
                    ) if place_groups and len(place_groups) == 1 else [],
                    generated_at=generated_at,
                    snapshot=snapshot,
                    context_route_path=context_route_path,
                    context_summary=context_summary,
                )
                written_paths.append(_write_payload(site_output, variant_payload.route_path, variant_payload, payload_root))
                benchmark_pages_written += 1

                for place_slug, place_items in place_groups.items():
                    place_size_groups = {
                        size_bucket: [item for item in place_items if item.locator.size_bucket == size_bucket]
                        for size_bucket in sorted({item.locator.size_bucket for item in place_items})
                    }
                    place_payload = _build_catalog_index(
                        payload_kind=SitePayloadKind.PLACE_INDEX,
                        route_path=_place_route_path(problem_type, benchmark_name, metric_variant, place_slug),
                        title=f"{benchmark_name.value} {metric_variant.value} {place_slug}",
                        breadcrumbs=_build_breadcrumbs(
                            ("benchmarks", "/benchmarks/"),
                            (problem_type.value, _problem_route_path(problem_type)),
                            (benchmark_name.value, _family_route_path(problem_type, benchmark_name)),
                            (metric_variant.value, _variant_route_path(problem_type, benchmark_name, metric_variant)),
                            (place_slug, _place_route_path(problem_type, benchmark_name, metric_variant, place_slug)),
                        ),
                        items=place_items,
                        problem_type=problem_type,
                        benchmark_name=benchmark_name,
                        metric_variant=metric_variant,
                        place_slug=place_slug,
                        size_bucket=None,
                        variant_routes=[],
                        place_routes=[],
                        size_routes=_make_subroute_entries(
                            place_size_groups,
                            lambda key: _size_route_path(problem_type, benchmark_name, key, metric_variant=metric_variant, place_slug=place_slug),
                        ),
                        generated_at=generated_at,
                        snapshot=snapshot,
                        context_route_path=context_route_path,
                        context_summary=context_summary,
                    )
                    written_paths.append(_write_payload(site_output, place_payload.route_path, place_payload, payload_root))
                    benchmark_pages_written += 1

                    for size_bucket, size_items in place_size_groups.items():
                        size_payload = _build_catalog_index(
                            payload_kind=SitePayloadKind.SIZE_INDEX,
                            route_path=_size_route_path(problem_type, benchmark_name, size_bucket, metric_variant=metric_variant, place_slug=place_slug),
                            title=f"{benchmark_name.value} {metric_variant.value} {place_slug} {size_bucket}",
                            breadcrumbs=_build_breadcrumbs(
                                ("benchmarks", "/benchmarks/"),
                                (problem_type.value, _problem_route_path(problem_type)),
                                (benchmark_name.value, _family_route_path(problem_type, benchmark_name)),
                                (metric_variant.value, _variant_route_path(problem_type, benchmark_name, metric_variant)),
                                (place_slug, _place_route_path(problem_type, benchmark_name, metric_variant, place_slug)),
                                (size_bucket, _size_route_path(problem_type, benchmark_name, size_bucket, metric_variant=metric_variant, place_slug=place_slug)),
                            ),
                            items=size_items,
                            problem_type=problem_type,
                            benchmark_name=benchmark_name,
                            metric_variant=metric_variant,
                            place_slug=place_slug,
                            size_bucket=size_bucket,
                            variant_routes=[],
                            place_routes=[],
                            size_routes=[],
                            generated_at=generated_at,
                            snapshot=snapshot,
                            context_route_path=context_route_path,
                            context_summary=context_summary,
                        )
                        written_paths.append(_write_payload(site_output, size_payload.route_path, size_payload, payload_root))
                        benchmark_pages_written += 1

    with (reporter.task("write instance payloads", len(resolved_items)) if reporter else _NullProgressTask()) as task:
        for resolved in resolved_items:
            instance_payload = _build_instance_page_payload(resolved, generated_at, snapshot)
            written_paths.append(_write_payload(site_output, resolved.route_path, instance_payload, payload_root))
            instance_pages_written += 1
            task.update(detail=resolved.display_name)

    return SitePayloadGenerationSummary(
        snapshot_id=snapshot.snapshot_id,
        source_commit=snapshot.source_commit,
        published_at=snapshot.published_at,
        payload_files_written=len(written_paths),
        benchmark_pages_written=benchmark_pages_written,
        instance_pages_written=instance_pages_written,
        history_entries=len(entries),
        payload_paths=_paths_for_summary(site_output, written_paths) if list_files else None,
    )
