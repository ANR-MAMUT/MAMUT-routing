const body = document.body;
const runtimeParams = new URLSearchParams(window.location.search);
const CANONICAL_WORKBENCH_ROUTE = "/workbench/";
// Leaflet's canvas renderer needs concrete color values, so the twenty route colors
// are resolved from the live theme rather than set in CSS; a theme change redraws.
// They live in nocturne-tokens.css as --route-0…19 and are read through nocturne.js,
// so this file no longer carries its own copy of the palette.

function isDarkTheme() {
  return document.documentElement.dataset.theme === "dark";
}

function routeColor(routeIndex) {
  const palette = window.MamutNocturne.routeColors();
  return palette[routeIndex % palette.length];
}

// Depot / unassigned-customer marker colors mirror the theme tokens (--acc,
// --mut in site.css); canvas markers cannot consume CSS variables directly.
function themeMarkerColors() {
  return isDarkTheme()
    ? { depot: "#9d8bff", unassigned: "#8d92b8" }
    : { depot: "#5b43e8", unassigned: "#6f6f92" };
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

// Leaflet has no star marker, so the depot star is a divIcon holding an inline
// SVG; the outline keeps it readable over dark route lines and road tiles.
function depotStarIcon(color) {
  const size = 26;
  const outline = isDarkTheme() ? "rgba(12, 14, 32, 0.85)" : "rgba(255, 255, 255, 0.9)";
  return L.divIcon({
    className: "depot-star-marker",
    html: `<svg viewBox="0 0 24 24" width="${size}" height="${size}" aria-hidden="true"><polygon points="${starPoints(12, 12, 11)}" fill="${color}" fill-opacity="0.95" stroke="${outline}" stroke-width="1.4" stroke-linejoin="round" /></svg>`,
    iconSize: [size, size],
    iconAnchor: [size / 2, size / 2],
    popupAnchor: [0, -size / 2],
  });
}
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
  catalogCostSortAvailable,
  catalogGeometryValue,
  catalogSortOptions,
  compareCatalogItems,
  escapeHtml,
  fetchGeometryMetaMemo,
  fetchJson,
  fetchRouteGeometryMetaMemo,
  fetchWorkbenchPayloadForRoute,
  normalizeCatalogSort,
  normalizeRoute,
  normalizeSortDirection,
  parseUploadedInstanceText,
  parseUploadedMetaText,
  parseUploadedSolutionText,
  projectEnuInstanceCoordinates,
  resolvePreviewGeometry,
  routeHref,
  setupThemeToggle,
  usesRoadMetric,
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
const benchmarkGeometryFilter = document.getElementById("benchmarkGeometryFilter");
const benchmarkSearchFilter = document.getElementById("benchmarkSearchFilter");
const benchmarkSortSelect = document.getElementById("benchmarkSortSelect");
const benchmarkSortDirection = document.getElementById("benchmarkSortDirection");
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
// The theme picks the matching Carto base by default; OpenStreetMap stays
// available in the layer control. A manual pick is respected until the user
// toggles the theme again.
let activeBaseLayer = isDarkTheme() ? darkMatterBaseLayer : positronBaseLayer;
activeBaseLayer.addTo(map);
map.on("baselayerchange", (event) => {
  activeBaseLayer = event.layer;
});
L.control.layers(
  {
    OpenStreetMap: osmBaseLayer,
    Positron: positronBaseLayer,
    "Dark Matter": darkMatterBaseLayer,
  },
  null,
  { position: "topright", collapsed: true },
).addTo(map);

// Redraw markers/routes (canvas colors are resolved per theme) and swap the
// theme-default base layer when the Nocturne theme toggles.
new MutationObserver(() => {
  const themedDefault = isDarkTheme() ? darkMatterBaseLayer : positronBaseLayer;
  if (activeBaseLayer !== themedDefault && (activeBaseLayer === darkMatterBaseLayer || activeBaseLayer === positronBaseLayer)) {
    map.removeLayer(activeBaseLayer);
    themedDefault.addTo(map);
    activeBaseLayer = themedDefault;
  }
  renderVisualState({ fitMap: false });
}).observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });

