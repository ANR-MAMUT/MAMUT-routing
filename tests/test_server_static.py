"""Static server contract: dual-root resolution, cache policy, precompressed
negotiation, conditional requests, and the opaque-gzip ATF rule."""

from __future__ import annotations

import gzip
import json
from pathlib import Path

import pytest
from starlette.testclient import TestClient

from mamut_routing_publish.precompress import precompress_tree
from mamut_routing_publish.server import create_app, normalize_request_path


@pytest.fixture()
def site_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "MAMUT-routing"
    dist = repo / "dist"
    (dist / "site-payloads").mkdir(parents=True)
    (dist / "webapp").mkdir()
    (dist / "benchmarks" / "cvrp").mkdir(parents=True)
    (dist / "atf-cache" / "Mamut2026").mkdir(parents=True)
    (dist / "route-geometry-cache" / "ab").mkdir(parents=True)

    (dist / "index.html").write_text("<html>home</html>")
    (dist / "benchmarks" / "cvrp" / "index.html").write_text("<html>cvrp</html>")
    (dist / "site-payloads" / "index.json").write_text(json.dumps({"route_path": "/"}))
    (dist / "webapp" / "site.js").write_text("// site\n")
    (dist / "atf-cache" / "Mamut2026" / "inst.atf.json.gz").write_bytes(
        gzip.compress(b'{"atfs": []}')
    )
    (dist / "route-geometry-cache" / "ab" / "abcdef.route-geometry.json.gz").write_bytes(
        gzip.compress(b"{}")
    )

    (repo / "LICENSE").write_text("MIT-ish license text")
    (repo / "benchmarks" / "CVRP" / "Fam").mkdir(parents=True)
    (repo / "benchmarks" / "CVRP" / "Fam" / "inst.vrp.json").write_text('{"instance_name": "inst"}')
    (repo / "secret.txt").write_text("not served")
    return repo


@pytest.fixture()
def client(site_repo: Path) -> TestClient:
    return TestClient(create_app(site_repo))


def test_normalize_request_path_rejects_traversal() -> None:
    assert normalize_request_path("../pyproject.toml") is None
    assert normalize_request_path("a/../../b") is None
    assert normalize_request_path("a/./b/") == "/a/b/"
    assert normalize_request_path("") == "/"


def test_root_and_directory_shells(client: TestClient) -> None:
    assert client.get("/").text == "<html>home</html>"
    assert client.get("/benchmarks/cvrp/").text == "<html>cvrp</html>"
    # Extensionless request falls back to the directory shell.
    assert client.get("/benchmarks/cvrp").text == "<html>cvrp</html>"


def test_site_files_and_cache_policy(client: TestClient) -> None:
    home = client.get("/")
    assert home.headers["cache-control"] == "public, max-age=300, must-revalidate"
    assert home.headers["content-type"].startswith("text/html")

    payload = client.get("/site-payloads/index.json")
    assert payload.status_code == 200
    assert payload.headers["cache-control"] == "public, max-age=300, stale-while-revalidate=600"
    assert payload.headers["content-type"].startswith("application/json")

    script = client.get("/webapp/site.js")
    assert script.headers["content-type"].startswith("text/javascript")


def test_payload_bytes_identical(client: TestClient, site_repo: Path) -> None:
    served = client.get("/site-payloads/index.json").content
    assert served == (site_repo / "dist" / "site-payloads" / "index.json").read_bytes()


def test_repo_artifact_roots(client: TestClient) -> None:
    license_response = client.get("/LICENSE")
    assert license_response.status_code == 200
    assert license_response.headers["cache-control"] == "public, max-age=3600"

    vrp = client.get("/benchmarks/CVRP/Fam/inst.vrp.json")
    assert vrp.status_code == 200
    assert vrp.headers["cache-control"] == "public, max-age=3600"

    # Repo files outside the whitelisted roots are never served.
    assert client.get("/secret.txt").status_code == 404
    assert client.get("/pyproject.toml").status_code == 404


