# Vendored web libraries

Self-hosted so that opening a page triggers no third-party asset request (see the legal-mentions page). Each directory keeps the upstream license file. To upgrade, copy the `dist/` files of the pinned npm release and update this table.

| Directory | Library | Version | License | Source |
|---|---|---|---|---|
| `maplibre-gl/` | MapLibre GL JS (UMD build `dist/maplibre-gl.js` + `dist/maplibre-gl.css`) | 5.24.0 | BSD-3-Clause | https://github.com/maplibre/maplibre-gl-js |
| `deck.gl/` | deck.gl (UMD bundle `dist.min.js`, global `deck`; loaded only when the route animation is opened) | 9.4.0 | MIT | https://github.com/visgl/deck.gl |

MapLibre GL JS stays on the 5.x line on purpose: 6.x ships ES modules only, while the workbench loads the library as a classic script that exposes the `maplibregl` global (read by the shared `mamut-map.js`).

deck.gl ships as one bundle: `dist.min.js` is the npm package root file, not a `dist/` file. It includes loaders.gl, whose 3D-tiles module probes for WebAssembly support while the bundle loads. The workbench CSP has no `wasm-unsafe-eval`, so the browser reports one blocked `wasm-eval`. The probe catches the error and falls back; the route animation does not use that module.
