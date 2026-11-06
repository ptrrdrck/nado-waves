// The back of the Swell card (MOCK, 2026-11-06): the geometry the model uses,
// from forecast.geomviz, drawn over Esri World Imagery with Leaflet. It reads
// the page's own helpers (point, compass, dualText, shortBlocker, heightText,
// selectSwellTab) and never re-derives a window: every fan, edge and vertex
// is the model's. The imagery is a photograph under it, not an input.
(function () {
  "use strict";
  const MODEL = window.__SWELLMAP_MODEL__;
  if (!MODEL || !window.L) return;
  const ESRI = "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}";
  const ATTR = 'Imagery <a href="https://www.esri.com/" target="_blank" rel="noopener">Esri</a>, Maxar, Earthstar Geographics';
  const FAN_KM = 40;          // how far a window or shadow is drawn out to sea
  const BUOY = "buoy";
  const REDUCED = matchMedia("(prefers-reduced-motion: reduce)").matches;
  const TOUCH = matchMedia("(pointer: coarse)").matches;
  const ICON_MAP = '<svg viewBox="0 0 16 16" aria-hidden="true"><path d="M1.5 3.5l4-1.5 5 2 4-1.5v10l-4 1.5-5-2-4 1.5z"/><path d="M5.5 2v10M10.5 4v10"/></svg>';
  const ICON_CARD = '<svg viewBox="0 0 16 16" aria-hidden="true"><rect x="2" y="3" width="12" height="10" rx="1.5"/><path d="M2 6.5h12"/></svg>';
  const ICON_FIT = '<svg viewBox="0 0 16 16" aria-hidden="true"><path d="M2 6V2h4M10 2h4v4M14 10v4h-4M6 14H2v-4"/></svg>';

  // --- the page's own helpers, with stand-ins so the mock never throws ---
  const has = (n) => typeof window[n] === "function" || (function () { try { return typeof eval(n) === "function"; } catch (e) { return false; } })();
  const call = (n, ...a) => { try { return eval(n)(...a); } catch (e) { return null; } };
  const ptOf = (d) => call("point", d) || "";
  const compassOf = (d) => call("compass", d) || `${ptOf(d)} ${Math.round(d)}°`;
  const blk = (n) => call("shortBlocker", n) || n;
  const dual = (imp, met) => call("dualText", imp, met) || `${imp} (${met})`;
  const ht = (m) => call("heightText", m) || `${(m * 3.28084).toFixed(1)} ft (${m.toFixed(2)} m)`;
  const MI = (() => { try { return eval("MI_PER_KM"); } catch (e) { return 0.621371; } })();
  const dist = (km) => dual(`${(km * MI).toFixed(km * MI < 10 ? 1 : 0)}\u00a0mi`, `${km.toFixed(km < 10 ? 1 : 0)}\u00a0km`);
  const deg = (b) => `${Math.round(((b % 360) + 360) % 360)}°`;

  // --- spherical geometry: the same great circles forecast.swell uses ---
  const rad = (d) => d * Math.PI / 180, dg = (r) => r * 180 / Math.PI;
  function dest(p, brg, km) {
    const d = km / 6371.0088, t = rad(brg), f1 = rad(p[0]), l1 = rad(p[1]);
    const f2 = Math.asin(Math.sin(f1) * Math.cos(d) + Math.cos(f1) * Math.sin(d) * Math.cos(t));
    const l2 = l1 + Math.atan2(Math.sin(t) * Math.sin(d) * Math.cos(f1), Math.cos(d) - Math.sin(f1) * Math.sin(f2));
    return [dg(f2), dg(l2)];
  }
  function gc(p, q) {
    const f1 = rad(p[0]), f2 = rad(q[0]), df = f2 - f1, dl = rad(q[1] - p[1]);
    const a = Math.sin(df / 2) ** 2 + Math.cos(f1) * Math.cos(f2) * Math.sin(dl / 2) ** 2;
    const km = 2 * 6371.0088 * Math.asin(Math.sqrt(a));
    const brg = (dg(Math.atan2(Math.sin(dl) * Math.cos(f2),
      Math.cos(f1) * Math.sin(f2) - Math.sin(f1) * Math.cos(f2) * Math.cos(dl))) + 360) % 360;
    return {km, brg};
  }
  function fan(p, from, to, km = FAN_KM) {
    const pts = [p];
    const span = ((to - from) % 360 + 360) % 360;
    const n = Math.max(2, Math.ceil(span));
    for (let i = 0; i <= n; i++) pts.push(dest(p, from + span * i / n, km));
    pts.push(p);
    return pts;
  }

  // --- which chain and which break the front is showing ---
  const chain = () => (document.querySelector('#tab-forecast[aria-selected="true"]') ? "forecast" : "now");
  const frontTab = () => {
    const b = document.querySelector('.cond.swell [data-swell-tab][aria-selected="true"]');
    return b ? b.dataset.swellTab : "coronado_center";
  };
  const reading = (id) => {
    if (chain() !== "now") return null;      // the mock carries LIVE's numbers only
    const now = (window.__MOCK_DATA__ || {})["now.json"];
    return now && (now.breaks || []).find((b) => b.id === id) || null;
  };
  const brk = (id) => MODEL.breaks.find((b) => b.id === id);
  const NAME = {coronado_north: "North", coronado_center: "Center", coronado_south: "South"};

  // --- state ---
  let back = null, map = null, layer = null, tab = null, picked = null, captions = {}, flipping = false;

  function caption(key) {
    const el = back && back.querySelector(".sm-cap");
    if (el) el.innerHTML = captions[key] || captions.default || "";
  }

  // One break's windows and shadows, as the front's drawing has them: the
  // shadows are whatever the seaward half-plane's windows leave, each cast by
  // the land that closes the window before it.
  function drawBreak(id) {
    const b = brk(id); if (!b) return;
    const c = reading(id);
    const p = b.position, wins = b.windows.slice().sort((x, y) => x.from - y.from);
    const lo = b.normal - 90, hi = b.normal + 90;
    const rel = (x) => ((x - b.normal) % 360 + 540) % 360 - 180;
    captions = {default: `<b>${NAME[id] || b.name}</b> facing ${compassOf(b.normal)}`};
    const pick = (key, lyr) => lyr.on("click", (e) => { L.DomEvent.stop(e); select(key); });

    // Shadows.
    const shadows = [];
    let from = lo;
    wins.forEach((w) => {
      if (rel(w.from) > rel(from) + 0.01) shadows.push({from, to: w.from, by: w.edges.find((e) => e.side === "low").blocker});
      from = w.to;
    });
    if (rel(hi) > rel(from) + 0.01) shadows.push({from, to: hi, by: wins[wins.length - 1].edges.find((e) => e.side === "high").blocker});
    shadows.forEach((s, i) => {
      const key = `s${i}`;
      const tb = c && (c.taken_by || []).find((t) => t.blocker === s.by);
      captions[key] = `<b>${s.by}</b>` + (c ? (tb ? `, blocking ${Math.round(100 * tb.share)}% of this swell` : ", blocking none of this swell") : "")
        + ` · ${deg(s.from)}–${deg(s.to)}`;
      pick(key, L.polygon(fan(p, s.from, s.to), {className: "sm-sec", color: "#000", weight: 0, fillColor: "#000",
        fillOpacity: 0.3, _key: key}).addTo(layer));
    });

    // Windows, each edge a ray to the one vertex that forms it.
    wins.forEach((w, i) => {
      const key = `w${i}`;
      const low = w.edges.find((e) => e.side === "low"), high = w.edges.find((e) => e.side === "high");
      captions[key] = `<b>${blk(low.blocker)} → ${blk(high.blocker)}</b>, ${ptOf(midOf(w.from, w.to))}, ${Math.round(w.span)}° wide · ${deg(w.from)}–${deg(w.to)}`;
      pick(key, L.polygon(fan(p, w.from, w.to), {color: "#fff", weight: 0, fillColor: "#fff", fillOpacity: 0.04, _key: key}).addTo(layer));
    });
    wins.forEach((w, i) => w.edges.forEach((e) => {
      const key = `v${i}${e.side[0]}`;
      L.polyline([p, e.vertex], {color: "#000", weight: 3.5, opacity: 0.35, interactive: false}).addTo(layer);
      L.polyline([p, e.vertex], {color: "#fff", weight: 1.5, opacity: 0.95, interactive: false}).addTo(layer);
      L.polyline([e.vertex, dest(p, e.bearing, FAN_KM)], {color: "#fff", weight: 1, opacity: 0.6, dashArray: "3 5", interactive: false}).addTo(layer);
      captions[key] = `<b>${e.blocker}</b>, the vertex that forms the ${deg(e.bearing)} edge · ${dist(e.range_km)} from this break`;
      pick(key, L.circleMarker(e.vertex, {radius: 4.5, color: "#fff", weight: 2, fillColor: "#000", fillOpacity: 0.6, _key: key}).addTo(layer));
    }));
    // The two outermost edges carry their degrees, as on the front.
    const ends = [wins[0].edges.find((e) => e.side === "low"), wins[wins.length - 1].edges.find((e) => e.side === "high")];
    ends.forEach((e) => label(dest(p, e.bearing, Math.min(e.range_km + 4, FAN_KM - 6)), deg(e.bearing)));

    // Trains, in from the sea along the heading each arrives from offshore.
    if (c) (c.trains || []).forEach((t, i) => {
      if (t.local || t.wind_sea || !isFinite(t.from_deg) || Math.abs(rel(t.from_deg)) >= 90) return;
      const key = `t${i}`, lead = i === 0;
      const a = dest(p, t.from_deg, lead ? 11 : 9), z = dest(p, t.from_deg, 1.4);
      captions[key] = `<b>${ht(t.hs_m)}</b> at ${t.period_s.toFixed(1)} s from ${ptOf(t.from_deg)} ${deg(t.from_deg)}, offshore`;
      L.polyline([a, z], {color: "#000", weight: lead ? 6 : 4.5, opacity: 0.35, interactive: false}).addTo(layer);
      pick(key, L.polyline([a, z], {color: "#fff", weight: lead ? 3 : 2, opacity: 1, _key: key}).addTo(layer));
      // The head is drawn in screen pixels, so it stays a head at every zoom.
      const sz = lead ? 16 : 13;
      const head = L.marker(z, {keyboard: false, _key: key, icon: L.divIcon({className: "sm-head-icon", iconSize: [sz, sz],
        html: `<svg viewBox="0 0 16 16" width="${sz}" height="${sz}" style="transform:rotate(${(t.from_deg + 180) % 360}deg)">`
          + `<path d="M8 15 L2 3 L8 6 L14 3 Z" fill="#fff" stroke="#000" stroke-opacity=".45" stroke-width="1"/></svg>`})}).addTo(layer);
      pick(key, head);
    });
    return [p, ...wins.flatMap((w) => w.edges.map((e) => e.vertex))];
  }
  const midOf = (a, b) => (call("midBearing", a, b) ?? (a + (((b - a) % 360 + 360) % 360) / 2));

  function label(at, text, cls = "sm-deg") {
    L.marker(at, {interactive: false, keyboard: false,
      icon: L.divIcon({className: cls, html: `<span>${text}</span>`, iconSize: [0, 0]})}).addTo(layer);
  }

  // The land the model has, as the model has it: Point Loma's charted hull,
  // and the islands' and Baja's edges, so the photograph shows how few
  // vertices the windows stand on.
  function drawBlockers() {
    MODEL.blockers.forEach((b) => {
      const line = b.outline && b.outline.length > 2 ? b.outline : [b.a, b.b];
      L.polyline(line, {color: "#fff", weight: 1.25, opacity: 0.85, dashArray: "2 4", interactive: false}).addTo(layer);
    });
  }

  function drawBreaks(selected) {
    MODEL.breaks.forEach((b) => {
      const on = b.id === selected;
      L.polyline(b.chord, {color: "#000", weight: on ? 6 : 4, opacity: 0.4, interactive: false}).addTo(layer);
      L.polyline(b.chord, {color: "#fff", weight: on ? 3 : 2, opacity: on ? 1 : 0.8, interactive: false}).addTo(layer);
      const dot = L.circleMarker(b.position, {radius: on ? 5.5 : 4, color: on ? "#000" : "#fff", weight: on ? 2 : 1.5,
        fillColor: on ? "#fff" : "#000", fillOpacity: 1}).addTo(layer);
      dot.on("click", (e) => { L.DomEvent.stop(e); choose(b.id); });
      if (!on || tab === BUOY) label(b.position, NAME[b.id] || b.id, "sm-tag sm-near");
    });
    label(brk("coronado_center").position, "Coronado", "sm-tag sm-far");
  }

  function drawBuoy() {
    const q = MODEL.buoy.position; if (!q) return null;
    const name = MODEL.buoy.cdip ? `CDIP ${MODEL.buoy.cdip}` : `NDBC ${MODEL.buoy.id}`;
    const c = brk("coronado_center"), g = gc(c.position, q);
    captions.buoy = `<b>${name}</b>, Point Loma South · ${dist(g.km)} ${ptOf(g.brg)} of Center break`;
    const m = L.circleMarker(q, {radius: 6, color: "#fff", weight: 2, fillColor: "#000", fillOpacity: 0.7}).addTo(layer);
    m.on("click", (e) => { L.DomEvent.stop(e); select("buoy"); });
    label(q, name, "sm-tag");
    return q;
  }

  function render(fit) {
    layer.clearLayers();
    picked = null;
    let pts;
    if (tab === BUOY) {
      captions = {};
      drawBlockers(); drawBreaks(null);
      const q = drawBuoy();
      captions.default = captions.buoy;
      pts = [q, ...MODEL.breaks.map((b) => b.position), ...MODEL.blockers.flatMap((b) => [b.a, b.b])].filter(Boolean);
    } else {
      drawBlockers();
      pts = drawBreak(tab) || [];
      drawBreaks(tab);
      drawBuoy();
    }
    caption("default");
    back._bounds = L.latLngBounds(pts);
    if (fit) map.fitBounds(back._bounds, {padding: [14, 14], animate: false});
    syncTabs();
  }

  function select(key) {
    picked = picked === key ? null : key;
    layer.eachLayer((l) => {
      if (!l.options._key) return;
      const on = l.options._key === picked;
      if (l instanceof L.Polygon && l.options.fillColor === "#000") l.setStyle({fillOpacity: on ? 0.55 : 0.3});
      else if (l instanceof L.Polygon && l.options.weight === 0) l.setStyle({fillOpacity: on ? 0.22 : 0.04});
    });
    caption(picked || "default");
  }

  function choose(id) {
    tab = id;
    // The front follows, so turning back lands on the same break.
    if (has("selectSwellTab")) call("selectSwellTab", id);
    render(true);
  }

  function syncTabs() {
    back.querySelectorAll("[data-sm-tab]").forEach((b) => {
      const on = b.dataset.smTab === tab;
      b.setAttribute("aria-selected", on); b.tabIndex = on ? 0 : -1;
    });
  }

  function build(card) {
    back = document.createElement("div");
    back.className = "sm-back"; back.hidden = true;
    const tabs = [...card.querySelectorAll("[data-swell-tab]")]
      .map((b) => `<button type="button" role="tab" data-sm-tab="${b.dataset.swellTab}">${b.textContent.trim()}</button>`).join("");
    back.innerHTML = `<div class="sm-head"><span class="lbl">Swell · Map</span>
        <button type="button" class="sm-turn" aria-label="Turn the card back over">${ICON_CARD}Card</button></div>
      <div class="subtabs" role="tablist" aria-label="Break on the map">${tabs}</div>
      <div class="sm-map"><div class="sm-hint">Use two fingers to move the map</div></div>
      <div class="sm-cap" aria-live="polite"></div>
      <div class="srcs"><span class="src"><span class="pills"><span class="pill">Esri World Imagery</span><span class="pill-tail">Model geometry</span><span class="pill-tail">NOAA ENC</span></span></span></div>`;
    back.querySelector(".sm-turn").addEventListener("click", () => turn(false));
    back.querySelectorAll("[data-sm-tab]").forEach((b) => b.addEventListener("click", () => choose(b.dataset.smTab)));
    card.after(back);
  }

  function makeMap() {
    const el = back.querySelector(".sm-map");
    map = L.map(el, {
      zoomSnap: 0.25, zoomDelta: 0.5, attributionControl: true, zoomControl: false,
      dragging: !TOUCH, touchZoom: true, scrollWheelZoom: false, tap: false,
      maxBounds: [[31.5, -118.6], [33.6, -116.3]], minZoom: 8, maxZoom: 18,
    });
    map.attributionControl.setPrefix(false);
    L.tileLayer(ESRI, {attribution: ATTR, maxNativeZoom: 18, maxZoom: 18}).addTo(map);
    L.control.zoom({position: "topright"}).addTo(map);
    const Fit = L.Control.extend({options: {position: "topright"}, onAdd() {
      const d = L.DomUtil.create("div", "leaflet-bar");
      d.innerHTML = `<a href="#" role="button" title="Back to the whole geometry" aria-label="Back to the whole geometry">${ICON_FIT}</a>`;
      L.DomEvent.on(d.firstChild, "click", (e) => { L.DomEvent.stop(e); map.fitBounds(back._bounds, {padding: [14, 14]}); });
      return d;
    }});
    new Fit().addTo(map);
    layer = L.featureGroup().addTo(map);
    window.__smMap = map;
    const zoomClass = () => el.classList.toggle("sm-close", map.getZoom() >= 13);
    map.on("zoomend", zoomClass); zoomClass();
    map.on("click", () => { if (picked) select(picked); });
    // Ctrl + wheel zooms, as the charts do; a plain wheel scrolls the page.
    el.addEventListener("wheel", (e) => {
      if (!e.ctrlKey) return;
      e.preventDefault();
      map.setZoom(map.getZoom() - Math.sign(e.deltaY) * 0.5);
    }, {passive: false});
    // One finger scrolls the page; say how to move the map instead.
    if (TOUCH) {
      const hint = el.querySelector(".sm-hint");
      let t0 = null, timer = 0;
      el.addEventListener("touchstart", (e) => { t0 = e.touches.length === 1 ? e.touches[0].clientY : null; }, {passive: true});
      el.addEventListener("touchmove", (e) => {
        if (t0 == null || e.touches.length !== 1 || Math.abs(e.touches[0].clientY - t0) < 8) return;
        hint.classList.add("on"); clearTimeout(timer);
        timer = setTimeout(() => hint.classList.remove("on"), 1100); t0 = null;
      }, {passive: true});
    }
  }

  // Turning over: the card turns away to its edge, the back turns in from
  // its edge, in the front's footprint so nothing below moves.
  async function turn(toBack) {
    const card = document.querySelector(".cond.swell");
    if (!card || flipping) return;
    flipping = true;
    const out = toBack ? card : back, inn = toBack ? back : card;
    if (toBack) {
      back.style.height = `${card.offsetHeight}px`;
      tab = frontTab();
    }
    const ease = (from, to, e) => ({duration: 170, easing: e, fill: "forwards"});
    if (!REDUCED) await out.animate([{transform: "perspective(1400px) rotateY(0)"},
      {transform: `perspective(1400px) rotateY(${toBack ? 90 : -90}deg)`}], ease(0, 90, "cubic-bezier(.4,0,1,1)")).finished;
    out.hidden = true; out.getAnimations().forEach((a) => a.cancel());
    inn.hidden = false;
    if (toBack) {
      if (!map) makeMap();
      map.invalidateSize({animate: false});
      render(true);
    }
    if (!REDUCED) await inn.animate([{transform: `perspective(1400px) rotateY(${toBack ? -90 : 90}deg)`},
      {transform: "perspective(1400px) rotateY(0)"}], ease(90, 0, "cubic-bezier(0,0,.2,1)")).finished;
    inn.getAnimations().forEach((a) => a.cancel());
    (toBack ? back.querySelector(".sm-turn") : card.querySelector(".sm-turn")).focus({preventScroll: true});
    flipping = false;
  }

  // The page redraws its cards on every refresh; the button is put back each
  // time, and a card redrawn while the back is showing stays turned away.
  function attach() {
    const card = document.querySelector(".cond.swell");
    if (!card) return;
    if (!card.querySelector(":scope > .sm-turn")) {
      const b = document.createElement("button");
      b.type = "button"; b.className = "sm-turn"; b.setAttribute("aria-label", "Turn the card over to the map");
      b.innerHTML = `${ICON_MAP}Map`;
      b.addEventListener("click", () => turn(true));
      card.prepend(b);
    }
    if (!back || !back.isConnected) { back = null; map = null; build(card); }
    else if (back.previousElementSibling !== card) card.after(back);
    if (!back.hidden) card.hidden = true;
  }
  new MutationObserver(() => attach()).observe(document.body, {childList: true, subtree: true});
  attach();
})();
