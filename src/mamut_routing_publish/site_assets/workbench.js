const body = document.body;
const runtimeParams = new URLSearchParams(window.location.search);
const CANONICAL_WORKBENCH_ROUTE = "/workbench/";
const WORKBENCH_RENDER_ROUTES_PATH = "/api/workbench/render-routes";
const WORKBENCH_GENERATION_CITIES_PATH = "/api/workbench/generation/cities";
const WORKBENCH_GENERATION_PREVIEW_PATH = "/api/workbench/generation/preview";
const WORKBENCH_GENERATION_GENERATE_PATH = "/api/workbench/generation/generate";
const WORKBENCH_GENERATION_SINGLE_PATH = "/api/workbench/generation/single";
const WORKBENCH_GENERATION_SINGLE_DOWNLOAD_PATH = "/api/workbench/generation/single-download";
const WORKBENCH_GENERATION_BULK_PATH = "/api/workbench/generation/bulk";
const WORKBENCH_GENERATION_BULK_DOWNLOAD_PATH = "/api/workbench/generation/bulk-download";
const WORKBENCH_GENERATION_FETCH_OSM_PATH = "/api/workbench/generation/fetch-osm-city";
const ROUTE_COLORS = [
  "#e63946",
  "#457b9d",
  "#2a9d8f",
  "#f4a261",
  "#8d5a97",
  "#264653",
  "#d62828",
  "#3a86ff",
  "#06d6a0",
  "#ff7f51",
  "#e76f51",
  "#1d3557",
  "#ff006e",
  "#4d908e",
  "#bc6c25",
];
const MODE_BY_ROUTE = new Map([
  ["/workbench/", "catalog"],
  ["/workbench/catalog/", "catalog"],
  ["/workbench/upload/", "upload"],
  ["/workbench/generate/", "generate"],
]);

function normalizeWorkbenchRoute(routePath) {
  if (!routePath || routePath === "/") {
    return "/";
  }
  const trimmed = String(routePath).replace(/^\/+/, "").replace(/\/+$/, "");
  return `/${trimmed}/`;
}

function resolveWorkbenchMode(routePath) {
  const explicitMode = runtimeParams.get("mode");
  if (explicitMode === "upload" || explicitMode === "generate") {
    return explicitMode;
  }
  return MODE_BY_ROUTE.get(normalizeWorkbenchRoute(routePath)) || body.dataset.workbenchMode || "catalog";
}

function redirectLegacyDeriveMode() {
  if (runtimeParams.get("mode") !== "derive") {
    return false;
  }
  if (window.location.protocol === "file:") {
    return false;
  }
  const nextParams = new URLSearchParams(window.location.search);
  nextParams.delete("mode");
  nextParams.delete("deriveTarget");
  const nextQuery = nextParams.toString();
  window.location.replace(`${CANONICAL_WORKBENCH_ROUTE}${nextQuery ? `?${nextQuery}` : ""}`);
  return true;
}

function canonicalizeWorkbenchLocation(routePath, workbenchMode) {
  if (window.location.protocol === "file:") {
    return;
  }

  const normalizedRoute = normalizeWorkbenchRoute(routePath);
  if (normalizedRoute === CANONICAL_WORKBENCH_ROUTE) {
    return;
  }

  if (!MODE_BY_ROUTE.has(normalizedRoute)) {
    return;
  }

  const nextParams = new URLSearchParams(window.location.search);
  if (workbenchMode === "catalog") {
    nextParams.delete("mode");
  } else {
    nextParams.set("mode", workbenchMode);
  }
  const nextQuery = nextParams.toString();
  const nextUrl = `${CANONICAL_WORKBENCH_ROUTE}${nextQuery ? `?${nextQuery}` : ""}`;
  window.history.replaceState({}, "", nextUrl);
}

if (!body.dataset.pageKind) {
  body.dataset.pageKind = "workbench-app";
}

const initialRoutePath = body.dataset.routePath || CANONICAL_WORKBENCH_ROUTE;
redirectLegacyDeriveMode();
const initialWorkbenchMode = resolveWorkbenchMode(initialRoutePath);
body.dataset.routePath = CANONICAL_WORKBENCH_ROUTE;
body.dataset.workbenchMode = initialWorkbenchMode;
body.dataset.workbenchSurface = "dedicated";
canonicalizeWorkbenchLocation(initialRoutePath, initialWorkbenchMode);

window.__PAPER7_SITE_NO_BOOTSTRAP__ = true;
const siteHelpers = await import("./site.js");
delete window.__PAPER7_SITE_NO_BOOTSTRAP__;

const {
  artifactHref,
  escapeHtml,
  fetchJson,
  fetchWorkbenchJson,
  fetchWorkbenchPayloadForRoute,
  normalizeRoute,
  parseUploadedInstanceText,
  parseUploadedMetaText,
  parseUploadedSolutionText,
  postWorkbenchBlob,
  postWorkbenchJson,
  resolvePreviewGeometry,
  routeHref,
  setupThemeToggle,
  uploadedPreviewRoutesToMetaRoutes,
} = siteHelpers;

const tabVisualize = document.getElementById("tabVisualize");
const tabGenerate = document.getElementById("tabGenerate");
const visualPanel = document.getElementById("visualPanel");
const generationPanel = document.getElementById("generationPanel");
const sourceBenchmarkBtn = document.getElementById("sourceBenchmarkBtn");
const sourceUploadBtn = document.getElementById("sourceUploadBtn");
const benchmarkVisualPanel = document.getElementById("benchmarkVisualPanel");
const uploadVisualPanel = document.getElementById("uploadVisualPanel");
const benchmarkCatalogSelect = document.getElementById("benchmarkCatalogSelect");
const benchmarkInstanceSelect = document.getElementById("benchmarkInstanceSelect");
const benchmarkStatus = document.getElementById("benchmarkStatus");
const benchmarkRenderStatus = document.getElementById("benchmarkRenderStatus");
const objectiveField = document.getElementById("objectiveField");
const benchmarkObjectiveSelect = document.getElementById("benchmarkObjectiveSelect");
const openBenchmarkBtn = document.getElementById("openBenchmarkBtn");
const browseBenchmarksBtn = document.getElementById("browseBenchmarksBtn");
const vrpInput = document.getElementById("vrpInput");
const solInput = document.getElementById("solInput");
const metaInput = document.getElementById("metaInput");
const apiUrlInput = document.getElementById("apiUrlInput");
const metricSelect = document.getElementById("metricSelect");
const roadBtn = document.getElementById("roadBtn");
const solveBtn = document.getElementById("solveBtn");
const saveHgsBtn = document.getElementById("saveHgsBtn");
const solveTimeLimitInput = document.getElementById("solveTimeLimitInput");
const clearBtn = document.getElementById("clearBtn");
const statsEl = document.getElementById("stats");
const routeLegendEl = document.getElementById("routeLegend");
const toastEl = document.getElementById("toast");
const routeSelectorCard = document.getElementById("routeSelectorCard");
const routeSelectorContainer = document.getElementById("routeSelectorContainer");
const genCitySelect = document.getElementById("genCitySelect");
const genMethodSelect = document.getElementById("genMethodSelect");
const genCustomersInput = document.getElementById("genCustomersInput");
const genSeedInput = document.getElementById("genSeedInput");
const genOnlyIntersectionsInput = document.getElementById("genOnlyIntersectionsInput");
const genDepotModeSelect = document.getElementById("genDepotModeSelect");
const genCustomerModeSelect = document.getElementById("genCustomerModeSelect");
const genClusterSeedsInput = document.getElementById("genClusterSeedsInput");
const genClusterDecayInput = document.getElementById("genClusterDecayInput");
const genHybridShareInput = document.getElementById("genHybridShareInput");
const genHybridShareValue = document.getElementById("genHybridShareValue");
const genDemandTypeSelect = document.getElementById("genDemandTypeSelect");
const genAvgRouteSizeSelect = document.getElementById("genAvgRouteSizeSelect");
const genPoiList = document.getElementById("genPoiList");
const genPoiCount = document.getElementById("genPoiCount");
const genPoiSelectAllBtn = document.getElementById("genPoiSelectAllBtn");
const genPoiClearBtn = document.getElementById("genPoiClearBtn");
const genDisplayBtn = document.getElementById("genDisplayBtn");
const genGenerateBtn = document.getElementById("genGenerateBtn");
const genFilesBtn = document.getElementById("genFilesBtn");
const genResult = document.getElementById("genResult");
const generationNote = document.getElementById("generationNote");
const openBulkModalBtn = document.getElementById("openBulkModalBtn");
const closeBulkModalBtn = document.getElementById("closeBulkModalBtn");
const closeBulkModalBtn2 = document.getElementById("closeBulkModalBtn2");
const bulkModal = document.getElementById("bulkModal");
const bulkCountBadge = document.getElementById("bulkCountBadge");
const bulkModalCount = document.getElementById("bulkModalCount");
const genBulkCitiesSelect = document.getElementById("genBulkCitiesSelect");
const bulkCityCount = document.getElementById("bulkCityCount");
const bulkCitySelectAllBtn = document.getElementById("bulkCitySelectAllBtn");
const bulkCityClearBtn = document.getElementById("bulkCityClearBtn");
const genBulkCustomersInput = document.getElementById("genBulkCustomersInput");
const bulkDemandChecks = document.getElementById("bulkDemandChecks");
const bulkRouteSizeChecks = document.getElementById("bulkRouteSizeChecks");
const bulkExpandBtn = document.getElementById("bulkExpandBtn");
const bulkAddRowBtn = document.getElementById("bulkAddRowBtn");
const bulkDeleteSelBtn = document.getElementById("bulkDeleteSelBtn");
const bulkClearBtn = document.getElementById("bulkClearBtn");
const bulkImportCsvBtn = document.getElementById("bulkImportCsvBtn");
const bulkExportCsvBtn = document.getElementById("bulkExportCsvBtn");
const bulkCsvFileInput = document.getElementById("bulkCsvFileInput");
const bulkSelectAll = document.getElementById("bulkSelectAll");
const bulkTableBody = document.getElementById("bulkTableBody");
const genBulkBtn = document.getElementById("genBulkBtn");
const genFetchCityInput = document.getElementById("genFetchCityInput");
const genFetchCountryInput = document.getElementById("genFetchCountryInput");
const genFetchPaddingInput = document.getElementById("genFetchPaddingInput");
const genFetchBtn = document.getElementById("genFetchBtn");
const genProblemTypeSelect = document.getElementById("genProblemTypeSelect");
const genTwMethodSelect = document.getElementById("genTwMethodSelect");
const genTwHorizonStartInput = document.getElementById("genTwHorizonStartInput");
const genTwHorizonEndInput = document.getElementById("genTwHorizonEndInput");
const genVrptwFieldset = document.getElementById("genVrptwFieldset");
const bulkProblemTypeSelect = document.getElementById("bulkProblemTypeSelect");
const bulkTwMethodSelect = document.getElementById("bulkTwMethodSelect");

const VRPTW_TW_METHODS = ["route_centered", "reachable_interval"];
const VRPTW_TW_METHOD_LABELS = {
  route_centered: "Route-centered",
  reachable_interval: "Reachable-interval",
};
const PROBLEM_TYPES = ["CVRP", "VRPTW"];
const VRPTW_DEFAULT_HORIZON_START = 0;
const VRPTW_DEFAULT_HORIZON_END = 86400;

const POI_CATEGORIES = [
  "restaurant", "cafe", "bar", "fast_food", "pub", "school", "university",
  "hospital", "clinic", "pharmacy", "dentist", "doctors", "veterinary",
  "bank", "atm", "post_office", "police", "fire_station", "townhall", "courthouse",
  "library", "theatre", "cinema", "arts_centre", "community_centre", "museum",
  "place_of_worship", "marketplace", "fuel", "charging_station", "car_wash", "parking",
  "bus_station", "taxi", "bicycle_rental", "ferry_terminal", "kindergarten", "college",
  "nightclub", "biergarten", "ice_cream", "food_court", "bench", "drinking_water",
  "toilets", "shower", "shelter", "waste_basket", "recycling",
];
const DEFAULT_POI_CATEGORIES = new Set([
  "restaurant", "cafe", "bar", "fast_food", "pub", "school", "university",
]);
const BULK_CSV_COLUMNS = [
  "problemType",
  "city",
  "nCustomers",
  "demandType",
  "avgRouteSize",
  "method",
  "seed",
  "depotMode",
  "customerMode",
  "twMethod",
  "onlyIntersections",
  "clusterSeeds",
  "clusterDecayMeters",
  "hybridPoiShare",
  "categories",
];
const BULK_INT_FIELDS = new Set(["demandType", "avgRouteSize", "seed", "clusterSeeds"]);
const BULK_FLOAT_FIELDS = new Set(["clusterDecayMeters", "hybridPoiShare"]);

const map = L.map("map", { zoomControl: true }).setView([48.8566, 2.3522], 11);
const osmBaseLayer = L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
  maxZoom: 20,
  attribution: "&copy; OpenStreetMap contributors",
});
const positronBaseLayer = L.tileLayer("https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png", {
  maxZoom: 20,
  subdomains: "abcd",
  attribution: "&copy; OpenStreetMap contributors &copy; CARTO",
});
const darkMatterBaseLayer = L.tileLayer("https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png", {
  maxZoom: 20,
  subdomains: "abcd",
  attribution: "&copy; OpenStreetMap contributors &copy; CARTO",
});
osmBaseLayer.addTo(map);
L.control.layers(
  {
    OpenStreetMap: osmBaseLayer,
    Positron: positronBaseLayer,
    "Dark Matter": darkMatterBaseLayer,
  },
  null,
  { position: "topright", collapsed: true },
).addTo(map);