const state = {
  activeTab: initialWorkbenchMode === "generate" ? "generate" : "visualize",
  sourceKind: initialWorkbenchMode === "upload" ? "upload" : "benchmark",
  instanceRoute: runtimeParams.get("instance"),
  objectiveFunction: runtimeParams.get("objective"),
  hiddenRoutes: new Set(),
  focusedRoute: null,
  routeView: {
    fadedOpacity: 0.2,
    arrowsEnabled: true,
    depotStar: false,
    depotLegMode: "faded",
    search: "",
    minStops: null,
    maxStops: null,
    minLoad: null,
    maxLoad: null,
    filtersOpen: false,
    appearanceOpen: false,
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
    routeGeometryLoadFailed: false,
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
      geometry: runtimeParams.get("geometry") || "",
      search: runtimeParams.get("q") || "",
      sort: normalizeCatalogSort(runtimeParams.get("sort")),
      direction: normalizeSortDirection(runtimeParams.get("dir")),
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

function populateBenchmarkFilter(select, values, placeholder, currentValue, labels = {}) {
  const counts = new Map();
  values.filter(Boolean).forEach((value) => counts.set(value, (counts.get(value) || 0) + 1));
  const options = Array.from(counts.keys()).sort((left, right) => String(left).localeCompare(String(right), undefined, { numeric: true }));
  select.innerHTML = [`<option value="">${escapeHtml(placeholder)}</option>`, ...options.map((value) => `<option value="${escapeHtml(value)}">${escapeHtml(labels[value] || value)} (${counts.get(value)})</option>`)].join("");
  select.value = options.includes(currentValue) ? currentValue : "";
  return select.value;
}

function compareFilteredBenchmarkItems(left, right) {
  const filters = state.benchmarkCatalog.filters;
  return compareCatalogItems(left, right, filters.sort, filters.direction) || compareBenchmarkCatalogInstances(left, right);
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
  const scenarioItems = methodItems.filter((item) => !filters.scenario || benchmarkScenarioValue(item) === filters.scenario);
  filters.geometry = populateBenchmarkFilter(
    benchmarkGeometryFilter,
    scenarioItems.map(catalogGeometryValue),
    "All geometry",
    filters.geometry,
    { road: "Road geometry", straight: "Straight-line" },
  );
  benchmarkSearchFilter.value = filters.search;
  const search = filters.search.trim().toLowerCase();
  const selectedGroupItems = rawGroupItems.filter((item) => {
    const locator = benchmarkCatalogLocator(item);
    if (filters.metric && locator.metric_variant !== filters.metric) return false;
    if (filters.city && locator.place_slug !== filters.city) return false;
    if (filters.size && String(benchmarkCatalogCustomerCount(item)) !== filters.size) return false;
    if (filters.method && item.sampling_method !== filters.method) return false;
    if (filters.scenario && benchmarkScenarioValue(item) !== filters.scenario) return false;
    if (filters.geometry && catalogGeometryValue(item) !== filters.geometry) return false;
    if (search && !`${item.display_name || ""} ${item.base_instance || ""} ${locator.instance_identifier || ""}`.toLowerCase().includes(search)) return false;
    return true;
  });
  if (filters.sort === "cost" && !catalogCostSortAvailable(selectedGroupItems)) filters.sort = "catalog";
  benchmarkSortSelect.innerHTML = catalogSortOptions(selectedGroupItems)
    .map((option) => `<option value="${option.value}"${option.value === filters.sort ? " selected" : ""}${option.disabled ? " disabled" : ""}>${escapeHtml(option.label)}</option>`)
    .join("");
  const descending = filters.direction === "desc";
  benchmarkSortDirection.querySelector("span").textContent = descending ? "↓" : "↑";
  benchmarkSortDirection.title = descending ? "Descending" : "Ascending";
  benchmarkSortDirection.setAttribute("aria-label", `Sort direction: ${descending ? "descending" : "ascending"}. Activate for ${descending ? "ascending" : "descending"}.`);
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

function resetRouteViewDefaults(routes, summary = null) {
  const routeCount = Array.isArray(routes) ? routes.length : 0;
  state.hiddenRoutes.clear();
  state.focusedRoute = null;
  state.routeView.fadedOpacity = 0.2;
  state.routeView.arrowsEnabled = routeCount <= 10;
  // A solution overlay defaults to the star depot; a bare instance keeps the dot.
  state.routeView.depotStar = routeCount > 0;
  // Road metrics draw depot legs along real streets, so they belong in the
  // picture; Euclidean and historical instances draw them as long chords.
  state.routeView.depotLegMode = usesRoadMetric(summary) ? "full" : "faded";
  state.routeView.search = "";
  state.routeView.minStops = null;
  state.routeView.maxStops = null;
  state.routeView.minLoad = null;
  state.routeView.maxLoad = null;
  state.routeView.filtersOpen = false;
  state.routeView.appearanceOpen = false;
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
  return new Set(filtered.filter((index) => !state.hiddenRoutes.has(index)));
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

let routeFilterRenderTimer = null;

function routeRangeInvalid(minKey, maxKey) {
  const min = state.routeView[minKey];
  const max = state.routeView[maxKey];
  return min !== null && max !== null && min > max;
}

function scheduleRouteViewRender(focusSelector) {
  window.clearTimeout(routeFilterRenderTimer);
  const active = routeSelectorContainer.querySelector(focusSelector);
  const selectionStart = typeof active?.selectionStart === "number" ? active.selectionStart : null;
  routeFilterRenderTimer = window.setTimeout(() => {
    renderVisualState({ fitMap: false });
    window.requestAnimationFrame(() => {
      const next = routeSelectorContainer.querySelector(focusSelector);
      next?.focus({ preventScroll: true });
      if (selectionStart !== null && typeof next?.setSelectionRange === "function") {
        next.setSelectionRange(selectionStart, selectionStart);
      }
    });
  }, 120);
}

function routeVisibilityIcon(hidden) {
  return `<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M2.5 12s3.5-6 9.5-6 9.5 6 9.5 6-3.5 6-9.5 6-9.5-6-9.5-6z"/><circle cx="12" cy="12" r="2.5"/>${hidden ? '<path class="eye-slash" d="M4 4l16 16"/>' : ""}</svg>`;
}

function buildRouteSelector(routes, instanceData) {
  if (!Array.isArray(routes) || routes.length === 0) {
    routeSelectorCard.hidden = true;
    routeSelectorContainer.innerHTML = "";
    return;
  }

  routeSelectorCard.hidden = false;
  const filtered = filteredRouteIndices(routes, instanceData);
  const visible = visibleRouteIndices(routes, instanceData);
  if (state.focusedRoute !== null && !visible.has(state.focusedRoute)) state.focusedRoute = null;
  const stopsInvalid = routeRangeInvalid("minStops", "maxStops");
  const loadInvalid = routeRangeInvalid("minLoad", "maxLoad");
  const filterError = stopsInvalid || loadInvalid;
  const routeRows = filtered.map((index) => {
    const route = routes[index];
    const hidden = state.hiddenRoutes.has(index);
    const focused = state.focusedRoute === index;
    const routeNumber = index + 1;
    return `<div class="route-list-row${hidden ? " route-hidden" : ""}${focused ? " route-focused" : ""}" role="listitem">
      <button type="button" class="route-eye-button" data-route-visibility="${index}" aria-pressed="${hidden ? "false" : "true"}" aria-label="${hidden ? "Show" : "Hide"} route ${routeNumber}" title="${hidden ? "Show" : "Hide"} route ${routeNumber}">${routeVisibilityIcon(hidden)}</button>
      <button type="button" class="route-focus-button" data-route-focus="${index}" aria-pressed="${focused ? "true" : "false"}" aria-label="${focused ? "Clear focus from" : "Focus"} route ${routeNumber}">
        <span class="swatch" style="background:${routeColor(index)}"></span>
        <span class="route-list-name">Route #${routeNumber}</span>
        <span class="route-list-meta">${route.length} stops · load ${routeLoad(route, instanceData)}</span>
      </button>
    </div>`;
  }).join("");

  routeSelectorContainer.innerHTML = `
    <div class="route-view-header">
      <p class="route-view-summary" aria-live="polite">${visible.size} visible · ${filtered.length} matching · ${routes.length} total</p>
      <div class="route-view-actions">
        <button type="button" data-route-action="show">Show all</button>
        <button type="button" data-route-action="hide">Hide all</button>
        <button type="button" data-route-action="reset">Reset routes</button>
      </div>
    </div>
    <label class="field route-search-field"><span>Find route</span><input class="route-view-search" type="search" value="${escapeHtml(state.routeView.search)}" placeholder="Route number" /></label>
    <div class="route-page-list" role="list">${routeRows || '<div class="empty-state">No routes match these filters.</div>'}</div>
    <details class="route-options" data-route-disclosure="filters"${state.routeView.filtersOpen ? " open" : ""}>
      <summary>Filters${filterError ? ' <span class="route-filter-warning">Check ranges</span>' : ""}</summary>
      <div class="route-view-grid route-filter-grid">
        <label class="field"><span>Min stops</span><input data-route-filter="minStops" type="number" min="0" value="${state.routeView.minStops ?? ""}"${stopsInvalid ? ' aria-invalid="true"' : ""} /></label>
        <label class="field"><span>Max stops</span><input data-route-filter="maxStops" type="number" min="0" value="${state.routeView.maxStops ?? ""}"${stopsInvalid ? ' aria-invalid="true"' : ""} /></label>
        <label class="field"><span>Min load</span><input data-route-filter="minLoad" type="number" min="0" value="${state.routeView.minLoad ?? ""}"${loadInvalid ? ' aria-invalid="true"' : ""} /></label>
        <label class="field"><span>Max load</span><input data-route-filter="maxLoad" type="number" min="0" value="${state.routeView.maxLoad ?? ""}"${loadInvalid ? ' aria-invalid="true"' : ""} /></label>
      </div>
    </details>
    <details class="route-options" data-route-disclosure="appearance"${state.routeView.appearanceOpen ? " open" : ""}>
      <summary>Appearance</summary>
      <div class="route-view-grid">
        <label class="field route-opacity-field"><span>Other routes${state.focusedRoute === null ? " (focus a route)" : ""}: <output class="route-view-opacity-value">${Math.round(state.routeView.fadedOpacity * 100)}%</output></span><input class="route-view-opacity" type="range" min="0" max="0.8" step="0.05" value="${state.routeView.fadedOpacity}"${state.focusedRoute === null ? " disabled" : ""} /></label>
        <label class="field"><span>Depot legs</span><select class="route-view-depot"><option value="full">Full</option><option value="faded">Faded</option><option value="hidden">Hidden</option></select></label>
        <label class="route-view-toggle"><input class="route-view-arrows" type="checkbox"${state.routeView.arrowsEnabled ? " checked" : ""} /> Direction arrows</label>
        <label class="route-view-toggle"><input class="route-view-depot-star" type="checkbox"${state.routeView.depotStar ? " checked" : ""} /> Depot as star</label>
      </div>
    </details>`;

  routeSelectorContainer.querySelector(".route-view-depot").value = state.routeView.depotLegMode;
  routeSelectorContainer.querySelector(".route-view-search").addEventListener("input", (event) => {
    state.routeView.search = event.target.value;
    scheduleRouteViewRender(".route-view-search");
  });
  routeSelectorContainer.querySelectorAll("[data-route-filter]").forEach((input) => {
    input.addEventListener("input", () => {
      const raw = input.value.trim();
      state.routeView[input.dataset.routeFilter] = raw === "" ? null : Math.max(0, Number(raw));
      scheduleRouteViewRender(`[data-route-filter="${input.dataset.routeFilter}"]`);
    });
  });
  routeSelectorContainer.querySelectorAll("[data-route-disclosure]").forEach((details) => {
    details.addEventListener("toggle", () => {
      state.routeView[details.dataset.routeDisclosure === "filters" ? "filtersOpen" : "appearanceOpen"] = details.open;
    });
  });
  routeSelectorContainer.querySelectorAll("[data-route-action]").forEach((button) => {
    button.addEventListener("click", () => {
      if (button.dataset.routeAction === "show") filtered.forEach((index) => state.hiddenRoutes.delete(index));
      if (button.dataset.routeAction === "hide") filtered.forEach((index) => state.hiddenRoutes.add(index));
      if (button.dataset.routeAction === "reset") {
        state.hiddenRoutes.clear();
        state.focusedRoute = null;
        state.routeView.search = "";
        state.routeView.minStops = state.routeView.maxStops = state.routeView.minLoad = state.routeView.maxLoad = null;
      }
      if (state.focusedRoute !== null && state.hiddenRoutes.has(state.focusedRoute)) state.focusedRoute = null;
      renderVisualState({ fitMap: false });
    });
  });
  routeSelectorContainer.querySelectorAll("[data-route-visibility]").forEach((button) => {
    button.addEventListener("click", () => {
      const index = Number(button.dataset.routeVisibility);
      if (state.hiddenRoutes.has(index)) state.hiddenRoutes.delete(index);
      else state.hiddenRoutes.add(index);
      if (state.focusedRoute === index && state.hiddenRoutes.has(index)) state.focusedRoute = null;
      renderVisualState({ fitMap: false });
    });
  });
  routeSelectorContainer.querySelectorAll("[data-route-focus]").forEach((button) => {
    button.addEventListener("click", () => {
      const index = Number(button.dataset.routeFocus);
      state.hiddenRoutes.delete(index);
      state.focusedRoute = state.focusedRoute === index ? null : index;
      renderVisualState({ fitMap: false });
    });
  });
  routeSelectorContainer.querySelector(".route-view-opacity").addEventListener("input", (event) => {
    state.routeView.fadedOpacity = Number(event.target.value);
    routeSelectorContainer.querySelector(".route-view-opacity-value").textContent = `${Math.round(state.routeView.fadedOpacity * 100)}%`;
    redrawRoutesOnly();
  });
  routeSelectorContainer.querySelector(".route-view-depot").addEventListener("change", (event) => {
    state.routeView.depotLegMode = event.target.value;
    redrawRoutesOnly();
  });
  routeSelectorContainer.querySelector(".route-view-arrows").addEventListener("change", (event) => {
    state.routeView.arrowsEnabled = event.target.checked;
    redrawRoutesOnly();
  });
  routeSelectorContainer.querySelector(".route-view-depot-star").addEventListener("change", (event) => {
    state.routeView.depotStar = event.target.checked;
    renderVisualState({ fitMap: false });
  });
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

function addArrowsToPolyline(polyline, color, opacity = 0.95) {
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
      html: `<div style="transform: rotate(${bearing - 90}deg); transform-origin: 50% 50%; font-size: 10px; line-height: 10px; color: ${color}; font-weight: 700; opacity: ${Math.min(0.95, opacity).toFixed(3)};">▶</div>`,
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
  // Loop rather than Math.min(...ids): the spread form takes an argument list,
  // which the engine caps, and this array grows with the instance.
  let smallestNodeId = Number.POSITIVE_INFINITY;
  for (let index = 0; index < instanceNodeIds.length; index += 1) {
    if (instanceNodeIds[index] < smallestNodeId) smallestNodeId = instanceNodeIds[index];
  }
  const offset = smallestNodeId === 0 ? 0 : 1;

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
  const usablePoint = (point) => Array.isArray(point) && point.length >= 2;
  return {
    nodeCoordinates,
    routeLines: visual.routes.map((route, routeIndex) => {
      const sequence = [Number(visual.instanceData.depot || 0), ...route, Number(visual.instanceData.depot || 0)];
      const points = sequence.map((nodeIndex) => nodeCoordinates[nodeIndex]);
      return {
        routeIndex,
        coordinates: points.filter(usablePoint),
        // Per-arc segments so the depot-leg modes can address the first and
        // last hop, matching what resolvePreviewGeometry builds for benchmarks.
        segments: sequence.slice(0, -1).map((_, edgeIndex) => [points[edgeIndex], points[edgeIndex + 1]].filter(usablePoint)),
        source: "straight_line",
      };
    }),
    routeMode: "straight_line",
  };
}

function drawCustomers(nodeCoordinates, routes, instanceData, options = {}) {
  const bounds = [];
  const markerColors = themeMarkerColors();
  const customerToRoute = new Map();
  routes.forEach((route, routeIndex) => {
    const color = routeColor(routeIndex);
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
    const color = isDepot ? markerColors.depot : customerToRoute.get(index) || markerColors.unassigned;
    const marker = isDepot && state.routeView.depotStar
      ? L.marker([lat, lon], { icon: depotStarIcon(color), interactive: true, keyboard: false })
      : L.circleMarker([lat, lon], {
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
  const visible = visibleRouteIndices(routes, instanceData);
  const hasFocus = state.focusedRoute !== null && visible.has(state.focusedRoute);
  routeLines.forEach((routeLine) => {
    const routeIndex = routeLine.routeIndex;
    if (!visible.has(routeIndex)) {
      return;
    }
    const color = routeColor(routeIndex);
    const focused = hasFocus && state.focusedRoute === routeIndex;
    const baseOpacity = hasFocus && !focused ? state.routeView.fadedOpacity : (routeMode === "straight_line" ? 0.78 : 0.88);
    if (baseOpacity <= 0) {
      // Faded all the way out: skip the route entirely so it leaves behind
      // neither arrows nor an invisible canvas hit target.
      return;
    }
    const rawSegments = Array.isArray(routeLine.segments) && routeLine.segments.length > 0
      ? routeLine.segments
      : [routeLine.coordinates];
    // A single merged polyline has no isolable depot legs; only a real per-arc
    // segment list lets us single out the first and last hop.
    const hasSeparableLegs = rawSegments.length > 1;
    rawSegments.forEach((segment, segmentIndex) => {
      const isDepotLeg = hasSeparableLegs && (segmentIndex === 0 || segmentIndex === rawSegments.length - 1);
      if (isDepotLeg && state.routeView.depotLegMode === "hidden") {
        return;
      }
      const opacity = isDepotLeg && state.routeView.depotLegMode === "faded"
        ? Math.min(baseOpacity, 0.25)
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
        weight: focused ? 5 : 3,
        opacity,
        lineCap: "round",
        lineJoin: "round",
      }).addTo(state.layers.route);
      polyline.bindPopup(`Route #${routeIndex + 1}<br/>Stops: ${routes[routeIndex]?.length ?? "?"}`);
      if (state.routeView.arrowsEnabled) {
        addArrowsToPolyline(polyline, color, opacity);
      }
    });
  });
}

function redrawRoutesOnly() {
  const visual = currentVisualState();
  const geometry = buildVisualGeometry();
  if (!visual.instanceData || !geometry) return;
  state.layers.route.clearLayers();
  state.layers.arrow.clearLayers();
  drawRoutes(geometry.routeLines, visual.routes, visual.instanceData, geometry.routeMode);
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
    routeSelectorContainer.innerHTML = "";
    routeSelectorCard.hidden = true;
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
    geometry: "geometry",
    search: "q",
    sort: "sort",
    direction: "dir",
  };
  Object.entries(catalogQueryKeys).forEach(([stateKey, queryKey]) => {
    const value = state.benchmarkCatalog.filters[stateKey];
    const isDefault = (stateKey === "sort" && value === "catalog") || (stateKey === "direction" && value === "asc");
    if (value && !isDefault) nextParams.set(queryKey, value);
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
  document.querySelectorAll("[data-rail-target]").forEach((button) => {
    button.classList.toggle("rail-active", button.dataset.railTarget === tab);
  });
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
    benchmarkRenderStatus.textContent = "Historical benchmark families use straight-line rendering. Generated OSM collections use published road geometry when available.";
    openBenchmarkBtn.href = browseBenchmarksBtn.href;
    return;
  }

  const payload = state.benchmark.payload;
  const objectiveEntries = Array.isArray(payload.bks_entries) ? payload.bks_entries : [];
  const renderSummary = state.benchmark.renderSummary;
  let renderStatus = null;
  if (renderSummary?.render_mode === "cached_road") {
    renderStatus = `Road geometry: published ${renderSummary.metric} paths.`;
  } else if (renderSummary?.render_mode === "mixed") {
    const suffix = renderSummary.straight_fallback_count === 1 ? "segment falls" : "segments fall";
    renderStatus = `Road geometry: published ${renderSummary.metric} paths. ${renderSummary.straight_fallback_count} ${suffix} back to straight lines.`;
  } else if (renderSummary?.fallback_reason === "historical_default") {
    renderStatus = "Straight-line rendering is the default for historical benchmark families.";
  } else if (renderSummary?.fallback_reason === "euclidean_metric") {
    renderStatus = "Straight-line rendering matches the Euclidean metric for this instance.";
  } else if (renderSummary?.fallback_reason === "sidecar_unavailable") {
    renderStatus = "Published road geometry is unavailable for this BKS. Showing straight-line routes.";
  } else if (payload.summary?.has_geometry_sidecar) {
    renderStatus = "Published road geometry is missing for this BKS. Showing straight-line routes.";
  } else {
    renderStatus = "Straight-line rendering is the default for historical benchmark families.";
  }
  objectiveField.hidden = objectiveEntries.length === 0;
  benchmarkObjectiveSelect.innerHTML = objectiveEntries
    .map((entry) => `<option value="${escapeHtml(entry.objective_function)}"${entry.objective_function === state.objectiveFunction ? " selected" : ""}>${escapeHtml(entry.objective_function)}</option>`)
    .join("");
  benchmarkStatus.textContent = `${payload.title} · ${payload.summary.problem_type} · ${payload.summary.benchmark_name} · ${payload.summary.num_customers} customers`;
  benchmarkRenderStatus.textContent = renderStatus;
  openBenchmarkBtn.href = routeHref(payload.route_path);
}

async function autoRenderBenchmarkRoadGeometry(options = {}) {
  const benchmark = state.benchmark;
  benchmark.roadGeojson = null;
  benchmark.renderSummary = null;

  if (!Array.isArray(benchmark.routes) || benchmark.routes.length === 0) {
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
      // Whether a family can render road-following routes is a property of its
      // artifacts -- does it ship a geo sidecar -- not of its name. Keying on
      // "Poryos2026" labelled every other generated OSM collection as historical.
      fallback_reason: !benchmark.payload?.summary?.has_geometry_sidecar
        ? "historical_default"
        : metric === "euclidean"
          ? "euclidean_metric"
          : benchmark.routeGeometryLoadFailed || benchmark.objectiveEntry?.route_geometry_path
            ? "sidecar_unavailable"
            : "sidecar_missing",
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
      routeGeometryLoadFailed: false,
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
    const [geometryResult, routeGeometryResult] = await Promise.allSettled([
      fetchGeometryMetaMemo(payload.artifact_links),
      fetchRouteGeometryMetaMemo(objectiveEntry),
    ]);
    if (geometryResult.status === "rejected") {
      console.warn("Unable to load benchmark coordinate sidecar", geometryResult.reason);
    }
    if (routeGeometryResult.status === "rejected") {
      console.warn("Unable to load benchmark route-geometry sidecar", routeGeometryResult.reason);
    }
    const geometryMeta = geometryResult.status === "fulfilled" ? geometryResult.value : null;
    const routeGeometryMeta = routeGeometryResult.status === "fulfilled" ? routeGeometryResult.value : null;
    let meta = null;
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
      routeGeometryLoadFailed: routeGeometryResult.status === "rejected",
    };
    const fitMap = options.fitMap !== undefined
      ? options.fitMap
      : !previousRoute || normalizeRoute(previousRoute) !== normalizeRoute(payload.route_path);
    if (fitMap) {
      requestVisualFit();
    }
    resetRouteViewDefaults(state.benchmark.routes, payload.summary);
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

/* ── Resizable layout (shared with the local tools GUI via layout.js) ── */
const layout = window.MamutLayout.initLayout({
  stage: document.documentElement,
  storageKey: window.MamutLayout.STORAGE_KEY,
  /* Matches the --wb-left-panel-width in workbench.css: this panel's filter grid
     needs more room than the local GUI's form. */
  defaults: { leftWidth: 320 },
  onResize: refreshMapSize,
});

document.documentElement.addEventListener("layout:rail-select", (event) => {
  const target = event.detail.target;
  if (target === "visualize" || target === "generate") {
    setActiveTab(target);
  }
});

document.addEventListener("keydown", (event) => {
  if (event.metaKey || event.ctrlKey || event.altKey) return;
  const target = event.target;
  if (target instanceof Element && target.closest("input, select, textarea, [contenteditable]")) return;
  if (event.key === "[") layout.toggleCollapsed("left");
  else if (event.key === "]") layout.toggleCollapsed("right");
  else return;
  event.preventDefault();
});
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
  ["metric", "city", "size", "method", "scenario", "geometry"].forEach((key) => { state.benchmarkCatalog.filters[key] = ""; });
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
  [benchmarkGeometryFilter, "geometry"],
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
  state.benchmarkCatalog.filters.sort = normalizeCatalogSort(event.target.value);
  renderBenchmarkCatalogOptions();
  syncWorkbenchUrl();
});

benchmarkSortDirection.addEventListener("click", () => {
  state.benchmarkCatalog.filters.direction = state.benchmarkCatalog.filters.direction === "asc" ? "desc" : "asc";
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
  ["metric", "city", "size", "method", "scenario", "geometry"].forEach((key) => { state.benchmarkCatalog.filters[key] = ""; });
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
  routeSelectorContainer.innerHTML = "";
  statsEl.innerHTML = "";
  routeSelectorCard.hidden = true;
  state.hiddenRoutes.clear();
  state.focusedRoute = null;
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
syncWorkbenchUrl();
renderVisualState();
