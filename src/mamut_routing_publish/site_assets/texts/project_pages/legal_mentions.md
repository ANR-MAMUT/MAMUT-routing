# Legal Mentions

`MAMUT-routing` and its related contributions are open-source, open-science, non-profit scientific contributions.

This page summarizes privacy, third-party asset requests, licensing, and contribution expectations for the public website and repository.

## Privacy

The static MAMUT-routing website has no account system, stores no user information, and does not require cookies for its own operation.

All fonts (Inter) and JavaScript libraries (Leaflet, MapLibre GL) are self-hosted with the website: opening a page triggers no third-party asset request. The one exception is the workbench map, whose background map is fetched by the browser when the map is displayed: OpenStreetMap raster tiles from `tile.openstreetmap.org`, and the CARTO Positron and Dark Matter vector basemaps from `basemaps.cartocdn.com` and `tiles.basemaps.cartocdn.com`. MAMUT-routing itself does not use these requests to identify users or store visitor data.

The CARTO basemaps are built on OpenStreetMap data and are used under the CARTO Basemaps free tier, which requires both [CARTO](https://carto.com/attributions) and [OpenStreetMap](https://www.openstreetmap.org/copyright) to stay credited on the map. The attribution shown in the map corner is part of that agreement.

## Licenses

Unless a more specific notice applies, MAMUT-routing source code and MAMUT-authored material are distributed under the [MIT License](https://mit-license.org/).

`Ortec2022` instances and some related BKS files are redistributed under their original [Creative Commons Attribution-NonCommercial 4.0 International](https://creativecommons.org/licenses/by-nc/4.0/) (`CC BY-NC 4.0`) terms.

`Poryos2026` instances and related generated artifacts are derived from OpenStreetMap data and are distributed, where applicable, under the [Open Data Commons Open Database License (ODbL) v1.0](https://www.openstreetmap.org/copyright).

For the authoritative repository-level notices, see the root `LICENSE`, `NOTICE`, and the `README.md` / `LICENSE` files present in each benchmark family directory.

## Contributions

Contributions are welcome on the [GitHub repository](https://github.com/ANR-MAMUT/MAMUT-routing). Any contribution must be compatible with the applicable repository licenses and with the benchmark-family licenses for the files it modifies or adds.

## Funding

This work is part of the ANR-MAMUT project, ANR-22-CE22-0016.