const state = {
  activeTab: initialWorkbenchMode === "generate" ? "generate" : "visualize",
  sourceKind: initialWorkbenchMode === "upload" ? "upload" : "benchmark",
  instanceRoute: runtimeParams.get("instance"),
  objectiveFunction: runtimeParams.get("objective"),
  selectedRoutes: new Set(),
  lastApiError: null,
  benchmark: {
    payload: null,
    instanceData: null,
    meta: null,
    bksData: null,
    objectiveEntry: null,
    routes: [],
    roadGeojson: null,
    renderSummary: null,
  },
  benchmarkCatalog: {
    options: [],
    loaded: false,
    loadingPromise: null,
    selectedGroupKey: null,
  },
  upload: {
    instanceData: null,
    meta: null,
    routes: [],
    solutionInfo: null,
    roadGeojson: null,
    renderSummary: null,
    vrpText: null,
    vrpJsonPayload: null,
    vrpFileName: null,
  },
  generation: {
    cities: [],
    previewSummary: null,
    generated: null,
    bulkInstances: [],
    bulkNextId: 1,
    localOsmdataDir: null,
  },
  layers: {
    marker: L.layerGroup().addTo(map),
    route: L.layerGroup().addTo(map),
    arrow: L.layerGroup().addTo(map),
    preview: L.layerGroup().addTo(map),
  },
  view: {
    visualShouldFit: false,
    previewShouldFit: true,
  },
};

function refreshMapSize() {
  window.requestAnimationFrame(() => {
    map.invalidateSize();
  });
}

function showToast(message) {
  toastEl.textContent = message;
  toastEl.classList.add("show");
  window.clearTimeout(showToast.timer);
  showToast.timer = window.setTimeout(() => {
    toastEl.classList.remove("show");
  }, 2600);
}

function predictDuration(operationName, params = {}) {
  const customerCount = params.customers || 50;
  const routeCount = params.routes || 1;
  const stopCount = params.stops || customerCount;

  switch (operationName) {
    case "Rendering Road Geometry":
      return Math.max(3000, routeCount * 200 + stopCount * 20);
    case "Generating Preview":
      return Math.max(3000, 2000 + customerCount * 50);
    default:
      return 10000;
  }
}

const activeProgressTimers = new Map();

function startProgressBar(operationName, operationId, anchorEl, durationMs) {
  hideAllProgressBars();
  const progressItem = document.createElement("div");
  progressItem.className = "progress-item";
  progressItem.id = `progress-${operationId}`;
  progressItem.innerHTML = `
    <div class="progress-label">
      <span class="operation-name">${escapeHtml(operationName)}</span>
      <span class="progress-percent" id="percent-${operationId}">0%</span>
    </div>
    <div class="progress-bar-bg">
      <div class="progress-bar-fill" id="fill-${operationId}" style="width: 0%"></div>
    </div>
  `;

  if (anchorEl) {
    const parentCard = anchorEl.closest(".card");
    if (parentCard) {
      parentCard.insertAdjacentElement("afterend", progressItem);
    } else {
      anchorEl.insertAdjacentElement("afterend", progressItem);
    }
  } else {
    document.body.appendChild(progressItem);
  }

  const duration = durationMs || 10000;
  const startTime = performance.now();

  function tick() {
    const elapsed = performance.now() - startTime;
    const t = Math.min(elapsed / duration, 1);
    const percent = Math.round(90 * (1 - Math.pow(1 - t, 1.5)));
    const fillEl = document.getElementById(`fill-${operationId}`);
    const percentEl = document.getElementById(`percent-${operationId}`);
    if (fillEl) {
      fillEl.style.width = `${percent}%`;
    }
    if (percentEl) {
      percentEl.textContent = `${percent}%`;
    }
    if (t < 1) {
      activeProgressTimers.set(operationId, requestAnimationFrame(tick));
    }
  }

  activeProgressTimers.set(operationId, requestAnimationFrame(tick));
}

function completeProgressBar(operationId) {
  const rafId = activeProgressTimers.get(operationId);
  if (rafId) {
    cancelAnimationFrame(rafId);
    activeProgressTimers.delete(operationId);
  }
  const fillEl = document.getElementById(`fill-${operationId}`);
  const percentEl = document.getElementById(`percent-${operationId}`);
  if (fillEl) {
    fillEl.style.width = "100%";
  }
  if (percentEl) {
    percentEl.textContent = "100%";
  }
  window.setTimeout(() => {
    const progressEl = document.getElementById(`progress-${operationId}`);
    if (progressEl) {
      progressEl.remove();
    }
  }, 600);
}

function hideAllProgressBars() {
  for (const [operationId, rafId] of activeProgressTimers.entries()) {
    cancelAnimationFrame(rafId);
    const progressEl = document.getElementById(`progress-${operationId}`);
    if (progressEl) {
      progressEl.remove();
    }
  }
  activeProgressTimers.clear();
  document.querySelectorAll(".progress-item").forEach((element) => element.remove());
}

function currentRenderEndpoint() {
  const value = apiUrlInput.value.trim();
  return value || WORKBENCH_RENDER_ROUTES_PATH;
}

function currentVisualState() {
  return state.sourceKind === "upload" ? state.upload : state.benchmark;
}

function benchmarkCatalogLocator(value) {
  return value?.locator || value?.summary || {};
}

function benchmarkCatalogGroupKey(value) {
  const locator = benchmarkCatalogLocator(value);
  return [locator.problem_type, locator.benchmark_name].filter(Boolean).join("::");
}

function benchmarkCatalogGroupLabel(item) {
  const locator = benchmarkCatalogLocator(item);
  return [locator.problem_type, locator.benchmark_name].filter(Boolean).join(" · ") || "Published Instances";
}

const BENCHMARK_VARIANT_SORT_ORDER = ["euclidean", "fastest", "shortest"];

function benchmarkCatalogVariantSortKey(variant) {
  const normalizedVariant = String(variant || "").toLowerCase();
  const idx = BENCHMARK_VARIANT_SORT_ORDER.indexOf(normalizedVariant);
  return idx === -1 ? BENCHMARK_VARIANT_SORT_ORDER.length : idx;
}

function benchmarkCatalogCustomerCount(item) {
  const locator = benchmarkCatalogLocator(item);
  const directCount = Number(item?.num_customers);
  if (Number.isFinite(directCount)) {
    return directCount;
  }
  const sizeMatch = String(locator.size_bucket || "").match(/\d+/);
  return sizeMatch ? Number(sizeMatch[0]) : Number.POSITIVE_INFINITY;
}

function benchmarkCatalogInstanceGroupKey(item) {
  const locator = benchmarkCatalogLocator(item);
  return [locator.place_slug ?? "", benchmarkCatalogCustomerCount(item), item?.display_name || locator.instance_identifier || ""]
    .join("␟");
}

function benchmarkCatalogInstanceGroupLabel(item) {
  const locator = benchmarkCatalogLocator(item);
  const name = item?.display_name || locator.instance_identifier || "Published instance";
  const context = [];
  if (locator.place_slug) {
    context.push(locator.place_slug);
  }
  const customerCount = benchmarkCatalogCustomerCount(item);
  if (Number.isFinite(customerCount)) {
    context.push(`n=${customerCount}`);
  } else if (locator.size_bucket) {
    context.push(locator.size_bucket);
  }
  return context.length > 0 ? `${name} · ${context.join(" · ")}` : name;
}

function benchmarkCatalogOptionLabel(item) {
  const locator = benchmarkCatalogLocator(item);
  return locator.metric_variant || item?.metric_variant || item?.display_name || locator.instance_identifier || "Published instance";
}

function compareBenchmarkCatalogInstances(left, right) {
  return (
    benchmarkCatalogCustomerCount(left) - benchmarkCatalogCustomerCount(right)
    || String(benchmarkCatalogLocator(left).place_slug ?? "").localeCompare(String(benchmarkCatalogLocator(right).place_slug ?? ""))
    || String(left?.display_name || benchmarkCatalogLocator(left).instance_identifier || "").localeCompare(String(right?.display_name || benchmarkCatalogLocator(right).instance_identifier || ""))
  );
}

function buildBenchmarkCatalogInstanceGroups(items) {
  const groups = new Map();
  items.forEach((item) => {
    const key = benchmarkCatalogInstanceGroupKey(item);
    if (!groups.has(key)) {
      groups.set(key, { head: item, items: [] });
    }
    groups.get(key).items.push(item);
  });
  return groups;
}

function buildBenchmarkCatalogGroups() {
  const groups = new Map();
  state.benchmarkCatalog.options.forEach((item) => {
    const key = benchmarkCatalogGroupKey(item);
    if (!key) {
      return;
    }
    if (!groups.has(key)) {
      groups.set(key, { label: benchmarkCatalogGroupLabel(item), items: [] });
    }
    groups.get(key).items.push(item);
  });
  return groups;
}

function renderBenchmarkCatalogOptions() {
  if (!state.benchmarkCatalog.loaded) {
    if (!state.benchmarkCatalog.loadingPromise && benchmarkInstanceSelect.options.length === 0) {
      benchmarkCatalogSelect.innerHTML = '<option value="">Published families unavailable</option>';
      benchmarkCatalogSelect.disabled = true;
      benchmarkInstanceSelect.innerHTML = '<option value="">Published instances unavailable</option>';
      benchmarkInstanceSelect.disabled = true;
    }
    return;
  }

  const groups = buildBenchmarkCatalogGroups();
  const sortedGroups = Array.from(groups.entries()).sort(([, left], [, right]) => left.label.localeCompare(right.label));
  const selectedItem = state.instanceRoute
    ? state.benchmarkCatalog.options.find((item) => normalizeRoute(item.route_path) === normalizeRoute(state.instanceRoute))
    : null;
  const selectedGroupKey = selectedItem
    ? benchmarkCatalogGroupKey(selectedItem)
    : state.benchmarkCatalog.selectedGroupKey && groups.has(state.benchmarkCatalog.selectedGroupKey)
      ? state.benchmarkCatalog.selectedGroupKey
      : sortedGroups[0]?.[0] || "";
  state.benchmarkCatalog.selectedGroupKey = selectedGroupKey || null;

  if (sortedGroups.length > 0) {
    benchmarkCatalogSelect.innerHTML = sortedGroups
      .map(([groupKey, group]) => `<option value="${escapeHtml(groupKey)}"${groupKey === selectedGroupKey ? " selected" : ""}>${escapeHtml(group.label)}</option>`)
      .join("");
    benchmarkCatalogSelect.disabled = false;
  } else {
    benchmarkCatalogSelect.innerHTML = '<option value="">Published families unavailable</option>';
    benchmarkCatalogSelect.disabled = true;
  }

  const fragments = ['<option value="">Select a published variant…</option>'];
  const selectedGroupItems = selectedGroupKey ? groups.get(selectedGroupKey)?.items || [] : [];
  Array.from(buildBenchmarkCatalogInstanceGroups(selectedGroupItems).values())
    .sort((left, right) => compareBenchmarkCatalogInstances(left.head, right.head))
    .forEach((group) => {
      fragments.push(`<optgroup label="${escapeHtml(benchmarkCatalogInstanceGroupLabel(group.head))}">`);
      group.items
        .slice()
        .sort((left, right) => (
          benchmarkCatalogVariantSortKey(benchmarkCatalogOptionLabel(left)) - benchmarkCatalogVariantSortKey(benchmarkCatalogOptionLabel(right))
          || benchmarkCatalogOptionLabel(left).localeCompare(benchmarkCatalogOptionLabel(right))
        ))
        .forEach((item) => {
          fragments.push(`<option value="${escapeHtml(item.route_path)}">${escapeHtml(benchmarkCatalogOptionLabel(item))}</option>`);
        });
      fragments.push("</optgroup>");
    });

  benchmarkInstanceSelect.innerHTML = fragments.join("");
  benchmarkInstanceSelect.disabled = selectedGroupItems.length === 0;
  if (state.instanceRoute && selectedGroupItems.some((item) => normalizeRoute(item.route_path) === normalizeRoute(state.instanceRoute))) {
    benchmarkInstanceSelect.value = state.instanceRoute;
  } else {
    benchmarkInstanceSelect.value = "";
  }
}

async function loadBenchmarkCatalogOptions() {
  if (state.benchmarkCatalog.loaded) {
    renderBenchmarkCatalogOptions();
    return state.benchmarkCatalog.options;
  }
  if (state.benchmarkCatalog.loadingPromise) {
    return state.benchmarkCatalog.loadingPromise;
  }

  benchmarkCatalogSelect.disabled = true;
  benchmarkCatalogSelect.innerHTML = '<option value="">Loading published families…</option>';
  benchmarkInstanceSelect.disabled = true;
  benchmarkInstanceSelect.innerHTML = '<option value="">Loading published instances…</option>';

  state.benchmarkCatalog.loadingPromise = (async () => {
    const benchmarksPayload = await fetchWorkbenchPayloadForRoute("/benchmarks/");
    const problemRoutes = Array.isArray(benchmarksPayload?.problems)
      ? benchmarksPayload.problems.map((problem) => problem?.route_path).filter(Boolean)
      : [];
    const problemPayloads = await Promise.all(problemRoutes.map((routePath) => fetchWorkbenchPayloadForRoute(routePath)));
    const familyRoutes = problemPayloads.flatMap((payload) => (Array.isArray(payload?.families)
      ? payload.families.map((family) => family?.route_path).filter(Boolean)
      : []));
    const familyPayloads = await Promise.all(familyRoutes.map((routePath) => fetchWorkbenchPayloadForRoute(routePath)));

    const itemsByRoute = new Map();
    familyPayloads.forEach((payload) => {
      if (!Array.isArray(payload?.items)) {
        return;
      }
      payload.items.forEach((item) => {
        if (!item?.route_path || itemsByRoute.has(item.route_path)) {
          return;
        }
        itemsByRoute.set(item.route_path, item);
      });
    });

    state.benchmarkCatalog.options = Array.from(itemsByRoute.values()).filter(
      (item) => Boolean(item?.locator?.place_slug || item?.place_slug),
    );
    state.benchmarkCatalog.loaded = true;
    renderBenchmarkCatalogOptions();
    return state.benchmarkCatalog.options;
  })();

  try {
    return await state.benchmarkCatalog.loadingPromise;
  } catch (error) {
    console.error(error);
    benchmarkCatalogSelect.innerHTML = '<option value="">Unable to load published families</option>';
    benchmarkCatalogSelect.disabled = true;
    benchmarkInstanceSelect.innerHTML = '<option value="">Unable to load published instances</option>';
    benchmarkInstanceSelect.disabled = true;
    throw error;
  } finally {
    state.benchmarkCatalog.loadingPromise = null;
  }
}

