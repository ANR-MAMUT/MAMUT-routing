"""Write the static browser catalog from the same rows as the public JSON index."""

from collections import defaultdict
import json
from pathlib import Path


def _costs_requiring_exact_comparison(items: list[dict]) -> set:
    # The browser compares binary64 displays first. A distinct exact value sharing
    # the same display (possibly in another family) requires its original fraction.
    first_ratio = {}
    collisions = {None}  # Certified overflows always require exact comparison.
    for item in items:
        for entry in item["objective_availability"]:
            cost = entry["cost"]
            if cost is None:
                continue
            display = float(cost)
            evaluation = entry.get("evaluation") or {}
            exact = evaluation.get("authoritative_cost")
            ratio = (exact["numerator"], exact["denominator"]) if exact else None
            if first_ratio.setdefault(display, ratio) != ratio:
                collisions.add(display)
    return collisions


def _catalog_row(item: dict, collisions: set) -> dict:
    row = {key: value for key, value in item.items() if value is not None}
    objectives = []
    for entry in item["objective_availability"]:
        badge = {key: value for key, value in entry.items() if key != "evaluation" and value is not None}
        evaluation = entry.get("evaluation")
        if evaluation:
            display = float(entry["cost"]) if entry["cost"] is not None else None
            if display in collisions:
                badge["evaluation"] = {
                    "display_overflow": evaluation["display_overflow"],
                    "authoritative_cost": evaluation["authoritative_cost"],
                }
        objectives.append(badge)
    row["objective_availability"] = objectives
    return row


def write_catalog_shards(root_index: dict, payload_root: Path) -> list[Path]:
    groups = defaultdict(list)
    collisions = _costs_requiring_exact_comparison(root_index["items"])
    for item in root_index["items"]:
        locator = item["locator"]
        groups[locator["problem_type"], locator["benchmark_name"]].append(_catalog_row(item, collisions))

    written = []

    def write(relative: str, data) -> None:
        path = payload_root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        written.append(path)

    manifest = {key: value for key, value in root_index.items() if key != "items"}
    shards = []
    search = {}
    for (problem, family), rows in sorted(groups.items()):
        path = f"benchmarks/{problem.lower()}/{family.lower()}/catalog-rows.json"
        write(path, rows)
        shards.append({
            "problem": problem,
            "family": family,
            "count": len(rows),
            "workbench_count": sum(bool(item.get("place_slug") or item["locator"].get("place_slug")) for item in rows),
            "path": path,
        })
        search[path] = [
            " ".join(item.get(field) or "" for field in ("display_name", "base_instance", "instance_id"))
            for item in rows
        ]
    example = {"problem": "CVRP", "family": "Poryos2026", "size": "100"}
    example_rows = groups.get((example["problem"], example["family"]), [])
    if any(str(item["num_customers"]) == example["size"] for item in example_rows):
        manifest["example"] = example
    search_path = "benchmarks/catalog-names.json"
    write(search_path, search)
    write("benchmarks/catalog.json", {**manifest, "shards": shards, "search_path": search_path})
    return written
