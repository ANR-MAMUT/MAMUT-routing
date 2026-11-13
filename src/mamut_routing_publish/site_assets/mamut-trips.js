"use strict";

/* Route animation shared by both frontends (the public workbench and the local
   MAMUT-routing-tools GUI): vehicles driving a solution's routes on the MapLibre map,
   drawn by deck.gl's TripsLayer. Byte-identical in both repositories, wrapped in a
   function for the same reason as mamut-map.js.

   Timing comes from a per-stop timeline -- the checker's schedule for VRPTW, the
   free-flow fastest matrix for CVRP, the checker-derived td_schedules for TD -- or,
   when an instance publishes none, from a constant speed. Inside an arc only the
   departure and the arrival are known, so the position in between is interpolated by
   distance along the drawn road path.

   deck.gl (~2 MB) is loaded on demand, the first time an animation is opened. */
(function (global) {
  const DEG = Math.PI / 180;
  const EARTH_RADIUS_M = 6371008.8;
  /* 25 km/h: a plausible urban delivery speed for instances with no travel times. */
  const SCHEMATIC_SPEED_MPS = 25 / 3.6;
  /* A dwelling vehicle repeats its stop point; the copy is nudged by this much
     (~1 cm) so the path never has a zero-length segment, which TripsLayer cannot
     orient. */
  const DWELL_NUDGE_DEG = 1e-7;
  const SPEED_STEPS = [1, 2, 5, 10, 20, 30, 60, 120, 300, 600, 1200, 1800, 3600];

  const CLOCK_LABELS = {
    checker: "Checker schedule: free-flow travel, waiting for windows, service times",
    free_flow_fastest: "Free-flow travel times (fastest metric); no service times",
    td_schedule: "Time-dependent schedule: each route leaves at its optimal departure",
    schematic: "Constant speed (25 km/h): no travel times are published for this instance",
  };

  /* ── Pure helpers (no DOM; loaded by the node tests through vm) ─────────────── */

  function haversineMeters(a, b) {
    const dLat = (b[1] - a[1]) * DEG;
    const dLon = (b[0] - a[0]) * DEG;
    const s = Math.sin(dLat / 2) ** 2 + Math.cos(a[1] * DEG) * Math.cos(b[1] * DEG) * Math.sin(dLon / 2) ** 2;
    return 2 * EARTH_RADIUS_M * Math.asin(Math.min(1, Math.sqrt(s)));
  }

  /* The checker-derived TD schedules of an instance page, in the common shape. */
  function timelineFromTdSchedules(tdSchedules) {
    if (!Array.isArray(tdSchedules) || tdSchedules.length === 0) return null;
    return {
      clock: "td_schedule",
      time_unit: "s",
      routes: tdSchedules.map((schedule) => ({
        departure: Number(schedule.departure_time),
        return_arrival: Number(schedule.return_arrival),
        stops: (schedule.stops || []).map((stop) => [Number(stop.node), Number(stop.arrival), Number(stop.service_start), Number(stop.departure)]),
      })),
    };
  }

  function usablePoint(point) {
    return Array.isArray(point) && point.length >= 2 && Number.isFinite(Number(point[0])) && Number.isFinite(Number(point[1]));
  }

  function arcSegments(routeLine) {
    const segments = Array.isArray(routeLine.segments) && routeLine.segments.length > 0
      ? routeLine.segments
      : [routeLine.coordinates || []];
    return segments.map((segment) => (Array.isArray(segment) ? segment.filter(usablePoint).map((point) => [Number(point[0]), Number(point[1])]) : []));
  }

  function segmentLength(points) {
    let length = 0;
    for (let index = 1; index < points.length; index += 1) length += haversineMeters(points[index - 1], points[index]);
    return length;
  }

  /* A timeline route fits a drawn route when it has one stop per customer arc and,
     when the drawn route knows its node sequence, the same customers in order. */
  function timelineFits(timelineRoute, routeLine, arcCount) {
    if (!timelineRoute || !Array.isArray(timelineRoute.stops) || timelineRoute.stops.length + 1 !== arcCount) return false;
    const sequence = Array.isArray(routeLine.sequence) ? routeLine.sequence : null;
    if (!sequence) return true;
    return timelineRoute.stops.every((stop, index) => Number(stop[0]) === Number(sequence[index + 1]));
  }

  /* Constant-speed schedule for a drawn route: no waiting, no service. */
  function schematicRoute(segments, routeLine, speed) {
    let time = 0;
    const stops = [];
    segments.forEach((segment, arc) => {
      time += segmentLength(segment) / speed;
      if (arc < segments.length - 1) {
        const node = Array.isArray(routeLine.sequence) ? Number(routeLine.sequence[arc + 1]) : arc + 1;
        stops.push([node, time, time, time]);
      }
    });
    return { departure: 0, return_arrival: time, stops };
  }

  /* Vehicle trips for deck.gl's TripsLayer: per route, the drawn path and one
     timestamp per vertex. Arc k runs from the previous departure to this stop's
     arrival; inside it, time is proportional to the distance travelled. A stop's
     waiting and service time is a repeated (nudged) point. Timestamps are relative
     to the earliest departure: deck stores them as 32-bit floats, which hold
     seconds of a day but not milliseconds since 1970. */
  function buildTrips(routeLines, timeline, options = {}) {
    const speed = options.schematicSpeed ?? SCHEMATIC_SPEED_MPS;
    const timelineRoutes = timeline && Array.isArray(timeline.routes) ? timeline.routes : [];
    let fallbackRoutes = 0;
    const raw = [];
    for (const routeLine of routeLines) {
      const routeIndex = Number(routeLine.routeIndex);
      const segments = arcSegments(routeLine);
      if (!Number.isInteger(routeIndex) || segments.every((segment) => segment.length === 0)) continue;
      let route = timelineRoutes[routeIndex];
      if (!timelineFits(route, routeLine, segments.length)) {
        route = schematicRoute(segments, routeLine, speed);
        fallbackRoutes += 1;
      }
      raw.push({ routeIndex, segments, route });
    }
    let origin = Infinity;
    raw.forEach(({ route }) => {
      if (Number(route.departure) < origin) origin = Number(route.departure);
    });
    if (!Number.isFinite(origin)) origin = 0;

    const trips = [];
    const visits = [];
    let span = 0;
    for (const { routeIndex, segments, route } of raw) {
      const path = [];
      const timestamps = [];
      const stops = route.stops;
      const push = (point, time) => {
        path.push(point);
        timestamps.push(time - origin);
      };
      segments.forEach((segment, arc) => {
        const leave = arc === 0 ? Number(route.departure) : Number(stops[arc - 1][3]);
        const reach = arc < stops.length ? Number(stops[arc][1]) : Number(route.return_arrival);
        if (segment.length === 0) return;
        const total = segmentLength(segment);
        let travelled = 0;
        segment.forEach((point, index) => {
          if (index > 0) travelled += haversineMeters(segment[index - 1], point);
          const time = total > 0 ? leave + ((reach - leave) * travelled) / total : (index === segment.length - 1 ? reach : leave);
          if (path.length > 0 && index === 0) {
            const last = path[path.length - 1];
            const lastTime = timestamps[timestamps.length - 1] + origin;
            if (last[0] === point[0] && last[1] === point[1]) {
              // The joint with the previous arc: dwell there until this arc leaves.
              if (time > lastTime) push([point[0] + DWELL_NUDGE_DEG, point[1]], time);
              return;
            }
          }
          // Monotone even with rounding in the source timeline.
          push(point, Math.max(time, timestamps.length ? timestamps[timestamps.length - 1] + origin : time));
        });
        if (arc < stops.length) {
          const endPoint = segment[segment.length - 1];
          visits.push({ node: Number(stops[arc][0]), r: routeIndex, coord: endPoint, serviceStart: Number(stops[arc][2]) - origin });
        }
      });
      if (path.length >= 2) {
        trips.push({ r: routeIndex, path, timestamps, departure: timestamps[0], arrival: timestamps[timestamps.length - 1] });
        if (timestamps[timestamps.length - 1] > span) span = timestamps[timestamps.length - 1];
      }
    }
    visits.sort((a, b) => a.serviceStart - b.serviceStart);
    let clock = timeline?.clock || "schematic";
    if (fallbackRoutes > 0 && fallbackRoutes === raw.length) clock = "schematic";
    return { origin, span, clock, fallbackRoutes, trips, visits, serviceTimes: visits.map((visit) => visit.serviceStart) };
  }

  /* Position of a trip at time t (relative seconds), or null while the vehicle is
     not on its route (before departure, after return). */
  function positionAt(trip, t) {
    const times = trip.timestamps;
    if (t < times[0] || t > times[times.length - 1]) return null;
    let low = 0;
    let high = times.length - 1;
    while (high - low > 1) {
      const middle = (low + high) >> 1;
      if (times[middle] <= t) low = middle;
      else high = middle;
    }
    const a = trip.path[low];
    const b = trip.path[high];
    const fraction = times[high] === times[low] ? 1 : (t - times[low]) / (times[high] - times[low]);
    return [a[0] + (b[0] - a[0]) * fraction, a[1] + (b[1] - a[1]) * fraction];
  }

  /* Customers whose service has started by t: a binary search on sorted times. */
  function servedCountAt(serviceTimes, t) {
    let low = 0;
    let high = serviceTimes.length;
    while (low < high) {
      const middle = (low + high) >> 1;
      if (serviceTimes[middle] <= t) low = middle + 1;
      else high = middle;
    }
    return low;
  }

  /* HH:MM:SS of an absolute time in seconds, with a day marker past midnight. */
  function formatClock(seconds) {
    const total = Math.max(0, Math.floor(Number(seconds) || 0));
    const days = Math.floor(total / 86400);
    const rest = total % 86400;
    const pad = (value) => String(value).padStart(2, "0");
    const text = `${pad(Math.floor(rest / 3600))}:${pad(Math.floor((rest % 3600) / 60))}:${pad(rest % 60)}`;
    return days > 0 ? `${text} +${days}d` : text;
  }

  /* Simulated seconds per real second so the whole span plays in about a minute. */
  function defaultSpeed(span, seconds = 60) {
    const wanted = Math.max(1, span / seconds);
    return SPEED_STEPS.find((step) => step >= wanted) || SPEED_STEPS[SPEED_STEPS.length - 1];
  }

  function hexToRgb(color) {
    const value = String(color || "").trim();
    const short = /^#([0-9a-f]{3})$/i.exec(value);
    const long = /^#([0-9a-f]{6})$/i.exec(value);
    const hex = short ? short[1].split("").map((c) => c + c).join("") : long ? long[1] : "888888";
    const number = parseInt(hex, 16);
    return [(number >> 16) & 255, (number >> 8) & 255, number & 255];
  }

  /* ── Browser-only parts ────────────────────────────────────────────────────── */

  let deckPromise = null;

  function loadDeck(src) {
    if (global.deck && global.deck.TripsLayer) return Promise.resolve(global.deck);
    if (!deckPromise) {
      deckPromise = new Promise((resolve, reject) => {
        const script = document.createElement("script");
        script.src = src;
        script.async = true;
        script.onload = () => {
          const deck = global.deck;
          const missing = ["TripsLayer", "ScatterplotLayer", "MapLibreOverlay", "DataFilterExtension"].filter((name) => !deck || !deck[name]);
          if (missing.length) reject(new Error(`deck.gl is missing ${missing.join(", ")}`));
          else resolve(deck);
        };
        script.onerror = () => reject(new Error("deck.gl could not be loaded"));
        document.head.appendChild(script);
      });
      deckPromise.catch(() => {
        deckPromise = null;
      });
    }
    return deckPromise;
  }

  /* Probed once: every probe is a WebGL context, and browsers cap live contexts (about
     16) and drop the oldest -- possibly the map's own -- when a page opens too many. */
  let webgl2 = null;

  function webgl2Available() {
    if (webgl2 === null) {
      try {
        const gl = document.createElement("canvas").getContext("webgl2");
        webgl2 = Boolean(gl);
        gl?.getExtension("WEBGL_lose_context")?.loseContext();
      } catch {
        webgl2 = false;
      }
    }
    return webgl2;
  }

  /* deck.gl's MapLibreOverlay as a control we own. Its onRemove finalizes deck but leaves
     its container in the controls corner and its WebGL context alive, so each animation
     leaked one of each; and from that corner its canvas painted over popups and the map's
     buttons. Its container goes right above the map canvas instead (still below markers,
     popups and controls), and removal releases the context and the container. */
  function mountOverlay(map, overlay) {
    const placeholder = document.createElement("div");
    placeholder.hidden = true;
    let container = null;
    const control = {
      onAdd(target) {
        container = overlay.onAdd(target);
        const canvas = target.getCanvas();
        canvas.parentNode.insertBefore(container, canvas.nextSibling);
        return placeholder;
      },
      onRemove(target) {
        const canvases = container ? [...container.querySelectorAll("canvas")] : [];
        overlay.onRemove(target);
        canvases.forEach((canvas) => {
          canvas.getContext("webgl2")?.getExtension("WEBGL_lose_context")?.loseContext();
          canvas.width = 0;
          canvas.height = 0;
        });
        container?.remove();
        placeholder.remove();
        container = null;
      },
      getDefaultPosition: () => "top-left",
    };
    map.addControl(control);
    return control;
  }

  function element(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  }

  /* The playback bar: play/pause, speed, scrubber, clock, served counter, the
     origin of the times, close. All text goes through textContent. */
  function buildBar(host, handlers) {
    host.replaceChildren();
    host.hidden = false;
    const bar = element("div", "trips-bar");
    bar.setAttribute("role", "group");
    bar.setAttribute("aria-label", "Route animation");
    const play = element("button", "trips-play", "Play");
    play.type = "button";
    const speedLabel = element("label", "trips-speed");
    const speedCaption = element("span", "trips-caption", "Speed");
    const speed = element("select");
    speed.setAttribute("aria-label", "Simulated seconds per second");
    SPEED_STEPS.forEach((step) => {
      const option = element("option", null, `×${step}`);
      option.value = String(step);
      speed.appendChild(option);
    });
    speedLabel.append(speedCaption, speed);
    const scrub = element("input", "trips-scrub");
    scrub.type = "range";
    scrub.min = "0";
    scrub.step = "any";
    scrub.setAttribute("aria-label", "Time");
    const clock = element("span", "trips-clock", "00:00:00");
    clock.setAttribute("aria-live", "off");
    const served = element("span", "trips-served", "");
    const close = element("button", "trips-close", "×");
    close.type = "button";
    close.setAttribute("aria-label", "Close the animation");
    close.title = "Close the animation";
    const note = element("p", "trips-note", "");
    const controls = element("div", "trips-controls");
    controls.append(play, speedLabel, scrub, clock, served, close);
    bar.append(controls, note);
    host.appendChild(bar);
    play.addEventListener("click", handlers.togglePlay);
    speed.addEventListener("change", () => handlers.setSpeed(Number(speed.value)));
    scrub.addEventListener("input", () => handlers.seek(Number(scrub.value)));
    // While the thumb is held, playback must not move it out from under the pointer. The release
    // can happen anywhere on the page, so it is listened for on the window.
    // Only one of pointerup / pointercancel ends a drag: both listeners go together, or the
    // other would stay on the window and keep this animation's data alive after it is closed.
    let endScrub = null;
    scrub.addEventListener("pointerdown", () => {
      endScrub?.();
      const release = () => {
        global.removeEventListener("pointerup", release);
        global.removeEventListener("pointercancel", release);
        endScrub = null;
        handlers.scrubbing(false);
      };
      endScrub = release;
      handlers.scrubbing(true);
      global.addEventListener("pointerup", release);
      global.addEventListener("pointercancel", release);
    });
    scrub.addEventListener("change", () => handlers.scrubbing(false));
    close.addEventListener("click", handlers.close);
    return { play, speed, scrub, clock, served, note, detach: () => endScrub?.() };
  }

  /* Without WebGL2: a note in the bar's place, closed like an animation (its × button, or
     the frontend's close when the instance or the solution changes). It is not one, though:
     `unavailable` tells the frontend not to dim the routes or show "Stop animation". */
  function unavailableNotice(host, options) {
    let open = true;
    const close = () => {
      if (!open) return;
      open = false;
      host.replaceChildren();
      host.hidden = true;
    };
    const bar = element("div", "trips-bar");
    const controls = element("div", "trips-controls");
    const note = element("p", "trips-note", "The route animation needs WebGL2, which this browser does not provide.");
    const dismiss = element("button", "trips-close", "×");
    dismiss.type = "button";
    dismiss.setAttribute("aria-label", "Close");
    dismiss.addEventListener("click", () => {
      close();
      options.onClose?.();
    });
    controls.append(note, dismiss);
    bar.append(controls);
    host.replaceChildren(bar);
    host.hidden = false;
    return { setView() {}, close, playing: false, data: null, unavailable: true };
  }

  /* Opens an animation on `map` with its playback bar in `host`.
     options: { deckSrc, routeLines, timeline, palette, visibleRoutes, focusedRoute,
                onClose, autoplay, clockLabels }
     clockLabels: the frontend's wording for a clock when it knows better than the
     defaults (why a TD BKS runs at constant speed, a clock borrowed from a sibling). */
  async function openAnimation(map, host, options) {
    if (!webgl2Available()) return unavailableNotice(host, options);
    const deck = await loadDeck(options.deckSrc);
    const data = buildTrips(options.routeLines, options.timeline, options);
    const overlay = new deck.MapLibreOverlay({ interleaved: false, layers: [] });
    const control = mountOverlay(map, overlay);
    const filterTrips = new deck.DataFilterExtension({ filterSize: 1 });
    const filterVisits = new deck.DataFilterExtension({ filterSize: 2 });
    const state = {
      t: 0,
      speed: defaultSpeed(data.span),
      playing: false,
      lastFrame: null,
      lastText: 0,
      scrubbing: false,
      frame: null,
      visibility: new Map(),
      visibilityVersion: 0,
      colors: new Map(),
      colorVersion: 0,
      focusedRoute: null,
      disposed: false,
      // Service starts of the visible routes' customers, sorted: what the counter counts.
      shownServiceTimes: data.serviceTimes,
    };
    const trail = Math.max(60, data.span / 40);

    function setView(view) {
      const palette = view.palette && view.palette.length ? view.palette : ["#888888"];
      const hasFocus = Number.isInteger(view.focusedRoute) && view.visibleRoutes?.has(view.focusedRoute);
      data.trips.forEach((trip) => {
        const visible = !view.visibleRoutes || view.visibleRoutes.has(trip.r);
        state.visibility.set(trip.r, visible ? 1 : 0);
        const rgb = hexToRgb(palette[trip.r % palette.length]);
        const alpha = hasFocus && view.focusedRoute !== trip.r ? 70 : 255;
        state.colors.set(trip.r, [...rgb, alpha]);
      });
      state.visibilityVersion += 1;
      state.colorVersion += 1;
      state.shownServiceTimes = data.visits.filter((visit) => state.visibility.get(visit.r) !== 0).map((visit) => visit.serviceStart);
      render();
    }

    function layers() {
      const t = state.t;
      const heads = [];
      for (const trip of data.trips) {
        if (!state.visibility.get(trip.r)) continue;
        const position = positionAt(trip, t);
        if (position) heads.push({ position, color: state.colors.get(trip.r) });
      }
      return [
        new deck.ScatterplotLayer({
          id: "mamut-trips-pending",
          data: data.visits,
          getPosition: (visit) => visit.coord,
          getFillColor: [150, 150, 165, 230],
          getLineColor: [255, 255, 255, 200],
          stroked: true,
          lineWidthMinPixels: 1,
          radiusMinPixels: 5,
          radiusMaxPixels: 5,
          extensions: [filterVisits],
          getFilterValue: (visit) => [visit.serviceStart, state.visibility.get(visit.r) ?? 1],
          filterRange: [[t, 1e12], [1, 1]],
          updateTriggers: { getFilterValue: state.visibilityVersion },
        }),
        new deck.ScatterplotLayer({
          id: "mamut-trips-served",
          data: data.visits,
          getPosition: (visit) => visit.coord,
          getFillColor: (visit) => state.colors.get(visit.r) || [136, 136, 136, 255],
          getLineColor: [255, 255, 255, 230],
          stroked: true,
          lineWidthMinPixels: 1.5,
          radiusMinPixels: 5.5,
          radiusMaxPixels: 5.5,
          extensions: [filterVisits],
          getFilterValue: (visit) => [visit.serviceStart, state.visibility.get(visit.r) ?? 1],
          filterRange: [[-1e12, t], [1, 1]],
          updateTriggers: { getFillColor: state.colorVersion, getFilterValue: state.visibilityVersion },
        }),
        new deck.TripsLayer({
          id: "mamut-trips",
          data: data.trips,
          getPath: (trip) => trip.path,
          getTimestamps: (trip) => trip.timestamps,
          getColor: (trip) => state.colors.get(trip.r) || [136, 136, 136, 255],
          widthMinPixels: 4,
          capRounded: true,
          jointRounded: true,
          fadeTrail: true,
          trailLength: trail,
          currentTime: t,
          extensions: [filterTrips],
          getFilterValue: (trip) => state.visibility.get(trip.r) ?? 1,
          filterRange: [1, 1],
          updateTriggers: { getColor: state.colorVersion, getFilterValue: state.visibilityVersion },
        }),
        new deck.ScatterplotLayer({
          id: "mamut-trips-vehicles",
          data: heads,
          getPosition: (head) => head.position,
          getFillColor: (head) => head.color,
          getLineColor: [255, 255, 255, 255],
          stroked: true,
          lineWidthMinPixels: 2,
          radiusMinPixels: 6,
          radiusMaxPixels: 6,
        }),
      ];
    }

    function updateText(force = false) {
      const now = performance.now();
      if (!force && now - state.lastText < 100) return;
      state.lastText = now;
      const absolute = data.origin + state.t;
      ui.clock.textContent = formatClock(absolute);
      if (!state.scrubbing) ui.scrub.value = String(state.t);
      ui.scrub.setAttribute("aria-valuetext", formatClock(absolute));
      const shown = state.shownServiceTimes;
      ui.served.textContent = `${servedCountAt(shown, state.t)}/${shown.length} served`;
    }

    function render() {
      if (state.disposed) return;
      overlay.setProps({ layers: layers() });
      updateText();
    }

    function tick(now) {
      if (!state.playing || state.disposed) return;
      if (state.lastFrame !== null && !state.scrubbing) {
        state.t = Math.min(data.span, state.t + ((now - state.lastFrame) / 1000) * state.speed);
      }
      state.lastFrame = now;
      render();
      if (state.t >= data.span) {
        setPlaying(false);
        updateText(true);
        return;
      }
      state.frame = requestAnimationFrame(tick);
    }

    function setPlaying(playing) {
      state.playing = playing;
      state.lastFrame = null;
      ui.play.textContent = playing ? "Pause" : "Play";
      ui.play.setAttribute("aria-pressed", String(playing));
      if (playing) {
        if (state.t >= data.span) state.t = 0;
        state.frame = requestAnimationFrame(tick);
      } else if (state.frame !== null) {
        cancelAnimationFrame(state.frame);
        state.frame = null;
      }
    }

    function dispose() {
      if (state.disposed) return;
      state.disposed = true;
      setPlaying(false);
      ui.detach();  // closed in the middle of a drag: nothing of this animation stays on the window
      // Finalizes deck, releases its WebGL context and removes its container (mountOverlay).
      map.removeControl(control);
      host.replaceChildren();
      host.hidden = true;
    }

    const ui = buildBar(host, {
      togglePlay: () => setPlaying(!state.playing),
      setSpeed: (value) => {
        state.speed = value;
      },
      seek: (value) => {
        state.t = Math.max(0, Math.min(data.span, value));
        state.lastFrame = null;
        render();
        updateText(true);
      },
      scrubbing: (held) => {
        state.scrubbing = held;
        state.lastFrame = null;  // resume from the dropped position, not with the held time added
      },
      close: () => {
        dispose();
        options.onClose?.();
      },
    });
    ui.scrub.max = String(data.span);
    ui.speed.value = String(state.speed);
    const clockKey = data.fallbackRoutes > 0 && data.clock !== "schematic" ? "schematic" : data.clock;
    const partial = data.fallbackRoutes > 0 && data.clock !== "schematic"
      ? ` ${data.fallbackRoutes} route(s) without a matching schedule run at constant speed.`
      : "";
    const labels = { ...CLOCK_LABELS, ...(options.clockLabels || {}) };
    ui.note.textContent = `${labels[data.clock] || labels[clockKey]}.${partial} Positions inside an arc are interpolated by distance.`;
    setView(options);
    updateText(true);
    const reducedMotion = global.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
    if (options.autoplay !== false && !reducedMotion) setPlaying(true);

    return {
      setView,
      close: dispose,
      get playing() {
        return state.playing;
      },
      data,
    };
  }

  global.MamutTrips = {
    CLOCK_LABELS,
    SCHEMATIC_SPEED_MPS,
    buildTrips,
    defaultSpeed,
    formatClock,
    hexToRgb,
    loadDeck,
    openAnimation,
    positionAt,
    servedCountAt,
    timelineFromTdSchedules,
  };
})(typeof window !== "undefined" ? window : globalThis);
