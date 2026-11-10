// Swell fill on the map (MOCK, 2026-11-10, option B): on the LIVE tab, a
// picked train's energy coming in along its rays' REAL paths over the seabed,
// on the Swell card's map (mocks/swell_map).
//
// Every ray is one row of the break's transfer table, re-traced with its
// path recorded (mocks/swell_fill/rays.py, checked against raytrace.trace):
// straight in from the line through NDBC 46232 square to its heading, where
// the clock reads 0, then bent over the seabed to 5 m of water, then on to
// the break along the line the surf zone is computed on. Its brightness is
// the train's energy it carries to 5 m, as nearshore.carry credits it; what
// diffraction adds is drawn on the clearing ray of the same period nearest
// the heading the table credits it to. The clock is minutes after the same
// wave group passed 46232 (raytrace.leg_table's arithmetic): long periods
// arrive first. Nothing here is a wave field or a crest.
//
// The map's base is the seabed (owner's choice, 2026-11-10), as map tiles
// loaded only where they are in view: the grids the rays were traced over
// near the breaks, and GMRT's coarse context grid out past Tanner Bank, where
// the map stops zooming out.
//
// Loaded after Leaflet and before swellmap.js, so it sees every map made.
(function () {
  "use strict";
  const RAYS = window.__SWELLRAYS__;
  if (!RAYS || !window.L) return;

  const PLAY_MS = 12000;
  const RAY = "#ffd84d";         // the map's pick colour
  const REDUCED = matchMedia("(prefers-reduced-motion: reduce)");
  const ICON = {
    play: '<svg viewBox="0 0 12 12" aria-hidden="true"><path d="M3 1.5v9l7.5-4.5z"/></svg>',
    pause: '<svg viewBox="0 0 12 12" aria-hidden="true"><rect x="2" y="1.5" width="3" height="9" rx=".5"/>'
      + '<rect x="7" y="1.5" width="3" height="9" rx=".5"/></svg>',
    // The forecast page's "back to" clock without its arms (owner's
    // reference, 2026-11-10: the week card's button), at the map buttons' line.
    again: '<svg class="stroke" viewBox="0 0 16 16" aria-hidden="true">'
      + '<path d="M3.1 5.6A5.4 5.4 0 1 1 2.6 8.6"/><path d="M2.7 3.2v2.6h2.6"/></svg>',
  };
  const g = (name, fb) => { try { return eval(name); } catch (e) { return fb; } };
  const live = () => g("MODE", "now") === "now";
  const height = (m) => { const f = g("heightText", null); return f ? f(m) : `${(m * 3.28084).toFixed(1)} ft`; };
  const rad = (d) => d * Math.PI / 180;

  function rowsOf(key) {
    if (!key) return [];
    let m = /^[Tt](\d+)(?:-\d+)?$/.exec(key);
    if (m) return [+m[1]];
    m = /^G([\d.]+)$/.exec(key);
    return m ? m[1].split(".").map(Number) : [];
  }

  // ------------------------------------------------------------ the base map
  // The seabed as map tiles (mocks/swell_fill/tiles.py), back to front: the
  // GMRT context grid out past Tanner Bank (zooms 6-9), the rays' own CoNED
  // and GMRT grids (10-12), and CoNED's nearshore grid (13-14), each layer
  // stretched past its last zoom and fetched only where it has tiles. Leaflet
  // loads the tiles in view and no others, so a wider grid costs nothing on
  // screen. No zooming out past Tanner Bank, no panning off it.
  const TILES = RAYS.tiles || {layers: []};
  const BUOYS = RAYS.buoys || {};
  window.__SWELLMAP_ATTR__ = "Seabed USGS CoNED, GMRT";
  window.__SWELLMAP_BASE__ = (map, b) => {
    TILES.layers.forEach((t, i) => {
      L.tileLayer(`${TILES.base}/{z}/{x}/{y}.png`, {
        minZoom: i ? t.zooms[0] : 0, maxNativeZoom: t.zooms[1], maxZoom: 18,
        bounds: L.latLngBounds(t.bounds), minNativeZoom: t.zooms[0],
        keepBuffer: 4, updateWhenZooming: false, className: `sf-tiles sf-tiles-${t.name}`,
        zIndex: i + 1,
      }).addTo(map);
    });
    // The other buoys the page shows, marked as 46232 is.
    Object.entries(BUOYS).forEach(([id, at]) => {
      L.circleMarker(at, {radius: 5, color: "#fff", weight: 2, fillColor: "#000",
        fillOpacity: 0.7, interactive: false}).addTo(map);
      L.marker(at, {interactive: false, keyboard: false,
        icon: L.divIcon({className: "sm-tag", html: `<span>NDBC ${id}</span>`, iconSize: [0, 0]})}).addTo(map);
    });
    if (!BUOYS["46047"] || !b) return;
    const home = L.latLng(b.position), t = L.latLng(BUOYS["46047"]);
    const reach = home.distanceTo(t) + 25000;     // just past Tanner Bank
    // At the widest, a point just past Tanner Bank is in view with the break
    // where the map keeps it (the middle of the foot, the normal up).
    const y = Math.sin(rad(t.lng - home.lng)) * Math.cos(rad(t.lat));
    const x = Math.cos(rad(home.lat)) * Math.sin(rad(t.lat))
      - Math.sin(rad(home.lat)) * Math.cos(rad(t.lat)) * Math.cos(rad(t.lng - home.lng));
    const rel = Math.atan2(y, x) - rad(b.normal);
    const fit = () => {
      const el = map.getContainer(), W = el.clientWidth || 330, H = el.clientHeight || 330;
      const across = Math.abs(Math.sin(rel)) * reach, along = Math.max(0, Math.cos(rel)) * reach;
      // 76 px kept at the side for 46047's label.
      const mpp = Math.max(across / (0.5 * W - 76), along / (0.85 * H), 1);
      map.setMinZoom(Math.log2(156543.03392 * Math.cos(rad(home.lat)) / mpp));
    };
    fit();
    map.on("resize", fit);
    // The view's middle stays within that reach of the break.
    let pulling = false;
    map.on("moveend", () => {
      if (pulling) return;
      const c = map.getCenter(), d = home.distanceTo(c);
      if (d <= reach) return;
      const k = 0.98 * reach / d;
      pulling = true;
      map.panTo([home.lat + (c.lat - home.lat) * k, home.lng + (c.lng - home.lng) * k], {animate: false});
      pulling = false;
    });
  };

  // ------------------------------------------------------------ the model
  function model(id, rows) {
    const b = RAYS.breaks[id];
    if (!b) return null;
    rows = rows.filter((n) => b.rows[n]);
    if (!rows.length) return null;
    const w = new Map();             // ray -> its 5 m energy, in the rows' own heights squared
    const byRow = rows.map(() => []);
    rows.forEach((n, ri) => {
      const row = b.rows[n], e0 = row.row_hs_m * row.row_hs_m;
      row.rays.forEach(([j, , share]) => {
        w.set(j, (w.get(j) || 0) + share * e0);
        byRow[ri].push([j, share]);
      });
    });
    const rays = [...w.entries()].map(([j, e]) => ({ray: b.rays[j], e, j}));
    const sorted = rays.map((r) => r.e).sort((p, q) => p - q);
    const ref = sorted[Math.floor(sorted.length * 0.9)] || 1;
    const arrive = (r) => r.ray.pts[r.ray.pts.length - 1][2];
    const order = rays.slice().sort((p, q) => arrive(p) - arrive(q));
    const total = rays.reduce((s, r) => s + r.e, 0);
    const pct = (p) => {
      let c = 0;
      for (const r of order) { c += r.e; if (c >= p * total) return arrive(r); }
      return order.length ? arrive(order[order.length - 1]) : 0;
    };
    const last = pct(0.98);
    // The clock opens as the swell passes 46232 (0), or earlier where much
    // of it leaves deep water up-swell of the buoy's line: where 2% of the
    // energy has started. A ray starting earlier opens part-way in.
    const starts = rays.map((r) => [r.ray.pts[0][2], r.e]).sort((p, q) => p[0] - q[0]);
    let acc = 0, start = 0;
    for (const [t, e] of starts) { acc += e; if (acc >= 0.02 * total) { start = Math.min(0, t); break; } }
    return {
      id, rows, rays, ref, total, byRow,
      rowHs: rows.map((n) => b.rows[n].row_hs_m),
      drawnShare: rows.map((n) => b.rows[n].drawn_share),
      t0: Math.floor(start), t1: last + 3, last,
    };
  }

  function soFar(m, t) {
    const inRow = m.rows.map(() => 0);
    const per = {};
    m.byRow.forEach((list, ri) => list.forEach(([j, share]) => {
      const ray = RAYS.breaks[m.id].rays[j];
      const at = ray.pts[ray.pts.length - 1][2];
      const p = ray.period_s;
      const v = per[p] || (per[p] = [0, 0]);
      v[1] += share;
      if (at <= t) { inRow[ri] += share; v[0] += share; }
    }));
    // A row's drawn rays hold `drawn_share` of its 5 m energy; the rest is in
    // rays too faint to draw, counted in as the drawn ones come in.
    const h = Math.sqrt(m.rowHs.reduce((s, hs, ri) =>
      s + hs * hs * Math.min(1, inRow[ri] / (m.drawnShare[ri] || 1)), 0));
    const tot = Object.values(per).reduce((s, v) => s + v[1], 0);
    const ps = Object.entries(per).filter(([, v]) => v[1] >= 0.02 * tot && v[0] >= 0.5 * v[1]).map(([p]) => +p);
    return {h, longest: ps.length ? Math.max(...ps) : null, shortest: ps.length ? Math.min(...ps) : null};
  }

  const minutes = (t) => (Math.round(t) < 0 ? `${-Math.round(t)} min before` : `+${Math.round(t)} min`);
  const clock = (t) => { const r = Math.round(t); return `${r < 0 ? "−" : "+"}${Math.abs(r)} min`; };
  function readout(S) {
    const {m, t} = S;
    if (t >= m.t1 - 1e-6) {
      const whole = Math.sqrt(m.rowHs.reduce((s, hs) => s + hs * hs, 0));
      return `98% in by ${minutes(m.last)} · ${height(whole)}`;
    }
    const sf = soFar(m, t);
    if (!(sf.h > 0)) return `${minutes(t)} · on its way in`;
    if (!sf.longest) return `${minutes(t)} · ${height(sf.h)} in`;
    const ps = sf.longest === sf.shortest ? `${sf.longest.toFixed(1)} s`
      : `${sf.longest.toFixed(1)}–${sf.shortest.toFixed(1)} s`;
    return `${minutes(t)} · ${ps} in · ${height(sf.h)}`;
  }

  // ------------------------------------------------------------ state
  // A fill belongs to a BREAK, not to a map: the page redraws its cards every
  // minute on LIVE, and each redraw makes a new map. `FILLS[id]` is
  // {key, m, t, playing, started}; each map shows its break's.
  const FILLS = {};
  const FACES = new Map();         // map -> {map, id, box, svg, canvas, bar, proj}
  window.__swellFillFaces = FACES; // for checking in a browser

  L.Map.addInitHook(function () {
    const map = this;
    const F = {map, proj: null};
    FACES.set(map, F);
    map.on("move zoom viewreset resize rotate", () => { F.proj = null; paint(F); });
    map.on("zoomend moveend resize", () => place(F));
    setTimeout(() => setup(F), 0);
  });

  const fill = (F) => (F.id && FILLS[F.id]) || null;

  function setup(F) {
    const el = F.map.getContainer();
    F.box = el.closest(".sm-face");
    if (!F.box) return;
    F.svg = F.box.querySelector("svg.aperture");
    F.id = F.svg && F.svg.getAttribute("data-break");
    F.canvas = document.createElement("canvas");
    F.canvas.className = "sf-canvas";
    F.canvas.setAttribute("aria-hidden", "true");
    el.appendChild(F.canvas);
    F.bar = document.createElement("div");
    F.bar.className = "sf-bar";
    F.bar.hidden = true;
    F.bar.innerHTML = `<button type="button" class="sf-play"></button>`
      + `<div class="sf-track" role="slider" tabindex="0" aria-label="Minutes after NDBC 46232">`
      + `<span class="sf-min"></span><span class="sf-line"><span class="sf-past"></span><span class="sf-head"></span></span></div>`;
    el.appendChild(F.bar);
    L.DomEvent.disableClickPropagation(F.bar);
    L.DomEvent.disableScrollPropagation(F.bar);
    F.bar.querySelector(".sf-play").addEventListener("click", (e) => { e.stopPropagation(); toggle(F); });
    const track = F.bar.querySelector(".sf-track");
    track.addEventListener("pointerdown", (e) => {
      const S = fill(F);
      if (!S) return;
      e.preventDefault(); e.stopPropagation();
      S.playing = false;
      start(F, S);
      track.setPointerCapture(e.pointerId);
      const line = track.querySelector(".sf-line");
      const move = (ev) => {
        const r = line.getBoundingClientRect();
        const f = Math.max(0, Math.min(1, (ev.clientX - r.left) / r.width));
        S.t = S.m.t0 + f * (S.m.t1 - S.m.t0);
        render(F);
      };
      move(e);
      const up = () => { track.removeEventListener("pointermove", move); track.removeEventListener("pointerup", up); };
      track.addEventListener("pointermove", move);
      track.addEventListener("pointerup", up);
    });
    track.addEventListener("keydown", (e) => {
      const S = fill(F);
      if (!S || (e.key !== "ArrowLeft" && e.key !== "ArrowRight")) return;
      e.preventDefault();
      S.playing = false;
      start(F, S);
      S.t = Math.max(S.m.t0, Math.min(S.m.t1, S.t + (e.key === "ArrowLeft" ? -1 : 1)));
      render(F);
    });
    if (F.svg) new MutationObserver(() => sync(F)).observe(F.svg, {attributes: true, subtree: true, attributeFilter: ["class", "hidden"]});
    new MutationObserver(() => sync(F)).observe(el, {attributes: true, attributeFilter: ["hidden"]});
    sync(F);
    const S = fill(F);
    if (S && S.playing) run();
  }

  // After a pick: LIVE, a train (or one swell's rows) picked, and this
  // break's rays built. The timeline shows at once, at its start; the rays
  // only once played or scrubbed. Any other pick ends the fill.
  function sync(F) {
    if (!F.box || !F.svg || !F.svg.isConnected) return;
    const el = F.map.getContainer();
    const key = g("PICKED", {})[F.id] || null;
    const ok = live() && !el.hidden && rowsOf(key).some((n) => (RAYS.breaks[F.id] || {rows: []}).rows[n]);
    let S = fill(F);
    if (S && (!ok || S.key !== key)) { end(F); S = null; }
    if (ok && !S) {
      const m = model(F.id, rowsOf(key));
      if (m) S = FILLS[F.id] = {key, m, t: m.t0, playing: false, started: false};
    }
    F.bar.hidden = !S;
    place(F);
    render(F);
  }

  function place(F) {
    if (!F.bar) return;
    const el = F.map.getContainer();
    const ctl = el.querySelector(".leaflet-bottom.leaflet-right");
    F.bar.style.right = `${ctl ? ctl.offsetWidth + 8 : 96}px`;
    const dpr = window.devicePixelRatio || 1, w = el.clientWidth, h = el.clientHeight;
    if (F.canvas.width !== Math.round(w * dpr) || F.canvas.height !== Math.round(h * dpr)) {
      F.canvas.width = Math.round(w * dpr); F.canvas.height = Math.round(h * dpr);
      F.proj = null;
      paint(F);
    }
  }

  function setIcon(F, S) {
    const b = F.bar.querySelector(".sf-play");
    const mode = S && S.playing ? "pause" : S && S.started && S.t >= S.m.t1 - 1e-6 ? "again" : "play";
    if (b.dataset.mode === mode) return;
    b.dataset.mode = mode;
    b.innerHTML = ICON[mode];
    b.setAttribute("aria-label", mode === "pause" ? "Pause the swell filling in"
      : mode === "again" ? "Play the swell filling in again" : "Play the swell filling in");
  }

  // The fill ends: the page's own caption for the pick comes back.
  function end(F) {
    delete FILLS[F.id];
    F.proj = null;
    paint(F);
    F.box.classList.remove("sf-filling");
    const faces = [...F.svg.querySelectorAll("text.faces")].find((t) => !t.hasAttribute("hidden"));
    const cap = F.box.querySelector(".sm-cap");
    if (cap && faces) cap.textContent = [...faces.querySelectorAll("tspan")].map((s) => s.textContent).join(" ");
  }

  // The first play or scrub: the arrows give way, and the map frames the rays.
  function start(F, S) {
    if (S.started) return;
    S.started = true;
    F.box.classList.add("sf-filling");
    frame(F, S);
  }

  // Frame the rays: the shore normal up, as the map always is, and every
  // drawn ray from where it leaves deep water to the break in view.
  function frame(F, S) {
    const map = F.map, b = RAYS.breaks[F.id];
    const normal = -map.getBearing();
    const p0 = b.start;
    const kmLat = 111.32, kmLon = 111.32 * Math.cos(rad(p0[0]));
    const up = [Math.sin(rad(normal)), Math.cos(rad(normal))];          // east, north
    const side = [Math.cos(rad(normal)), -Math.sin(rad(normal))];
    let a0 = 0, a1 = 0, s0 = 0, s1 = 0;
    S.m.rays.forEach(({ray, e}) => {
      if (e < 0.05 * S.m.ref) return;
      ray.pts.forEach(([la, lo]) => {
        const dx = (lo - p0[1]) * kmLon, dy = (la - p0[0]) * kmLat;
        const al = dx * up[0] + dy * up[1], sd = dx * side[0] + dy * side[1];
        a0 = Math.min(a0, al); a1 = Math.max(a1, al); s0 = Math.min(s0, sd); s1 = Math.max(s1, sd);
      });
    });
    const el = map.getContainer(), W = el.clientWidth, H = el.clientHeight;
    const kmW = (s1 - s0) * 1.12, kmH = (a1 - a0) * 1.15 + 0.5;
    const mpp = Math.max(kmW * 1000 / W, kmH * 1000 / H);
    const zoom = Math.max(map.getMinZoom(), Math.log2(156543.03392 * Math.cos(rad(p0[0])) / mpp));
    const ca = (a0 + a1) / 2 - 0.25, cs = (s0 + s1) / 2;
    const cdx = ca * up[0] + cs * side[0], cdy = ca * up[1] + cs * side[1];
    map.setView([p0[0] + cdy / kmLat, p0[1] + cdx / kmLon], zoom, {animate: !REDUCED.matches});
  }

  let RAF = 0, LAST = 0;
  function run() {
    LAST = performance.now();
    if (!RAF) RAF = requestAnimationFrame(tick);
  }

  function toggle(F) {
    const S = fill(F);
    if (!S) return;
    start(F, S);
    if (REDUCED.matches) {
      S.playing = false; S.t = S.m.t1;
    } else if (S.playing) {
      S.playing = false;
    } else {
      if (S.t >= S.m.t1 - 1e-6) S.t = S.m.t0;
      S.playing = true;
      run();
    }
    render(F);
  }

  // One clock per break; each map shows its own break's.
  function tick(now) {
    RAF = 0;
    const dt = Math.min(now - LAST, 100);
    LAST = now;
    let more = false;
    Object.values(FILLS).forEach((S) => {
      if (!S.playing) return;
      if (!live()) { S.playing = false; return; }
      S.t = Math.min(S.m.t1, S.t + dt * (S.m.t1 - S.m.t0) / PLAY_MS);
      if (S.t >= S.m.t1) S.playing = false;
      more = more || S.playing;
    });
    FACES.forEach((F, map) => {
      if (!F.svg || !F.svg.isConnected) { FACES.delete(map); return; }
      if (fill(F)) render(F);
    });
    if (more) RAF = requestAnimationFrame(tick);
  }

  function render(F) {
    if (!F.bar) return;
    const S = fill(F);
    setIcon(F, S);
    if (!S) return;
    const f = (S.t - S.m.t0) / (S.m.t1 - S.m.t0);
    F.bar.querySelector(".sf-min").textContent = clock(S.t);
    F.bar.querySelector(".sf-past").style.width = `${(100 * f).toFixed(2)}%`;
    F.bar.querySelector(".sf-head").style.left = `${(100 * f).toFixed(2)}%`;
    const track = F.bar.querySelector(".sf-track");
    track.setAttribute("aria-valuemin", Math.round(S.m.t0));
    track.setAttribute("aria-valuemax", Math.round(S.m.t1));
    track.setAttribute("aria-valuenow", Math.round(S.t));
    if (!S.started) return;
    F.box.classList.add("sf-filling");
    const text = readout(S);
    track.setAttribute("aria-valuetext", text);
    const cap = F.box.querySelector(".sm-cap");
    if (cap && cap.textContent !== text) cap.textContent = text;
    paint(F);
  }

  function project(F, S) {
    if (F.proj && F.projFor === S.m) return F.proj;
    const map = F.map;
    F.projFor = S.m;
    F.proj = S.m.rays.map(({ray}) => ray.pts.map(([la, lo]) => {
      const p = map.latLngToContainerPoint([la, lo]);
      return [p.x, p.y];
    }));
    return F.proj;
  }

  function paint(F) {
    if (!F.canvas) return;
    const ctx = F.canvas.getContext("2d");
    const dpr = window.devicePixelRatio || 1;
    ctx.setTransform(1, 0, 0, 1, 0, 0);
    ctx.clearRect(0, 0, F.canvas.width, F.canvas.height);
    const S = fill(F);
    if (!S || !S.started || F.map.getContainer().hidden) return;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    const proj = project(F, S), t = S.t;
    ctx.globalCompositeOperation = "lighter";
    ctx.strokeStyle = RAY;
    ctx.fillStyle = RAY;
    ctx.lineWidth = 1.3;
    ctx.lineJoin = "round";
    S.m.rays.forEach(({ray, e}, n) => {
      const pts = ray.pts, xy = proj[n];
      if (t <= pts[0][2]) return;
      const a = Math.min(1, 0.9 * e / S.m.ref);
      if (a < 0.01) return;
      ctx.globalAlpha = a;
      ctx.beginPath();
      ctx.moveTo(xy[0][0], xy[0][1]);
      let k = 1, fx = xy[0][0], fy = xy[0][1];
      for (; k < pts.length && pts[k][2] <= t; k++) { ctx.lineTo(xy[k][0], xy[k][1]); fx = xy[k][0]; fy = xy[k][1]; }
      if (k < pts.length) {
        const u = (t - pts[k - 1][2]) / (pts[k][2] - pts[k - 1][2]);
        fx = xy[k - 1][0] + u * (xy[k][0] - xy[k - 1][0]);
        fy = xy[k - 1][1] + u * (xy[k][1] - xy[k - 1][1]);
        ctx.lineTo(fx, fy);
      }
      ctx.stroke();
      if (k < pts.length) {             // the front, while it is still on its way
        ctx.globalAlpha = Math.min(1, a * 1.6);
        ctx.beginPath();
        ctx.arc(fx, fy, 1.6, 0, 2 * Math.PI);
        ctx.fill();
      }
    });
    ctx.globalAlpha = 1;
    ctx.globalCompositeOperation = "source-over";
  }

  window.addEventListener("resize", () => FACES.forEach((F) => { place(F); F.proj = null; paint(F); }));
})();
