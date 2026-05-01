# MAMUT-routing Julia Webapp Environment

This folder contains the Julia-side contract loader, the site payload API surface, and the static file server needed to browse the generated Paper7 site from Julia alone.

## One-time setup

From `papers/paper7/MAMUT-routing`:

```bash
julia --project=webapp -e 'using Pkg; Pkg.instantiate(); Pkg.precompile()'
```

## Start the payload API

From `papers/paper7/MAMUT-routing`:

```bash
julia --project=webapp webapp/run_site_api.jl --repo-root "$(pwd)"
```

The default API prefix is `/api/site-payload` and the default bind address is `127.0.0.1:8081`.

The same server now serves:

- payload JSON under `/api/site-payload`
- generated static site files from `dist/`, including `/`, `/benchmarks/vrptw/`, `/history/.../`, `/site-payloads/`, and `/webapp/`
- benchmark artifacts such as `.vrp.json`, `.vrp`, `.meta.json`, and `.manifest.json`

## Generate shells for API hydration mode

From `papers/paper7`:

```bash
PYTHONPATH=src /home/apichon/code/code/VRPTW-benchmarks/.venv/bin/python -m src.scripts.build_site_snapshot --output-repo-dir MAMUT-routing --payload-mode api
```

That keeps the same generated HTML routes, but the frontend hydrator will fetch route payloads from the Julia API instead of local `index.json` files.