def test_atf_sidecar_is_opaque_gzip(client: TestClient, site_repo: Path) -> None:
    response = client.get(
        "/dist/atf-cache/Mamut2026/inst.atf.json.gz",
        headers={"Accept-Encoding": "gzip, br"},
    )
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/gzip"
    assert "content-encoding" not in response.headers
    raw = (site_repo / "dist" / "atf-cache" / "Mamut2026" / "inst.atf.json.gz").read_bytes()
    # httpx must not have transparently decompressed: the payload is opaque.
    assert response.content == raw
    assert gzip.decompress(response.content) == b'{"atfs": []}'


def test_route_geometry_cache_is_immutable(client: TestClient) -> None:
    response = client.get("/dist/route-geometry-cache/ab/abcdef.route-geometry.json.gz")
    assert response.status_code == 200
    assert response.headers["cache-control"] == "public, max-age=31536000, immutable"


def test_traversal_and_methods(client: TestClient) -> None:
    # httpx collapses literal ".." segments client-side; percent-encoded
    # traversal reaches the server and must be rejected there.
    assert client.get("/dist/%2e%2e/pyproject.toml").status_code == 400
    assert client.post("/").status_code == 405


def test_healthz(client: TestClient) -> None:
    for path in ("/healthz", "/api/healthz"):
        response = client.get(path)
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}
        assert response.headers["cache-control"] == "no-store"


def test_precompressed_negotiation(site_repo: Path) -> None:
    summary = precompress_tree(site_repo / "dist")
    # index.html and site.js are under 1 KiB; grow one file over the threshold.
    big = site_repo / "dist" / "webapp" / "big.js"
    big.write_text("// filler\n" * 200)
    summary = precompress_tree(site_repo / "dist")
    assert summary.written >= 1
    assert (site_repo / "dist" / "webapp" / "big.js.gz").is_file()
    assert (site_repo / "dist" / "webapp" / "big.js.br").is_file()
    # Existing .gz content never gains double-compressed sidecars.
    assert not (site_repo / "dist" / "atf-cache" / "Mamut2026" / "inst.atf.json.gz.gz").exists()

    client = TestClient(create_app(site_repo))
    plain = client.get("/webapp/big.js", headers={"Accept-Encoding": "identity"})
    assert "content-encoding" not in plain.headers
    assert plain.headers["vary"] == "Accept-Encoding"

    with client.stream("GET", "/webapp/big.js", headers={"Accept-Encoding": "gzip"}) as gz:
        assert gz.headers["content-encoding"] == "gzip"
        assert gz.headers["content-type"].startswith("text/javascript")

    with client.stream("GET", "/webapp/big.js", headers={"Accept-Encoding": "gzip, br"}) as br:
        assert br.headers["content-encoding"] == "br"

    # Sidecars themselves are not directly negotiable content.
    direct = client.get("/webapp/big.js.gz", headers={"Accept-Encoding": "br"})
    assert direct.headers["content-type"] == "application/gzip"
    assert "content-encoding" not in direct.headers


def test_conditional_requests(client: TestClient) -> None:
    first = client.get("/")
    etag = first.headers["etag"]
    hit = client.get("/", headers={"If-None-Match": etag})
    assert hit.status_code == 304
    assert hit.content == b""
    assert hit.headers["etag"] == etag
    assert hit.headers["cache-control"] == "public, max-age=300, must-revalidate"
    miss = client.get("/", headers={"If-None-Match": '"other"'})
    assert miss.status_code == 200


def test_symlinked_dist_release_layout(site_repo: Path, tmp_path: Path) -> None:
    """Deployments swap ``dist`` as a symlink to a release dir; the preview
    layout for side-by-side comparison uses the same shape. Both must serve."""
    release = tmp_path / "releases" / "dist-1"
    release.parent.mkdir(parents=True)
    (site_repo / "dist").rename(release)
    (site_repo / "dist").symlink_to(release)

    client = TestClient(create_app(site_repo))
    assert client.get("/").text == "<html>home</html>"
    assert client.get("/site-payloads/index.json").status_code == 200
    assert client.get("/dist/atf-cache/Mamut2026/inst.atf.json.gz").status_code == 200
    assert client.get("/LICENSE").status_code == 200
    assert client.get("/secret.txt").status_code == 404


def test_head_and_range(client: TestClient) -> None:
    head = client.head("/")
    assert head.status_code == 200
    assert head.content == b""
    partial = client.get("/", headers={"Range": "bytes=0-3"})
    assert partial.status_code == 206
    assert partial.content == b"<htm"
