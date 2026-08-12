"use strict";

/* Shared workbench layout controller — resizable side panels with collapse-to-rail.
   Loaded as a classic script by both frontends so the local GUI (plain scripts) and
   the published site (ES modules) can share one file with no build step; it exposes
   itself as window.MamutLayout rather than exporting.

   The contract is CSS custom properties on a stage element:
     --wb-panel-inset        gutter between a panel and the viewport edge
     --wb-left-panel-width   current width of the left panel (rail width when collapsed)
     --wb-right-panel-width  current width of the right panel
   Panels, splitters, Leaflet control offsets and the map-clear button all position
   themselves off those variables with calc(), so everything follows a drag for free. */
(function (global) {
  const STORAGE_KEY = "mamut-workbench-layout";
  const RAIL_WIDTH = 44;
  const MIN_WIDTH = 240;
  const MAX_FRACTION = 0.4;
  /* Below this the panels stop being side-by-side columns and the stylesheet takes
     over with its own narrow-viewport treatment, so resizing must not apply. */
  const NARROW_BREAKPOINT = 1000;

  const DEFAULTS = {
    leftWidth: 300,
    rightWidth: 300,
    leftCollapsed: false,
    rightCollapsed: false,
  };

  function clampWidth(width) {
    const max = Math.max(MIN_WIDTH, Math.round(global.innerWidth * MAX_FRACTION));
    return Math.min(max, Math.max(MIN_WIDTH, Math.round(width)));
  }

  /* `defaults` lets each frontend keep the panel widths its own stylesheet was
     designed around — the published site's filter grid wants a wider left column than
     the local GUI. Without this, applying state would silently rewrite the CSS default
     even when the user has never resized anything. */
  function readState(storageKey, defaults) {
    const state = Object.assign({}, DEFAULTS, defaults || {});
    let stored = null;
    try {
      stored = JSON.parse(global.localStorage.getItem(storageKey) || "null");
    } catch (error) {
      stored = null; /* private mode, or a hand-edited value */
    }
    if (!stored || typeof stored !== "object") return state;
    if (Number.isFinite(stored.leftWidth)) state.leftWidth = clampWidth(stored.leftWidth);
    if (Number.isFinite(stored.rightWidth)) state.rightWidth = clampWidth(stored.rightWidth);
    state.leftCollapsed = stored.leftCollapsed === true;
    state.rightCollapsed = stored.rightCollapsed === true;
    return state;
  }

  function writeState(storageKey, state) {
    try {
      global.localStorage.setItem(storageKey, JSON.stringify(state));
    } catch (error) { /* private mode — the layout simply won't persist */ }
  }

  /* Paint the state onto the stage. Kept free of side effects beyond the DOM so the
     blocking bootstrap in <head> can call the same logic before first paint. */
  function applyState(stage, state) {
    stage.style.setProperty(
      "--wb-left-panel-width",
      (state.leftCollapsed ? RAIL_WIDTH : state.leftWidth) + "px",
    );
    stage.style.setProperty(
      "--wb-right-panel-width",
      (state.rightCollapsed ? RAIL_WIDTH : state.rightWidth) + "px",
    );
    stage.dataset.leftCollapsed = String(state.leftCollapsed);
    stage.dataset.rightCollapsed = String(state.rightCollapsed);
  }

  function initLayout(options) {
    const config = options || {};
    const stage = config.stage || document.body;
    const storageKey = config.storageKey || STORAGE_KEY;
    const onResize = typeof config.onResize === "function" ? config.onResize : function () {};

    const defaults = Object.assign({}, DEFAULTS, config.defaults || {});
    const state = readState(storageKey, defaults);
    applyState(stage, state);

    /* role="separator" is only meaningful to a screen reader if it reports its value. */
    function syncSplitterAria() {
      const max = Math.max(MIN_WIDTH, Math.round(global.innerWidth * MAX_FRACTION));
      stage.querySelectorAll("[data-splitter]").forEach((splitter) => {
        const width = splitter.dataset.splitter === "left" ? state.leftWidth : state.rightWidth;
        splitter.setAttribute("aria-valuenow", String(width));
        splitter.setAttribute("aria-valuemin", String(MIN_WIDTH));
        splitter.setAttribute("aria-valuemax", String(max));
      });
    }
    syncSplitterAria();

    let framePending = false;
    /* Leaflet only recomputes its pixel origin when told to. Coalesce to one call per
       frame during a drag, otherwise a fast drag fires dozens of full map relayouts. */
    function notifyResize() {
      if (framePending) return;
      framePending = true;
      global.requestAnimationFrame(() => {
        framePending = false;
        onResize();
      });
    }

    function commit() {
      applyState(stage, state);
      syncSplitterAria();
      writeState(storageKey, state);
      notifyResize();
    }

    function isNarrow() {
      return global.innerWidth <= NARROW_BREAKPOINT;
    }

    function setWidth(side, width) {
      const clamped = clampWidth(width);
      if (side === "left") state.leftWidth = clamped;
      else state.rightWidth = clamped;
      commit();
    }

    function setCollapsed(side, collapsed) {
      if (side === "left") state.leftCollapsed = collapsed;
      else state.rightCollapsed = collapsed;
      commit();
    }

    function toggleCollapsed(side) {
      setCollapsed(side, !(side === "left" ? state.leftCollapsed : state.rightCollapsed));
    }

    /* ── Splitters ── */
    stage.querySelectorAll("[data-splitter]").forEach((splitter) => {
      const side = splitter.dataset.splitter;

      const widthFromPointer = (clientX) => {
        const inset = parseFloat(
          getComputedStyle(stage).getPropertyValue("--wb-panel-inset"),
        ) || 0;
        return side === "left"
          ? clientX - inset
          : global.innerWidth - clientX - inset;
      };

      splitter.addEventListener("pointerdown", (event) => {
        if (isNarrow() || event.button !== 0) return;
        /* A collapsed panel has no width to drag; the rail's own button expands it. */
        if (side === "left" ? state.leftCollapsed : state.rightCollapsed) return;
        event.preventDefault();
        splitter.setPointerCapture(event.pointerId);
        splitter.dataset.dragging = "true";
        document.body.style.cursor = "col-resize";
        /* Stop the map and text selection from reacting while the splitter drags. */
        document.body.style.userSelect = "none";
      });

      splitter.addEventListener("pointermove", (event) => {
        if (splitter.dataset.dragging !== "true") return;
        setWidth(side, widthFromPointer(event.clientX));
      });

      const endDrag = (event) => {
        if (splitter.dataset.dragging !== "true") return;
        delete splitter.dataset.dragging;
        try { splitter.releasePointerCapture(event.pointerId); } catch (error) { /* already released */ }
        document.body.style.cursor = "";
        document.body.style.userSelect = "";
        onResize();
      };
      splitter.addEventListener("pointerup", endDrag);
      splitter.addEventListener("pointercancel", endDrag);

      splitter.addEventListener("dblclick", () => {
        if (isNarrow()) return;
        setWidth(side, side === "left" ? defaults.leftWidth : defaults.rightWidth);
      });

      /* Keyboard resizing: the splitter is a focusable separator, so arrow keys have
         to do something useful or it is a focus trap for keyboard users. */
      splitter.addEventListener("keydown", (event) => {
        if (isNarrow()) return;
        const current = side === "left" ? state.leftWidth : state.rightWidth;
        const step = event.shiftKey ? 64 : 16;
        const grow = side === "left" ? "ArrowRight" : "ArrowLeft";
        const shrink = side === "left" ? "ArrowLeft" : "ArrowRight";
        if (event.key === grow) setWidth(side, current + step);
        else if (event.key === shrink) setWidth(side, current - step);
        else if (event.key === "Enter" || event.key === " ") toggleCollapsed(side);
        else return;
        event.preventDefault();
      });
    });

    /* ── Collapse toggles and rails ── */
    stage.querySelectorAll("[data-panel-toggle]").forEach((button) => {
      button.addEventListener("click", () => toggleCollapsed(button.dataset.panelToggle));
    });

    stage.querySelectorAll("[data-rail-target]").forEach((button) => {
      button.addEventListener("click", () => {
        const side = button.dataset.railSide || "left";
        setCollapsed(side, false);
        const target = button.dataset.railTarget;
        if (target) {
          stage.dispatchEvent(
            new CustomEvent("layout:rail-select", { detail: { side, target } }),
          );
        }
      });
    });

    /* Re-clamp on viewport resize: a width that was legal on a wide monitor can exceed
       40% after the window shrinks, which would bury the map. */
    global.addEventListener("resize", () => {
      const left = clampWidth(state.leftWidth);
      const right = clampWidth(state.rightWidth);
      if (left !== state.leftWidth || right !== state.rightWidth) {
        state.leftWidth = left;
        state.rightWidth = right;
        commit();
      } else {
        notifyResize();
      }
    });

    return {
      state,
      setWidth,
      setCollapsed,
      toggleCollapsed,
      reset() {
        Object.assign(state, defaults);
        commit();
      },
    };
  }

  global.MamutLayout = {
    STORAGE_KEY,
    RAIL_WIDTH,
    MIN_WIDTH,
    DEFAULTS,
    readState,
    applyState,
    initLayout,
  };
})(window);
