"use strict";

/* Shared Nocturne runtime helpers, loaded as a classic script by both frontends
   (see layout.js for why that form rather than an ES module).

   The twenty route colours used to be hard-coded as two JS arrays in *each* frontend
   while the same values also existed as --route-0…19 in the token sheet: four copies
   of one palette. They are now read from the live CSS variables, so nocturne-tokens.css
   is the only place a colour is written, and a theme swap needs no JS bookkeeping. */
(function (global) {
  const ROUTE_COUNT = 20;
  /* Reading twenty custom properties per polyline is wasteful on a large solution, so
     the resolved palette is cached and invalidated whenever the theme attribute
     changes. */
  let cache = null;
  let cacheTheme = null;

  function routeColors() {
    const theme = document.documentElement.dataset.theme || "";
    if (cache && cacheTheme === theme) return cache;
    const styles = getComputedStyle(document.documentElement);
    const colors = [];
    for (let index = 0; index < ROUTE_COUNT; index += 1) {
      const value = styles.getPropertyValue(`--route-${index}`).trim();
      if (value) colors.push(value);
    }
    /* If the token sheet failed to load there is nothing sensible to draw with;
       fall back to the accent so routes stay visible rather than vanishing. */
    cache = colors.length ? colors : [styles.getPropertyValue("--acc").trim() || "#9d8bff"];
    cacheTheme = theme;
    return cache;
  }

  function routeColor(index) {
    const colors = routeColors();
    return colors[index % colors.length];
  }

  function invalidate() {
    cache = null;
  }

  global.MamutNocturne = { ROUTE_COUNT, routeColors, routeColor, invalidate };
})(window);
