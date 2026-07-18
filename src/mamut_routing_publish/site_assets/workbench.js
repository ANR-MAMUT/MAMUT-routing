const body = document.body;
const runtimeParams = new URLSearchParams(window.location.search);
const CANONICAL_WORKBENCH_ROUTE = "/workbench/";
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
  fetchGeometryMetaMemo,
  fetchJson,
  fetchRouteGeometryMetaMemo,
  fetchWorkbenchPayloadForRoute,
  normalizeRoute,
  parseUploadedInstanceText,
  parseUploadedMetaText,
  parseUploadedSolutionText,
  projectEnuInstanceCoordinates,
  resolvePreviewGeometry,
  routeHref,
  setupThemeToggle,
} = siteHelpers;

const tabVisualize = document.getElementById("tabVisualize");
const tabGenerate = document.getElementById("tabGenerate");
const visualPanel = document.getElementById("visualPanel");
const generationPanel = document.getElementById("generationPanel");
const sourceBenchmarkBtn = document.getElementById("sourceBenchmarkBtn");
const sourceUploadBtn = document.getElementById("sourceUploadBtn");
const benchmarkVisualPanel = document.getElementById("benchmarkVisualPanel");
const uploadVisualPanel = document.getElementById("uploadVisualPanel");
const benchmarkProblemSelect = document.getElementById("benchmarkProblemSelect");
const benchmarkCatalogSelect = document.getElementById("benchmarkCatalogSelect");
const benchmarkInstanceSelect = document.getElementById("benchmarkInstanceSelect");
const benchmarkMetricFilter = document.getElementById("benchmarkMetricFilter");
const benchmarkCityFilter = document.getElementById("benchmarkCityFilter");
const benchmarkSizeFilter = document.getElementById("benchmarkSizeFilter");
const benchmarkMethodFilter = document.getElementById("benchmarkMethodFilter");
const benchmarkScenarioFilter = document.getElementById("benchmarkScenarioFilter");
const benchmarkSearchFilter = document.getElementById("benchmarkSearchFilter");
const benchmarkSortSelect = document.getElementById("benchmarkSortSelect");
const benchmarkStatus = document.getElementById("benchmarkStatus");
const benchmarkRenderStatus = document.getElementById("benchmarkRenderStatus");
const objectiveField = document.getElementById("objectiveField");
const benchmarkObjectiveSelect = document.getElementById("benchmarkObjectiveSelect");
const openBenchmarkBtn = document.getElementById("openBenchmarkBtn");
const browseBenchmarksBtn = document.getElementById("browseBenchmarksBtn");
const vrpInput = document.getElementById("vrpInput");
const solInput = document.getElementById("solInput");
const metaInput = document.getElementById("metaInput");
const clearBtn = document.getElementById("clearBtn");
const statsEl = document.getElementById("stats");
const routeLegendEl = document.getElementById("routeLegend");
const toastEl = document.getElementById("toast");
const routeSelectorCard = document.getElementById("routeSelectorCard");
const routeSelectorContainer = document.getElementById("routeSelectorContainer");
const map = L.map("map", { zoomControl: true }).setView([48.8566, 2.3522], 11);
const routeCanvasRenderer = L.canvas({ padding: 0.35, tolerance: 5 });
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
  routeView: {
    visibleLimit: 10,
    fadedOpacity: 0.8,
    arrowsEnabled: true,
    depotLegMode: "full",
    search: "",
    minStops: null,
    maxStops: null,
    minLoad: null,
    maxLoad: null,
    page: 1,
    pageSize: 40,
  },
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
    filters: {
      problem: runtimeParams.get("problem") || "",
      family: runtimeParams.get("family") || "",
      metric: runtimeParams.get("metric") || "",
      city: runtimeParams.get("city") || "",
      size: runtimeParams.get("size") || "",
      method: runtimeParams.get("method") || "",
      scenario: runtimeParams.get("scenario") || "",
      search: runtimeParams.get("q") || "",
      sort: runtimeParams.get("sort") || "city-size",
    },
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
  layers: {
    marker: L.layerGroup().addTo(map),
    route: L.layerGroup().addTo(map),
    arrow: L.layerGroup().addTo(map),
    preview: L.layerGroup().addTo(map),
  },
  view: {
    visualShouldFit: false,
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

function benchmarkScenarioValue(item) {
  if (item.tw_set) return `TW: ${item.tw_set}`;
  if (item.traffic_model || item.traffic_intensity) return `Traffic: ${item.traffic_model || "?"} / ${item.traffic_intensity || "?"}`;
  return "";
}

function populateBenchmarkFilter(select, values, placeholder, currentValue) {
  const counts = new Map();
  values.filter(Boolean).forEach((value) => counts.set(value, (counts.get(value) || 0) + 1));
  const options = Array.from(counts.keys()).sort((left, right) => String(left).localeCompare(String(right), undefined, { numeric: true }));
  select.innerHTML = [`<option value="">${escapeHtml(placeholder)}</option>`, ...options.map((value) => `<option value="${escapeHtml(value)}">${escapeHtml(value)} (${counts.get(value)})</option>`)].join("");
  select.value = options.includes(currentValue) ? currentValue : "";
  return select.value;
}

function benchmarkObjectiveNumber(item, field) {
  const values = (item.objective_availability || []).map((entry) => Number(entry?.[field])).filter(Number.isFinite);
  return values.length > 0 ? Math.min(...values) : Number.POSITIVE_INFINITY;
}

function compareFilteredBenchmarkItems(left, right) {
  const filters = state.benchmarkCatalog.filters;
  const leftLocator = benchmarkCatalogLocator(left);
  const rightLocator = benchmarkCatalogLocator(right);
  if (filters.sort === "size") return benchmarkCatalogCustomerCount(left) - benchmarkCatalogCustomerCount(right) || compareBenchmarkCatalogInstances(left, right);
  if (filters.sort === "metric") return String(leftLocator.metric_variant || "").localeCompare(String(rightLocator.metric_variant || "")) || compareBenchmarkCatalogInstances(left, right);
  if (filters.sort === "cost") return benchmarkObjectiveNumber(left, "cost") - benchmarkObjectiveNumber(right, "cost") || compareBenchmarkCatalogInstances(left, right);
  if (filters.sort === "routes") return benchmarkObjectiveNumber(left, "num_routes") - benchmarkObjectiveNumber(right, "num_routes") || compareBenchmarkCatalogInstances(left, right);
  if (filters.sort === "cache") return String(right.road_cache_status || "").localeCompare(String(left.road_cache_status || "")) || compareBenchmarkCatalogInstances(left, right);
  if (filters.sort === "name") return String(left.display_name || "").localeCompare(String(right.display_name || ""), undefined, { numeric: true });
  return String(leftLocator.place_slug || "").localeCompare(String(rightLocator.place_slug || "")) || compareBenchmarkCatalogInstances(left, right);
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
  const filters = state.benchmarkCatalog.filters;
  const selectedItem = state.instanceRoute
    ? state.benchmarkCatalog.options.find((item) => normalizeRoute(item.route_path) === normalizeRoute(state.instanceRoute))
    : null;
  if (selectedItem) {
    filters.problem = benchmarkCatalogLocator(selectedItem).problem_type || filters.problem;
    filters.family = benchmarkCatalogLocator(selectedItem).benchmark_name || filters.family;
  }
  const problemValues = state.benchmarkCatalog.options.map((item) => benchmarkCatalogLocator(item).problem_type).filter(Boolean);
  const problems = Array.from(new Set(problemValues)).sort();
  filters.problem = problems.includes(filters.problem) ? filters.problem : problems[0] || "";
  populateBenchmarkFilter(benchmarkProblemSelect, problemValues, "All problems", filters.problem);
  benchmarkProblemSelect.value = filters.problem;
  const sortedGroups = Array.from(groups.entries())
    .filter(([, group]) => !filters.problem || benchmarkCatalogLocator(group.items[0]).problem_type === filters.problem)
    .sort(([, left], [, right]) => left.label.localeCompare(right.label));
  const selectedGroupKey = selectedItem && (!filters.problem || benchmarkCatalogLocator(selectedItem).problem_type === filters.problem)
    ? benchmarkCatalogGroupKey(selectedItem)
    : state.benchmarkCatalog.selectedGroupKey && sortedGroups.some(([key]) => key === state.benchmarkCatalog.selectedGroupKey)
      ? state.benchmarkCatalog.selectedGroupKey
      : sortedGroups.find(([, group]) => benchmarkCatalogLocator(group.items[0]).benchmark_name === filters.family)?.[0]
        || sortedGroups[0]?.[0]
        || "";
  state.benchmarkCatalog.selectedGroupKey = selectedGroupKey || null;
  filters.family = selectedGroupKey ? benchmarkCatalogLocator(groups.get(selectedGroupKey).items[0]).benchmark_name || "" : "";

  if (sortedGroups.length > 0) {
    benchmarkCatalogSelect.innerHTML = sortedGroups
      .map(([groupKey, group]) => `<option value="${escapeHtml(groupKey)}"${groupKey === selectedGroupKey ? " selected" : ""}>${escapeHtml(benchmarkCatalogLocator(group.items[0]).benchmark_name || group.label)} (${group.items.length})</option>`)
      .join("");
    benchmarkCatalogSelect.disabled = false;
  } else {
    benchmarkCatalogSelect.innerHTML = '<option value="">Published families unavailable</option>';
    benchmarkCatalogSelect.disabled = true;
  }

  const fragments = ['<option value="">Select a published variant…</option>'];
  const rawGroupItems = selectedGroupKey ? groups.get(selectedGroupKey)?.items || [] : [];
  filters.metric = populateBenchmarkFilter(benchmarkMetricFilter, rawGroupItems.map((item) => benchmarkCatalogLocator(item).metric_variant), "All metrics", filters.metric);
  const metricItems = rawGroupItems.filter((item) => !filters.metric || benchmarkCatalogLocator(item).metric_variant === filters.metric);
  filters.city = populateBenchmarkFilter(benchmarkCityFilter, metricItems.map((item) => benchmarkCatalogLocator(item).place_slug), "All cities", filters.city);
  const cityItems = metricItems.filter((item) => !filters.city || benchmarkCatalogLocator(item).place_slug === filters.city);
  filters.size = populateBenchmarkFilter(benchmarkSizeFilter, cityItems.map((item) => String(benchmarkCatalogCustomerCount(item))), "All sizes", filters.size);
  const sizeItems = cityItems.filter((item) => !filters.size || String(benchmarkCatalogCustomerCount(item)) === filters.size);
  filters.method = populateBenchmarkFilter(benchmarkMethodFilter, sizeItems.map((item) => item.sampling_method), "All methods", filters.method);
  const methodItems = sizeItems.filter((item) => !filters.method || item.sampling_method === filters.method);
  filters.scenario = populateBenchmarkFilter(benchmarkScenarioFilter, methodItems.map(benchmarkScenarioValue), "All scenarios", filters.scenario);
  benchmarkSearchFilter.value = filters.search;
  benchmarkSortSelect.value = filters.sort;
  const search = filters.search.trim().toLowerCase();
  const selectedGroupItems = rawGroupItems.filter((item) => {
    const locator = benchmarkCatalogLocator(item);
    if (filters.metric && locator.metric_variant !== filters.metric) return false;
    if (filters.city && locator.place_slug !== filters.city) return false;
    if (filters.size && String(benchmarkCatalogCustomerCount(item)) !== filters.size) return false;
    if (filters.method && item.sampling_method !== filters.method) return false;
    if (filters.scenario && benchmarkScenarioValue(item) !== filters.scenario) return false;
    if (search && !`${item.display_name || ""} ${item.base_instance || ""} ${locator.instance_identifier || ""}`.toLowerCase().includes(search)) return false;
    return true;
  });
  Array.from(buildBenchmarkCatalogInstanceGroups(selectedGroupItems).values())
    .sort((left, right) => compareFilteredBenchmarkItems(left.head, right.head))
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
    const itemsByRoute = new Map();
    (Array.isArray(benchmarksPayload?.items) ? benchmarksPayload.items : []).forEach((item) => {
      if (!item?.route_path || itemsByRoute.has(item.route_path)) {
        return;
      }
      itemsByRoute.set(item.route_path, item);
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

function resetRouteViewDefaults(routes) {
  const routeCount = Array.isArray(routes) ? routes.length : 0;
  state.selectedRoutes.clear();
  if (routeCount <= 10) {
    for (let index = 0; index < routeCount; index += 1) {
      state.selectedRoutes.add(index);
    }
  } else if (routeCount > 0) {
    state.selectedRoutes.add(0);
  }
  state.routeView.visibleLimit = routeCount >= 100 ? 99 : routeCount;
  state.routeView.fadedOpacity = 0.8;
  state.routeView.arrowsEnabled = routeCount <= 10;
  state.routeView.depotLegMode = routeCount <= 10 ? "full" : "faded";
  state.routeView.search = "";
  state.routeView.minStops = null;
  state.routeView.maxStops = null;
  state.routeView.minLoad = null;
  state.routeView.maxLoad = null;
  state.routeView.page = 1;
}

function routeMatchesView(route, routeIndex, instanceData) {
  const search = state.routeView.search.trim().toLowerCase();
  if (search && !`route ${routeIndex + 1}`.includes(search) && !String(routeIndex + 1).includes(search)) {
    return false;
  }
  const stops = route.length;
  const load = routeLoad(route, instanceData);
  if (state.routeView.minStops != null && stops < state.routeView.minStops) return false;
  if (state.routeView.maxStops != null && stops > state.routeView.maxStops) return false;
  if (state.routeView.minLoad != null && load < state.routeView.minLoad) return false;
  if (state.routeView.maxLoad != null && load > state.routeView.maxLoad) return false;
  return true;
}

function filteredRouteIndices(routes, instanceData) {
  return routes.map((route, index) => ({ route, index }))
    .filter(({ route, index }) => routeMatchesView(route, index, instanceData))
    .map(({ index }) => index);
}

function visibleRouteIndices(routes, instanceData) {
  const filtered = filteredRouteIndices(routes, instanceData);
  const visible = new Set(filtered.slice(0, Math.max(0, state.routeView.visibleLimit)));
  state.selectedRoutes.forEach((index) => {
    if (filtered.includes(index)) visible.add(index);
  });
  return visible;
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

function updateVisualModePanels() {
  const benchmarkActive = state.sourceKind === "benchmark";
  benchmarkVisualPanel.hidden = !benchmarkActive;
  uploadVisualPanel.hidden = benchmarkActive;
}

function updateRouteCheckboxStates() {
  const routeCheckboxes = routeSelectorContainer.querySelectorAll("input.route-checkbox");
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
  const filtered = filteredRouteIndices(routes, instanceData);
  const visible = visibleRouteIndices(routes, instanceData);
  const totalPages = Math.max(1, Math.ceil(filtered.length / state.routeView.pageSize));
  state.routeView.page = Math.min(Math.max(1, state.routeView.page), totalPages);
  const pageStart = (state.routeView.page - 1) * state.routeView.pageSize;
  const pageIndices = filtered.slice(pageStart, pageStart + state.routeView.pageSize);

  routeSelectorContainer.innerHTML = `
    <p class="route-view-summary">${routes.length} total · ${filtered.length} filtered · ${visible.size} visible · ${state.selectedRoutes.size} full opacity · ${Math.max(0, routes.length - visible.size)} hidden</p>
    <div class="route-view-grid">
      <label class="field"><span>Search route</span><input class="route-view-search" type="search" value="${escapeHtml(state.routeView.search)}" placeholder="Route number" /></label>
      <label class="field"><span>Visible limit</span><input class="route-view-limit" type="number" min="0" max="${routes.length}" value="${state.routeView.visibleLimit}" /></label>
      <label class="field"><span>Faded opacity</span><input class="route-view-opacity" type="range" min="0.03" max="0.8" step="0.01" value="${state.routeView.fadedOpacity}" /></label>
      <label class="field"><span>Depot legs</span><select class="route-view-depot"><option value="full">Full</option><option value="faded">Faded</option><option value="absent">Absent</option></select></label>
      <label class="route-view-toggle"><input class="route-view-arrows" type="checkbox"${state.routeView.arrowsEnabled ? " checked" : ""} /> Direction arrows</label>
    </div>
    <div class="route-view-grid route-filter-grid">
      <label class="field"><span>Min stops</span><input data-route-filter="minStops" type="number" min="0" value="${state.routeView.minStops ?? ""}" /></label>
      <label class="field"><span>Max stops</span><input data-route-filter="maxStops" type="number" min="0" value="${state.routeView.maxStops ?? ""}" /></label>
      <label class="field"><span>Min load</span><input data-route-filter="minLoad" type="number" min="0" value="${state.routeView.minLoad ?? ""}" /></label>
      <label class="field"><span>Max load</span><input data-route-filter="maxLoad" type="number" min="0" value="${state.routeView.maxLoad ?? ""}" /></label>
    </div>
    <div class="btn-row route-view-actions">
      <button type="button" data-route-action="all">Show all</button>
      <button type="button" data-route-action="filtered">Show filtered</button>
      <button type="button" data-route-action="selected">Show selected</button>
      <button type="button" data-route-action="none">Show none</button>
      <button type="button" data-route-action="full-filtered">Full opacity: filtered</button>
      <button type="button" data-route-action="fade-filtered">Fade: filtered</button>
    </div>
    <p class="meta-line">Checked routes use full opacity. Unchecked visible routes use the faded opacity.</p>
  `;
  routeSelectorContainer.querySelector(".route-view-depot").value = state.routeView.depotLegMode;

  const rerender = () => renderVisualState({ fitMap: false });
  routeSelectorContainer.querySelector(".route-view-search").addEventListener("change", (event) => {
    state.routeView.search = event.target.value;
    state.routeView.page = 1;
    rerender();
  });
  routeSelectorContainer.querySelector(".route-view-limit").addEventListener("change", (event) => {
    state.routeView.visibleLimit = Math.max(0, Math.min(routes.length, Number(event.target.value) || 0));
    rerender();
  });
  routeSelectorContainer.querySelector(".route-view-opacity").addEventListener("input", (event) => {
    state.routeView.fadedOpacity = Number(event.target.value);
    rerender();
  });
  routeSelectorContainer.querySelector(".route-view-depot").addEventListener("change", (event) => {
    state.routeView.depotLegMode = event.target.value;
    rerender();
  });
  routeSelectorContainer.querySelector(".route-view-arrows").addEventListener("change", (event) => {
    state.routeView.arrowsEnabled = event.target.checked;
    rerender();
  });
  routeSelectorContainer.querySelectorAll("[data-route-filter]").forEach((input) => {
    input.addEventListener("change", () => {
      const raw = input.value.trim();
      state.routeView[input.dataset.routeFilter] = raw === "" ? null : Number(raw);
      state.routeView.page = 1;
      rerender();
    });
  });
  routeSelectorContainer.querySelectorAll("[data-route-action]").forEach((button) => {
    button.addEventListener("click", () => {
      const action = button.dataset.routeAction;
      if (action === "all") {
        state.routeView.search = "";
        state.routeView.minStops = state.routeView.maxStops = state.routeView.minLoad = state.routeView.maxLoad = null;
        state.routeView.visibleLimit = routes.length;
      } else if (action === "filtered") {
        state.routeView.visibleLimit = filtered.length;
      } else if (action === "selected") {
        state.routeView.visibleLimit = 0;
      } else if (action === "none") {
        state.routeView.visibleLimit = 0;
        state.selectedRoutes.clear();
      } else if (action === "full-filtered") {
        filtered.forEach((index) => state.selectedRoutes.add(index));
      } else if (action === "fade-filtered") {
        filtered.forEach((index) => state.selectedRoutes.delete(index));
      }
      rerender();
    });
  });

  const routeList = document.createElement("div");
  routeList.className = "route-page-list";
  pageIndices.forEach((index) => {
    const route = routes[index];
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
    });
    label.appendChild(checkbox);
    label.appendChild(document.createTextNode(`Route #${index + 1} (${route.length} stops, load ${routeLoad(route, instanceData)})`));
    routeList.appendChild(label);
  });
  routeSelectorContainer.appendChild(routeList);

  const pager = document.createElement("div");
  pager.className = "route-pager";
  pager.innerHTML = `<button type="button" data-page="prev"${state.routeView.page <= 1 ? " disabled" : ""}>Previous</button><span>Page ${state.routeView.page} / ${totalPages}</span><button type="button" data-page="next"${state.routeView.page >= totalPages ? " disabled" : ""}>Next</button>`;
  pager.querySelector('[data-page="prev"]').addEventListener("click", () => { state.routeView.page -= 1; rerender(); });
  pager.querySelector('[data-page="next"]').addEventListener("click", () => { state.routeView.page += 1; rerender(); });
  routeSelectorContainer.appendChild(pager);

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
  const visible = visibleRouteIndices(routes, instanceData);
  routeLines.forEach((routeLine) => {
    const routeIndex = routeLine.routeIndex;
    if (!visible.has(routeIndex)) {
      return;
    }
    const color = ROUTE_COLORS[routeIndex % ROUTE_COLORS.length];
    const fullOpacity = state.selectedRoutes.has(routeIndex);
    const baseOpacity = fullOpacity ? (routeMode === "straight_line" ? 0.78 : 0.88) : state.routeView.fadedOpacity;
    const rawSegments = Array.isArray(routeLine.segments) && routeLine.segments.length > 0
      ? routeLine.segments
      : [routeLine.coordinates];
    rawSegments.forEach((segment, segmentIndex) => {
      const isDepotLeg = segmentIndex === 0 || segmentIndex === rawSegments.length - 1;
      if (isDepotLeg && state.routeView.depotLegMode === "absent") {
        return;
      }
      const opacity = isDepotLeg && state.routeView.depotLegMode === "faded"
        ? Math.min(baseOpacity, state.routeView.fadedOpacity)
        : baseOpacity;
      const latlngs = segment
        .filter((point) => Array.isArray(point) && point.length >= 2)
        .map((point) => [Number(point[1]), Number(point[0])]);
      if (latlngs.length < 2) {
        return;
      }
      const polyline = L.polyline(latlngs, {
        renderer: routeCanvasRenderer,
        color,
        weight: fullOpacity ? 4 : 3,
        opacity,
        lineCap: "round",
        lineJoin: "round",
      }).addTo(state.layers.route);
      polyline.bindPopup(`Route #${routeIndex + 1}<br/>Stops: ${routes[routeIndex]?.length ?? "?"}`);
      if (state.routeView.arrowsEnabled) {
        addArrowsToPolyline(polyline, color);
      }
    });

    const legendItem = document.createElement("li");
    legendItem.style.opacity = fullOpacity ? "1" : String(Math.max(0.35, state.routeView.fadedOpacity));
    legendItem.innerHTML = `<span class="swatch" style="background:${color}"></span><span>Route #${routeIndex + 1}: ${routes[routeIndex]?.length ?? 0} stops, load ${routeLoad(routes[routeIndex] || [], instanceData)} (${fullOpacity ? "full" : "faded"}, ${escapeHtml(routeMode)})</span>`;
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
  const catalogQueryKeys = {
    problem: "problem",
    family: "family",
    metric: "metric",
    city: "city",
    size: "size",
    method: "method",
    scenario: "scenario",
    search: "q",
    sort: "sort",
  };
  Object.entries(catalogQueryKeys).forEach(([stateKey, queryKey]) => {
    const value = state.benchmarkCatalog.filters[stateKey];
    if (value && !(stateKey === "sort" && value === "city-size")) nextParams.set(queryKey, value);
    else nextParams.delete(queryKey);
  });
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

  if (!benchmark.meta || !Array.isArray(benchmark.routes) || benchmark.routes.length === 0) {
    return;
  }

  const metric = ["shortest", "fastest", "euclidean"].includes(String(benchmark.payload?.summary?.metric_variant || "").toLowerCase())
    ? String(benchmark.payload.summary.metric_variant).toLowerCase()
    : "shortest";
  if (benchmark.meta?.road_cache?.[metric]) {
    const straightFallbackCount = Array.isArray(benchmark.meta.route_geometry_straight_fallback_paths)
      ? benchmark.meta.route_geometry_straight_fallback_paths.length
      : 0;
    benchmark.renderSummary = {
      metric,
      route_count: benchmark.routes.length,
      render_mode: straightFallbackCount > 0 ? "mixed" : "cached_road",
      used_cache: true,
      cache_miss_count: 0,
      straight_fallback_count: straightFallbackCount,
      cache_persisted: false,
    };
  } else {
    // No precomputed geometry in the published snapshot: the public
    // workbench draws straight lines. Road-following rendering for new
    // data lives in the local MAMUT-routing-tools workbench.
    benchmark.renderSummary = {
      metric,
      route_count: benchmark.routes.length,
      render_mode: "straight_line",
      used_cache: false,
      cache_miss_count: 0,
      straight_fallback_count: 0,
      cache_persisted: false,
    };
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
    const instanceData = projectEnuInstanceCoordinates(
      await fetchJson(artifactHref(payload.artifact_links.vrp_json_path)),
    );
    const objectiveEntries = Array.isArray(payload.bks_entries) ? payload.bks_entries : [];
    const objectiveEntry = objectiveEntries.find((entry) => entry.objective_function === preferredObjective)
      || objectiveEntries[0]
      || null;
    const bksData = objectiveEntry ? await fetchJson(artifactHref(objectiveEntry.artifact_path)) : { routes: [] };
    let meta = null;
    try {
      const [geometryMeta, routeGeometryMeta] = await Promise.all([
        fetchGeometryMetaMemo(payload.artifact_links),
        fetchRouteGeometryMetaMemo(objectiveEntry),
      ]);
      if (geometryMeta || routeGeometryMeta) {
        meta = {
          ...(geometryMeta || {}),
          ...(routeGeometryMeta || {}),
          road_cache: {
            ...(geometryMeta?.road_cache || {}),
            ...(routeGeometryMeta?.road_cache || {}),
          },
        };
      }
    } catch (error) {
      console.warn("Unable to load benchmark geometry sidecar", error);
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
    resetRouteViewDefaults(state.benchmark.routes);
    updateBenchmarkContextUi();
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

benchmarkProblemSelect.addEventListener("change", async (event) => {
  state.benchmarkCatalog.filters.problem = event.target.value || "";
  state.benchmarkCatalog.filters.family = "";
  ["metric", "city", "size", "method", "scenario"].forEach((key) => { state.benchmarkCatalog.filters[key] = ""; });
  state.benchmarkCatalog.selectedGroupKey = null;
  await loadBenchmarkInstance(null, null, { quiet: true, fitMap: false });
  renderBenchmarkCatalogOptions();
  syncWorkbenchUrl();
});

const benchmarkCascadeControls = [
  [benchmarkMetricFilter, "metric"],
  [benchmarkCityFilter, "city"],
  [benchmarkSizeFilter, "size"],
  [benchmarkMethodFilter, "method"],
  [benchmarkScenarioFilter, "scenario"],
];
benchmarkCascadeControls.forEach(([control, key], controlIndex) => {
  control.addEventListener("change", (event) => {
    state.benchmarkCatalog.filters[key] = event.target.value || "";
    benchmarkCascadeControls.slice(controlIndex + 1).forEach(([, laterKey]) => { state.benchmarkCatalog.filters[laterKey] = ""; });
    renderBenchmarkCatalogOptions();
    syncWorkbenchUrl();
  });
});
benchmarkSortSelect.addEventListener("change", (event) => {
  state.benchmarkCatalog.filters.sort = event.target.value || "city-size";
  renderBenchmarkCatalogOptions();
  syncWorkbenchUrl();
});

benchmarkSearchFilter.addEventListener("change", (event) => {
  state.benchmarkCatalog.filters.search = event.target.value;
  renderBenchmarkCatalogOptions();
  syncWorkbenchUrl();
});

benchmarkCatalogSelect.addEventListener("change", async (event) => {
  state.benchmarkCatalog.selectedGroupKey = event.target.value || null;
  const selectedGroupItem = state.benchmarkCatalog.options.find((item) => benchmarkCatalogGroupKey(item) === state.benchmarkCatalog.selectedGroupKey);
  state.benchmarkCatalog.filters.family = benchmarkCatalogLocator(selectedGroupItem).benchmark_name || "";
  ["metric", "city", "size", "method", "scenario"].forEach((key) => { state.benchmarkCatalog.filters[key] = ""; });
  const activeItem = state.instanceRoute
    ? state.benchmarkCatalog.options.find((item) => normalizeRoute(item.route_path) === normalizeRoute(state.instanceRoute))
    : null;
  if (!activeItem || benchmarkCatalogGroupKey(activeItem) !== state.benchmarkCatalog.selectedGroupKey) {
    await loadBenchmarkInstance(null, null, { quiet: true, fitMap: false });
  } else {
    renderBenchmarkCatalogOptions();
  }
  setActiveTab("visualize");
  syncWorkbenchUrl();
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
    resetRouteViewDefaults(state.upload.routes);
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
    resetRouteViewDefaults(state.upload.routes);
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

clearBtn.addEventListener("click", async () => {
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
  map.setView([48.8566, 2.3522], 11);
  showToast("Cleared current map layers");
});

setupThemeToggle();
browseBenchmarksBtn.href = routeHref("/benchmarks/");
updateVisualModePanels();
updateBenchmarkContextUi();
const benchmarkCatalogPromise = loadBenchmarkCatalogOptions();
await loadBenchmarkInstance(state.instanceRoute, state.objectiveFunction, { quiet: true });
await benchmarkCatalogPromise;
await setSourceKind(state.sourceKind, { sync: false });
setActiveTab(state.activeTab, { sync: false });
renderVisualState();
