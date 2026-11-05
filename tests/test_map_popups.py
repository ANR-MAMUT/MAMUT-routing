"""Click popups of the shared MapLibre kit, driven through the vendored MapLibre ``Popup``.

A MapLibre popup with ``closeOnClick`` adds a map click listener every time it opens;
the listener left by the previous opening closed the popup again right after the next
feature click reopened it, so every second click on a feature showed nothing. The kit
keeps ``closeOnClick`` off and closes the popup itself on a click on the empty map.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ASSETS = Path(__file__).resolve().parents[1] / "src" / "mamut_routing_publish" / "site_assets"
MAPLIBRE_JS = ASSETS / "vendor" / "maplibre-gl" / "maplibre-gl.js"

pytestmark = [
    pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed"),
    pytest.mark.skipif(not MAPLIBRE_JS.is_file(), reason="vendored MapLibre missing"),
]

# A DOM just large enough for maplibregl.Popup: elements with children and no layout.
SCRIPT = r"""
const fs = require("fs");
const vm = require("vm");
class El {
  constructor(tag) { this.tagName = tag; this.children = []; this.parentNode = null; this.style = {};
    this.classList = { add() {}, remove() {}, contains() { return false; }, toggle() {} }; this.attrs = {}; }
  appendChild(child) { child.parentNode = this; this.children.push(child); return child; }
  removeChild(child) { this.children = this.children.filter((item) => item !== child); child.parentNode = null; return child; }
  remove() { if (this.parentNode) this.parentNode.removeChild(this); }
  hasChildNodes() { return this.children.length > 0; }
  get firstChild() { return this.children[0] || null; }
  setAttribute(key, value) { this.attrs[key] = value; } getAttribute(key) { return this.attrs[key]; }
  removeAttribute(key) { delete this.attrs[key]; }
  addEventListener() {} removeEventListener() {}
  querySelector() { return null; } querySelectorAll() { return []; }
  getBoundingClientRect() { return { left: 0, top: 0, width: 100, height: 100, right: 100, bottom: 100 }; }
  focus() {} getContext() { return null; }
}
const document = { createElement: (tag) => new El(tag), createElementNS: (ns, tag) => new El(tag), body: new El("body"),
  head: new El("head"), documentElement: new El("html"), addEventListener() {}, removeEventListener() {} };
const window = { document, addEventListener() {}, removeEventListener() {}, devicePixelRatio: 1,
  navigator: { userAgent: "node", language: "en" }, location: { href: "http://x/", protocol: "http:" },
  matchMedia: () => ({ matches: false, addEventListener() {}, addListener() {} }),
  requestAnimationFrame: (fn) => setTimeout(fn, 0), cancelAnimationFrame: clearTimeout, performance: { now: () => Date.now() },
  URL, Blob, setTimeout, clearTimeout, console, Promise, Math, Date, JSON, Object, Array, Float32Array, Float64Array,
  Uint8Array, Uint16Array, Uint32Array, Int32Array, Int16Array, Int8Array, Uint8ClampedArray, ArrayBuffer, DataView,
  Map, Set, WeakMap, Symbol, Error, TypeError, RangeError, Number, String, Boolean, RegExp, Reflect, Proxy, isNaN,
  isFinite, parseFloat, parseInt, encodeURIComponent, decodeURIComponent, TextDecoder, TextEncoder,
  fetch: () => Promise.reject(new Error("no fetch")), Worker: function () { return { postMessage() {}, addEventListener() {}, terminate() {} }; },
  Image: function () { return new El("img"); }, HTMLImageElement: El, HTMLCanvasElement: El, HTMLVideoElement: El,
  ImageData: function () {}, ImageBitmap: function () {}, WebGLRenderingContext: function () {},
  WebGL2RenderingContext: function () {}, AbortController, queueMicrotask, structuredClone };
window.self = window; window.window = window; window.globalThis = window;
URL.createObjectURL = () => "blob:x";
const context = vm.createContext(window);
vm.runInContext(fs.readFileSync(process.argv[2], "utf8"), context);  // MapLibre
vm.runInContext(fs.readFileSync(process.argv[3], "utf8"), context);  // mamut-map.js
const { maplibregl, MamutMap } = context;

const container = new El("div");
class FakeMap extends maplibregl.Evented {
  constructor() { super(); this.feature = null; }
  getContainer() { return container; }
  getCanvas() { return { style: {} }; }
  _getUIString(key) { return key; }
  getLayer() { return {}; }
  getLayoutProperty() { return "visible"; }
  queryRenderedFeatures() {
    return this.feature ? [{ id: this.feature, layer: { id: "points" }, geometry: { type: "Point", coordinates: [2, 48] } }] : [];
  }
}
const map = new FakeMap();
map._canvasContainer = new El("div");
const describe = (feature) => { const node = new El("div"); node.textContent = feature.id; return node; };
const { popup } = MamutMap.bindLayerTooltip(map, ["points"], describe, { interaction: "click" });
// No layout in this DOM: render the popup's container directly (what _update does in a browser).
popup._update = () => {
  if (popup._map && !popup._container) {
    popup._container = new El("div");
    container.appendChild(popup._container);
    if (popup._content) popup._container.appendChild(popup._content);
  }
};
popup._focusFirstElement = () => {};
const states = [];
for (const feature of ["A", "B", "C", "D", null, "E"]) {
  map.feature = feature;
  map.fire("click", { point: { x: 1, y: 1 }, lngLat: { lng: 2, lat: 48 } });
  states.push([feature, popup.isOpen(), popup.isOpen() ? popup._content.children[0]?.textContent ?? popup._content.textContent : null]);
}
console.log(JSON.stringify(states));
"""


def test_every_feature_click_opens_its_popup_and_an_empty_click_closes_it(tmp_path: Path) -> None:
    script = tmp_path / "popups.js"
    script.write_text(SCRIPT, encoding="utf-8")
    completed = subprocess.run(
        ["node", str(script), str(MAPLIBRE_JS), str(ASSETS / "mamut-map.js")], capture_output=True, text=True, timeout=60
    )
    assert completed.returncode == 0, completed.stderr
    states = json.loads(completed.stdout.strip().splitlines()[-1])
    assert [open_ for _, open_, _ in states] == [True, True, True, True, False, True], states
    assert [text for feature, _, text in states if feature] == ["A", "B", "C", "D", "E"]
