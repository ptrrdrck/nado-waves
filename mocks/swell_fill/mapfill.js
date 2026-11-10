// Swell fill on the map (MOCK, 2026-11-10, option B): on the LIVE tab, a
// picked train's energy coming in along its rays' REAL paths over the seabed,
// on the Swell card's map (mocks/swell_map).
//
// Every ray is one row of the break's transfer table, re-traced with its
// path recorded (mocks/swell_fill/rays.py, checked against raytrace.trace):
// from 15 km seaward of where it leaves deep water, straight, then bent over
// the seabed to the 5 m start point off the break. Its brightness is the
// train's energy it carries to 5 m, as nearshore.carry credits it; what
// diffraction adds is drawn on the clearing ray of the same period nearest
// the heading the table credits it to. The clock is minutes after the same
// wave group passed NDBC 46232 (raytrace.leg_table's arithmetic): long
// periods arrive first. Nothing here is a wave field or a crest.
//
// Loaded after Leaflet and before swellmap.js, so it sees every map made.
(function () {
  "use strict";
  const RAYS = window.__SWELLRAYS__;
  if (!RAYS || !window.L) return;

  const PLAY_MS = 12000;
  const LEAD_MIN = 40;           // the clock starts this long before 2% of the energy is in
  const RAY = "#ffd84d";         // the map's pick colour
  const REDUCED = matchMedia("(prefers-reduced-motion: reduce)");
  const ICON = {
    play: '<svg viewBox="0 0 12 12" aria-hidden="true"><path d="M3 1.5v9l7.5-4.5z"/></svg>',
    pause: '<svg viewBox="0 0 12 12" aria-hidden="true"><rect x="2" y="1.5" width="3" height="9" rx=".5"/>'
      + '<rect x="7" y="1.5" width="3" height="9" rx=".5"/></svg>',
    again: '<svg class="stroke" viewBox="0 0 12 12" aria-hidden="true"><path d="M2.2 6.6A3.9 3.9 0 1 0 3.4 3.1"/>'
      + '<path d="M3.6 0.9v2.4H1.2"/></svg>',
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
    const first = pct(0.02), last = pct(0.98);
    return {
      id, rows, rays, ref, total, byRow,
      rowHs: rows.map((n) => b.rows[n].row_hs_m),
      drawnShare: rows.map((n) => b.rows[n].drawn_share),
      t0: first - LEAD_MIN, t1: last + 3, first, last,
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
  function readout(F) {
    const {m, t} = F;
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

  // ------------------------------------------------------------ one map's fill
  const FACES = new Map();         // map -> face state

  L.Map.addInitHook(function () {
    const map = this;
    const F = {map, t: 0, playing: false, m: null, key: null, proj: null, seabed: null, tilesFailed: false};
    FACES.set(map, F);
    map.on("layeradd", (e) => {
      if (e.layer instanceof L.TileLayer && !e.layer._sfWatched) {
        e.layer._sfWatched = true;
        e.layer.on("tileerror", () => { F.tilesFailed = true; seabed(F, true); });
      }
    });
    map.on("move zoom viewreset resize rotate", () => { F.proj = null; if (F.m) paint(F); });
    map.on("zoomend moveend", () => { if (F.m) place(F); });
    setTimeout(() => setup(F), 0);
  });

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
      + `<span class="sf-min"></span><span class="sf-line"><span class="sf-done"></span><span class="sf-head"></span></span></div>`;
    el.appendChild(F.bar);
    L.DomEvent.disableClickPropagation(F.bar);
    L.DomEvent.disableScrollPropagation(F.bar);
    F.bar.querySelector(".sf-play").addEventListener("click", (e) => { e.stopPropagation(); toggle(F); });
    const track = F.bar.querySelector(".sf-track");
    track.addEventListener("pointerdown", (e) => {
      if (!F.m) return;
      e.preventDefault(); e.stopPropagation();
      F.playing = false;
      track.setPointerCapture(e.pointerId);
      const line = track.querySelector(".sf-line");
      const move = (ev) => {
        const r = line.getBoundingClientRect();
        const f = Math.max(0, Math.min(1, (ev.clientX - r.left) / r.width));
        F.t = F.m.t0 + f * (F.m.t1 - F.m.t0);
        render(F);
      };
      move(e);
      const up = () => { track.removeEventListener("pointermove", move); track.removeEventListener("pointerup", up); };
      track.addEventListener("pointermove", move);
      track.addEventListener("pointerup", up);
    });
    track.addEventListener("keydown", (e) => {
      if (!F.m || (e.key !== "ArrowLeft" && e.key !== "ArrowRight")) return;
      e.preventDefault();
      F.playing = false;
      F.t = Math.max(F.m.t0, Math.min(F.m.t1, F.t + (e.key === "ArrowLeft" ? -1 : 1)));
      render(F);
    });
    if (F.svg) new MutationObserver(() => sync(F)).observe(F.svg, {attributes: true, subtree: true, attributeFilter: ["class", "hidden"]});
    new MutationObserver(() => sync(F)).observe(el, {attributes: true, attributeFilter: ["hidden"]});
    sync(F);
  }

  // The seabed under the rays: shown while a fill is, and whenever the
  // imagery cannot load (an artifact's host blocks tile servers).
  function seabed(F, on) {
    const map = F.map;
    if (on && !F.seabed && RAYS.seabed) {
      // The finer picture over the breaks sits on the wide one.
      F.seabed = RAYS.seabed.layers.map((s) =>
        L.imageOverlay(s.png, s.bounds, {interactive: false, opacity: 1}).addTo(map));
      F.seabed.slice().reverse().forEach((l) => l.bringToBack());
    } else if (!on && F.seabed && !F.tilesFailed) {
      F.seabed.forEach((l) => map.removeLayer(l));
      F.seabed = null;
    }
    const attr = map.getContainer().querySelector(".sm-attr");
    if (attr) {
      if (!attr.dataset.imagery) attr.dataset.imagery = attr.textContent;
      attr.textContent = F.seabed ? `Seabed ${RAYS.seabed.source.split(",")[0]}` : attr.dataset.imagery;
    }
  }

  function sync(F) {
    if (!F.box || !F.svg || !F.svg.isConnected) return;
    const el = F.map.getContainer();
    const key = g("PICKED", {})[F.id] || null;
    const ok = live() && !el.hidden && rowsOf(key).some((n) => (RAYS.breaks[F.id] || {rows: []}).rows[n]);
    if (F.m && (!ok || F.key !== key)) stop(F);
    F.bar.hidden = !ok;
    if (ok) { place(F); setIcon(F); }
    if (F.m) render(F);
  }

  function place(F) {
    const el = F.map.getContainer();
    const ctl = el.querySelector(".leaflet-bottom.leaflet-right");
    const right = ctl ? ctl.offsetWidth + 8 : 96;
    F.bar.style.right = `${right}px`;
    const dpr = window.devicePixelRatio || 1, w = el.clientWidth, h = el.clientHeight;
    if (F.canvas.width !== Math.round(w * dpr) || F.canvas.height !== Math.round(h * dpr)) {
      F.canvas.width = Math.round(w * dpr); F.canvas.height = Math.round(h * dpr);
      F.proj = null;
    }
  }

  function setIcon(F) {
    const b = F.bar.querySelector(".sf-play");
    const mode = F.playing ? "pause" : F.m && F.t >= F.m.t1 - 1e-6 ? "again" : "play";
    if (b.dataset.mode === mode) return;
    b.dataset.mode = mode;
    b.innerHTML = ICON[mode];
    b.setAttribute("aria-label", mode === "pause" ? "Pause the swell filling in"
      : mode === "again" ? "Play the swell filling in again" : "Play the swell filling in");
  }

  function stop(F) {
    F.m = null; F.playing = false; F.key = null; F.proj = null;
    const ctx = F.canvas.getContext("2d");
    ctx.setTransform(1, 0, 0, 1, 0, 0);
    ctx.clearRect(0, 0, F.canvas.width, F.canvas.height);
    F.box.classList.remove("sf-filling", "sf-complete");
    seabed(F, false);
    F.bar.querySelector(".sf-min").textContent = "";
    F.bar.querySelector(".sf-done").style.width = "0";
    F.bar.querySelector(".sf-head").style.left = "0";
    // The caption back: the page's own words for the pick.
    const faces = [...F.svg.querySelectorAll("text.faces")].find((t) => !t.hasAttribute("hidden"));
    const cap = F.box.querySelector(".sm-cap");
    if (cap && faces) cap.textContent = [...faces.querySelectorAll("tspan")].map((s) => s.textContent).join(" ");
    setIcon(F);
  }

  // Frame the rays: the shore normal up, as the map always is, and every
  // drawn ray from where it leaves deep water to the break in view.
  function frame(F) {
    const map = F.map, b = RAYS.breaks[F.id];
    const normal = -map.getBearing();
    const p0 = b.start;
    const kmLat = 111.32, kmLon = 111.32 * Math.cos(rad(p0[0]));
    const up = [Math.sin(rad(normal)), Math.cos(rad(normal))];          // east, north
    const side = [Math.cos(rad(normal)), -Math.sin(rad(normal))];
    let a0 = 0, a1 = 0, s0 = 0, s1 = 0;
    F.m.rays.forEach(({ray, e}) => {
      if (e < 0.05 * F.m.ref) return;
      ray.pts.slice(1).forEach(([la, lo]) => {
        const dx = (lo - p0[1]) * kmLon, dy = (la - p0[0]) * kmLat;
        const al = dx * up[0] + dy * up[1], sd = dx * side[0] + dy * side[1];
        a0 = Math.min(a0, al); a1 = Math.max(a1, al); s0 = Math.min(s0, sd); s1 = Math.max(s1, sd);
      });
    });
    const el = map.getContainer(), W = el.clientWidth, H = el.clientHeight;
    const kmW = (s1 - s0) * 1.12, kmH = (a1 - a0) * 1.15 + 0.5;
    const mpp = Math.max(kmW * 1000 / W, kmH * 1000 / H);
    const zoom = Math.log2(156543.03392 * Math.cos(rad(p0[0])) / mpp);
    const ca = (a0 + a1) / 2 - 0.25, cs = (s0 + s1) / 2;
    const cdx = ca * up[0] + cs * side[0], cdy = ca * up[1] + cs * side[1];
    map.setView([p0[0] + cdy / kmLat, p0[1] + cdx / kmLon], zoom, {animate: !REDUCED.matches});
  }

  let RAF = 0, LAST = 0;
  function toggle(F) {
    const key = g("PICKED", {})[F.id] || null;
    if (!F.m) {
      const m = model(F.id, rowsOf(key));
      if (!m) return;
      F.m = m; F.key = key; F.t = m.t0;
      F.box.classList.add("sf-filling");
      seabed(F, true);
      place(F);
      frame(F);
    }
    if (REDUCED.matches) {
      F.playing = false; F.t = F.m.t1;
    } else if (F.playing) {
      F.playing = false;
    } else {
      if (F.t >= F.m.t1 - 1e-6) F.t = F.m.t0;
      F.playing = true;
      LAST = performance.now();
      if (!RAF) RAF = requestAnimationFrame(tick);
    }
    render(F);
  }

  function tick(now) {
    RAF = 0;
    const dt = Math.min(now - LAST, 100);
    LAST = now;
    let more = false;
    FACES.forEach((F) => {
      if (!F.m) return;
      if (!live() || !F.svg.isConnected || F.map.getContainer().hidden) { stop(F); return; }
      if (F.playing) {
        F.t = Math.min(F.m.t1, F.t + dt * (F.m.t1 - F.m.t0) / PLAY_MS);
        if (F.t >= F.m.t1) F.playing = false;
        render(F);
        more = more || F.playing;
      }
    });
    if (more) RAF = requestAnimationFrame(tick);
  }

  function render(F) {
    if (!F.m) return;
    const done = F.t >= F.m.t1 - 1e-6;
    F.box.classList.toggle("sf-complete", done);
    const f = (F.t - F.m.t0) / (F.m.t1 - F.m.t0);
    const r = Math.round(F.t);
    F.bar.querySelector(".sf-min").textContent = `${r < 0 ? "\u2212" : "+"}${Math.abs(r)} min`;
    F.bar.querySelector(".sf-done").style.width = `${(100 * f).toFixed(2)}%`;
    F.bar.querySelector(".sf-head").style.left = `${(100 * f).toFixed(2)}%`;
    const track = F.bar.querySelector(".sf-track");
    track.setAttribute("aria-valuemin", Math.round(F.m.t0));
    track.setAttribute("aria-valuemax", Math.round(F.m.t1));
    track.setAttribute("aria-valuenow", Math.round(F.t));
    const text = readout(F);
    track.setAttribute("aria-valuetext", text);
    const cap = F.box.querySelector(".sm-cap");
    if (cap && cap.textContent !== text) cap.textContent = text;
    setIcon(F);
    paint(F);
  }

  function project(F) {
    if (F.proj) return F.proj;
    const map = F.map;
    F.proj = F.m.rays.map(({ray}) => ray.pts.map(([la, lo]) => {
      const p = map.latLngToContainerPoint([la, lo]);
      return [p.x, p.y];
    }));
    return F.proj;
  }

  function paint(F) {
    const ctx = F.canvas.getContext("2d");
    const dpr = window.devicePixelRatio || 1;
    ctx.setTransform(1, 0, 0, 1, 0, 0);
    ctx.clearRect(0, 0, F.canvas.width, F.canvas.height);
    if (!F.m) return;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    const proj = project(F), t = F.t;
    ctx.globalCompositeOperation = "lighter";
    ctx.strokeStyle = RAY;
    ctx.fillStyle = RAY;
    ctx.lineWidth = 1.3;
    ctx.lineJoin = "round";
    F.m.rays.forEach(({ray, e}, n) => {
      const pts = ray.pts, xy = proj[n];
      if (t <= pts[0][2]) return;
      const a = Math.min(1, 0.9 * e / F.m.ref);
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

  window.addEventListener("resize", () => FACES.forEach((F) => { if (F.m) { place(F); F.proj = null; paint(F); } }));
})();
