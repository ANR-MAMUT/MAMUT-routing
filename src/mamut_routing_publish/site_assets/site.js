const runtimeParams = new URLSearchParams(window.location.search);

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
};

const PALETTE = [
  "#4338ca",
  "#b83a06",
  "#1f77b4",
  "#16a34a",
  "#d97706",
  "#dc2626",
  "#0891b2",
  "#8b5cf6",
];
const WORKBENCH_GENERATION_CITIES_PATH = "/api/workbench/generation/cities";
const WORKBENCH_GENERATION_PREVIEW_PATH = "/api/workbench/generation/preview";
const WORKBENCH_RENDER_ROUTES_PATH = "/api/workbench/render-routes";
const HOME_PREVIEW_ROTATION_MS = 5000;
const ROAD_CACHE_ENDPOINT_TOLERANCE_METERS = 250;
const WGS84_A = 6378137.0;
const WGS84_F = 1 / 298.257223563;
const WGS84_E2 = WGS84_F * (2 - WGS84_F);
const MAMUT_PROJECT_LOGO_PATH = "/webapp/logos/logo_anr_mamut.png";
const GITHUB_BENCHMARKS_ROOT = "https://github.com/ANR-MAMUT/MAMUT-routing/tree/main/benchmarks";
const GITHUB_ICON_PATH = "/webapp/icons/GitHub_Invertocat_Black.svg";
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
  const response = await fetch(sourcePath, { cache: "no-store" });
  if (!response.ok) {
    throw new Error(`Unable to fetch ${sourcePath}: ${response.status}`);
  }
  return response.json();
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

async function fetchWorkbenchJson(sourcePath, init = {}) {
  const response = await fetch(sourcePath, {
    cache: "no-store",
    ...init,
    headers: {
      ...(init.headers || {}),
    },
  });
  const data = await response.json().catch(() => null);
  if (!response.ok || !data?.ok) {
    throw new Error(data?.error || `Unable to fetch ${sourcePath}: ${response.status}`);
  }
  return data;
}

function postWorkbenchJson(sourcePath, payload) {
  return fetchWorkbenchJson(sourcePath, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });
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

function bksLinkChip(formatted, artifactPath, objective) {
  if (!artifactPath) {
    return badgeWithTitleHtml(formatted.labelHtml, formatted.title);
  }
  const href = artifactHref(artifactPath);
  const title = `Open BKS JSON · ${objective}`;
  return `<a class="bks-link-chip" href="${href}" target="_blank" rel="noopener" title="${escapeHtml(title)}">${formatted.labelHtml}<span class="bks-link-chip-glyph" aria-hidden="true">↗</span></a>`;
}

function formatObjectiveBadge(entry) {
  const costHtml = costSpan(entry.cost);
  const costPlain = formatCost(entry.cost);
  const objective = escapeHtml(entry.objective_function);
  if (isHierarchicalObjective(entry) && entry.num_routes != null) {
    const routesHtml = `<span class="badge-cost">${escapeHtml(String(entry.num_routes))}</span>`;
    return {
      labelHtml: `${objective} · ${routesHtml} / ${costHtml}`,
      title: `Hierarchical objective — vehicles / cost = ${entry.num_routes} / ${costPlain}`,
    };
  }
  if (entry.num_routes != null) {
    return {
      labelHtml: `${objective} · ${escapeHtml(String(entry.num_routes))} / ${costHtml}`,
      title: `Mono-cost objective — vehicles / cost = ${entry.num_routes} / ${costPlain}`,
    };
  }
  return {
    labelHtml: `${objective} · ${costHtml}`,
    title: `Mono-cost objective — cost = ${costPlain}`,
  };
}

function renderCard(title, body) {
  return `<section class="card"><h2>${escapeHtml(title)}</h2>${body}</section>`;
}

