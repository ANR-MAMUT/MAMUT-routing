const runtimeParams = new URLSearchParams(window.location.search);

const CATALOG_SORT_OPTIONS = Object.freeze([
  { value: "catalog", label: "Catalog order" },
  { value: "name", label: "Instance name" },
  { value: "size", label: "Customers" },
  { value: "routes", label: "Routes" },
  { value: "cost", label: "BKS cost", requiresSingleObjective: true },
]);

function normalizeCatalogSort(value) {
  const normalized = String(value || "").toLowerCase();
  if (normalized === "city-size") return "catalog";
  return CATALOG_SORT_OPTIONS.some((option) => option.value === normalized) ? normalized : "catalog";
}

function normalizeSortDirection(value) {
  return String(value || "").toLowerCase() === "desc" ? "desc" : "asc";
}

const state = {
  routePath: document.body.dataset.routePath || "/",
  payloadSource: document.body.dataset.payloadSource || "",
  payloadMode: resolvePayloadMode(),
  payloadApiPrefix: resolvePayloadApiPrefix(),
  payloadStaticRoot: resolvePayloadStaticRoot(),
  pageKind: document.body.dataset.pageKind || "payload",
  workbenchMode: document.body.dataset.workbenchMode || "catalog",
  aside: document.getElementById("pageAside"),
  stage: document.getElementById("pageStage"),
  title: document.getElementById("pageTitle"),
  intro: document.getElementById("pageIntro"),
  breadcrumbs: document.getElementById("breadcrumbTrail"),
  layout: document.getElementById("pageLayout"),
  status: document.getElementById("pageStatus"),
  catalogFilters: {
    problem: runtimeParams.get("problem") || "",
    family: runtimeParams.get("family") || "",
    metric: runtimeParams.get("metric") || "",
    city: runtimeParams.get("city") || "",
    size: runtimeParams.get("size") || "",
    method: runtimeParams.get("method") || "",
    scenario: runtimeParams.get("scenario") || "",
    geometry: runtimeParams.get("geometry") || "",
    search: runtimeParams.get("q") || "",
    sort: normalizeCatalogSort(runtimeParams.get("sort")),
    direction: normalizeSortDirection(runtimeParams.get("dir")),
  },
  collectionFilters: {
    size_bucket: runtimeParams.get("size") || "",
    historical_topology_type: runtimeParams.get("topology") || "",
    historical_tw_type: runtimeParams.get("tw") || "",
    place_slug: runtimeParams.get("city") || "",
    objective_function: runtimeParams.get("objective") || "",
    has_bks: runtimeParams.get("bks") || "",
    search: runtimeParams.get("q") || "",
    sort: runtimeParams.get("sort") || "size-name",
  },
};

// Nocturne per-theme 20-color route palette: the concrete values live in the
// CSS custom properties --route-0..--route-19 (VIVID_D / VIVID_L from the
// merged demo), so SVG previews and swatches recolor with the theme toggle.
const PALETTE = Array.from({ length: 20 }, (_, index) => `var(--route-${index})`);
const HOME_PREVIEW_ROTATION_MS = 5000;
const ROAD_CACHE_ENDPOINT_TOLERANCE_METERS = 250;
const WGS84_A = 6378137.0;
const WGS84_F = 1 / 298.257223563;
const WGS84_E2 = WGS84_F * (2 - WGS84_F);
const MAMUT_PROJECT_LOGO_PATH = "/webapp/logos/logo_anr_mamut.png";
const GITHUB_BENCHMARKS_ROOT = "https://github.com/ANR-MAMUT/MAMUT-routing/tree/main/benchmarks";
const GITHUB_ICON_PATH = "/webapp/icons/GitHub_Invertocat_Black.svg";
const OPTIMAL_BADGE_ICON_PATH = "/webapp/icons/check-badge-svgrepo-com.svg";
const FILE_BACKED_BENCHMARK_FAMILIES = new Set(["Dimacs2021", "Sintef2008"]);
const PROJECT_PARTICIPANT_LOGOS = [
  { label: "ANR", src: "/webapp/logos/ANR-logo-2021-noir.png", wide: true, href: "https://anr.fr/en/" },
  { label: "CNRS", src: "/webapp/logos/LOGO_CNRS_BLEU.png", href: "https://www.cnrs.fr/en" },
  { label: "CITI", src: "/webapp/logos/citi_logo.png", href: "https://www.citi-lab.fr/" },
  { label: "Inria", src: "/webapp/logos/inr_logo_rouge.png", wide: true, href: "https://www.inria.fr/en" },
  { label: "INSA", src: "/webapp/logos/logo-insa.png", wide: true, href: "https://www.insa-lyon.fr/en" },
  { label: "LAB-STICC", src: "/webapp/logos/logo-labsticc.png", wide: true, href: "https://labsticc.fr/en" },
  { label: "Universite Bretagne Sud", src: "/webapp/logos/logo-ubs.png", wide: true, href: "https://www.univ-ubs.fr/en/index.html" },
];

const WORKBENCH_PAYLOAD_CACHE = new Map();
const ARTIFACT_JSON_CACHE = new Map();
let homePreviewRotationTimer = null;

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function normalizeApiPrefix(prefix) {
  const value = String(prefix || "/api/site-payload").trim();
  if (!value) {
    return "/api/site-payload";
  }
  if (/^https?:\/\//i.test(value)) {
    return value.replace(/\/+$/, "");
  }
  return `/${value.replace(/^\/+/, "").replace(/\/+$/, "")}`;
}

function resolvePayloadMode() {
  const requestedMode = runtimeParams.get("payloadMode") || document.body.dataset.payloadMode || "static";
  return requestedMode === "api" ? "api" : "static";
}


function resolvePayloadApiPrefix() {
  return normalizeApiPrefix(runtimeParams.get("apiPrefix") || document.body.dataset.payloadApiPrefix || "/api/site-payload");
}

function resolvePayloadStaticRoot() {
  const value = runtimeParams.get("payloadRoot") || document.body.dataset.payloadStaticRoot || "/site-payloads";
  return `/${String(value).replace(/^\/+/, "").replace(/\/+$/, "")}`;
}

function normalizeRoute(routePath) {
  if (!routePath || routePath === "/") {
    return "/";
  }
  const trimmed = routePath.replace(/^\/+/, "").replace(/\/+$/, "");
  return `/${trimmed}/`;
}

function routeSegments(routePath) {
  const normalized = normalizeRoute(routePath);
  if (normalized === "/") {
    return [];
  }
  return normalized.replace(/^\/+|\/+$/g, "").split("/").filter(Boolean);
}

function relativeFromCurrent(targetPath, { directory = false } = {}) {
  if (!targetPath) {
    return "#";
  }
  const fromParts = routeSegments(state.routePath);
  let target = targetPath.startsWith("/") ? targetPath : `/${targetPath}`;
  if (directory) {
    target = `${normalizeRoute(target)}index.html`;
  }
  const targetParts = target.replace(/^\/+/, "").split("/").filter(Boolean);
  let shared = 0;
  while (shared < fromParts.length && shared < targetParts.length && fromParts[shared] === targetParts[shared]) {
    shared += 1;
  }
  const up = new Array(fromParts.length - shared).fill("..");
  const down = targetParts.slice(shared);
  const relative = [...up, ...down].join("/");
  return relative || "index.html";
}

function routeHref(routePath) {
  return relativeFromCurrent(routePath, { directory: true });
}

function artifactHref(path) {
  return relativeFromCurrent(path, { directory: false });
}

function siteAssetHref(path) {
  return relativeFromCurrent(path, { directory: false });
}

async function fetchJson(sourcePath) {
  const response = await fetch(sourcePath);
  if (!response.ok) {
    throw new Error(`Unable to fetch ${sourcePath}: ${response.status}`);
  }
  return response.json();
}

function fetchJsonMemo(sourcePath) {
  if (ARTIFACT_JSON_CACHE.has(sourcePath)) {
    return ARTIFACT_JSON_CACHE.get(sourcePath);
  }
  const promise = fetchJson(sourcePath).catch((error) => {
    ARTIFACT_JSON_CACHE.delete(sourcePath);
    throw error;
  });
  ARTIFACT_JSON_CACHE.set(sourcePath, promise);
  return promise;
}

// --- Collection geo sidecars (Poryos2026 v2) ------------------------------
// v1 instances ship an explicit .meta.json geometry sidecar; collection
// instances ship a shared, gzipped geo sidecar with an indexed road cache
// (a local vertex table + per-metric paths as index lists). The loader below
// resolves either into the same geometryMeta shape the viewer consumes.

const GEOMETRY_META_CACHE = new Map();

function geometryMetaSourcePath(artifactLinks) {
  if (!artifactLinks) {
    return null;
  }
  return artifactLinks.meta_path || artifactLinks.geo_json_path || null;
}

async function fetchGeoSidecarJson(sourceHref) {
  const response = await fetch(sourceHref, { headers: { Accept: "application/json, */*" } });
  if (!response.ok) {
    throw new Error(`HTTP ${response.status} for ${sourceHref}`);
  }
  const buffer = await response.arrayBuffer();
  const bytes = new Uint8Array(buffer);
  // The server may already have decoded Content-Encoding: gzip; sniff the magic.
  if (bytes.length >= 2 && bytes[0] === 0x1f && bytes[1] === 0x8b) {
    const decompressed = new Response(new Blob([buffer]).stream().pipeThrough(new DecompressionStream("gzip")));
    return JSON.parse(await decompressed.text());
  }
  return JSON.parse(new TextDecoder().decode(bytes));
}

function geometryMetaFromGeoSidecar(geo) {
  const nodes = Array.isArray(geo?.nodes) ? geo.nodes : [];
  const roadCache = {};
  const cache = geo?.road_cache;
  const vertexTable = Array.isArray(cache?.vertex_lonlat) ? cache.vertex_lonlat : [];
  const paths = cache?.paths && typeof cache.paths === "object" ? cache.paths : {};
  Object.entries(paths).forEach(([metric, entries]) => {
    const converted = {};
    Object.entries(entries || {}).forEach(([key, indexes]) => {
      const separator = key.indexOf("-");
      if (separator <= 0 || !Array.isArray(indexes)) {
        return;
      }
      const fromNode = key.slice(0, separator);
      const toNode = key.slice(separator + 1);
      const polyline = indexes
        .map((vertexIndex) => vertexTable[vertexIndex])
        .filter((point) => Array.isArray(point) && point.length === 2);
      if (polyline.length >= 2) {
        converted[`node:${fromNode}_${toNode}`] = polyline;
      }
    });
    roadCache[String(metric).toLowerCase()] = converted;
  });
  return { nodes, depot_instance_node_id: 0, road_cache: roadCache };
}

function geometryMetaFromRouteSidecar(routeGeometry) {
  const vertexTable = Array.isArray(routeGeometry?.vertex_lonlat) ? routeGeometry.vertex_lonlat : [];
  const converted = {};
  Object.entries(routeGeometry?.paths || {}).forEach(([key, indexes]) => {
    const separator = key.indexOf("-");
    if (separator <= 0 || !Array.isArray(indexes)) {
      return;
    }
    const fromNode = key.slice(0, separator);
    const toNode = key.slice(separator + 1);
    const polyline = indexes
      .map((vertexIndex) => vertexTable[vertexIndex])
      .filter((point) => Array.isArray(point) && point.length === 2);
    if (polyline.length >= 2) {
      converted[`node:${fromNode}_${toNode}`] = polyline;
    }
  });
  return {
    road_cache: {
      [String(routeGeometry?.metric || "fastest").toLowerCase()]: converted,
    },
    route_geometry_straight_fallback_paths: Array.isArray(routeGeometry?.straight_fallback_paths)
      ? routeGeometry.straight_fallback_paths
      : [],
  };
}

function fetchGeometryMetaMemo(artifactLinks) {
  const sourcePath = geometryMetaSourcePath(artifactLinks);
  if (!sourcePath) {
    return Promise.resolve(null);
  }
  const href = artifactHref(sourcePath);
  if (GEOMETRY_META_CACHE.has(href)) {
    return GEOMETRY_META_CACHE.get(href);
  }
  const promise = (artifactLinks.meta_path
    ? fetchJsonMemo(href)
    : fetchGeoSidecarJson(href).then(geometryMetaFromGeoSidecar)
  ).catch((error) => {
    GEOMETRY_META_CACHE.delete(href);
    throw error;
  });
  GEOMETRY_META_CACHE.set(href, promise);
  return promise;
}

function fetchRouteGeometryMetaMemo(bksEntry) {
  const sourcePath = bksEntry?.route_geometry_path;
  if (!sourcePath) {
    return Promise.resolve(null);
  }
  const href = artifactHref(sourcePath);
  if (GEOMETRY_META_CACHE.has(href)) {
    return GEOMETRY_META_CACHE.get(href);
  }
  const promise = fetchGeoSidecarJson(href).then(geometryMetaFromRouteSidecar).catch((error) => {
    GEOMETRY_META_CACHE.delete(href);
    throw error;
  });
  GEOMETRY_META_CACHE.set(href, promise);
  return promise;
}

async function routeGeometryMetaForEntry(bksEntry) {
  if (!bksEntry?.route_geometry_path) {
    return null;
  }
  try {
    return await fetchRouteGeometryMetaMemo(bksEntry);
  } catch (error) {
    console.warn("Unable to load the BKS route-geometry artifact", error);
    return null;
  }
}

function mergeGeometryMeta(geometryMeta, routeGeometryMeta) {
  if (!routeGeometryMeta) {
    return geometryMeta;
  }
  return {
    ...(geometryMeta || {}),
    ...routeGeometryMeta,
    road_cache: {
      ...(geometryMeta?.road_cache || {}),
      ...(routeGeometryMeta.road_cache || {}),
    },
  };
}

async function fetchWorkbenchPayloadForRoute(routePath) {
  const sourcePath = payloadUrlForRoute(routePath);
  const cacheKey = `${state.payloadMode}:${sourcePath}`;
  if (WORKBENCH_PAYLOAD_CACHE.has(cacheKey)) {
    return WORKBENCH_PAYLOAD_CACHE.get(cacheKey);
  }
  const payload = await fetchJson(sourcePath);
  WORKBENCH_PAYLOAD_CACHE.set(cacheKey, payload);
  return payload;
}

function payloadStaticHref(routePath) {
  const normalizedRoute = normalizeRoute(routePath);
  if (normalizedRoute === "/") {
    return relativeFromCurrent(`${state.payloadStaticRoot}/index.json`, { directory: false });
  }
  return relativeFromCurrent(`${state.payloadStaticRoot}${normalizedRoute}index.json`, { directory: false });
}

function payloadUrlForRoute(routePath) {
  const normalizedRoute = normalizeRoute(routePath);
  if (state.payloadMode !== "api") {
    if (normalizedRoute === state.routePath && state.payloadSource) {
      return state.payloadSource;
    }
    return payloadStaticHref(normalizedRoute);
  }
  if (normalizedRoute === "/") {
    return state.payloadApiPrefix;
  }
  return `${state.payloadApiPrefix}${normalizedRoute.slice(0, -1)}`;
}

function setStatus(message) {
  state.status.textContent = message;
}

function clearHomePreviewRotation() {
  if (homePreviewRotationTimer) {
    window.clearInterval(homePreviewRotationTimer);
    homePreviewRotationTimer = null;
  }
}

function updateWorkbenchRuntimeParams(values) {
  Object.entries(values).forEach(([key, value]) => {
    if (value === null || value === undefined || value === "") {
      runtimeParams.delete(key);
      return;
    }
    runtimeParams.set(key, String(value));
  });
  const query = runtimeParams.toString();
  const nextUrl = `${window.location.pathname}${query ? `?${query}` : ""}`;
  window.history.replaceState({}, "", nextUrl);
}

function setPage(title, intro, breadcrumbs = [], shell = "catalog") {
  clearHomePreviewRotation();
  if (state.title) {
    state.title.textContent = title;
  }
  if (state.intro) {
    state.intro.textContent = intro;
  }
  if (state.layout) {
    state.layout.dataset.shell = shell;
  }
  if (state.aside) {
    state.aside.hidden = shell === "home";
    state.aside.setAttribute("aria-hidden", shell === "home" ? "true" : "false");
  }
  renderBreadcrumbs(breadcrumbs);
}

function renderBreadcrumbs(items) {
  if (!items || items.length === 0) {
    state.breadcrumbs.innerHTML = "";
    return;
  }
  const breadcrumbHtml = items
    .map(
      (item, index) =>
        `${index > 0 ? '<span class="breadcrumb-sep">/</span>' : ""}<a href="${routeHref(item.route_path)}">${escapeHtml(item.label)}</a>`,
    )
    .join("");
  const githubHref = githubBenchmarksHref(items);
  state.breadcrumbs.innerHTML = `${breadcrumbHtml}${githubHref ? renderBenchmarksGithubLink(githubHref) : ""}`;
}

function githubBenchmarksHref(items) {
  if (!items?.length || normalizeRoute(items[0]?.route_path) !== "/benchmarks/") {
    return "";
  }
  const sourceSegments = items
    .map((item) => String(item?.label || "").trim())
    .filter(Boolean);
  if (sourceSegments.length === 0 || sourceSegments[0].toLowerCase() !== "benchmarks") {
    return "";
  }
  const githubSegments = githubBenchmarkPathSegments(sourceSegments);
  const encodedPath = githubSegments
    .slice(1)
    .map((segment) => encodeGithubPathSegment(segment))
    .join("/");
  return encodedPath ? `${GITHUB_BENCHMARKS_ROOT}/${encodedPath}` : GITHUB_BENCHMARKS_ROOT;
}

function githubBenchmarkPathSegments(sourceSegments) {
  const benchmarkFamily = sourceSegments[2] || "";
  const lastSegment = sourceSegments[sourceSegments.length - 1] || "";
  const pointsToHistoricalInstance =
    FILE_BACKED_BENCHMARK_FAMILIES.has(benchmarkFamily) &&
    sourceSegments.length >= 5 &&
    !lastSegment.startsWith("n=");
  return pointsToHistoricalInstance ? sourceSegments.slice(0, -1) : sourceSegments;
}

function encodeGithubPathSegment(segment) {
  return encodeURIComponent(segment).replaceAll("%3D", "=");
}

function renderBenchmarksGithubLink(href) {
  return `<a class="breadcrumb-github-link" href="${href}" target="_blank" rel="noopener noreferrer" aria-label="Open this benchmark path on GitHub" title="Open this benchmark path on GitHub"><img src="${siteAssetHref(GITHUB_ICON_PATH)}" alt="" /></a>`;
}

function renderGithubMiniLink(label, href) {
  return `<a class="mini-link github-mini-link" href="${escapeHtml(href)}" target="_blank" rel="noopener"><img src="${siteAssetHref(GITHUB_ICON_PATH)}" alt="" /> <span>${escapeHtml(label)}</span></a>`;
}

function badge(label, alt = false) {
  return `<span class="badge${alt ? " alt" : ""}">${escapeHtml(label)}</span>`;
}

function badgeWithTitleHtml(labelHtml, title, alt = false) {
  return `<span class="badge${alt ? " alt" : ""}" title="${escapeHtml(title)}">${labelHtml}</span>`;
}

function badgeHtml(labelHtml, alt = false) {
  return `<span class="badge${alt ? " alt" : ""}">${labelHtml}</span>`;
}

function formatCost(value) {
  if (value === null || value === undefined) {
    return "n/a";
  }
  if (typeof value === "number" && Number.isFinite(value)) {
    return Number.isInteger(value) ? String(value) : value.toFixed(2);
  }
  return String(value);
}

function costSpan(value, className = "badge-cost") {
  return `<span class="${className}">${escapeHtml(formatCost(value))}</span>`;
}

// Escape, then turn `backtick spans` into inline <code> elements.
function formatInlineCode(text) {
  return escapeHtml(text).replace(/`([^`]+)`/g, "<code>$1</code>");
}

function isHierarchicalObjective(entry) {
  return entry?.objective_function === "HierarchicalVehicleCost";
}

function routesStatValue(entry) {
  if (entry?.num_routes == null) return "";
  if (isHierarchicalObjective(entry)) {
    return { html: `<span class="stat-cost">${escapeHtml(String(entry.num_routes))}</span>` };
  }
  return String(entry.num_routes);
}

// Extra stat-grid rows for a BKS entry carrying a structured optimality proof
// (entry.optimality mirrors the mamut-routing-lib OptimalityMetadata object).
// The full proof detail (certificate wording, prover, campaign) belongs to the
// instance page's BKS card; the compact contexts (inspector pane, lists) only
// show the proven-optimal badge.
function optimalityStatRows(entry) {
  const proof = entry?.optimality;
  if (!proof?.proven) return [];
  const badge = `<span class="badge optimal">${optimalBadgeIconHtml()}proven optimal</span>`;
  const meta = proof.date ? ` <span class="meta-line">${escapeHtml(proof.date)}</span>` : "";
  const rows = [["Optimality", { html: `${badge}${meta}` }]];
  if (proof.certificate) rows.push(["Certificate", proof.certificate]);
  if (proof.prover) rows.push(["Prover", proof.prover]);
  if (proof.campaign) rows.push(["Campaign", proof.campaign]);
  return rows;
}

// Check-badge icon marking a BKS that carries a structured optimality proof.
function optimalBadgeIconHtml() {
  return `<img class="optimal-badge-icon" src="${siteAssetHref(OPTIMAL_BADGE_ICON_PATH)}" alt="" aria-hidden="true" />`;
}

function bksLinkChip(formatted, artifactPath, objective, optimalityProven = false) {
  const iconHtml = optimalityProven ? optimalBadgeIconHtml() : "";
  if (!artifactPath) {
    return badgeWithTitleHtml(`${iconHtml}${formatted.labelHtml}`, formatted.title);
  }
  const href = artifactHref(artifactPath);
  const title = `${optimalityProven ? "Proven optimal: open" : "Open"} BKS JSON · ${objective}`;
  return `<a class="bks-link-chip${optimalityProven ? " optimal" : ""}" href="${href}" target="_blank" rel="noopener" title="${escapeHtml(title)}">${iconHtml}${formatted.labelHtml}<span class="bks-link-chip-glyph" aria-hidden="true">↗</span></a>`;
}

function formatObjectiveBadge(entry) {
  const costHtml = costSpan(entry.cost);
  const costPlain = formatCost(entry.cost);
  const objective = escapeHtml(entry.objective_function);
  if (isHierarchicalObjective(entry) && entry.num_routes != null) {
    const routesHtml = `<span class="badge-cost">${escapeHtml(String(entry.num_routes))}</span>`;
    return {
      labelHtml: `${objective} · ${routesHtml} / ${costHtml}`,
      title: `Hierarchical objective: vehicles / cost = ${entry.num_routes} / ${costPlain}`,
    };
  }
  if (entry.num_routes != null) {
    return {
      labelHtml: `${objective} · ${escapeHtml(String(entry.num_routes))} / ${costHtml}`,
      title: `Mono-cost objective: vehicles / cost = ${entry.num_routes} / ${costPlain}`,
    };
  }
  return {
    labelHtml: `${objective} · ${costHtml}`,
    title: `Mono-cost objective: cost = ${costPlain}`,
  };
}

function renderCard(title, body) {
  return `<section class="card"><h2>${escapeHtml(title)}</h2>${body}</section>`;
}

function renderMarkdownInline(value) {
  // Protect inline-code spans first so their contents (e.g. `t*`, snake_case)
  // are never touched by the emphasis passes below.
  const codeSpans = [];
  let text = escapeHtml(value).replace(/`([^`]+)`/g, (_match, code) => {
    codeSpans.push(code);
    return `@@CODE${codeSpans.length - 1}@@`;
  });
  text = text
    .replace(/\[([^\]]+)\]\((https?:\/\/[^)\s]+)\)/g, (_match, label, href) => {
      return `<a href="${href}" target="_blank" rel="noopener">${label}</a>`;
    })
    .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
    .replace(/\*([^*]+)\*/g, "<em>$1</em>");
  return text.replace(/@@CODE(\d+)@@/g, (_match, index) => `<code>${codeSpans[Number(index)]}</code>`);
}