function routeLoad(route, instanceData) {
  return route.reduce((total, stopIndex) => total + (Number(instanceData?.demands?.[stopIndex]) || 0), 0);
}

function clearMapLayers() {
  state.layers.marker.clearLayers();
  state.layers.route.clearLayers();
  state.layers.arrow.clearLayers();
  state.layers.preview.clearLayers();
}

function requestVisualFit() {
  state.view.visualShouldFit = true;
}

function consumeVisualFit(requestedFit) {
  if (requestedFit === true) {
    state.view.visualShouldFit = false;
    return true;
  }
  if (requestedFit === false) {
    return false;
  }
  const shouldFit = state.view.visualShouldFit;
  state.view.visualShouldFit = false;
  return shouldFit;
}

function requestPreviewFit() {
  state.view.previewShouldFit = true;
}

function consumePreviewFit(requestedFit) {
  if (requestedFit === true) {
    state.view.previewShouldFit = false;
    return true;
  }
  if (requestedFit === false) {
    return false;
  }
  const shouldFit = state.view.previewShouldFit;
  state.view.previewShouldFit = false;
  return shouldFit;
}

function updateVisualModePanels() {
  const benchmarkActive = state.sourceKind === "benchmark";
  benchmarkVisualPanel.hidden = !benchmarkActive;
  uploadVisualPanel.hidden = benchmarkActive;
}

function updateRouteCheckboxStates() {
  const allCheckbox = routeSelectorContainer.querySelector(".route-checkbox-all");
  const routeCheckboxes = routeSelectorContainer.querySelectorAll("input.route-checkbox:not(.route-checkbox-all)");
  if (allCheckbox) {
    allCheckbox.checked = state.selectedRoutes.size === 0;
  }
  routeCheckboxes.forEach((checkbox) => {
    const index = Number.parseInt(checkbox.dataset.routeIndex || "", 10);
    checkbox.checked = state.selectedRoutes.has(index);
  });
}

function buildRouteSelector(routes, instanceData) {
  if (!Array.isArray(routes) || routes.length < 2) {
    routeSelectorCard.style.display = "none";
    routeSelectorContainer.innerHTML = "";
    return;
  }

  routeSelectorCard.style.display = "block";
  routeSelectorContainer.innerHTML = "";

  const showAllLabel = document.createElement("label");
  showAllLabel.className = "route-checkbox-label";
  const showAllCheck = document.createElement("input");
  showAllCheck.type = "checkbox";
  showAllCheck.className = "route-checkbox route-checkbox-all";
  showAllCheck.checked = state.selectedRoutes.size === 0;
  showAllCheck.addEventListener("change", () => {
    if (showAllCheck.checked) {
      state.selectedRoutes.clear();
    } else {
      state.selectedRoutes.clear();
      for (let index = 0; index < routes.length; index += 1) {
        state.selectedRoutes.add(index);
      }
    }
    renderVisualState();
    updateRouteCheckboxStates();
  });
  showAllLabel.appendChild(showAllCheck);
  showAllLabel.appendChild(document.createTextNode("Show All Routes"));
  routeSelectorContainer.appendChild(showAllLabel);

  const divider = document.createElement("hr");
  divider.style.margin = "0.5rem 0";
  divider.style.opacity = "0.2";
  routeSelectorContainer.appendChild(divider);

  routes.forEach((route, index) => {
    const label = document.createElement("label");
    label.className = "route-checkbox-label";
    const checkbox = document.createElement("input");
    checkbox.type = "checkbox";
    checkbox.className = "route-checkbox";
    checkbox.dataset.routeIndex = String(index);
    checkbox.checked = state.selectedRoutes.has(index);
    checkbox.addEventListener("change", () => {
      if (checkbox.checked) {
        state.selectedRoutes.add(index);
      } else {
        state.selectedRoutes.delete(index);
      }
      renderVisualState();
      updateRouteCheckboxStates();
    });
    label.appendChild(checkbox);
    label.appendChild(document.createTextNode(`Route #${index + 1} (${route.length} stops, load ${routeLoad(route, instanceData)})`));
    routeSelectorContainer.appendChild(label);
  });

  updateRouteCheckboxStates();
}

function calculateBearing(from, to) {
  const lat1 = (from.lat * Math.PI) / 180;
  const lat2 = (to.lat * Math.PI) / 180;
  const dLon = ((to.lng - from.lng) * Math.PI) / 180;
  const y = Math.sin(dLon) * Math.cos(lat2);
  const x = Math.cos(lat1) * Math.sin(lat2) - Math.sin(lat1) * Math.cos(lat2) * Math.cos(dLon);
  return ((Math.atan2(y, x) * 180) / Math.PI + 360) % 360;
}

function getArrowSpacing() {
  const zoom = map.getZoom();
  if (zoom >= 16) return 150;
  if (zoom >= 14) return 300;
  if (zoom >= 12) return 600;
  if (zoom >= 10) return 1200;
  return 2500;
}

function addArrowsToPolyline(polyline, color) {
  const latlngs = polyline.getLatLngs();
  if (latlngs.length < 2) {
    return;
  }
  const spacingMeters = getArrowSpacing();
  let distSinceLastArrow = 0;
  for (let index = 1; index < latlngs.length; index += 1) {
    const from = latlngs[index - 1];
    const to = latlngs[index];
    if (from.lat === to.lat && from.lng === to.lng) {
      continue;
    }
    const segmentDistance = map.distance(from, to);
    if (segmentDistance < 3) {
      continue;
    }
    distSinceLastArrow += segmentDistance;
    if (distSinceLastArrow < spacingMeters) {
      continue;
    }
    const overshoot = distSinceLastArrow - spacingMeters;
    const interpolation = Math.max(0, Math.min(1, (segmentDistance - overshoot) / segmentDistance));
    const bearing = calculateBearing(from, to);
    const midpoint = L.latLng(from.lat + (to.lat - from.lat) * interpolation, from.lng + (to.lng - from.lng) * interpolation);
    const icon = L.divIcon({
      html: `<div style="transform: rotate(${bearing - 90}deg); transform-origin: 50% 50%; font-size: 10px; line-height: 10px; color: ${color}; font-weight: 700; opacity: 0.95;">▶</div>`,
      className: "arrow-marker",
      iconSize: [10, 10],
    });
    L.marker(midpoint, { icon }).addTo(state.layers.arrow);
    distSinceLastArrow = 0;
  }
}

function uploadedNodeCoordinatesFromMeta(instanceData, meta) {
  const fallbackCoordinates = Array.isArray(instanceData?.coordinates) ? instanceData.coordinates : [];
  const metaNodes = Array.isArray(meta?.nodes) ? meta.nodes : [];
  if (metaNodes.length === 0 || fallbackCoordinates.length === 0) {
    return fallbackCoordinates;
  }

  const instanceNodeIds = metaNodes
    .map((node) => Number(node?.instance_node_id))
    .filter(Number.isFinite);
  if (instanceNodeIds.length === 0) {
    return fallbackCoordinates;
  }
  const offset = Math.min(...instanceNodeIds) === 0 ? 0 : 1;

  const resolved = new Array(fallbackCoordinates.length);
  let hasGeographical = false;
  metaNodes.forEach((node) => {
    const instanceNodeId = Number(node?.instance_node_id);
    if (!Number.isFinite(instanceNodeId)) {
      return;
    }
    const lon = Number(node?.poi_lon);
    const lat = Number(node?.poi_lat);
    if (Number.isFinite(lon) && Number.isFinite(lat)) {
      const targetIndex = instanceNodeId - offset;
      if (targetIndex >= 0 && targetIndex < fallbackCoordinates.length) {
        resolved[targetIndex] = [lon, lat];
        hasGeographical = true;
      }
    }
  });

  if (!hasGeographical) {
    return fallbackCoordinates;
  }

  for (let index = 0; index < fallbackCoordinates.length; index += 1) {
    if (!resolved[index] && fallbackCoordinates[index]) {
      resolved[index] = fallbackCoordinates[index];
    }
  }
  return resolved;
}

function buildVisualGeometry() {
  const visual = currentVisualState();
  if (!visual.instanceData) {
    return null;
  }
  if (state.sourceKind === "benchmark" && visual.bksData) {
    const previewGeometry = resolvePreviewGeometry(
      visual.instanceData,
      visual.bksData,
      visual.objectiveEntry,
      {
        geometryMeta: visual.meta,
        metricVariant: visual.payload?.summary?.metric_variant,
        viewerRenderMode: visual.payload?.summary?.viewer_render_mode,
        roadCacheStatus: visual.payload?.summary?.road_cache_status,
      },
    );
    if (visual.roadGeojson && Array.isArray(visual.roadGeojson.features)) {
      const routeLines = visual.roadGeojson.features.map((feature, routeIndex) => ({
        routeIndex,
        coordinates: Array.isArray(feature?.geometry?.coordinates)
          ? feature.geometry.coordinates.filter((point) => Array.isArray(point) && point.length >= 2)
          : [],
        source: String(feature?.properties?.render_mode || visual.renderSummary?.render_mode || "road"),
      }));
      const usableRoadLines = routeLines.length === visual.routes.length && routeLines.every((routeLine) => routeLine.coordinates.length >= 2);
      if (usableRoadLines) {
        return {
          nodeCoordinates: previewGeometry.nodeCoordinates,
          routeLines,
          routeMode: visual.renderSummary?.render_mode || "road",
        };
      }
    }
    return {
      nodeCoordinates: previewGeometry.nodeCoordinates,
      routeLines: previewGeometry.routeLines,
      routeMode: previewGeometry.hasCachedRoadRoutes ? "cached_road" : "straight_line",
    };
  }

  const nodeCoordinates = uploadedNodeCoordinatesFromMeta(visual.instanceData, visual.meta);
  if (visual.roadGeojson && Array.isArray(visual.roadGeojson.features)) {
    const roadRouteLines = visual.roadGeojson.features.map((feature, routeIndex) => ({
      routeIndex,
      coordinates: Array.isArray(feature?.geometry?.coordinates)
        ? feature.geometry.coordinates.filter((point) => Array.isArray(point) && point.length >= 2)
        : [],
      source: String(feature?.properties?.render_mode || visual.renderSummary?.render_mode || "road"),
    }));
    if (roadRouteLines.length === visual.routes.length && roadRouteLines.every((routeLine) => routeLine.coordinates.length >= 2)) {
      return {
        nodeCoordinates,
        routeLines: roadRouteLines,
        routeMode: visual.renderSummary?.render_mode || "road",
      };
    }
  }
  return {
    nodeCoordinates,
    routeLines: visual.routes.map((route, routeIndex) => ({
      routeIndex,
      coordinates: [Number(visual.instanceData.depot || 0), ...route, Number(visual.instanceData.depot || 0)]
        .map((nodeIndex) => nodeCoordinates[nodeIndex])
        .filter((point) => Array.isArray(point) && point.length >= 2),
      source: "straight_line",
    })),
    routeMode: "straight_line",
  };
}

function drawCustomers(nodeCoordinates, routes, instanceData, options = {}) {
  const bounds = [];
  const customerToRoute = new Map();
  routes.forEach((route, routeIndex) => {
    const color = ROUTE_COLORS[routeIndex % ROUTE_COLORS.length];
    route.forEach((stopIndex) => {
      customerToRoute.set(Number(stopIndex), color);
    });
  });
  nodeCoordinates.forEach((coordinate, index) => {
    if (!Array.isArray(coordinate) || coordinate.length < 2) {
      return;
    }
    const lat = Number(coordinate[1]);
    const lon = Number(coordinate[0]);
    const isDepot = index === Number(instanceData.depot || 0);
    const color = isDepot ? "#111111" : customerToRoute.get(index) || "#0f766e";
    const marker = L.circleMarker([lat, lon], {
      radius: isDepot ? 7 : 5,
      color,
      fillColor: color,
      fillOpacity: 0.85,
      weight: isDepot ? 2 : 1,
    });
    const demand = Number(instanceData.demands?.[index]) || 0;
    marker.bindPopup(`<strong>${isDepot ? "Depot" : `Node ${index}`}</strong><br/>Demand: ${demand}<br/>Lat/Lon: ${lat.toFixed(6)}, ${lon.toFixed(6)}`);
    marker.addTo(state.layers.marker);
    bounds.push([lat, lon]);
  });
  if (options.fitBounds && bounds.length > 1) {
    map.fitBounds(bounds, { padding: [20, 20] });
  }
}