function renderMarkdownInline(value) {
  return escapeHtml(value)
    .replace(/\[([^\]]+)\]\((https?:\/\/[^)\s]+)\)/g, (_match, label, href) => {
      return `<a href="${href}" target="_blank" rel="noopener">${label}</a>`;
    })
    .replace(/`([^`]+)`/g, "<code>$1</code>")
    .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
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

function renderHomeStatStrip(payload) {
  const stats = [
    ["Problems", payload.counts.problem_count],
    ["Families", payload.counts.family_count],
    ["Instances", payload.counts.instance_count],
    ["BKS", payload.counts.bks_count],
    ["Snapshot", payload.snapshot.snapshot_id],
  ];
  return `<section class="home-stat-strip" aria-label="Snapshot overview">${stats
    .map(
      ([label, value]) =>
        `<div class="home-stat"><span>${escapeHtml(label)}</span><strong>${escapeHtml(value)}</strong></div>`,
    )
    .join("")}</section>`;
}

function renderHomeLinkTile(title, description, routePath, actionLabel) {
  return `<article class="home-link-card">
    <h3>${escapeHtml(title)}</h3>
    <p>${escapeHtml(description)}</p>
    <a class="button-link primary" href="${routeHref(routePath)}">${escapeHtml(actionLabel)}</a>
  </article>`;
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

function renderHomePreviewCard(previewMarkup) {
  return `<article class="home-preview-card">
    ${previewMarkup}
  </article>`;
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
  return `${renderHomePreviewCard(renderHomePreviewMarkup(sample))}${renderHomePreviewDots(activeIndex, count)}`;
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

function homePreviewSampleKey(sample) {
  return [
    normalizeRoute(sample?.instancePayload?.route_path || ""),
    sample?.preview?.selectedEntry?.objective_function || "",
  ].join("::");
}

async function loadHomePreviewLibrary() {
  const seeds = [
    { problemType: "CVRP", benchmarkName: "Mamut2026", metricVariant: "fastest", placeSlug: "brest", objectiveFunction: "MonoCost" },
    { problemType: "CVRP", benchmarkName: "Mamut2026", metricVariant: "shortest", placeSlug: "london", objectiveFunction: "MonoCost" },
    { problemType: "CVRP", benchmarkName: "Mamut2026", metricVariant: "euclidean", placeSlug: "brest", objectiveFunction: "MonoCost" },
    { problemType: "VRPTW", benchmarkName: "Mamut2026", metricVariant: "fastest", placeSlug: "brest", objectiveFunction: "HierarchicalVehicleCost" },
    { problemType: "VRPTW", benchmarkName: "Mamut2026", metricVariant: "fastest", placeSlug: "london", objectiveFunction: "HierarchicalVehicleCost" },
    { problemType: "VRPTW", benchmarkName: "Mamut2026", metricVariant: "euclidean", placeSlug: "london", objectiveFunction: "HierarchicalVehicleCost" },
    { problemType: "CVRP", benchmarkName: "Mamut2026", objectiveFunction: "MonoCost" },
    {},
  ];
  const samples = [];
  const seenKeys = new Set();
  for (const seed of seeds) {
    try {
      const selection = await buildWorkbenchBenchmarkSelection(seed);
      if (!selection.instancePayload) {
        continue;
      }
      const preview = await loadWorkbenchInstancePreview(selection.instancePayload, seed.objectiveFunction || null);
      if (!Array.isArray(preview?.selectedBksData?.routes) || preview.selectedBksData.routes.length === 0) {
        continue;
      }
      const sample = { selection, instancePayload: selection.instancePayload, preview };
      const key = homePreviewSampleKey(sample);
      if (seenKeys.has(key)) {
        continue;
      }
      seenKeys.add(key);
      samples.push(sample);
    } catch (error) {
      console.warn("Unable to load homepage preview sample", error);
    }
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

function renderInstanceRows(items) {
  if (!items || items.length === 0) {
    return `<div class="empty-state">No instances are present in this slice.</div>`;
  }
  return `<div class="table-wrap"><table><thead><tr><th>Instance</th><th>Size</th><th>Context</th><th>Objectives</th><th>Actions</th></tr></thead><tbody>${items
    .map((item) => {
      const contextParts = [item.place_slug, item.historical_topology_type, item.historical_tw_type && `TW${item.historical_tw_type}`].filter(Boolean);
      const objectiveBadges = item.objective_availability
        .map((entry) => {
          const formatted = formatObjectiveBadge(entry);
          return bksLinkChip(formatted, entry.artifact_path, entry.objective_function);
        })
        .join("");
      const objectiveCell = objectiveBadges
        ? `<div class="bks-link-chip-row">${objectiveBadges}</div>`
        : '<span class="meta-line">No BKS</span>';
      const workbenchLink = supportsWorkbenchInstance(item)
        ? `<a class="mini-link" href="${routeHref('/workbench/')}?instance=${encodeURIComponent(item.route_path)}">Workbench</a>`
        : "";
      const rowTitle = `${item.instance_id}\n${item.artifact_vrp_json_path}`;
      const vrpHref = artifactHref(item.artifact_vrp_json_path);
      const nameCell = `<a class="vrp-link" href="${vrpHref}" target="_blank" rel="noopener" title="Open ${escapeHtml(item.display_name)}.vrp.json">${escapeHtml(item.display_name)}</a>`;
      return `<tr title="${escapeHtml(rowTitle)}"><td class="table-cell-mono">${nameCell}</td><td class="table-cell-num">${escapeHtml(item.num_customers)}</td><td>${escapeHtml(contextParts.join(" · ")) || '<span class="meta-line">—</span>'}</td><td>${objectiveCell}</td><td><div class="inline-actions"><a class="mini-link" href="${routeHref(item.route_path)}">Open</a>${workbenchLink}</div></td></tr>`;
    })
    .join("")}</tbody></table></div>`;
}

const VARIANT_SORT_ORDER = ["euclidean", "fastest", "shortest"];

function variantSortKey(variant) {
  const idx = VARIANT_SORT_ORDER.indexOf(variant);
  return idx === -1 ? VARIANT_SORT_ORDER.length : idx;
}

function renderInstanceGroups(items) {
  if (!items || items.length === 0) {
    return `<div class="empty-state">No instances are present in this slice.</div>`;
  }
  const groups = new Map();
  for (const item of items) {
    const key = [item.place_slug ?? "", item.num_customers, item.display_name].join("␟");
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key).push(item);
  }
  const orderedKeys = [...groups.keys()].sort((a, b) => {
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
          return bksLinkChip(formatted, entry.artifact_path, entry.objective_function);
        })
        .join("");
      const objectiveCell = objectiveBadges
        ? `<div class="bks-link-chip-row">${objectiveBadges}</div>`
        : '<span class="meta-line">No BKS</span>';
      const workbenchLink = supportsWorkbenchInstance(item)
        ? `<a class="mini-link" href="${routeHref('/workbench/')}?instance=${encodeURIComponent(item.route_path)}">Workbench</a>`
        : "";
      const rowTitle = `${item.instance_id}\n${item.artifact_vrp_json_path}`;
      const variantLabel = item.locator.metric_variant ?? "";
      const vrpHref = artifactHref(item.artifact_vrp_json_path);
      const variantCell = variantLabel
        ? `<a class="vrp-link" href="${vrpHref}" target="_blank" rel="noopener" title="Open ${escapeHtml(item.display_name)} (${escapeHtml(variantLabel)}) .vrp.json">${escapeHtml(variantLabel)}</a>`
        : "";
      return `<tr class="group-sub" title="${escapeHtml(rowTitle)}"><td class="indent" aria-hidden="true">↳</td><td class="table-cell-mono">${variantCell}</td><td>${objectiveCell}</td><td><div class="inline-actions"><a class="mini-link" href="${routeHref(item.route_path)}">Open</a>${workbenchLink}</div></td></tr>`;
    }).join("");
    return `<tbody class="group"><tr class="group-header">${headerCell}</tr>${subRows}</tbody>`;
  });
  return `<div class="table-wrap"><table class="grouped-instance-table"><thead><tr><th></th><th>Variant</th><th>Objectives</th><th>Actions</th></tr></thead>${tbodies.join("")}</table></div>`;
}

async function renderHome(payload) {
  setPage(payload.title, payload.subtitle, [], "home");
  if (state.aside) {
    state.aside.innerHTML = "";
  }
  setStatus("Loading homepage preview...");
  const previewLibrary = await loadHomePreviewLibrary();
  state.stage.innerHTML = `
    <section class="home-page">
      <section class="home-hero">
        <div class="home-hero-copy">
          <div class="home-title-row">
            <img class="home-project-logo" src="${siteAssetHref(MAMUT_PROJECT_LOGO_PATH)}" alt="MAMUT project logo" />
            <div class="home-title-copy">
              <div class="badge-row home-kicker">${payload.problems.map((problem) => badge(problem.problem_type)).join("")}${badge(`snapshot ${payload.snapshot.snapshot_id}`, true)}</div>
              <h1>${escapeHtml(payload.title)}</h1>
            </div>
          </div>
          <p>${escapeHtml(payload.hero_summary)}</p>
          <div class="home-actions">
            <a class="button-link" href="${routeHref(payload.benchmarks_route_path)}">Browse Benchmarks</a>
            <a class="button-link" href="${routeHref(payload.workbench_route_path)}">Open Workbench</a>
            <a class="button-link" href="${routeHref(payload.project_route_path)}">Project</a>
            <a class="button-link" href="${routeHref(payload.objectives_route_path)}">Objectives</a>
            <a class="button-link" href="${routeHref(payload.history_route_path)}">History</a>
          </div>
          ${renderHomeStatStrip(payload)}
        </div>
        ${renderHomePreviewShowcase(payload, previewLibrary)}
      </section>
      <section class="home-section">
        <div class="home-section-heading">
          <h2>What Is Inside</h2>
          <p>Direct paths to the public catalog, viewer, contract notes, and release provenance.</p>
        </div>
        <div class="home-link-grid">
          ${renderHomeLinkTile("Benchmarks", "Browse curated CVRP and VRPTW families, variants, places, sizes, and instance artifacts.", payload.benchmarks_route_path, "Browse Benchmarks")}
          ${renderHomeLinkTile("Workbench", "Visualize published instances, inspect uploaded files, and generate OSM-backed previews.", payload.workbench_route_path, "Open Workbench")}
          ${renderHomeLinkTile("ANR Project", "Understand how this benchmark and generation work sits inside the MAMUT research project.", payload.project_route_path, "Open Project")}
          ${renderHomeLinkTile("Objective Semantics", "Check how HierarchicalVehicleCost and MonoCost should be interpreted before comparing results.", payload.objectives_route_path, "Read Objectives")}
          ${renderHomeLinkTile("Publication History", "Track the repository snapshot, source commit, and release notes for this static publication.", payload.history_route_path, "Open History")}
        </div>
      </section>
      <section class="home-publication-note">
        <strong>Current publication</strong>
        <span>${escapeHtml(payload.latest_publication_summary)}</span>
        <span>Published ${escapeHtml(payload.snapshot.published_at)} from commit ${escapeHtml(payload.snapshot.source_commit)}</span>
      </section>
    </section>`;
  activateHomePreviewLibrary(previewLibrary);
  setStatus(`Loaded snapshot ${payload.snapshot.snapshot_id}`);
}

function renderBenchmarksIndex(payload) {
  const breadcrumbs = payload.breadcrumbs || [{ label: "benchmarks", route_path: "/benchmarks/" }];
  setPage("Benchmarks", "Choose a problem class first, then narrow to a benchmark family or generated variant.", breadcrumbs, "catalog");
  state.aside.innerHTML = [
    renderCard(
      "Browse Benchmarks",
      `<p>This static publication separates CVRP and VRPTW at the top level, then preserves family and variant structure inside each problem class.</p>${renderStatGrid([
        ["Snapshot", payload.snapshot.snapshot_id],
        ["Published", payload.snapshot.published_at],
        ["Commit", payload.snapshot.source_commit],
      ])}`,
    ),
  ].join("");
  state.stage.innerHTML = renderProblemCards(payload.problems);
  setStatus(`Loaded ${payload.problems.length} problem classes`);
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

function renderCatalogIndex(payload) {
  setPage(payload.title, payload.description || `Static listing for ${payload.benchmark_name}.`, payload.breadcrumbs, "catalog");
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
    descriptionCard,
    renderSubrouteList("Variants", payload.variant_routes),
    renderSubrouteList("Subsets", payload.subset_routes),
    renderSubrouteList("Places", payload.place_routes),
    renderSubrouteList("Sizes", payload.size_routes),
    renderFacetList(payload.filter_facets),
  ].join("");
  const isMamut2026FamilyPage =
    payload.payload_kind === "family_index" && payload.benchmark_name === "Mamut2026";
  state.stage.innerHTML = isMamut2026FamilyPage
    ? renderInstanceGroups(payload.items)
    : renderInstanceRows(payload.items);
  setStatus(`Loaded ${payload.items.length} instances`);
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

function cachedRouteCoordinates(sequence, metricCache, graphVertexIds, nodeCoordinates, instanceNodeIds) {
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

  return mergeGeometrySegments(segments);
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

  const routeLines = routes.map((route, routeIndex) => {
    const sequence = [depotIndex, ...route.map((nodeIndex) => Number(nodeIndex)), depotIndex];
    const cachedCoordinates = cachedRoadAvailable ? cachedRouteCoordinates(sequence, metricCache, graphVertexIds, nodeCoordinates, instanceNodeIds) : null;
    const routeCoordinates = cachedCoordinates || sequence.map((nodeIndex) => normalizeGeometryPoint(nodeCoordinates[nodeIndex])).filter(Boolean);
    return {
      routeIndex,
      coordinates: routeCoordinates,
      source: cachedCoordinates ? "cached_road" : "straight_line",
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

function supportsWorkbenchInstance(value) {
  const placeSlug = String(value?.place_slug || value?.summary?.place_slug || "").trim();
  return placeSlug.length > 0;
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
  const routePaths = previewGeometry.routeLines
    .map((routeLine) => {
      const projectedRoute = projectCoordinates(routeLine.coordinates, width, height, projectionBounds).filter(Boolean);
      if (projectedRoute.length < 2) {
        return "";
      }
      const routeTitle = `Route ID ${routeLine.routeIndex + 1} · ${routeLine.stopCount} customer${routeLine.stopCount === 1 ? "" : "s"} · ${String(routeLine.source).replaceAll("_", " ")}`;
      return `<g class="route-line"><title>${escapeHtml(routeTitle)}</title><polyline fill="none" stroke="${PALETTE[routeLine.routeIndex % PALETTE.length]}" stroke-width="3" stroke-linecap="round" stroke-linejoin="round" points="${projectedRoute
        .map((point) => `${point.x},${point.y}`)
        .join(" ")}" /></g>`;
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
      return `<g class="viewer-node"><title>${escapeHtml(nodeTitle)}</title><circle cx="${point.x}" cy="${point.y}" r="${isDepot ? 6 : 4}" fill="${isDepot ? '#b83a06' : '#111111'}" opacity="${isDepot ? 1 : 0.8}" /></g>`;
    })
    .join("");
  const geometryCaption = previewGeometry.hasCachedRoadRoutes
    ? `Cached-road preview from sidecar geometry (${String(options.metricVariant || "road").toLowerCase()})`
    : "Straight-line preview from canonical coordinates";
  return `
    <div class="viewer-toolbar">
      <div>${badgeHtml(previewGeometry.geometryNoteHtml, true)}</div>
      <div class="meta-line">${escapeHtml(geometryCaption)}</div>
    </div>
    <div class="viewer-frame">
      <svg viewBox="0 0 ${width} ${height}" role="img" aria-label="Routing preview">${routePaths}${nodes}</svg>
    </div>`;
}

