"""Populate benchmarks/TDVRPTW/Dabia2013 (and TDVRP/Dabia2013) from Lera-Romero raw instances.

One-shot curation pipeline for the TD-IGP-Solomon benchmark (Dabia et al. 2013,
instances as distributed with Lera-Romero et al. 2020). For every raw instance:

1. Merge the duplicated end depot into depot 0 (distances/coordinates/TWs are
   mirrored in the raw data — verified here; speed-profile assignments for
   incoming arcs only exist on the end-depot column, which is the one used).
2. Build one exact arrival-time NDCPWLF per arc from the IGP data: breakpoints
   where the departure or the arrival crosses a speed-zone boundary, each
   breakpoint re-evaluated with the exact forward Ichoua loop (no drift). The
   last zone's speed is extended beyond the horizon so ATFs are total on [0, T].
3. Cross-validate the PWL against direct Ichoua evaluation on random points.
4. Write canonical .vrp.json + ATF sidecar (.atf.json below 50 customers,
   .atf.json.gz at 50 and above) with the storage-independent sha256.
5. Re-validate the published Lera BKS with the canonical Duration checker and
   seed .bks.Duration.json from the checker's authoritative costs; solutions
   rejected by the checker are reported, not written.

Usage (from the MAMUT-routing repository root):
    .venv/bin/python tools/populate_td_dabia2013.py [--sizes 25 50 100] [--tdvrp]
        [--lera-dir PATH] [--report PATH]
"""

from __future__ import annotations

import argparse
import datetime
import json
import random
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "MAMUT-routing-lib" / "src"))

from mamut_routing_lib.enums import ObjectiveFunction
from mamut_routing_lib.json_utils import save_json_to_file
from mamut_routing_lib.models import BenchmarkBKS, BenchmarkSolution
from mamut_routing_lib.artifacts import get_bks_path_for_instance
from mamut_routing_lib.td import (
    InstanceATFs,
    NDCPWLF,
    check_td_solution,
    compute_atf_sha256,
    load_td_instance,
    save_instance_atfs,
)

DEFAULT_LERA_DIR = Path("/home/onyr/code/phd/TDVRPTW-solver/instances/dabia_et_al_2013")
GENERATOR = {"name": "populate_td_dabia2013", "version": "1", "source": "Lera-Romero dabia_et_al_2013"}
AUTHORS = "Florian Rascoussier (0nyr)"


def ichoua_travel_time(zones, speeds, distance, t0):
    """Exact forward IGP loop; last-zone speed extended beyond the horizon."""
    k = 0
    while k < len(zones) - 1 and t0 > zones[k][1]:
        k += 1
    t = t0
    d = distance
    tt = t + d / speeds[k]
    while k < len(zones) - 1 and tt > zones[k][1]:
        d = d - speeds[k] * (zones[k][1] - t)
        t = zones[k][1]
        if d <= 0.0:
            break
        k += 1
        tt = t + d / speeds[k]
    return tt - t0


def build_arc_atf(zones, speeds, distance, horizon):
    """Exact PWL arrival function: breakpoints where departure or arrival crosses a zone boundary."""
    t_end = horizon[1]
    if distance == 0.0:
        return NDCPWLF([horizon[0], t_end], [horizon[0], t_end])

    def zone_right(x):
        # Zone governing the speed immediately AFTER instant x (forward march).
        k = 0
        while k < len(zones) - 1 and x >= zones[k][1]:
            k += 1
        return k

    xs, ys = [], []
    t = horizon[0]
    while True:
        a = t + ichoua_travel_time(zones, speeds, distance, t)
        xs.append(t)
        ys.append(a)
        if t >= t_end:
            break
        kd, ka = zone_right(t), zone_right(a)
        next_dep = zones[kd][1] if kd < len(zones) - 1 else t_end
        if ka < len(zones) - 1:
            next_arr = t + (zones[ka][1] - a) * speeds[ka] / speeds[kd]
        else:
            next_arr = t_end
        t_next = min(next_dep, next_arr, t_end)
        if t_next <= t:
            raise RuntimeError(f"marching stalled at t={t} (distance {distance})")
        t = t_next
    return NDCPWLF(xs, ys)