function drawRoutes(routeLines, routes, instanceData, routeMode) {
  routeLegendEl.innerHTML = "";
  routeLines.forEach((routeLine) => {
    const routeIndex = routeLine.routeIndex;
    if (state.selectedRoutes.size > 0 && !state.selectedRoutes.has(routeIndex)) {
      return;
    }
    const latlngs = routeLine.coordinates
      .filter((point) => Array.isArray(point) && point.length >= 2)
      .map((point) => [Number(point[1]), Number(point[0])]);
    if (latlngs.length < 2) {
      return;
    }
    const color = ROUTE_COLORS[routeIndex % ROUTE_COLORS.length];
    const polyline = L.polyline(latlngs, {
      color,
      weight: 4,
      opacity: routeMode === "straight_line" ? 0.78 : 0.88,
      lineCap: "round",
      lineJoin: "round",
    }).addTo(state.layers.route);
    polyline.bindPopup(`Route #${routeIndex + 1}<br/>Stops: ${routes[routeIndex]?.length ?? "?"}`);
    addArrowsToPolyline(polyline, color);

    const legendItem = document.createElement("li");
    legendItem.innerHTML = `<span class="swatch" style="background:${color}"></span><span>Route #${routeIndex + 1}: ${routes[routeIndex]?.length ?? 0} stops, load ${routeLoad(routes[routeIndex] || [], instanceData)} (${escapeHtml(routeMode)})</span>`;
    routeLegendEl.appendChild(legendItem);
  });
}

function updateStats(routeMode) {
  const visual = currentVisualState();
  if (!visual.instanceData) {
    statsEl.innerHTML = "";
    return;
  }
  const instanceData = visual.instanceData;
  const totalDemand = Array.isArray(instanceData.demands) ? instanceData.demands.slice(1).reduce((total, value) => total + (Number(value) || 0), 0) : 0;
  const rows = [
    ["Name", instanceData.name || visual.payload?.title || "n/a"],
    ["Nodes", String(instanceData.dimension || instanceData.coordinates?.length || 0)],
    ["Customers", String(Math.max(0, (instanceData.dimension || instanceData.coordinates?.length || 1) - 1))],
    ["Capacity", String(instanceData.capacity ?? visual.payload?.summary?.vehicle_capacity ?? "n/a")],
    ["Total Demand", String(totalDemand)],
    ["Routes", String(visual.routes.length)],
    ["Source", state.sourceKind],
    ["Render", routeMode],
  ];
  if (state.sourceKind === "benchmark") {
    rows.push(["Objective", visual.objectiveEntry?.objective_function || "n/a"]);
    rows.push(["Benchmark", visual.payload?.summary?.benchmark_name || "n/a"]);
  } else {
    rows.push(["Solution", visual.solutionInfo?.mode || "n/a"]);
    rows.push(["Coverage", visual.solutionInfo?.coverage || "n/a"]);
    rows.push(["Road API", state.lastApiError ? `error: ${state.lastApiError}` : "ok"]);
  }
  statsEl.innerHTML = rows.map(([label, value]) => `<dt>${escapeHtml(label)}</dt><dd>${escapeHtml(value)}</dd>`).join("");
}

function renderVisualState(options = {}) {
  clearMapLayers();
  const visual = currentVisualState();
  if (!visual.instanceData) {
    statsEl.innerHTML = "";
    routeLegendEl.innerHTML = "";
    routeSelectorCard.style.display = "none";
    return;
  }
  const geometry = buildVisualGeometry();
  if (!geometry) {
    return;
  }
  const fitBounds = consumeVisualFit(options.fitMap);
  drawCustomers(geometry.nodeCoordinates, visual.routes, visual.instanceData, { fitBounds });
  buildRouteSelector(visual.routes, visual.instanceData);
  drawRoutes(geometry.routeLines, visual.routes, visual.instanceData, geometry.routeMode);
  updateStats(geometry.routeMode);
}

function renderGenerationPreview(geojson, summary = {}, options = {}) {
  state.layers.preview.clearLayers();
  state.layers.marker.clearLayers();
  state.layers.route.clearLayers();
  state.layers.arrow.clearLayers();
  const features = Array.isArray(geojson?.features) ? geojson.features : [];
  const bounds = [];
  features.forEach((feature) => {
    const coordinates = feature?.geometry?.coordinates;
    if (!Array.isArray(coordinates) || coordinates.length < 2) {
      return;
    }
    const lng = Number(coordinates[0]);
    const lat = Number(coordinates[1]);
    const role = feature?.properties?.role || "customer";
    const sourceTag = String(feature?.properties?.source_tag || "unknown");
    const fill = role === "depot" ? "#111111" : sourceTag === "catalog_sample" ? "#16a34a" : sourceTag.startsWith("poi") ? "#b83a06" : "#0891b2";
    const marker = L.circleMarker([lat, lng], {
      radius: role === "depot" ? 8 : 5,
      color: fill,
      fillColor: fill,
      fillOpacity: 0.9,
      weight: 1,
    });
    marker.bindPopup(`<strong>${escapeHtml(role)}</strong><br/>${escapeHtml(sourceTag)}`);
    marker.addTo(state.layers.preview);
    bounds.push([lat, lng]);
  });
  if (consumePreviewFit(options.fitMap) && bounds.length > 1) {
    map.fitBounds(bounds, { padding: [20, 20] });
  }
  state.generation.previewSummary = summary;
  const customerParts = [];
  if (summary.customers !== undefined) {
    customerParts.push(`${summary.customers} customers`);
  }
  if (summary.requested_customers !== undefined && summary.requested_customers !== summary.customers) {
    customerParts.push(`requested ${summary.requested_customers}`);
  }
  genResult.textContent = [
    `City: ${summary.city || "n/a"}`,
    `Method: ${summary.method || "n/a"}`,
    `Preview mode: ${summary.preview_mode || "n/a"}`,
    `Customers: ${customerParts.join(" · ") || "n/a"}`,
    `Sample: ${summary.sample_instance_name || "n/a"}`,
    summary.note || "Preview rendered on the map.",
  ].join("\n");
}

function syncWorkbenchUrl() {
  const nextParams = new URLSearchParams(window.location.search);
  const mode = state.activeTab === "generate" ? "generate" : state.sourceKind === "upload" ? "upload" : null;
  if (mode) {
    nextParams.set("mode", mode);
  } else {
    nextParams.delete("mode");
  }
  if (state.instanceRoute) {
    nextParams.set("instance", state.instanceRoute);
  } else {
    nextParams.delete("instance");
  }
  if (state.objectiveFunction) {
    nextParams.set("objective", state.objectiveFunction);
  } else {
    nextParams.delete("objective");
  }
  nextParams.delete("deriveTarget");
  const nextQuery = nextParams.toString();
  const nextUrl = `${CANONICAL_WORKBENCH_ROUTE}${nextQuery ? `?${nextQuery}` : ""}`;
  window.history.replaceState({}, "", nextUrl);
}

function setActiveTab(tab, options = {}) {
  state.activeTab = tab;
  const visualize = tab === "visualize";
  tabVisualize.classList.toggle("tab-active", visualize);
  tabGenerate.classList.toggle("tab-active", !visualize);
  visualPanel.classList.toggle("tab-panel-active", visualize);
  generationPanel.classList.toggle("tab-panel-active", !visualize);
  if (options.sync !== false) {
    syncWorkbenchUrl();
  }
  if (visualize) {
    renderVisualState();
  }
  refreshMapSize();
}

async function setSourceKind(sourceKind, options = {}) {
  state.sourceKind = sourceKind;
  sourceBenchmarkBtn.classList.toggle("active", sourceKind === "benchmark");
  sourceUploadBtn.classList.toggle("active", sourceKind === "upload");
  updateVisualModePanels();
  if (options.sync !== false) {
    syncWorkbenchUrl();
  }
  if (sourceKind === "benchmark" && state.instanceRoute) {
    await loadBenchmarkInstance(state.instanceRoute, state.objectiveFunction, {
      quiet: true,
      fitMap: options.fitMap,
    });
    return;
  }
  renderVisualState({ fitMap: options.fitMap });
}

function updateBenchmarkContextUi() {
  renderBenchmarkCatalogOptions();
  if (!state.benchmark.payload) {
    objectiveField.hidden = true;
    benchmarkStatus.textContent = state.instanceRoute
      ? "Benchmark preload is unavailable for the requested route. Browse the catalog and open another instance."
      : "Select a published family, then choose an instance here or open one from the public catalog.";
    benchmarkRenderStatus.textContent = "Road geometry will be rendered automatically when a benchmark sidecar is available.";
    openBenchmarkBtn.href = browseBenchmarksBtn.href;
    return;
  }

  const payload = state.benchmark.payload;
  const objectiveEntries = Array.isArray(payload.bks_entries) ? payload.bks_entries : [];
  const renderSummary = state.benchmark.renderSummary;
  const renderFragments = [];
  if (renderSummary) {
    renderFragments.push(`Automatic road render: ${renderSummary.render_mode} · ${renderSummary.metric}`);
    if (renderSummary.straight_fallback_count > 0) {
      const suffix = renderSummary.straight_fallback_count === 1 ? "segment" : "segments";
      renderFragments.push(`${renderSummary.straight_fallback_count} straight-line fallback ${suffix}`);
    }
    if (renderSummary.cache_persisted) {
      renderFragments.push("sidecar cache updated");
    }
  }
  objectiveField.hidden = objectiveEntries.length === 0;
  benchmarkObjectiveSelect.innerHTML = objectiveEntries
    .map((entry) => `<option value="${escapeHtml(entry.objective_function)}"${entry.objective_function === state.objectiveFunction ? " selected" : ""}>${escapeHtml(entry.objective_function)}</option>`)
    .join("");
  benchmarkStatus.textContent = `${payload.title} · ${payload.summary.problem_type} · ${payload.summary.benchmark_name} · ${payload.summary.num_customers} customers`;
  benchmarkRenderStatus.textContent = renderFragments.length > 0
    ? renderFragments.join(" · ")
    : payload.summary?.road_cache_status === "partial"
      ? "Road geometry is only partially cached for this benchmark in the published snapshot. Missing segments currently fall back to straight lines."
      : "Road geometry will be rendered automatically when a benchmark sidecar is available.";
  openBenchmarkBtn.href = routeHref(payload.route_path);
}

async function autoRenderBenchmarkRoadGeometry(options = {}) {
  const benchmark = state.benchmark;
  benchmark.roadGeojson = null;
  benchmark.renderSummary = null;

  if (window.location.protocol === "file:") {
    return;
  }
  if (!benchmark.meta || !Array.isArray(benchmark.routes) || benchmark.routes.length === 0) {
    return;
  }

  const metric = ["shortest", "fastest", "euclidean"].includes(String(benchmark.payload?.summary?.metric_variant || "").toLowerCase())
    ? String(benchmark.payload.summary.metric_variant).toLowerCase()
    : "shortest";
  const routes = uploadedPreviewRoutesToMetaRoutes(benchmark.routes, benchmark.meta);
  const requestPayload = {
    routes,
    metric,
    meta: benchmark.meta,
  };
  if (metric !== "euclidean" && benchmark.payload?.artifact_links?.meta_path) {
    requestPayload.meta_path = benchmark.payload.artifact_links.meta_path;
  }

  const operationId = `benchmark-render-${Date.now()}`;
  const totalStops = benchmark.routes.reduce((sum, route) => sum + route.length, 0);
  startProgressBar(
    "Rendering Road Geometry",
    operationId,
    sourceBenchmarkBtn,
    predictDuration("Rendering Road Geometry", { routes: benchmark.routes.length, stops: totalStops }),
  );

  try {
    let response;
    try {
      response = await postWorkbenchJson(currentRenderEndpoint(), requestPayload);
    } catch (error) {
      if (!requestPayload.meta_path) {
        throw error;
      }
      response = await postWorkbenchJson(currentRenderEndpoint(), {
        meta: benchmark.meta,
        routes,
        metric,
      });
    }
    benchmark.roadGeojson = response.geojson || null;
    benchmark.renderSummary = response.summary || null;
    state.lastApiError = null;
    completeProgressBar(operationId);
  } catch (error) {
    console.warn("Unable to auto-render benchmark road geometry", error);
    benchmark.roadGeojson = null;
    benchmark.renderSummary = null;
    hideAllProgressBars();
  }
  updateBenchmarkContextUi();
  if (options.render !== false && state.sourceKind === "benchmark") {
    renderVisualState({ fitMap: options.fitMap });
  }
}

async function loadBenchmarkInstance(instanceRoute, preferredObjective = null, options = {}) {
  if (!instanceRoute) {
    state.instanceRoute = null;
    state.objectiveFunction = null;
    state.benchmark = {
      payload: null,
      instanceData: null,
      meta: null,
      bksData: null,
      objectiveEntry: null,
      routes: [],
      roadGeojson: null,
      renderSummary: null,
    };
    updateBenchmarkContextUi();
    if (state.sourceKind === "benchmark") {
      renderVisualState({ fitMap: options.fitMap });
    }
    return;
  }

  try {
    benchmarkStatus.textContent = "Loading benchmark instance…";
    const previousRoute = state.benchmark.payload?.route_path || null;
    const payload = await fetchWorkbenchPayloadForRoute(instanceRoute);
    if (payload?.payload_kind !== "instance_page") {
      throw new Error(`Route '${instanceRoute}' is not a benchmark instance page.`);
    }
    const instanceData = await fetchJson(artifactHref(payload.artifact_links.vrp_json_path));
    const objectiveEntries = Array.isArray(payload.bks_entries) ? payload.bks_entries : [];
    const objectiveEntry = objectiveEntries.find((entry) => entry.objective_function === preferredObjective)
      || objectiveEntries[0]
      || null;
    const bksData = objectiveEntry ? await fetchJson(artifactHref(objectiveEntry.artifact_path)) : { routes: [] };
    let meta = null;
    if (payload.artifact_links.meta_path) {
      try {
        meta = await fetchJson(artifactHref(payload.artifact_links.meta_path));
      } catch (error) {
        console.warn("Unable to load benchmark sidecar", error);
      }
    }
    state.instanceRoute = payload.route_path;
    state.objectiveFunction = objectiveEntry?.objective_function || null;
    state.benchmarkCatalog.selectedGroupKey = benchmarkCatalogGroupKey(payload);
    state.benchmark = {
      payload,
      instanceData,
      meta,
      bksData,
      objectiveEntry,
      routes: Array.isArray(bksData?.routes) ? bksData.routes.map((route) => route.map((nodeIndex) => Number(nodeIndex))) : [],
      roadGeojson: null,
      renderSummary: null,
    };
    const fitMap = options.fitMap !== undefined
      ? options.fitMap
      : !previousRoute || normalizeRoute(previousRoute) !== normalizeRoute(payload.route_path);
    if (fitMap) {
      requestVisualFit();
    }
    state.selectedRoutes.clear();
    updateBenchmarkContextUi();
    syncGenerationControlsFromBenchmark();
    syncWorkbenchUrl();
    await autoRenderBenchmarkRoadGeometry({ render: false });
    if (state.sourceKind === "benchmark") {
      renderVisualState({ fitMap });
    }
    if (!options.quiet) {
      showToast(`Loaded benchmark ${payload.title}`);
    }
  } catch (error) {
    console.error(error);
    benchmarkStatus.textContent = error.message || String(error);
    showToast(`Benchmark load error: ${error.message || error}`);
  }
}

