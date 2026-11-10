// Swell fill (MOCK, 2026-11-10): on the LIVE tab, a picked train's energy
// filling in through its break's windows, on the window drawing itself.
//
// Everything drawn is the chain read back (mocks/swell_fill/fill.py), for
// the spectrum the card shows:
// - each LANE is one degree the train's energy left deep water FROM, drawn
//   from the drawing's rim toward the break, darker for more energy;
// - a lane whose degree the windows close stops at the rim (the land is out
//   there somewhere along that bearing; the drawing has no distances);
// - a lane that reaches the break bends on its way in to the heading its
//   rays arrive from in 5 m of water, and fades or darkens to what reached
//   5 m (diffraction and bottom friction in, shoaling divided out, so the
//   two ends compare);
// - each period's energy reaches the break at its own minutes after the same
//   group passed NDBC 46232 (the tables' `_leg.csv`): long periods first.
// The rim-to-break leg is DRAWN, a fixed LEAD_MIN of the clock: the drawing
// has no distances, and only the arrival minutes are the chain's.
(function () {
  "use strict";
  const FILL = window.__SWELLFILL__;
  const DATA = window.__MOCK_DATA__ || {};
  if (!FILL || !DATA["now.json"]) return;
  const NORMAL = {};
  (DATA["now.json"].breaks || []).forEach((b) => { NORMAL[b.id] = b.shore_normal_deg; });

  const LEAD_MIN = 15;           // the drawn rim-to-break leg, in the clock's minutes
  const PLAY_MS = 9000;          // the whole fill, on screen
  const BLOCKED_REACH = 0.07;    // how far in from the rim a closed lane is drawn
  const SAMPLES = 28;            // points along each lane
  const MIN_LANE = 0.004;        // lanes under this share of the strongest are not drawn
  const END_AT = 0.2;            // lanes end this far out (of the rim's radius), clear of the 5 m head
  const REDUCED = matchMedia("(prefers-reduced-motion: reduce)");
  const SVGNS = "http://www.w3.org/2000/svg";
  const ICON = {
    play: '<svg viewBox="0 0 12 12" aria-hidden="true"><path d="M3 1.5v9l7.5-4.5z"/></svg>',
    pause: '<svg viewBox="0 0 12 12" aria-hidden="true"><rect x="2" y="1.5" width="3" height="9" rx=".5"/>'
      + '<rect x="7" y="1.5" width="3" height="9" rx=".5"/></svg>',
    again: '<svg class="stroke" viewBox="0 0 12 12" aria-hidden="true"><path d="M2.2 6.6A3.9 3.9 0 1 0 3.4 3.1"/>'
      + '<path d="M3.6 0.9v2.4H1.2"/></svg>',
  };

  const g = (name, fb) => { try { return eval(name); } catch (e) { return fb; } };
  const D = () => g("DRAW", {w: 320, h: 200, cx: 160, cy: 162, r: 140});
  const live = () => g("MODE", "now") === "now";
  const height = (m) => { const f = g("heightText", null); return f ? f(m) : `${(m * 3.28084).toFixed(1)} ft`; };

  // A key's rows: "T1", "t1", "t1-1" one train; "G0.2" each row of one swell.
  function rowsOf(key) {
    if (!key) return [];
    let m = /^[Tt](\d+)(?:-\d+)?$/.exec(key);
    if (m) return [+m[1]];
    m = /^G([\d.]+)$/.exec(key);
    return m ? m[1].split(".").map(Number) : [];
  }

  // ------------------------------------------------------------ the model
  // Lanes by offshore degree, each with its parts by period bin.
  function model(id, rows) {
    const data = (FILL.breaks || {})[id];
    const normal = NORMAL[id];
    if (!data || normal == null) return null;
    rows = rows.filter((n) => data[n]);
    if (!rows.length) return null;
    const rel = (b) => ((b - normal) % 360 + 540) % 360 - 180;
    const lanes = new Map();
    let fiveTotal = 0;
    const rowFive = rows.map(() => 0);
    const arrivals = [];
    const periods = {};
    rows.forEach((n, ri) => {
      const row = data[n];
      Object.assign(periods, row.bins);
      // Each bin's energy-weighted arrival, for its closed lanes' timing.
      const binT = {};
      row.streams.forEach(([i, , , r, , t]) => {
        if (t == null || r <= 0) return;
        const v = binT[i] || (binT[i] = [0, 0]);
        v[0] += t * r; v[1] += r;
      });
      row.streams.forEach(([i, k, b, r, nd, t, f]) => {
        const a = rel(k + 0.5);
        if (a <= -90 || a >= 90) return;
        b *= row.scale; r *= row.scale; f *= row.five_scale;
        let lane = lanes.get(k);
        if (!lane) {
          lane = {a, b: 0, r: 0, s: 0, c: 0, parts: []};
          lanes.set(k, lane);
        }
        lane.b += b; lane.r += r;
        const reached = r > 0 && t != null;
        if (reached) {
          const th = nd * Math.PI / 180;
          lane.s += r * Math.sin(th); lane.c += r * Math.cos(th);
          arrivals.push([t, f, ri]);
        }
        const bt = binT[i];
        lane.parts.push({
          reached, b, r, f, ri, bin: i,
          t: reached ? t : (bt ? bt[0] / bt[1] : null),
        });
        rowFive[ri] += f; fiveTotal += f;
      });
    });
    // A closed lane's parts with no timing of their own take the train's
    // middle arrival; they only ever reach the rim.
    arrivals.sort((p, q) => p[0] - q[0]);
    const tot = arrivals.reduce((s, x) => s + x[1], 0);
    const pct = (p) => {
      let c = 0;
      for (const x of arrivals) { c += x[1]; if (c >= p * tot) return x[0]; }
      return arrivals.length ? arrivals[arrivals.length - 1][0] : 0;
    };
    const mid = pct(0.5);
    const list = [...lanes.values()];
    let top = 0;
    list.forEach((lane) => {
      lane.near = lane.r > 0 ? rel(Math.atan2(lane.s, lane.c) * 180 / Math.PI) : lane.a;
      lane.parts.forEach((p) => { if (p.t == null) p.t = mid; });
      top = Math.max(top, lane.b, lane.r);
    });
    const drawn = list.filter((l) => Math.max(l.b, l.r) >= MIN_LANE * top);
    const first = pct(0.02), last = pct(0.98);
    return {
      id, rows, lanes: drawn, top, arrivals, fiveTotal, rowFive,
      rowHs: rows.map((n) => data[n].row_hs_m),
      periods,
      t0: Math.min(0, first - LEAD_MIN), t1: last + 2,
      first, last,
    };
  }

  // What has reached 5 m by minute t: the rows' own heights scaled by the
  // share of each row's 5 m energy in, combined in energy; and the periods
  // more than half in.
  function soFar(m, t) {
    const inRow = m.rows.map(() => 0);
    const byBin = {};
    m.lanes.forEach((lane) => lane.parts.forEach((p) => {
      if (!p.reached) return;
      const v = byBin[p.bin] || (byBin[p.bin] = [0, 0]);
      v[1] += p.f;
      if (p.t <= t) { inRow[p.ri] += p.f; v[0] += p.f; }
    }));
    const h = Math.sqrt(m.rowHs.reduce((s, hs, ri) =>
      s + hs * hs * (m.rowFive[ri] > 0 ? inRow[ri] / m.rowFive[ri] : 0), 0));
    const total = Object.values(byBin).reduce((s, v) => s + v[1], 0);
    const ps = Object.entries(byBin)
      .filter(([, v]) => v[1] >= 0.02 * total && v[0] >= 0.5 * v[1])
      .map(([i]) => m.periods[i]).filter((p) => p != null);
    return {h, longest: ps.length ? Math.max(...ps) : null, shortest: ps.length ? Math.min(...ps) : null};
  }

  // ------------------------------------------------------------ drawing
  const at = (a, rad) => {
    const d = D(), t = a * Math.PI / 180;
    return [d.cx + rad * Math.sin(t), d.cy - rad * Math.cos(t)];
  };
  // A lane: in from the rim along its offshore heading, turning on the way
  // to arrive along its 5 m heading.
  function lanePoints(lane) {
    if (lane.pts) return lane.pts;
    const d = D();
    // Each lane stops short of the break, as the drawing's arrows do, where
    // the 5 m arrowhead takes over once the fill is in.
    const p0 = at(lane.a, d.r), p1 = at(lane.a, d.r * 0.55), p2 = at(lane.near, d.r * 0.36);
    const p3 = at(lane.near, d.r * END_AT);
    const pts = [];
    for (let j = 0; j <= SAMPLES; j++) {
      const s = j / SAMPLES, u = 1 - s;
      pts.push([
        u * u * u * p0[0] + 3 * u * u * s * p1[0] + 3 * u * s * s * p2[0] + s * s * s * p3[0],
        u * u * u * p0[1] + 3 * u * u * s * p1[1] + 3 * u * s * s * p2[1] + s * s * s * p3[1],
      ]);
    }
    return (lane.pts = pts);
  }

  function paint(st) {
    const {canvas, m, t} = st;
    const ctx = canvas.getContext("2d");
    const d = D();
    const w = canvas.width, h = canvas.height;
    ctx.setTransform(1, 0, 0, 1, 0, 0);
    ctx.clearRect(0, 0, w, h);
    ctx.setTransform(w / d.w, 0, 0, h / d.h, 0, 0);
    const css = getComputedStyle(canvas.parentElement);
    const ink = css.getPropertyValue("--ink").trim() || "#111";
    const soft = css.getPropertyValue("--soft").trim() || "#777";
    ctx.lineCap = "butt";
    const width = (2 * Math.PI * d.r / 360) * 1.15;    // one degree at the rim, a little over
    const alpha = (e) => Math.min(1, 0.95 * Math.sqrt(e / m.top));
    // Closed lanes first, in the shadows' grey, then the lanes that get in.
    for (const pass of ["closed", "open"]) {
      ctx.strokeStyle = pass === "closed" ? soft : ink;
      for (const lane of m.lanes) {
        const pts = lanePoints(lane);
        const e = new Float64Array(SAMPLES);
        let any = false;
        for (const p of lane.parts) {
          if ((pass === "open") !== p.reached) continue;
          const front = Math.min(1, (t - (p.t - LEAD_MIN)) / LEAD_MIN);
          if (front <= 0) continue;
          const reach = p.reached ? front : Math.min(front, 1) * BLOCKED_REACH;
          for (let j = 0; j < SAMPLES; j++) {
            const s = (j + 0.5) / SAMPLES;
            if (s > reach) break;
            const u = Math.min(1, s / 0.7);       // what the buoy holds, turning into what reaches 5 m
            e[j] += p.reached ? p.b + (p.r - p.b) * u * u * (3 - 2 * u) : p.b;
            any = true;
          }
        }
        if (!any) continue;
        ctx.lineWidth = pass === "closed" ? width * 1.6 : width;
        for (let j = 0; j < SAMPLES; j++) {
          if (e[j] <= 0) continue;
          ctx.globalAlpha = alpha(e[j]) * (pass === "closed" ? 0.9 : 1);
          ctx.beginPath();
          ctx.moveTo(pts[j][0], pts[j][1]);
          ctx.lineTo(pts[j + 1][0], pts[j + 1][1]);
          ctx.stroke();
        }
      }
    }
    ctx.globalAlpha = 1;
  }

  // ------------------------------------------------------------ the svg's own parts
  function ui(svg) {
    let g0 = svg.querySelector(".fill-ui");
    if (g0) return g0;
    const d = D();
    g0 = document.createElementNS(SVGNS, "g");
    g0.setAttribute("class", "fill-ui");
    const y = d.cy + 32, x0 = 84, x1 = 236;
    g0.innerHTML = `<text class="fill-cap" x="${d.cx}" y="${d.cy + 20}"></text>`
      + `<text class="fill-end" x="${x0 - 7}" y="${y}" text-anchor="end">NDBC 46232</text>`
      + `<text class="fill-end fill-endt" x="${x1 + 7}" y="${y}" text-anchor="start"></text>`
      + `<line class="fill-track" x1="${x0}" y1="${y}" x2="${x1}" y2="${y}"/>`
      + `<line class="fill-done-bar" x1="${x0}" y1="${y}" x2="${x0}" y2="${y}"/>`
      + `<circle class="fill-head" cx="${x0}" cy="${y}" r="3.5"/>`
      + `<rect class="fill-hit" x="${x0 - 8}" y="${y - 9}" width="${x1 - x0 + 16}" height="18"`
      + ` role="slider" tabindex="0" aria-label="Minutes after NDBC 46232"/>`;
    g0.dataset.x0 = x0; g0.dataset.x1 = x1;
    svg.appendChild(g0);
    const hit = g0.querySelector(".fill-hit");
    const stop = (e) => e.stopPropagation();
    hit.addEventListener("click", stop);
    hit.addEventListener("pointerdown", (e) => {
      e.stopPropagation();
      e.preventDefault();
      const id = svg.getAttribute("data-break");
      const st = STATE[id];
      if (!st) return;
      st.playing = false;
      hit.setPointerCapture(e.pointerId);
      const move = (ev) => {
        const ctm = hit.ownerSVGElement.getScreenCTM();
        if (!ctm) return;
        const p = new DOMPoint(ev.clientX, ev.clientY).matrixTransform(ctm.inverse());
        const f = Math.max(0, Math.min(1, (p.x - x0) / (x1 - x0)));
        st.t = st.m.t0 + f * (st.m.t1 - st.m.t0);
        render(id);
      };
      move(e);
      const up = () => {
        hit.removeEventListener("pointermove", move);
        hit.removeEventListener("pointerup", up);
        hit.removeEventListener("pointercancel", up);
      };
      hit.addEventListener("pointermove", move);
      hit.addEventListener("pointerup", up);
      hit.addEventListener("pointercancel", up);
    });
    hit.addEventListener("keydown", (e) => {
      const id = svg.getAttribute("data-break");
      const st = STATE[id];
      if (!st || (e.key !== "ArrowLeft" && e.key !== "ArrowRight")) return;
      e.preventDefault(); e.stopPropagation();
      st.playing = false;
      st.t = Math.max(st.m.t0, Math.min(st.m.t1, st.t + (e.key === "ArrowLeft" ? -1 : 1)));
      render(id);
    });
    return g0;
  }

  const minutes = (t) => (Math.round(t) < 0 ? `${-Math.round(t)} min before` : `+${Math.round(t)} min`);

  function caption(st) {
    const {m, t} = st;
    const sf = soFar(m, t);
    // At the end, the row's own number, whole: the share in is a reading of
    // the clock, and the row is what the card says.
    if (t >= m.t1 - 1e-6) {
      const whole = Math.sqrt(m.rowHs.reduce((s, hs) => s + hs * hs, 0));
      return `98% in by ${minutes(m.last)} · ${height(whole)}`;
    }
    if (!(sf.h > 0)) return `${minutes(t)} · on its way in`;
    if (!sf.longest) return `${minutes(t)} · ${height(sf.h)} in`;
    const ps = sf.longest === sf.shortest ? `${sf.longest.toFixed(1)} s`
      : `${sf.longest.toFixed(1)}–${sf.shortest.toFixed(1)} s`;
    return `${minutes(t)} · ${ps} in · ${height(sf.h)}`;
  }

  // ------------------------------------------------------------ state
  const STATE = {};
  let RAF = 0, LAST = 0;

  function host(svg) {
    const parent = svg.parentElement;
    if (!parent.classList.contains("fill-host")) parent.classList.add("fill-host");
    return parent;
  }

  // Where the svg sits inside its parent, in CSS pixels (an svg has no
  // offsetLeft or offsetTop of its own).
  function offset(svg) {
    const parent = svg.parentElement;
    const pr = parent.getBoundingClientRect(), sr = svg.getBoundingClientRect();
    return {left: sr.left - pr.left - parent.clientLeft + parent.scrollLeft,
      top: sr.top - pr.top - parent.clientTop + parent.scrollTop, width: sr.width, height: sr.height};
  }

  function place(st, svg) {
    const parent = host(svg);
    if (st.canvas.parentElement !== parent || st.canvas.previousElementSibling !== svg) svg.after(st.canvas);
    const o = offset(svg), w = o.width, h = o.height;
    const dpr = window.devicePixelRatio || 1;
    Object.assign(st.canvas.style, {left: `${o.left}px`, top: `${o.top}px`,
      width: `${w}px`, height: `${h}px`});
    const cw = Math.round(w * dpr), ch = Math.round(h * dpr);
    if (st.canvas.width !== cw || st.canvas.height !== ch) { st.canvas.width = cw; st.canvas.height = ch; }
  }

  function button(svg) {
    const parent = host(svg);
    let b = parent.querySelector(":scope > .fill-play");
    if (!b) {
      b = document.createElement("button");
      b.type = "button";
      b.className = "fill-play";
      b.addEventListener("click", (e) => {
        e.stopPropagation();
        const s = parent.querySelector(":scope > svg.aperture");
        if (s) toggle(s);
      });
      parent.appendChild(b);
    }
    const o = offset(svg);
    b.style.left = `${o.left + o.width - 28 - 2}px`;
    b.style.top = `${o.top + 2}px`;
    return b;
  }

  function setIcon(b, st) {
    const mode = st && st.playing ? "pause" : st && st.t >= st.m.t1 - 1e-6 ? "again" : "play";
    if (b.dataset.mode === mode) return;
    b.dataset.mode = mode;
    b.innerHTML = ICON[mode];
    b.setAttribute("aria-label", mode === "pause" ? "Pause the swell filling in"
      : mode === "again" ? "Play the swell filling in again" : "Play the swell filling in");
  }

  function clear(id) {
    const st = STATE[id];
    if (!st) return;
    st.canvas.remove();
    delete STATE[id];
    const svg = document.querySelector(`svg.aperture[data-break="${id}"]`);
    if (svg) {
      svg.classList.remove("filling", "fill-done");
      const u = svg.querySelector(".fill-ui");
      if (u) u.remove();
      const b = svg.parentElement && svg.parentElement.querySelector(":scope > .fill-play");
      if (b) setIcon(b, null);
    }
  }

  function toggle(svg) {
    const id = svg.getAttribute("data-break");
    let st = STATE[id];
    const key = g("PICKED", {})[id];
    if (!st) {
      const m = model(id, rowsOf(key));
      if (!m) return;
      const canvas = document.createElement("canvas");
      canvas.className = "fill-canvas";
      canvas.setAttribute("aria-hidden", "true");
      st = STATE[id] = {key, m, canvas, t: m.t0, playing: false};
    }
    if (REDUCED.matches) {
      // No motion: the filled drawing at once; the line under it still reads
      // any minute.
      st.playing = false;
      st.t = st.m.t1;
    } else if (st.playing) {
      st.playing = false;
    } else {
      if (st.t >= st.m.t1 - 1e-6) st.t = st.m.t0;
      st.playing = true;
      LAST = performance.now();
      if (!RAF) RAF = requestAnimationFrame(tick);
    }
    render(id);
  }

  function render(id) {
    const st = STATE[id];
    const svg = document.querySelector(`svg.aperture[data-break="${id}"]`);
    if (!st || !svg) return;
    svg.classList.add("filling");
    const done = st.t >= st.m.t1 - 1e-6;
    svg.classList.toggle("fill-done", done);
    place(st, svg);
    const u = ui(svg);
    u.querySelector(".fill-cap").textContent = caption(st);
    u.querySelector(".fill-endt").textContent = minutes(st.m.t1);
    const x0 = +u.dataset.x0, x1 = +u.dataset.x1;
    const x = x0 + (x1 - x0) * (st.t - st.m.t0) / (st.m.t1 - st.m.t0);
    u.querySelector(".fill-head").setAttribute("cx", x.toFixed(1));
    u.querySelector(".fill-done-bar").setAttribute("x2", x.toFixed(1));
    const hit = u.querySelector(".fill-hit");
    hit.setAttribute("aria-valuemin", Math.round(st.m.t0));
    hit.setAttribute("aria-valuemax", Math.round(st.m.t1));
    hit.setAttribute("aria-valuenow", Math.round(st.t));
    hit.setAttribute("aria-valuetext", caption(st));
    setIcon(button(svg), st);
    paint(st);
  }

  function tick(now) {
    RAF = 0;
    const dt = Math.min(now - LAST, 100);
    LAST = now;
    let more = false;
    for (const id of Object.keys(STATE)) {
      const st = STATE[id];
      const svg = document.querySelector(`svg.aperture[data-break="${id}"]`);
      if (!live() || !svg) { clear(id); continue; }
      if (st.playing) {
        st.t = Math.min(st.m.t1, st.t + dt * (st.m.t1 - st.m.t0) / PLAY_MS);
        if (st.t >= st.m.t1) st.playing = false;
        render(id);
        more = more || st.playing;
      }
    }
    if (more) RAF = requestAnimationFrame(tick);
  }

  // After the page shows a pick, put the fill's control where it applies:
  // LIVE only, a train (or one swell's rows) picked, and this break's rows
  // read back. Any other pick, or none, ends a fill.
  function sync(svg) {
    if (!svg || !svg.isConnected) return;
    const id = svg.getAttribute("data-break");
    const key = g("PICKED", {})[id] || null;
    const ok = live() && rowsOf(key).some((n) => ((FILL.breaks || {})[id] || [])[n]);
    const st = STATE[id];
    if (st && (!ok || st.key !== key)) clear(id);
    const parent = svg.parentElement;
    const b = parent && parent.querySelector(":scope > .fill-play");
    if (!ok) { if (b) b.hidden = true; return; }
    const btn = button(svg);
    btn.hidden = false;
    if (STATE[id]) render(id); else setIcon(btn, null);
  }

  const base = g("showPick", null);
  if (typeof base === "function") {
    // eslint-disable-next-line no-global-assign
    showPick = function (svg, key) {
      base(svg, key);
      sync(svg);
    };
  }
  window.addEventListener("resize", () => {
    document.querySelectorAll("svg.aperture[data-break]").forEach(sync);
  });
  new MutationObserver(() => {
    document.querySelectorAll("svg.aperture[data-break]").forEach((svg) => {
      const id = svg.getAttribute("data-break");
      if (STATE[id] && !svg.querySelector(".fill-ui")) render(id);
    });
  }).observe(document.body, {childList: true, subtree: true});
})();
