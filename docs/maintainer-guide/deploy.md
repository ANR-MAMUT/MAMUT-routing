# Deploy

The production site is static files behind a reverse proxy. The private repository `mamut-routing-deploy` pins this
repository as a submodule and carries the host templates and `deploy.sh`; its `docs/OPERATIONS.md` is the host-specific
runbook (paths, users, certificates). This page is the part that is true of any deployment.

## Architecture

- `mamut-routing-publish serve` serves the built tree, the repository artifact roots (`LICENSE`, `benchmarks/`, the
  `dist/` caches referenced by payloads) and `/healthz`, with cache headers, ETags, Range and precompressed negotiation.
  There is no compute endpoint.
- In root mode nginx serves `dist/` and `benchmarks/` directly and proxies `/api/*`; in rootless mode the Python
  server serves everything on one port behind the domain's reverse proxy.
- Releases are built into `<releases>/dist-<timestamp>` and activated by an atomic `dist` symlink swap. Publication
  state lives outside the release directories and is hydrated before each build.
- Reference sizing: 4 to 6 vCPU, 8 to 16 GB RAM, 25+ GB disk. Serving is light; the build is what needs memory.

## What `deploy.sh` does

1. `git pull --ff-only` the superproject and update submodules recursively (skipped with `SKIP_SOURCE_UPDATE=1`);
2. archive stale directories of retired submodules (`ARCHIVE_STALE_SUBMODULES`);
3. `uv sync --frozen`;
4. hydrate `publish-state` and seed the new release from older `atf-cache` / `route-geometry-cache` trees;
5. `site build --precompress` into a new release directory, static payload mode;
6. swap the `dist` symlink;
7. restart the server (direct process or systemd unit), wait for `/healthz`;
8. refresh nginx if the templates changed (root mode);
9. keep the newest `KEEP_RELEASES` release directories.

## The environment contract

| Variable | Meaning |
|---|---|
| `ENV_FILE` | shell file exported before everything else (holds `MAMUT_BASEMAP_API_KEY`, never committed) |
| `APP_DIR`, `ROUTING_DIR`, `RELEASES_DIR` | superproject, the MAMUT-routing checkout, the releases root |
| `SITE_BUILD_JOBS`, `SITE_BUILD_ATF_MAX_N`, `SITE_BUILD_SKIP_ATF_CACHE` (default 1), `SITE_BUILD_SKIP_ROUTE_GEOMETRY`, `SITE_BUILD_FETCH_MISSING_OSM` (default 0), `ROUTE_GEOMETRY_JOBS` (default 1) | forwarded to `site build` |
| `SITE_BUILD_STATE_DIR`, `SITE_BUILD_HYDRATE_PUBLISH_STATE`, `SITE_BUILD_SEED_RELEASE_SIDECARS` | state and cache reuse across releases |
| `API_RESTART_MODE` (`direct` or systemd), `API_HOST`, `PORT`, `API_HEALTH_HOST`, `API_REPO_ROOT`, `API_PID_FILE`, `API_LOG_FILE` | how the server is (re)started and checked |
| `START_API_ONLY` | restart the server without building; **always pass `START_API_ONLY=0` explicitly** for a real deploy, a stale export silently turns the deploy into a restart |
| `SKIP_SOURCE_UPDATE`, `GIT_SUBMODULE_TRANSPORT` (`ssh`, `https`), `GIT_SSH_KEY` | source update behaviour |
| `KEEP_RELEASES`, `REFRESH_NGINX`, `DOMAIN`, `CERTBOT_ROOT` | housekeeping, root mode only |

## A deploy, end to end

```bash
# 1. locally: bump the MAMUT-routing pointer in the deploy superproject and push it
# 2. on the host, in a screen/tmux session or with nohup (a build outlives an ssh session).
#    deploy.sh pulls the superproject and updates every submodule itself (SKIP_SOURCE_UPDATE=0, the default):
cd ~/mamut-routing-deploy
ENV_FILE=~/mamut.env START_API_ONLY=0 nohup ./scripts/deploy.sh > ~/deploy-$(date +%F).log 2>&1 < /dev/null &
tail -f ~/deploy-*.log
# 3. smoke test from the host and from outside
BASE_URL=http://127.0.0.1:8081 CHECK_HTTP_REDIRECT=0 ./scripts/smoke-test.sh
BASE_URL=https://<domain> ./scripts/smoke-test.sh
```

The smoke test checks the home page, payloads, artifacts, `LICENSE`, `/healthz`, that retired compute endpoints return
404, and precompressed serving. Add `/docs/` to your manual check.

### When the host cannot pull

`SKIP_SOURCE_UPDATE=1` builds **the host's current checkout as it is**: set it only after you updated the sources
yourself, otherwise the deploy succeeds and republishes the old content. The rootless variant without a GitHub key
(the deploy repository is private; the site repositories are public over HTTPS):

```bash
# locally: push the superproject commit straight to the host
git push ssh://<host>/<path>/mamut-routing-deploy main:refs/remotes/local-push/main
# on the host: fast-forward, then update submodules over HTTPS, then deploy without a source update
cd ~/mamut-routing-deploy && git merge --ff-only local-push/main
git -c url."https://github.com/".insteadOf="git@github.com:" submodule update --init --recursive Mamut-routing
ENV_FILE=~/mamut.env START_API_ONLY=0 SKIP_SOURCE_UPDATE=1 GIT_SUBMODULE_TRANSPORT=https nohup ./scripts/deploy.sh > ~/deploy-$(date +%F).log 2>&1 < /dev/null &
```

## Rollback

Content: point `dist` at the previous release directory (`ln -sfn <releases>/dist-<older> dist`) and restart the
server. Code: check out the previous superproject commit, `git submodule update --init --recursive`, restart. Then
smoke test.

## Before you deploy a heavy change

- Route geometry for new or replaced BKS: compute locally, copy `dist/route-geometry-cache` into the release
  directory (tar over ssh), let the build reuse it.
- Free disk (`df -h`) and memory (`free -m`) first; never unpack archives under a tmpfs `/tmp`.
- New satellite: initialise it on the host with HTTPS remotes if the host has no GitHub key.