function syncGenerationControlsFromBenchmark() {
  const summary = state.benchmark.payload?.summary;
  if (!summary) {
    updateGenerationFieldVisibility();
    return;
  }

  const benchmarkProblemType = String(summary.problem_type || "").trim().toUpperCase();
  if (genProblemTypeSelect && PROBLEM_TYPES.includes(benchmarkProblemType)) {
    genProblemTypeSelect.value = benchmarkProblemType;
  }

  const benchmarkCity = String(summary.place_slug || "").trim().toLowerCase();
  if (genCitySelect && !genCitySelect.disabled && benchmarkCity) {
    const match = state.generation.cities.find((city) => city.slug === benchmarkCity);
    if (match) {
      genCitySelect.value = match.slug;
    }
  }

  const benchmarkCustomers = Number(summary.num_customers);
  if (Number.isFinite(benchmarkCustomers) && benchmarkCustomers > 0 && genCustomersInput) {
    genCustomersInput.value = String(benchmarkCustomers);
  }

  updateGenerationFieldVisibility();
}

async function loadGenerationCities() {
  if (window.location.protocol === "file:") {
    generationNote.textContent = "Generation preview requires the Paper7 site API server. Open the workbench over HTTP instead of file://.";
    return;
  }
  try {
    const response = await fetchWorkbenchJson(WORKBENCH_GENERATION_CITIES_PATH);
    state.generation.cities = Array.isArray(response.cities) ? response.cities : [];
    state.generation.localOsmdataDir = response.local_osmdata_dir || "osmdata";

    if (state.generation.cities.length === 0) {
      genCitySelect.innerHTML = '<option value="">No OSM data — fetch a city above</option>';
      genCitySelect.disabled = true;
    } else {
      genCitySelect.disabled = false;
      genCitySelect.innerHTML = state.generation.cities
        .map((city) => `<option value="${escapeHtml(city.slug)}">${escapeHtml(city.label || city.slug)}</option>`)
        .join("");
    }

    if (genBulkCitiesSelect) {
      const previousChecks = new Set(
        Array.from(genBulkCitiesSelect.querySelectorAll("input[type='checkbox']:checked")).map((cb) => cb.value),
      );
      genBulkCitiesSelect.innerHTML = "";
      if (state.generation.cities.length === 0) {
        const empty = document.createElement("p");
        empty.className = "workbench-card-intro";
        empty.style.margin = "0";
        empty.textContent = `No OSM data in '${state.generation.localOsmdataDir}'. Fetch a city to populate this list.`;
        genBulkCitiesSelect.appendChild(empty);
      } else {
        for (const city of state.generation.cities) {
          const label = document.createElement("label");
          if (city.osm_path || city.osm_filename) {
            label.title = city.osm_path || city.osm_filename;
          }
          const checkbox = document.createElement("input");
          checkbox.type = "checkbox";
          checkbox.value = city.slug;
          checkbox.checked = previousChecks.has(city.slug);
          checkbox.addEventListener("change", updateBulkCityCount);
          label.appendChild(checkbox);
          label.appendChild(document.createTextNode(" " + (city.label || city.slug)));
          genBulkCitiesSelect.appendChild(label);
        }
      }
      updateBulkCityCount();
    }

    syncGenerationControlsFromBenchmark();
    const fetchedDir = state.generation.localOsmdataDir || "osmdata";
    if (state.generation.cities.length > 0) {
      generationNote.textContent = `Generation reads OSM extracts from '${fetchedDir}' (${state.generation.cities.length} available). Use 'Fetch OSM Data' to add another city by name.`;
    } else {
      generationNote.textContent = `'${fetchedDir}' is empty. Use 'Fetch OSM Data' above to download a city's OSM extract before generating.`;
    }
    renderBulkTable();
  } catch (error) {
    console.error(error);
    generationNote.textContent = error.message || String(error);
  }
}

function getSelectedPoiCategories() {
  if (!genPoiList) {
    return [];
  }
  return Array.from(genPoiList.querySelectorAll("input[type='checkbox']:checked")).map((el) => el.value);
}

function updatePoiCount() {
  if (!genPoiList || !genPoiCount) {
    return;
  }
  const checked = genPoiList.querySelectorAll("input[type='checkbox']:checked").length;
  genPoiCount.textContent = `${checked} selected`;
}

function renderPoiCategoryMenu() {
  if (!genPoiList) {
    return;
  }
  genPoiList.innerHTML = "";
  for (const category of POI_CATEGORIES) {
    const label = document.createElement("label");
    label.className = "poi-item";
    const checkbox = document.createElement("input");
    checkbox.type = "checkbox";
    checkbox.value = category;
    checkbox.checked = DEFAULT_POI_CATEGORIES.has(category);
    checkbox.addEventListener("change", updatePoiCount);
    const text = document.createElement("span");
    text.textContent = category;
    label.appendChild(checkbox);
    label.appendChild(text);
    genPoiList.appendChild(label);
  }
  updatePoiCount();
}

function updateGenerationFieldVisibility() {
  if (!genMethodSelect) {
    return;
  }
  const method = genMethodSelect.value;
  const customerMode = genCustomerModeSelect ? genCustomerModeSelect.value : "random_clustered";
  const problemType = genProblemTypeSelect ? genProblemTypeSelect.value.toUpperCase() : "CVRP";
  const groups = {
    poi: document.querySelectorAll(".gen-field-poi"),
    parametric: document.querySelectorAll(".gen-field-parametric"),
    hybrid: document.querySelectorAll(".gen-field-hybrid"),
    cluster: document.querySelectorAll(".gen-field-cluster"),
    vrptw: document.querySelectorAll(".gen-field-vrptw"),
  };
  Object.values(groups).forEach((nodes) => nodes.forEach((node) => { node.style.display = "none"; }));
  if (method === "poi_categories") {
    groups.poi.forEach((node) => { node.style.display = ""; });
  } else if (method === "parametric_attach") {
    groups.parametric.forEach((node) => { node.style.display = ""; });
  } else if (method === "hybrid") {
    groups.poi.forEach((node) => { node.style.display = ""; });
    groups.parametric.forEach((node) => { node.style.display = ""; });
    groups.hybrid.forEach((node) => { node.style.display = ""; });
  }
  if (customerMode !== "random") {
    groups.cluster.forEach((node) => { node.style.display = ""; });
  }
  if (problemType === "VRPTW") {
    groups.vrptw.forEach((node) => { node.style.display = ""; });
  }
}

function updateBulkCityCount() {
  if (!genBulkCitiesSelect || !bulkCityCount) {
    return;
  }
  const selected = genBulkCitiesSelect.querySelectorAll("input[type='checkbox']:checked").length;
  bulkCityCount.textContent = `${selected} selected`;
}

function getCheckedIntValues(container) {
  if (!container) {
    return [];
  }
  return Array.from(container.querySelectorAll("input[type='checkbox']:checked"))
    .map((cb) => Number.parseInt(cb.value, 10))
    .filter(Number.isFinite);
}

function resetUploadState() {
  state.upload = {
    instanceData: null,
    meta: null,
    routes: [],
    solutionInfo: null,
    roadGeojson: null,
    renderSummary: null,
    vrpText: null,
    vrpJsonPayload: null,
    vrpFileName: null,
  };
}

function currentProblemType() {
  if (!genProblemTypeSelect) {
    return "CVRP";
  }
  const value = String(genProblemTypeSelect.value || "CVRP").toUpperCase();
  return PROBLEM_TYPES.includes(value) ? value : "CVRP";
}

function currentTwMethod() {
  if (!genTwMethodSelect) {
    return "route_centered";
  }
  const value = String(genTwMethodSelect.value || "route_centered").toLowerCase();
  return VRPTW_TW_METHODS.includes(value) ? value : "route_centered";
}

function currentTwHorizonStart() {
  const raw = Number.parseInt(genTwHorizonStartInput?.value ?? "", 10);
  return Number.isFinite(raw) && raw >= 0 ? raw : VRPTW_DEFAULT_HORIZON_START;
}

function currentTwHorizonEnd() {
  const raw = Number.parseInt(genTwHorizonEndInput?.value ?? "", 10);
  return Number.isFinite(raw) && raw > 0 ? raw : VRPTW_DEFAULT_HORIZON_END;
}

function currentGenerationPreviewPayload() {
  const payload = {
    city: genCitySelect.value || "",
    method: genMethodSelect.value || "poi_categories",
    nCustomers: Number.parseInt(genCustomersInput.value, 10) || 50,
    demandType: genDemandTypeSelect ? Number.parseInt(genDemandTypeSelect.value, 10) || 7 : 7,
    avgRouteSize: genAvgRouteSizeSelect ? Number.parseInt(genAvgRouteSizeSelect.value, 10) || 4 : 4,
    seed: Number.parseInt(genSeedInput.value, 10) || 0,
    onlyIntersections: genOnlyIntersectionsInput.checked,
    depotMode: genDepotModeSelect.value || "center",
    customerMode: genCustomerModeSelect.value || "random_clustered",
    clusterSeeds: Number.parseInt(genClusterSeedsInput.value, 10) || 4,
    clusterDecayMeters: Number.parseFloat(genClusterDecayInput.value) || 800,
    hybridPoiShare: Number.parseFloat(genHybridShareInput.value) || 0.5,
    categories: getSelectedPoiCategories(),
    problemType: currentProblemType(),
  };
  if (payload.problemType === "VRPTW") {
    payload.twMethod = currentTwMethod();
    payload.twHorizonStart = currentTwHorizonStart();
    payload.twHorizonEnd = currentTwHorizonEnd();
  }
  return payload;
}

function splitCommaList(text) {
  return String(text || "")
    .split(",")
    .map((value) => value.trim())
    .filter(Boolean);
}

function boolFromValue(value, fallback = false) {
  if (typeof value === "boolean") {
    return value;
  }
  if (value === null || value === undefined || value === "") {
    return fallback;
  }
  const normalized = String(value).trim().toLowerCase();
  if (["1", "true", "yes", "y", "on"].includes(normalized)) {
    return true;
  }
  if (["0", "false", "no", "n", "off"].includes(normalized)) {
    return false;
  }
  return fallback;
}

function categoryTextFromValue(value, fallback = "") {
  if (Array.isArray(value)) {
    return value.map((entry) => String(entry).trim()).filter(Boolean).join(",");
  }
  const text = String(value ?? "").trim();
  return text || fallback;
}

function bulkCategoryTextFromBase(base = currentGenerationPreviewPayload()) {
  return categoryTextFromValue(base.categories, Array.from(DEFAULT_POI_CATEGORIES).join(","));
}

function bulkPanelProblemType() {
  if (!bulkProblemTypeSelect) {
    return "CVRP";
  }
  const value = String(bulkProblemTypeSelect.value || "CVRP").toUpperCase();
  return PROBLEM_TYPES.includes(value) ? value : "CVRP";
}

function bulkPanelTwMethod() {
  if (!bulkTwMethodSelect) {
    return "route_centered";
  }
  const value = String(bulkTwMethodSelect.value || "route_centered").toLowerCase();
  return VRPTW_TW_METHODS.includes(value) ? value : "route_centered";
}

function applyBulkRowDefaults(row, base = currentGenerationPreviewPayload()) {
  row.city = row.city || genCitySelect.value || "";
  const nCustomers = Number.parseInt(row.nCustomers, 10);
  const demandType = Number.parseInt(row.demandType, 10);
  const avgRouteSize = Number.parseInt(row.avgRouteSize, 10);
  const seed = Number.parseInt(row.seed, 10);
  const clusterSeeds = Number.parseInt(row.clusterSeeds, 10);
  const clusterDecayMeters = Number.parseFloat(row.clusterDecayMeters);
  row.nCustomers = Number.isFinite(nCustomers) ? nCustomers : base.nCustomers || 50;
  row.demandType = Number.isFinite(demandType) ? demandType : base.demandType || 7;
  row.avgRouteSize = Number.isFinite(avgRouteSize) ? avgRouteSize : base.avgRouteSize || 4;
  row.method = row.method || base.method || "poi_categories";
  row.seed = Number.isFinite(seed) ? seed : base.seed || 0;
  row.depotMode = row.depotMode || base.depotMode || "center";
  row.customerMode = row.customerMode || base.customerMode || "random_clustered";
  row.onlyIntersections = boolFromValue(row.onlyIntersections, base.onlyIntersections !== false);
  row.clusterSeeds = Number.isFinite(clusterSeeds) ? clusterSeeds : base.clusterSeeds || 4;
  row.clusterDecayMeters = Number.isFinite(clusterDecayMeters) ? clusterDecayMeters : base.clusterDecayMeters || 800;
  row.hybridPoiShare = Number.parseFloat(row.hybridPoiShare);
  if (!Number.isFinite(row.hybridPoiShare)) {
    row.hybridPoiShare = Number.isFinite(Number(base.hybridPoiShare)) ? Number(base.hybridPoiShare) : 0.5;
  }
  row.categories = categoryTextFromValue(row.categories, bulkCategoryTextFromBase(base));
  const problemType = String(row.problemType || "").toUpperCase();
  row.problemType = PROBLEM_TYPES.includes(problemType) ? problemType : bulkPanelProblemType();
  const twMethod = String(row.twMethod || "").toLowerCase();
  row.twMethod = VRPTW_TW_METHODS.includes(twMethod) ? twMethod : bulkPanelTwMethod();
  return row;
}

