# Vendored web libraries

Self-hosted so that opening a page triggers no third-party asset request (see the legal-mentions page). Each directory keeps the upstream license file. To upgrade, copy the `dist/` files of the pinned npm release and update this table.

| Directory | Library | Version | License | Source |
|---|---|---|---|---|
| `leaflet/` | Leaflet | 1.9.4 | BSD-2-Clause | https://github.com/Leaflet/Leaflet |
| `maplibre-gl/` | MapLibre GL JS (UMD build `dist/maplibre-gl.js` + `dist/maplibre-gl.css`) | 5.24.0 | BSD-3-Clause | https://github.com/maplibre/maplibre-gl-js |
| `maplibre-gl-leaflet/` | maplibre-gl-leaflet (`leaflet-maplibre-gl.js`) | 0.1.4 | ISC | https://github.com/maplibre/maplibre-gl-leaflet |

MapLibre GL JS stays on the 5.x line on purpose: 6.x ships ES modules only, while the workbench loads the library and the Leaflet plugin as classic scripts that expose the `maplibregl` and `L.maplibreGL` globals.
