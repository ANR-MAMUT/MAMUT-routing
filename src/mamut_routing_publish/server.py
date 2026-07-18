"""Static site server for the published MAMUT-routing website.

Replaces the Julia HTTP.jl webapp on the serving side: the public website
is fully static, so this serves exactly three things and nothing else:

- the built ``dist/`` tree (resolved first, like the Julia server did);
- the repo artifact roots that payload links reference by repo-relative
  path (``LICENSE``, ``benchmarks``, ``dist``), with traversal containment;
- ``/healthz`` (also mirrored at ``/api/healthz`` so existing smoke tests
  and monitoring keep working across the cutover).

Serving quality the Julia server lacked in rootless mode: real
Cache-Control policy instead of a universal ``no-store``, strong ETags
with conditional 304s, Range support (via Starlette's FileResponse), and
precompressed ``.gz``/``.br`` sidecar negotiation (see ``precompress.py``).

One deliberate rule: files whose own name ends in ``.gz`` (the
``.atf.json.gz`` sidecars, the collection geo sidecars) are opaque
``application/gzip`` bytes with NO ``Content-Encoding`` header. The
frontend fetches them raw and decompresses via DecompressionStream;
transparent decompression by the browser would break that contract.
"""

from __future__ import annotations

from pathlib import Path

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import FileResponse, JSONResponse, PlainTextResponse, Response
from starlette.routing import Route

DEFAULT_SERVE_HOST = "127.0.0.1"
#: 8082 by default, never 8081: during the transition the old Julia server
#: keeps 8081 on the local machine so both versions can be compared side by
#: side. Deployments that own the proxy target pass --port explicitly.
DEFAULT_SERVE_PORT = 8082

REPO_ARTIFACT_ROOT_ENTRIES = frozenset({"LICENSE", "benchmarks", "dist"})

CONTENT_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".ico": "image/x-icon",
    ".json": "application/json; charset=utf-8",
    ".vrp": "text/plain; charset=utf-8",
    ".txt": "text/plain; charset=utf-8",
    ".md": "text/markdown; charset=utf-8",
    ".xml": "application/xml; charset=utf-8",
    ".gz": "application/gzip",
    ".woff2": "font/woff2",
}
DEFAULT_CONTENT_TYPE = "application/octet-stream"


def content_type_for(filename: str) -> str:
    suffix = Path(filename).suffix.lower()
    return CONTENT_TYPES.get(suffix, DEFAULT_CONTENT_TYPE)


def normalize_request_path(raw_path: str) -> str | None:
    """Collapse a request path to /segment/... form; None rejects traversal."""
    candidate = raw_path.replace("\\", "/")
    keep_trailing_slash = candidate.endswith("/")
    segments: list[str] = []
    for segment in candidate.split("/"):
        if not segment or segment == ".":
            continue
        if segment == ".." or "\x00" in segment:
            return None
        segments.append(segment)
    if not segments:
        return "/"
    return "/" + "/".join(segments) + ("/" if keep_trailing_slash else "")


def _contained(candidate: Path, root: Path) -> bool:
    """Containment against the RESOLVED root: ``dist`` is a symlink to the
    active release on deployments (atomic-swap layout), so candidates resolve
    outside the repo tree legitimately. Traversal segments are already
    rejected at normalization; this guards symlink escapes past the root."""
    try:
        return candidate.resolve().is_relative_to(root.resolve())
    except OSError:
        return False


def resolve_public_file(repo_root: Path, request_path: str) -> Path | None:
    """Port of the Julia server's dual-root resolution.

    The ``dist`` tree is tried first (with the extensionless -> index.html
    and trailing-slash -> index.html conventions the shells rely on), then
    the whitelisted repo artifact roots for repo-relative payload links.
    """
    relative_candidates: list[str] = []
    if request_path == "/":
        relative_candidates.append("index.html")
    elif request_path.endswith("/"):
        relative_candidates.append(f"{request_path[1:-1]}/index.html")
    else:
        relative = request_path[1:]
        relative_candidates.append(relative)
        if "." not in relative.rsplit("/", 1)[-1]:
            relative_candidates.append(f"{relative}/index.html")

    site_root = repo_root / "dist"
    for relative_candidate in relative_candidates:
        site_candidate = site_root / relative_candidate
        if site_candidate.is_file() and _contained(site_candidate, site_root):
            return site_candidate
        first_segment = relative_candidate.split("/", 1)[0]
        if first_segment not in REPO_ARTIFACT_ROOT_ENTRIES:
            continue
        repo_candidate = repo_root / relative_candidate
        if repo_candidate.is_file() and _contained(repo_candidate, repo_root / first_segment):
            return repo_candidate
    return None


