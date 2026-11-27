"""Write the static browser catalog from the same rows as the public JSON index."""

from collections import defaultdict
import json
from pathlib import Path


def _catalog_row(item: dict) -> dict:
    """Keep display and navigation fields in lists. The record owns the certificate."""
    row = {key: value for key, value in item.items() if value is not None}
    objectives = []
    for entry in item["objective_availability"]:
        badge = {key: value for key, value in entry.items() if key != "evaluation" and value is not None}
        evaluation = entry.get("evaluation")
        if evaluation and evaluation["display_overflow"]:
            badge["evaluation"] = {"display_overflow": True}
        objectives.append(badge)
    row["objective_availability"] = objectives
    return row


def write_catalog_shards(root_index: dict, payload_root: Path) -> list[Path]:
    groups = defaultdict(list)
    for item in root_index["items"]:
        locator = item["locator"]
        groups[locator["problem_type"], locator["benchmark_name"]].append(_catalog_row(item))

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