function bulkRowKey(row) {
  return [
    row.city,
    row.nCustomers,
    row.demandType,
    row.avgRouteSize,
    row.method,
    row.seed,
    row.depotMode,
    row.customerMode,
    row.onlyIntersections,
    row.clusterSeeds,
    row.clusterDecayMeters,
    row.hybridPoiShare,
    row.categories,
  ].join("|");
}

function refreshBulkBadges() {
  const count = state.generation.bulkInstances.length;
  const label = `${count} instance${count === 1 ? "" : "s"}`;
  if (bulkCountBadge) bulkCountBadge.textContent = label;
  if (bulkModalCount) bulkModalCount.textContent = label;
}

function makeBulkSelectCell(row, field, options, labels = null) {
  const td = document.createElement("td");
  td.dataset.field = field;
  const select = document.createElement("select");
  for (let index = 0; index < options.length; index += 1) {
    const value = options[index];
    const opt = document.createElement("option");
    opt.value = value;
    opt.textContent = labels && labels[index] ? labels[index] : value;
    if (String(row[field]) === value) {
      opt.selected = true;
    }
    select.appendChild(opt);
  }
  select.addEventListener("change", () => {
    const value = select.value;
    row[field] = BULK_INT_FIELDS.has(field)
      ? Number.parseInt(value, 10)
      : BULK_FLOAT_FIELDS.has(field)
        ? Number.parseFloat(value)
        : value;
  });
  td.appendChild(select);
  return td;
}

function makeBulkNumberCell(row, field, { min = null, max = null, step = "1", fallback = 0 } = {}) {
  const td = document.createElement("td");
  td.dataset.field = field;
  const input = document.createElement("input");
  input.type = "number";
  if (min !== null) input.min = String(min);
  if (max !== null) input.max = String(max);
  input.step = String(step);
  input.value = String(row[field]);
  input.addEventListener("change", () => {
    const parsed = BULK_FLOAT_FIELDS.has(field) ? Number.parseFloat(input.value) : Number.parseInt(input.value, 10);
    row[field] = Number.isFinite(parsed) ? parsed : fallback;
    input.value = String(row[field]);
  });
  td.appendChild(input);
  return td;
}

function makeBulkCheckboxCell(row, field) {
  const td = document.createElement("td");
  td.dataset.field = field;
  const input = document.createElement("input");
  input.type = "checkbox";
  input.checked = boolFromValue(row[field], true);
  row[field] = input.checked;
  input.addEventListener("change", () => {
    row[field] = input.checked;
  });
  td.appendChild(input);
  return td;
}

function makeBulkTextCell(row, field, placeholder = "") {
  const td = document.createElement("td");
  td.dataset.field = field;
  const input = document.createElement("input");
  input.type = "text";
  input.value = String(row[field] ?? "");
  input.placeholder = placeholder;
  input.addEventListener("change", () => {
    row[field] = input.value.trim();
  });
  td.appendChild(input);
  return td;
}

function bulkCityOptionsForRow(row) {
  const labelBySlug = new Map(state.generation.cities.map((city) => [city.slug, city.label || city.slug]));
  const slugs = state.generation.cities.map((city) => city.slug);
  const rowCity = String(row?.city || "").trim();
  if (rowCity && !labelBySlug.has(rowCity)) {
    slugs.push(rowCity);
    labelBySlug.set(rowCity, `${rowCity} (not fetched)`);
  }
  const labels = slugs.map((slug) => labelBySlug.get(slug) || slug);
  return { values: slugs, labels };
}

function renderBulkTable() {
  if (!bulkTableBody) {
    return;
  }
  bulkTableBody.innerHTML = "";
  for (const row of state.generation.bulkInstances) {
    applyBulkRowDefaults(row);
    const tr = document.createElement("tr");
    tr.dataset.id = String(row.id);

    const tdCheck = document.createElement("td");
    const checkbox = document.createElement("input");
    checkbox.type = "checkbox";
    checkbox.className = "bulk-row-check";
    tdCheck.appendChild(checkbox);
    tr.appendChild(tdCheck);

    const problemTypeCell = makeBulkSelectCell(row, "problemType", PROBLEM_TYPES, PROBLEM_TYPES);
    problemTypeCell.querySelector("select").addEventListener("change", () => renderBulkTable());
    tr.appendChild(problemTypeCell);

    const cityOpts = bulkCityOptionsForRow(row);
    tr.appendChild(makeBulkSelectCell(row, "city", cityOpts.values, cityOpts.labels));

    tr.appendChild(makeBulkNumberCell(row, "nCustomers", { min: 2, fallback: 2 }));
    tr.appendChild(makeBulkSelectCell(row, "demandType", ["1", "2", "3", "4", "5", "6", "7"]));
    tr.appendChild(makeBulkSelectCell(row, "avgRouteSize", ["1", "2", "3", "4", "5", "6", "7"]));
    tr.appendChild(makeBulkSelectCell(row, "method", ["poi_categories", "parametric_attach", "hybrid"]));
    tr.appendChild(makeBulkNumberCell(row, "seed", { min: 0, fallback: 0 }));
    tr.appendChild(makeBulkSelectCell(row, "depotMode", ["center", "random", "corner"]));
    tr.appendChild(makeBulkSelectCell(row, "customerMode", ["random_clustered", "clustered", "random"]));
    const twMethodLabels = VRPTW_TW_METHODS.map((value) => VRPTW_TW_METHOD_LABELS[value] || value);
    const twCell = makeBulkSelectCell(row, "twMethod", VRPTW_TW_METHODS, twMethodLabels);
    if (String(row.problemType || "CVRP").toUpperCase() !== "VRPTW") {
      twCell.querySelector("select").disabled = true;
    }
    tr.appendChild(twCell);
    tr.appendChild(makeBulkCheckboxCell(row, "onlyIntersections"));
    tr.appendChild(makeBulkNumberCell(row, "clusterSeeds", { min: 1, fallback: 4 }));
    tr.appendChild(makeBulkNumberCell(row, "clusterDecayMeters", { min: 50, step: 50, fallback: 800 }));
    tr.appendChild(makeBulkNumberCell(row, "hybridPoiShare", { min: 0, max: 1, step: 0.05, fallback: 0.5 }));
    tr.appendChild(makeBulkTextCell(row, "categories", "restaurant,cafe"));

    const tdDel = document.createElement("td");
    const delBtn = document.createElement("button");
    delBtn.textContent = "✕";
    delBtn.className = "bulk-delete-btn";
    delBtn.addEventListener("click", () => {
      state.generation.bulkInstances = state.generation.bulkInstances.filter((r) => r.id !== row.id);
      renderBulkTable();
    });
    tdDel.appendChild(delBtn);
    tr.appendChild(tdDel);

    bulkTableBody.appendChild(tr);
  }
  refreshBulkBadges();
  if (bulkSelectAll) {
    bulkSelectAll.checked = false;
  }
}

function expandBulkCombinations() {
  const cities = Array.from(genBulkCitiesSelect?.querySelectorAll("input[type='checkbox']:checked") || [])
    .map((cb) => cb.value);
  const customers = splitCommaList(genBulkCustomersInput?.value)
    .map((value) => Number.parseInt(value, 10))
    .filter((value) => Number.isFinite(value) && value >= 2);
  const demands = getCheckedIntValues(bulkDemandChecks);
  const routes = getCheckedIntValues(bulkRouteSizeChecks);
  if (cities.length === 0 || customers.length === 0 || demands.length === 0 || routes.length === 0) {
    showToast("Select at least one value for each parameter");
    return;
  }
  const base = currentGenerationPreviewPayload();
  let duplicates = 0;
  const existing = new Set(state.generation.bulkInstances.map(bulkRowKey));
  for (const city of cities) {
    for (const nCustomers of customers) {
      for (const demandType of demands) {
        for (const avgRouteSize of routes) {
          const candidate = {
            id: state.generation.bulkNextId,
            city,
            nCustomers,
            demandType,
            avgRouteSize,
            method: base.method,
            seed: base.seed,
            depotMode: base.depotMode,
            customerMode: base.customerMode,
            onlyIntersections: base.onlyIntersections,
            clusterSeeds: base.clusterSeeds,
            clusterDecayMeters: base.clusterDecayMeters,
            hybridPoiShare: base.hybridPoiShare,
            categories: bulkCategoryTextFromBase(base),
          };
          applyBulkRowDefaults(candidate, base);
          const key = bulkRowKey(candidate);
          if (existing.has(key)) {
            duplicates += 1;
            continue;
          }
          existing.add(key);
          state.generation.bulkInstances.push(candidate);
          state.generation.bulkNextId += 1;
        }
      }
    }
  }
  renderBulkTable();
  if (duplicates > 0) {
    showToast(`Skipped ${duplicates} duplicate combination(s)`);
  }
}

function addBulkRow() {
  const base = currentGenerationPreviewPayload();
  state.generation.bulkInstances.push(applyBulkRowDefaults({
    id: state.generation.bulkNextId,
    city: genCitySelect.value || "",
    nCustomers: base.nCustomers,
    demandType: base.demandType,
    avgRouteSize: base.avgRouteSize,
    method: base.method,
    seed: base.seed,
    depotMode: base.depotMode,
    customerMode: base.customerMode,
    onlyIntersections: base.onlyIntersections,
    clusterSeeds: base.clusterSeeds,
    clusterDecayMeters: base.clusterDecayMeters,
    hybridPoiShare: base.hybridPoiShare,
    categories: bulkCategoryTextFromBase(base),
  }, base));
  state.generation.bulkNextId += 1;
  renderBulkTable();
}

function deleteSelectedBulkRows() {
  const selected = new Set();
  bulkTableBody?.querySelectorAll(".bulk-row-check:checked").forEach((cb) => {
    const id = Number.parseInt(cb.closest("tr")?.dataset.id || "", 10);
    if (Number.isFinite(id)) {
      selected.add(id);
    }
  });
  if (selected.size === 0) {
    showToast("No rows selected");
    return;
  }
  state.generation.bulkInstances = state.generation.bulkInstances.filter((row) => !selected.has(row.id));
  renderBulkTable();
}