function renderMarkdownBlocks(markdown) {
  const lines = String(markdown || "").split(/\r?\n/);
  const blocks = [];
  let paragraph = [];
  let listItems = [];
  let quoteLines = [];
  let codeLines = [];
  let inCodeBlock = false;
  let codeLanguage = "";

  const flushParagraph = () => {
    if (paragraph.length === 0) return;
    blocks.push(`<p>${renderMarkdownInline(paragraph.join(" "))}</p>`);
    paragraph = [];
  };
  const flushList = () => {
    if (listItems.length === 0) return;
    blocks.push(`<ul>${listItems.map((item) => `<li>${renderMarkdownInline(item)}</li>`).join("")}</ul>`);
    listItems = [];
  };
  const flushQuote = () => {
    if (quoteLines.length === 0) return;
    blocks.push(`<blockquote>${renderMarkdownBlocks(quoteLines.join("\n"))}</blockquote>`);
    quoteLines = [];
  };
  const flushCode = () => {
    if (codeLines.length === 0 && !codeLanguage) return;
    const languageClass = codeLanguage ? ` class="language-${escapeHtml(codeLanguage)}"` : "";
    blocks.push(`<pre class="mono-block"><code${languageClass}>${escapeHtml(codeLines.join("\n"))}</code></pre>`);
    codeLines = [];
    codeLanguage = "";
  };
  const flushAll = () => {
    flushParagraph();
    flushList();
    flushQuote();
  };

  for (const line of lines) {
    const trimmed = line.trim();
    if (trimmed.startsWith("```")) {
      if (inCodeBlock) {
        flushCode();
        inCodeBlock = false;
      } else {
        flushAll();
        inCodeBlock = true;
        codeLanguage = trimmed.slice(3).trim();
        codeLines = [];
      }
      continue;
    }
    if (inCodeBlock) {
      codeLines.push(line);
      continue;
    }
    if (!trimmed) {
      flushParagraph();
      flushList();
      flushQuote();
      continue;
    }
    const headingMatch = trimmed.match(/^(#{1,5})\s+(.+)$/);
    if (headingMatch) {
      flushAll();
      const level = headingMatch[1].length;
      blocks.push(`<h${level}>${renderMarkdownInline(headingMatch[2].trim())}</h${level}>`);
      continue;
    }
    if (trimmed.startsWith(">")) {
      flushParagraph();
      flushList();
      quoteLines.push(trimmed.replace(/^>\s?/, ""));
      continue;
    }
    if (trimmed.startsWith("- ")) {
      flushParagraph();
      flushQuote();
      listItems.push(trimmed.slice(2).trim());
      continue;
    }
    flushList();
    flushQuote();
    paragraph.push(trimmed);
  }
  if (inCodeBlock) {
    flushCode();
  }
  flushAll();
  return blocks.join("");
}

function renderStatGrid(entries) {
  return `<dl class="stat-grid">${entries
    .map(([label, value]) => {
      const valueHtml = value && typeof value === "object" && typeof value.html === "string"
        ? value.html
        : escapeHtml(value);
      return `<dt>${escapeHtml(label)}</dt><dd>${valueHtml}</dd>`;
    })
    .join("")}</dl>`;
}

function renderSubrouteList(title, entries) {
  if (!entries || entries.length === 0) {
    return "";
  }
  return renderCard(
    title,
    `<ul class="link-list">${entries
      .map(
        (entry) =>
          `<li><a href="${routeHref(entry.route_path)}">${escapeHtml(entry.label)}</a> <span class="meta-line">${entry.instance_count} instances · ${entry.bks_count} BKS</span></li>`,
      )
      .join("")}</ul>`,
  );
}

function renderFacetList(facets) {
  if (!facets || facets.length === 0) {
    return "";
  }
  return renderCard(
    "Filters",
    facets
      .map(
        (facet) =>
          `<div class="mini-card"><h3>${escapeHtml(facet.label)}</h3><div class="chip-row">${facet.options
            .map((option) => `<span class="badge">${escapeHtml(option.label)} · ${option.count}</span>`)
            .join("")}</div></div>`,
      )
      .join(""),
  );
}

const COLLECTION_FILTER_QUERY_KEYS = {
  size_bucket: "size",
  historical_topology_type: "topology",
  historical_tw_type: "tw",
  place_slug: "city",
  objective_function: "objective",
  has_bks: "bks",
};

function collectionFacetValues(item, key) {
  if (key === "size_bucket") return [item.locator?.size_bucket || ""];
  if (key === "historical_topology_type") return [item.historical_topology_type || ""];
  if (key === "historical_tw_type") return [item.historical_tw_type || ""];
  if (key === "place_slug") return [item.place_slug || item.locator?.place_slug || ""];
  if (key === "objective_function") return (item.objective_availability || []).map((entry) => entry.objective_function);
  if (key === "has_bks") return [item.bks_count > 0 ? "yes" : "no"];
  return [];
}

function collectionItemMatchesFacets(item, ignoredKey = null) {
  return Object.keys(COLLECTION_FILTER_QUERY_KEYS).every((key) => {
    if (key === ignoredKey || !state.collectionFilters[key]) return true;
    return collectionFacetValues(item, key).includes(state.collectionFilters[key]);
  });
}

function collectionFacetOptions(payload, facet) {
  const labels = new Map((facet.options || []).map((option) => [option.value, option.label]));
  const counts = new Map();
  payload.items.filter((item) => collectionItemMatchesFacets(item, facet.key)).forEach((item) => {
    new Set(collectionFacetValues(item, facet.key).filter(Boolean)).forEach((value) => {
      counts.set(value, (counts.get(value) || 0) + 1);
    });
  });
  return Array.from(counts, ([value, count]) => ({ value, label: labels.get(value) || value, count }))
    .sort((left, right) => String(left.label).localeCompare(String(right.label), undefined, { numeric: true }));
}

function renderCollectionFilterSelect(payload, facet) {
  const options = collectionFacetOptions(payload, facet);
  const selected = state.collectionFilters[facet.key];
  if (selected && !options.some((option) => option.value === selected)) {
    const sourceOption = (facet.options || []).find((option) => option.value === selected);
    options.push({ value: selected, label: sourceOption?.label || selected, count: 0 });
  }
  return `<label class="field"><span>${escapeHtml(facet.label)}</span><select data-collection-filter="${escapeHtml(facet.key)}"><option value="">All</option>${options.map((option) => `<option value="${escapeHtml(option.value)}"${state.collectionFilters[facet.key] === option.value ? " selected" : ""}>${escapeHtml(option.label)} (${option.count})</option>`).join("")}</select></label>`;
}

function collectionSearchMatches(item) {
  const search = state.collectionFilters.search.trim().toLowerCase();
  if (!search) return true;
  return `${item.display_name || ""} ${item.instance_id || ""} ${item.base_instance || ""}`.toLowerCase().includes(search);
}

function compareCollectionItems(left, right) {
  const sort = state.collectionFilters.sort;
  if (sort === "name") return left.display_name.localeCompare(right.display_name, undefined, { numeric: true });
  if (sort === "cost") return publicCatalogObjectiveNumber(left, "cost") - publicCatalogObjectiveNumber(right, "cost") || left.num_customers - right.num_customers;
  if (sort === "routes") return publicCatalogObjectiveNumber(left, "num_routes") - publicCatalogObjectiveNumber(right, "num_routes") || left.num_customers - right.num_customers;
  return left.num_customers - right.num_customers || left.display_name.localeCompare(right.display_name, undefined, { numeric: true });
}

function filteredCollectionItems(payload) {
  return payload.items
    .filter((item) => collectionItemMatchesFacets(item) && collectionSearchMatches(item))
    .slice()
    .sort(compareCollectionItems);
}

function syncCollectionFilterUrl() {
  const params = new URLSearchParams(window.location.search);
  Object.entries(COLLECTION_FILTER_QUERY_KEYS).forEach(([stateKey, queryKey]) => {
    const value = state.collectionFilters[stateKey];
    if (value) params.set(queryKey, value);
    else params.delete(queryKey);
  });
  if (state.collectionFilters.search) params.set("q", state.collectionFilters.search);
  else params.delete("q");
  if (state.collectionFilters.sort !== "size-name") params.set("sort", state.collectionFilters.sort);
  else params.delete("sort");
  const query = params.toString();
  window.history.replaceState({}, "", `${window.location.pathname}${query ? `?${query}` : ""}`);
}

function renderCollectionFilterCard(payload, matchingCount) {
  return renderCard(
    "Filter instances",
    `<div class="collection-filter-grid">${(payload.filter_facets || []).map((facet) => renderCollectionFilterSelect(payload, facet)).join("")}<label class="field"><span>Search</span><input data-collection-search type="search" value="${escapeHtml(state.collectionFilters.search)}" placeholder="Instance or base name" /></label><label class="field"><span>Sort</span><select data-collection-sort><option value="size-name">Size, name</option><option value="name">Name</option><option value="cost">BKS cost</option><option value="routes">Routes</option></select></label></div><p class="meta-line" data-collection-count>${matchingCount} of ${payload.items.length} instances</p><button class="button-link collection-filter-reset" type="button" data-collection-reset>Reset filters</button>`,
  );
}

function renderProblemCards(problems) {
  return `<div class="problem-grid">${problems
    .map(
      (problem) =>
        `<article class="mini-card"><h3>${escapeHtml(problem.problem_type)}</h3><p>${problem.family_count} families · ${problem.instance_count} instances · ${problem.bks_count} BKS</p><div class="badge-row">${problem.supported_objective_functions
          .map((objective) => badge(objective))
          .join("")}</div><div class="inline-actions"><a class="button-link primary" href="${routeHref(problem.route_path)}">Browse ${escapeHtml(problem.problem_type)}</a></div></article>`,
    )
    .join("")}</div>`;
}

function renderHomeStats(payload) {
  const stats = [
    ["Problem classes", payload.counts.problem_count],
    ["Benchmark families", payload.counts.family_count],
    ["Instances", payload.counts.instance_count],
    ["Validated BKS", payload.counts.bks_count],
  ];
  return `<div class="home-stats" aria-label="Catalog overview">${stats
    .map(
      ([label, value]) =>
        `<div class="home-stat"><strong>${escapeHtml(value)}</strong><span>${escapeHtml(label)}</span></div>`,
    )
    .join("")}</div>`;
}

// Home catalog rows per the merged demo: one row per problem class with the
// family tag chips, the objective column, and a fading rule between rows.
const HOME_PROBLEM_DESCRIPTIONS = {
  CVRP: "Capacitated routing on generated city road graphs",
  VRPTW: "Capacity + time windows",
  TDVRPTW: "Time-dependent travel times + windows, ATF sidecars",
  TDVRP: "Time-dependent, no windows, unpruned search spaces",
};

const HOME_PROBLEM_TAG_TONES = {
  CVRP: "tag-am",
  VRPTW: "tag-cy",
  TDVRPTW: "tag-acc",
  TDVRP: "tag-cor",
};

function renderHomeCatalogRow(problem) {
  const tone = HOME_PROBLEM_TAG_TONES[problem.problem_type] || "tag-acc";
  const description = HOME_PROBLEM_DESCRIPTIONS[problem.problem_type] || `${problem.instance_count} instances`;
  const familyChips = (problem.benchmark_names || [])
    .map((name) => `<span class="badge ${tone}">${escapeHtml(name)}</span>`)
    .join("");
  const objectives = (problem.supported_objective_functions || []).join(" · ");
  return `<a class="catalog-row" href="${routeHref(problem.route_path)}">
    <div class="catalog-row-name">${escapeHtml(problem.problem_type)}</div>
    <div class="catalog-row-desc">${escapeHtml(description)}<div class="catalog-row-tags">${familyChips}</div></div>
    <div class="catalog-row-obj">${escapeHtml(objectives)}</div>
    <div class="catalog-row-arrow" aria-hidden="true">→</div>
  </a>`;
}

function renderHomePreviewFallback(payload) {
  return `<div class="home-preview-showcase">
    <article class="home-preview-card home-preview-fallback">
      <h3>Instance Visuals</h3>
      <p>Open the catalog or workbench to inspect route SVGs and OSM-backed road geometry for published instances.</p>
      <div class="inline-actions">
        <a class="button-link primary" href="${routeHref(payload.workbench_route_path)}">Open Workbench</a>
        <a class="button-link" href="${routeHref(payload.benchmarks_route_path)}">Browse Benchmarks</a>
      </div>
    </article>
  </div>`;
}

function renderHomePreviewCard(sample, previewMarkup) {
  const summary = sample?.instancePayload?.summary || {};
  const entry = sample?.preview?.selectedEntry || null;
  const routePath = sample?.instancePayload?.route_path || "";
  const title = [sample?.instancePayload?.title, summary.benchmark_name].filter(Boolean).join(" · ");
  const proven = Boolean(entry?.optimality?.proven);
  const statusChip = entry
    ? `<span class="badge ${proven ? "tag-gr" : "tag-am"}">${proven ? "proven optimal" : escapeHtml(entry.method || "heuristic")}</span>`
    : "";
  const metaParts = [
    summary.problem_type,
    summary.metric_variant,
    summary.num_customers != null ? `n=${summary.num_customers}` : "",
    entry ? `${entry.objective_function} ${formatCost(entry.cost)}` : "",
  ].filter(Boolean);
  return `<a class="home-preview-card" href="${routeHref(routePath)}">
    <div class="home-preview-kicker">Featured instance</div>
    ${previewMarkup}
    <div class="home-preview-title">${escapeHtml(title)}</div>
    <div class="home-preview-meta">${escapeHtml(metaParts.join(" · "))} ${statusChip}</div>
  </a>`;
}

function renderHomePreviewMarkup(sample) {
  const { instancePayload, preview } = sample;
  const summary = instancePayload.summary || {};
  const straightPreview = renderPreviewSvg(preview.instanceData, preview.selectedBksData, preview.selectedEntry, {
    metricVariant: summary.metric_variant,
    viewerRenderMode: "straight_line",
    roadCacheStatus: "not_applicable",
  });
  const hasRoadPreview = summary.viewer_render_mode === "cached_road" && summary.road_cache_status === "complete" && preview.geometryMeta;
  const roadPreview = hasRoadPreview
    ? renderPreviewSvg(preview.instanceData, preview.selectedBksData, preview.selectedEntry, {
        geometryMeta: preview.geometryMeta,
        metricVariant: summary.metric_variant,
        viewerRenderMode: summary.viewer_render_mode,
        roadCacheStatus: summary.road_cache_status,
      })
    : `<div class="empty-state">No cached road sidecar is available for this sample. Open the workbench to inspect available map layers.</div>`;
  return hasRoadPreview ? roadPreview : straightPreview;
}

function renderHomePreviewDots(activeIndex, count) {
  if (count <= 1) {
    return "";
  }
  return `<div class="home-preview-dots" aria-hidden="true">${Array.from(
    { length: count },
    (_, index) => `<span class="home-preview-dot${index === activeIndex ? " active" : ""}"></span>`,
  ).join("")}</div>`;
}

function renderHomePreviewFrame(sample, activeIndex, count) {
  return `${renderHomePreviewCard(sample, renderHomePreviewMarkup(sample))}${renderHomePreviewDots(activeIndex, count)}`;
}

function renderHomePreviewShowcase(payload, samples) {
  const library = Array.isArray(samples)
    ? samples.filter((sample) => sample?.instancePayload && sample?.preview)
    : [];
  if (library.length === 0) {
    return renderHomePreviewFallback(payload);
  }

  return `<div class="home-preview-showcase" data-home-preview-showcase>
    ${renderHomePreviewFrame(library[0], 0, library.length)}
  </div>`;
}

function renderHomePreviewSkeleton() {
  return `<div class="home-preview-showcase home-preview-loading" data-home-preview-showcase aria-busy="true">
    <article class="home-preview-card home-preview-skeleton" aria-hidden="true">
      <div class="home-preview-skeleton-frame">
        <div class="home-preview-skeleton-spinner"></div>
      </div>
    </article>
    <span class="visually-hidden">Loading instance preview…</span>
  </div>`;
}

function fillHomePreviewShowcase(payload, samples) {
  const showcase = state.stage?.querySelector("[data-home-preview-showcase]");
  if (!showcase) {
    return;
  }
  const library = Array.isArray(samples)
    ? samples.filter((sample) => sample?.instancePayload && sample?.preview)
    : [];
  showcase.classList.remove("home-preview-loading");
  showcase.removeAttribute("aria-busy");
  if (library.length === 0) {
    showcase.outerHTML = renderHomePreviewFallback(payload);
    return;
  }
  showcase.dataset.activeIndex = "0";
  showcase.innerHTML = renderHomePreviewFrame(library[0], 0, library.length);
}

function homePreviewSampleKey(sample) {
  return [
    normalizeRoute(sample?.instancePayload?.route_path || ""),
    sample?.preview?.selectedEntry?.objective_function || "",
  ].join("::");
}

// Runtime fallback equivalent of the server-generated Poryos2026 preview mix.
const HOME_PREVIEW_SEEDS = [
  { problemType: "CVRP", benchmarkName: "Poryos2026", metricVariant: "shortest", placeSlug: "hong_kong", objectiveFunction: "MonoCost" },
  { problemType: "VRPTW", benchmarkName: "Poryos2026", metricVariant: "euclidean", placeSlug: "lyon", objectiveFunction: "MonoCost" },
  { problemType: "TDVRP", benchmarkName: "Poryos2026", metricVariant: "fastest", placeSlug: "paris", objectiveFunction: "Duration" },
  { problemType: "TDVRPTW", benchmarkName: "Poryos2026", metricVariant: "fastest", placeSlug: "san_francisco", objectiveFunction: "Duration" },
];

async function loadHomePreviewSample(seed) {
  const selection = await buildWorkbenchBenchmarkSelection(seed);
  if (!selection.instancePayload) {
    return null;
  }
  const preview = await loadWorkbenchInstancePreview(selection.instancePayload, seed.objectiveFunction || null);
  if (!Array.isArray(preview?.selectedBksData?.routes) || preview.selectedBksData.routes.length === 0) {
    return null;
  }
  return { selection, instancePayload: selection.instancePayload, preview };
}

async function loadFirstHomePreviewSample(seeds) {
  for (const seed of seeds) {
    try {
      const sample = await loadHomePreviewSample(seed);
      if (sample) {
        return { sample, seedIndex: seeds.indexOf(seed) };
      }
    } catch (error) {
      console.warn("Unable to load homepage preview sample", error);
    }
  }
  return null;
}

async function loadRemainingHomePreviewSamples(seeds, skipIndex, seenKeys) {
  const tasks = seeds.map((seed, index) => {
    if (index === skipIndex) {
      return null;
    }
    return loadHomePreviewSample(seed).catch((error) => {
      console.warn("Unable to load homepage preview sample", error);
      return null;
    });
  });
  const results = await Promise.all(tasks.filter(Boolean));
  const samples = [];
  for (const sample of results) {
    if (!sample) {
      continue;
    }
    const key = homePreviewSampleKey(sample);
    if (seenKeys.has(key)) {
      continue;
    }
    seenKeys.add(key);
    samples.push(sample);
  }
  return samples;
}

function activateHomePreviewLibrary(samples) {
  clearHomePreviewRotation();
  const library = Array.isArray(samples)
    ? samples.filter((sample) => sample?.instancePayload && sample?.preview)
    : [];
  if (library.length <= 1) {
    return;
  }

  const showcase = state.stage?.querySelector("[data-home-preview-showcase]");
  if (!showcase) {
    return;
  }

  let activeIndex = 0;
  homePreviewRotationTimer = window.setInterval(() => {
    if (document.hidden || !showcase.isConnected) {
      return;
    }

    const nextIndex = (activeIndex + 1) % library.length;
    showcase.classList.add("home-preview-showcase-swapping");
    window.setTimeout(() => {
      if (!showcase.isConnected) {
        return;
      }
      activeIndex = nextIndex;
      showcase.dataset.activeIndex = String(activeIndex);
      showcase.innerHTML = renderHomePreviewFrame(library[activeIndex], activeIndex, library.length);
      window.requestAnimationFrame(() => {
        showcase.classList.remove("home-preview-showcase-swapping");
      });
    }, 180);
  }, HOME_PREVIEW_ROTATION_MS);
}

function renderFamilyCards(families) {
  return `<div class="family-grid">${families
    .map(
      (family) => {
        const contextAction = family.context_route_path
          ? `<a class="button-link" href="${routeHref(family.context_route_path)}">Description</a>`
          : "";
        return `<article class="mini-card"><h3>${escapeHtml(family.benchmark_name)}</h3><p>${family.instance_count} instances · ${family.bks_count} BKS</p><div class="badge-row">${family.metric_variants.map((variant) => badge(variant)).join("")}${family.supported_objective_functions
          .map((objective) => badge(objective, true))
          .join("")}</div><div class="inline-actions"><a class="button-link primary" href="${routeHref(family.route_path)}">Open family</a>${contextAction}</div></article>`;
      },
    )
    .join("")}</div>`;
}

function renderInstanceRows(items, options = {}) {
  if (!items || items.length === 0) {
    return `<div class="empty-state">No instances are present in this slice.</div>`;
  }
  const inspector = options.inspector === true;
  const actionsHeader = inspector ? "" : "<th>Actions</th>";
  return `<div class="table-wrap"><table><thead><tr><th>Instance</th><th>Size</th><th>Context</th><th>Objectives</th>${actionsHeader}</tr></thead><tbody>${items
    .map((item) => {
      const contextParts = [item.place_slug, item.historical_topology_type, item.historical_tw_type && `TW${item.historical_tw_type}`].filter(Boolean);
      const objectiveBadges = item.objective_availability
        .map((entry) => {
          const formatted = formatObjectiveBadge(entry);
          return bksLinkChip(formatted, entry.artifact_path, entry.objective_function, entry.optimality_proven);
        })
        .join("");
      const objectiveCell = objectiveBadges
        ? `<div class="bks-link-chip-row">${objectiveBadges}</div>`
        : '<span class="meta-line">No BKS</span>';
      const rowTitle = `${item.instance_id}\n${item.artifact_vrp_json_path}`;
      const vrpHref = artifactHref(item.artifact_vrp_json_path);
      const nameCell = `<a class="vrp-link" href="${vrpHref}" target="_blank" rel="noopener" title="Open ${escapeHtml(item.display_name)}.vrp.json">${escapeHtml(item.display_name)}</a>`;
      const baseCells = `<td class="table-cell-mono">${nameCell}</td><td class="table-cell-num">${escapeHtml(item.num_customers)}</td><td>${escapeHtml(contextParts.join(" · ")) || '<span class="meta-line">—</span>'}</td><td>${objectiveCell}</td>`;
      if (inspector) {
        return `<tr class="inspector-row" tabindex="0" data-inspect-route="${escapeHtml(item.route_path)}" title="${escapeHtml(rowTitle)}">${baseCells}</tr>`;
      }
      const workbenchLink = supportsWorkbenchInstance(item)
        ? `<a class="mini-link" href="${routeHref('/workbench/')}?instance=${encodeURIComponent(item.route_path)}">Workbench</a>`
        : "";
      return `<tr title="${escapeHtml(rowTitle)}">${baseCells}<td><div class="inline-actions"><a class="mini-link" href="${routeHref(item.route_path)}">Open</a>${workbenchLink}</div></td></tr>`;
    })
    .join("")}</tbody></table></div>`;
}

const VARIANT_SORT_ORDER = ["euclidean", "fastest", "shortest"];

// A family whose base instances each appear under several arc-cost metrics is
// one instance with N variants, not N unrelated rows, and reads far better
// grouped. Decided from the items themselves rather than from a family name:
// Poryos2026 was the only such family when this table was written, and
// hardcoding it meant the next one (Mamut2026) silently fell back to a flat
// list where the three variants of a base were indistinguishable.
function hasMetricVariantGroups(items) {
  const variantsByBase = new Map();
  for (const item of items || []) {
    const variant = item.locator?.metric_variant;
    if (!variant) continue;
    const key = instanceGroupKey(item);
    const variants = variantsByBase.get(key) ?? new Set();
    variants.add(variant);
    if (variants.size > 1) return true;
    variantsByBase.set(key, variants);
  }
  return false;
}

function variantSortKey(variant) {
  const idx = VARIANT_SORT_ORDER.indexOf(variant);
  return idx === -1 ? VARIANT_SORT_ORDER.length : idx;
}

function instanceGroupKey(item) {
  return [item.place_slug ?? "", item.num_customers, item.display_name].join("␟");
}

function renderInstanceGroups(items, preserveOrder = false, options = {}) {
  const inspector = options.inspector === true;
  if (!items || items.length === 0) {
    return `<div class="empty-state">No instances are present in this slice.</div>`;
  }
  const groups = new Map();
  for (const item of items) {
    const key = instanceGroupKey(item);
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key).push(item);
  }
  const orderedKeys = [...groups.keys()];
  if (!preserveOrder) orderedKeys.sort((a, b) => {
    const ga = groups.get(a)[0];
    const gb = groups.get(b)[0];
    return (
      ga.num_customers - gb.num_customers
      || String(ga.place_slug ?? "").localeCompare(String(gb.place_slug ?? ""))
      || ga.display_name.localeCompare(gb.display_name)
    );
  });
  const tbodies = orderedKeys.map((key) => {
    const groupItems = groups.get(key).slice().sort((a, b) =>
      variantSortKey(a.locator.metric_variant) - variantSortKey(b.locator.metric_variant)
    );
    const head = groupItems[0];
    const headerCell = `<td class="group-header-cell" colspan="4"><span class="group-name">${escapeHtml(head.display_name)}</span><span class="meta-line"> · ${escapeHtml(head.place_slug ?? "")} · n=${escapeHtml(head.num_customers)}</span></td>`;
    const subRows = groupItems.map((item) => {
      const objectiveBadges = item.objective_availability
        .map((entry) => {
          const formatted = formatObjectiveBadge(entry);
          return bksLinkChip(formatted, entry.artifact_path, entry.objective_function, entry.optimality_proven);
        })
        .join("");
      const objectiveCell = objectiveBadges
        ? `<div class="bks-link-chip-row">${objectiveBadges}</div>`
        : '<span class="meta-line">No BKS</span>';
      const rowTitle = `${item.instance_id}\n${item.artifact_vrp_json_path}`;
      const variantLabel = item.locator.metric_variant ?? "";
      const vrpHref = artifactHref(item.artifact_vrp_json_path);
      const variantCell = variantLabel
        ? `<a class="vrp-link" href="${vrpHref}" target="_blank" rel="noopener" title="Open ${escapeHtml(item.display_name)} (${escapeHtml(variantLabel)}) .vrp.json">${escapeHtml(variantLabel)}</a>`
        : "";
      const baseCells = `<td class="indent" aria-hidden="true">↳</td><td class="table-cell-mono">${variantCell}</td><td>${objectiveCell}</td>`;
      if (inspector) {
        return `<tr class="group-sub inspector-row" tabindex="0" data-inspect-route="${escapeHtml(item.route_path)}" title="${escapeHtml(rowTitle)}">${baseCells}</tr>`;
      }
      const workbenchLink = supportsWorkbenchInstance(item)
        ? `<a class="mini-link" href="${routeHref('/workbench/')}?instance=${encodeURIComponent(item.route_path)}">Workbench</a>`
        : "";
      return `<tr class="group-sub" title="${escapeHtml(rowTitle)}">${baseCells}<td><div class="inline-actions"><a class="mini-link" href="${routeHref(item.route_path)}">Open</a>${workbenchLink}</div></td></tr>`;
    }).join("");
    return `<tbody class="group"><tr class="group-header">${headerCell}</tr>${subRows}</tbody>`;
  });
  const actionsHeader = inspector ? "" : "<th>Actions</th>";
  return `<div class="table-wrap"><table class="grouped-instance-table"><thead><tr><th></th><th>Variant</th><th>Objectives</th>${actionsHeader}</tr></thead>${tbodies.join("")}</table></div>`;
}

function renderHome(payload) {
  setPage(payload.title, payload.subtitle, [], "home");
  if (state.aside) {
    state.aside.innerHTML = "";
  }
  const catalogRows = payload.problems
    .map((problem) => renderHomeCatalogRow(problem))
    .join('<div class="fading-rule"></div>');
  state.stage.innerHTML = `
    <section class="home-page">
      <section class="home-hero">
        <div class="home-hero-copy">
          <div class="home-kicker">ANR MAMUT · open benchmark library</div>
          <h1>Vehicle routing benchmarks, <span class="hero-grad">curated with provenance.</span></h1>
          <p class="home-lede">${escapeHtml(payload.hero_summary)}</p>
          <div class="home-cta-row">
            <a class="button-link primary" href="${routeHref(payload.benchmarks_route_path)}">Browse the catalog</a>
            <a class="button-link" href="${routeHref(payload.workbench_route_path)}">Open the workbench</a>
          </div>
          ${renderHomeStats(payload)}
        </div>
        ${renderHomePreviewSkeleton()}
      </section>
      <section class="home-catalog">
        <h2 class="home-catalog-heading">The catalog</h2>
        ${catalogRows}
        <div class="home-foot">
          <span>MAMUT project · ANR-22-CE22-0016</span>
          <span>MIT + family-specific data licences</span>
          <span>Snapshot ${escapeHtml(payload.snapshot.snapshot_id)} · published ${escapeHtml(payload.snapshot.published_at)}</span>
          <span class="home-foot-right"><a href="https://github.com/ANR-MAMUT/MAMUT-routing" target="_blank" rel="noopener">GitHub</a><a href="${routeHref(payload.history_route_path)}">History</a></span>
        </div>
      </section>
    </section>`;
  setStatus(`Loaded snapshot ${payload.snapshot.snapshot_id}`);
  hydrateHomePreviewShowcase(payload);
}

async function loadHomePreviewBundle(payload) {
  if (!payload?.home_preview_bundle_href) {
    return null;
  }
  try {
    const bundle = await fetchJsonMemo(artifactHref(payload.home_preview_bundle_href));
    if (!Array.isArray(bundle?.samples) || bundle.samples.length === 0) {
      return null;
    }
    return bundle.samples.map((entry) => ({
      instancePayload: entry.instance_payload,
      preview: {
        instanceData: entry.instance_data,
        // geometryMeta is excluded from the bundle (3-11 MB per instance) and
        // lazy-loaded after first paint via loadHomePreviewSampleGeometry().
        geometryMeta: null,
        selectedEntry: entry.selected_entry,
        selectedBksData: entry.selected_bks_data,
        selectedIndex: 0,
      },
    }));
  } catch (error) {
    console.warn("Unable to load home preview bundle", error);
    return null;
  }
}

function loadHomePreviewSampleGeometry(sample, onLoaded) {
  const summary = sample?.instancePayload?.summary;
  const artifactLinks = sample?.instancePayload?.artifact_links;
  if (!summary || !geometryMetaSourcePath(artifactLinks)) {
    return;
  }
  if (summary.viewer_render_mode !== "cached_road" || summary.road_cache_status !== "complete") {
    return;
  }
  if (sample.preview.geometryMeta) {
    return;
  }
  Promise.all([
    fetchGeometryMetaMemo(artifactLinks),
    routeGeometryMetaForEntry(sample.preview.selectedEntry),
  ])
    .then(([data, routeGeometryMeta]) => {
      sample.preview.geometryMeta = mergeGeometryMeta(data, routeGeometryMeta);
      onLoaded?.(sample);
    })
    .catch((error) => console.warn("Unable to load homepage geometry sidecar", error));
}

function refreshHomePreviewActiveFrame(samples, sample) {
  const showcase = state.stage?.querySelector("[data-home-preview-showcase]");
  if (!showcase) {
    return;
  }
  const activeIndex = Number(showcase.dataset.activeIndex || 0);
  if (samples[activeIndex] !== sample) {
    return;
  }
  showcase.innerHTML = renderHomePreviewFrame(sample, activeIndex, samples.length);
}

async function hydrateHomePreviewShowcase(payload) {
  const bundleSamples = await loadHomePreviewBundle(payload);
  if (bundleSamples) {
    fillHomePreviewShowcase(payload, bundleSamples);
    activateHomePreviewLibrary(bundleSamples);
    bundleSamples.forEach((sample) =>
      loadHomePreviewSampleGeometry(sample, (updated) => refreshHomePreviewActiveFrame(bundleSamples, updated)),
    );
    return;
  }

  // Fallback: the bundle is missing (e.g. older publish, dev environment).
  // Walk seeds at runtime, same flow as before the bundle was introduced.
  // TODO: remove this fallback (and the loadHomePreview*/buildWorkbenchBenchmarkSelection helpers it relies on) once we're confident every publish produces a bundle.
  const seeds = HOME_PREVIEW_SEEDS;
  const firstResult = await loadFirstHomePreviewSample(seeds);
  if (!firstResult) {
    fillHomePreviewShowcase(payload, []);
    return;
  }
  const samples = [firstResult.sample];
  const seenKeys = new Set([homePreviewSampleKey(firstResult.sample)]);
  fillHomePreviewShowcase(payload, samples);

  const rest = await loadRemainingHomePreviewSamples(seeds, firstResult.seedIndex, seenKeys);
  if (rest.length === 0) {
    return;
  }
  samples.push(...rest);
  const showcase = state.stage?.querySelector("[data-home-preview-showcase]");
  if (showcase) {
    showcase.dataset.activeIndex = "0";
    showcase.innerHTML = renderHomePreviewFrame(samples[0], 0, samples.length);
  }
  activateHomePreviewLibrary(samples);
}

function publicCatalogValue(item, key) {
  const locator = item.locator || {};
  if (key === "problem") return locator.problem_type || "";
  if (key === "family") return locator.benchmark_name || "";
  if (key === "metric") return locator.metric_variant || "";
  if (key === "city") return locator.place_slug || item.place_slug || "";
  if (key === "size") return String(item.num_customers ?? "");
  if (key === "method") return item.sampling_method || "";
  if (key === "scenario") {
    if (item.tw_set) return `TW: ${item.tw_set}`;
    if (item.traffic_model || item.traffic_intensity) return `Traffic: ${item.traffic_model || "?"} / ${item.traffic_intensity || "?"}`;
  }
  if (key === "geometry") return catalogGeometryValue(item);
  return "";
}

function catalogGeometryValue(item) {
  return item?.viewer_render_mode === "cached_road" || item?.road_cache_status === "complete" ? "road" : "straight";
}

const PUBLIC_CATALOG_FILTER_ORDER = ["problem", "family", "metric", "city", "size", "method", "scenario", "geometry"];
const PUBLIC_PROBLEM_ORDER = ["CVRP", "VRPTW", "TDVRPTW", "TDVRP"];
const PUBLIC_CATALOG_OPTION_LABELS = {
  geometry: { road: "Road geometry", straight: "Straight-line" },
};

function publicCatalogOptions(items, key) {
  const keyIndex = PUBLIC_CATALOG_FILTER_ORDER.indexOf(key);
  const eligible = items.filter((item) => PUBLIC_CATALOG_FILTER_ORDER.slice(0, keyIndex).every((prior) => {
    const selected = state.catalogFilters[prior];
    return !selected || publicCatalogValue(item, prior) === selected;
  }));
  const counts = new Map();
  eligible.forEach((item) => {
    const value = publicCatalogValue(item, key);
    if (value) counts.set(value, (counts.get(value) || 0) + 1);
  });
  return Array.from(counts, ([value, count]) => ({ value, count }))
    .sort((left, right) => key === "problem"
      ? PUBLIC_PROBLEM_ORDER.indexOf(left.value) - PUBLIC_PROBLEM_ORDER.indexOf(right.value)
      : String(left.value).localeCompare(String(right.value), undefined, { numeric: true }));
}

function publicCatalogSelect(key, label, items) {
  if (key === "size" && !state.catalogFilters.family) {
    state.catalogFilters.size = "";
    return `<label class="field"><span>${escapeHtml(label)}</span><select data-public-filter="${key}" disabled><option value="">Choose a family first</option></select></label>`;
  }
  const options = publicCatalogOptions(items, key);
  if (!options.some((option) => option.value === state.catalogFilters[key])) state.catalogFilters[key] = "";
  return `<label class="field"><span>${escapeHtml(label)}</span><select data-public-filter="${key}"><option value="">All</option>${options.map(({ value, count }) => `<option value="${escapeHtml(value)}"${state.catalogFilters[key] === value ? " selected" : ""}>${escapeHtml(PUBLIC_CATALOG_OPTION_LABELS[key]?.[value] || value)} (${count})</option>`).join("")}</select></label>`;
}

function catalogObjectiveNumber(item, field) {
  const values = (item.objective_availability || []).map((entry) => Number(entry?.[field])).filter(Number.isFinite);
  return values.length > 0 ? Math.min(...values) : null;
}

function catalogCostSortAvailable(items) {
  const objectives = new Set(
    items.flatMap((item) => (item.objective_availability || []).map((entry) => entry.objective_function).filter(Boolean)),
  );
  return objectives.size === 1;
}

function catalogSortOptions(items) {
  const costAvailable = catalogCostSortAvailable(items);
  return CATALOG_SORT_OPTIONS.map((option) => ({
    ...option,
    disabled: option.requiresSingleObjective === true && !costAvailable,
    label: option.value === "cost" && !costAvailable ? "BKS cost (filter to one objective)" : option.label,
  }));
}

function compareCatalogText(left, right) {
  return String(left || "").localeCompare(String(right || ""), undefined, { numeric: true, sensitivity: "base" });
}

function compareCatalogNumber(left, right, direction) {
  const leftNumber = Number(left);
  const rightNumber = Number(right);
  const leftPresent = left !== null && left !== undefined && Number.isFinite(leftNumber);
  const rightPresent = right !== null && right !== undefined && Number.isFinite(rightNumber);
  if (leftPresent !== rightPresent) return leftPresent ? -1 : 1;
  if (!leftPresent) return 0;
  return (leftNumber - rightNumber) * direction;
}

function compareCatalogOrder(left, right) {
  const leftProblem = publicCatalogValue(left, "problem");
  const rightProblem = publicCatalogValue(right, "problem");
  const leftProblemIndex = PUBLIC_PROBLEM_ORDER.includes(leftProblem) ? PUBLIC_PROBLEM_ORDER.indexOf(leftProblem) : PUBLIC_PROBLEM_ORDER.length;
  const rightProblemIndex = PUBLIC_PROBLEM_ORDER.includes(rightProblem) ? PUBLIC_PROBLEM_ORDER.indexOf(rightProblem) : PUBLIC_PROBLEM_ORDER.length;
  return leftProblemIndex - rightProblemIndex
    || compareCatalogText(leftProblem, rightProblem)
    || compareCatalogText(publicCatalogValue(left, "family"), publicCatalogValue(right, "family"))
    || compareCatalogText(publicCatalogValue(left, "city"), publicCatalogValue(right, "city"))
    || compareCatalogNumber(left.num_customers, right.num_customers, 1)
    || compareCatalogText(left.display_name, right.display_name);
}

function compareCatalogItems(left, right, sortValue = "catalog", directionValue = "asc") {
  const sort = normalizeCatalogSort(sortValue);
  const direction = normalizeSortDirection(directionValue) === "desc" ? -1 : 1;
  if (sort === "name") return compareCatalogText(left.display_name, right.display_name) * direction || compareCatalogOrder(left, right);
  if (sort === "size") return compareCatalogNumber(left.num_customers, right.num_customers, direction) || compareCatalogOrder(left, right);
  if (sort === "cost") return compareCatalogNumber(catalogObjectiveNumber(left, "cost"), catalogObjectiveNumber(right, "cost"), direction) || compareCatalogOrder(left, right);
  if (sort === "routes") return compareCatalogNumber(catalogObjectiveNumber(left, "num_routes"), catalogObjectiveNumber(right, "num_routes"), direction) || compareCatalogOrder(left, right);
  return compareCatalogOrder(left, right) * direction;
}

function syncPublicCatalogUrl() {
  const params = new URLSearchParams(window.location.search);
  const queryKeys = { problem: "problem", family: "family", metric: "metric", city: "city", size: "size", method: "method", scenario: "scenario", geometry: "geometry", search: "q", sort: "sort", direction: "dir" };
  Object.entries(queryKeys).forEach(([stateKey, queryKey]) => {
    const value = state.catalogFilters[stateKey];
    const isDefault = (stateKey === "sort" && value === "catalog") || (stateKey === "direction" && value === "asc");
    if (value && !isDefault) params.set(queryKey, value);
    else params.delete(queryKey);
  });
  const query = params.toString();
  window.history.replaceState({}, "", `${window.location.pathname}${query ? `?${query}` : ""}`);
}

function renderPublicCatalogExplorer(items) {
  const search = state.catalogFilters.search.trim().toLowerCase();
  const filtered = items.filter((item) => {
    if (!PUBLIC_CATALOG_FILTER_ORDER.every((key) => !state.catalogFilters[key] || publicCatalogValue(item, key) === state.catalogFilters[key])) return false;
    if (search && !`${item.display_name || ""} ${item.base_instance || ""} ${item.instance_id || ""}`.toLowerCase().includes(search)) return false;
    return true;
  });
  if (state.catalogFilters.sort === "cost" && !catalogCostSortAvailable(filtered)) {
    state.catalogFilters.sort = "catalog";
    syncPublicCatalogUrl();
  }
  filtered.sort((left, right) => compareCatalogItems(left, right, state.catalogFilters.sort, state.catalogFilters.direction));
  const shown = filtered.slice(0, 100);
  const sortOptions = catalogSortOptions(filtered)
    .map((option) => `<option value="${option.value}"${option.value === state.catalogFilters.sort ? " selected" : ""}${option.disabled ? " disabled" : ""}>${escapeHtml(option.label)}</option>`)
    .join("");
  const descending = state.catalogFilters.direction === "desc";
  const directionLabel = descending ? "Descending" : "Ascending";
  const controls = `<section class="card catalog-filter-card">
    <h2>Filter instances</h2>
    <div class="catalog-filter-grid">
      ${publicCatalogSelect("problem", "Problem", items)}
      ${publicCatalogSelect("family", "Family", items)}
      ${publicCatalogSelect("metric", "Metric", items)}
      ${publicCatalogSelect("city", "City", items)}
      ${publicCatalogSelect("size", "Size", items)}
      ${publicCatalogSelect("method", "Method", items)}
      ${publicCatalogSelect("scenario", "TW / traffic", items)}
      ${publicCatalogSelect("geometry", "Geometry", items)}
      <label class="field"><span>Search</span><input data-public-search type="search" value="${escapeHtml(state.catalogFilters.search)}" placeholder="Instance or base name" /></label>
    </div>
    <div class="catalog-filter-footer">
      <p class="meta-line">${filtered.length} matching instances${filtered.length > shown.length ? ` · showing the first ${shown.length}` : ""}</p>
      <div class="catalog-sort-controls">
        <label class="field catalog-sort-field"><span>Sort by</span><select data-public-sort>${sortOptions}</select></label>
        <button type="button" class="sort-direction-button" data-public-sort-direction aria-label="Sort direction: ${directionLabel.toLowerCase()}. Activate for ${descending ? "ascending" : "descending"}." title="${directionLabel}"><span aria-hidden="true">${descending ? "↓" : "↑"}</span></button>
      </div>
    </div>
  </section>`;
  const problemNames = items.length
    ? Array.from(new Set(items.map((item) => publicCatalogValue(item, "problem"))))
      .sort((left, right) => PUBLIC_PROBLEM_ORDER.indexOf(left) - PUBLIC_PROBLEM_ORDER.indexOf(right))
    : [];
  const problemCards = problemNames.map((problem) => ({ problem_type: problem, route_path: `/benchmarks/${problem.toLowerCase()}/`, family_count: new Set(items.filter((item) => publicCatalogValue(item, "problem") === problem).map((item) => publicCatalogValue(item, "family"))).size, instance_count: items.filter((item) => publicCatalogValue(item, "problem") === problem).length, bks_count: items.filter((item) => publicCatalogValue(item, "problem") === problem).reduce((total, item) => total + item.bks_count, 0), supported_objective_functions: [] }));
  state.stage.innerHTML = `${renderProblemCards(problemCards)}${controls}<section class="catalog-results">${renderInstanceRows(shown)}</section>`;
  state.stage.querySelectorAll("[data-public-filter]").forEach((select) => select.addEventListener("change", () => {
    const key = select.dataset.publicFilter;
    state.catalogFilters[key] = select.value;
    const keyIndex = PUBLIC_CATALOG_FILTER_ORDER.indexOf(key);
    PUBLIC_CATALOG_FILTER_ORDER.slice(keyIndex + 1).forEach((later) => { state.catalogFilters[later] = ""; });
    syncPublicCatalogUrl();
    renderPublicCatalogExplorer(items);
  }));
  state.stage.querySelector("[data-public-search]").addEventListener("change", (event) => { state.catalogFilters.search = event.target.value; syncPublicCatalogUrl(); renderPublicCatalogExplorer(items); });
  state.stage.querySelector("[data-public-sort]").addEventListener("change", (event) => { state.catalogFilters.sort = event.target.value; syncPublicCatalogUrl(); renderPublicCatalogExplorer(items); });
  state.stage.querySelector("[data-public-sort-direction]").addEventListener("click", () => {
    state.catalogFilters.direction = state.catalogFilters.direction === "asc" ? "desc" : "asc";
    syncPublicCatalogUrl();
    renderPublicCatalogExplorer(items);
  });
  syncPublicCatalogUrl();
  setStatus(`Loaded ${filtered.length} matching instances`);
}

function renderBenchmarksIndex(payload) {
  const breadcrumbs = payload.breadcrumbs || [{ label: "benchmarks", route_path: "/benchmarks/" }];
  setPage("Benchmarks", "Choose a problem class first, then narrow to a benchmark family or generated variant.", breadcrumbs, "catalog");
  state.aside.innerHTML = [
    renderCard(
      "Browse Benchmarks",
      `<p>This static publication separates the problem classes (CVRP, VRPTW, and the time-dependent TDVRPTW/TDVRP) at the top level, then preserves family and variant structure inside each class.</p>${renderStatGrid([
        ["Snapshot", payload.snapshot.snapshot_id],
        ["Published", payload.snapshot.published_at],
        ["Commit", payload.snapshot.source_commit],
      ])}`,
    ),
  ].join("");
  if (Array.isArray(payload.items) && payload.items.length > 0) {
    renderPublicCatalogExplorer(payload.items);
  } else {
    state.stage.innerHTML = renderProblemCards(payload.problems);
    setStatus(`Loaded ${payload.problems.length} problem classes`);
  }
}

function renderProblemIndex(payload) {
  setPage(payload.title, `Browse benchmark families available under ${payload.problem_type}.`, payload.breadcrumbs, "catalog");
  state.aside.innerHTML = renderCard(
    "Problem Summary",
    `${renderStatGrid([
      ["Instances", payload.summary.instance_count],
      ["BKS", payload.summary.bks_count],
      ["Size buckets", payload.summary.size_bucket_count],
      ["Places", payload.summary.place_count],
    ])}<div class="badge-row">${payload.summary.supported_objective_functions.map((objective) => badge(objective)).join("")}</div>`,
  );
  state.stage.innerHTML = renderFamilyCards(payload.families);
  setStatus(`Loaded ${payload.families.length} families`);
}

// ── A7 step 2: inspector pane on instance-list pages ──────────────────────
// Selecting a row fills the right-side pane (mini route preview, key facts,
// BKS/provenance, actions); Enter or a direct link still opens the record.
// The pane exists only on catalog index pages whose rows are instances;
// higher catalog levels and every route/URL stay untouched.

let inspectorRoute = null;
let inspectorLoadToken = 0;

function inspectorStatusChip(item) {
  const availability = item.objective_availability || [];
  if (availability.some((entry) => entry.optimality_proven)) {
    return '<span class="badge tag-gr">proven optimal</span>';
  }
  return availability.length ? '<span class="badge tag-am">heuristic</span>' : "";
}

function renderInspectorPaneShell(item) {
  if (!item) {
    return `<div class="inspector-kicker">Inspector</div><div class="empty-state">Select an instance row to inspect it.</div>`;
  }
  const problemType = item.locator?.problem_type || "";
  const problemChip = problemType ? `<span class="badge">${escapeHtml(problemType)}</span>` : "";
  const workbenchAction = supportsWorkbenchInstance(item)
    ? `<a class="button-link" href="${routeHref('/workbench/')}?instance=${encodeURIComponent(item.route_path)}">Open in workbench →</a>`
    : "";
  return `
    <div class="inspector-kicker">Inspector</div>
    <div class="inspector-title-row"><span class="inspector-name">${escapeHtml(item.display_name)}</span>${problemChip}${inspectorStatusChip(item)}</div>
    <div class="inspector-preview" data-inspector-preview><div class="inspector-preview-skeleton" aria-hidden="true"></div></div>
    <div data-inspector-details><div class="meta-line">Loading instance details…</div></div>
    <div class="inspector-actions">
      <a class="button-link primary" href="${routeHref(item.route_path)}">Open full record →</a>
      ${workbenchAction}
    </div>`;
}

function renderInspectorDetails(item, payload, preview) {
  const summary = payload.summary || {};
  const entries = payload.bks_entries || [];
  const entry = preview?.selectedEntry || null;
  const objectiveChips = entries.length > 1
    ? `<div class="selector-row">${entries
        .map((candidate) => `<button type="button" class="bks-chip${entry && candidate.objective_function === entry.objective_function ? " active" : ""}" data-inspector-objective="${escapeHtml(candidate.objective_function)}">${escapeHtml(candidate.objective_function)}</button>`)
        .join("")}</div>`
    : "";
  const stats = [
    [entry ? `BKS · ${entry.objective_function}` : "BKS", entry ? { html: `<strong class="inspector-cost">${escapeHtml(formatCost(entry.cost))}</strong>` } : "none"],
    ["Routes", entry?.num_routes ?? "n/a"],
    ["Customers", summary.num_customers ?? item.num_customers],
    ["Capacity", summary.vehicle_capacity ?? "n/a"],
  ];
  const statCells = stats
    .map(([label, value]) => `<div><span>${escapeHtml(label)}</span>${typeof value === "object" && value?.html ? value.html : `<strong>${escapeHtml(value)}</strong>`}</div>`)
    .join("");
  // Compact by design: the proven-optimal chip in the title row is enough
  // here; the full proof detail (certificate, prover, campaign) lives on the
  // record page's BKS card. Only the short attribution rows stay.
  const provenance = [];
  if (entry?.method) provenance.push(["Method", entry.method]);
  if (entry?.authors) provenance.push(["Authors", entry.authors]);
  if (entry?.optimality?.proven && entry.optimality.date) provenance.push(["Proven", entry.optimality.date]);
  const provenanceGrid = provenance.length
    ? `<div class="inspector-prov">${provenance.map(([key, value]) => `<span>${escapeHtml(key)}</span><span>${escapeHtml(value)}</span>`).join("")}</div>`
    : "";
  const downloads = [
    `<a class="download-chip" href="${artifactHref(item.artifact_vrp_json_path)}" target="_blank" rel="noopener">.vrp.json ↓</a>`,
    entry?.artifact_path ? `<a class="download-chip" href="${artifactHref(entry.artifact_path)}" target="_blank" rel="noopener">.bks.${escapeHtml(entry.objective_function)}.json ↓</a>` : "",
  ].join("");
  return `${objectiveChips}<div class="inspector-stats">${statCells}</div>${provenanceGrid}<div class="inline-actions">${downloads}</div>`;
}

async function hydrateInspectorPane(item, preferredObjective = null) {
  const token = ++inspectorLoadToken;
  const pane = state.stage.querySelector("[data-inspector-pane]");
  if (!pane || !item) {
    return;
  }
  try {
    const payload = await fetchWorkbenchPayloadForRoute(item.route_path);
    const preview = await loadWorkbenchInstancePreview(payload, preferredObjective);
    if (token !== inspectorLoadToken || inspectorRoute !== item.route_path) {
      return;
    }
    const routeGeometryMeta = await routeGeometryMetaForEntry(preview?.selectedEntry);
    if (token !== inspectorLoadToken || inspectorRoute !== item.route_path) {
      return;
    }
    const previewBox = pane.querySelector("[data-inspector-preview]");
    if (previewBox && preview?.instanceData) {
      previewBox.innerHTML = renderPreviewSvg(preview.instanceData, preview.selectedBksData, preview.selectedEntry, {
        geometryMeta: mergeGeometryMeta(preview.geometryMeta, routeGeometryMeta),
        metricVariant: payload.summary?.metric_variant,
        viewerRenderMode: routeGeometryMeta ? "cached_road" : payload.summary?.viewer_render_mode,
        roadCacheStatus: routeGeometryMeta ? "complete" : payload.summary?.road_cache_status,
      });
    }
    const details = pane.querySelector("[data-inspector-details]");
    if (details) {
      details.innerHTML = renderInspectorDetails(item, payload, preview);
      details.querySelectorAll("[data-inspector-objective]").forEach((button) => {
        button.addEventListener("click", () => hydrateInspectorPane(item, button.dataset.inspectorObjective));
      });
    }
  } catch (error) {
    console.warn("Unable to hydrate the inspector pane", error);
    if (token === inspectorLoadToken) {
      const details = pane.querySelector("[data-inspector-details]");
      if (details) {
        details.innerHTML = `<div class="empty-state">Unable to load this instance's details.</div>`;
      }
    }
  }
}

function selectInspectorRow(route, itemsByRoute) {
  inspectorRoute = route;
  state.stage.querySelectorAll("[data-inspect-route]").forEach((row) => {
    row.classList.toggle("inspector-selected", row.dataset.inspectRoute === route);
  });
  const pane = state.stage.querySelector("[data-inspector-pane]");
  const item = itemsByRoute.get(route);
  if (!pane) {
    return;
  }
  pane.innerHTML = renderInspectorPaneShell(item);
  if (item) {
    hydrateInspectorPane(item);
  }
}

function inspectorPaneVisible() {
  const pane = state.stage.querySelector("[data-inspector-pane]");
  return Boolean(pane && pane.offsetParent !== null);
}

function attachInspectorRows(itemsByRoute) {
  state.stage.querySelectorAll("[data-inspect-route]").forEach((row) => {
    const route = row.dataset.inspectRoute;
    row.addEventListener("click", (event) => {
      if (event.target.closest("a")) {
        return;
      }
      if (!inspectorPaneVisible()) {
        window.location.href = routeHref(route);
        return;
      }
      selectInspectorRow(route, itemsByRoute);
    });
    row.addEventListener("keydown", (event) => {
      if (event.key === "Enter") {
        window.location.href = routeHref(route);
        return;
      }
      if (event.key === "ArrowDown" || event.key === "ArrowUp") {
        event.preventDefault();
        const rows = Array.from(state.stage.querySelectorAll("[data-inspect-route]"));
        const nextRow = rows[rows.indexOf(row) + (event.key === "ArrowDown" ? 1 : -1)];
        if (nextRow) {
          nextRow.focus();
          selectInspectorRow(nextRow.dataset.inspectRoute, itemsByRoute);
        }
      }
    });
  });
}

function renderCatalogIndex(payload) {
  setPage(payload.title, payload.description || `Static listing for ${payload.benchmark_name}.`, payload.breadcrumbs, "catalog");
  const filteredItems = filteredCollectionItems(payload);
  const descriptionCard = payload.context_route_path
    ? renderCard(
        "Description",
        `${renderMarkdownBlocks(payload.context_summary || "")}<div class="inline-actions" style="margin-top:0.8rem"><a class="button-link" href="${routeHref(payload.context_route_path)}">Description</a></div>`,
      )
    : "";
  state.aside.innerHTML = [
    renderCard(
      "Catalog Summary",
      `${renderStatGrid([
        ["Instances", payload.summary.instance_count],
        ["BKS", payload.summary.bks_count],
        ["Size buckets", payload.summary.size_bucket_count],
        ["Places", payload.summary.place_count],
      ])}<div class="badge-row">${payload.summary.supported_objective_functions.map((objective) => badge(objective)).join("")}</div>`,
    ),
    renderCollectionFilterCard(payload, filteredItems.length),
    descriptionCard,
    renderSubrouteList("Variants", payload.variant_routes),
    renderSubrouteList("Subsets", payload.subset_routes),
    renderSubrouteList("Places", payload.place_routes),
    renderSubrouteList("Sizes", payload.size_routes),
  ].join("");
  const groupsByMetricVariant =
    payload.payload_kind === "family_index" && hasMetricVariantGroups(filteredItems);
  const tableHtml = groupsByMetricVariant
    ? renderInstanceGroups(filteredItems, true, { inspector: true })
    : renderInstanceRows(filteredItems, { inspector: true });
  const tableHint = filteredItems.length
    ? `<div class="meta-line inspector-hint">Click a row to inspect · ⏎ opens the full record</div>`
    : "";
  state.stage.innerHTML = `<div class="catalog-with-inspector"><div class="catalog-table-col">${tableHtml}${tableHint}</div><aside class="inspector-pane" data-inspector-pane></aside></div>`;
  const itemsByRoute = new Map(filteredItems.map((item) => [item.route_path, item]));
  attachInspectorRows(itemsByRoute);
  const initialRoute = itemsByRoute.has(inspectorRoute) ? inspectorRoute : (filteredItems[0]?.route_path ?? null);
  selectInspectorRow(initialRoute, itemsByRoute);
  const sortSelect = state.aside.querySelector("[data-collection-sort]");
  if (sortSelect) sortSelect.value = state.collectionFilters.sort;
  state.aside.querySelectorAll("[data-collection-filter]").forEach((select) => select.addEventListener("change", () => {
    state.collectionFilters[select.dataset.collectionFilter] = select.value;
    syncCollectionFilterUrl();
    renderCatalogIndex(payload);
  }));
  state.aside.querySelector("[data-collection-search]")?.addEventListener("change", (event) => {
    state.collectionFilters.search = event.target.value;
    syncCollectionFilterUrl();
    renderCatalogIndex(payload);
  });
  sortSelect?.addEventListener("change", (event) => {
    state.collectionFilters.sort = event.target.value;
    syncCollectionFilterUrl();
    renderCatalogIndex(payload);
  });
  state.aside.querySelector("[data-collection-reset]")?.addEventListener("click", () => {
    Object.keys(COLLECTION_FILTER_QUERY_KEYS).forEach((key) => { state.collectionFilters[key] = ""; });
    state.collectionFilters.search = "";
    state.collectionFilters.sort = "size-name";
    syncCollectionFilterUrl();
    renderCatalogIndex(payload);
  });
  setStatus(`Loaded ${filteredItems.length} of ${payload.items.length} instances`);
}

function renderFamilyContext(payload) {
  setPage(payload.title, "Benchmark family provenance, objective contract, and curation notes.", payload.breadcrumbs, "editorial");
  const licenseCard = payload.license_markdown || payload.license_spdx_id
    ? renderCard(
        "License",
        `${payload.license_spdx_id ? `<div class="badge-row">${badge(payload.license_spdx_id, true)}</div>` : ""}${payload.license_markdown ? renderMarkdownBlocks(payload.license_markdown) : ""}`,
      )
    : "";
  state.aside.innerHTML = [
    renderCard(
      "Family",
      `${renderStatGrid([
        ["Problem", payload.problem_type],
        ["Benchmark", payload.benchmark_name],
        ["Snapshot", payload.snapshot.snapshot_id],
      ])}<div class="inline-actions" style="margin-top:0.8rem"><a class="button-link primary" href="${routeHref(payload.family_route_path)}">Open family</a></div>`,
    ),
    licenseCard,
  ].join("");
  state.stage.innerHTML = `<article class="context-prose">${renderMarkdownBlocks(payload.markdown)}</article>`;
  setStatus(`Loaded context for ${payload.problem_type} / ${payload.benchmark_name}`);
}

function coordinateBounds(points) {
  if (!Array.isArray(points) || points.length === 0) {
    return null;
  }
  const validPoints = points
    .map((point) => {
      if (!Array.isArray(point) || point.length < 2) {
        return null;
      }
      const x = Number(point[0]);
      const y = Number(point[1]);
      return Number.isFinite(x) && Number.isFinite(y) ? [x, y] : null;
    })
    .filter(Boolean);
  if (validPoints.length === 0) {
    return null;
  }
  const xs = validPoints.map((point) => point[0]);
  const ys = validPoints.map((point) => point[1]);
  return {
    minX: Math.min(...xs),
    maxX: Math.max(...xs),
    minY: Math.min(...ys),
    maxY: Math.max(...ys),
  };
}

function projectCoordinates(points, width, height, bounds = null) {
  if (!Array.isArray(points) || points.length === 0) {
    return [];
  }
  const activeBounds = bounds || coordinateBounds(points);
  if (!activeBounds) {
    return [];
  }
  const pad = 28;
  const usableWidth = Math.max(width - pad * 2, 1);
  const usableHeight = Math.max(height - pad * 2, 1);
  const spanX = Math.max(activeBounds.maxX - activeBounds.minX, 0);
  const spanY = Math.max(activeBounds.maxY - activeBounds.minY, 0);
  const scaleX = spanX > 0 ? usableWidth / spanX : Number.POSITIVE_INFINITY;
  const scaleY = spanY > 0 ? usableHeight / spanY : Number.POSITIVE_INFINITY;
  let scale = Math.min(scaleX, scaleY);
  if (!Number.isFinite(scale)) {
    scale = 1;
  }
  const drawnWidth = spanX * scale;
  const drawnHeight = spanY * scale;
  const offsetX = pad + Math.max((usableWidth - drawnWidth) / 2, 0);
  const offsetY = pad + Math.max((usableHeight - drawnHeight) / 2, 0);

  return points.map((point) => {
    const normalized = normalizeGeometryPoint(point);
    if (!normalized) {
      return null;
    }
    return {
      x: offsetX + (normalized[0] - activeBounds.minX) * scale,
      y: offsetY + (activeBounds.maxY - normalized[1]) * scale,
    };
  });
}

function normalizeGeometryPoint(value) {
  if (!Array.isArray(value) || value.length < 2) {
    return null;
  }
  const x = Number(value[0]);
  const y = Number(value[1]);
  if (!Number.isFinite(x) || !Number.isFinite(y)) {
    return null;
  }
  return [x, y];
}

function geometryPointFromMetaNode(node) {
  if (!node || typeof node !== "object") {
    return null;
  }
  if (Number.isFinite(Number(node.poi_lon)) && Number.isFinite(Number(node.poi_lat))) {
    return [Number(node.poi_lon), Number(node.poi_lat)];
  }
  if (Number.isFinite(Number(node.enu_x)) && Number.isFinite(Number(node.enu_y))) {
    return [Number(node.enu_x), Number(node.enu_y)];
  }
  return null;
}

function metaNodeIndexOffset(metaNodes) {
  const nodeIds = Array.isArray(metaNodes)
    ? metaNodes.map((node) => Number(node?.instance_node_id)).filter(Number.isFinite)
    : [];
  return nodeIds.length > 0 && Math.min(...nodeIds) === 0 ? 0 : 1;
}

function resolveViewerNodeCoordinates(instanceData, geometryMeta) {
  const fallbackCoordinates = Array.isArray(instanceData.coordinates) ? instanceData.coordinates : [];
  const metaNodes = Array.isArray(geometryMeta?.nodes) ? geometryMeta.nodes : [];
  if (metaNodes.length === 0) {
    return fallbackCoordinates;
  }

  const resolved = [];
  const offset = metaNodeIndexOffset(metaNodes);
  metaNodes.forEach((node) => {
    const point = geometryPointFromMetaNode(node);
    const instanceNodeId = Number(node?.instance_node_id);
    if (!point || !Number.isFinite(instanceNodeId)) {
      return;
    }
    resolved[instanceNodeId - offset] = point;
  });

  const missingPoints = fallbackCoordinates.some((_, index) => !resolved[index]);
  return missingPoints ? fallbackCoordinates : resolved;
}

function resolveViewerGraphVertexIds(instanceData, geometryMeta) {
  const fallbackCoordinates = Array.isArray(instanceData.coordinates) ? instanceData.coordinates : [];
  const metaNodes = Array.isArray(geometryMeta?.nodes) ? geometryMeta.nodes : [];
  if (metaNodes.length === 0) {
    return fallbackCoordinates.map((_, index) => index + 1);
  }

  const resolved = [];
  const offset = metaNodeIndexOffset(metaNodes);
  metaNodes.forEach((node) => {
    const instanceNodeId = Number(node?.instance_node_id);
    const graphVertexId = Number(node?.graph_vertex_id);
    if (!Number.isFinite(instanceNodeId) || !Number.isFinite(graphVertexId)) {
      return;
    }
    resolved[instanceNodeId - offset] = graphVertexId;
  });

  const missingIds = fallbackCoordinates.some((_, index) => !Number.isFinite(Number(resolved[index])));
  return missingIds ? fallbackCoordinates.map((_, index) => index + 1) : resolved;
}

function resolveViewerInstanceNodeIds(instanceData, geometryMeta) {
  const fallbackCoordinates = Array.isArray(instanceData.coordinates) ? instanceData.coordinates : [];
  const metaNodes = Array.isArray(geometryMeta?.nodes) ? geometryMeta.nodes : [];
  if (metaNodes.length === 0) {
    return fallbackCoordinates.map((_, index) => index + 1);
  }

  const resolved = [];
  const offset = metaNodeIndexOffset(metaNodes);
  metaNodes.forEach((node) => {
    const instanceNodeId = Number(node?.instance_node_id);
    if (!Number.isFinite(instanceNodeId)) {
      return;
    }
    resolved[instanceNodeId - offset] = instanceNodeId;
  });

  const missingIds = fallbackCoordinates.some((_, index) => !Number.isFinite(Number(resolved[index])));
  return missingIds ? fallbackCoordinates.map((_, index) => index + 1) : resolved;
}

function mergeGeometrySegments(segments) {
  const merged = [];
  segments.forEach((segment, segmentIndex) => {
    segment.forEach((point, pointIndex) => {
      if (segmentIndex > 0 && pointIndex === 0) {
        return;
      }
      merged.push(point);
    });
  });
  return merged;
}

function isLonLatPoint(point) {
  return Array.isArray(point)
    && point.length >= 2
    && Math.abs(Number(point[0])) <= 180
    && Math.abs(Number(point[1])) <= 90;
}

function pointDistanceMeters(firstPoint, secondPoint) {
  if (isLonLatPoint(firstPoint) && isLonLatPoint(secondPoint)) {
    const meanLat = (Number(firstPoint[1]) + Number(secondPoint[1])) / 2;
    const lonScale = 111320 * Math.cos((meanLat * Math.PI) / 180);
    const latScale = 111320;
    return Math.hypot((Number(firstPoint[0]) - Number(secondPoint[0])) * lonScale, (Number(firstPoint[1]) - Number(secondPoint[1])) * latScale);
  }
  return Math.hypot(Number(firstPoint[0]) - Number(secondPoint[0]), Number(firstPoint[1]) - Number(secondPoint[1]));
}

function cachedSegmentMatchesEndpoints(segment, expectedFrom, expectedTo) {
  if (!expectedFrom || !expectedTo) {
    return true;
  }
  if (!Array.isArray(segment) || segment.length < 2) {
    return false;
  }
  return pointDistanceMeters(segment[0], expectedFrom) <= ROAD_CACHE_ENDPOINT_TOLERANCE_METERS
    && pointDistanceMeters(segment[segment.length - 1], expectedTo) <= ROAD_CACHE_ENDPOINT_TOLERANCE_METERS;
}

function cachedSegmentFromKeys(metricCache, key, reverseKey, expectedFrom, expectedTo) {
  let rawSegment = metricCache[key];
  let shouldReverse = false;
  if (!Array.isArray(rawSegment)) {
    rawSegment = metricCache[reverseKey];
    shouldReverse = Array.isArray(rawSegment);
  }
  if (!Array.isArray(rawSegment) || rawSegment.length < 2) {
    return null;
  }
  const normalizedSegment = rawSegment.map(normalizeGeometryPoint).filter(Boolean);
  if (shouldReverse) {
    normalizedSegment.reverse();
  }
  if (normalizedSegment.length < 2) {
    return null;
  }
  return cachedSegmentMatchesEndpoints(normalizedSegment, expectedFrom, expectedTo) ? normalizedSegment : null;
}

function cachedRouteSegments(sequence, metricCache, graphVertexIds, nodeCoordinates, instanceNodeIds) {
  if (!metricCache || typeof metricCache !== "object") {
    return null;
  }

  const segments = [];
  for (let index = 1; index < sequence.length; index += 1) {
    const fromIndex = Number(sequence[index - 1]);
    const toIndex = Number(sequence[index]);
    const expectedFrom = normalizeGeometryPoint(nodeCoordinates[fromIndex]);
    const expectedTo = normalizeGeometryPoint(nodeCoordinates[toIndex]);

    const fromNodeId = Number(instanceNodeIds?.[fromIndex]);
    const toNodeId = Number(instanceNodeIds?.[toIndex]);
    let normalizedSegment = null;
    if (Number.isFinite(fromNodeId) && Number.isFinite(toNodeId)) {
      normalizedSegment = cachedSegmentFromKeys(
        metricCache,
        `node:${fromNodeId}_${toNodeId}`,
        `node:${toNodeId}_${fromNodeId}`,
        expectedFrom,
        expectedTo,
      );
    }

    if (!normalizedSegment) {
      const fromId = Number(graphVertexIds[fromIndex]);
      const toId = Number(graphVertexIds[toIndex]);
      if (!Number.isFinite(fromId) || !Number.isFinite(toId)) {
        return null;
      }
      normalizedSegment = cachedSegmentFromKeys(metricCache, `${fromId}_${toId}`, `${toId}_${fromId}`, expectedFrom, expectedTo);
    }

    if (!normalizedSegment) {
      return null;
    }
    segments.push(normalizedSegment);
  }

  return segments;
}

function cachedRouteCoordinates(sequence, metricCache, graphVertexIds, nodeCoordinates, instanceNodeIds) {
  const segments = cachedRouteSegments(sequence, metricCache, graphVertexIds, nodeCoordinates, instanceNodeIds);
  return segments ? mergeGeometrySegments(segments) : null;
}

function routeNodeLookup(routes) {
  const lookup = new Map();
  if (!Array.isArray(routes)) {
    return lookup;
  }
  routes.forEach((route, routeIndex) => {
    if (!Array.isArray(route)) {
      return;
    }
    route.forEach((nodeIndex) => {
      const normalizedIndex = Number(nodeIndex);
      if (Number.isFinite(normalizedIndex) && !lookup.has(normalizedIndex)) {
        lookup.set(normalizedIndex, routeIndex);
      }
    });
  });
  return lookup;
}

function resolvePreviewGeometry(instanceData, bksData, selectedEntry, options = {}) {
  const geometryMeta = options.geometryMeta || null;
  const metricVariant = String(options.metricVariant || "").toLowerCase();
  const nodeCoordinates = resolveViewerNodeCoordinates(instanceData, geometryMeta);
  const graphVertexIds = resolveViewerGraphVertexIds(instanceData, geometryMeta);
  const instanceNodeIds = resolveViewerInstanceNodeIds(instanceData, geometryMeta);
  const depotIndex = Number(instanceData.depot || 0);
  const routes = Array.isArray(bksData?.routes) ? bksData.routes : [];
  const metricCache = geometryMeta?.road_cache?.[metricVariant];
  const cachedRoadAvailable = options.viewerRenderMode === "cached_road" && options.roadCacheStatus === "complete" && metricCache;
  const straightFallbackPaths = new Set(geometryMeta?.route_geometry_straight_fallback_paths || []);

  const routeLines = routes.map((route, routeIndex) => {
    const sequence = [depotIndex, ...route.map((nodeIndex) => Number(nodeIndex)), depotIndex];
    const cachedSegments = cachedRoadAvailable ? cachedRouteSegments(sequence, metricCache, graphVertexIds, nodeCoordinates, instanceNodeIds) : null;
    const cachedCoordinates = cachedSegments ? mergeGeometrySegments(cachedSegments) : null;
    const hasStraightFallback = sequence.slice(1).some((toNode, edgeIndex) => straightFallbackPaths.has(`${sequence[edgeIndex]}-${toNode}`));
    const routeCoordinates = cachedCoordinates || sequence.map((nodeIndex) => normalizeGeometryPoint(nodeCoordinates[nodeIndex])).filter(Boolean);
    const segments = cachedSegments || sequence.slice(0, -1).map((_, segmentIndex) => [
      normalizeGeometryPoint(nodeCoordinates[sequence[segmentIndex]]),
      normalizeGeometryPoint(nodeCoordinates[sequence[segmentIndex + 1]]),
    ].filter(Boolean));
    return {
      routeIndex,
      sequence,
      coordinates: routeCoordinates,
      segments,
      source: cachedCoordinates ? (hasStraightFallback ? "mixed" : "cached_road") : "straight_line",
      stopCount: route.length,
    };
  });

  return {
    depotIndex,
    nodeCoordinates,
    routeLines,
    routeMembership: routeNodeLookup(routes),
    hasCachedRoadRoutes: routeLines.some((routeLine) => routeLine.source === "cached_road"),
    geometryNoteHtml: selectedEntry
      ? (() => {
          const objective = escapeHtml(selectedEntry.objective_function);
          const costHtml = costSpan(selectedEntry.cost);
          if (selectedEntry.num_routes == null) {
            return `${objective} · ${costHtml}`;
          }
          const routesText = `${escapeHtml(String(selectedEntry.num_routes))} routes`;
          const routesHtml = isHierarchicalObjective(selectedEntry)
            ? `<span class="badge-cost">${routesText}</span>`
            : routesText;
          return `${objective} · ${routesHtml} · ${costHtml}`;
        })()
      : escapeHtml("Instance preview without BKS overlay"),
  };
}

// Only the road metrics draw depot legs that follow real streets. Euclidean
// variants -- and the historical families, which carry no metric variant -- draw
// them as long straight chords across the picture, so those keep them faded.
function usesRoadMetric(summary) {
  return ["fastest", "shortest"].includes(String(summary?.metric_variant || "").toLowerCase());
}

function supportsWorkbenchInstance(value) {
  const placeSlug = String(value?.place_slug || value?.summary?.place_slug || "").trim();
  return placeSlug.length > 0;
}

// Five-pointed star polygon, first point up, as an SVG "points" string. Used for
// the depot marker so it stays distinguishable from the customer dots.
function starPoints(centerX, centerY, outerRadius, innerRatio = 0.42, spikes = 5) {
  const innerRadius = outerRadius * innerRatio;
  const points = [];
  for (let index = 0; index < spikes * 2; index += 1) {
    const radius = index % 2 === 0 ? outerRadius : innerRadius;
    const angle = -Math.PI / 2 + (index * Math.PI) / spikes;
    points.push(`${(centerX + radius * Math.cos(angle)).toFixed(2)},${(centerY + radius * Math.sin(angle)).toFixed(2)}`);
  }
  return points.join(" ");
}

function renderPreviewSvg(instanceData, bksData, selectedEntry, options = {}) {
  const width = 860;
  const height = 520;
  const previewGeometry = resolvePreviewGeometry(instanceData, bksData, selectedEntry, options);
  const projectionBounds = coordinateBounds([
    ...(previewGeometry.nodeCoordinates || []),
    ...previewGeometry.routeLines.flatMap((routeLine) => routeLine.coordinates || []),
  ]);
  const projectedNodes = projectCoordinates(previewGeometry.nodeCoordinates || [], width, height, projectionBounds);
  const display = {
    hiddenRoutes: options.displayOptions?.hiddenRoutes || new Set(),
    depotLegMode: options.displayOptions?.depotLegMode || "full",
    fadedOpacity: options.displayOptions?.fadedOpacity ?? 0.25,
    routeOpacity: options.displayOptions?.routeOpacity ?? 1,
    // Thumbnails (home previews, catalog inspector) pass no display options and
    // keep the plain dot; the instance solution view opts into the star.
    depotStar: options.displayOptions?.depotStar ?? false,
  };
  const polylineFor = (points, color, opacity) => {
    const projected = projectCoordinates(points || [], width, height, projectionBounds).filter(Boolean);
    if (projected.length < 2) {
      return "";
    }
    const opacityAttr = opacity < 1 ? ` stroke-opacity="${opacity.toFixed(3)}"` : "";
    return `<polyline fill="none" style="stroke:${color}" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"${opacityAttr} points="${projected
      .map((point) => `${point.x},${point.y}`)
      .join(" ")}" />`;
  };
  const routePaths = previewGeometry.routeLines
    .map((routeLine) => {
      if (display.hiddenRoutes.has(routeLine.routeIndex)) {
        return "";
      }
      const color = PALETTE[routeLine.routeIndex % PALETTE.length];
      let body;
      if (display.depotLegMode === "full" || !Array.isArray(routeLine.segments) || routeLine.segments.length < 2) {
        body = polylineFor(routeLine.coordinates, color, display.routeOpacity);
      } else {
        // Depot legs (first and last segments) drawn separately so they can
        // fade or hide; the route body keeps full presence.
        body = polylineFor(mergeGeometrySegments(routeLine.segments.slice(1, -1)), color, display.routeOpacity);
        if (display.depotLegMode === "faded") {
          const legOpacity = Math.max(0, Math.min(1, display.fadedOpacity * display.routeOpacity));
          body += polylineFor(routeLine.segments[0], color, legOpacity);
          body += polylineFor(routeLine.segments[routeLine.segments.length - 1], color, legOpacity);
        }
      }
      if (!body) {
        return "";
      }
      const routeTitle = `Route ID ${routeLine.routeIndex + 1} · ${routeLine.stopCount} customer${routeLine.stopCount === 1 ? "" : "s"} · ${String(routeLine.source).replaceAll("_", " ")}`;
      return `<g class="route-line"><title>${escapeHtml(routeTitle)}</title>${body}</g>`;
    })
    .join("");
  const nodes = projectedNodes
    .map((point, index) => {
      if (!point) {
        return "";
      }
      const isDepot = index === previewGeometry.depotIndex;
      const routeIndex = previewGeometry.routeMembership.get(index);
      const nodeTitle = isDepot
        ? `Depot · ${previewGeometry.routeLines.length} route${previewGeometry.routeLines.length === 1 ? "" : "s"}`
        : routeIndex === undefined
          ? `Customer ID ${index} · no route`
          : `Customer ID ${index} · Route ID ${routeIndex + 1}`;
      const shape = isDepot && display.depotStar
        ? `<polygon points="${starPoints(point.x, point.y, 10)}" style="fill:var(--cor);stroke:var(--svg)" stroke-width="1.4" stroke-linejoin="round" />`
        : `<circle cx="${point.x}" cy="${point.y}" r="${isDepot ? 6 : 4}" style="fill:${isDepot ? 'var(--cor)' : 'var(--ptc)'}" opacity="${isDepot ? 1 : 0.8}" />`;
      return `<g class="viewer-node"><title>${escapeHtml(nodeTitle)}</title>${shape}</g>`;
    })
    .join("");
  let arcHitTargets = "";
  if (options.interactiveArcs) {
    arcHitTargets = previewGeometry.routeLines
      .filter((routeLine) => routeLine.source === "straight_line" && !display.hiddenRoutes.has(routeLine.routeIndex))
      .map((routeLine) => {
        const projectedRoute = projectCoordinates(routeLine.coordinates, width, height, projectionBounds);
        const segments = [];
        for (let k = 0; k + 1 < routeLine.sequence.length; k += 1) {
          const a = projectedRoute[k];
          const b = projectedRoute[k + 1];
          if (!a || !b) continue;
          segments.push(
            `<line class="arc-hit" x1="${a.x}" y1="${a.y}" x2="${b.x}" y2="${b.y}" stroke="transparent" stroke-width="14" stroke-linecap="round" data-arc-from="${routeLine.sequence[k]}" data-arc-to="${routeLine.sequence[k + 1]}" data-arc-route="${routeLine.routeIndex}"><title>Arc ${routeLine.sequence[k]} → ${routeLine.sequence[k + 1]} · click to plot its travel-time functions</title></line>`,
          );
        }
        return segments.join("");
      })
      .join("");
  }
  const geometryCaption = previewGeometry.hasCachedRoadRoutes
    ? `Cached-road preview from sidecar geometry (${String(options.metricVariant || "road").toLowerCase()})`
    : "Straight-line preview from canonical coordinates";
  return `
    <div class="viewer-toolbar">
      <div>${badgeHtml(previewGeometry.geometryNoteHtml, true)}</div>
      <div class="meta-line">${escapeHtml(geometryCaption)}${options.interactiveArcs ? " · click an arc to plot its ATF/TTF" : ""}</div>
    </div>
    <div class="viewer-frame">
      <svg viewBox="0 0 ${width} ${height}" role="img" aria-label="Routing preview">${routePaths}${nodes}${arcHitTargets}</svg>
    </div>`;
}

function renderDisplayOptionsCard(bksData, displayOptions) {
  const routes = Array.isArray(bksData?.routes) ? bksData.routes : [];
  if (routes.length === 0) {
    return "";
  }
  const hiddenCount = routes.reduce((count, _, index) => count + (displayOptions.hiddenRoutes.has(index) ? 1 : 0), 0);
  const routeToggles = routes
    .map(
      (route, index) =>
        `<label class="route-toggle"><input type="checkbox" data-route-toggle="${index}"${displayOptions.hiddenRoutes.has(index) ? "" : " checked"} /><span class="legend-swatch" style="background:${PALETTE[index % PALETTE.length]}"></span><span class="route-toggle-label">R${index + 1}</span><span class="route-toggle-meta">${route.length} stop${route.length === 1 ? "" : "s"}</span></label>`,
    )
    .join("");
  return renderCard(
    "Routes · click to toggle",
    `<div class="route-toggle-toolbar">
        <button type="button" class="bks-chip" data-routes-all>All</button>
        <button type="button" class="bks-chip" data-routes-none>None</button>
        <span class="meta-line">${routes.length - hiddenCount}/${routes.length} visible</span>
      </div>
      <div class="route-toggle-list">${routeToggles}</div>
      <label class="field"><span>Depot legs</span><select data-display-depot-legs>
        <option value="full"${displayOptions.depotLegMode === "full" ? " selected" : ""}>Full</option>
        <option value="faded"${displayOptions.depotLegMode === "faded" ? " selected" : ""}>Faded</option>
        <option value="hidden"${displayOptions.depotLegMode === "hidden" ? " selected" : ""}>Hidden</option>
      </select></label>
      <label class="field"><span>Legs opacity: <output data-legs-opacity-value>${Math.round(displayOptions.fadedOpacity * 100)}%</output></span><input type="range" min="0" max="1" step="0.05" value="${displayOptions.fadedOpacity}" data-display-legs-opacity${displayOptions.depotLegMode === "faded" ? "" : " disabled"} /></label>
      <label class="field"><span>Route opacity: <output data-route-opacity-value>${Math.round(displayOptions.routeOpacity * 100)}%</output></span><input type="range" min="0.1" max="1" step="0.05" value="${displayOptions.routeOpacity}" data-display-route-opacity /></label>
      <label class="display-toggle"><input type="checkbox" data-display-depot-star${displayOptions.depotStar ? " checked" : ""} /><span>Depot as star</span></label>`,
  );
}

function renderBksSelector(entries, selectedIndex) {
  if (!entries || entries.length === 0) {
    return `<div class="empty-state">No best-known solution is currently attached to this instance.</div>`;
  }
  return `<div class="selector-row">${entries
    .map(
      (entry, index) =>
        `<button type="button" class="bks-chip${index === selectedIndex ? ' active' : ''}" data-bks-index="${index}">${escapeHtml(entry.objective_function)}</button>`,
    )
    .join("")}</div>`;
}

function labelizeCapability(value) {
  return String(value ?? "n/a").replaceAll("_", " ");
}

function renderGeometryCard(summary) {
  const metrics = Array.isArray(summary.road_cache_metrics) && summary.road_cache_metrics.length > 0
    ? summary.road_cache_metrics.join(", ")
    : "none";
  return renderCard(
    "Geometry",
    `${renderStatGrid([
      ["Viewer mode", labelizeCapability(summary.viewer_render_mode)],
      ["Road cache", labelizeCapability(summary.road_cache_status)],
      ["Sidecar", summary.has_geometry_sidecar ? "yes" : "no"],
      ["Cached paths", summary.road_cache_entry_count ?? 0],
      ["BKS route edges", summary.road_cache_expected_entry_count ?? "n/a"],
      ["Metrics", metrics],
    ])}`,
  );
}

function renderWorkbenchModeCard(instanceRoute) {
  const activeMode = state.workbenchMode === "upload" ? "visualize" : state.workbenchMode === "catalog" ? "visualize" : state.workbenchMode;
  const workbenchTargets = [
    { mode: "visualize", path: "/workbench/", includeInstance: true },
    { mode: "generate", path: "/workbench/generate/", includeInstance: true },
  ];
  return renderCard(
    "Workbench Mode",
    `<div class="chip-row">${workbenchTargets
      .map(({ mode, path, includeInstance }) => {
        const suffix = includeInstance && instanceRoute ? `?instance=${encodeURIComponent(instanceRoute)}` : "";
        return `<a class="selector-chip${mode === activeMode ? ' active' : ''}" href="${routeHref(path)}${suffix}">${escapeHtml(mode)}</a>`;
      })
      .join("")}</div><p class="meta-line" style="margin-top:0.8rem">Catalog mode now reuses the benchmark instance viewer through the workbench deep link.</p>`,
  );
}

function renderWorkbenchVisualizeSourceCard(instanceRoute) {
  const sourceTargets = [
    { label: "benchmark", path: "/workbench/", active: state.workbenchMode !== "upload" },
    { label: "upload", path: "/workbench/upload/", active: state.workbenchMode === "upload" },
  ];
  return renderCard(
    "Visualize Source",
    `<div class="chip-row">${sourceTargets
      .map(({ label, path, active }) => {
        const suffix = instanceRoute ? `?instance=${encodeURIComponent(instanceRoute)}` : "";
        return `<a class="selector-chip${active ? ' active' : ''}" href="${routeHref(path)}${suffix}">${escapeHtml(label)}</a>`;
      })
      .join("")}</div><p class="meta-line" style="margin-top:0.8rem">Switch between benchmark-backed visualization and local file uploads without leaving the workbench shell.</p>`,
  );
}

const ATF_SIDECAR_CACHE = new Map();

async function fetchInstanceAtfArcs(atfArtifactPath) {
  if (ATF_SIDECAR_CACHE.has(atfArtifactPath)) return ATF_SIDECAR_CACHE.get(atfArtifactPath);
  const promise = (async () => {
    const response = await fetch(artifactHref(atfArtifactPath));
    if (!response.ok) throw new Error(`Unable to fetch the ATF sidecar (${response.status})`);
    let payload;
    if (atfArtifactPath.endsWith(".gz")) {
      if (typeof DecompressionStream === "undefined") {
        throw new Error("This browser cannot decompress the gzipped ATF sidecar (DecompressionStream unavailable).");
      }
      payload = await new Response(response.body.pipeThrough(new DecompressionStream("gzip"))).json();
    } else {
      payload = await response.json();
    }
    const arcs = new Map();
    for (const [i, j, xs, ys] of payload.arcs || []) arcs.set(`${i},${j}`, { xs, ys });
    return { arcs, horizon: payload.horizon };
  })();
  ATF_SIDECAR_CACHE.set(atfArtifactPath, promise);
  promise.catch(() => ATF_SIDECAR_CACHE.delete(atfArtifactPath));
  return promise;
}

function renderArcFunctionChart(chartId, title, xs, ys, color, options = {}) {
  const width = 420;
  const height = 260;
  const pad = { left: 56, right: 14, top: 14, bottom: 34 };
  const xMin = xs[0];
  const xMax = xs[xs.length - 1];
  const yMin = Math.min(...ys);
  const yMax = Math.max(...ys);
  const ySpan = yMax - yMin || 1;
  const xSpan = xMax - xMin || 1;
  const px = (x) => pad.left + ((x - xMin) / xSpan) * (width - pad.left - pad.right);
  const py = (y) => height - pad.bottom - ((y - yMin) / ySpan) * (height - pad.top - pad.bottom);
  const points = xs.map((x, k) => `${px(x).toFixed(1)},${py(ys[k]).toFixed(1)}`).join(" ");
  let markerSvg = "";
  if (options.marker) {
    const m = options.marker;
    const mx = px(m.x);
    const my = py(m.y);
    markerSvg = `
        <line x1="${pad.left}" y1="${my.toFixed(1)}" x2="${mx.toFixed(1)}" y2="${my.toFixed(1)}" style="stroke:${m.color}" stroke-width="1" stroke-dasharray="4 3" />
        <line x1="${mx.toFixed(1)}" y1="${height - pad.bottom}" x2="${mx.toFixed(1)}" y2="${my.toFixed(1)}" style="stroke:${m.color}" stroke-width="1" stroke-dasharray="4 3" />
        <circle cx="${mx.toFixed(1)}" cy="${my.toFixed(1)}" r="4" style="fill:${m.color};stroke:var(--s)" stroke-width="1.5"><title>${escapeHtml(m.label)}</title></circle>
        <text x="${Math.min(mx + 7, width - pad.right - 4).toFixed(1)}" y="${Math.max(my - 7, pad.top + 10).toFixed(1)}" font-size="10.5" style="fill:${m.color}">${escapeHtml(m.label)}</text>`;
  }
  const yTicks = [yMin, (yMin + yMax) / 2, yMax];
  const xTicks = [xMin, (xMin + xMax) / 2, xMax];
  const grid = yTicks
    .map((t) => `<line x1="${pad.left}" y1="${py(t).toFixed(1)}" x2="${width - pad.right}" y2="${py(t).toFixed(1)}" style="stroke:var(--div)" stroke-width="1" />`)
    .join("");
  const yLabels = yTicks
    .map((t) => `<text x="${pad.left - 6}" y="${(py(t) + 3.5).toFixed(1)}" text-anchor="end" font-size="10.5" style="fill:var(--mut)">${formatScheduleTime(t)}</text>`)
    .join("");
  const xLabels = xTicks
    .map((t, k) => {
      const anchor = k === 0 ? "start" : k === xTicks.length - 1 ? "end" : "middle";
      return `<text x="${px(t).toFixed(1)}" y="${height - pad.bottom + 16}" text-anchor="${anchor}" font-size="10.5" style="fill:var(--mut)">${formatScheduleTime(t)}</text>`;
    })
    .join("");
  return `
    <div class="arc-chart" data-arc-chart="${chartId}">
      <div class="meta-line" style="margin-bottom:0.2rem">${escapeHtml(title)}</div>
      <svg viewBox="0 0 ${width} ${height}" role="img" aria-label="${escapeHtml(title)}" style="width:100%;height:auto">
        ${grid}
        <line x1="${pad.left}" y1="${height - pad.bottom}" x2="${width - pad.right}" y2="${height - pad.bottom}" style="stroke:var(--div)" stroke-width="1" />
        <line x1="${pad.left}" y1="${pad.top}" x2="${pad.left}" y2="${height - pad.bottom}" style="stroke:var(--div)" stroke-width="1" />
        ${yLabels}${xLabels}
        <text x="${(pad.left + width - pad.right) / 2}" y="${height - 4}" text-anchor="middle" font-size="10.5" style="fill:var(--mut)">departure time t</text>
        <polyline fill="none" style="stroke:${color}" stroke-width="2" stroke-linejoin="round" points="${points}" />${markerSvg}
        <line class="arc-crosshair" x1="0" y1="${pad.top}" x2="0" y2="${height - pad.bottom}" style="display:none;stroke:var(--mut)" stroke-width="1" />
        <circle class="arc-hover-dot" r="3.5" style="display:none;fill:${color};stroke:var(--s)" stroke-width="1.5" />
        <rect class="arc-hover-zone" x="${pad.left}" y="${pad.top}" width="${width - pad.left - pad.right}" height="${height - pad.top - pad.bottom}" fill="transparent" />
      </svg>
      <div class="meta-line arc-hover-readout" style="min-height:1.2em"></div>
    </div>`;
}

function evaluateNdcpwlf(xs, ys, x) {
  // Mirrors NDCPWLF.evaluate (bisect_left): an exact hit on a vertical step
  // returns the smallest value, matching the canonical checker convention.
  if (x <= xs[0]) return ys[0];
  if (x >= xs[xs.length - 1]) return ys[xs.indexOf(xs[xs.length - 1])];
  let low = 0;
  let high = xs.length - 1;
  while (high - low > 1) {
    const mid = (low + high) >> 1;
    if (xs[mid] < x) low = mid;
    else high = mid;
  }
  if (xs[high] === x) {
    while (high > 0 && xs[high - 1] === x) high -= 1;
    return ys[high];
  }
  const ratio = (x - xs[low]) / (xs[high] - xs[low]);
  return ys[low] + ratio * (ys[high] - ys[low]);
}

function attachArcChartHover(container, chartId, xs, ys, formatReadout) {
  const chart = container.querySelector(`[data-arc-chart="${chartId}"]`);
  if (!chart) return;
  const svg = chart.querySelector("svg");
  const zone = chart.querySelector(".arc-hover-zone");
  const crosshair = chart.querySelector(".arc-crosshair");
  const dot = chart.querySelector(".arc-hover-dot");
  const readout = chart.querySelector(".arc-hover-readout");
  const viewBox = svg.viewBox.baseVal;
  const pad = { left: 56, right: 14, top: 14, bottom: 34 };
  const xMin = xs[0];
  const xMax = xs[xs.length - 1];
  const yMin = Math.min(...ys);
  const yMax = Math.max(...ys);
  const ySpan = yMax - yMin || 1;
  const xSpan = xMax - xMin || 1;
  zone.addEventListener("mousemove", (event) => {
    const rect = svg.getBoundingClientRect();
    const sx = ((event.clientX - rect.left) / rect.width) * viewBox.width;
    const dataX = xMin + ((sx - pad.left) / (viewBox.width - pad.left - pad.right)) * xSpan;
    const clamped = Math.min(Math.max(dataX, xMin), xMax);
    const value = evaluateNdcpwlf(xs, ys, clamped);
    const px = pad.left + ((clamped - xMin) / xSpan) * (viewBox.width - pad.left - pad.right);
    const py = viewBox.height - pad.bottom - ((value - yMin) / ySpan) * (viewBox.height - pad.top - pad.bottom);
    crosshair.setAttribute("x1", px);
    crosshair.setAttribute("x2", px);
    crosshair.style.display = "";
    dot.setAttribute("cx", px);
    dot.setAttribute("cy", py);
    dot.style.display = "";
    readout.textContent = formatReadout(clamped, value);
  });
  zone.addEventListener("mouseleave", () => {
    crosshair.style.display = "none";
    dot.style.display = "none";
    readout.textContent = "";
  });
}

function renderArcFunctionsCard(arcState) {
  if (!arcState) return "";
  if (arcState.status === "loading") {
    return `<section class="mini-card"><h3>Arc Functions</h3><div class="meta-line">Loading the ATF sidecar…</div></section>`;
  }
  if (arcState.status === "error") {
    return `<section class="mini-card"><h3>Arc Functions</h3><div class="empty-state">${escapeHtml(arcState.message)}</div></section>`;
  }
  const { from, to, xs, ys } = arcState;
  const ttf = ys.map((y, k) => y - xs[k]);
  const minTtf = Math.min(...ttf);
  const maxTtf = Math.max(...ttf);
  const steps = xs.filter((x, k) => k > 0 && x === xs[k - 1]).length;
  return `
    <section class="mini-card">
      <h3>Arc Functions · ${from} → ${to}</h3>
      <div class="meta-line">Canonical arrival-time function α(t) of arc ${from} → ${to} and its derived travel-time function τ(t) = α(t) − t. ${xs.length} breakpoints${steps > 0 ? ` (including ${steps} vertical step${steps === 1 ? "" : "s"})` : ""}; travel time ranges from ${formatScheduleTime(minTtf)} to ${formatScheduleTime(maxTtf)}.</div>
      <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:1rem;margin-top:0.6rem">
        ${renderArcFunctionChart("atf", "Arrival time α(t)", xs, ys, PALETTE[0])}
        ${renderArcFunctionChart("ttf", "Travel time τ(t) = α(t) − t", xs, ttf, PALETTE[1])}
      </div>
    </section>`;
}

function formatScheduleTime(value) {
  if (typeof value !== "number" || !Number.isFinite(value)) return "n/a";
  return value.toFixed(2);
}

function routeFunctionsHref(routeFunctionsPath) {
  const normalized = routeFunctionsPath.startsWith("/") ? routeFunctionsPath : `/${routeFunctionsPath}`;
  return relativeFromCurrent(`${resolvePayloadStaticRoot()}${normalized}`, { directory: false });
}

function renderTdRouteFunctionCharts(routeFunctions, routeFunctionsStatus, routeIndex) {
  if (routeFunctionsStatus === "loading") {
    return `<div class="meta-line" style="margin-top:0.8rem">Loading the route ready-time function…</div>`;
  }
  if (routeFunctionsStatus === "error") {
    return `<div class="meta-line" style="margin-top:0.8rem">The route function payload could not be loaded.</div>`;
  }
  const entry = routeFunctions?.routes?.[routeIndex];
  if (!entry) return "";
  const durations = entry.ys.map((y, k) => y - entry.xs[k]);
  return `
      <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:1rem;margin-top:0.8rem">
        ${renderArcFunctionChart("route-arr", "Arrival time at depot δ(t)", entry.xs, entry.ys, PALETTE[0], {
          marker: { x: entry.xs[0], y: entry.ys[0], color: "var(--cy)", label: `EAT ${formatScheduleTime(entry.ys[0])}` },
        })}
        ${renderArcFunctionChart("route-dur", "Duration Δ(t) = δ(t) − t", entry.xs, durations, PALETTE[1], {
          marker: { x: entry.departure_time, y: entry.duration, color: "var(--gr)", label: `MDT ${formatScheduleTime(entry.duration)} (at t* ${formatScheduleTime(entry.departure_time)})` },
        })}
      </div>
      <div class="meta-line" style="margin-top:0.4rem">Route ready-time function δ over the feasible depot-departure domain (${entry.xs.length} breakpoints, checker fold). EAT = earliest arrival back at the depot; MDT = minimum duration time Δ* = ${formatScheduleTime(entry.duration)}, attained at the optimal departure t* = ${formatScheduleTime(entry.departure_time)}.</div>`;
}

function renderTdScheduleSection(selectedEntry, instanceData, selectedRouteIndex, routeFunctions, routeFunctionsStatus) {
  const schedules = selectedEntry?.td_schedules;
  if (!Array.isArray(schedules) || schedules.length === 0) return "";
  const routeIndex = Math.min(Math.max(selectedRouteIndex, 0), schedules.length - 1);
  const schedule = schedules[routeIndex];
  const timeWindows = Array.isArray(instanceData?.time_windows) ? instanceData.time_windows : null;
  const serviceTimes = Array.isArray(instanceData?.service_times) ? instanceData.service_times : null;
  const options = schedules
    .map((entry, index) => `<option value="${index}"${index === routeIndex ? " selected" : ""}>Route ${index + 1} · ${entry.stops.length} clients · Δ* ${formatScheduleTime(entry.duration)}</option>`)
    .join("");
  const twHeader = timeWindows ? "<th>Time window</th>" : "";
  const rows = [];
  rows.push(`<tr><td class="table-cell-mono">depot</td>${timeWindows ? "<td></td>" : ""}<td></td><td></td><td></td><td class="table-cell-num">${formatScheduleTime(schedule.departure_time)}</td></tr>`);
  for (const stop of schedule.stops) {
    const tw = timeWindows ? `<td class="table-cell-mono">[${formatScheduleTime(Number(timeWindows[stop.node]?.[0]))}, ${formatScheduleTime(Number(timeWindows[stop.node]?.[1]))}]</td>` : "";
    const service = serviceTimes ? formatScheduleTime(Number(serviceTimes[stop.node])) : "";
    rows.push(`<tr><td class="table-cell-mono">${stop.node}</td>${tw}<td class="table-cell-num">${formatScheduleTime(stop.arrival)}</td><td class="table-cell-num">${stop.wait > 0 ? formatScheduleTime(stop.wait) : ""}</td><td class="table-cell-num">${service}</td><td class="table-cell-num">${formatScheduleTime(stop.departure)}</td></tr>`);
  }
  rows.push(`<tr><td class="table-cell-mono">depot</td>${timeWindows ? "<td></td>" : ""}<td class="table-cell-num">${formatScheduleTime(schedule.return_arrival)}</td><td></td><td></td><td></td></tr>`);
  return `
    <section class="mini-card">
      <h3>Schedule</h3>
      <div class="meta-line">Checker-derived schedule: the route is dispatched at its earliest optimal depot departure t* = ${formatScheduleTime(schedule.departure_time)} and achieves the optimal duration Δ* = ${formatScheduleTime(schedule.duration)}.</div>
      <div class="inline-actions" style="margin:0.6rem 0"><select data-schedule-route>${options}</select></div>
      ${renderTdRouteFunctionCharts(routeFunctions, routeFunctionsStatus, routeIndex)}
      <div class="table-wrap" style="margin-top:0.8rem"><table>
        <thead><tr><th>Stop</th>${twHeader}<th>Arrival</th><th>Wait</th><th>Service</th><th>Departure</th></tr></thead>
        <tbody>${rows.join("")}</tbody>
      </table></div>
    </section>`;
}

async function renderInstancePage(payload, options = {}) {
  const inWorkbench = options.inWorkbench === true;
  const pageTitle = inWorkbench ? `Workbench: ${payload.title}` : payload.title;
  const pageIntro = inWorkbench
    ? "Inspect a benchmark instance inside the shared workbench shell while the broader catalog and generation flows are being wired in."
    : "Inspect canonical artifacts, objective-specific BKS entries, and the shared route preview.";
  const breadcrumbs = inWorkbench
    ? [{ label: "Workbench", route_path: "/workbench/" }]
    : payload.breadcrumbs;
  setPage(pageTitle, pageIntro, breadcrumbs, "explorer");
  setStatus(`Loading ${payload.title}…`);
  const instanceData = projectEnuInstanceCoordinates(
    await fetchJsonMemo(artifactHref(payload.artifact_links.vrp_json_path)),
  );
  let geometryMeta = null;
  const hasRouteGeometryEntries = (payload.bks_entries || []).some((entry) => entry?.route_geometry_path);
  const wantsSidecarGeometry =
    (payload.summary.viewer_render_mode === "cached_road" && payload.summary.road_cache_status === "complete") || hasRouteGeometryEntries;
  if (wantsSidecarGeometry && geometryMetaSourcePath(payload.artifact_links)) {
    try {
      geometryMeta = await fetchGeometryMetaMemo(payload.artifact_links);
    } catch (error) {
      console.warn("Unable to load geometry sidecar", error);
    }
  }
  let selectedIndex = 0;
  let selectedEntry = payload.bks_entries[selectedIndex] || null;
  let selectedBksData = selectedEntry ? await fetchJsonMemo(artifactHref(selectedEntry.artifact_path)) : null;
  let selectedRouteGeometryMeta = await routeGeometryMetaForEntry(selectedEntry);
  let selectedScheduleRoute = 0;
  let arcState = null;
  let routeFunctionsData = null;
  let routeFunctionsStatus = "idle";
  const supportsArcFunctions = Boolean(payload.artifact_links.atf_json_path);
  const displayOptions = {
    hiddenRoutes: new Set(),
    depotLegMode: usesRoadMetric(payload.summary) ? "full" : "faded",
    fadedOpacity: 0.25,
    routeOpacity: 1,
    depotStar: true,
  };

  const renderSelectedState = () => {
    const asideCards = [
      inWorkbench ? renderWorkbenchModeCard(payload.route_path) : "",
      inWorkbench ? renderWorkbenchVisualizeSourceCard(payload.route_path) : "",
      renderDisplayOptionsCard(selectedBksData, displayOptions),
      renderCard(
        "Instance Summary",
        `${renderStatGrid([
          ["Problem", payload.summary.problem_type],
          ["Family", payload.summary.benchmark_name],
          ["Variant", payload.summary.metric_variant || "historical"],
          ["Place", payload.summary.place_slug || payload.summary.historical_topology_type || "n/a"],
          ["Size", payload.summary.size_bucket],
          ["Customers", payload.summary.num_customers],
          ["Vehicles", payload.summary.num_vehicles ?? payload.summary.num_vehicles_lb ?? "unlimited"],
          ["Capacity", payload.summary.vehicle_capacity],
          ...(payload.summary.subset ? [["Subset", payload.summary.subset]] : []),
          ...(payload.summary.instance_provider ? [["Provider", payload.summary.instance_provider]] : []),
          ...(payload.summary.authors ? [["Authors", payload.summary.authors]] : []),
          ...(payload.summary.license ? [["License", payload.summary.license_url
            ? { html: `<a href="${escapeHtml(payload.summary.license_url)}" target="_blank" rel="noopener">${escapeHtml(payload.summary.license)}</a>` }
            : payload.summary.license]] : []),
        ])}<div class="badge-row">${(payload.summary.supported_objective_functions || []).map((objective) => badge(objective)).join("")}${payload.summary.historical_topology_type ? badge(payload.summary.historical_topology_type, true) : ""}${payload.summary.historical_tw_type ? badge(`TW${payload.summary.historical_tw_type}`, true) : ""}${payload.summary.subset ? badge(`subset:${payload.summary.subset}`, true) : ""}</div>`,
      ),
      renderGeometryCard(payload.summary),
      renderCard(
        "Artifacts",
        `<ul class="artifact-list">
          <li><a href="${artifactHref(payload.artifact_links.vrp_json_path)}">vrp.json</a></li>
          ${payload.artifact_links.vrp_path ? `<li><a href="${artifactHref(payload.artifact_links.vrp_path)}">vrp</a></li>` : ""}
          ${payload.artifact_links.meta_path ? `<li><a href="${artifactHref(payload.artifact_links.meta_path)}">meta.json</a></li>` : ""}
          ${payload.artifact_links.geo_json_path ? `<li><a href="${artifactHref(payload.artifact_links.geo_json_path)}">geo.json.gz</a></li>` : ""}
          ${payload.artifact_links.manifest_path ? `<li><a href="${artifactHref(payload.artifact_links.manifest_path)}">manifest.json</a></li>` : ""}
          ${payload.artifact_links.atf_json_path ? `<li><a href="${artifactHref(payload.artifact_links.atf_json_path)}">${escapeHtml(payload.artifact_links.atf_json_path.split("/").pop().replace(/^.*?\.atf\./, "atf."))}</a></li>` : ""}
        </ul><div class="meta-line" style="margin-top:0.8rem">Published ${escapeHtml(payload.snapshot.published_at)} from commit ${escapeHtml(payload.snapshot.source_commit)}</div>`,
      ),
      renderCard("BKS Selector", `${renderBksSelector(payload.bks_entries, selectedIndex)}${selectedEntry ? `<div class="mini-card" style="margin-top:0.8rem">${renderStatGrid([["Objective", selectedEntry.objective_function], ["Routes", routesStatValue(selectedEntry)], ["Cost", { html: costSpan(selectedEntry.cost, "stat-cost") }], ...optimalityStatRows(selectedEntry), ["Method", selectedEntry.method || 'n/a'], ["Authors", selectedEntry.authors || 'n/a'], ...(selectedEntry.license ? [["License", selectedEntry.license_url ? { html: `<a href="${escapeHtml(selectedEntry.license_url)}" target="_blank" rel="noopener">${escapeHtml(selectedEntry.license)}</a>` } : selectedEntry.license]] : [])])}<div class="inline-actions" style="margin-top:0.8rem"><a class="mini-link" href="${artifactHref(selectedEntry.artifact_path)}">Download BKS</a></div></div>` : ''}`),
      renderCard(
        "Related Links",
        `<ul class="link-list">
          ${Object.entries(payload.sibling_variant_routes || {}).map(([key, value]) => `<li><a href="${routeHref(value)}">Sibling variant: ${escapeHtml(key)}</a></li>`).join("")}
          ${Object.entries(payload.source_problem_routes || {}).map(([key, value]) => `<li><a href="${routeHref(value)}">Source problem: ${escapeHtml(key)}</a></li>`).join("")}
          ${Object.entries(payload.derived_problem_routes || {}).map(([key, value]) => `<li><a href="${routeHref(value)}">Derived problem: ${escapeHtml(key)}</a></li>`).join("")}
        </ul>`,
      ),
      renderCard(
        "Actions",
        inWorkbench
          ? `<div class="inline-actions"><a class="button-link primary" href="${routeHref(payload.route_path)}">Open Public Page</a><a class="button-link" href="${routeHref('/benchmarks/')}">Browse Benchmarks</a></div>`
          : supportsWorkbenchInstance(payload.summary)
            ? `<div class="inline-actions"><a class="button-link primary" href="${routeHref(payload.workbench_route_path)}?instance=${encodeURIComponent(payload.route_path)}">Open In Workbench</a></div>`
            : `<div class="inline-actions"><a class="button-link primary" href="${routeHref('/benchmarks/')}">Browse Benchmarks</a></div>`,
      ),
    ].filter(Boolean);
    state.aside.innerHTML = asideCards.join("");

    const routeLegend = Array.isArray(selectedBksData?.routes)
      ? `<div class="route-legend">${selectedBksData.routes
          .map(
            (route, index) =>
              `<div class="legend-item"><span class="legend-swatch" style="background:${PALETTE[index % PALETTE.length]}"></span><span>Route ${index + 1} · ${route.length} clients</span></div>`,
          )
          .join("")}</div>`
      : `<div class="empty-state">No route overlay is available for this instance.</div>`;

    state.stage.innerHTML = `
      <div class="viewer-stage">
        ${renderPreviewSvg(instanceData, selectedBksData, selectedEntry, {
          geometryMeta: mergeGeometryMeta(geometryMeta, selectedRouteGeometryMeta),
          metricVariant: payload.summary.metric_variant,
          viewerRenderMode: selectedRouteGeometryMeta ? "cached_road" : payload.summary.viewer_render_mode,
          roadCacheStatus: selectedRouteGeometryMeta ? "complete" : payload.summary.road_cache_status,
          interactiveArcs: supportsArcFunctions,
          displayOptions,
        })}
        <section class="mini-card">
          <h3>Route Legend</h3>
          ${routeLegend}
        </section>
        ${renderArcFunctionsCard(arcState)}
        ${renderTdScheduleSection(selectedEntry, instanceData, selectedScheduleRoute, routeFunctionsData, routeFunctionsStatus)}
      </div>`;

    if (selectedEntry?.route_functions_path && routeFunctionsStatus === "idle") {
      routeFunctionsStatus = "loading";
      fetchJsonMemo(routeFunctionsHref(selectedEntry.route_functions_path))
        .then((data) => {
          routeFunctionsData = data;
          routeFunctionsStatus = "ready";
          renderSelectedState();
        })
        .catch((error) => {
          console.warn("Unable to load the route functions payload", error);
          routeFunctionsStatus = "error";
          renderSelectedState();
        });
    }

    state.aside.querySelectorAll("[data-bks-index]").forEach((button) => {
      button.addEventListener("click", async () => {
        selectedIndex = Number(button.dataset.bksIndex);
        selectedEntry = payload.bks_entries[selectedIndex] || null;
        selectedBksData = selectedEntry ? await fetchJsonMemo(artifactHref(selectedEntry.artifact_path)) : null;
        selectedRouteGeometryMeta = await routeGeometryMetaForEntry(selectedEntry);
        selectedScheduleRoute = 0;
        routeFunctionsData = null;
        routeFunctionsStatus = "idle";
        // Route indices are objective-specific; visibility resets, the
        // rendering preferences carry over.
        displayOptions.hiddenRoutes = new Set();
        renderSelectedState();
      });
    });
    state.aside.querySelectorAll("[data-route-toggle]").forEach((checkbox) => {
      checkbox.addEventListener("change", () => {
        const routeIndex = Number(checkbox.dataset.routeToggle);
        if (checkbox.checked) {
          displayOptions.hiddenRoutes.delete(routeIndex);
        } else {
          displayOptions.hiddenRoutes.add(routeIndex);
        }
        renderSelectedState();
      });
    });
    state.aside.querySelector("[data-routes-all]")?.addEventListener("click", () => {
      displayOptions.hiddenRoutes = new Set();
      renderSelectedState();
    });
    state.aside.querySelector("[data-routes-none]")?.addEventListener("click", () => {
      displayOptions.hiddenRoutes = new Set((selectedBksData?.routes || []).map((_, index) => index));
      renderSelectedState();
    });
    state.aside.querySelector("[data-display-depot-legs]")?.addEventListener("change", (event) => {
      displayOptions.depotLegMode = event.target.value;
      renderSelectedState();
    });
    state.aside.querySelector("[data-display-depot-star]")?.addEventListener("change", (event) => {
      displayOptions.depotStar = event.target.checked;
      renderSelectedState();
    });
    const legsOpacitySlider = state.aside.querySelector("[data-display-legs-opacity]");
    legsOpacitySlider?.addEventListener("input", (event) => {
      const output = state.aside.querySelector("[data-legs-opacity-value]");
      if (output) output.textContent = `${Math.round(Number(event.target.value) * 100)}%`;
    });
    legsOpacitySlider?.addEventListener("change", (event) => {
      displayOptions.fadedOpacity = Number(event.target.value);
      renderSelectedState();
    });
    const routeOpacitySlider = state.aside.querySelector("[data-display-route-opacity]");
    routeOpacitySlider?.addEventListener("input", (event) => {
      const output = state.aside.querySelector("[data-route-opacity-value]");
      if (output) output.textContent = `${Math.round(Number(event.target.value) * 100)}%`;
    });
    routeOpacitySlider?.addEventListener("change", (event) => {
      displayOptions.routeOpacity = Number(event.target.value);
      renderSelectedState();
    });
    if (routeFunctionsStatus === "ready") {
      const entry = routeFunctionsData?.routes?.[Math.min(selectedScheduleRoute, (routeFunctionsData?.routes?.length || 1) - 1)];
      if (entry) {
        const durations = entry.ys.map((y, k) => y - entry.xs[k]);
        attachArcChartHover(state.stage, "route-arr", entry.xs, entry.ys, (t, v) => `depart t = ${formatScheduleTime(t)} → arrival δ(t) = ${formatScheduleTime(v)}`);
        attachArcChartHover(state.stage, "route-dur", entry.xs, durations, (t, v) => `depart t = ${formatScheduleTime(t)} → duration Δ(t) = ${formatScheduleTime(v)}`);
      }
    }
    state.stage.querySelector("[data-schedule-route]")?.addEventListener("change", (event) => {
      selectedScheduleRoute = Number(event.target.value) || 0;
      renderSelectedState();
    });
    if (supportsArcFunctions) {
      state.stage.querySelectorAll(".arc-hit").forEach((segment) => {
        segment.style.cursor = "pointer";
        segment.addEventListener("click", async () => {
          const from = Number(segment.dataset.arcFrom);
          const to = Number(segment.dataset.arcTo);
          arcState = { status: "loading", from, to };
          renderSelectedState();
          try {
            const sidecar = await fetchInstanceAtfArcs(payload.artifact_links.atf_json_path);
            const arc = sidecar.arcs.get(`${from},${to}`);
            if (!arc) throw new Error(`Arc ${from} → ${to} is missing from the ATF sidecar.`);
            arcState = { status: "ready", from, to, xs: arc.xs, ys: arc.ys };
          } catch (error) {
            arcState = { status: "error", from, to, message: String(error?.message || error) };
          }
          renderSelectedState();
        });
      });
      if (arcState?.status === "ready") {
        const ttf = arcState.ys.map((y, k) => y - arcState.xs[k]);
        attachArcChartHover(state.stage, "atf", arcState.xs, arcState.ys, (t, v) => `t = ${formatScheduleTime(t)} → arrival α(t) = ${formatScheduleTime(v)}`);
        attachArcChartHover(state.stage, "ttf", arcState.xs, ttf, (t, v) => `t = ${formatScheduleTime(t)} → travel time τ(t) = ${formatScheduleTime(v)}`);
      }
    }
    setStatus(selectedEntry ? `Showing ${selectedEntry.objective_function}` : `Loaded ${payload.title}`);
  };

  renderSelectedState();
}

function formatPct(pct) {
  if (pct === null || pct === undefined || !Number.isFinite(pct)) return "";
  const sign = pct > 0 ? "+" : (pct < 0 ? "−" : "±");
  return `${sign}${Math.abs(pct).toFixed(2)}%`;
}

function formatSignedDelta(delta) {
  if (delta === null || delta === undefined) return "";
  if (typeof delta === "number" && Number.isFinite(delta)) {
    const sign = delta > 0 ? "+" : (delta < 0 ? "−" : "±");
    const abs = Math.abs(delta);
    const formatted = Number.isInteger(abs) ? String(abs) : abs.toFixed(2);
    return `${sign}${formatted}`;
  }
  return String(delta);
}

function timelineCountsHeadline(counts, options = {}) {
  const initial = options.initial === true;
  if (initial) {
    const parts = [
      counts.instances_added && `+${counts.instances_added} instance${counts.instances_added > 1 ? "s" : ""}`,
      counts.bks_added && `+${counts.bks_added} BKS`,
    ].filter(Boolean);
    return parts.length ? `${parts.join(" · ")} (initial)` : "Initial snapshot";
  }
  const parts = [
    counts.instances_added && `+${counts.instances_added} instance${counts.instances_added > 1 ? "s" : ""}`,
    counts.instances_removed && `−${counts.instances_removed} instance${counts.instances_removed > 1 ? "s" : ""}`,
    counts.bks_improved && `${counts.bks_improved} BKS improved`,
    counts.bks_regressed && `${counts.bks_regressed} BKS regressed`,
    counts.bks_added && `+${counts.bks_added} BKS`,
    counts.bks_removed && `−${counts.bks_removed} BKS`,
  ].filter(Boolean);
  return parts.length ? parts.join(" · ") : "No instance- or BKS-level changes";
}

function renderAffectedBadgeRow(scope) {
  const badges = [
    ...(scope.affected_problem_types || []).map((value) => badge(value)),
    ...(scope.affected_benchmark_names || []).map((value) => badge(value, true)),
    ...(scope.affected_objective_functions || []).map((value) => badge(value)),
  ];
  return badges.length ? `<div class="badge-row">${badges.join("")}</div>` : "";
}

function renderHistoryLedger(payload) {
  setPage("History", "Every published website state is tied to an explicit repository snapshot.", [], "editorial");
  const currentEntry = payload.entries[0];
  const repoCommitUrl = currentEntry
    ? `https://github.com/ANR-MAMUT/MAMUT-routing/commit/${encodeURIComponent(currentEntry.snapshot.source_commit)}`
    : "https://github.com/ANR-MAMUT/MAMUT-routing";
  state.aside.innerHTML = [
    renderCard(
      "Current Publication",
      currentEntry
        ? `<p>${escapeHtml(currentEntry.summary)}</p>${renderStatGrid([["Snapshot", payload.current_snapshot_id], ["Published", currentEntry.snapshot.published_at], ["Commit", currentEntry.snapshot.source_commit]])}`
        : '<div class="empty-state">No history entries yet.</div>',
    ),
    renderCard(
      "Repository",
      `<p>The public site is a static publication ledger, not a live reflection of repository HEAD. Compare the published commit with the repository to check whether this publication is up to date.</p><div class="inline-actions"><a class="button-link primary" href="https://github.com/ANR-MAMUT/MAMUT-routing" target="_blank" rel="noopener">GitHub repository</a><a class="button-link" href="${repoCommitUrl}" target="_blank" rel="noopener">Published commit</a></div>`,
    ),
  ].join("");
  if (!currentEntry) {
    state.stage.innerHTML = `<div class="empty-state">No history entries are available.</div>`;
    setStatus(`Loaded 0 history entries`);
    return;
  }
  const lastIdx = payload.entries.length - 1;
  const nodes = payload.entries.map((entry, idx) => {
    const counts = entry.change_counts || {};
    const isInitial = idx === lastIdx;
    const headline = timelineCountsHeadline(counts, { initial: isInitial });
    const dateOnly = String(entry.snapshot.published_at || "").slice(0, 10) || entry.snapshot.published_at;
    const isCurrentAttr = idx === 0 ? ' data-current="true"' : "";
    const initialTag = isInitial ? `<span class="badge alt timeline-initial-tag">initial</span>` : "";
    return `<li class="timeline-node"${isCurrentAttr}>
      <span class="timeline-dot"></span>
      <article class="timeline-card">
        <header class="timeline-header">
          <span class="timeline-date">${escapeHtml(dateOnly)}</span>
          <code class="meta-line">${escapeHtml(entry.snapshot.source_commit)}</code>
          ${initialTag}
        </header>
        <p class="timeline-summary">${escapeHtml(entry.summary)}</p>
        <p class="timeline-counts">${escapeHtml(headline)}</p>
        ${renderAffectedBadgeRow(entry)}
        <div class="inline-actions" style="margin-top:0.8rem">
          <a class="button-link primary" href="${routeHref(entry.detail_route_path)}">Open snapshot</a>
          <a class="button-link" href="${routeHref('/benchmarks/')}">Browse benchmarks</a>
        </div>
      </article>
    </li>`;
  }).join("");
  state.stage.innerHTML = `<ol class="history-timeline">${nodes}</ol>`;
  setStatus(`Loaded ${payload.entries.length} history entries`);
}

function renderChangeRowFamily(change) {
  const cls = change.kind === "added" ? "change-add" : "change-remove";
  const sign = change.kind === "added" ? "+" : "−";
  return `<li class="${cls}">${sign} ${escapeHtml(change.problem_type)} / ${escapeHtml(change.benchmark_name)}</li>`;
}

function renderChangeRowInstance(change) {
  const cls = change.kind === "added" ? "change-add" : "change-remove";
  const sign = change.kind === "added" ? "+" : "−";
  const variant = change.metric_variant ? ` · ${escapeHtml(change.metric_variant)}` : "";
  const place = change.place_slug ? ` · ${escapeHtml(change.place_slug)}` : "";
  return `<li class="${cls}">${sign} <code>${escapeHtml(change.instance_name)}</code> · n=${escapeHtml(change.num_customers)}${variant}${place}</li>`;
}

function renderChangeRowBks(change) {
  let cls;
  if (change.kind === "added") cls = "change-add";
  else if (change.kind === "removed") cls = "change-remove";
  else if (change.kind === "improved") cls = "change-improve";
  else cls = "change-regress";

  const variant = change.metric_variant ? ` · ${escapeHtml(change.metric_variant)}` : "";
  const place = change.place_slug ? ` · ${escapeHtml(change.place_slug)}` : "";
  const head = `<code>${escapeHtml(change.instance_name)}</code> · n=${escapeHtml(change.num_customers)}${variant}${place}`;

  const hierarchical = isHierarchicalObjective(change);
  const valueHtml = (v) => {
    const cost = costSpan(v.cost, "change-cost-value");
    if (v.num_routes == null) return cost;
    const routesText = escapeHtml(String(v.num_routes));
    const routesHtml = hierarchical ? `<span class="change-cost-value">${routesText}</span>` : routesText;
    return `${routesHtml} / ${cost}`;
  };

  if (change.kind === "added") {
    const v = change.new || {};
    const meta = v.method ? ` <span class="meta-line">${escapeHtml(v.method)}</span>` : "";
    return `<li class="${cls}">+ ${head} · <span class="change-to">${valueHtml(v)}</span>${meta}</li>`;
  }
  if (change.kind === "removed") {
    const v = change.prev || {};
    return `<li class="${cls}">− ${head} · <span class="change-from">${valueHtml(v)}</span></li>`;
  }
  // improved / regressed
  const prev = change.prev || {};
  const next = change.new || {};
  const deltaParts = [];
  if (change.routes_delta != null && change.routes_delta !== 0) {
    deltaParts.push(`${formatSignedDelta(change.routes_delta)} veh`);
  }
  if (change.cost_delta != null) {
    const pctSuffix = change.cost_pct != null ? `, ${formatPct(change.cost_pct)}` : "";
    deltaParts.push(`${formatSignedDelta(change.cost_delta)}${pctSuffix}`);
  }
  const deltaText = deltaParts.length ? ` <span class="change-delta">(${deltaParts.join(" · ")})</span>` : "";
  const meta = next.method ? ` <span class="meta-line">${escapeHtml(next.method)}</span>` : "";
  return `<li class="${cls}">${head} · <span class="change-from">${valueHtml(prev)}</span> → <span class="change-to">${valueHtml(next)}</span>${deltaText}${meta}</li>`;
}

function renderFamilyChangeSection(changes) {
  const added = changes.filter((c) => c.kind === "added");
  const removed = changes.filter((c) => c.kind === "removed");
  const summary = `Families · +${added.length} / −${removed.length}`;
  const body = changes.length
    ? `<ul class="change-list">${changes.map(renderChangeRowFamily).join("")}</ul>`
    : `<p class="meta-line">No family-level changes.</p>`;
  return `<details class="change-section"><summary>${escapeHtml(summary)}</summary>${body}</details>`;
}

function renderInstanceChangeSection(changes) {
  const added = changes.filter((c) => c.kind === "added");
  const removed = changes.filter((c) => c.kind === "removed");
  const summary = `Instances · +${added.length} / −${removed.length}`;
  const groupBy = (list) => {
    const map = new Map();
    for (const c of list) {
      const key = `${c.problem_type} / ${c.benchmark_name}`;
      if (!map.has(key)) map.set(key, []);
      map.get(key).push(c);
    }
    return [...map.entries()];
  };
  const renderGroup = (kind, list, sign) => {
    if (list.length === 0) return "";
    const header = `${kind === "added" ? "Added" : "Removed"} · ${sign}${list.length}`;
    const groups = groupBy(list)
      .map(([key, items]) => `<details class="change-subsection"><summary>${escapeHtml(key)} · ${sign}${items.length}</summary><ul class="change-list">${items.map(renderChangeRowInstance).join("")}</ul></details>`)
      .join("");
    return `<details class="change-subsection"><summary>${escapeHtml(header)}</summary>${groups}</details>`;
  };
  const body = changes.length
    ? `${renderGroup("added", added, "+")}${renderGroup("removed", removed, "−")}`
    : `<p class="meta-line">No instance-level changes.</p>`;
  return `<details class="change-section"><summary>${escapeHtml(summary)}</summary>${body}</details>`;
}

function renderBksChangeSection(changes) {
  const buckets = { added: [], removed: [], improved: [], regressed: [] };
  for (const c of changes) {
    if (buckets[c.kind]) buckets[c.kind].push(c);
  }
  const summary = `BKS · +${buckets.added.length} / −${buckets.removed.length} / ${buckets.improved.length} improved / ${buckets.regressed.length} regressed`;
  const groupBy = (list) => {
    const map = new Map();
    for (const c of list) {
      const key = `${c.problem_type} / ${c.benchmark_name} · ${c.objective_function}`;
      if (!map.has(key)) map.set(key, []);
      map.get(key).push(c);
    }
    return [...map.entries()];
  };
  const renderBucket = (label, list, sign) => {
    if (list.length === 0) return "";
    const groups = groupBy(list)
      .map(([key, items]) => `<details class="change-subsection"><summary>${escapeHtml(key)} · ${sign}${items.length}</summary><ul class="change-list">${items.map(renderChangeRowBks).join("")}</ul></details>`)
      .join("");
    return `<details class="change-subsection"><summary>${escapeHtml(label)} · ${sign}${list.length}</summary>${groups}</details>`;
  };
  const body = changes.length
    ? `${renderBucket("Improved", buckets.improved, "")}${renderBucket("Regressed", buckets.regressed, "")}${renderBucket("Added", buckets.added, "+")}${renderBucket("Removed", buckets.removed, "−")}`
    : `<p class="meta-line">No BKS-level changes.</p>`;
  return `<details class="change-section"><summary>${escapeHtml(summary)}</summary>${body}</details>`;
}

function renderChangesCard(changeLog) {
  if (!changeLog) {
    return renderCard("Changes", `<p class="empty-state">No change log available for this snapshot.</p>`);
  }
  const banner = changeLog.is_initial
    ? `<p class="meta-line initial-banner">Initial snapshot: full inventory shown as additions.</p>`
    : "";
  const headline = timelineCountsHeadline(changeLog.counts || {}, { initial: changeLog.is_initial });
  return renderCard(
    "Changes",
    `${banner}<p class="meta-line">${escapeHtml(headline)}</p>${renderFamilyChangeSection(changeLog.family_changes || [])}${renderInstanceChangeSection(changeLog.instance_changes || [])}${renderBksChangeSection(changeLog.bks_changes || [])}`,
  );
}

function renderHistoryDetail(payload) {
  setPage(payload.title, "Snapshot-level summary for one published website build.", payload.breadcrumbs, "editorial");
  state.aside.innerHTML = [
    renderCard(
      "Snapshot Metadata",
      `${renderStatGrid([
        ["Snapshot", payload.snapshot.snapshot_id],
        ["Published", payload.snapshot.published_at],
        ["Commit", payload.snapshot.source_commit],
        ["Summary", payload.summary],
      ])}`,
    ),
    renderCard(
      "Affected Scope",
      renderAffectedBadgeRow(payload) || '<p class="meta-line">No families or BKS were modified by this publication.</p>',
    ),
  ].join("");
  state.stage.innerHTML = [
    renderChangesCard(payload.change_log),
    `<article class="mini-card"><h3>Counts</h3>${renderStatGrid([
      ["Problems", payload.counts.problem_count],
      ["Families", payload.counts.family_count],
      ["Variants", payload.counts.variant_count],
      ["Instances", payload.counts.instance_count],
      ["BKS", payload.counts.bks_count],
    ])}</article>`,
    `<article class="mini-card"><h3>Actions</h3><div class="inline-actions"><a class="button-link primary" href="${routeHref('/benchmarks/')}">Browse Benchmarks</a><a class="button-link" href="${routeHref('/history/')}">Back to History</a></div></article>`,
  ].join("");
  setStatus(`Loaded snapshot ${payload.snapshot.snapshot_id}`);
}

function matchesWorkbenchValue(left, right) {
  return String(left ?? "").toLowerCase() === String(right ?? "").toLowerCase();
}

function selectWorkbenchOption(options, predicate) {
  return options.find(predicate) || options[0] || null;
}

async function buildWorkbenchBenchmarkSelection(seed = {}) {
  const rootPayload = await fetchWorkbenchPayloadForRoute("/benchmarks/");
  const problemCards = Array.isArray(rootPayload?.problems) ? rootPayload.problems : [];
  const selectedProblem = selectWorkbenchOption(problemCards, (problem) => matchesWorkbenchValue(problem.problem_type, seed.problemType));

  const problemPayload = selectedProblem ? await fetchWorkbenchPayloadForRoute(selectedProblem.route_path) : null;
  const familyCards = Array.isArray(problemPayload?.families) ? problemPayload.families : [];
  const selectedFamily = selectWorkbenchOption(familyCards, (family) => matchesWorkbenchValue(family.benchmark_name, seed.benchmarkName));

  const familyPayload = selectedFamily ? await fetchWorkbenchPayloadForRoute(selectedFamily.route_path) : null;
  let activeCatalogPayload = familyPayload;

  const variantEntries = Array.isArray(familyPayload?.variant_routes) ? familyPayload.variant_routes : [];
  const selectedVariant = variantEntries.length > 0
    ? selectWorkbenchOption(variantEntries, (entry) => matchesWorkbenchValue(entry.key, seed.metricVariant))
    : null;
  if (selectedVariant) {
    activeCatalogPayload = await fetchWorkbenchPayloadForRoute(selectedVariant.route_path);
  }

  const placeEntries = Array.isArray(activeCatalogPayload?.place_routes) ? activeCatalogPayload.place_routes : [];
  const selectedPlace = placeEntries.length > 0
    ? selectWorkbenchOption(placeEntries, (entry) => matchesWorkbenchValue(entry.key, seed.placeSlug))
    : null;
  if (selectedPlace) {
    activeCatalogPayload = await fetchWorkbenchPayloadForRoute(selectedPlace.route_path);
  }

  const sizeEntries = Array.isArray(activeCatalogPayload?.size_routes) ? activeCatalogPayload.size_routes : [];
  const selectedSize = sizeEntries.length > 0
    ? selectWorkbenchOption(sizeEntries, (entry) => matchesWorkbenchValue(entry.key, seed.sizeBucket))
    : null;
  if (selectedSize) {
    activeCatalogPayload = await fetchWorkbenchPayloadForRoute(selectedSize.route_path);
  }

  const items = Array.isArray(activeCatalogPayload?.items) ? activeCatalogPayload.items : [];
  const selectedInstance = selectWorkbenchOption(items, (item) => normalizeRoute(item.route_path) === normalizeRoute(seed.instanceRoute || ""));
  const instancePayload = selectedInstance ? await fetchWorkbenchPayloadForRoute(selectedInstance.route_path) : null;

  return {
    rootPayload,
    problemCards,
    selectedProblem,
    problemPayload,
    familyCards,
    selectedFamily,
    familyPayload,
    activeCatalogPayload,
    variantEntries,
    selectedVariant,
    placeEntries,
    selectedPlace,
    sizeEntries,
    selectedSize,
    items,
    selectedInstance,
    instancePayload,
  };
}

async function loadWorkbenchInstancePreview(instancePayload, preferredObjectiveFunction = null) {
  if (!instancePayload) {
    return null;
  }

  const bksEntries = Array.isArray(instancePayload.bks_entries) ? instancePayload.bks_entries : [];
  let selectedIndex = bksEntries.findIndex((entry) => matchesWorkbenchValue(entry.objective_function, preferredObjectiveFunction));
  if (selectedIndex < 0) {
    selectedIndex = 0;
  }
  const selectedEntry = bksEntries[selectedIndex] || null;

  const hasCachedRoad = instancePayload.summary.viewer_render_mode === "cached_road"
    && instancePayload.summary.road_cache_status === "complete"
    && geometryMetaSourcePath(instancePayload.artifact_links);
  const [instanceData, geometryMeta, selectedBksData] = await Promise.all([
    fetchJsonMemo(artifactHref(instancePayload.artifact_links.vrp_json_path)).then(projectEnuInstanceCoordinates),
    hasCachedRoad
      ? fetchGeometryMetaMemo(instancePayload.artifact_links).catch((error) => {
          console.warn("Unable to load geometry sidecar", error);
          return null;
        })
      : Promise.resolve(null),
    selectedEntry ? fetchJsonMemo(artifactHref(selectedEntry.artifact_path)) : Promise.resolve(null),
  ]);

  return {
    instanceData,
    geometryMeta,
    selectedIndex,
    selectedEntry,
    selectedBksData,
  };
}

function degToRad(value) {
  return (value * Math.PI) / 180.0;
}

function radToDeg(value) {
  return (value * 180.0) / Math.PI;
}

function geodeticToEcef(latDeg, lonDeg, altitude) {
  const lat = degToRad(latDeg);
  const lon = degToRad(lonDeg);
  const sinLat = Math.sin(lat);
  const cosLat = Math.cos(lat);
  const sinLon = Math.sin(lon);
  const cosLon = Math.cos(lon);
  const radius = WGS84_A / Math.sqrt(1 - WGS84_E2 * sinLat * sinLat);

  return {
    x: (radius + altitude) * cosLat * cosLon,
    y: (radius + altitude) * cosLat * sinLon,
    z: (radius * (1 - WGS84_E2) + altitude) * sinLat,
  };
}

function ecefToGeodetic(x, y, z) {
  const semiMinorAxis = WGS84_A * (1 - WGS84_F);
  const ep2 = (WGS84_A * WGS84_A - semiMinorAxis * semiMinorAxis) / (semiMinorAxis * semiMinorAxis);
  const p = Math.sqrt(x * x + y * y);
  const theta = Math.atan2(WGS84_A * z, semiMinorAxis * p);
  const sinTheta = Math.sin(theta);
  const cosTheta = Math.cos(theta);
  const lon = Math.atan2(y, x);
  const lat = Math.atan2(
    z + ep2 * semiMinorAxis * sinTheta * sinTheta * sinTheta,
    p - WGS84_E2 * WGS84_A * cosTheta * cosTheta * cosTheta,
  );
  const sinLat = Math.sin(lat);
  const radius = WGS84_A / Math.sqrt(1 - WGS84_E2 * sinLat * sinLat);
  const altitude = p / Math.cos(lat) - radius;
  return { lat: radToDeg(lat), lon: radToDeg(lon), alt: altitude };
}

function enuToGeodetic(east, north, up, refLatDeg, refLonDeg, refAlt) {
  const ref = geodeticToEcef(refLatDeg, refLonDeg, refAlt);
  const lat0 = degToRad(refLatDeg);
  const lon0 = degToRad(refLonDeg);
  const sinLat = Math.sin(lat0);
  const cosLat = Math.cos(lat0);
  const sinLon = Math.sin(lon0);
  const cosLon = Math.cos(lon0);

  const dx = -sinLon * east - sinLat * cosLon * north + cosLat * cosLon * up;
  const dy = cosLon * east - sinLat * sinLon * north + cosLat * sinLon * up;
  const dz = cosLat * north + sinLat * up;

  return ecefToGeodetic(ref.x + dx, ref.y + dy, ref.z + dz);
}

function safeHeader(getter, key, fallback) {
  try {
    return getter(key);
  } catch (_error) {
    return fallback;
  }
}

function parseRefLla(comment) {
  const match = comment.match(/LLA\(\s*([-+]?\d*\.?\d+)\s*,\s*([-+]?\d*\.?\d+)\s*,\s*([-+]?\d*\.?\d+)\s*\)/i);
  if (!match) {
    return null;
  }
  return {
    lat: Number.parseFloat(match[1]),
    lon: Number.parseFloat(match[2]),
    alt: Number.parseFloat(match[3]),
  };
}

function extractSection(text, sectionName, nextSectionName) {
  const pattern = new RegExp(`${sectionName}\\s*([\\s\\S]*?)\\n${nextSectionName}\\b`, "i");
  const match = text.match(pattern);
  if (!match) {
    throw new Error(`Could not extract ${sectionName}.`);
  }
  return match[1].trim();
}

function parseNodeCoords(sectionText) {
  return sectionText
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line) => {
      const parts = line.split(/\s+/);
      if (parts.length < 3) {
        throw new Error(`Invalid NODE_COORD_SECTION row: '${line}'`);
      }
      return {
        id: Number.parseInt(parts[0], 10),
        x: Number.parseFloat(parts[1]),
        y: Number.parseFloat(parts[2]),
      };
    });
}

