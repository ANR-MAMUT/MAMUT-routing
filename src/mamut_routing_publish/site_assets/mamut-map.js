"use strict";

/* Shared MapLibre map kit, loaded as a classic script by both frontends: the public
   workbench and the local MAMUT-routing-tools GUI. Like nocturne.js the file is
   byte-identical in both repositories (tests/test_shared_frontend_assets.py in the
   MAMUT-routing repo checks the two copies match), so it is wrapped in a function:
   the tools GUI is a classic script with top-level declarations of its own, and a
   shared top-level `function starPoints` would silently replace one of them.

   Everything a solution draws -- routes, direction arrows, customers, the depot --
   lives in three GeoJSON sources whose data changes only when a new solution or
   render mode is loaded. Focus, fading, hiding and colours are feature-state, which
   MapLibre applies without re-tiling: a slider tick on a 4000-customer solution costs
   a few milliseconds instead of a full redraw. Changing a data-driven paint value or
   a filter would instead re-process the whole source in the worker, so the layer
   expressions below never change after they are added. */
(function (global) {
  const DEG = Math.PI / 180;
  const EARTH_RADIUS_M = 6371008.8;
  /* One arrow bitmap per palette slot: icon-image is a layout property, so the
     colour has to be baked into the image rather than set through feature-state. */
  const ROUTE_SLOTS = 20;
  const APP_LAYER_PREFIX = "mamut-";

  const OSM_TILE_URL = "https://tile.openstreetmap.org/{z}/{x}/{y}.png";
  const OSM_ATTRIBUTION = '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors';
  const CARTO_ATTRIBUTION = `${OSM_ATTRIBUTION} &copy; <a href="https://carto.com/attributions">CARTO</a>`;
  const BASEMAPS = [
    { id: "positron", label: "Positron", carto: "positron-gl-style" },
    { id: "dark-matter", label: "Dark Matter", carto: "dark-matter-gl-style" },
    { id: "osm", label: "OpenStreetMap", carto: null },
  ];

  /* ── Pure helpers (no DOM; loaded by the node tests through vm) ─────────────── */

  function cartoStyleUrl(styleName, key) {
    return `https://basemaps.cartocdn.com/gl/${styleName}/style.json?key=${encodeURIComponent(key)}`;
  }

  function withBasemapKey(url, key) {
    // MapLibre transformRequest: every request to a CARTO basemap host carries
    // the key (sprite, glyphs, tiles.json, tiles), not only the style document.
    if (!key) return { url };
    let parsed;
    try {
      parsed = new URL(url);
    } catch {
      return { url };
    }
    const host = parsed.hostname;
    const isCarto = host === "basemaps.cartocdn.com" || host.endsWith(".basemaps.cartocdn.com");
    if (!isCarto || parsed.searchParams.has("key")) return { url };
    parsed.searchParams.set("key", key);
    return { url: parsed.toString() };
  }

  /* OpenStreetMap raster tiles as a MapLibre style. It carries no glyphs, so no app
     layer may use text-field: symbols here are icon-only. */
  function osmRasterStyle() {
    return {
      version: 8,
      sources: {
        "basemap-osm": { type: "raster", tiles: [OSM_TILE_URL], tileSize: 256, maxzoom: 19, attribution: OSM_ATTRIBUTION },
      },
      layers: [{ id: "basemap-osm", type: "raster", source: "basemap-osm" }],
    };
  }

  function availableBasemaps(apiKey) {
    return BASEMAPS.filter((basemap) => basemap.carto === null || Boolean(apiKey));
  }

  /* The theme picks the matching CARTO style; without a key both themes fall back to
     OpenStreetMap. */
  function themedBasemapId(dark, apiKey) {
    if (!apiKey) return "osm";
    return dark ? "dark-matter" : "positron";
  }

  function clamp01(value) {
    return Math.max(0, Math.min(1, Number(value) || 0));
  }

  /* Opacity and width of one route feature: a port of the Leaflet drawRoutes rules.
     `leg` is "body" or "depot" (the first and last arc, which only exist as their own
     feature when the route has per-arc segments). */
  function routeFeatureStyle(routeIndex, leg, view) {
    const visible = view.visibleRoutes;
    if (!visible || !visible.has(routeIndex)) return { o: 0, w: 3 };
    const focusedRoute = view.focusedRoute;
    const hasFocus = Number.isInteger(focusedRoute) && visible.has(focusedRoute);
    const focused = hasFocus && focusedRoute === routeIndex;
    const width = focused ? 5 : 3;
    const straight = view.routeMode === "straight_line";
    let opacity;
    if (hasFocus && !focused) {
      opacity = Number(view.fadedOpacity) || 0;
    } else if (straight) {
      opacity = 0.78;
    } else {
      opacity = view.roadOpacity ?? 0.88;
    }
    if (opacity <= 0) return { o: 0, w: width };
    if (leg === "depot" && straight) {
      opacity = Math.min(opacity, clamp01(view.depotLegOpacity));
    }
    return { o: Math.max(0, opacity), w: width };
  }

  function usablePoint(point) {
    return Array.isArray(point) && point.length >= 2 && Number.isFinite(Number(point[0])) && Number.isFinite(Number(point[1]));
  }

  function routeSegments(routeLine) {
    const segments = Array.isArray(routeLine.segments) && routeLine.segments.length > 0
      ? routeLine.segments
      : [routeLine.coordinates || []];
    return segments.map((segment) => (Array.isArray(segment) ? segment.filter(usablePoint) : []));
  }

  /* Concatenate arcs into one line, dropping the joint point a following arc repeats. */
  function mergeSegments(segments) {
    const merged = [];
    for (const segment of segments) {
      for (let index = 0; index < segment.length; index += 1) {
        if (index === 0 && merged.length > 0) {
          const last = merged[merged.length - 1];
          if (last[0] === segment[0][0] && last[1] === segment[0][1]) continue;
        }
        merged.push(segment[index]);
      }
    }
    return merged;
  }

  /* At most two features per route: the body (interior arcs, id 2r) and the depot legs
     (first and last arc as one MultiLineString, id 2r+1). A route without per-arc
     segments is a single body feature, as a merged polyline has no isolable legs. */
  function buildRouteFeatures(routeLines) {
    const features = [];
    for (const routeLine of routeLines) {
      const routeIndex = Number(routeLine.routeIndex);
      if (!Number.isInteger(routeIndex) || routeIndex < 0) continue;
      const segments = routeSegments(routeLine);
      const properties = (leg) => ({ r: routeIndex, leg, slot: routeIndex % ROUTE_SLOTS });
      if (segments.length > 1) {
        const body = mergeSegments(segments.slice(1, -1));
        if (body.length >= 2) {
          features.push({ type: "Feature", id: 2 * routeIndex, properties: properties("body"), geometry: { type: "LineString", coordinates: body } });
        }
        const legs = [segments[0], segments[segments.length - 1]].filter((segment) => segment.length >= 2);
        if (legs.length > 0) {
          features.push({ type: "Feature", id: 2 * routeIndex + 1, properties: properties("depot"), geometry: { type: "MultiLineString", coordinates: legs } });
        }
      } else if (segments[0] && segments[0].length >= 2) {
        features.push({ type: "Feature", id: 2 * routeIndex, properties: properties("body"), geometry: { type: "LineString", coordinates: segments[0] } });
      }
    }
    return features;
  }

  function haversineMeters(a, b) {
    const dLat = (b[1] - a[1]) * DEG;
    const dLon = (b[0] - a[0]) * DEG;
    const s = Math.sin(dLat / 2) ** 2 + Math.cos(a[1] * DEG) * Math.cos(b[1] * DEG) * Math.sin(dLon / 2) ** 2;
    return 2 * EARTH_RADIUS_M * Math.asin(Math.min(1, Math.sqrt(s)));
  }

  /* Douglas–Peucker run once at `minTolerance`, recording for every kept point the
     largest tolerance at which it would still be kept: its own split distance, capped
     by its ancestors' (a split point under a dropped range is dropped with it). A later
     threshold on that rank reproduces Douglas–Peucker at any tolerance >= minTolerance
     exactly, so thinning a solution to a point budget needs one pass, not one per
     candidate tolerance. Distances are metres in a local equirectangular frame.
     Endpoints rank Infinity and always survive. */
  function rankLine(points, minTolerance) {
    const count = points.length;
    if (count <= 2) {
      return { points: points.slice(), ranks: points.map(() => Infinity) };
    }
    const kx = DEG * EARTH_RADIUS_M * Math.cos(points[0][1] * DEG);
    const ky = DEG * EARTH_RADIUS_M;
    const xs = new Float64Array(count);
    const ys = new Float64Array(count);
    for (let index = 0; index < count; index += 1) {
      xs[index] = points[index][0] * kx;
      ys[index] = points[index][1] * ky;
    }
    const rank = new Float64Array(count);
    rank[0] = Infinity;
    rank[count - 1] = Infinity;
    const minSquared = minTolerance * minTolerance;
    // Flat (start, end, inherited rank) triples: a 5 M-point solution would allocate
    // millions of small arrays otherwise.
    const stack = [0, count - 1, Infinity];
    while (stack.length > 0) {
      const inherited = stack.pop();
      const end = stack.pop();
      const start = stack.pop();
      const dx = xs[end] - xs[start];
      const dy = ys[end] - ys[start];
      const lengthSquared = dx * dx + dy * dy;
      let best = -1;
      let bestSquared = minSquared;
      for (let index = start + 1; index < end; index += 1) {
        let px = xs[index] - xs[start];
        let py = ys[index] - ys[start];
        if (lengthSquared > 0) {
          const t = Math.max(0, Math.min(1, (px * dx + py * dy) / lengthSquared));
          px -= t * dx;
          py -= t * dy;
        }
        const distanceSquared = px * px + py * py;
        if (distanceSquared > bestSquared) {
          bestSquared = distanceSquared;
          best = index;
        }
      }
      if (best >= 0) {
        const ownRank = Math.min(Math.sqrt(bestSquared), inherited);
        rank[best] = ownRank;
        stack.push(start, best, ownRank, best, end, ownRank);
      }
    }
    const kept = [];
    const ranks = [];
    for (let index = 0; index < count; index += 1) {
      if (rank[index] > 0) {
        kept.push(points[index]);
        ranks.push(rank[index]);
      }
    }
    return { points: kept, ranks };
  }

  function rankRouteLines(routeLines, options = {}) {
    const minTolerance = options.minTolerance ?? 0.5;
    let pointCount = 0;
    const routes = routeLines.map((routeLine) => {
      const segments = routeSegments(routeLine).map((segment) => {
        const ranked = rankLine(segment, minTolerance);
        pointCount += ranked.points.length;
        return ranked;
      });
      return { line: routeLine, segments };
    });
    return { minTolerance, pointCount, routes };
  }

  const THINNING_TOLERANCES_M = [1, 2, 5, 10, 20, 40, 80, 160, 320, 640, 1280];

  /* Route lines thinned to at most `budget` points where possible: the smallest
     tolerance from the ladder that fits, never below the ranking tolerance. */
  function thinRouteLines(ranked, budget) {
    let tolerance = ranked.minTolerance;
    if (ranked.pointCount > budget) {
      const counts = new Array(THINNING_TOLERANCES_M.length).fill(0);
      for (const route of ranked.routes) {
        for (const segment of route.segments) {
          for (const value of segment.ranks) {
            for (let level = 0; level < THINNING_TOLERANCES_M.length && value > THINNING_TOLERANCES_M[level]; level += 1) {
              counts[level] += 1;
            }
          }
        }
      }
      const level = counts.findIndex((count) => count <= budget);
      tolerance = Math.max(ranked.minTolerance, THINNING_TOLERANCES_M[level === -1 ? THINNING_TOLERANCES_M.length - 1 : level]);
    }
    let pointCount = 0;
    const routeLines = ranked.routes.map(({ line, segments }) => {
      const thinned = segments.map(({ points, ranks }) => {
        const kept = [];
        for (let index = 0; index < points.length; index += 1) {
          if (ranks[index] > tolerance) kept.push(points[index]);
        }
        pointCount += kept.length;
        return kept;
      });
      return { ...line, segments: thinned, coordinates: mergeSegments(thinned) };
    });
    return { tolerance, pointCount, routeLines };
  }

  /* [[minLon, minLat], [maxLon, maxLat]] over several point lists, or null. A loop,
     not a spread into Math.min: an argument list is capped by the engine. */
  function boundsOf(...pointLists) {
    let minX = Infinity;
    let minY = Infinity;
    let maxX = -Infinity;
    let maxY = -Infinity;
    for (const points of pointLists) {
      if (!Array.isArray(points)) continue;
      for (const point of points) {
        if (!usablePoint(point)) continue;
        const x = Number(point[0]);
        const y = Number(point[1]);
        if (x < minX) minX = x;
        if (x > maxX) maxX = x;
        if (y < minY) minY = y;
        if (y > maxY) maxY = y;
      }
    }
    return Number.isFinite(minX) ? [[minX, minY], [maxX, maxY]] : null;
  }

  /* fitBounds padding that keeps the fitted area clear of the floating panels. Each
     panel rect covers the left or right side of the map depending on its centre;
     the padding never leaves less than `minVisible` pixels in the middle. */
  function panelPadding(mapRect, panelRects, base = 24, minVisible = 160) {
    const padding = { top: base, bottom: base, left: base, right: base };
    for (const rect of panelRects) {
      if (!rect || rect.width <= 0 || rect.height <= 0) continue;
      const centre = rect.left + rect.width / 2;
      if (centre < mapRect.left + mapRect.width / 2) {
        padding.left = Math.max(padding.left, rect.right - mapRect.left + base);
      } else {
        padding.right = Math.max(padding.right, mapRect.right - rect.left + base);
      }
    }
    const room = mapRect.width - padding.left - padding.right;
    if (room < minVisible) {
      const scale = Math.max(0, mapRect.width - minVisible) / Math.max(1, padding.left + padding.right);
      padding.left = Math.floor(padding.left * scale);
      padding.right = Math.floor(padding.right * scale);
    }
    return padding;
  }

  /* ── Browser-only parts ────────────────────────────────────────────────────── */

  function webglAvailable() {
    try {
      const canvas = document.createElement("canvas");
      return Boolean(window.WebGLRenderingContext && (canvas.getContext("webgl2") || canvas.getContext("webgl")));
    } catch {
      return false;
    }
  }

  const IMAGE_PIXEL_RATIO = 2;

  function canvasImage(size, draw) {
    const canvas = document.createElement("canvas");
    canvas.width = size;
    canvas.height = size;
    const context = canvas.getContext("2d");
    draw(context, size);
    return context.getImageData(0, 0, size, size);
  }

  /* Pointing east: with symbol-placement "line" an icon's x axis follows the line. */
  function arrowImage(color, outline) {
    return canvasImage(22, (context) => {
      context.beginPath();
      context.moveTo(19, 11);
      context.lineTo(5, 3.5);
      context.lineTo(8, 11);
      context.lineTo(5, 18.5);
      context.closePath();
      context.lineJoin = "round";
      context.lineWidth = 2;
      context.strokeStyle = outline;
      context.stroke();
      context.fillStyle = color;
      context.fill();
    });
  }

  /* Five-pointed star, first point up: the depot marker, distinguishable from the
     customer dots. */
  function starImage(color, outline) {
    return canvasImage(52, (context, size) => {
      const centre = size / 2;
      const outer = size / 2 - 3;
      context.beginPath();
      for (let index = 0; index < 10; index += 1) {
        const radius = index % 2 === 0 ? outer : outer * 0.42;
        const angle = -Math.PI / 2 + (index * Math.PI) / 5;
        const x = centre + radius * Math.cos(angle);
        const y = centre + radius * Math.sin(angle);
        if (index === 0) context.moveTo(x, y);
        else context.lineTo(x, y);
      }
      context.closePath();
      context.globalAlpha = 0.95;
      context.fillStyle = color;
      context.fill();
      context.globalAlpha = 1;
      context.lineJoin = "round";
      context.lineWidth = 2.8;
      context.strokeStyle = outline;
      context.stroke();
    });
  }

  /* Several hover handlers share the canvas cursor; each claims "pointer" for itself
     so one handler finding nothing does not clear another's pointer. */
  const cursorClaims = new WeakMap();
  function claimCursor(map, owner, wanted) {
    let claims = cursorClaims.get(map);
    if (!claims) {
      claims = new Set();
      cursorClaims.set(map, claims);
    }
    if (wanted) claims.add(owner);
    else claims.delete(owner);
    map.getCanvas().style.cursor = claims.size > 0 ? "pointer" : "";
  }

  function emptyCollection() {
    return { type: "FeatureCollection", features: [] };
  }

  /* Basemap switching without map.setStyle: setStyle would diff the whole style,
     app sources included, and deep-copies the multi-megabyte route GeoJSON on every
     theme toggle. Instead the basemap's own layers and sources are replaced in place,
     below the first app layer; app sources, feature-state and images are untouched. */
  class BasemapManager {
    constructor(map, apiKey) {
      this.map = map;
      this.apiKey = apiKey;
      this.current = null;
      this.layerIds = [];
      this.sourceIds = [];
      this.sourceSpecs = {};
      this.listeners = [];
      this.loading = null;
    }

    available() {
      return availableBasemaps(this.apiKey);
    }

    onChange(listener) {
      this.listeners.push(listener);
    }

    async styleFor(id) {
      const basemap = BASEMAPS.find((candidate) => candidate.id === id);
      if (!basemap || basemap.carto === null || !this.apiKey) return osmRasterStyle();
      const response = await fetch(withBasemapKey(cartoStyleUrl(basemap.carto, this.apiKey), this.apiKey).url);
      if (!response.ok) throw new Error(`CARTO style request failed (${response.status})`);
      const style = await response.json();
      // CARTO's free tier requires both CARTO and OpenStreetMap to stay credited.
      Object.values(style.sources || {}).forEach((source) => {
        source.attribution = CARTO_ATTRIBUTION;
      });
      return style;
    }

    set(id) {
      const request = (async () => {
        let style;
        let resolvedId = id;
        try {
          style = await this.styleFor(id);
        } catch (error) {
          console.warn(`Basemap '${id}' is unavailable, using OpenStreetMap tiles.`, error);
          style = osmRasterStyle();
          resolvedId = "osm";
        }
        if (this.loading !== request) return this.current;
        this.apply(style);
        this.current = resolvedId;
        this.listeners.forEach((listener) => listener(resolvedId));
        return resolvedId;
      })();
      this.loading = request;
      return request;
    }

    apply(style) {
      const map = this.map;
      const order = map.getLayersOrder();
      const firstAppLayer = order.find((layerId) => layerId.startsWith(APP_LAYER_PREFIX));
      this.layerIds.forEach((layerId) => {
        if (map.getLayer(layerId)) map.removeLayer(layerId);
      });
      const nextSources = style.sources || {};
      const keptSources = new Set();
      this.sourceIds.forEach((sourceId) => {
        const unchanged = nextSources[sourceId] && JSON.stringify(nextSources[sourceId]) === JSON.stringify(this.sourceSpecs[sourceId]);
        if (unchanged) {
          keptSources.add(sourceId);
        } else if (map.getSource(sourceId)) {
          map.removeSource(sourceId);
        }
      });
      if (style.glyphs) map.setGlyphs(style.glyphs);
      if (style.sprite) map.setSprite(style.sprite);
      Object.entries(nextSources).forEach(([sourceId, spec]) => {
        if (!keptSources.has(sourceId) && !map.getSource(sourceId)) map.addSource(sourceId, spec);
      });
      (style.layers || []).forEach((layer) => map.addLayer(layer, firstAppLayer));
      this.layerIds = (style.layers || []).map((layer) => layer.id);
      this.sourceIds = Object.keys(nextSources);
      this.sourceSpecs = nextSources;
    }
  }

  class BasemapControl {
    constructor(manager) {
      this.manager = manager;
    }

    onAdd() {
      const container = document.createElement("div");
      container.className = "maplibregl-ctrl maplibregl-ctrl-group mamut-basemap-control";
      const label = document.createElement("label");
      const caption = document.createElement("span");
      caption.className = "mamut-basemap-caption";
      caption.textContent = "Basemap";
      const select = document.createElement("select");
      select.setAttribute("aria-label", "Basemap");
      this.manager.available().forEach((basemap) => {
        const option = document.createElement("option");
        option.value = basemap.id;
        option.textContent = basemap.label;
        select.appendChild(option);
      });
      select.addEventListener("change", () => {
        this.userChoice?.(select.value);
        this.manager.set(select.value);
      });
      this.manager.onChange((id) => {
        select.value = id;
      });
      if (this.manager.current) select.value = this.manager.current;
      label.append(caption, select);
      container.appendChild(label);
      this.container = container;
      return container;
    }

    onRemove() {
      this.container?.remove();
    }
  }

  /* Map factory. Returns null when WebGL (or MapLibre itself) is unavailable, so the
     page can say so instead of throwing. The map starts on an empty style and the
     basemap is added through the manager, so every basemap -- the first one included
     -- goes through the same code path. */
  function createMap(container, options = {}) {
    if (!global.maplibregl || !webglAvailable()) return null;
    const apiKey = options.apiKey || "";
    let map;
    try {
      map = new global.maplibregl.Map({
        container,
        style: { version: 8, sources: {}, layers: [] },
        center: options.center || [2.3522, 48.8566],
        zoom: options.zoom ?? 10,
        maxZoom: options.maxZoom ?? 19,
        transformRequest: (url) => withBasemapKey(url, apiKey),
        dragRotate: false,
        pitchWithRotate: false,
        maxPitch: 0,
        boxZoom: options.boxZoom ?? true,
        attributionControl: false,
      });
    } catch (error) {
      console.warn("MapLibre could not create a map.", error);
      return null;
    }
    map.touchZoomRotate.disableRotation();
    map.keyboard.disableRotation();
    map.addControl(new global.maplibregl.NavigationControl({ showCompass: false }), "top-left");
    map.addControl(new global.maplibregl.AttributionControl({ compact: true }), "bottom-right");
    if (options.scale) {
      map.addControl(new global.maplibregl.ScaleControl({ unit: "metric", maxWidth: 120 }), "bottom-left");
    }
    const basemaps = new BasemapManager(map, apiKey);
    const switcher = new BasemapControl(basemaps);
    map.addControl(switcher, "top-right");
    const ready = new Promise((resolve) => {
      map.once("load", resolve);
    });
    if (!apiKey) {
      console.info("CARTO basemaps disabled: no basemap API key was configured, using OpenStreetMap tiles.");
    }
    const initialBasemap = options.initialBasemap || themedBasemapId(Boolean(options.dark), apiKey);
    ready.then(() => basemaps.set(initialBasemap));
    return {
      map,
      basemaps,
      ready,
      // Lets a frontend remember that the user picked a basemap by hand.
      onUserBasemapChoice(callback) {
        switcher.userChoice = callback;
      },
    };
  }

  /* The solution layers: routes, arrows, customers and depot, restyled through
     feature-state only. `options.describe(info)` returns the DOM node a popup shows
     for a picked feature; `options.interaction` is "click" (popups) or "hover"
     (tooltips). */
  function createSolutionLayers(map, options = {}) {
    const nodeRadius = options.nodeRadius ?? 5;
    const depotRadius = options.depotRadius ?? 7;
    const nodeStrokeWidth = options.nodeStrokeWidth ?? 1;
    const depotStrokeWidth = options.depotStrokeWidth ?? 2;
    const nodeFillOpacity = options.nodeFillOpacity ?? 0.85;
    const interaction = options.interaction || "click";
    const ids = {
      routes: "mamut-routes",
      line: "mamut-routes-line",
      arrows: "mamut-routes-arrows",
      nodes: "mamut-nodes",
      nodeCircles: "mamut-nodes-circle",
      depot: "mamut-depot",
      depotCircle: "mamut-depot-circle",
      depotStar: "mamut-depot-star",
    };
    const model = {
      routeFeatures: [],
      nodes: [],
      nodeByIndex: new Map(),
      depot: null,
      routeOpacity: new Map(),
      nodeOpacity: new Map(),
    };
    let installed = false;
    let dataDirty = false;
    let lastView = null;
    let imageKey = null;

    function install() {
      map.addSource(ids.routes, { type: "geojson", data: emptyCollection(), maxzoom: 16 });
      map.addSource(ids.nodes, { type: "geojson", data: emptyCollection() });
      map.addSource(ids.depot, { type: "geojson", data: emptyCollection() });
      map.addLayer({
        id: ids.line,
        type: "line",
        source: ids.routes,
        layout: { "line-cap": "round", "line-join": "round" },
        paint: {
          "line-color": ["to-color", ["coalesce", ["feature-state", "c"], "#888888"]],
          "line-width": ["coalesce", ["feature-state", "w"], 3],
          "line-opacity": ["coalesce", ["feature-state", "o"], 0],
        },
      });
      map.addLayer({
        id: ids.arrows,
        type: "symbol",
        source: ids.routes,
        layout: {
          "symbol-placement": "line",
          "symbol-spacing": ["interpolate", ["linear"], ["zoom"], 8, 70, 16, 160],
          "icon-image": ["concat", "mamut-arrow-", ["to-string", ["get", "slot"]]],
          "icon-rotation-alignment": "map",
          "icon-keep-upright": false,
          "icon-allow-overlap": true,
          "icon-ignore-placement": true,
        },
        paint: { "icon-opacity": ["min", 0.95, ["coalesce", ["feature-state", "o"], 0]] },
      });
      map.addLayer({
        id: ids.nodeCircles,
        type: "circle",
        source: ids.nodes,
        paint: {
          "circle-radius": nodeRadius,
          "circle-color": ["to-color", ["coalesce", ["feature-state", "c"], "#888888"]],
          "circle-opacity": ["*", nodeFillOpacity, ["coalesce", ["feature-state", "o"], 1]],
          "circle-stroke-width": nodeStrokeWidth,
          "circle-stroke-color": ["to-color", ["coalesce", ["feature-state", "c"], "#888888"]],
          "circle-stroke-opacity": ["coalesce", ["feature-state", "o"], 1],
        },
      });
      map.addLayer({
        id: ids.depotCircle,
        type: "circle",
        source: ids.depot,
        paint: {
          "circle-radius": depotRadius,
          "circle-color": ["to-color", ["coalesce", ["feature-state", "c"], "#888888"]],
          "circle-opacity": nodeFillOpacity,
          "circle-stroke-width": depotStrokeWidth,
          "circle-stroke-color": ["to-color", ["coalesce", ["feature-state", "c"], "#888888"]],
        },
      });
      map.addLayer({
        id: ids.depotStar,
        type: "symbol",
        source: ids.depot,
        layout: {
          "icon-image": "mamut-depot-star",
          "icon-allow-overlap": true,
          "icon-ignore-placement": true,
          visibility: "none",
        },
      });
      map.on("styleimagemissing", (event) => {
        if (String(event.id).startsWith(APP_LAYER_PREFIX) && lastView) {
          imageKey = null;
          refreshImages(lastView);
        }
      });
      installed = true;
      if (dataDirty) pushData();
      if (lastView) applyView(lastView);
    }

    function refreshImages(view) {
      const palette = view.palette || [];
      const outline = view.dark ? "rgba(12, 14, 32, 0.85)" : "rgba(255, 255, 255, 0.9)";
      const key = `${palette.join(",")}|${view.depotColor}|${outline}`;
      if (key === imageKey) return;
      imageKey = key;
      const put = (id, image) => {
        if (map.hasImage(id)) map.updateImage(id, image);
        else map.addImage(id, image, { pixelRatio: IMAGE_PIXEL_RATIO });
      };
      for (let slot = 0; slot < ROUTE_SLOTS; slot += 1) {
        put(`mamut-arrow-${slot}`, arrowImage(palette.length ? palette[slot % palette.length] : "#888888", outline));
      }
      put("mamut-depot-star", starImage(view.depotColor || "#888888", outline));
    }

    /* The model is updated at once, so bounds() and pick() are right even before the
       map style has loaded; only the writes to MapLibre wait for install(). */
    function setData(data) {
      const routeLines = Array.isArray(data.routeLines) ? data.routeLines : [];
      model.routeFeatures = buildRouteFeatures(routeLines);
      model.nodes = (data.nodes || []).filter((node) => usablePoint(node.coord));
      model.nodeByIndex = new Map(model.nodes.map((node) => [node.index, node]));
      model.depot = data.depot && usablePoint(data.depot.coord) ? data.depot : null;
      model.routeOpacity.clear();
      model.nodeOpacity.clear();
      dataDirty = true;
      if (installed) pushData();
      if (lastView) applyView(lastView);
    }

    function pushData() {
      dataDirty = false;
      [ids.routes, ids.nodes, ids.depot].forEach((sourceId) => map.removeFeatureState({ source: sourceId }));
      map.getSource(ids.routes).setData({ type: "FeatureCollection", features: model.routeFeatures });
      map.getSource(ids.nodes).setData({
        type: "FeatureCollection",
        features: model.nodes.map((node) => ({
          type: "Feature",
          id: node.index,
          properties: { n: node.index },
          geometry: { type: "Point", coordinates: [Number(node.coord[0]), Number(node.coord[1])] },
        })),
      });
      map.getSource(ids.depot).setData(model.depot
        ? {
          type: "FeatureCollection",
          features: [{ type: "Feature", id: 0, properties: { n: model.depot.index }, geometry: { type: "Point", coordinates: [Number(model.depot.coord[0]), Number(model.depot.coord[1])] } }],
        }
        : emptyCollection());
    }

    function applyView(view) {
      lastView = view;
      const palette = view.palette && view.palette.length ? view.palette : ["#888888"];
      // `dim` steps the static routes back, e.g. while vehicles animate on top.
      const dim = clamp01(view.dim ?? 1);
      const routeStates = model.routeFeatures.map((feature) => {
        const routeIndex = feature.properties.r;
        const style = routeFeatureStyle(routeIndex, feature.properties.leg, view);
        model.routeOpacity.set(feature.id, style.o);
        return [feature.id, { c: palette[routeIndex % palette.length], w: style.w, o: style.o * dim }];
      });
      const customerOpacity = typeof view.customerOpacity === "function" ? view.customerOpacity : () => 1;
      // A string, or a function of the node for frontends that colour unrouted
      // customers by their origin.
      const unassignedColor = typeof view.unassignedColor === "function"
        ? view.unassignedColor
        : () => view.unassignedColor || "#888888";
      const nodeStates = model.nodes.map((node) => {
        const routeIndex = Number.isInteger(node.routeIndex) ? node.routeIndex : undefined;
        const opacity = clamp01(customerOpacity(routeIndex));
        model.nodeOpacity.set(node.index, opacity);
        const color = routeIndex === undefined ? unassignedColor(node) : palette[routeIndex % palette.length];
        return [node.index, { c: color, o: opacity }];
      });
      if (!installed) return;
      refreshImages(view);
      routeStates.forEach(([id, state]) => map.setFeatureState({ source: ids.routes, id }, state));
      nodeStates.forEach(([id, state]) => map.setFeatureState({ source: ids.nodes, id }, state));
      if (model.depot) {
        map.setFeatureState({ source: ids.depot, id: 0 }, { c: view.depotColor || "#888888" });
      }
      map.setLayoutProperty(ids.arrows, "visibility", view.arrowsEnabled ? "visible" : "none");
      map.setLayoutProperty(ids.depotStar, "visibility", view.depotStar ? "visible" : "none");
      map.setLayoutProperty(ids.depotCircle, "visibility", view.depotStar ? "none" : "visible");
    }

    function clear() {
      setData({ routeLines: [], nodes: [], depot: null });
    }

    /* The topmost visible feature near a screen point: depot, then customers, then
       routes. Fully faded features are skipped, as Leaflet skipped drawing them. */
    function pick(point, tolerance = 5) {
      if (!installed) return null;
      const box = [[point.x - tolerance, point.y - tolerance], [point.x + tolerance, point.y + tolerance]];
      const layers = [ids.depotStar, ids.depotCircle, ids.nodeCircles, ids.line].filter((layerId) => map.getLayoutProperty(layerId, "visibility") !== "none");
      const features = map.queryRenderedFeatures(box, { layers });
      const priority = { [ids.depotStar]: 0, [ids.depotCircle]: 0, [ids.nodeCircles]: 1, [ids.line]: 2 };
      features.sort((a, b) => priority[a.layer.id] - priority[b.layer.id]);
      for (const feature of features) {
        if (feature.layer.id === ids.depotStar || feature.layer.id === ids.depotCircle) {
          return { kind: "depot", nodeIndex: model.depot.index, lngLat: model.depot.coord };
        }
        if (feature.layer.id === ids.nodeCircles) {
          if ((model.nodeOpacity.get(feature.id) ?? 1) <= 0) continue;
          const node = model.nodeByIndex.get(feature.id);
          if (node) return { kind: "node", nodeIndex: node.index, routeIndex: node.routeIndex, lngLat: node.coord };
        }
        if (feature.layer.id === ids.line) {
          if ((model.routeOpacity.get(feature.id) ?? 0) <= 0) continue;
          return { kind: "route", routeIndex: feature.properties.r, lngLat: null };
        }
      }
      return null;
    }

    /* closeOnClick stays off: MapLibre would add a close listener each time the popup
       opens, and the one left from the previous opening would close it again right after
       the next feature click reopened it. A click on the empty map closes it below. */
    const popup = new global.maplibregl.Popup({
      closeButton: interaction === "click",
      closeOnClick: false,
      maxWidth: "300px",
      offset: 10,
      className: "mamut-popup",
    });
    let hoverKey = null;
    function showInfo(info, lngLat) {
      const content = info && typeof options.describe === "function" ? options.describe(info) : null;
      if (!content) {
        popup.remove();
        return;
      }
      popup.setLngLat(info.lngLat || lngLat).setDOMContent(content).addTo(map);
    }
    let framePending = false;
    map.on("mousemove", (event) => {
      if (framePending) return;
      framePending = true;
      requestAnimationFrame(() => {
        framePending = false;
        const info = pick(event.point);
        claimCursor(map, ids.routes, Boolean(info));
        if (interaction !== "hover") return;
        const key = info ? `${info.kind}:${info.nodeIndex ?? ""}:${info.routeIndex ?? ""}` : null;
        if (key === hoverKey) {
          if (info && info.kind === "route") popup.setLngLat(event.lngLat);
          return;
        }
        hoverKey = key;
        showInfo(info, event.lngLat);
      });
    });
    map.on("mouseout", () => {
      if (interaction === "hover") {
        hoverKey = null;
        popup.remove();
      }
    });
    if (interaction === "click") {
      map.on("click", (event) => {
        const info = pick(event.point);
        if (info) showInfo(info, event.lngLat);
        else popup.remove();
      });
    }

    /* Bounds of what is drawn: visible customers and the depot, as the Leaflet
       version fitted to its markers. */
    function bounds() {
      const points = model.nodes.filter((node) => (model.nodeOpacity.get(node.index) ?? 1) > 0).map((node) => node.coord);
      if (model.depot) points.push(model.depot.coord);
      return boundsOf(points);
    }

    if (map.loaded() || map.isStyleLoaded()) install();
    else map.once("load", install);

    return { setData, applyView, clear, pick, bounds, popup, layerIds: ids, closePopup: () => popup.remove() };
  }

  /* Text-only tooltips (hover) or popups (click) for a frontend's own layers: the
     topmost feature under the pointer in `layerIds` is handed to `describe`, which
     returns a DOM node or null. */
  function bindLayerTooltip(map, layerIds, describe, options = {}) {
    const interaction = options.interaction || "hover";
    const popup = new global.maplibregl.Popup({
      closeButton: interaction === "click",
      closeOnClick: false, // see createSolutionLayers: closed by the click handler below
      maxWidth: "320px",
      offset: 8,
      className: "mamut-popup",
    });
    const owner = layerIds.join(",");
    const topFeature = (point) => {
      const layers = layerIds.filter((layerId) => map.getLayer(layerId) && map.getLayoutProperty(layerId, "visibility") !== "none");
      if (!layers.length) return null;
      const box = [[point.x - 4, point.y - 4], [point.x + 4, point.y + 4]];
      return map.queryRenderedFeatures(box, { layers })[0] || null;
    };
    let shownId = null;
    map.on("mousemove", (event) => {
      const feature = topFeature(event.point);
      claimCursor(map, owner, Boolean(feature));
      if (interaction !== "hover") return;
      const key = feature ? `${feature.layer.id}:${feature.id}` : null;
      if (key === shownId) return;
      shownId = key;
      const content = feature ? describe(feature) : null;
      if (!content) {
        popup.remove();
        return;
      }
      popup.setLngLat(feature.geometry.type === "Point" ? feature.geometry.coordinates : event.lngLat).setDOMContent(content).addTo(map);
    });
    map.on("mouseout", () => {
      shownId = null;
      if (interaction === "hover") popup.remove();
    });
    if (interaction === "click") {
      map.on("click", (event) => {
        const feature = topFeature(event.point);
        const content = feature ? describe(feature) : null;
        if (content) popup.setLngLat(event.lngLat).setDOMContent(content).addTo(map);
        else popup.remove();
      });
    }
    return { popup, refresh: () => { shownId = null; } };
  }

  /* Fit the map to bounds, clear of the floating panels. */
  function fitToBounds(map, bounds, panelElements = [], options = {}) {
    if (!bounds) return;
    const mapRect = map.getContainer().getBoundingClientRect();
    const rects = panelElements
      .filter((element) => element && element.offsetParent !== null)
      .map((element) => element.getBoundingClientRect());
    const padding = panelPadding(mapRect, rects, options.base ?? 24);
    const [[minX, minY], [maxX, maxY]] = bounds;
    if (minX === maxX && minY === maxY) {
      map.jumpTo({ center: [minX, minY], zoom: Math.min(options.maxZoom ?? 16, 15) });
      return;
    }
    map.fitBounds(bounds, { padding, maxZoom: options.maxZoom ?? 16, duration: options.duration ?? 0 });
  }

  global.MamutMap = {
    ROUTE_SLOTS,
    OSM_ATTRIBUTION,
    CARTO_ATTRIBUTION,
    BASEMAPS,
    availableBasemaps,
    bindLayerTooltip,
    boundsOf,
    buildRouteFeatures,
    cartoStyleUrl,
    createMap,
    createSolutionLayers,
    fitToBounds,
    haversineMeters,
    mergeSegments,
    osmRasterStyle,
    panelPadding,
    rankLine,
    rankRouteLines,
    routeFeatureStyle,
    themedBasemapId,
    thinRouteLines,
    withBasemapKey,
  };
})(typeof window !== "undefined" ? window : globalThis);