function csvEscape(value) {
  const text = String(value ?? "");
  return /[",\n\r]/.test(text) ? `"${text.replaceAll('"', '""')}"` : text;
}

function parseCsvLine(line) {
  const values = [];
  let current = "";
  let quoted = false;
  for (let index = 0; index < line.length; index += 1) {
    const char = line[index];
    if (quoted) {
      if (char === '"' && line[index + 1] === '"') {
        current += '"';
        index += 1;
      } else if (char === '"') {
        quoted = false;
      } else {
        current += char;
      }
    } else if (char === '"') {
      quoted = true;
    } else if (char === ",") {
      values.push(current.trim());
      current = "";
    } else {
      current += char;
    }
  }
  values.push(current.trim());
  return values;
}

function bulkRowToCsvValues(row) {
  applyBulkRowDefaults(row);
  return [
    row.problemType,
    row.city,
    row.nCustomers,
    row.demandType,
    row.avgRouteSize,
    row.method,
    row.seed,
    row.depotMode,
    row.customerMode,
    row.twMethod,
    row.onlyIntersections ? "true" : "false",
    row.clusterSeeds,
    row.clusterDecayMeters,
    row.hybridPoiShare,
    row.categories,
  ];
}

function exportBulkCsv() {
  if (state.generation.bulkInstances.length === 0) {
    showToast("No instances to export");
    return;
  }
  const header = BULK_CSV_COLUMNS.join(",");
  const rows = state.generation.bulkInstances.map((row) =>
    bulkRowToCsvValues(row).map(csvEscape).join(","),
  );
  const blob = new Blob([header + "\n" + rows.join("\n") + "\n"], { type: "text/csv" });
  const anchor = document.createElement("a");
  anchor.href = URL.createObjectURL(blob);
  anchor.download = "bulk_instances.csv";
  anchor.click();
  URL.revokeObjectURL(anchor.href);
}

function importBulkCsv(file) {
  const reader = new FileReader();
  reader.onload = () => {
    const lines = String(reader.result || "")
      .split("\n")
      .map((line) => line.trim())
      .filter(Boolean);
    if (lines.length < 2) {
      showToast("CSV must have a header row and at least one data row");
      return;
    }
    const header = parseCsvLine(lines[0]).map((value) => value.toLowerCase().trim());
    const required = ["city", "ncustomers", "demandtype", "avgroutesize"];
    for (const column of required) {
      if (!header.includes(column)) {
        showToast(`Missing required CSV column: ${column}`);
        return;
      }
    }
    const indexOf = Object.fromEntries(header.map((column, index) => [column, index]));
    let added = 0;
    const base = currentGenerationPreviewPayload();
    for (let i = 1; i < lines.length; i += 1) {
      const cols = parseCsvLine(lines[i]);
      if (cols.length < header.length) {
        continue;
      }
      state.generation.bulkInstances.push(applyBulkRowDefaults({
        id: state.generation.bulkNextId,
        problemType: indexOf.problemtype === undefined ? bulkPanelProblemType() : String(cols[indexOf.problemtype] || "").toUpperCase(),
        city: cols[indexOf.city] || "",
        nCustomers: Number.parseInt(cols[indexOf.ncustomers], 10) || 50,
        demandType: Number.parseInt(cols[indexOf.demandtype], 10) || 7,
        avgRouteSize: Number.parseInt(cols[indexOf.avgroutesize], 10) || 4,
        method: cols[indexOf.method] || "poi_categories",
        seed: Number.parseInt(cols[indexOf.seed], 10) || 0,
        depotMode: cols[indexOf.depotmode] || "center",
        customerMode: cols[indexOf.customermode] || "random_clustered",
        twMethod: indexOf.twmethod === undefined ? bulkPanelTwMethod() : String(cols[indexOf.twmethod] || "").toLowerCase(),
        onlyIntersections: indexOf.onlyintersections === undefined ? base.onlyIntersections : boolFromValue(cols[indexOf.onlyintersections], base.onlyIntersections),
        clusterSeeds: indexOf.clusterseeds === undefined ? base.clusterSeeds : Number.parseInt(cols[indexOf.clusterseeds], 10),
        clusterDecayMeters: indexOf.clusterdecaymeters === undefined ? base.clusterDecayMeters : Number.parseFloat(cols[indexOf.clusterdecaymeters]),
        hybridPoiShare: indexOf.hybridpoishare === undefined ? base.hybridPoiShare : Number.parseFloat(cols[indexOf.hybridpoishare]),
        categories: indexOf.categories === undefined ? bulkCategoryTextFromBase(base) : cols[indexOf.categories],
      }, base));
      state.generation.bulkNextId += 1;
      added += 1;
    }
    renderBulkTable();
    showToast(`Imported ${added} instance(s) from CSV`);
  };
  reader.readAsText(file);
}

function openBulkModal() {
  if (!bulkModal) return;
  bulkModal.hidden = false;
  bulkModal.style.display = "flex";
}

function closeBulkModal() {
  if (!bulkModal) return;
  bulkModal.hidden = true;
  bulkModal.style.display = "";
}

tabVisualize.addEventListener("click", () => setActiveTab("visualize"));
tabGenerate.addEventListener("click", () => setActiveTab("generate"));
sourceBenchmarkBtn.addEventListener("click", async () => {
  await setSourceKind("benchmark", { fitMap: true });
  setActiveTab("visualize");
});
sourceUploadBtn.addEventListener("click", async () => {
  await setSourceKind("upload", { fitMap: false });
  setActiveTab("visualize");
});
window.addEventListener("resize", refreshMapSize);
map.on("zoomend", () => {
  if (state.activeTab === "generate") {
    return;
  }
  renderVisualState();
});

benchmarkObjectiveSelect.addEventListener("change", async (event) => {
  state.objectiveFunction = event.target.value || null;
  await loadBenchmarkInstance(state.instanceRoute, state.objectiveFunction, { quiet: true, fitMap: false });
});

benchmarkCatalogSelect.addEventListener("change", async (event) => {
  state.benchmarkCatalog.selectedGroupKey = event.target.value || null;
  const activeItem = state.instanceRoute
    ? state.benchmarkCatalog.options.find((item) => normalizeRoute(item.route_path) === normalizeRoute(state.instanceRoute))
    : null;
  if (!activeItem || benchmarkCatalogGroupKey(activeItem) !== state.benchmarkCatalog.selectedGroupKey) {
    await loadBenchmarkInstance(null, null, { quiet: true, fitMap: false });
  } else {
    renderBenchmarkCatalogOptions();
  }
  setActiveTab("visualize");
});

benchmarkInstanceSelect.addEventListener("change", async (event) => {
  const nextRoute = event.target.value || null;
  if (!nextRoute) {
    return;
  }
  state.objectiveFunction = null;
  await loadBenchmarkInstance(nextRoute, null, { fitMap: true });
  setActiveTab("visualize");
});

vrpInput.addEventListener("change", async (event) => {
  const file = event.target.files?.[0];
  if (!file) {
    return;
  }
  try {
    const text = await file.text();
    const isJsonInstance = /\.json$/i.test(file.name);
    state.upload.instanceData = parseUploadedInstanceText(text, file.name);
    state.upload.vrpText = isJsonInstance ? null : text;
    state.upload.vrpJsonPayload = isJsonInstance ? JSON.parse(text) : null;
    state.upload.vrpFileName = file.name;
    state.upload.routes = [];
    state.upload.solutionInfo = null;
    state.upload.roadGeojson = null;
    state.upload.renderSummary = null;
    state.selectedRoutes.clear();
    requestVisualFit();
    await setSourceKind("upload", { fitMap: true });
    setActiveTab("visualize");
    showToast(`Loaded instance ${state.upload.instanceData.name || file.name}`);
  } catch (error) {
    console.error(error);
    showToast(`Instance parse error: ${error.message || error}`);
  }
});

solInput.addEventListener("change", async (event) => {
  const file = event.target.files?.[0];
  if (!file) {
    return;
  }
  if (!state.upload.instanceData) {
    showToast("Load an instance file first.");
    return;
  }
  try {
    const text = await file.text();
    const solutionPayload = parseUploadedSolutionText(text, file.name, state.upload.instanceData.dimension || state.upload.instanceData.coordinates?.length || 0);
    state.upload.routes = solutionPayload.routes;
    state.upload.solutionInfo = solutionPayload.info;
    state.upload.roadGeojson = null;
    state.upload.renderSummary = null;
    state.selectedRoutes.clear();
    await setSourceKind("upload", { fitMap: false });
    setActiveTab("visualize");
    showToast(`Loaded solution with ${state.upload.routes.length} route(s)`);
  } catch (error) {
    console.error(error);
    showToast(`Solution parse error: ${error.message || error}`);
  }
});

metaInput.addEventListener("change", async (event) => {
  const file = event.target.files?.[0];
  if (!file) {
    return;
  }
  try {
    const text = await file.text();
    state.upload.meta = parseUploadedMetaText(text, file.name);
    state.upload.roadGeojson = null;
    state.upload.renderSummary = null;
    requestVisualFit();
    await setSourceKind("upload", { fitMap: true });
    setActiveTab("visualize");
    showToast(`Loaded metadata ${file.name}`);
  } catch (error) {
    console.error(error);
    showToast(`Metadata parse error: ${error.message || error}`);
  }
});

roadBtn.addEventListener("click", async () => {
  if (!state.upload.instanceData || state.upload.routes.length === 0) {
    showToast("Load both an instance and a solution before requesting road geometry.");
    return;
  }
  if (!state.upload.meta) {
    showToast("Load a metadata sidecar before requesting road geometry.");
    return;
  }
  if (window.location.protocol === "file:") {
    showToast("Road geometry rendering requires the site API server over HTTP.");
    return;
  }
  const operationId = `upload-render-${Date.now()}`;
  const totalStops = state.upload.routes.reduce((sum, route) => sum + route.length, 0);
  startProgressBar(
    "Rendering Road Geometry",
    operationId,
    roadBtn,
    predictDuration("Rendering Road Geometry", { routes: state.upload.routes.length, stops: totalStops }),
  );
  try {
    const response = await postWorkbenchJson(currentRenderEndpoint(), {
      meta: state.upload.meta,
      routes: uploadedPreviewRoutesToMetaRoutes(state.upload.routes, state.upload.meta),
      metric: metricSelect.value || "shortest",
    });
    state.upload.roadGeojson = response.geojson || null;
    state.upload.renderSummary = response.summary || null;
    state.lastApiError = null;
    await setSourceKind("upload", { sync: false });
    renderVisualState({ fitMap: false });
    completeProgressBar(operationId);
    showToast(`Rendered road geometry (${metricSelect.value || "shortest"})`);
  } catch (error) {
    console.error(error);
    state.lastApiError = error.message || String(error);
    state.upload.roadGeojson = null;
    state.upload.renderSummary = null;
    renderVisualState({ fitMap: false });
    hideAllProgressBars();
    showToast(`Road geometry error: ${error.message || error}`);
  }
});

solveBtn.addEventListener("click", async () => {
  if (!state.upload.instanceData) {
    showToast("Load a CVRP instance file first.");
    return;
  }
  if (!state.upload.vrpText && !state.upload.vrpJsonPayload) {
    showToast("HGS solving requires an uploaded .vrp or .vrp.json instance file.");
    return;
  }
  if (window.location.protocol === "file:") {
    showToast("HGS solving requires the site API server over HTTP.");
    return;
  }

  const timeLimit = Number.parseFloat(solveTimeLimitInput.value);
  const requestedTimeLimit = Number.isFinite(timeLimit) && timeLimit > 0 ? timeLimit : 30;
  const operationId = `solve-hgs-${Date.now()}`;
  startProgressBar(
    "Solving with HGS",
    operationId,
    solveBtn,
    Math.max(3000, requestedTimeLimit * 1000),
  );

  try {
    const requestBody = state.upload.vrpJsonPayload
      ? { vrp_json: state.upload.vrpJsonPayload, time_limit: requestedTimeLimit }
      : { vrp_text: state.upload.vrpText, time_limit: requestedTimeLimit };
    const response = await postWorkbenchJson("/api/workbench/solve", requestBody);
    const hgsRoutes = Array.isArray(response.routes) ? response.routes : [];
    if (hgsRoutes.length === 0) {
      throw new Error("HGS returned no routes");
    }

    const dimension = state.upload.instanceData.dimension
      || (Array.isArray(state.upload.instanceData.coordinates) ? state.upload.instanceData.coordinates.length : 0);
    const solText = hgsRoutes
      .map((route, index) => `Route #${index + 1}: ${route.join(" ")}`)
      .join("\n") + "\n";
    const solutionPayload = parseUploadedSolutionText(solText, "hgs.sol", dimension);

    state.upload.routes = solutionPayload.routes;
    state.upload.solutionInfo = { ...solutionPayload.info, source: "hgs", cost: response.cost, solveTime: response.time };
    state.upload.roadGeojson = null;
    state.upload.renderSummary = null;
    state.selectedRoutes.clear();
    state.lastApiError = null;
    await setSourceKind("upload", { sync: false });
    renderVisualState({ fitMap: false });
    completeProgressBar(operationId);
    const costDisplay = Number.isFinite(Number(response.cost)) ? Math.round(Number(response.cost)) : "?";
    showToast(`HGS solved: ${hgsRoutes.length} route(s), cost ${costDisplay}`);
  } catch (error) {
    console.error(error);
    state.lastApiError = error.message || String(error);
    hideAllProgressBars();
    showToast(`HGS solve error: ${error.message || error}`);
  }
});

genDisplayBtn.addEventListener("click", async () => {
  if (state.generation.generated?.geojson) {
    setActiveTab("generate");
    requestPreviewFit();
    renderGenerationPreview(
      state.generation.generated.geojson,
      state.generation.generated.summary || {},
      { fitMap: true },
    );
    showToast(`Displaying generated instance for ${state.generation.generated.summary?.city || "selected city"}`);
    return;
  }
  if (window.location.protocol === "file:") {
    showToast("Generation preview requires the site API server over HTTP.");
    return;
  }
  const operationId = `generation-preview-${Date.now()}`;
  try {
    const payload = currentGenerationPreviewPayload();
    startProgressBar(
      "Generating Preview",
      operationId,
      genDisplayBtn,
      predictDuration("Generating Preview", { customers: payload.nCustomers }),
    );
    const response = await postWorkbenchJson(WORKBENCH_GENERATION_PREVIEW_PATH, payload);
    setActiveTab("generate");
    requestPreviewFit();
    renderGenerationPreview(response.geojson, response.summary || {}, { fitMap: true });
    completeProgressBar(operationId);
    showToast(`Preview ready for ${response.summary?.city || payload.city}`);
  } catch (error) {
    console.error(error);
    genResult.textContent = error.message || String(error);
    hideAllProgressBars();
    showToast(`Generation preview error: ${error.message || error}`);
  }
});

genGenerateBtn.addEventListener("click", async () => {
  if (window.location.protocol === "file:") {
    showToast("Instance generation requires the site API server over HTTP.");
    return;
  }
  const payload = currentGenerationPreviewPayload();
  const operationId = `generation-generate-${Date.now()}`;
  startProgressBar(
    "Generating Preview Data",
    operationId,
    genGenerateBtn,
    predictDuration("Generating Preview", { customers: payload.nCustomers }),
  );
  try {
    const response = await postWorkbenchJson(WORKBENCH_GENERATION_GENERATE_PATH, payload);
    state.generation.generated = {
      geojson: response.geojson || null,
      summary: response.summary || {},
      payload,
    };
    const summary = response.summary || {};
    const lines = [
      `Problem type: ${payload.problemType}`,
      `City: ${summary.city ?? payload.city ?? "n/a"}`,
      `Method: ${summary.method ?? payload.method ?? "n/a"}`,
      `Customers: ${summary.customers ?? payload.nCustomers ?? "n/a"}`,
      `  POI: ${summary.poi_customers ?? "n/a"}`,
      `  Parametric: ${summary.parametric_customers ?? 0}`,
    ];
    if ((summary.parametric_customers ?? 0) > 0) {
      lines.push(`⚠ Not enough POI — ${summary.parametric_customers} customer(s) filled with parametric placement`);
    }
    if (payload.problemType === "VRPTW") {
      lines.push(`TW method: ${payload.twMethod}`);
      lines.push("Download Files will let you choose a folder to save the CVRPTW files.");
    } else {
      lines.push("Download Files will let you choose a folder to save the CVRP files.");
    }
    lines.push("Press 'Display on Map' to render this selection.");
    genResult.textContent = lines.join("\n");
    completeProgressBar(operationId);
    showToast(`Generated instance for ${summary.city ?? payload.city}`);
  } catch (error) {
    console.error(error);
    state.generation.generated = null;
    genResult.textContent = `Generation error: ${error.message || error}`;
    hideAllProgressBars();
    showToast(`Generation failed: ${error.message || error}`);
  }
});

async function saveZipBlob(blob, suggestedName) {
  if (typeof window.showSaveFilePicker === "function") {
    const handle = await window.showSaveFilePicker({
      suggestedName,
      types: [
        {
          description: "Zip archive",
          accept: { "application/zip": [".zip"] },
        },
      ],
    });
    const writable = await handle.createWritable();
    await writable.write(blob);
    await writable.close();
    return handle.name || suggestedName;
  }
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = suggestedName;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
  return "browser download folder";
}

genFilesBtn.addEventListener("click", async () => {
  if (window.location.protocol === "file:") {
    showToast("Downloading generated files requires the site API server over HTTP.");
    return;
  }
  const cached = state.generation.generated;
  const currentPayload = currentGenerationPreviewPayload();
  const payload = {
    ...(cached?.payload || {}),
    ...currentPayload,
  };
  const operationId = `generation-download-${Date.now()}`;
  startProgressBar(
    "Preparing Download",
    operationId,
    genFilesBtn,
    predictDuration("Generating Preview", { customers: payload.nCustomers }),
  );
  try {
    const { blob, filename } = await postWorkbenchBlob(WORKBENCH_GENERATION_SINGLE_DOWNLOAD_PATH, payload);
    const suggestedName = filename || "instance.zip";

    let location;
    try {
      location = await saveZipBlob(blob, suggestedName);
    } catch (saveError) {
      if (saveError && saveError.name === "AbortError") {
        genResult.textContent = "Download cancelled.";
        hideAllProgressBars();
        showToast("Download cancelled.");
        return;
      }
      throw saveError;
    }

    const sizeKb = Math.max(1, Math.round(blob.size / 1024));
    genResult.textContent = [
      `Downloaded archive: ${suggestedName}`,
      `Saved to: ${location}`,
      `Size: ${sizeKb} KB`,
      "The archive includes MAMUT_summary.json with generation details.",
    ].join("\n");
    completeProgressBar(operationId);
    showToast(`Downloaded ${suggestedName}`);
  } catch (error) {
    console.error(error);
    genResult.textContent = `Download error: ${error.message || error}`;
    hideAllProgressBars();
    showToast(`Download failed: ${error.message || error}`);
  }
});

if (genFetchBtn) {
  genFetchBtn.addEventListener("click", async () => {
    if (window.location.protocol === "file:") {
      showToast("Fetching OSM requires the site API server over HTTP.");
      return;
    }
    const city = (genFetchCityInput?.value || "").trim();
    if (!city) {
      showToast("Enter a city name to fetch OSM data.");
      genFetchCityInput?.focus();
      return;
    }
    const country = (genFetchCountryInput?.value || "").trim();
    const padding = Number.parseFloat(genFetchPaddingInput?.value || "0");
    const operationId = `fetch-osm-${Date.now()}`;
    genFetchBtn.disabled = true;
    const originalLabel = genFetchBtn.textContent;
    genFetchBtn.textContent = "Fetching…";
    startProgressBar(
      "Downloading OSM Data",
      operationId,
      genFetchBtn,
      45000,
    );
    try {
      const response = await postWorkbenchJson(WORKBENCH_GENERATION_FETCH_OSM_PATH, {
        city,
        country,
        paddingKm: Number.isFinite(padding) && padding > 0 ? padding : 0,
      });
      const fetchedSlug = String(response.city || city);
      await loadGenerationCities();
      const fetchedSlugLower = fetchedSlug.toLowerCase();
      const matchingOption = Array.from(genCitySelect.options).find((option) => option.value.toLowerCase() === fetchedSlugLower);
      if (matchingOption) {
        genCitySelect.value = matchingOption.value;
      }
      renderBulkTable();
      const lines = [
        `Fetched OSM for ${fetchedSlug}`,
        `Path: ${response.osm_path || "?"}`,
        `Dataset mode: ${response.dataset_mode || "?"}`,
      ];
      if (response.amenity_tiling && Number(response.amenity_tiling.amenity_nodes_added) > 0) {
        lines.push(`Tiled amenities added: ${response.amenity_tiling.amenity_nodes_added} (tiles ok ${response.amenity_tiling.tiles_ok}/${response.amenity_tiling.tiles_total})`);
      }
      if (response.warning) {
        lines.push(`⚠ ${response.warning}`);
      }
      genResult.textContent = lines.join("\n");
      completeProgressBar(operationId);
      showToast(`Fetched OSM for ${fetchedSlug}`);
    } catch (error) {
      console.error(error);
      genResult.textContent = `Fetch OSM error: ${error.message || error}`;
      hideAllProgressBars();
      showToast(`Fetch OSM failed: ${error.message || error}`);
    } finally {
      genFetchBtn.disabled = false;
      genFetchBtn.textContent = originalLabel;
    }
  });
}

if (genPoiSelectAllBtn) {
  genPoiSelectAllBtn.addEventListener("click", () => {
    genPoiList?.querySelectorAll("input[type='checkbox']").forEach((cb) => { cb.checked = true; });
    updatePoiCount();
  });
}
if (genPoiClearBtn) {
  genPoiClearBtn.addEventListener("click", () => {
    genPoiList?.querySelectorAll("input[type='checkbox']").forEach((cb) => { cb.checked = false; });
    updatePoiCount();
  });
}
if (genHybridShareInput && genHybridShareValue) {
  genHybridShareInput.addEventListener("input", () => {
    genHybridShareValue.textContent = Number.parseFloat(genHybridShareInput.value).toFixed(2);
  });
}
if (genMethodSelect) {
  genMethodSelect.addEventListener("change", updateGenerationFieldVisibility);
}
if (genCustomerModeSelect) {
  genCustomerModeSelect.addEventListener("change", updateGenerationFieldVisibility);
}
if (genProblemTypeSelect) {
  genProblemTypeSelect.addEventListener("change", updateGenerationFieldVisibility);
}

if (openBulkModalBtn) openBulkModalBtn.addEventListener("click", openBulkModal);
if (closeBulkModalBtn) closeBulkModalBtn.addEventListener("click", closeBulkModal);
if (closeBulkModalBtn2) closeBulkModalBtn2.addEventListener("click", closeBulkModal);
if (bulkModal) {
  bulkModal.addEventListener("click", (event) => {
    if (event.target === bulkModal) closeBulkModal();
  });
}
if (bulkCitySelectAllBtn) {
  bulkCitySelectAllBtn.addEventListener("click", () => {
    genBulkCitiesSelect?.querySelectorAll("input[type='checkbox']").forEach((cb) => { cb.checked = true; });
    updateBulkCityCount();
  });
}
if (bulkCityClearBtn) {
  bulkCityClearBtn.addEventListener("click", () => {
    genBulkCitiesSelect?.querySelectorAll("input[type='checkbox']").forEach((cb) => { cb.checked = false; });
    updateBulkCityCount();
  });
}
if (bulkExpandBtn) bulkExpandBtn.addEventListener("click", expandBulkCombinations);
if (bulkAddRowBtn) bulkAddRowBtn.addEventListener("click", addBulkRow);
if (bulkDeleteSelBtn) bulkDeleteSelBtn.addEventListener("click", deleteSelectedBulkRows);
if (bulkClearBtn) {
  bulkClearBtn.addEventListener("click", () => {
    state.generation.bulkInstances = [];
    renderBulkTable();
  });
}
if (bulkExportCsvBtn) bulkExportCsvBtn.addEventListener("click", exportBulkCsv);
if (bulkImportCsvBtn) bulkImportCsvBtn.addEventListener("click", () => bulkCsvFileInput?.click());
if (bulkCsvFileInput) {
  bulkCsvFileInput.addEventListener("change", () => {
    if (bulkCsvFileInput.files && bulkCsvFileInput.files.length > 0) {
      importBulkCsv(bulkCsvFileInput.files[0]);
      bulkCsvFileInput.value = "";
    }
  });
}
if (bulkSelectAll) {
  bulkSelectAll.addEventListener("change", () => {
    bulkTableBody?.querySelectorAll(".bulk-row-check").forEach((cb) => {
      cb.checked = bulkSelectAll.checked;
    });
  });
}

if (genBulkBtn) {
  genBulkBtn.addEventListener("click", async () => {
    if (window.location.protocol === "file:") {
      showToast("Bulk generation requires the site API server over HTTP.");
      return;
    }
    if (state.generation.bulkInstances.length === 0) {
      showToast("Add instances to the table first");
      return;
    }
    const base = currentGenerationPreviewPayload();
    const operationId = `bulk-generate-${Date.now()}`;
    const maxN = Math.max(...state.generation.bulkInstances.map((row) => row.nCustomers), 50);
    startProgressBar(
      "Bulk Generation",
      operationId,
      genBulkBtn,
      Math.max(5000, state.generation.bulkInstances.length * (200 + maxN * 30)),
    );
    try {
      const payload = {
        instances: state.generation.bulkInstances.map((row) => {
          applyBulkRowDefaults(row, base);
          return {
            problemType: row.problemType,
            city: row.city,
            nCustomers: row.nCustomers,
            demandType: row.demandType,
            avgRouteSize: row.avgRouteSize,
            method: row.method,
            seed: row.seed,
            depotMode: row.depotMode,
            customerMode: row.customerMode,
            twMethod: row.twMethod,
            twHorizonStart: VRPTW_DEFAULT_HORIZON_START,
            twHorizonEnd: VRPTW_DEFAULT_HORIZON_END,
            onlyIntersections: row.onlyIntersections,
            clusterSeeds: row.clusterSeeds,
            clusterDecayMeters: row.clusterDecayMeters,
            hybridPoiShare: row.hybridPoiShare,
            categories: row.categories,
          };
        }),
        categories: base.categories,
        hybridPoiShare: base.hybridPoiShare,
        onlyIntersections: base.onlyIntersections,
        clusterSeeds: base.clusterSeeds,
        clusterDecayMeters: base.clusterDecayMeters,
        twMethod: base.twMethod || bulkPanelTwMethod(),
        twHorizonStart: VRPTW_DEFAULT_HORIZON_START,
        twHorizonEnd: VRPTW_DEFAULT_HORIZON_END,
      };
      const { blob, filename } = await postWorkbenchBlob(WORKBENCH_GENERATION_BULK_DOWNLOAD_PATH, payload);
      const suggestedName = filename || "mamut_bulk.zip";

      let saveLocation;
      try {
        saveLocation = await saveZipBlob(blob, suggestedName);
      } catch (saveError) {
        if (saveError && saveError.name === "AbortError") {
          genResult.textContent = "Bulk download cancelled.";
          hideAllProgressBars();
          showToast("Bulk download cancelled.");
          return;
        }
        throw saveError;
      }

      const sizeKb = Math.max(1, Math.round(blob.size / 1024));
      genResult.textContent = [
        `Downloaded archive: ${suggestedName}`,
        `Saved to: ${saveLocation}`,
        `Size: ${sizeKb} KB`,
        "The archive includes MAMUT_summary.json listing instances and city reports.",
      ].join("\n");
      completeProgressBar(operationId);
      showToast(`Downloaded ${suggestedName}`);
      closeBulkModal();
    } catch (error) {
      console.error(error);
      genResult.textContent = `Bulk generation error: ${error.message || error}`;
      hideAllProgressBars();
      showToast(`Bulk generation failed: ${error.message || error}`);
    }
  });
}

clearBtn.addEventListener("click", async () => {
  hideAllProgressBars();
  clearMapLayers();
  routeLegendEl.innerHTML = "";
  statsEl.innerHTML = "";
  routeSelectorCard.style.display = "none";
  state.selectedRoutes.clear();
  if (state.sourceKind === "upload") {
    resetUploadState();
    vrpInput.value = "";
    solInput.value = "";
    metaInput.value = "";
  } else if (state.instanceRoute) {
    await loadBenchmarkInstance(state.instanceRoute, state.objectiveFunction, { quiet: true });
    return;
  }
  state.generation.generated = null;
  state.generation.previewSummary = null;
  map.setView([48.8566, 2.3522], 11);
  genResult.textContent = "No generation call yet.";
  showToast("Cleared current map layers");
});

if (window.location.protocol !== "file:") {
  apiUrlInput.value = new URL(WORKBENCH_RENDER_ROUTES_PATH, window.location.origin).toString();
}

setupThemeToggle();
browseBenchmarksBtn.href = routeHref("/benchmarks/");
renderPoiCategoryMenu();
updateGenerationFieldVisibility();
if (genHybridShareInput && genHybridShareValue) {
  genHybridShareValue.textContent = Number.parseFloat(genHybridShareInput.value).toFixed(2);
}
refreshBulkBadges();
updateVisualModePanels();
updateBenchmarkContextUi();
const benchmarkCatalogPromise = loadBenchmarkCatalogOptions();
await loadBenchmarkInstance(state.instanceRoute, state.objectiveFunction, { quiet: true });
await loadGenerationCities();
await benchmarkCatalogPromise;
await setSourceKind(state.sourceKind, { sync: false });
setActiveTab(state.activeTab, { sync: false });
renderVisualState();