def cache_control_for(request_path: str) -> str:
    if request_path.startswith("/dist/route-geometry-cache/"):
        # Content-addressed by BKS sha256: a changed BKS gets a new URL.
        return "public, max-age=31536000, immutable"
    if request_path.startswith("/site-payloads/"):
        return "public, max-age=300, stale-while-revalidate=600"
    if request_path.startswith(("/benchmarks/", "/dist/")) or request_path == "/LICENSE":
        return "public, max-age=3600"
    return "public, max-age=300, must-revalidate"


def accepted_encodings(header_value: str) -> set[str]:
    encodings: set[str] = set()
    for token in header_value.split(","):
        name = token.split(";", 1)[0].strip().lower()
        if name:
            encodings.add(name)
    return encodings


def negotiate_variant(path: Path, accept_encoding: str) -> tuple[Path, str | None]:
    """Pick a precompressed sidecar when the client accepts its encoding.

    Files that are themselves ``.gz``/``.br`` content are never negotiated:
    they are opaque bytes by contract.
    """
    if path.name.endswith((".gz", ".br")):
        return path, None
    accepted = accepted_encodings(accept_encoding)
    for encoding, suffix in (("br", ".br"), ("gzip", ".gz")):
        if encoding in accepted:
            variant = path.with_name(path.name + suffix)
            if variant.is_file():
                return variant, encoding
    return path, None


def _etag_for(path: Path) -> str:
    stat = path.stat()
    return f'"{stat.st_mtime_ns:x}-{stat.st_size:x}"'


def _if_none_match_hits(header_value: str | None, etag: str) -> bool:
    if not header_value:
        return False
    if header_value.strip() == "*":
        return True
    candidates = {value.strip().removeprefix("W/") for value in header_value.split(",")}
    return etag in candidates


async def serve_site_file(request: Request) -> Response:
    repo_root: Path = request.app.state.repo_root
    normalized = normalize_request_path(request.path_params.get("path", ""))
    if normalized is None:
        return PlainTextResponse("Path traversal is not allowed", status_code=400)
    resolved = resolve_public_file(repo_root, normalized)
    if resolved is None:
        return PlainTextResponse("Not found", status_code=404)

    body_path, encoding = negotiate_variant(resolved, request.headers.get("accept-encoding", ""))
    headers = {
        "Cache-Control": cache_control_for(normalized),
        "Vary": "Accept-Encoding",
        "ETag": _etag_for(body_path),
    }
    if encoding is not None:
        headers["Content-Encoding"] = encoding
    if _if_none_match_hits(request.headers.get("if-none-match"), headers["ETag"]):
        return Response(status_code=304, headers=headers)
    return FileResponse(body_path, media_type=content_type_for(resolved.name), headers=headers)


async def healthz(request: Request) -> Response:
    return JSONResponse({"status": "ok"}, headers={"Cache-Control": "no-store"})


def create_app(repo_root: str | Path) -> Starlette:
    root = Path(repo_root).resolve()
    if not (root / "dist").is_dir():
        raise FileNotFoundError(f"No dist/ tree under repo root: {root}. Run `site build` first.")
    app = Starlette(
        routes=[
            Route("/healthz", healthz, methods=["GET", "HEAD"]),
            Route("/api/healthz", healthz, methods=["GET", "HEAD"]),
            Route("/{path:path}", serve_site_file, methods=["GET", "HEAD"]),
        ]
    )
    app.state.repo_root = root
    return app