def verify_depot_mirror(data):
    """The duplicated end depot must mirror depot 0 for all geometry-level data."""
    end = data["end_depot"]
    assert data["digraph"]["coordinates"][0] == data["digraph"]["coordinates"][end]
    assert data["time_windows"][0] == data["time_windows"][end]
    assert data["demands"][0] == data["demands"][end] == 0
    assert data["service_times"][0] == data["service_times"][end] == 0
    n_vertices = data["digraph"]["vertex_count"]
    for i in range(1, n_vertices - 1):
        assert data["distances"][i][end] == data["distances"][end][i], f"asymmetric mirror at {i}"


def build_canonical(data, name):
    """Return (instance payload without td block, InstanceATFs)."""
    verify_depot_mirror(data)
    n_vertices = data["digraph"]["vertex_count"]
    n = n_vertices - 2
    end = data["end_depot"]
    zones = data["speed_zones"]
    horizon = [float(data["horizon"][0]), float(data["horizon"][1])]

    arcs = {}
    for i in range(n_vertices - 1):  # skip end depot as source
        for j in range(1, n_vertices):  # skip start depot as target
            ci = i
            cj = 0 if j == end else j
            if ci == cj:
                continue
            profile = data["cluster_speeds"][data["clusters"][i][j]]
            arcs[(ci, cj)] = build_arc_atf(zones, profile, data["distances"][i][j], horizon)

    atfs = InstanceATFs(
        instance_name=name,
        benchmark_name="Dabia2013",
        horizon=(horizon[0], horizon[1]),
        num_customers=n,
        arcs=arcs,
        generator=dict(GENERATOR),
    )
    payload = {
        "instance_name": name,
        "instance_origin": "Solomon1987",
        "benchmark_name": "Dabia2013",
        "num_customers": n,
        "num_vehicles": data["vehicle_count"],
        "vehicle_capacity": data["capacity"],
        "coordinates": [list(c) for c in data["digraph"]["coordinates"][: n + 1]],
        "demands": [int(q) for q in data["demands"][: n + 1]],
        "service_times": data["service_times"][: n + 1],
        "time_windows": [list(tw) for tw in data["time_windows"][: n + 1]],
        "depot": 0,
        "horizon": horizon,
        "metadata": {
            "authors": AUTHORS,
            "generated_at": datetime.date.today().isoformat(),
            "generator": dict(GENERATOR),
            "notes": (
                "IGP (Ichoua et al. 2003) speed model consolidated into arrival-time "
                "NDCPWLFs; duplicated end depot merged into depot 0; last speed zone "
                "extended beyond the horizon so ATF domains span it."
            ),
        },
    }
    return payload, atfs


def cross_validate_atfs(data, atfs, rng, num_arcs=40, points_per_arc=8, tolerance=1e-9):
    zones = data["speed_zones"]
    end = data["end_depot"]
    worst = 0.0
    for (ci, cj) in rng.sample(sorted(atfs.arcs), min(num_arcs, len(atfs.arcs))):
        i, j = ci, (end if cj == 0 else cj)
        profile = data["cluster_speeds"][data["clusters"][i][j]]
        d = data["distances"][i][j]
        atf = atfs.arcs[(ci, cj)]
        for _ in range(points_per_arc):
            t = rng.uniform(atfs.horizon[0], atfs.horizon[1])
            worst = max(worst, abs((t + ichoua_travel_time(zones, profile, d, t)) - atf.evaluate(t)))
    if worst > tolerance:
        raise RuntimeError(f"ATF cross-validation failed: max abs error {worst:.3e}")
    return worst


def populate_instance(lera_path, out_dir, *, tdvrp, rng):
    data = json.loads(lera_path.read_text())
    base, size = lera_path.stem.rsplit("_", 1)
    payload, atfs = build_canonical(data, base)
    cross_validate_atfs(data, atfs, rng)

    sidecar_name = f"{base}.atf.json.gz" if int(size) >= 50 else f"{base}.atf.json"
    payload["td"] = {
        "model": "atf-ndcpwlf",
        "atf_path": sidecar_name,
        "atf_sha256": compute_atf_sha256(atfs),
    }
    if tdvrp:
        del payload["time_windows"]

    out_dir.mkdir(parents=True, exist_ok=True)
    save_instance_atfs(atfs, out_dir / sidecar_name)
    instance_path = out_dir / f"{base}.vrp.json"
    save_json_to_file(payload, instance_path)
    # Full reload: schema + sidecar invariants + sha consistency.
    return load_td_instance(instance_path)


