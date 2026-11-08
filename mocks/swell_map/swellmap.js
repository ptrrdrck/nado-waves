// The Swell card's map (MOCK, 2026-11-07): a toggle in the corner of each
// break's drawing swaps it for the same geometry over Esri World Imagery,
// in the drawing's own footprint and turned the drawing's way -- the break's
// shore normal straight up, the break where the drawing puts it.
//
// The map reads the DRAWING, never a payload of its own: the windows' and
// shadows' angles, each train's arrow, the 5 m arrowheads and the captions
// are the svg's (`data-geo`, its arrows, its `.faces`), and a tap on the map
// goes through the page's own `togglePick`, so a row tap, an arrow tap and a
// map tap are one pick with one caption, on both tabs and every past hour.
// Only the edge vertices and the land outlines come from forecast.geomviz,
// because the drawing has no distances.
(function () {
  "use strict";
  const MODEL = window.__SWELLMAP_MODEL__;
  if (!MODEL || !window.L) return;
  const ESRI = "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}";
  const ATTR = "Imagery Esri, Maxar, Earthstar Geographics";
  const KEY = "nado-sm-view";               // one choice for every tab, kept on this device
  const TOUCH = matchMedia("(pointer: coarse)").matches;
  const ICON_DRAW = '<svg viewBox="0 0 16 16" aria-hidden="true"><path d="M1.5 12.5h13M8 12.5L2.6 7M8 12.5L5 3.6M8 12.5l5.4-5.5"/><path d="M2.6 7a6.5 6.5 0 0 1 10.8 0" stroke-dasharray="1.6 1.8"/></svg>';
  const ICON_MAP = '<svg viewBox="0 0 16 16" aria-hidden="true"><path d="M1.5 3.5l4-1.5 5 2 4-1.5v10l-4 1.5-5-2-4 1.5z"/><path d="M5.5 2v10M10.5 4v10"/></svg>';
  const ICON_FIT = '<svg viewBox="0 0 16 16" aria-hidden="true"><path d="M2 6V2h4M10 2h4v4M14 10v4h-4M6 14H2v-4"/></svg>';

  const call = (n, ...a) => { try { return eval(n)(...a); } catch (e) { return null; } };
  const brk = (id) => MODEL.breaks.find((b) => b.id === id);
  const picked = () => { try { return eval("PICKED"); } catch (e) { return {}; } };
  const deg = (b) => `${Math.round(((b % 360) + 360) % 360)}°`;
  const MI = (() => { try { return eval("MI_PER_KM"); } catch (e) { return 0.621371; } })();
  const dist = (km) => call("dualText", `${(km * MI).toFixed(km * MI < 10 ? 1 : 0)} mi`,
    `${km.toFixed(km < 10 ? 1 : 0)} km`) || `${(km * MI).toFixed(1)} mi`;
  const OPEN_STEPS = 3;                      // zoom steps in from the drawing's scale
  const BUOY_NAME = `NDBC ${MODEL.buoy.id}`;  // as the page names every buoy since 2026-11-06

  let view = "drawing";
  try { view = localStorage.getItem(KEY) === "map" ? "map" : "drawing"; } catch (e) { /* storage off */ }

  // --- spherical geometry, as forecast.swell has it ---
  const rad = (d) => d * Math.PI / 180, dg = (r) => r * 180 / Math.PI;
  function dest(p, brg, km) {
    const d = km / 6371.0088, t = rad(brg), f1 = rad(p[0]), l1 = rad(p[1]);
    const f2 = Math.asin(Math.sin(f1) * Math.cos(d) + Math.cos(f1) * Math.sin(d) * Math.cos(t));
    const l2 = l1 + Math.atan2(Math.sin(t) * Math.sin(d) * Math.cos(f1), Math.cos(d) - Math.sin(f1) * Math.sin(f2));
    return [dg(f2), dg(l2)];
  }
  function fan(p, from, to, km) {
    const span = ((to - from) % 360 + 360) % 360, n = Math.max(2, Math.ceil(span)), pts = [p];
    for (let i = 0; i <= n; i++) pts.push(dest(p, from + span * i / n, km));
    pts.push(p);
    return pts;
  }

  // --- what the drawing holds ---
  function readSvg(svg) {
    let geo = {};
    try { geo = JSON.parse(svg.getAttribute("data-geo")); } catch (e) { return null; }
    const ang = (x, y) => dg(Math.atan2(x - geo.cx, geo.cy - y));
    const trains = (geo.trains || []).map((t) => {
      const g = svg.querySelector(`g.swell[data-pick="${t.key}"]`);
      return {key: t.key, a: ang(t.x0, t.y0), lead: !!(g && g.classList.contains("lead"))};
    });
    const nears = [...svg.querySelectorAll("polygon.near")].map((p) => {
      const [x, y] = p.getAttribute("points").trim().split(/\s+/)[0].split(",").map(Number);
      return {show: p.getAttribute("data-show"), a: ang(x, y), on: !p.hasAttribute("hidden")};
    });
    const faces = [...svg.querySelectorAll("text.faces")].find((t) => !t.hasAttribute("hidden"));
    const caption = faces ? [...faces.querySelectorAll("tspan")].map((s) => s.textContent).join("\n") : "";
    const on = new Set([...svg.querySelectorAll("[data-pick].on")].map((e) => e.getAttribute("data-pick")));
    return {sections: geo.sections || [], trains, nears, caption, on, rimPx: geo.r, cx: geo.cx, cy: geo.cy};
  }

  // One map per drawing, made the first time it is shown.
  class Face {
    constructor(svg) {
      this.svg = svg;
      this.id = svg.getAttribute("data-break");
      this.b = brk(this.id);
      this.box = document.createElement("div");
      this.box.className = "sm-face";
      svg.before(this.box);
      this.box.append(svg);
      this.box.insertAdjacentHTML("beforeend",
        `<div class="sm-map" hidden><div class="sm-attr">${ATTR}</div><div class="sm-cap" aria-live="polite"></div>`
        + `<div class="sm-hint">Use two fingers to move the map</div></div>`
        + `<button type="button" class="sm-switch"></button>`);
      this.el = this.box.querySelector(".sm-map");
      // One button: it shows what a tap turns to -- the map from the
      // drawing, the drawing from the map (owner's request, 2026-11-08).
      this.box.querySelector(".sm-switch").addEventListener("click", (e) => {
        e.stopPropagation();
        setView(view === "map" ? "drawing" : "map");
      });
      // The drawing's own picks, from its rows or its arrows, redraw the map's.
      new MutationObserver(() => this.sync()).observe(svg, {attributes: true, subtree: true, attributeFilter: ["class", "hidden"]});
      this.show();
    }

    show() {
      const on = view === "map" && !!this.b;
      const btn = this.box.querySelector(".sm-switch");
      btn.innerHTML = on ? ICON_DRAW : ICON_MAP;
      btn.setAttribute("aria-label", on ? "Show the drawing" : "Show the map");
      btn.title = on ? "Drawing" : "Map";
      this.el.hidden = !on;
      this.box.classList.toggle("on-map", on);
      if (on && this.box.offsetWidth) {
        if (!this.map) this.make();
        this.map.invalidateSize({animate: false});
        if (!this.framed) this.frame();
        this.draw();
      }
    }

    make() {
      const map = this.map = L.map(this.el, {
        rotate: true, bearing: 0, touchRotate: false, shiftKeyRotate: false, rotateControl: false,
        compassBearing: false, zoomSnap: 0, zoomDelta: 0.5, zoomControl: false, attributionControl: false,
        dragging: !TOUCH, touchZoom: true, scrollWheelZoom: false, doubleClickZoom: true, minZoom: 8, maxZoom: 18,
      });
      L.tileLayer(ESRI, {maxNativeZoom: 18, maxZoom: 18}).addTo(map);
      const self = this;
      // + and - zoom around the break, so it stays where the drawing has it;
      // pinch and double-tap zoom where the reader puts them.
      const Zoom = L.Control.extend({options: {position: "topright"}, onAdd() {
        const d = L.DomUtil.create("div", "leaflet-bar");
        d.innerHTML = '<a href="#" role="button" title="Zoom in" aria-label="Zoom in">+</a>'
          + '<a href="#" role="button" title="Zoom out" aria-label="Zoom out">\u2212</a>';
        const step = (dz) => (e) => { L.DomEvent.stop(e); map.setZoomAround(self.b.position, map.getZoom() + dz); };
        L.DomEvent.on(d.children[0], "click", step(1));
        L.DomEvent.on(d.children[1], "click", step(-1));
        L.DomEvent.disableClickPropagation(d);
        return d;
      }});
      new Zoom().addTo(map);
      const Fit = L.Control.extend({options: {position: "topright"}, onAdd() {
        const d = L.DomUtil.create("div", "leaflet-bar");
        d.innerHTML = `<a href="#" role="button" title="Back to the opening view" aria-label="Back to the opening view">${ICON_FIT}</a>`;
        L.DomEvent.on(d.firstChild, "click", (e) => { L.DomEvent.stop(e); self.frame(true); });
        L.DomEvent.disableClickPropagation(d);
        return d;
      }});
      new Fit().addTo(map);
      this.land = L.featureGroup().addTo(map);     // geometry that keeps its place on the ground
      this.marks = L.featureGroup().addTo(map);    // arrows drawn at the drawing's pixel size
      map.on("click", () => { const k = picked()[this.id]; if (k) call("togglePick", this.svg, k); });
      map.on("zoomend", () => this.drawMarks());
      this.el.addEventListener("wheel", (e) => {
        if (!e.ctrlKey) return;
        e.preventDefault();
        map.setZoom(map.getZoom() - Math.sign(e.deltaY) * 0.5);
      }, {passive: false});
      if (TOUCH) {
        const hint = this.el.querySelector(".sm-hint");
        let y0 = null, timer = 0;
        this.el.addEventListener("touchstart", (e) => { y0 = e.touches.length === 1 ? e.touches[0].clientY : null; }, {passive: true});
        this.el.addEventListener("touchmove", (e) => {
          if (y0 == null || e.touches.length !== 1 || Math.abs(e.touches[0].clientY - y0) < 8) return;
          hint.classList.add("on"); clearTimeout(timer);
          timer = setTimeout(() => hint.classList.remove("on"), 1100); y0 = null;
        }, {passive: true});
      }
      this.drawLand();
    }

    // The opening view: the shore normal up, the break as far above the
    // map's foot as it sits above the drawing's, and three zoom steps in
    // from the drawing's own scale -- where the farthest vertex forming an
    // edge sits on its rim (owner's request, 2026-11-08: "+" three times).
    frame(animate = false) {
      const map = this.map, b = this.b, d = readSvg(this.svg);
      const W = this.el.clientWidth, H = this.el.clientHeight;
      const vb = this.svg.viewBox.baseVal, s = W / vb.width;
      const rimPx = d.rimPx * s, far = Math.max(...b.windows.flatMap((w) => w.edges.map((e) => e.range_km)));
      const mpp = far * 1000 / rimPx / 2 ** OPEN_STEPS;
      const zoom = Math.log2(156543.03392 * Math.cos(rad(b.position[0])) / mpp);
      const breakY = H - (vb.height - d.cy) * s;
      const upKm = (breakY - H / 2) * mpp / 1000;  // the break sits below the middle, so the centre is seaward
      map.setBearing(-b.normal);
      map.setView(dest(b.position, b.normal, upKm), zoom, {animate});
      this.framed = true;
    }

    drawLand() {
      const g = this.land, b = this.b, p = b.position;
      g.clearLayers();
      const d = readSvg(this.svg) || {sections: []};
      const far = Math.max(...b.windows.flatMap((w) => w.edges.map((e) => e.range_km))) * 1.6;
      d.sections.forEach((sec) => {
        const shadow = sec.key[0] === "s";
        L.polygon(fan(p, b.normal + sec.a0, b.normal + sec.a1, far), {
          color: "#fff", weight: 0, fillColor: shadow ? "#000" : "#fff",
          fillOpacity: shadow ? 0.22 : 0.13, _key: sec.key, _shadow: shadow,
        }).on("click", (e) => { L.DomEvent.stop(e); call("togglePick", this.svg, sec.key); }).addTo(g);
      });
      // Each window edge: a ray to the one vertex that forms it, then on to sea.
      b.windows.forEach((w) => w.edges.forEach((e) => {
        L.polyline([p, e.vertex], {color: "#000", weight: 3.5, opacity: 0.35, interactive: false}).addTo(g);
        L.polyline([p, e.vertex], {color: "#fff", weight: 1.5, opacity: 0.95, interactive: false}).addTo(g);
        L.polyline([e.vertex, dest(p, e.bearing, far)], {color: "#fff", weight: 1, opacity: 0.6, dashArray: "3 5", interactive: false}).addTo(g);
        L.circleMarker(e.vertex, {radius: 4.5, color: "#fff", weight: 2, fillColor: "#000", fillOpacity: 0.6})
          .on("click", (ev) => { L.DomEvent.stop(ev); this.say(`${e.blocker}, the vertex that forms the ${deg(e.bearing)} edge, ${dist(e.range_km)} from this break`); })
          .addTo(g);
      }));
      // The land the model has, as it has it: dashed, so the photograph shows
      // how few vertices the windows stand on.
      MODEL.blockers.forEach((bl) => {
        const line = bl.outline && bl.outline.length > 2 ? bl.outline : [bl.a, bl.b];
        L.polyline(line, {color: "#fff", weight: 1.25, opacity: 0.85, dashArray: "2 4", interactive: false}).addTo(g);
      });
      MODEL.breaks.forEach((o) => {
        const on = o.id === this.id;
        L.polyline(o.chord, {color: "#000", weight: on ? 6 : 4, opacity: 0.4, interactive: false}).addTo(g);
        L.polyline(o.chord, {color: "#fff", weight: on ? 3 : 2, opacity: on ? 1 : 0.8, interactive: false}).addTo(g);
        L.circleMarker(o.position, {radius: on ? 5 : 3.5, color: on ? "#000" : "#fff", weight: on ? 2 : 1.5,
          fillColor: on ? "#fff" : "#000", fillOpacity: 1, interactive: false}).addTo(g);
      });
      const q = MODEL.buoy.position;
      if (q) {
        L.circleMarker(q, {radius: 5, color: "#fff", weight: 2, fillColor: "#000", fillOpacity: 0.7}).addTo(g)
          .on("click", (ev) => { L.DomEvent.stop(ev); this.say(`${BUOY_NAME}, Point Loma South`); });
        tag(g, q, BUOY_NAME);
      }
    }

    // Arrows in screen pixels from the break, as the drawing draws them: in
    // from the rim to 0.62 of it, the lead heavier; and a picked train's 5 m
    // arrowhead at the break. Redrawn on every zoom so they keep their size.
    drawMarks() {
      const map = this.map, g = this.marks, d = readSvg(this.svg);
      g.clearLayers();
      if (!d) return;
      const s = this.el.clientWidth / this.svg.viewBox.baseVal.width, r = d.rimPx * s;
      const o = map.latLngToContainerPoint(this.b.position);
      const at = (a, rr) => map.containerPointToLatLng([o.x + rr * Math.sin(rad(a)), o.y - rr * Math.cos(rad(a))]);
      [...d.trains].reverse().forEach((t) => {
        const lit = d.on.has(t.key), w = t.lead ? 3 : 2;
        const line = [at(t.a, r * 0.95), at(t.a, r * 0.62 + 6)];
        L.polyline(line, {color: "#000", weight: w + 3, opacity: 0.35, interactive: false}).addTo(g);
        L.polyline(line, {color: lit ? "#ffd84d" : "#fff", weight: lit ? w + 1 : w, _key: t.key})
          .on("click", (e) => { L.DomEvent.stop(e); call("togglePick", this.svg, t.key); }).addTo(g);
        head(g, at(t.a, r * 0.62), t.a, t.lead ? 14 : 11, lit).on("click", (e) => { L.DomEvent.stop(e); call("togglePick", this.svg, t.key); });
      });
      d.nears.filter((n) => n.on).forEach((n) => head(g, at(n.a, r * 0.1), n.a, 17, true, true));
      // The two outermost edges carry their degrees, where the drawing puts
      // them: just inside the rim, so they never sit on the break.
      const secs = d.sections.slice().sort((x, y) => x.a0 - y.a0);
      const wins = secs.filter((x) => x.key[0] === "w");
      if (wins.length) {
        [wins[0].a0, wins[wins.length - 1].a1].forEach((a) =>
          tag(g, at(a, r * 0.86), deg(this.b.normal + a), "sm-deg"));
      }
    }

    draw() {
      if (!this.map) return;
      const d = readSvg(this.svg);
      this.land.eachLayer((l) => {
        if (!l.options._key) return;
        const lit = d.on.has(l.options._key);
        l.setStyle(l.options._shadow ? {fillOpacity: lit ? 0.5 : 0.22} : {fillOpacity: lit ? 0.3 : 0.13});
      });
      this.drawMarks();
      this.say(d.caption);
    }

    say(text) { this.el.querySelector(".sm-cap").textContent = text; }
    sync() { if (!this.el.hidden) this.draw(); }
  }

  // A label that stays upright whatever way the map is turned.
  function tag(g, at, text, cls = "sm-tag") {
    return L.marker(at, {interactive: false, keyboard: false,
      icon: L.divIcon({className: cls, html: `<span>${text}</span>`, iconSize: [0, 0]})}).addTo(g);
  }
  // An arrowhead pointing in along screen angle `a` (degrees off straight up).
  function head(g, at, a, size, lit, near = false) {
    const fill = lit ? "#ffd84d" : "#fff";
    return L.marker(at, {keyboard: false, icon: L.divIcon({className: "sm-head", iconSize: [size, size],
      html: `<svg viewBox="0 0 16 16" width="${size}" height="${size}" style="transform:rotate(${a}deg)">`
        + `<path d="M8 15 L2 3 L8 6 L14 3 Z" fill="${fill}" stroke="#000" stroke-opacity=".5" stroke-width="1"/></svg>`})}).addTo(g);
  }

  const faces = new Map();
  function setView(v) {
    view = v;
    try { localStorage.setItem(KEY, v); } catch (e) { /* storage off */ }
    faces.forEach((f) => f.show());
  }

  // The page redraws its cards on every refresh and every hour picked: each
  // new drawing gets its toggle and, if the map is the choice, its map.
  function attach() {
    document.querySelectorAll("svg.aperture").forEach((svg) => {
      if (faces.has(svg) || !brk(svg.getAttribute("data-break"))) return;
      if (svg.closest(".swell-wide, [data-layout='stack'] .cols, [data-layout='console'] .cols")) return;
      faces.set(svg, new Face(svg));
    });
    faces.forEach((f, svg) => { if (!svg.isConnected) faces.delete(svg); });
  }
  // A tab or tab-chain switch reveals a drawing that was hidden when made.
  document.addEventListener("click", () => setTimeout(() => faces.forEach((f) => { if (!f.el.hidden || view === "map") f.show(); }), 0));
  new MutationObserver(() => attach()).observe(document.body, {childList: true, subtree: true});
  attach();
})();
