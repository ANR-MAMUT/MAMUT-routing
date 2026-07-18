# Campaign-only Julia environment (official TD generation)

This folder holds the Julia code that generates the official Mamut2026 time-dependent data: `osm_generation.jl` (OSM road-graph import and CVRP base generation) and `td_traffic.jl` (BPR/wave time-dependent traffic bridge), plus their pinned `Project.toml`/`Manifest.toml`.

It is not a web application anymore. The former Julia server (`site_api.jl`, `io-json-vrp.jl`, `run_site_api.jl`) was retired in the 2026-07 clean-up split: the website is fully static, built and served by the Python publisher (see the repository README, `mamut-routing-publish site build` and `serve`), and interactive generation lives in the local [MAMUT-routing-tools](https://github.com/ANR-MAMUT/MAMUT-routing-tools) suite.

## Who calls this code

`src/mamut_routing_publish/td_generation/julia_driver.py` includes exactly `osm_generation.jl` and `td_traffic.jl` to run the official campaign pipeline behind the publisher CLI:

```bash
uv run mamut-routing-publish workbench build-family <City>   # fetch (Python), generate-base, derive-vrptw, traffic-sim, build-td
uv run mamut-routing-publish workbench traffic-sim <City>
```

City OSM acquisition is Python-side (`mamut-routing-publish workbench fetch-city`, backed by mamut-routing-tools); Julia starts from the stored `osmdata/<City>.osm`.

## One-time setup

From the repository root:

```bash
julia --project=webapp -e 'using Pkg; Pkg.instantiate(); Pkg.precompile()'
```

Julia is required only for this campaign pipeline. Building and serving the website needs no Julia at all.