function parseDemands(sectionText) {
  const demands = new Map();
  for (const line of sectionText.split(/\r?\n/)) {
    const trimmed = line.trim();
    if (!trimmed) {
      continue;
    }
    const parts = trimmed.split(/\s+/);
    if (parts.length < 2) {
      continue;
    }
    demands.set(Number.parseInt(parts[0], 10), Number.parseInt(parts[1], 10));
  }
  return demands;
}

function parseSol(text) {
  const routes = [];
  for (const line of text.split(/\r?\n/)) {
    const match = line.match(/^\s*Route\s*#\d+\s*:\s*(.*)$/i);
    if (!match) {
      continue;
    }
    const stops = match[1]
      .trim()
      .split(/\s+/)
      .filter(Boolean)
      .map((value) => Number.parseInt(value, 10))
      .filter((value) => Number.isInteger(value));
    routes.push(stops);
  }
  if (routes.length === 0) {
    throw new Error("No 'Route #k: ...' lines found in solution file.");
  }
  return routes;
}

function normalizeUploadedSolutionRoutes(rawRoutes, dimension) {
  const allStops = rawRoutes.flat();
  if (allStops.length === 0) {
    throw new Error("Solution contains no customer stops.");
  }

  const customerCount = Math.max(0, dimension - 1);
  const minId = Math.min(...allStops);
  const maxId = Math.max(...allStops);
  let mode = "customer-1based";
  let transform = (value) => value;

  if (minId >= 1 && maxId <= customerCount) {
    mode = "customer-1based";
    transform = (value) => value;
  } else if (minId >= 0 && maxId <= customerCount - 1 && allStops.includes(0)) {
    mode = "customer-0based";
    transform = (value) => value + 1;
  } else if (minId >= 2 && maxId <= dimension) {
    mode = "instance-node-id";
    transform = (value) => value - 1;
  } else {
    throw new Error("Unable to normalize solution routes against the uploaded instance dimension.");
  }

  const routes = rawRoutes.map((route) => route.map((value) => transform(Number(value))).filter((value) => value !== 0));
  const invalidStops = routes.flat().filter((value) => value < 1 || value > customerCount);
  if (invalidStops.length > 0) {
    throw new Error(`Route contains invalid customer indices after normalization: ${invalidStops.slice(0, 6).join(", ")}`);
  }

  const uniqueCustomers = new Set(routes.flat());
  return {
    routes,
    info: {
      mode,
      coverage: `${uniqueCustomers.size}/${customerCount}`,
    },
  };
}

function parseVrpText(text, fileName) {
  const getHeaderValue = (key) => {
    const pattern = new RegExp(`^\\s*${key}\\s*:\\s*(.+)$`, "im");
    const match = text.match(pattern);
    if (!match) {
      throw new Error(`Missing header: ${key}`);
    }
    return match[1].trim();
  };

  const name = safeHeader(getHeaderValue, "NAME", fileName.replace(/\.vrp$/i, ""));
  const comment = safeHeader(getHeaderValue, "COMMENT", "");
  const dimension = Number.parseInt(getHeaderValue("DIMENSION"), 10);
  const capacity = Number.parseInt(getHeaderValue("CAPACITY"), 10);
  if (!Number.isFinite(dimension) || dimension < 2) {
    throw new Error("Invalid DIMENSION value.");
  }

  const ref = parseRefLla(comment);
  if (!ref) {
    throw new Error("COMMENT does not contain reference LLA(lat, lon, alt).");
  }

  const nodeSection = extractSection(text, "NODE_COORD_SECTION", "DEMAND_SECTION");
  const demandSection = extractSection(text, "DEMAND_SECTION", "DEPOT_SECTION");
  const rawNodes = parseNodeCoords(nodeSection);
  const demands = parseDemands(demandSection);
  if (rawNodes.length !== dimension) {
    throw new Error(`NODE_COORD_SECTION has ${rawNodes.length} rows, expected ${dimension}.`);
  }

  const coordinates = rawNodes.map((node) => {
    const geo = enuToGeodetic(node.x, node.y, 0.0, ref.lat, ref.lon, ref.alt);
    return [geo.lon, geo.lat];
  });

  return {
    name,
    dimension,
    capacity,
    depot: 0,
    coordinates,
    demands: Array.from({ length: dimension }, (_value, index) => demands.get(index + 1) || 0),
  };
}

function projectEnuInstanceCoordinates(payload) {
  const refPayload = payload?.reference_lla;
  const refLat = Number(refPayload?.lat);
  const refLon = Number(refPayload?.lon);
  if (!Number.isFinite(refLat) || !Number.isFinite(refLon) || !Array.isArray(payload?.coordinates)) {
    return payload;
  }
  const refAlt = Number.isFinite(Number(refPayload?.alt)) ? Number(refPayload.alt) : 0;
  return {
    ...payload,
    coordinates: payload.coordinates.map((point) => {
      if (!Array.isArray(point) || point.length < 2) {
        return point;
      }
      const geo = enuToGeodetic(Number(point[0]), Number(point[1]), 0.0, refLat, refLon, refAlt);
      return [geo.lon, geo.lat];
    }),
  };
}

function parseUploadedInstanceJson(payload, fileName) {
  const projected = projectEnuInstanceCoordinates(payload);
  const coordinates = Array.isArray(projected?.coordinates)
    ? projected.coordinates.map(normalizeGeometryPoint)
    : [];
  if (coordinates.length === 0 || coordinates.some((point) => !point)) {
    throw new Error(`JSON instance '${fileName}' does not expose a usable coordinates array.`);
  }

  return {
    name: payload.instance_id || payload.instance_name || payload.name || fileName,
    dimension: coordinates.length,
    capacity: Number.isFinite(Number(payload.vehicle_capacity)) ? Number(payload.vehicle_capacity) : Number(payload.capacity) || null,
    depot: Number.isFinite(Number(payload.depot)) ? Number(payload.depot) : 0,
    coordinates,
    demands: Array.isArray(payload.demands) ? payload.demands.map((value) => Number(value) || 0) : Array.from({ length: coordinates.length }, () => 0),
  };
}

function parseUploadedInstanceText(text, fileName) {
  if (/\.json$/i.test(fileName)) {
    return parseUploadedInstanceJson(JSON.parse(text), fileName);
  }
  return parseVrpText(text, fileName);
}

function parseUploadedSolutionText(text, fileName, dimension) {
  const rawRoutes = /\.json$/i.test(fileName)
    ? (() => {
        const payload = JSON.parse(text);
        if (Array.isArray(payload)) {
          return payload;
        }
        if (Array.isArray(payload?.routes)) {
          return payload.routes;
        }
        throw new Error(`JSON solution '${fileName}' does not expose a routes array.`);
      })()
    : parseSol(text);
  return normalizeUploadedSolutionRoutes(rawRoutes, dimension);
}

function parseUploadedMetaText(text, fileName) {
  const payload = JSON.parse(text);
  if (!Array.isArray(payload?.nodes)) {
    throw new Error(`Metadata sidecar '${fileName}' does not expose a nodes array.`);
  }
  return payload;
}

function uploadedRouteLoad(route, instanceData) {
  return route.reduce((total, stopIndex) => {
    const demand = Number(instanceData?.demands?.[stopIndex]);
    return total + (Number.isFinite(demand) ? demand : 0);
  }, 0);
}

function renderObjectives(payload) {
  setPage(payload.title, "Objective semantics are part of the benchmark contract, not a display detail.", [], "editorial");
  state.aside.innerHTML = renderCard(
    "Objective Quick Nav",
    `<div class="chip-row">${payload.explainers.map((explainer) => `<a class="selector-chip" href="#${escapeHtml(explainer.objective_function)}">${escapeHtml(explainer.short_label)}</a>`).join("")}</div>`,
  );
  state.stage.innerHTML = `<div class="explainer-grid">${payload.explainers
    .map(
      (explainer) => `<article class="mini-card" id="${escapeHtml(explainer.objective_function)}"><div class="badge-row">${badge(explainer.short_label)}${badge(explainer.objective_function, true)}</div><h3>${escapeHtml(explainer.title)}</h3><p>${formatInlineCode(explainer.description)}</p><ul class="plain-list">${explainer.interpretation_notes.map((note) => `<li>${formatInlineCode(note)}</li>`).join("")}</ul><h4 style="margin-top:0.9rem">Related Families</h4><ul class="link-list">${explainer.related_routes.map((entry) => `<li><a href="${routeHref(entry.route_path)}">${escapeHtml(entry.label)}</a> <span class="meta-line">${entry.instance_count} instances · ${entry.bks_count} BKS</span></li>`).join("")}</ul></article>`,
    )
    .join("")}</div>`;
  setStatus(`Loaded ${payload.explainers.length} objective guides`);
}

function renderProject(payload) {
  setPage(payload.title, payload.subtitle, [], "project");
  const projectPages = (payload.related_pages || [])
    .map(
      (page) => `<article class="mini-card"><h3>${escapeHtml(page.title)}</h3><p>${escapeHtml(page.description)}</p><div class="inline-actions"><a class="button-link" href="${routeHref(page.route_path)}">Open page</a></div></article>`,
    )
    .join("");
  state.aside.innerHTML = [
    renderCard(
      "Project Record",
      `${renderStatGrid([
        ["Code", payload.anr_project_code],
        ["Project", payload.anr_project_title],
        ["Source", { html: `<a class="mini-link" href="${escapeHtml(payload.anr_project_url)}" target="_blank" rel="noopener">ANR official page</a>` }],
      ])}`,
    ),
    renderCard(
      "Repos and Related links",
      `${renderStatGrid([
        ["Source", { html: renderGithubMiniLink("ANR-MAMUT/MAMUT-routing", "https://github.com/ANR-MAMUT/MAMUT-routing") }],
        ["mamut-routing-lib", { html: renderGithubMiniLink("ANR-MAMUT/MAMUT-routing-lib", "https://github.com/ANR-MAMUT/MAMUT-routing-lib") }],
        ["Organization", { html: renderGithubMiniLink("ANR-MAMUT", "https://github.com/ANR-MAMUT") }],
      ])}`,
    ),
  ].join("");

  const factCards = (payload.facts || [])
    .map((fact) => {
      const value = fact.href
        ? `<a class="mini-link" href="${escapeHtml(fact.href)}" target="_blank" rel="noopener">${escapeHtml(fact.value)}</a>`
        : escapeHtml(fact.value);
      return `<article class="project-fact"><span>${escapeHtml(fact.label)}</span><strong>${value}</strong></article>`;
    })
    .join("");
  const participantLogos = PROJECT_PARTICIPANT_LOGOS
    .map(
      (logo) => `<a class="project-logo-card${logo.wide ? " project-logo-card-wide" : ""}" href="${escapeHtml(logo.href)}" target="_blank" rel="noopener noreferrer" aria-label="${escapeHtml(logo.label)} (opens in a new tab)">
        <img src="${siteAssetHref(logo.src)}" alt="${escapeHtml(logo.label)} logo" loading="lazy" />
        <span class="project-logo-caption">${escapeHtml(logo.label)}</span>
      </a>`,
    )
    .join("");

  state.stage.innerHTML = `
    <div class="project-page">
      <section class="mini-card project-lead">
        <div class="project-lead-header">
          <img class="project-lead-logo" src="${siteAssetHref(MAMUT_PROJECT_LOGO_PATH)}" alt="MAMUT project logo" />
          <div>
            <div class="badge-row">${badge(payload.anr_project_code)}${badge("ANR MAMUT", true)}</div>
            <h2>${escapeHtml(payload.anr_project_title)}</h2>
          </div>
        </div>
        <p>${escapeHtml(payload.anr_context)}</p>
      </section>
      <section class="mini-card">
        <h3>Project Pages</h3>
        ${projectPages ? `<div class="family-grid">${projectPages}</div>` : `<div class="empty-state">No project sub-pages are published yet.</div>`}
      </section>
      <section class="mini-card project-logo-panel">
        <h3>Participants</h3>
        <div class="project-logo-grid">${participantLogos}</div>
      </section>
      <section class="project-fact-grid">${factCards}</section>
    </div>`;
  setStatus(`Loaded ${payload.anr_project_code}`);
}

function renderProjectTextPage(payload) {
  setPage(payload.title, payload.subtitle, payload.breadcrumbs || [], "project");
  state.aside.innerHTML = [
    renderCard(
      "Project",
      `<div class="inline-actions"><a class="button-link primary" href="${routeHref(payload.project_route_path || "/project/")}">Back to Project</a></div>`,
    ),
    renderCard(
      "Snapshot",
      renderStatGrid([
        ["Snapshot", payload.snapshot?.snapshot_id || "n/a"],
        ["Generated", payload.generated_at || "n/a"],
      ]),
    ),
    renderCard(
      "Source",
      `<div class="inline-actions"><a class="mini-link" href="https://github.com/ANR-MAMUT/MAMUT-routing" target="_blank" rel="noopener">GitHub repository</a></div>`,
    ),
  ].join("");
  state.stage.innerHTML = `<article class="context-prose">${renderMarkdownBlocks(payload.markdown)}</article>`;
  setStatus(`Loaded ${payload.title}`);
}

function renderUnknownPayload(payload) {
  setPage(payload.payload_kind || "Unknown", "No renderer is registered for this payload yet.", [], "editorial");
  state.aside.innerHTML = renderCard("Payload Kind", `<p class="mono-block">${escapeHtml(payload.payload_kind || 'unknown')}</p>`);
  state.stage.innerHTML = `<pre class="mono-block">${escapeHtml(JSON.stringify(payload, null, 2))}</pre>`;
  setStatus("Rendered fallback view");
}

function applyTheme(theme) {
  document.documentElement.dataset.theme = theme;
  const switchInput = document.getElementById("themeSwitch");
  if (switchInput) {
    switchInput.checked = theme === "dark";
  }
  localStorage.setItem("mamut-theme", theme);
}

function setupThemeToggle() {
  // The initial theme is applied by the inline bootstrap script in the HTML
  // <head> (see site_webapp.py:THEME_INIT_SCRIPT) so that the first paint is
  // already correct. Here we only sync the sun/moon pill to the resolved value
  // and wire the click handler; the active side is styled from html[data-theme].
  const currentTheme = document.documentElement.dataset.theme === "dark" ? "dark" : "light";
  const switchInput = document.getElementById("themeSwitch");
  if (!switchInput) {
    return;
  }
  switchInput.checked = currentTheme === "dark";
  switchInput.addEventListener("change", (event) => {
    applyTheme(event.target.checked ? "dark" : "light");
  });
}

async function renderPayloadPage() {
  const payload = await fetchJson(payloadUrlForRoute(state.routePath));
  switch (payload.payload_kind) {
    case "home_page":
      await renderHome(payload);
      break;
    case "benchmarks_index":
      renderBenchmarksIndex(payload);
      break;
    case "problem_index":
    case "family_index":
    case "variant_index":
    case "place_index":
    case "size_index":
    case "subset_index":
      if (payload.payload_kind === "problem_index") {
        renderProblemIndex(payload);
      } else {
        renderCatalogIndex(payload);
      }
      break;
    case "instance_page":
      await renderInstancePage(payload);
      break;
    case "site_history":
      renderHistoryLedger(payload);
      break;
    case "history_detail":
      renderHistoryDetail(payload);
      break;
    case "project_page":
      renderProject(payload);
      break;
    case "project_text_page":
      renderProjectTextPage(payload);
      break;
    case "objectives_page":
      renderObjectives(payload);
      break;
    case "family_context_page":
      renderFamilyContext(payload);
      break;
    default:
      renderUnknownPayload(payload);
  }
}

async function init() {
  setupThemeToggle();
  try {
    await renderPayloadPage();
  } catch (error) {
    setPage("Unable to load page", "The static shell could not hydrate this route.", [], "editorial");
    state.aside.innerHTML = renderCard("Error", `<p>${escapeHtml(error.message)}</p>`);
    state.stage.innerHTML = `<pre class="mono-block">${escapeHtml(String(error.stack || error.message || error))}</pre>`;
    setStatus("Load failed");
  }
}

export {
  artifactHref,
  catalogCostSortAvailable,
  catalogGeometryValue,
  catalogSortOptions,
  compareCatalogItems,
  escapeHtml,
  fetchJson,
  fetchGeometryMetaMemo,
  fetchRouteGeometryMetaMemo,
  fetchWorkbenchPayloadForRoute,
  normalizeRoute,
  normalizeCatalogSort,
  normalizeSortDirection,
  parseUploadedInstanceText,
  parseUploadedMetaText,
  projectEnuInstanceCoordinates,
  parseUploadedSolutionText,
  relativeFromCurrent,
  resolvePreviewGeometry,
  routeHref,
  setupThemeToggle,
  usesRoadMetric,
};

if (!window.__PAPER7_SITE_NO_BOOTSTRAP__) {
  void init();
}