function renderGenerationPreviewSvg(geojson, summary = {}) {
  const width = 860;
  const height = 520;
  const features = Array.isArray(geojson?.features) ? geojson.features : [];
  const featurePoints = features
    .map((feature) => normalizeGeometryPoint(feature?.geometry?.coordinates))
    .filter(Boolean);

  if (featurePoints.length === 0) {
    return `<div class="empty-state">No preview geometry was returned for the requested generation parameters.</div>`;
  }

  const projectedPoints = projectCoordinates(featurePoints, width, height);
  const nodes = projectedPoints
    .map((point, index) => {
      if (!point) {
        return "";
      }
      const feature = features[index];
      const role = feature?.properties?.role || "customer";
      const sourceTag = String(feature?.properties?.source_tag || "unknown");
      const fill = role === "depot" ? "#111111" : sourceTag === "catalog_sample" ? "#16a34a" : sourceTag.startsWith("poi") ? "#b83a06" : "#0891b2";
      const radius = role === "depot" ? 8 : 5;
      return `<g class="viewer-node"><title>${escapeHtml(role)} · ${escapeHtml(sourceTag)}</title><circle cx="${point.x}" cy="${point.y}" r="${radius}" fill="${fill}" opacity="0.92" /></g>`;
    })
    .join("");

  const customerCounts = [];
  if (summary.customers !== undefined) {
    customerCounts.push(`${summary.customers} customers`);
  }
  if (summary.requested_customers !== undefined && summary.requested_customers !== summary.customers) {
    customerCounts.push(`requested ${summary.requested_customers}`);
  }

  return `
    <div class="viewer-toolbar">
      <div>${badge(`${summary.city || "Preview"} · ${summary.method || "generation"}`, true)}</div>
      <div class="meta-line">${escapeHtml(summary.note || "Preview generated from workbench parameters")}</div>
    </div>
    <div class="viewer-frame">
      <svg viewBox="0 0 ${width} ${height}" role="img" aria-label="Generation preview">${nodes}</svg>
    </div>
    <div class="preview-summary">
      <article class="mini-card">
        <h3>Preview Summary</h3>
        ${renderStatGrid([
          ["Mode", summary.preview_mode || "n/a"],
          ["City", summary.city || "n/a"],
          ["Method", summary.method || "n/a"],
          ["Customers", customerCounts.join(" · ") || "n/a"],
          ["POI", summary.poi_customers ?? "n/a"],
          ["Parametric", summary.parametric_customers ?? "n/a"],
        ])}
      </article>
      <article class="mini-card">
        <h3>Preview Source</h3>
        ${renderStatGrid([
          ["Sample instance", summary.sample_instance_name || "live selection"],
          ["Sample method", summary.sample_method || "live"],
          ["Sample size", summary.sample_size_dir || "live"],
        ])}
      </article>
    </div>`;
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
      ["Expected paths", summary.road_cache_expected_entry_count ?? "n/a"],
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
  const instanceData = await fetchJson(artifactHref(payload.artifact_links.vrp_json_path));
  let geometryMeta = null;
  if (payload.summary.viewer_render_mode === "cached_road" && payload.summary.road_cache_status === "complete" && payload.artifact_links.meta_path) {
    try {
      geometryMeta = await fetchJson(artifactHref(payload.artifact_links.meta_path));
    } catch (error) {
      console.warn("Unable to load geometry sidecar", error);
    }
  }
  let selectedIndex = 0;
  let selectedEntry = payload.bks_entries[selectedIndex] || null;
  let selectedBksData = selectedEntry ? await fetchJson(artifactHref(selectedEntry.artifact_path)) : null;

  const renderSelectedState = () => {
    const asideCards = [
      inWorkbench ? renderWorkbenchModeCard(payload.route_path) : "",
      inWorkbench ? renderWorkbenchVisualizeSourceCard(payload.route_path) : "",
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
          ${payload.artifact_links.manifest_path ? `<li><a href="${artifactHref(payload.artifact_links.manifest_path)}">manifest.json</a></li>` : ""}
        </ul><div class="meta-line" style="margin-top:0.8rem">Published ${escapeHtml(payload.snapshot.published_at)} from commit ${escapeHtml(payload.snapshot.source_commit)}</div>`,
      ),
      renderCard("BKS Selector", `${renderBksSelector(payload.bks_entries, selectedIndex)}${selectedEntry ? `<div class="mini-card" style="margin-top:0.8rem">${renderStatGrid([["Objective", selectedEntry.objective_function], ["Routes", routesStatValue(selectedEntry)], ["Cost", { html: costSpan(selectedEntry.cost, "stat-cost") }], ["Method", selectedEntry.method || 'n/a'], ["Authors", selectedEntry.authors || 'n/a'], ...(selectedEntry.license ? [["License", selectedEntry.license_url ? { html: `<a href="${escapeHtml(selectedEntry.license_url)}" target="_blank" rel="noopener">${escapeHtml(selectedEntry.license)}</a>` } : selectedEntry.license]] : [])])}<div class="inline-actions" style="margin-top:0.8rem"><a class="mini-link" href="${artifactHref(selectedEntry.artifact_path)}">Download BKS</a></div></div>` : ''}`),
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
          geometryMeta,
          metricVariant: payload.summary.metric_variant,
          viewerRenderMode: payload.summary.viewer_render_mode,
          roadCacheStatus: payload.summary.road_cache_status,
        })}
        <section class="mini-card">
          <h3>Route Legend</h3>
          ${routeLegend}
        </section>
      </div>`;

    state.aside.querySelectorAll("[data-bks-index]").forEach((button) => {
      button.addEventListener("click", async () => {
        selectedIndex = Number(button.dataset.bksIndex);
        selectedEntry = payload.bks_entries[selectedIndex] || null;
        selectedBksData = selectedEntry ? await fetchJson(artifactHref(selectedEntry.artifact_path)) : null;
        renderSelectedState();
      });
    });
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

function renderHistoryLedger(payload) {
  setPage("History", "Every published website state is tied to an explicit repository snapshot.", [], "editorial");
  const currentEntry = payload.entries[0];
  state.aside.innerHTML = [
    renderCard(
      "History Overview",
      `<p>The public site is a static publication ledger, not a live reflection of repository HEAD.</p>${currentEntry ? renderStatGrid([["Current snapshot", payload.current_snapshot_id], ["Published", currentEntry.snapshot.published_at], ["Commit", currentEntry.snapshot.source_commit]]) : '<div class="empty-state">No history entries yet.</div>'}`,
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
        <div class="badge-row">${(entry.affected_problem_types || []).map((value) => badge(value)).join("")}${(entry.affected_objective_functions || []).map((value) => badge(value, true)).join("")}</div>
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
    ? `<p class="meta-line initial-banner">Initial snapshot — full inventory shown as additions.</p>`
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
      `<div class="badge-row">${(payload.affected_problem_types || []).map((value) => badge(value)).join("")}${(payload.affected_benchmark_names || []).map((value) => badge(value, true)).join("")}${(payload.affected_objective_functions || []).map((value) => badge(value)).join("")}</div>`,
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

function buildGenerationPreviewPayload(formData) {
  return {
    city: formData.get("city") || "",
    method: formData.get("method") || "poi_categories",
    nCustomers: Number.parseInt(formData.get("nCustomers") || "50", 10),
    seed: Number.parseInt(formData.get("seed") || "0", 10),
    onlyIntersections: formData.get("onlyIntersections") === "on",
    depotMode: formData.get("depotMode") || "center",
    customerMode: formData.get("customerMode") || "random_clustered",
    clusterSeeds: Number.parseInt(formData.get("clusterSeeds") || "4", 10),
    clusterDecayMeters: Number.parseFloat(formData.get("clusterDecayMeters") || "800"),
    hybridPoiShare: Number.parseFloat(formData.get("hybridPoiShare") || "0.5"),
    categories: String(formData.get("categories") || "restaurant,cafe")
      .split(",")
      .map((value) => value.trim())
      .filter(Boolean),
  };
}

async function loadWorkbenchInstanceContext(instanceRoute) {
  if (!instanceRoute) {
    return null;
  }
  try {
    const payload = await fetchJson(payloadUrlForRoute(instanceRoute));
    return payload?.payload_kind === "instance_page" ? payload : null;
  } catch (error) {
    console.warn("Unable to hydrate workbench instance context", error);
    return null;
  }
}

function renderWorkbenchInstanceContextCard(instancePayload) {
  if (!instancePayload) {
    return renderCard(
      "Benchmark Context",
      '<div class="empty-state">Choose a benchmark instance first to prefill city and customer-count defaults.</div>',
    );
  }

  return renderCard(
    "Benchmark Context",
    `${renderStatGrid([
      ["Instance", instancePayload.summary.instance_identifier || instancePayload.title],
      ["Problem", instancePayload.summary.problem_type],
      ["Family", instancePayload.summary.benchmark_name],
      ["Place", instancePayload.summary.place_slug || "n/a"],
      ["Customers", instancePayload.summary.num_customers],
    ])}<div class="inline-actions" style="margin-top:0.8rem"><a class="mini-link" href="${routeHref(instancePayload.route_path)}">Open benchmark instance</a></div>`,
  );
}

function matchesWorkbenchValue(left, right) {
  return String(left ?? "").toLowerCase() === String(right ?? "").toLowerCase();
}

function selectWorkbenchOption(options, predicate) {
  return options.find(predicate) || options[0] || null;
}

function buildWorkbenchSeedFromInstancePayload(instancePayload, preferredObjectiveFunction = null) {
  return {
    problemType: instancePayload?.summary?.problem_type || null,
    benchmarkName: instancePayload?.summary?.benchmark_name || null,
    metricVariant: instancePayload?.summary?.metric_variant || null,
    placeSlug: instancePayload?.summary?.place_slug || null,
    sizeBucket: instancePayload?.summary?.size_bucket || null,
    instanceRoute: instancePayload?.route_path || null,
    objectiveFunction: preferredObjectiveFunction || instancePayload?.bks_entries?.[0]?.objective_function || null,
  };
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

  const instanceData = await fetchJson(artifactHref(instancePayload.artifact_links.vrp_json_path));
  let geometryMeta = null;
  if (instancePayload.summary.viewer_render_mode === "cached_road" && instancePayload.summary.road_cache_status === "complete" && instancePayload.artifact_links.meta_path) {
    try {
      geometryMeta = await fetchJson(artifactHref(instancePayload.artifact_links.meta_path));
    } catch (error) {
      console.warn("Unable to load geometry sidecar", error);
    }
  }

  const bksEntries = Array.isArray(instancePayload.bks_entries) ? instancePayload.bks_entries : [];
  let selectedIndex = bksEntries.findIndex((entry) => matchesWorkbenchValue(entry.objective_function, preferredObjectiveFunction));
  if (selectedIndex < 0) {
    selectedIndex = 0;
  }
  const selectedEntry = bksEntries[selectedIndex] || null;
  const selectedBksData = selectedEntry ? await fetchJson(artifactHref(selectedEntry.artifact_path)) : null;

  return {
    instanceData,
    geometryMeta,
    selectedIndex,
    selectedEntry,
    selectedBksData,
  };
}

function renderWorkbenchSelectField(label, name, options, selectedValue, hint = "") {
  const normalizedValue = String(selectedValue ?? "");
  const renderedOptions = options.length > 0
    ? options
        .map((option) => `<option value="${escapeHtml(option.value)}"${String(option.value) === normalizedValue ? " selected" : ""}>${escapeHtml(option.label)}</option>`)
        .join("")
    : '<option value="">Unavailable</option>';
  return `<label class="form-field"><span>${escapeHtml(label)}</span><select name="${escapeHtml(name)}"${options.length === 0 ? " disabled" : ""}>${renderedOptions}</select>${hint ? `<small class="field-hint">${escapeHtml(hint)}</small>` : ""}</label>`;
}

function renderWorkbenchRouteLegend(routes) {
  if (!Array.isArray(routes) || routes.length === 0) {
    return '<div class="empty-state">No route overlay is available for this selection.</div>';
  }

  return `<div class="route-legend">${routes
    .map(
      (route, index) =>
        `<div class="legend-item"><span class="legend-swatch" style="background:${PALETTE[index % PALETTE.length]}"></span><span>Route ${index + 1} · ${route.length} clients</span></div>`,
    )
    .join("")}</div>`;
}

function renderWorkbenchBenchmarkSelectionCard(selection) {
  const summary = selection.activeCatalogPayload?.summary || null;
  return renderCard(
    "Benchmark Selection",
    `${renderStatGrid([
      ["Problem", selection.selectedProblem?.problem_type || "n/a"],
      ["Family", selection.selectedFamily?.benchmark_name || "n/a"],
      ["Variant", selection.selectedVariant?.label || selection.instancePayload?.summary?.metric_variant || "n/a"],
      ["Place", selection.selectedPlace?.label || selection.instancePayload?.summary?.place_slug || "n/a"],
      ["Size", selection.selectedSize?.label || selection.instancePayload?.summary?.size_bucket || "n/a"],
      ["Instances", summary?.instance_count ?? selection.items.length ?? "n/a"],
      ["BKS", summary?.bks_count ?? selection.instancePayload?.bks_entries?.length ?? "n/a"],
    ])}`,
  );
}

function renderWorkbenchSelectedObjectiveCard(selectedEntry) {
  if (!selectedEntry) {
    return renderCard("Selected Objective", '<div class="empty-state">No BKS entry is available for the selected instance.</div>');
  }

  return renderCard(
    "Selected Objective",
    `${renderStatGrid([
      ["Objective", selectedEntry.objective_function],
      ["Routes", routesStatValue(selectedEntry)],
      ["Cost", { html: costSpan(selectedEntry.cost, "stat-cost") }],
      ["Method", selectedEntry.method || "n/a"],
      ["Authors", selectedEntry.authors || "n/a"],
    ])}<div class="inline-actions" style="margin-top:0.8rem"><a class="mini-link" href="${artifactHref(selectedEntry.artifact_path)}">Download BKS</a></div>`,
  );
}

function renderWorkbenchArtifactsCard(instancePayload) {
  return renderCard(
    "Artifacts",
    `<ul class="artifact-list">
      <li><a href="${artifactHref(instancePayload.artifact_links.vrp_json_path)}">vrp.json</a></li>
      ${instancePayload.artifact_links.vrp_path ? `<li><a href="${artifactHref(instancePayload.artifact_links.vrp_path)}">vrp</a></li>` : ""}
      ${instancePayload.artifact_links.meta_path ? `<li><a href="${artifactHref(instancePayload.artifact_links.meta_path)}">meta.json</a></li>` : ""}
      ${instancePayload.artifact_links.manifest_path ? `<li><a href="${artifactHref(instancePayload.artifact_links.manifest_path)}">manifest.json</a></li>` : ""}
    </ul><div class="meta-line" style="margin-top:0.8rem">Published ${escapeHtml(instancePayload.snapshot.published_at)} from commit ${escapeHtml(instancePayload.snapshot.source_commit)}</div>`,
  );
}

async function renderWorkbenchBenchmarkPage() {
  const seededInstancePayload = await loadWorkbenchInstanceContext(runtimeParams.get("instance"));
  let workbenchState = seededInstancePayload
    ? buildWorkbenchSeedFromInstancePayload(seededInstancePayload, runtimeParams.get("objective"))
    : {
        problemType: null,
        benchmarkName: null,
        metricVariant: null,
        placeSlug: null,
        sizeBucket: null,
        instanceRoute: runtimeParams.get("instance"),
        objectiveFunction: runtimeParams.get("objective"),
      };

  const refreshSelection = async () => {
    setStatus("Loading benchmark selector…");
    const selection = await buildWorkbenchBenchmarkSelection(workbenchState);
    const preview = await loadWorkbenchInstancePreview(selection.instancePayload, workbenchState.objectiveFunction);

    workbenchState = {
      problemType: selection.selectedProblem?.problem_type || null,
      benchmarkName: selection.selectedFamily?.benchmark_name || null,
      metricVariant: selection.selectedVariant?.key || null,
      placeSlug: selection.selectedPlace?.key || null,
      sizeBucket: selection.selectedSize?.key || selection.instancePayload?.summary?.size_bucket || null,
      instanceRoute: selection.selectedInstance?.route_path || null,
      objectiveFunction: preview?.selectedEntry?.objective_function || null,
    };
    updateWorkbenchRuntimeParams({ instance: workbenchState.instanceRoute, objective: workbenchState.objectiveFunction, deriveTarget: null });

    setPage(
      selection.instancePayload ? `Workbench: ${selection.instancePayload.title}` : "Workbench: Visualize Benchmarks",
      selection.instancePayload
        ? "Navigate the benchmark hierarchy, keep the current instance selection in sync with the menus, and switch objective overlays from one workbench surface."
        : "Browse the published benchmark hierarchy directly from the workbench, then preview one instance and objective at a time.",
      [{ label: "Workbench", route_path: "/workbench/" }],
      "explorer",
    );

    const asideCards = [
      renderWorkbenchModeCard(workbenchState.instanceRoute),
      renderWorkbenchVisualizeSourceCard(workbenchState.instanceRoute),
      renderWorkbenchBenchmarkSelectionCard(selection),
    ];
    if (selection.instancePayload) {
      asideCards.push(
        renderCard(
          "Instance Summary",
          `${renderStatGrid([
            ["Problem", selection.instancePayload.summary.problem_type],
            ["Family", selection.instancePayload.summary.benchmark_name],
            ["Variant", selection.instancePayload.summary.metric_variant || "historical"],
            ["Place", selection.instancePayload.summary.place_slug || selection.instancePayload.summary.historical_topology_type || "n/a"],
            ["Size", selection.instancePayload.summary.size_bucket],
            ["Customers", selection.instancePayload.summary.num_customers],
            ["Vehicles", selection.instancePayload.summary.num_vehicles ?? selection.instancePayload.summary.num_vehicles_lb ?? "n/a"],
            ["Capacity", selection.instancePayload.summary.vehicle_capacity],
          ])}<div class="badge-row">${(selection.instancePayload.summary.supported_objective_functions || []).map((objective) => badge(objective)).join("")}${selection.instancePayload.summary.historical_topology_type ? badge(selection.instancePayload.summary.historical_topology_type, true) : ""}${selection.instancePayload.summary.historical_tw_type ? badge(`TW${selection.instancePayload.summary.historical_tw_type}`, true) : ""}</div>`,
        ),
        renderGeometryCard(selection.instancePayload.summary),
        renderWorkbenchSelectedObjectiveCard(preview?.selectedEntry || null),
        renderWorkbenchArtifactsCard(selection.instancePayload),
      );
    } else {
      asideCards.push(renderCard("Instance Summary", '<div class="empty-state">Select a benchmark instance to populate the preview and artifact cards.</div>'));
    }
    state.aside.innerHTML = asideCards.join("");

    const problemOptions = selection.problemCards.map((problem) => ({ value: problem.problem_type, label: problem.problem_type }));
    const familyOptions = selection.familyCards.map((family) => ({ value: family.benchmark_name, label: family.benchmark_name }));
    const variantOptions = selection.variantEntries.map((entry) => ({ value: entry.key, label: entry.label }));
    const placeOptions = selection.placeEntries.map((entry) => ({ value: entry.key, label: entry.label }));
    const sizeOptions = selection.sizeEntries.map((entry) => ({ value: entry.key, label: entry.label }));
    const instanceOptions = selection.items.map((item) => ({ value: item.route_path, label: item.display_name }));
    const objectiveOptions = Array.isArray(selection.instancePayload?.bks_entries)
      ? selection.instancePayload.bks_entries.map((entry) => ({ value: entry.objective_function, label: entry.objective_function }))
      : [];

    const previewMarkup = selection.instancePayload && preview
      ? `
        ${renderPreviewSvg(preview.instanceData, preview.selectedBksData, preview.selectedEntry, {
          geometryMeta: preview.geometryMeta,
          metricVariant: selection.instancePayload.summary.metric_variant,
          viewerRenderMode: selection.instancePayload.summary.viewer_render_mode,
          roadCacheStatus: selection.instancePayload.summary.road_cache_status,
        })}
        <section class="mini-card">
          <h3>Route Legend</h3>
          ${renderWorkbenchRouteLegend(preview.selectedBksData?.routes)}
        </section>`
      : '<div class="empty-state">No benchmark instance is available for the current selector combination.</div>';

    state.stage.innerHTML = `
      <div class="viewer-stage">
        <section class="mini-card">
          <h2>Benchmark Selection</h2>
          <form class="form-grid" data-benchmark-selector>
            ${renderWorkbenchSelectField("Problem", "problemType", problemOptions, workbenchState.problemType, "Choose the top-level problem family first.")}
            ${renderWorkbenchSelectField("Benchmark Family", "benchmarkName", familyOptions, workbenchState.benchmarkName, "Families come from the selected problem payload.")}
            ${variantOptions.length > 0 ? renderWorkbenchSelectField("Variant", "metricVariant", variantOptions, workbenchState.metricVariant, "Generated Mamut families expose metric variants here.") : ""}
            ${placeOptions.length > 0 ? renderWorkbenchSelectField("Place", "placeSlug", placeOptions, workbenchState.placeSlug, "Historical families skip this level.") : ""}
            ${sizeOptions.length > 0 ? renderWorkbenchSelectField("Size", "sizeBucket", sizeOptions, workbenchState.sizeBucket, "Sizes come from the currently active catalog slice.") : ""}
            ${renderWorkbenchSelectField("Instance", "instanceRoute", instanceOptions, workbenchState.instanceRoute, "The selected instance keeps the workbench query string in sync.")}
            ${objectiveOptions.length > 0 ? renderWorkbenchSelectField("Objective", "objectiveFunction", objectiveOptions, workbenchState.objectiveFunction, "Use this menu to switch the active BKS overlay.") : ""}
            <div class="inline-actions form-field-wide">
              ${selection.instancePayload ? `<a class="button-link primary" href="${routeHref(selection.instancePayload.route_path)}">Open Public Instance</a>` : ""}
              <a class="button-link" href="${routeHref('/benchmarks/')}">Browse Full Catalog</a>
            </div>
          </form>
        </section>
        <section class="mini-card">
          <h2>Preview Surface</h2>
          ${previewMarkup}
        </section>
      </div>`;

    const form = state.stage.querySelector("[data-benchmark-selector]");
    form?.querySelector('select[name="problemType"]')?.addEventListener("change", async (event) => {
      workbenchState.problemType = event.target.value || null;
      workbenchState.benchmarkName = null;
      workbenchState.metricVariant = null;
      workbenchState.placeSlug = null;
      workbenchState.sizeBucket = null;
      workbenchState.instanceRoute = null;
      workbenchState.objectiveFunction = null;
      await refreshSelection();
    });
    form?.querySelector('select[name="benchmarkName"]')?.addEventListener("change", async (event) => {
      workbenchState.benchmarkName = event.target.value || null;
      workbenchState.metricVariant = null;
      workbenchState.placeSlug = null;
      workbenchState.sizeBucket = null;
      workbenchState.instanceRoute = null;
      workbenchState.objectiveFunction = null;
      await refreshSelection();
    });
    form?.querySelector('select[name="metricVariant"]')?.addEventListener("change", async (event) => {
      workbenchState.metricVariant = event.target.value || null;
      workbenchState.placeSlug = null;
      workbenchState.sizeBucket = null;
      workbenchState.instanceRoute = null;
      workbenchState.objectiveFunction = null;
      await refreshSelection();
    });
    form?.querySelector('select[name="placeSlug"]')?.addEventListener("change", async (event) => {
      workbenchState.placeSlug = event.target.value || null;
      workbenchState.sizeBucket = null;
      workbenchState.instanceRoute = null;
      workbenchState.objectiveFunction = null;
      await refreshSelection();
    });
    form?.querySelector('select[name="sizeBucket"]')?.addEventListener("change", async (event) => {
      workbenchState.sizeBucket = event.target.value || null;
      workbenchState.instanceRoute = null;
      workbenchState.objectiveFunction = null;
      await refreshSelection();
    });
    form?.querySelector('select[name="instanceRoute"]')?.addEventListener("change", async (event) => {
      workbenchState.instanceRoute = event.target.value || null;
      workbenchState.objectiveFunction = null;
      await refreshSelection();
    });
    form?.querySelector('select[name="objectiveFunction"]')?.addEventListener("change", async (event) => {
      workbenchState.objectiveFunction = event.target.value || null;
      await refreshSelection();
    });

    setStatus(preview?.selectedEntry ? `Showing ${preview.selectedEntry.objective_function}` : "Benchmark selector ready");
  };

  await refreshSelection();
}

function buildWorkbenchRelatedEntries(instancePayload) {
  const groups = [
    {
      key: "source",
      label: "Source Problems",
      entries: Object.entries(instancePayload?.source_problem_routes || {}).map(([entryKey, routePath]) => ({
        entryKey,
        label: labelizeCapability(entryKey),
        routePath,
      })),
    },
    {
      key: "derived",
      label: "Derived Problems",
      entries: Object.entries(instancePayload?.derived_problem_routes || {}).map(([entryKey, routePath]) => ({
        entryKey,
        label: labelizeCapability(entryKey),
        routePath,
      })),
    },
    {
      key: "sibling",
      label: "Sibling Variants",
      entries: Object.entries(instancePayload?.sibling_variant_routes || {}).map(([entryKey, routePath]) => ({
        entryKey,
        label: labelizeCapability(entryKey),
        routePath,
      })),
    },
  ];
  return groups.map((group) => ({ ...group, count: group.entries.length }));
}

function renderWorkbenchRelationGroup(instanceRoute, group, activeRoute, objectiveFunction) {
  if (!Array.isArray(group.entries) || group.entries.length === 0) {
    return "";
  }

  const chips = group.entries
    .map((entry) => {
      const isActive = normalizeRoute(entry.routePath) === normalizeRoute(activeRoute || "");
      const params = new URLSearchParams();
      params.set("instance", instanceRoute);
      params.set("deriveTarget", entry.routePath);
      if (objectiveFunction) {
        params.set("objective", objectiveFunction);
      }
      return `<a class="selector-chip${isActive ? ' active' : ''}" href="${routeHref('/workbench/derive/')}?${params.toString()}">${escapeHtml(entry.label)}</a>`;
    })
    .join("");

  return `<section class="mini-card"><h3>${escapeHtml(group.label)}</h3><div class="chip-row">${chips}</div></section>`;
}

async function renderWorkbenchDerivePage() {
  const instanceRoute = runtimeParams.get("instance");
  const currentPayload = await loadWorkbenchInstanceContext(instanceRoute);
  if (!currentPayload) {
    setPage(
      "Workbench: Derive",
      "Derive mode needs a benchmark instance context so it can trace source, derived, and sibling routes.",
      [{ label: "Workbench", route_path: "/workbench/derive/" }],
      "explorer",
    );
    state.aside.innerHTML = [
      renderWorkbenchModeCard(null),
      renderCard("Derive Context", '<div class="empty-state">Open a benchmark instance first, then switch to derive mode to inspect related published instances.</div>'),
    ].join("");
    state.stage.innerHTML = `<div class="viewer-stage"><section class="mini-card"><h2>Derive Mode</h2><p>Select an instance in benchmark visualize mode to inspect source-problem, derived-problem, and sibling-variant links here.</p><div class="inline-actions"><a class="button-link primary" href="${routeHref('/workbench/')}">Open Benchmark Visualize</a><a class="button-link" href="${routeHref('/benchmarks/')}">Browse Benchmarks</a></div></section></div>`;
    setStatus("Derive mode needs an instance selection");
    return;
  }

  const relationGroups = buildWorkbenchRelatedEntries(currentPayload);
  const relatedEntries = relationGroups.flatMap((group) => group.entries.map((entry) => ({ ...entry, groupKey: group.key, groupLabel: group.label })));
  const selectedRelation = selectWorkbenchOption(
    relatedEntries,
    (entry) => normalizeRoute(entry.routePath) === normalizeRoute(runtimeParams.get("deriveTarget") || ""),
  );
  const relatedPayload = selectedRelation ? await loadWorkbenchInstanceContext(selectedRelation.routePath) : null;
  const relatedPreview = await loadWorkbenchInstancePreview(relatedPayload, runtimeParams.get("objective"));
  const selectedObjective = relatedPreview?.selectedEntry?.objective_function || null;
  updateWorkbenchRuntimeParams({ instance: currentPayload.route_path, deriveTarget: selectedRelation?.routePath || null, objective: selectedObjective });

  setPage(
    `Workbench: Derive ${currentPayload.title}`,
    "Inspect the published source-problem, derived-problem, and sibling-variant links attached to the selected benchmark instance.",
    [{ label: "Workbench", route_path: "/workbench/derive/" }],
    "explorer",
  );

  const relationCounts = relationGroups.map((group) => [group.label, group.count]);
  const asideCards = [
    renderWorkbenchModeCard(currentPayload.route_path),
    renderWorkbenchInstanceContextCard(currentPayload),
    renderCard("Derivation Graph", `${renderStatGrid(relationCounts)}`),
  ];
  if (relatedPayload) {
    asideCards.push(
      renderCard(
        "Selected Related Instance",
        `${renderStatGrid([
          ["Relation", `${selectedRelation.groupLabel} · ${selectedRelation.label}`],
          ["Problem", relatedPayload.summary.problem_type],
          ["Family", relatedPayload.summary.benchmark_name],
          ["Variant", relatedPayload.summary.metric_variant || "historical"],
          ["Place", relatedPayload.summary.place_slug || relatedPayload.summary.historical_topology_type || "n/a"],
          ["Size", relatedPayload.summary.size_bucket],
          ["Customers", relatedPayload.summary.num_customers],
        ])}<div class="inline-actions" style="margin-top:0.8rem"><a class="mini-link" href="${routeHref(relatedPayload.route_path)}">Open public page</a></div>`,
      ),
      renderWorkbenchSelectedObjectiveCard(relatedPreview?.selectedEntry || null),
      renderWorkbenchArtifactsCard(relatedPayload),
    );
  } else {
    asideCards.push(renderCard("Selected Related Instance", '<div class="empty-state">This instance does not expose any published source, derived, or sibling links.</div>'));
  }
  state.aside.innerHTML = asideCards.join("");

  const objectiveOptions = Array.isArray(relatedPayload?.bks_entries)
    ? relatedPayload.bks_entries.map((entry) => ({ value: entry.objective_function, label: entry.objective_function }))
    : [];
  const relationMarkup = relationGroups.map((group) => renderWorkbenchRelationGroup(currentPayload.route_path, group, selectedRelation?.routePath || null, selectedObjective)).join("");
  const previewMarkup = relatedPayload && relatedPreview
    ? `
      <section class="mini-card">
        <h2>Relation Preview</h2>
        ${renderPreviewSvg(relatedPreview.instanceData, relatedPreview.selectedBksData, relatedPreview.selectedEntry, {
          geometryMeta: relatedPreview.geometryMeta,
          metricVariant: relatedPayload.summary.metric_variant,
          viewerRenderMode: relatedPayload.summary.viewer_render_mode,
          roadCacheStatus: relatedPayload.summary.road_cache_status,
        })}
        <div class="preview-summary">
          <article class="mini-card">
            <h3>Current Instance</h3>
            ${renderStatGrid([
              ["Problem", currentPayload.summary.problem_type],
              ["Family", currentPayload.summary.benchmark_name],
              ["Variant", currentPayload.summary.metric_variant || "historical"],
              ["Customers", currentPayload.summary.num_customers],
            ])}
          </article>
          <article class="mini-card">
            <h3>Related Instance</h3>
            ${renderStatGrid([
              ["Relation", `${selectedRelation.groupLabel} · ${selectedRelation.label}`],
              ["Problem", relatedPayload.summary.problem_type],
              ["Family", relatedPayload.summary.benchmark_name],
              ["Variant", relatedPayload.summary.metric_variant || "historical"],
              ["Customers", relatedPayload.summary.num_customers],
            ])}
          </article>
        </div>
        <section class="mini-card">
          <h3>Route Legend</h3>
          ${renderWorkbenchRouteLegend(relatedPreview.selectedBksData?.routes)}
        </section>
      </section>`
    : '<section class="mini-card"><h2>Relation Preview</h2><div class="empty-state">No related instance is selected yet.</div></section>';

  state.stage.innerHTML = `
    <div class="viewer-stage">
      <section class="mini-card">
        <h2>Derivation Links</h2>
        ${relationMarkup || '<div class="empty-state">No source, derived, or sibling routes are published for this instance.</div>'}
        ${objectiveOptions.length > 0 ? `<form class="form-grid" data-derive-form>${renderWorkbenchSelectField("Related Objective", "objectiveFunction", objectiveOptions, selectedObjective, "Switch the active BKS overlay for the selected related instance.")}</form>` : ""}
        <div class="inline-actions">
          <a class="button-link primary" href="${routeHref('/workbench/')}?instance=${encodeURIComponent(currentPayload.route_path)}">Back To Benchmark Visualize</a>
          <a class="button-link" href="${routeHref(currentPayload.route_path)}">Open Current Public Instance</a>
        </div>
      </section>
      ${previewMarkup}
    </div>`;

  const objectiveSelect = state.stage.querySelector('select[name="objectiveFunction"]');
  objectiveSelect?.addEventListener("change", async (event) => {
    updateWorkbenchRuntimeParams({ objective: event.target.value || null });
    await renderWorkbenchDerivePage();
  });

  setStatus(relatedPreview?.selectedEntry ? `Showing ${relatedPreview.selectedEntry.objective_function}` : "Derive mode ready");
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

function parseUploadedInstanceJson(payload, fileName) {
  const rawCoordinates = Array.isArray(payload?.coordinates)
    ? payload.coordinates.map(normalizeGeometryPoint)
    : [];
  if (rawCoordinates.length === 0 || rawCoordinates.some((point) => !point)) {
    throw new Error(`JSON instance '${fileName}' does not expose a usable coordinates array.`);
  }

  const refPayload = payload?.reference_lla;
  const refLat = Number(refPayload?.lat);
  const refLon = Number(refPayload?.lon);
  const refAlt = Number.isFinite(Number(refPayload?.alt)) ? Number(refPayload.alt) : 0;
  const coordinates = (Number.isFinite(refLat) && Number.isFinite(refLon))
    ? rawCoordinates.map(([east, north]) => {
        const geo = enuToGeodetic(Number(east), Number(north), 0.0, refLat, refLon, refAlt);
        return [geo.lon, geo.lat];
      })
    : rawCoordinates;

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

function uploadedPreviewRoutesToMetaRoutes(routes, meta) {
  const nodeIds = Array.isArray(meta?.nodes)
    ? meta.nodes.map((node) => Number(node?.instance_node_id)).filter(Number.isFinite)
    : [];
  const offset = nodeIds.length > 0 && Math.min(...nodeIds) === 0 ? 0 : 1;
  return routes.map((route) => route.map((stopIndex) => stopIndex + offset));
}

function uploadedStraightRouteCoordinates(instanceData, routes) {
  const depotIndex = Number(instanceData?.depot || 0);
  const nodeCoordinates = Array.isArray(instanceData?.coordinates) ? instanceData.coordinates : [];
  return routes.map((route, routeIndex) => {
    const sequence = [depotIndex, ...route, depotIndex];
    return {
      routeIndex,
      coordinates: sequence.map((nodeIndex) => normalizeGeometryPoint(nodeCoordinates[nodeIndex])).filter(Boolean),
      source: "straight_line",
    };
  });
}

function uploadedRoadRouteCoordinates(roadGeojson) {
  const features = Array.isArray(roadGeojson?.features) ? roadGeojson.features : [];
  return features.map((feature, routeIndex) => ({
    routeIndex,
    coordinates: Array.isArray(feature?.geometry?.coordinates) ? feature.geometry.coordinates.map(normalizeGeometryPoint).filter(Boolean) : [],
    source: String(feature?.properties?.render_mode || "cached_road"),
  }));
}

function renderUploadedRoutePreviewSvg(instanceData, routes, options = {}) {
  const width = 860;
  const height = 520;
  const nodeCoordinates = Array.isArray(instanceData?.coordinates) ? instanceData.coordinates : [];
  if (nodeCoordinates.length === 0) {
    return '<div class="empty-state">The uploaded instance did not yield any previewable coordinates.</div>';
  }

  const roadRouteLines = uploadedRoadRouteCoordinates(options.roadGeojson);
  const hasRoadRoutes = roadRouteLines.length === routes.length && roadRouteLines.every((routeLine) => routeLine.coordinates.length >= 2);
  const routeLines = hasRoadRoutes ? roadRouteLines : uploadedStraightRouteCoordinates(instanceData, routes);
  const routeMembership = routeNodeLookup(routes);
  const projectedNodes = projectCoordinates(nodeCoordinates, width, height);
  const routePaths = routeLines
    .map((routeLine) => {
      const projectedRoute = projectCoordinates(routeLine.coordinates, width, height).filter(Boolean);
      if (projectedRoute.length < 2) {
        return "";
      }
      const route = routes[routeLine.routeIndex] || [];
      const routeTitle = `Route ID ${routeLine.routeIndex + 1} · ${route.length} customer${route.length === 1 ? "" : "s"} · ${String(routeLine.source).replaceAll("_", " ")}`;
      return `<g class="route-line"><title>${escapeHtml(routeTitle)}</title><polyline fill="none" stroke="${PALETTE[routeLine.routeIndex % PALETTE.length]}" stroke-width="3" stroke-linecap="round" stroke-linejoin="round" points="${projectedRoute.map((point) => `${point.x},${point.y}`).join(" ")}" /></g>`;
    })
    .join("");
  const nodes = projectedNodes
    .map((point, index) => {
      if (!point) {
        return "";
      }
      const isDepot = index === Number(instanceData?.depot || 0);
      const routeIndex = routeMembership.get(index);
      const nodeTitle = isDepot
        ? `Depot · ${routes.length} route${routes.length === 1 ? "" : "s"}`
        : routeIndex === undefined
          ? `Customer ID ${index} · no route`
          : `Customer ID ${index} · Route ID ${routeIndex + 1}`;
      return `<g class="viewer-node"><title>${escapeHtml(nodeTitle)}</title><circle cx="${point.x}" cy="${point.y}" r="${isDepot ? 6 : 4}" fill="${isDepot ? '#b83a06' : '#111111'}" opacity="${isDepot ? 1 : 0.84}" /></g>`;
    })
    .join("");

  const routeLegend = routes
    .map(
      (route, index) => `<div class="legend-item"><span class="legend-swatch" style="background:${PALETTE[index % PALETTE.length]}"></span><span>Route ${index + 1} · ${route.length} clients · load ${uploadedRouteLoad(route, instanceData)}</span></div>`,
    )
    .join("");

  return `
    <div class="viewer-toolbar">
      <div>${badge(`${instanceData.name || "Upload"} · ${routes.length} route${routes.length === 1 ? "" : "s"}`, true)}</div>
      <div class="meta-line">${escapeHtml(hasRoadRoutes ? `Road-following preview (${options.metric || "shortest"})` : "Straight-line preview from uploaded instance coordinates")}</div>
    </div>
    <div class="viewer-frame">
      <svg viewBox="0 0 ${width} ${height}" role="img" aria-label="Uploaded routing preview">${routePaths}${nodes}</svg>
    </div>
    <div class="preview-summary">
      <article class="mini-card">
        <h3>Upload Summary</h3>
        ${renderStatGrid([
          ["Instance", instanceData.name || "n/a"],
          ["Nodes", instanceData.dimension || nodeCoordinates.length],
          ["Routes", routes.length],
          ["Coverage", options.solutionInfo?.coverage || "n/a"],
          ["Route ids", options.solutionInfo?.mode || "n/a"],
          ["Render", options.renderSummary?.render_mode || (hasRoadRoutes ? "cached_road" : "straight_line")],
        ])}
      </article>
      <article class="mini-card">
        <h3>Routes</h3>
        <div class="route-legend">${routeLegend}</div>
      </article>
    </div>`;
}

async function renderWorkbenchGeneratePage() {
  const instanceRoute = runtimeParams.get("instance");
  const instancePayload = await loadWorkbenchInstanceContext(instanceRoute);
  const benchmarkCitySlug = String(instancePayload?.summary?.place_slug || "").trim().toLowerCase();
  const benchmarkCustomerCount = Number(instancePayload?.summary?.num_customers);

  setPage(
    "Workbench: Generate",
    instancePayload
      ? "Preview generation parameters against local OSM-backed Mamut2026 data, starting from the selected benchmark instance context."
      : "Preview generation parameters against local OSM-backed Mamut2026 data before exporting new instances.",
    [{ label: "Workbench", route_path: "/workbench/" }],
    "explorer",
  );

  state.aside.innerHTML = [
    renderWorkbenchModeCard(instanceRoute),
    renderWorkbenchInstanceContextCard(instancePayload),
    renderCard(
      "Preview Contract",
      '<p class="meta-line" id="generationModeHint">Loading generation preview capabilities…</p>',
    ),
    renderCard(
      "Source Data",
      '<p class="meta-line">City options come from local MAMUT OSM extracts under osmdata/. Generated sample sizes come from local instances_v2/osm when present.</p>',
    ),
  ].join("");

  state.stage.innerHTML = `
    <div class="viewer-stage">
      <section class="mini-card">
        <h2>Generation Parameters</h2>
        <form class="form-grid" data-generation-form>
          <label class="form-field">
            <span>City</span>
            <select name="city" required></select>
            <small class="field-hint" data-size-hint>Loading city sizes…</small>
          </label>
          <label class="form-field">
            <span>Method</span>
            <select name="method">
              <option value="poi_categories">poi_categories</option>
              <option value="hybrid">hybrid</option>
              <option value="parametric_attach">parametric_attach</option>
            </select>
            <small class="field-hint">Preview honors live OSM parameters when raw extracts are configured.</small>
          </label>
          <label class="form-field">
            <span>Customers</span>
            <input name="nCustomers" type="number" min="2" step="1" value="51" />
            <small class="field-hint">Use generated sizes for the closest local sample-backed preview.</small>
          </label>
          <label class="form-field">
            <span>Seed</span>
            <input name="seed" type="number" step="1" value="0" />
            <small class="field-hint">Kept for parity with the MAMUT OSM generator.</small>
          </label>
          <label class="form-field">
            <span>Depot Mode</span>
            <select name="depotMode">
              <option value="center">center</option>
              <option value="random">random</option>
              <option value="corner">corner</option>
            </select>
            <small class="field-hint">Matches the local preview request contract.</small>
          </label>
          <label class="form-field">
            <span>Customer Mode</span>
            <select name="customerMode">
              <option value="random_clustered">random_clustered</option>
              <option value="random">random</option>
              <option value="clustered">clustered</option>
            </select>
            <small class="field-hint">Used for live parametric or hybrid previews.</small>
          </label>
          <label class="form-field">
            <span>Cluster Seeds</span>
            <input name="clusterSeeds" type="number" min="1" step="1" value="4" />
            <small class="field-hint">Relevant for clustered and hybrid previews.</small>
          </label>
          <label class="form-field">
            <span>Cluster Decay (m)</span>
            <input name="clusterDecayMeters" type="number" min="100" step="50" value="800" />
            <small class="field-hint">Controls clustering radius in the live generator.</small>
          </label>
          <label class="form-field">
            <span>Hybrid POI Share</span>
            <input name="hybridPoiShare" type="number" min="0" max="1" step="0.05" value="0.5" />
            <small class="field-hint">Blend between POI and parametric placement for hybrid mode.</small>
          </label>
          <label class="form-field form-field-wide">
            <span>POI Categories</span>
            <input name="categories" type="text" value="restaurant,cafe" />
            <small class="field-hint">Comma-separated categories used by POI and hybrid generation modes.</small>
          </label>
          <label class="form-field checkbox-field form-field-wide">
            <input name="onlyIntersections" type="checkbox" checked />
            <span>Restrict live previews to road intersections when raw OSM extracts are configured.</span>
          </label>
          <div class="inline-actions form-field-wide">
            <button type="submit" class="button-link primary" data-preview-button>Preview Selection</button>
          </div>
        </form>
      </section>
      <section class="mini-card">
        <h2>Preview Surface</h2>
        <div class="preview-shell" data-generation-preview>
          <div class="empty-state">Submit generation parameters to load a preview.</div>
        </div>
      </section>
    </div>`;

  const modeHint = state.aside.querySelector("#generationModeHint");
  const form = state.stage.querySelector("[data-generation-form]");
  const citySelect = form.querySelector('select[name="city"]');
  const customersInput = form.querySelector('input[name="nCustomers"]');
  const sizeHint = form.querySelector("[data-size-hint]");
  const previewButton = form.querySelector("[data-preview-button]");
  const previewRoot = state.stage.querySelector("[data-generation-preview]");

  if (Number.isFinite(benchmarkCustomerCount) && benchmarkCustomerCount > 0) {
    customersInput.value = String(benchmarkCustomerCount);
  }

  if (window.location.protocol === "file:") {
    const message = "Generation preview requires the Paper7 site API server. Open the workbench over HTTP instead of file://.";
    modeHint.textContent = message;
    previewRoot.innerHTML = `<div class="empty-state">${escapeHtml(message)}</div>`;
    setStatus("Generation preview requires the site API server");
    return;
  }

  setStatus("Loading generation preview options…");
  let cityOptions;
  try {
    const response = await fetchWorkbenchJson(WORKBENCH_GENERATION_CITIES_PATH);
    cityOptions = Array.isArray(response.cities) ? response.cities : [];
    if (cityOptions.length === 0) {
      throw new Error("No local OSM cities are available for generation preview.");
    }

    citySelect.innerHTML = cityOptions
      .map((city, index) => `<option value="${escapeHtml(city.slug)}"${index === 0 ? " selected" : ""}>${escapeHtml(city.label || city.slug)}</option>`)
      .join("");

    const cityLookup = new Map(cityOptions.map((city) => [city.slug, city]));
    if (benchmarkCitySlug && cityLookup.has(benchmarkCitySlug)) {
      citySelect.value = benchmarkCitySlug;
    }

    const updateSizeHint = () => {
      const city = cityLookup.get(citySelect.value);
      if (!city) {
        sizeHint.textContent = "No generated sizes are registered for the selected city.";
        return;
      }
      const counts = Array.isArray(city.customer_counts) ? city.customer_counts : [];
      if (counts.length > 0) {
        sizeHint.textContent = `Generated sizes: ${counts.join(", ")}`;
        if (!customersInput.value) {
          customersInput.value = String(counts[0]);
        }
      } else {
        sizeHint.textContent = "No generated sizes are registered for the selected city.";
      }
    };

    citySelect.addEventListener("change", updateSizeHint);
    updateSizeHint();

    modeHint.textContent = response.preview_available
      ? "Live preview is available because local raw OSM extracts are configured."
      : "Raw OSM extracts are not configured here, so preview uses local generated Mamut2026 samples when available.";
    setStatus(`Loaded ${cityOptions.length} generation preview cities`);
  } catch (error) {
    const message = error.message || String(error);
    modeHint.textContent = message;
    previewRoot.innerHTML = `<div class="empty-state">${escapeHtml(message)}</div>`;
    setStatus("Generation preview options unavailable");
    return;
  }

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const payload = buildGenerationPreviewPayload(new FormData(form));
    previewButton.disabled = true;
    previewRoot.innerHTML = '<div class="empty-state">Loading generation preview…</div>';
    setStatus(`Generating preview for ${payload.city}…`);
    try {
      const response = await postWorkbenchJson(WORKBENCH_GENERATION_PREVIEW_PATH, payload);
      previewRoot.innerHTML = renderGenerationPreviewSvg(response.geojson, response.summary || {});
      setStatus(`Preview ready for ${response.summary?.city || payload.city}`);
    } catch (error) {
      previewRoot.innerHTML = `<div class="empty-state">${escapeHtml(error.message || String(error))}</div>`;
      setStatus("Generation preview failed");
    } finally {
      previewButton.disabled = false;
    }
  });
}

async function renderWorkbenchUploadPage() {
  const instanceRoute = runtimeParams.get("instance");
  const instancePayload = await loadWorkbenchInstanceContext(instanceRoute);

  setPage(
    "Workbench: Visualize Uploads",
    "Load local .vrp or .json instances, attach .sol or JSON routes, and optionally use a metadata sidecar to request road-following geometry.",
    [{ label: "Workbench", route_path: "/workbench/" }],
    "explorer",
  );

  state.aside.innerHTML = [
    renderWorkbenchModeCard(instanceRoute),
    renderWorkbenchVisualizeSourceCard(instanceRoute),
    renderWorkbenchInstanceContextCard(instancePayload),
    renderCard(
      "Upload Contract",
      '<p class="meta-line">The instance input accepts .vrp and benchmark-style .json files. The solution input accepts .sol and JSON route payloads. Metadata sidecars are optional but enable road-following rendering.</p>',
    ),
  ].join("");

  state.stage.innerHTML = `
    <div class="viewer-stage">
      <section class="mini-card">
        <h2>Upload Files</h2>
        <form class="form-grid" data-upload-form>
          <label class="form-field">
            <span>Instance (.vrp or .json)</span>
            <input name="instanceFile" type="file" accept=".vrp,.json,.txt" required />
            <small class="field-hint">Use benchmark vrp.json files or original .vrp exports with embedded reference LLA.</small>
          </label>
          <label class="form-field">
            <span>Solution (.sol or .json)</span>
            <input name="solutionFile" type="file" accept=".sol,.json,.txt" required />
            <small class="field-hint">JSON solutions can be either a raw routes array or an object with a routes field.</small>
          </label>
          <label class="form-field">
            <span>Metadata sidecar (.json)</span>
            <input name="metaFile" type="file" accept=".json" />
            <small class="field-hint">Optional. When present, the workbench can request road-following geometry from embedded road cache data.</small>
          </label>
          <label class="form-field">
            <span>Route metric</span>
            <select name="metric">
              <option value="shortest">shortest</option>
              <option value="fastest">fastest</option>
              <option value="euclidean">euclidean</option>
            </select>
            <small class="field-hint">Used only when a metadata sidecar is supplied and the site API is available.</small>
          </label>
          <label class="form-field checkbox-field form-field-wide">
            <input name="preferRoadGeometry" type="checkbox" checked />
            <span>Prefer road-following geometry when a metadata sidecar is available.</span>
          </label>
          <div class="inline-actions form-field-wide">
            <button type="submit" class="button-link primary" data-upload-preview-button>Preview Uploads</button>
          </div>
        </form>
      </section>
      <section class="mini-card">
        <h2>Preview Surface</h2>
        <div class="preview-shell" data-upload-preview>
          <div class="empty-state">Upload an instance and a solution to render a preview.</div>
        </div>
      </section>
    </div>`;

  const form = state.stage.querySelector("[data-upload-form]");
  const previewButton = state.stage.querySelector("[data-upload-preview-button]");
  const previewRoot = state.stage.querySelector("[data-upload-preview]");

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const formData = new FormData(form);
    const instanceFile = form.querySelector('input[name="instanceFile"]').files?.[0];
    const solutionFile = form.querySelector('input[name="solutionFile"]').files?.[0];
    const metaFile = form.querySelector('input[name="metaFile"]').files?.[0] || null;
    if (!instanceFile || !solutionFile) {
      previewRoot.innerHTML = '<div class="empty-state">Both an instance file and a solution file are required.</div>';
      return;
    }

    previewButton.disabled = true;
    previewRoot.innerHTML = '<div class="empty-state">Loading uploaded files…</div>';
    setStatus(`Parsing ${instanceFile.name} and ${solutionFile.name}…`);
    try {
      const [instanceText, solutionText, metaText] = await Promise.all([
        instanceFile.text(),
        solutionFile.text(),
        metaFile ? metaFile.text() : Promise.resolve(null),
      ]);

      const instanceData = parseUploadedInstanceText(instanceText, instanceFile.name);
      const solutionPayload = parseUploadedSolutionText(solutionText, solutionFile.name, instanceData.dimension);
      const metaPayload = metaText && metaFile ? parseUploadedMetaText(metaText, metaFile.name) : null;
      const metric = String(formData.get("metric") || "shortest");
      const preferRoadGeometry = formData.get("preferRoadGeometry") === "on";

      let roadResponse = null;
      if (preferRoadGeometry && metaPayload && window.location.protocol !== "file:") {
        try {
          roadResponse = await postWorkbenchJson(WORKBENCH_RENDER_ROUTES_PATH, {
            meta: metaPayload,
            routes: uploadedPreviewRoutesToMetaRoutes(solutionPayload.routes, metaPayload),
            metric,
          });
        } catch (error) {
          console.warn("Unable to render uploaded road geometry", error);
        }
      }

      previewRoot.innerHTML = renderUploadedRoutePreviewSvg(instanceData, solutionPayload.routes, {
        metric,
        roadGeojson: roadResponse?.geojson || null,
        renderSummary: roadResponse?.summary || null,
        solutionInfo: solutionPayload.info,
      });
      setStatus(`Preview ready for ${instanceData.name || instanceFile.name}`);
    } catch (error) {
      previewRoot.innerHTML = `<div class="empty-state">${escapeHtml(error.message || String(error))}</div>`;
      setStatus("Upload preview failed");
    } finally {
      previewButton.disabled = false;
    }
  });
}

function renderObjectives(payload) {
  setPage(payload.title, "Objective semantics are part of the benchmark contract, not a display detail.", [], "editorial");
  state.aside.innerHTML = renderCard(
    "Objective Quick Nav",
    `<div class="chip-row">${payload.explainers.map((explainer) => `<a class="selector-chip" href="#${escapeHtml(explainer.objective_function)}">${escapeHtml(explainer.short_label)}</a>`).join("")}</div>`,
  );
  state.stage.innerHTML = `<div class="explainer-grid">${payload.explainers
    .map(
      (explainer) => `<article class="mini-card" id="${escapeHtml(explainer.objective_function)}"><div class="badge-row">${badge(explainer.short_label)}${badge(explainer.objective_function, true)}</div><h3>${escapeHtml(explainer.title)}</h3><p>${escapeHtml(explainer.description)}</p><ul class="plain-list">${explainer.interpretation_notes.map((note) => `<li>${escapeHtml(note)}</li>`).join("")}</ul><h4 style="margin-top:0.9rem">Related Families</h4><ul class="link-list">${explainer.related_routes.map((entry) => `<li><a href="${routeHref(entry.route_path)}">${escapeHtml(entry.label)}</a> <span class="meta-line">${entry.instance_count} instances · ${entry.bks_count} BKS</span></li>`).join("")}</ul></article>`,
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

function renderWorkbenchPlaceholder() {
  const instanceRoute = runtimeParams.get("instance");
  setPage("Workbench", "The shared workbench shell is reserved for expert interactions and will hydrate benchmark-backed state next.", [], "explorer");
  state.aside.innerHTML = [
    renderWorkbenchModeCard(instanceRoute),
    renderWorkbenchVisualizeSourceCard(instanceRoute),
    renderCard(
      "Requested Instance",
      instanceRoute ? `<p class="mono-block">${escapeHtml(instanceRoute)}</p><div class="inline-actions"><a class="button-link primary" href="${routeHref(instanceRoute)}">Back to Instance</a></div>` : `<div class="empty-state">Open an instance page and use the workbench action to arrive here with context.</div>`,
    ),
  ].join("");
  state.stage.innerHTML = `<div class="viewer-stage"><section class="mini-card"><h2>Workbench Shell Placeholder</h2><p>The static shell is in place so benchmark pages can link into one shared workbench surface. The next slice will hydrate catalog-backed loading, uploads, generation drafts, and derivation-aware flows here.</p><div class="inline-actions"><a class="button-link primary" href="${routeHref('/benchmarks/')}">Browse Benchmarks</a></div></section></div>`;
  setStatus(`Workbench mode: ${state.workbenchMode}`);
}

async function renderWorkbenchPage() {
  if (state.workbenchMode === "generate") {
    await renderWorkbenchGeneratePage();
    return;
  }

  if (state.workbenchMode === "upload") {
    await renderWorkbenchUploadPage();
    return;
  }

  if (state.workbenchMode === "derive") {
    await renderWorkbenchDerivePage();
    return;
  }


  await renderWorkbenchBenchmarkPage();
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
  const themeIcon = document.getElementById("themeIcon");
  switchInput.checked = theme === "dark";
  themeIcon.innerHTML = theme === "dark" ? "&#9728;" : "&#9790;";
  localStorage.setItem("mamut-routing-theme", theme);
}

function setupThemeToggle() {
  const storedTheme = localStorage.getItem("mamut-routing-theme");
  const prefersDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
  applyTheme(storedTheme || (prefersDark ? "dark" : "light"));
  document.getElementById("themeSwitch").addEventListener("change", (event) => {
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
    if (state.pageKind === "workbench-placeholder") {
      await renderWorkbenchPage();
      return;
    }
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
  buildGenerationPreviewPayload,
  escapeHtml,
  fetchJson,
  fetchWorkbenchJson,
  fetchWorkbenchPayloadForRoute,
  loadWorkbenchInstanceContext,
  normalizeRoute,
  parseUploadedInstanceText,
  parseUploadedMetaText,
  parseUploadedSolutionText,
  postWorkbenchJson,
  relativeFromCurrent,
  resolvePreviewGeometry,
  routeHref,
  setupThemeToggle,
  uploadedPreviewRoutesToMetaRoutes,
};

if (!window.__PAPER7_SITE_NO_BOOTSTRAP__) {
  void init();
}
