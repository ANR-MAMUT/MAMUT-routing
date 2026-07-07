"""Non-interactive Julia driver for the workbench generation stages.

Runs the webapp Julia code in a subprocess (the ``road_cache.py`` pattern —
no HTTP server needed): city OSM fetch, stage-1 CVRP generation and the TD
traffic/bridge export. Requires ``julia`` on PATH with the ``webapp``
project instantiated.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

_RESULT_MARKER = "MAMUT_RESULT_JSON:"


def find_julia() -> str:
    julia = shutil.which("julia")
    if julia is None:
        raise RuntimeError(
            "The workbench generation stages require Julia on PATH "
            "(the webapp project drives OSM parsing and traffic simulation)."
        )
    return julia


def _run_julia_call(repo_root: Path, call_expression: str, payload: dict[str, Any], *, threads: str = "auto") -> dict:
    """Include the webapp code and evaluate ``call_expression`` on a JSON payload.

    The expression receives the parsed payload as ``payload`` and must end
    with a JSON-serializable value, echoed back through a marker line.
    """
    julia = find_julia()
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as handle:
        json.dump(payload, handle)
        payload_path = handle.name
    program = f"""
include("webapp/osm_generation.jl")
include("webapp/td_traffic.jl")
payload = JSON3.read(read({json.dumps(payload_path)}, String))
result = {call_expression}
println({json.dumps(_RESULT_MARKER)}, JSON3.write(result))
"""
    completed = subprocess.run(
        [julia, "-t", threads, "--project=webapp", "--startup-file=no", "-e", program],
        cwd=repo_root,
        capture_output=True,
        text=True,
    )
    Path(payload_path).unlink(missing_ok=True)
    if completed.returncode != 0:
        raise RuntimeError(
            f"Julia call failed (exit {completed.returncode}):\n{completed.stderr[-4000:]}"
        )
    for line in reversed(completed.stdout.splitlines()):
        if line.startswith(_RESULT_MARKER):
            return json.loads(line[len(_RESULT_MARKER):])
    raise RuntimeError(f"Julia call produced no result marker:\n{completed.stdout[-2000:]}")


def fetch_city(repo_root: Path, *, city: str, country: str = "", max_radius_km: float = 0.0,
               padding_km: float = 0.0) -> dict:
    payload = {
        "city": city,
        "country": country,
        "maxRadiusKm": max_radius_km,
        "paddingKm": padding_km,
    }
    return _run_julia_call(repo_root, "fetch_and_store_city_osm(payload)", payload)


def generate_base(repo_root: Path, *, city: str, n_customers: int, method: str, seed: int,
                  osm_path: str | None = None, demand_type: int = 7, avg_route_size: int = 4) -> dict:
    payload: dict[str, Any] = {
        "city": city,
        "nCustomers": n_customers,
        "method": method,
        "seed": seed,
        "demandType": demand_type,
        "avgRouteSize": avg_route_size,
    }
    if osm_path:
        payload["osmPath"] = osm_path
    return _run_julia_call(repo_root, "generate_single_instance(payload)", payload)


def export_bridge(repo_root: Path, *, osm_path: str, city_slug: str,
                  out_root: str = "instances_v2/td-bridge",
                  models: list[str] | None = None, intensities: list[str] | None = None,
                  seed: int = 42, meta_paths: list[str] | None = None, force: bool = False) -> dict:
    payload: dict[str, Any] = {
        "osm_path": osm_path,
        "city_slug": city_slug,
        "out_root": out_root,
        "seed": seed,
        "force": force,
        "meta_paths": meta_paths or [],
    }
    if models:
        payload["models"] = models
    if intensities:
        payload["intensities"] = intensities
    expression = (
        'export_td_bridge(; osm_path=String(payload["osm_path"]), city_slug=String(payload["city_slug"]), '
        'out_root=String(payload["out_root"]), seed=Int(payload["seed"]), force=Bool(payload["force"]), '
        'meta_paths=[String(p) for p in payload["meta_paths"]], '
        'models=[String(m) for m in get(payload, "models", collect(TD_MODELS))], '
        'intensities=[String(i) for i in get(payload, "intensities", collect(TD_INTENSITIES))])'
    )
    return _run_julia_call(repo_root, expression, payload)