def seed_bks(loaded, lera_solution, bks_path):
    """Re-validate a Lera BKS; return (written, result). Costs come from the checker."""
    end_vertex = loaded.instance.num_customers + 1
    routes = [[v for v in r["path"] if v not in (0, end_vertex)] for r in lera_solution["routes"]]
    routes = sorted(routes, key=lambda route: route[0])
    solution = BenchmarkSolution(instance_name=loaded.instance.instance_name, routes=routes)
    result = check_td_solution(loaded, solution)
    if not result.is_valid():
        return False, result

    evaluations = {tuple(e.route): e for e in result.route_evaluations}
    ordered = [evaluations[tuple(route)] for route in routes]
    bks = BenchmarkBKS(
        instance_name=loaded.instance.instance_name,
        routes=routes,
        cost=result.routing_cost,
        objective_function=ObjectiveFunction.DURATION,
        metadata={
            "authors": AUTHORS,
            "source": "Lera-Romero et al. 2020 (linear edge costs) published solutions",
            "validated_by": "mamut-routing-lib td Duration checker",
            "date": datetime.date.today().isoformat(),
            "route_durations": [e.duration for e in ordered],
            "route_departure_times": [e.departure_time for e in ordered],
            "published_duration_sum": sum(r["duration"] for r in lera_solution["routes"]),
        },
    )
    save_json_to_file(bks.model_dump(mode="json"), bks_path)
    return True, result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lera-dir", type=Path, default=DEFAULT_LERA_DIR)
    parser.add_argument("--sizes", type=int, nargs="+", default=[25, 50, 100])
    parser.add_argument("--tdvrp", action="store_true", help="also populate the TW-free TDVRP variant")
    parser.add_argument("--report", type=Path, default=REPO_ROOT / "dist" / "td-population-report.json")
    args = parser.parse_args()

    rng = random.Random(20260702)
    solutions = json.loads((args.lera_dir / "solutions.json").read_text())
    solutions_by_name = {s["instance_name"]: s for s in solutions}
    report = {"benchmark": "Dabia2013", "generated_at": datetime.datetime.now().isoformat(), "instances": []}

    for size in args.sizes:
        lera_files = sorted(args.lera_dir.glob(f"*_{size}.json"))
        print(f"== n={size}: {len(lera_files)} instances")
        for lera_path in lera_files:
            base = lera_path.stem.rsplit("_", 1)[0]
            out_dir = REPO_ROOT / "benchmarks" / "TDVRPTW" / "Dabia2013" / f"n={size}"
            loaded = populate_instance(lera_path, out_dir, tdvrp=False, rng=rng)
            entry = {"instance": base, "n": size, "bks": None}

            lera_solution = solutions_by_name.get(lera_path.stem)
            if lera_solution is not None:
                bks_path = get_bks_path_for_instance(loaded.instance_path, ObjectiveFunction.DURATION)
                written, result = seed_bks(loaded, lera_solution, bks_path)
                entry["bks"] = {
                    "status": result.status.value,
                    "written": written,
                    "cost": result.routing_cost,
                    "error": result.error_message,
                }
                marker = "ok" if written else f"REJECTED ({result.status.value}: {result.error_message})"
                print(f"  {base}: bks {marker}")
            else:
                print(f"  {base}: no published solution")

            if args.tdvrp:
                tdvrp_dir = REPO_ROOT / "benchmarks" / "TDVRP" / "Dabia2013" / f"n={size}"
                populate_instance(lera_path, tdvrp_dir, tdvrp=True, rng=rng)
            report["instances"].append(entry)

    rejected = [e for e in report["instances"] if e["bks"] and not e["bks"]["written"]]
    total_bks = sum(1 for e in report["instances"] if e["bks"] is not None)
    report["summary"] = {
        "instances": len(report["instances"]),
        "bks_checked": total_bks,
        "bks_written": total_bks - len(rejected),
        "bks_rejected": len(rejected),
        "rejected": [{"instance": e["instance"], "n": e["n"], **e["bks"]} for e in rejected],
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + "\n")
    print(f"\nSummary: {report['summary']['instances']} instances populated, "
          f"{report['summary']['bks_written']}/{total_bks} BKS written, "
          f"{len(rejected)} rejected -> {args.report}")


if __name__ == "__main__":
    main()
