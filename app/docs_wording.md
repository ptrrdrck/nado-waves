# Nado Waves documentation: wording

This file is generated from `app/docs.html` by `python -m forecast.docswording`.
The page is the system of record; this is its prose, for editing.

How to edit:

- Edit wording in place. Keep every `## [section-id]` and `### [section-id]`
  line: the id in brackets is how an edit finds its way back to the page. The
  title after it is editable.
- Work on a branch (any name), push it, and say which branch. The test that
  keeps this file in step with the page fails on your push until the edits
  are carried into the page; that is expected.
- `{{geo:...}}` is a number the page reads from the geometry. Leave it as is,
  or change the words around it.
- `[bracketed notes]` are things the page draws or fills in itself: drawings,
  live blocks, the geometry tables. Their wording is not here.
- Fenced blocks are the math. Edit them like any other text.
- A line starting `>>` is a note to Claude, not page text. Use it for
  anything that is not a wording change, where it applies:
  `>> move this section after [calc-table]`, `>> delete this section`,
  `>> new section here: ### [new-id] Title`, `>> add a drawing of the tip`.
  Notes are removed when they are carried out.

## [start] How the Coronado forecast works

Nado Waves · documentation

Every card, chart and calculation on the forecast page, what each one is built from, and what each one is standing on. Start at the top for the tour, or use the contents to go straight to one thing.

### [start-what] What Nado Waves is

A swell forecaster for the three breaks on Coronado Central Beach: North, Center and South. All three read the same offshore buoy, buoy 46232 off Point Loma, and they get three different answers. The reason is geometric. Point Loma, the Coronado Islands and the Baja coast block most of the ocean from these beaches, and the gaps they leave open, the *swell windows*, point a different way from each spot on the sand. Walking from North to South moves the west edge of the window by about {{geo:west-sweep}}.

The premise is that a forecast that respects that geometry can say something a regional forecast cannot: which of the three breaks is holding more of today's swell.

### [start-claims] What it claims, and what it does not

**Nothing has ever measured a wave at these three breaks.** This is **physically derived**, not an accurate forecast, and it carries no error bar because there is nothing to compute one against. What it claims is which break holds more of today's swell — not how big it is.

Each break's number is the buoy's swell carried by physics to where it **breaks**: through the windows the coast leaves open, bent over the seabed and slowed by its friction, diffracted round every window edge, lifted by shoaling into 5 m of water with local wind chop added, then carried in over the surveyed beach profile at the tide of the moment until it breaks. It is still not a wave height at the beach as a surfer would call it: a significant height, not a face height, and the step from one to the other has not been fitted; the beach profile is a 2016 survey rather than this season's sandbars; and nothing has checked it against the sand.

### [start-minute] The page in one minute

From the top of the forecast page down. The figures are a real hour, noon on Monday 28 September 2026, at the North break.

[annotated card, row by row:]
- “LIVE” / Forecast
- North / Center / South / Buoy
- 3.5 ft (1.07 m) breaking at 8 ft (2.3 m) depth ▾
- the window drawing, and the swell trains under it
- Observed 12:00 PM, 15 min ago · Spectral wave data, Point Loma South, CA (NDBC 46232) · **Update in 59:12.**
- **Charts** ▴
- **Wind** 9 mph (8 kt) from the west, cross-shore at this break · **Tide** 6.2 ft (1.89 m)

1. **Two tabs.** “LIVE” is built only from measurements, Forecast only from a model. [Two tabs, two chains](#chains).
2. **One tab per break**, ranked by how much swell each one's windows let in, with the buoy itself always last. [Break tabs](#swell-tabs).
3. **The headline**: the height where the waves break, and the depth they break in. The caret at its end folds out the calculation behind it. [Reading the table](#calc-table).
4. **The windows**, drawn facing the way the break faces, and the wave trains that make up the number. [The window drawing](#swell-drawing).
5. **Where it came from, and when the next one is due.** [Countdowns](#swell-countdown).
6. **Charts**, closed until opened, the last line of every card. [Charts](#charts).
7. **Wind and Tide**, cards of their own because one station feeds all three breaks. [Wind](#wind), [Tide](#tide).

### [start-standing] What each tab is standing on, right now

Each tab's file says which of the four confidence levels (geometry, model, calibration, observation) it has reached. These blocks are read from those files as the page loads, so they say what the forecast page is standing on at this moment. A level that reads none is one the project has not reached. [The four levels](#confidence-levels).

[live block: What “LIVE” is standing on]

[live block: What Forecast is standing on]

## [chains] Two tabs, two chains

The two tabs are not two views of one forecast. They are two separate *evidence chains* that share the geometry and nothing else, and the page never mixes a number from one into the other.

### [chains-live] “LIVE”: measurements only

Built from what was measured: buoy 46232's directional spectrum, the wind reported at the airfield on North Island (KNZY), and the water level at the San Diego Bay tide gauge (NOAA 9410170). The quotation marks are deliberate. The feeds update, but a reading is always some minutes old, and each card's countdown says exactly how old.

It carries exactly one modelled number, the tide's next high or low, and that is labelled *predicted* wherever it appears. [Why that one](#tide-turn).

Its Buoys tab also shows a second buoy, 46047 at Tanner Banks, measured the same way, and a [rose](#swell-roses) under each buoy. Nothing on any other tab is computed from 46047. [Why it is there](#swell-tabs).

### [chains-forecast] Forecast: the model only

Built from the GFS-Wave model run by NOAA (WAVEWATCH III), read at the buoy's position and carried in through the same windows, seabed and surf zone. Its wind is the National Weather Service's forecast at Coronado and its tide is the harmonic prediction. It shows every third hour, from 48 hours back to the end of the newest run.

### [chains-apart] Why they are never mixed

So that you always know which chain a number belongs to. A forecast hour that has gone by gets a red line under it that comes from the measured chain, and that line is labelled “Observed at” with its hour, never blended into the forecast figure above it. [The red line](#time-observed).

A refresh keeps the tab you chose. A new visit always opens on “LIVE”.

## [aperture] The aperture

Which compass bearings can reach each break at all, from coordinates alone. Everything later in the chain starts here. The drawing below and throughout this page shows every vertex the forecast's geometry uses, drawn where it sits and joined the way the model joins it. Each coloured ray runs from a break to the one vertex that forms that edge of its swell window, which is also the vertex whose error would move the edge. It is the model, not the chart: NOAA's charts hold thousands of coastline vertices, and the aperture is decided by a few dozen.

### [aperture-windows] Swell windows, and which way a bearing points

A bearing here is always the direction the swell comes **from**, as a buoy reports it: 270° is a swell arriving from due west. Each break has three windows:

- **South**, between the Baja coast and the Coronado Islands' south group: where the summer's south swells arrive.
- **The channel**, the gap of open water between the two island groups, about {{geo:channel-deg:coronado_center}} wide.
- **West**, between the north island and the tip of Point Loma: the widest, and the one that changes most along the beach.

[drawing: whole] Caption: The whole aperture. Point Loma is 5–7 km out, the Baja coast 23–25 km and the islands 28–33 km. Every window edge ends on a charted vertex.

Everything else (north-west swell behind Point Loma, the open Pacific to the south-west beyond the islands' shadow) cannot reach these beaches in a straight line. The buoy sits outside all of it, 29 km offshore with nothing in the way, which is why the buoy's own number is always the biggest on the page.

### [aperture-tip] Point Loma: one tip, three tangents

The west edge of every window is the line from the break that just grazes the tip of Point Loma. The tip is a rounded headland, so each break's line touches it at a different charted vertex: the three are {{geo:tip-spread}} apart. No single point can stand for all three, so the model carries the tip as the convex hull of the charted coastline, and only a hull vertex can be a tangent.

[drawing: tip] Caption: The tip as the model carries it. Each break's tangent lands on its own vertex, ringed in that break's colour.

It is the highest-leverage coordinate in the model. The tip is only {{geo:tangent-km:coronado_north}} from North, so 100 m of error there moves North's west edge by {{geo:costs:coronado_north:Point Loma peninsula}}.

### [aperture-islands] The Coronado Islands: two screens and a channel

The islands are two groups with open water between them, and the model draws each as a screen between its two extreme vertices as seen from the beach. They are far away and narrow, so they take only a small share of a swell's energy. Point Loma takes far more. Treating them as an open-or-shut switch on a single swell direction is the error this model was built to avoid. [Why the whole spectrum](#calc-windows).

[drawing: islands] Caption: Two islands, each modelled as a screen between its two extreme-bearing vertices, with open channel between them.

### [aperture-baja] The Baja coast

The south edge of every window is a single vertex on the Mexican coast, {{geo:baja-km}} from the center break, that every other charted vertex from the border to Rosarito sits behind. Because it is far away, 100 m of error there moves an edge only {{geo:costs:coronado_center:Baja peninsula}}. NOAA's charts stop just south of it, so no coast further south has been checked.

### [aperture-breaks] Why three breaks 2.8 km apart differ

As you walk south along the sand, the line to the Point Loma tip swings west, and the west window opens with it:

[table the page fills in: geo-west]

[drawing: near] Caption: The west edge of each window is the ray to the Point Loma tip. It sweeps as you walk the sand, and that sweep is the whole difference between the three breaks' windows.

So a west swell reaches South more easily than North. That is the window. The seabed then has its own say, and it can reverse the order. [The worked hour](#calc-hour) is an example where it does.

### [aperture-chords] Breaks, chords and shore normals

Each break is a short stretch of shoreline, a *chord* between two charted vertices, and its position is the chord's midpoint. The *shore normal* is the direction straight out to sea, at right angles to the chord. It is the reference for everything that depends on which way the beach faces: whether a wind is offshore, and which way the window drawing on each card is turned.

[table the page fills in: geo-breaks]

Where along the coast each break sits is a surfer's choice, not a chart's. Position matters: it sets the window. The chord's angle does not move the window at all (both window edges come from the blockers), but it does set the normal.

### [aperture-tables] Reference tables

Bearings are the direction swell comes FROM. “100 m moves it” is how far the edge swings if that one vertex is wrong by 100 m (328 ft): the leverage of each coordinate.

#### Windows, and the vertex behind each edge

[table the page fills in: wtable]

#### Vertices in use

[table the page fills in: vtable]

#### Distances

[table the page fills in: dtable]

### [aperture-map] Explore the map

The full drawing. Drag to pan, scroll or pinch to zoom, tap a ray, vertex or distance for its details, and switch breaks and layers on and off.

## [calc] The swell calculation

Each break's headline number is built in eight steps, and each step is one row of the calculation table that folds out under the card's headline. Every step is textbook physics on charted and surveyed inputs. None of it has been fitted to anything, because nothing at these beaches has been observed to fit it to.

Buoy*→*Windows*→*Refraction*→* Diffraction*→*Bottom friction*→*Shoaling*→* Local chop*→*Wave break

Each step below says what it does, which model was chosen and why, the math, and what it did to the worked hour. The math is in metres and seconds, the units the buoy and the model publish and the chain runs in. Results are given in feet first, as on the cards.

### [calc-hour] One worked hour

Monday 28 September 2026, 19:00 UTC (12:00 PM local), on the “LIVE” chain. The buoy read 4.3 ft (1.30 m), peaking at 11.8 s from 188°: a south swell with west swell under it. The airfield had a 9 mph (8 kt) wind from 270°, and the gauge read 6.6 ft (2.01 m) above its low-water datum. Here is what the chain made of it at each break:

[table the page fills in: worked-table]

The ordering is the point. Through the straight-line windows alone, South's was the biggest (0.90 m against North's 0.84 m), because its west window is widest. Over the seabed, North came out on top, 3.5 ft (1.07 m) against 2.9 ft (0.88 m) at Center and South. The window alone would have ranked them the other way round. That reversal is a *claim*, physically derived and unchecked. It is exactly the kind of claim the beach observation log exists to test. [The log](#confidence-log).

The steps below follow North. These figures were rebuilt from the archive with the chain as it stood on 2 October 2026. A test rebuilds the same hour on every change, so if the chain moves, this page has to move with it.

### [calc-buoy] Buoy

Buoy 46232 publishes its spectrum every hour: for each of 64 frequency bands, the energy in that band and four numbers that describe which directions it came from. Height comes from the total energy:

```
m₀ = Σ E(f)·Δf                      total energy over the 64 bands
Hs = 4·√m₀

worked hour
m₀ = 0.1050 m²
Hs = 4 × √0.1050 = 1.296 m           → 4.3 ft (1.30 m)
```

Direction is harder. The four numbers per band (two mean directions α₁, α₂ and two concentrations r₁, r₂) don't give the spread of directions on their own. They have to be read back into a spread, and there are two standard ways to do it.

> **Model choice · maximum entropy**
> The usual two-term Fourier series spreads energy wide and can go below zero, and clipping the negative part adds energy that isn't there. The maximum entropy method (Lygre & Krogstad, 1986) builds the narrowest spread consistent with the four numbers and can never go negative. The page uses maximum entropy. Where it cannot be computed for a band, that band falls back to Fourier, and the fallbacks are counted.

```
Fourier:  D(θ) = (1/π)·[½ + r₁·cos(θ−α₁) + r₂·cos 2(θ−α₂)]
MEM:      D(θ) ∝ 1 / |1 − φ₁e^(−iθ) − φ₂e^(−2iθ)|²
          c₁ = r₁e^(iα₁),  c₂ = r₂e^(2iα₂)
          φ₁ = (c₁ − c₂c₁*) / (1 − |c₁|²),   φ₂ = c₂ − c₁φ₁

worked hour, the peak band (0.085 Hz, 11.8 s): α₁ = α₂ = 188°, r₁ = 0.94, r₂ = 0.87
Fourier:  below zero over 138° of the circle; clipped, it carries 24% more energy than it should
          half-power width 91°
MEM:      half-power width 10°, centred on 187–188°
```

On a narrow swell the difference is large. Maximum entropy puts this band's energy where the swell is, so the windows downstream see it in the right place.

### [calc-windows] Windows

Each break's windows are applied to the whole spectrum, every frequency and every direction, and the energy aimed through them is added up:

```
m₀,window = ∫∫ E(f,θ) · T(θ) dθ df     T = 1 inside a window, 0 outside
Hs,window = 4·√m₀,window = Hs · √(share)

worked hour, North
share     = (0.836 / 1.296)² = 0.416     42% of the energy is aimed through North's windows
Hs        = 1.296 × √0.416 = 0.836 m      → 2.7 ft (0.84 m)
Center 0.875 m (46%), South 0.899 m (48%)
```

> **Model choice · integrate, never test one direction**
> Testing a single “mean direction” against the windows gives a yes or no: a swell from 190° would read as fully blocked by the islands, and one from 192.6° as fully open. Integrating the spectrum shows the islands for what they are, a small partial reduction, and Point Loma as the large one. So a single bearing is never tested anywhere on the page.

[drawing: near] Caption: North, Center and South's windows shaded. The edges are straight lines here. The next two steps bend them and soften them.

At this step the edges are hard and the lines are straight, as if the sea had no bottom. This row is also what the [Window chart](#charts-live-swell) plots as a share of the buoy.

### [calc-refraction] Refraction

Swell slows down in shallow water, so a wave crossing the shelf at an angle bends toward the shallows. Rays are traced *backward*: from a start point in 5 m of water straight off each break, out over the surveyed seabed until the water is deep, for every frequency band and every half-degree of arrival heading. Each ray then says which offshore heading it really came from, and whether that heading is open.

```
ω² = g·k·tanh(k·h)                   how fast a wave of period T = 2π/ω travels in depth h
c = ω/k,   c_g = ½·c·(1 + 2kh / sinh 2kh)

12.5 s, North's leading train
deep water   L₀ = gT²/2π = 244 m,  c = 19.5 m/s
5 m depth    L  = 86 m,            c = 6.85 m/s

sin θ / c = constant along a ray     Snell's law, on a straight, even beach
a swell 30° off the normal in deep water arrives 10° off it in 5 m
```

The energy that arrives comes from S(f,θ)·c·c_g staying constant along each ray, which gives refraction and the height change together. The next rows split those apart. This row is refraction alone, with every window edge still a hard shadow, so its change from the Windows row is the seabed and nothing else.

> **Model choice · backward rays over the whole seabed**
> Tracing from the beach outward means every ray that reaches the break is found, and none is wasted on water that never arrives. The seabed is the USGS CoNED survey near shore with GMRT further out, the islands' own shelves included. Point Loma, the islands and Baja are land the rays stop on. The method is the one Scripps' CDIP uses for its coastal model, checked here against Snell's law on a flat test beach.

```
worked hour
North    0.836 → 0.833 m    −0.4%
Center   0.875 → 0.628 m   −28%
South    0.899 → 0.691 m   −23%
```

This is the step that reversed the order. North's seabed delivered almost everything its window let in. Center's and South's lost a quarter. The table measures that difference; it does not explain it, and the bathymetry in front of each break is different.

### [calc-diffraction] Diffraction

A shadow edge is not sharp. Swell leaks round a headland into its shadow, and some of the energy grazing the edge is lost. Each window edge is softened, measured along the *bent* rays from the previous step, because the ray that grazes an edge is refracted again between the edge and the beach.

```
u = x · √( 2 / (λ·D) )               x: how far the ray passes the edge (negative: inside the shadow)
                                     λ: wavelength there, D: distance on to the break
straight edge (Point Loma, Baja):
K(u) = ½·[(C(u) + ½)² + (S(u) + ½)²]  C, S the Fresnel integrals

u   −2      −1      0       +1      +2
K   0.012   0.041   0.250   1.259   0.844
at the edge itself a ray carries exactly a quarter of the open-water energy

12.5 s at the Point Loma tip, 4.7 km from North: 100 m past the edge is u = 0.13
```

The islands use the same idea twice. By Babinet's principle an obstacle is open water minus the wave through a slit its shape, so each island is a slit subtracted from open water.

[drawing: islands] Caption: The two island screens. Each is diffracted as its own slit, so the channel between them stays open water.

```
worked hour
North    0.833 → 0.851 m    +2.2%
Center   0.628 → 0.663 m    +5.6%
South    0.691 → 0.718 m    +3.9%
```

Diffraction added a little at all three: more leaked into the shadows than was lost along the edges.

### [calc-friction] Bottom friction

Swell crossing shallow water loses energy to the seabed. The loss is computed along each ray's own path.

```
d(flux)/ds = −flux · C_b·ω² / (g²·sinh²(kh)·c_g),    C_b = 0.038 m²/s³

12.5 s, energy kept per kilometre of ray
h = 30 m   99.4%
h = 20 m   98.8%
h = 15 m   98.1%
h = 10 m   96.4%

worked hour
North    0.851 → 0.754 m   −11%     energy × 0.79
Center   0.663 → 0.594 m   −10%
South    0.718 → 0.657 m    −8.5%
```

> **Model choice · the JONSWAP friction law, untuned**
> Its coefficient comes from the literature and has not been adjusted. It is linear in energy, so each ray's loss is a fixed factor that can be worked out once, ahead of time, with the rest of the seabed tables. A law that depends on the wave height could not be precomputed that way.

### [calc-shoaling] Shoaling

As water shallows, waves slow and bunch up, and their height grows. This row puts back the growth the refraction step kept separate, from deep water to the 5 m start point.

```
Ks² = c_g,deep / c_g(h)

12.5 s into 5 m:  c_g = 9.76 m/s deep, 6.56 m/s at 5 m
Ks  = √(9.76 / 6.56) = 1.22           +22% in height

worked hour, the whole spectrum
North    0.754 → 0.926 m   +23%
Center   0.594 → 0.715 m   +20%
South    0.657 → 0.737 m   +12%
```

> **Model choice · hand over at 5 m**
> The ray tables stop in 5 m of water, close in and still inside Point Loma's shadow. From there the surf zone takes over (step 8). A table that stopped further out would describe water outside the shadow, a different place.

### [calc-chop] Local chop

Wind makes its own small waves close to the beach, which the buoy never saw. Their height depends on the wind and on the *fetch*, the stretch of open water it blows over before it reaches the break.

```
u*² = C_D·U₁₀²,   C_D = 0.001·(1.1 + 0.035·U₁₀)
g·Hm0/u*² = 0.0413·(g·X/u*²)^½       X: the fetch
g·Tp/u*   = 0.751·(g·X/u*²)^⅓        capped where the sea is fully grown

worked hour, North: 8 kt from 270°, fetch 2.3 km, closed by Point Loma
U₁₀ = 4.12 m/s,  C_D = 0.00124,  u* = 0.145 m/s
Hm0 = 0.092 m,   Tp = 1.1 s           → 0.3 ft (0.09 m)

chop and swell add in energy:
√(0.926² + 0.092²) = 0.931 m          +0.5%
```

> **Model choice · two kinds of fetch**
> The growth law is the Coastal Engineering Manual's (US Army Corps of Engineers, 2002). Only a wind blowing from the sea toward the break makes chop that reaches it. When the upwind line ends on land (Point Loma's lee, the islands, Baja), the chop is grown fresh over that short stretch. When it runs out to open sea, the buoy's spectrum already holds the wind sea made upwind of it, so only the extra growth over the water *between* the buoy and the break is added. Adding a whole fresh sea there would count it twice.

On the Forecast tab the wind is the National Weather Service's forecast at Coronado, and the calculation row says whose wind it used.

### [calc-break] Wave break

From 5 m of water the sea is carried in along the surveyed beach profile, the depth every 2 m straight in along the shore normal to dry sand. The tide is added to that depth. As the water shallows the waves grow until the biggest start breaking and lose energy faster than shoaling adds it. The reported height is the largest along the way, and the depth where that happens.

```
d(E·c_g·cos θ)/dx = −D,   E = Hrms²/8                energy flux in, minus breaking
D = ¼·α·f_p·Qb·Hmax²,   α = 1,   Hmax = γ·h           Battjes & Janssen (1978)
(1 − Qb) / ln Qb = −(Hrms / Hmax)²                    Qb: the share of waves breaking
γ = 0.5 + 0.4·tanh(33·s₀),   s₀ = Hrms,deep / L₀      Battjes & Stive (1985)

worked hour, North: 0.931 m at 5 m, 12.5 s
Hrms,deep = 0.931/√2 × √(6.56/9.76) = 0.540 m
s₀ = 0.540 / 244 = 0.0022  →  γ = 0.529

tide at the open coast: +1.022 m above mean sea level  (see the Tide card's math)
largest Hs 88 m in from the start point, in h = 2.32 m of water
Hmax = 0.529 × 2.32 = 1.227 m,   Hrms = 1.069/√2 = 0.756 m
(Hrms/Hmax)² = 0.380  →  Qb = 0.091                   9% of waves breaking

Hs = 1.069 m                         → 3.5 ft (1.07 m), breaking at 8 ft (2.3 m) depth   +15%
```

> **Model choice · the standard 1-D surf zone, γ from the literature**
> One line straight in, the same all along the beach, one period (the peak's). That is the textbook surf-zone model and no more. The breaker index γ is taken from Battjes & Stive and not tuned. Fitting it to anything here would be calibration, and there is nothing observed at these beaches to fit it to.

If the waves are already breaking at the start point, the true break is further out than the profile begins. The card then says “breaking at 16 ft (5.0 m) depth or deeper”, and the last row of the table is marked ≤ as an upper bound. Without a measured tide no breaking height is computed at all, and the card shows the 5 m figure, labelled with its depth. That is why no hour before 17 September 2026 has one.

### [calc-table] Reading the calculation table

The caret at the end of a card's headline folds out the table. Each row is one step above. **Change** is what that step added or took away, **%** is that change as a share of the row before, and **Hs** is the height after it. Read down, the last row is the headline. A step whose row is missing was not in the build that made that hour.

The Local chop row names the chop's period, its kind (behind land, or open water) and whose wind made it. The last row is the breaking height at the tide of that hour.

### [calc-not] What the number is not

- **Not a face height.** It is a *significant height*: the average of the biggest third of waves, trough to crest, the way buoys and wave models measure height. A surfer's call is different again, and the conversion between the two has never been fitted, because nothing has observed these breaks.
- **Not this season's sand.** The beach profile is the 2016 CoNED survey. A sandbar would move where and how the waves break, and nothing here knows where this season's bars are. On a profile without bars the tide changes *where* the waves break far more than *how big* they are.
- **Not checked.** Every step is physics and none has been compared against the sand. [Confidence and verification](#confidence).

## [swell] The Swell card

### [swell-tabs] Break tabs and the Buoys tab

One tab per break, ranked by how much of the buoy's energy its windows let through, with the Buoys tab always last. It shows the swell at buoy 46232, 29 km offshore, with nothing in the way, so it is always the biggest number, and it is the one the breaks are measured from.

On “LIVE” the Buoys tab also shows buoy 46047 at Tanner Banks, 222 km west, the buoy in the array that the islands shadow least. It is read the same way as 46232: the combined height of its directional spectrum, and its [swell trains](#swell-trains), with a train fed from two directions naming both. It is open ocean outside every break's windows, so it is carried to no break, and no number on any other tab comes from it. It is there so the swell before the Channel Islands and the Bight can be read beside the swell at 46232. Its spectra are stamped every half hour, at :20 and :50, so it has its own observed time and its own [countdown](#swell-countdown). The Forecast tab's Buoys tab shows 46232 only, because the model run is read at 46232 alone.

### [swell-headline] The headline

The breaking height, in feet with metres in parentheses, and the depth it breaks in: “3.5 ft (1.07 m) breaking at 8 ft (2.3 m) depth”. When there is no tide to break it at, the headline is the height in 5 m of water and says so. The caret at its end opens [the calculation](#calc-table).

### [swell-drawing] The window drawing

The break's windows, drawn facing the way the break faces: open water above the shore, the grey shadows of the land either side, and an arrow for each swell train, two for a train arriving from two directions. Tap a shadow for the land casting it and the share of this swell it takes; tap a window for the land either side and its width; tap an arrow for that train. Tap it again, or the sand below the shoreline, to return. A mouse previews on hover, and the keyboard reaches every part with Tab.

### [swell-trains] Swell trains

The number is rarely one swell. The spectrum is split at its low points into separate trains, each with its height, period and direction, and the local chop is listed as its own train, tagged. The trains add up, in energy, to the number above them.

The biggest train at the buoy need not be the biggest at a break, because the windows take whichever trains point at the blocked sectors. In the worked hour the buoy's lead was 11.8 s from 219°, and North's was 12.5 s from 206°.

A train's direction is where its energy comes from. When two directions each carry a fifth of a train or more, both are given by compass point, “WSW & S”, and the drawing has an arrow from each: one direction there would be their average, which sits between them where almost none of it comes from. A train with one direction gives its degrees, “SSW 197°”. Every train keeps to one line: on a narrow phone, a row tagged “wind sea” or “local chop” shortens its direction to a single compass point, the larger one's when there are two. It happens most at South, whose trains often arrive through both the south window and the west one.

The split is made on the spectrum by frequency, not on frequency and direction together, so two swells of the same period from different directions read as one train — with both its directions named.

### [swell-roses] The roses on the Buoys tab

On “LIVE”, under each buoy's reading on the Buoys tab, a rose drawn from that buoy's spectrum. Each petal points where its energy comes from, one petal for each of the sixteen compass points, 22.5° wide. A new rose is drawn for every spectrum: hourly at 46232, every half hour at 46047. The last six hours of them play in a loop, then the newest holds. One clock drives both roses, so both always show the same moment. The line under each rose is those six hours, with a tick for every spectrum that buoy sent; a missing spectrum is a missing tick, and while the loop passes it the rose says so rather than showing the one before. Tap the line to go to a moment, or step it with the arrow keys; the button to its left plays and pauses the loop. A reader whose device asks for less motion gets the newest rose, paused.

**Height** gives each sector's energy as a height. Heights combine in energy, so the petals do not add up to the combined height above them; the square root of the sum of their squares does, exactly. **Period** gives each sector's share of the spectrum's energy, split into five bands by the period of the energy, the shortest palest and the longest in ink. Each buoy's rose has its own scale for each view, given in one line under it: evenly spaced rings, at most five, the outermost being the largest petal in its six hours rounded up to the next ring (the next whole foot, until the petals pass 5 ft and the rings go every 2 ft), so no petal passes it. The scale holds through the loop, so a petal that grows from one frame to the next really grew. The two buoys' scales differ, so compare them by their rings, not by the size of the petals.

A petal is the height of one compass point's energy alone, so a swell spread over several points shows petals well under the combined height: on 7 October 46232 read 3 ft combined, spread over seven to ten points, its largest petal 1.8 ft.

A rose is the direction-reading method's picture of four numbers per frequency, not a measurement at each bearing, and it is the same reading the trains above it come from. 46047's spread reads broader than 46232's, so its petals spread over more compass points. The two buoys can also point one swell different ways for a real reason: 46232 sits behind the Channel Islands, 46047 in the open ocean before them. Neither rose is carried to a break.

### [swell-origin] Origin: where the swell was born

On “LIVE”, the **Origin** line folds out, like the charts, from its own line right above “Charts”. The number in parentheses beside its title counts the origins arriving at that tab now, named hurricanes and readings alike, and is not there when nothing is arriving; a last readable arrival is not counted. Under it, each train that came from a distant storm says where that storm was: a sea, about how far away and in which direction, and when the swell left it. It is read backwards off the buoy's own spectrum. It is not a forecast, and nothing observes the storm.

Long-period waves travel faster than short ones. In deep water a wave group moves at *gT*/4π, so a 20-second swell outruns a 14-second one. A storm makes every period at once, and by the time the energy has crossed an ocean the long periods have pulled ahead. At the buoy they arrive in order, longest first, and the frequency rises in a straight line with time:

```
f(t) = g·(t − t₀) / (4π·R)          f = 1/T, the frequency of the train's peak
R  = g / (4π · slope)                the distance to the storm
t₀ = where the line reaches f = 0    when it blew
```

Every hour, each peak in the buoy's spectrum between 10 and 29 seconds is found and followed from hour to hour. A peak that moves steadily to shorter periods for at least 12 hours, starting at 13 seconds or longer, on a line straight enough to read (R² of 0.8 or more), is a readable arrival.

The direction is read where the sea is open: at 46047, Tanner Banks. Never at 46232 itself: on a north-west swell it reads two directions at once, a westerly one held near 270° and the south's, and their average falls 50 to 74° too far south. Nor at 46086 in the San Clemente Basin, which is open to the south but holds a north-west swell near 279° whatever its real direction. And not at 46047 either when its energy at that period comes from two directions, each at least 15% of it: which one is the arrival's is not known, and their average would point between them. An arrival with no direction read gets a distance and a date and no place.

An origin belongs to a train, so a break shows only the arrivals that are one of its own trains, and the buoy's tab only those among the buoy's.

Every origin is written the same way, in three lines, whatever kind it is. The first says what it is: a hurricane by name with its winds, a sea, or an **unplaced storm** when neither unshadowed buoy saw the train. The second names the train, then how far away the storm was and its bearing from the buoy, in degrees and by compass point, and the day the swell left it; an unplaced storm has no bearing. A hurricane's line ends with how many hours of its swell the match has read so far. The third says how it is known: for a hurricane, its match to NHC's track and the count behind it at each buoy; for a reading, how many hours of the swell have been read, because a reading can still move while the train is arriving. When nothing readable is arriving, the last readable arrival at that tab in the last three weeks is shown in the same three lines, marked as the last, with the train it was at its busiest hour and the day it arrived. One set of sources follows them all and names only what is on screen: every train is read off 46232's spectrum, a hurricane's too; a reading's storm is then read backwards from it, with its direction from an unshadowed buoy; and a hurricane's place and winds are the National Hurricane Center's best track, an analysis.

How far the distance can be taken. The same storm read independently at two buoys gives distances about a fifth apart at the median: 18% between six Southern California buoys and buoys 1,000 to 4,000 km up the swell's path (2023–2025), and 25% between 46232 and 46047, 46086 and 46258 (August to October 2026). So the card rounds to the nearest 500 miles and 500 km, says “about”, and names a sea rather than a point. A storm is an area that moves, and one running toward the coast while it blows reads nearer than it was. The version this grew out of also said which buoys upstream had seen the swell pass; measured, that check could not tell a storm 4,000 km away from one 6,000 km away, so it is not shown.

Checked against the hurricanes the National Hurricane Center tracked in the eastern and central Pacific, August to September 2026, run forward: where and when each one's swell had to arrive, against the energy the buoys measured from its direction, with the same storm moved days earlier and later, and turned 45°, as controls. Hurricane Marie's swell is found that way at two buoys independently. None of the readings this card made that season survives it: four that read as “Tropical Pacific” due south to south-south-west had no hurricane near at all, and the two that agree with a tracked storm in timing and direction (Polo, Nolo) agree no more often than shuffled directions do. A reading of a nearby tropical storm on this card has been, so far, more often wrong than right. Readings of the Southern Ocean and the north-west storm track cannot be checked this way.

**Swell from a hurricane.** What can be shown is the converse: a hurricane the National Hurricane Center is tracking, with how well its track matches what the buoys measured. Each position on its track, at hurricane strength and with open water to the buoy, says when each period of its swell must arrive; those whose path crosses the Baja peninsula or the mainland are dropped. As of the newest spectrum, the energy 46047 or 46086 measured from the storm's direction on that schedule is set against the same storm's schedule moved back in time, every 12 hours up to 30 days, when its swell was not arriving. The **match** is the share of those earlier moments it beats on both counts: more energy on schedule than usual for each period, and more from the storm's direction than from 45° to either side. It is stated only when the swell on schedule is livelier than usual on both counts and there are at least 20 earlier moments to beat. It is a count, not a probability, and it says where a train came from, never how big it is.

Under Origin, “Hurricane …” appears when the match is 50% or more, with a word: **strong** from 90%, **partial** from 70%, **weak** from 50%. It shows on a break only when one of that break's own trains is the one arriving. Where the storm was and how strong are NHC's, from the position that sent that train, rounded to 100 miles and 100 km, and the sources say so: a best track is an analysis, not a measurement.

What the words are worth. Asked every six hours from August to October 2026 as of each moment, the card would have named Marie (4 to 8 September, strong at both buoys by the 6th), Polo (27 to 30 September, partial at best, 78% its highest) and Odalys (26 to 29 September, partial at best, 82%). The same question asked of every track moved 8 to 24 days later, where its swell was not, named 12 of 55 such tracks at some moment: 9 reached partial and 2 strong. Those two sat on another swell from the same direction: the test cannot tell two sources on one bearing apart, and a storm due west shares its bearing with the North Pacific's own storms. So a weak match is no more than misplaced tracks manage, partial is what about one misplaced track in six reached, and only strong is rare by chance. WAVEWATCH III's own hindcast at the buoys is checked alongside on this page's reports, never on the card: a model.

### [swell-countdown] Countdowns: when the next reading is due

Each “LIVE” card counts down to when its next reading should be on screen. The countdown is three real events on the clock, not an interval added to the reading:

1. when the source next **publishes** a reading;
2. plus how long that source typically takes to become fetchable;
3. rounded up to the next **collection**, which runs every 10 minutes at :05, :15, :25, :35, :45 and :55;

then the page adds its own refresh, every 5 minutes.

| Source | Publishes | Typical lag | Late after | Reading at 12:00 PM, next due |
|---|---|---|---|---|
| Swell, buoy 46232 | hourly, stamped :00 |  |  | 1:15 PM, red after 1:45 PM |
| Swell, buoy 46047 (Buoys tab) | half-hourly, stamped :20 and :50 |  |  | (12:20 PM reading) 1:15 PM, red after 2:15 PM |
| Wind, KNZY | hourly at :52 |  |  | (11:52 AM reading) 12:55 PM, red after 1:05 PM |
| Tide, 9410170 | every 6 min |  |  | 12:15 PM |

It reads “Update in m:ss”, then “Update due” once the typical time has passed. Only past the late time does it turn red and say “Overdue by m:ss”. The publishing lag varies from hour to hour, so one deadline would either cry wolf on every slow hour or promise a time that almost never applies. Hence two figures.

## [wind] The Wind card

### [wind-three] Three winds

- **KNZY**
  The airfield at Naval Air Station North Island, a few kilometres from the breaks. Its routine report lands at :52 each hour. This is the “LIVE” tab's wind.
- **Local**
  The National Weather Service's forecast grid at the center break, hourly for 7 days. On the Forecast tab it is the wind on the sand, and the offshore/onshore line comes from it.
- **GFS-Wave**
  The wave model's own wind at the buoy, 29 km offshore. Kept on the Forecast card because it is the wind the model grows its wind sea from, never used for the offshore/onshore line.

### [wind-sense] Offshore, cross-shore, onshore or light

Whether a wind is offshore depends on which way the beach faces, and the three breaks face {{geo:normals}}. So the line is per break, shown for the break whose tab is open and hidden on the buoy's tab.

```
offshore component = −cos(wind from − shore normal)     +1 straight off the land, −1 straight off the sea
  > +0.3   offshore          within 72.5° of straight off the land
  < −0.3   onshore           within 72.5° of straight off the sea
  between  cross-shore
  ≤ 3 kt   light, whatever the direction

worked hour: 8 kt from 270°
North   normal 194.1°   −cos(75.9°) = −0.24   cross-shore
Center  normal 213.9°   −cos(56.1°) = −0.56   onshore
South   normal 220.9°   −cos(49.1°) = −0.66   onshore
```

[drawing: near] Caption: Each break's chord, with its shore normal drawn out to sea from the midpoint. One wind, three answers.

A wind of 3 kt or less, the Beaufort scale's light air, is “light”: its direction is too faint to matter, and a forecast gives it one anyway. The rule lives in one place on the page, so the card and both Shore direction charts change together.

## [tide] The Tide card

### [tide-coast] From the bay to the open coast

The gauge, NOAA 9410170, is at Broadway Pier inside San Diego Bay. The breaks are on the open coast, where the tide swings a little less and turns a few minutes earlier. Measured against La Jolla's open-coast gauge, and confirmed by NOAA's own offsets for Imperial Beach and Point Loma:

```
open coast = 0.944 × bay, 3 minutes earlier          the card's heights, on MLLW
open coast (MSL) = −0.024 + 0.944 × (bay − MSL)      what breaking uses

worked hour: the gauge read 2.005 m above MLLW; MSL is 0.897 m above MLLW there
card       0.944 × 2.005 = 1.893 m                   → 6.2 ft (1.89 m)
breaking  −0.024 + 0.944 × (2.005 − 0.897) = +1.022 m above mean sea level
```

The source line names the gauge the reading was carried from. The countdown keeps the gauge's own time.

### [tide-turn] The next high or low

The next turn is NOAA's own prediction of high and low water, computed from the tidal constituents. It is the one predicted number on the “LIVE” tab, tagged *predicted*. Rising or falling is read from it: if the next turn is a high, the tide is rising into it. Direction and target come from one source, so they cannot contradict each other on screen.

> **Model choice · never difference the gauge**
> Comparing the two newest gauge readings would get the direction backwards on a large share of readings near slack water, where the real change is smaller than the gauge's own wobble. Picking the highest hour of an hourly prediction would put the time of high water up to half an hour out. So neither is used, and there is no fallback from one to the other.

### [tide-departure] The measured departure

The harmonic prediction is tied to sea level as it was in 1983–2001, and knows nothing of the rise since or of the season. So the gauge's measured level less its prediction, averaged over the last 3 days, is added to the predicted turn's height and to every forecast hour's tide. The measured level itself never gets it, because the departure *is* measured minus predicted.

```
departure = mean(measured − predicted) over the last 72 hours

worked hour: +0.255 m over 73 hourly pairs
```

Breaking needs it. Without a departure the forecast computes no breaking height at all, rather than breaking the waves in water about 0.2 m too shallow.

## [time] Moving through time

### [time-picker] The hour picker

On the Forecast tab, the arrows step through the hours three at a time, and tapping the hour between them opens the full list. It opens on the first hour not yet passed, never one that has.

### [time-past] Past hours: what the page showed then

The Forecast tab reaches 48 hours back. For each hour that has gone by, the forecast figure is what this page showed for that hour: the newest run that had been published before it, which is not always the run on screen now. A past hour is drawn as it was published, with the drawing and the calculation, from that build's own record. When an older build kept only the headline, the card says “The calculation for this hour was not kept” rather than borrowing another build's detail.

### [time-observed] The red “Observed at” line

The red line under it is what buoy 46232 measured at that hour, carried in by the same chain the “LIVE” tab uses: the same windows, seabed and surf zone, with the airfield's wind and the gauge's water level from that hour. It is labelled “Observed at 8:00 AM” with its hour, and the tide's reads “Measured at”. An hour with no buoy spectrum is shown as a gap. It is never filled from the hour beside it, and the newest hour reads “not in yet” until a later spectrum has passed it.

Because both figures go through the same physics, the difference between them is the model's error at the buoy, carried in. It does not check the beach. Nothing has been fitted from it, and no difference or percentage is put on screen, because that would be a claim about the forecast without a verification series behind it.

## [charts] Charts

Every card ends with a “Charts” line, closed until opened. The charts carry no description of their own; this section is where each is explained.

### [charts-using] Using the charts

- **Pick a view** from the menu above the plot.
- **Zoom and pan** with 1D / 7D / 1M / All (Forecast's swell chart: 1D / 3D / 7D / All), or pinch, drag, or ctrl + scroll.
- **Read a value** by swiping sideways across the plot. The readout above the plot follows your finger and keeps the last hour when you let go. A vertical swipe still scrolls the page.
- **The tabs keep their own** window, picked hour and view, and the Wind and Tide charts share the tab's window and picked hour.
- **A gap is a gap**: an hour with no reading is a break in the line at every zoom, never filled from the hour beside it.

### [charts-live-swell] “LIVE”: the Swell charts

Buoy 46232's own spectrum at every hour, carried in by the same chain as the reading above them. They open on the last day; zoom and pan them to go back to the start of the buoy's archive (4 August 2026). Every hour is rebuilt with today's windows, seabed and surf zone, so an earlier hour shows what the current chain makes of it, not what this page said at the time: the last week on every collection, the rest once a day. When the older hours no longer match today's chain they are not shown until they have been rebuilt, so two versions of the chain are never drawn on one line.

An hour with no buoy spectrum is a gap: a pale band with no line through it, at every zoom, never filled from the hour beside it. A break has no breaking height for an hour whose water level was not measured, which is every hour before 17 September 2026. Each tab draws its own line, in ink; only Height draws anything beside it.

- **Height**
  The break's breaking height, with the other two breaks' in lighter lines under it, the more southern of the two dashed, so the three can be compared at a glance on one axis. On the buoy's tab, the buoy's own height alone.
- **Window**
  A break's height through its windows as a share of the buoy's, before the seabed: the [Windows row](#calc-windows). Under it, a dot for each hour marks where the buoy's peak came from, over the break's open windows shaded. The share is the whole spectrum through the windows, so it moves with how widely the swell is spread as well as with where its peak sits. A dot is never “inside” or “outside”: a single bearing tested against a window is the yes-or-no the model refuses.
- **Origins**
  Where the swell arriving at the tab came from, over time, on every break's tab and the buoy's. A black dot every six hours is a hurricane the card would have named then, with the match it would have stated (see [Origin](#swell-origin)), at the distance of NHC's position that sent the train; its name sits by its first dot in view. A grey bar is an arrival read off the swell itself with no storm named for it, at its dispersion distance, over the hours it was arriving. Distance runs on a log scale, 500 to 10,000 miles. Each mark is on a tab only where it was one of that tab's own trains, as on the card; and an arrival is drawn as the storm, not as a bar, where the storm's train at that tab is the arrival's own and Origin read it from within 45° of the storm. Under it, the bearing each came from, as seen from the buoy, never tested against the windows. A moment with no 46232 spectrum, such as the outage of 1 to 17 September, places a named storm on no tab, so Marie's swell, which arrived then, is not on this chart. Rebuilt with today's chain like the rest: the whole archive once a day, the newest hours with every collection.
- **North vs. South**
  North's less South's. Where it crosses zero, which of the two is bigger has flipped.

[drawing: whole] Caption: The windows the Window chart's direction strip shades, here as they sit on the map.

### [charts-live-wt] “LIVE”: the Wind and Tide charts

On the same hours and the same window as the Swell charts. Both are read straight from the collected records rather than rebuilt, so nothing done to the chain can change an earlier hour. They reach back a month, or to where the records begin (18 September 2026 for the wind, 17 September for the tide).

- **Wind**
  The airfield's report taken in the hour up to each hour: its speed, a dot for any gust, and under it the direction it blows from, which a calm or a variable wind does not have. A report is never carried into the next hour. An hour with no report is a gap.
- **Shore direction**
  How often the airfield's wind has been offshore, cross-shore, onshore or light at the break whose tab is open, one bar for each hour of the day on your clock. Each bar is that hour on every day counted, one reading a day, by the [same rule](#wind-sense) as the card. The readout says “over N days”, because a bar is many days' readings, not one hour's.
- **Tide**
  The gauge's sample at each hour exactly, carried to the open coast as the card's is. Past the present, the next 24 hours of harmonic prediction, dashed, with the measured departure added: the one modelled line on this tab, as the card's next turn is its one modelled number.
- **Departure**
  The gauge's measured level less its prediction at each hour, on the open coast, with the 3-day mean of it that the forecast's tide carries.

Night, from sunset to sunrise at the center break, is shaded behind the tide on both tabs, so a low tide in the dark reads apart from one at dawn. Sunrise and sunset are worked out from the sun's position with NOAA's solar equations, not measured.

### [charts-fc-swell] Forecast: the Swell charts

Drawn from the model, every 3 hours, from 48 hours back to the end of the run. They open on three days with the present a quarter of the way in. A break's line is its breaking height only; an hour whose figure was at 5 m of water, or that no run covered, is a gap.

- **Forecast + Observed**
  The newest GFS-Wave run's line over what each of the last eight runs said for the same hours, as the page showed them, and beside the hours that have passed, buoy 46232 carried in by the same chain, in red. Where the run lines bunch, the runs agree; where they fan out, the model has been changing its mind. Runs agreeing is not the same as being right, and the spread between them is not a range the swell will fall in.
- **Swell trains**
  Each train the chain carries in, a dot at its period, larger for a bigger train, with the heading it comes from under it. A new swell arrives long-period first, so it shows as dots stepping down in period. Trains are split hour by hour, so a dot is not the same train as the one beside it, and they are kept only for the runs whose hours were kept in full.
- **North vs. South**
  North's forecast breaking height less South's.
- **Ensemble**
  On the buoy's tab only. GEFS-Wave is the same wave model run 31 times from slightly different weather. The dashed line is the mean of its members at the buoy and the shading one standard deviation either side, beside the newest GFS-Wave run and the red line. It is total height at the buoy with no direction, so it cannot be carried through a break's windows and says nothing about the beach. The chart states how often buoy 46232 has fallen inside the shading, per lead time, over which dates and how many hours. So far that is far less often than a range that size would imply, because the members agree with each other more closely than any of them agrees with the sea, and their mean runs above the buoy. Nothing has been removed from it or added to it to make it look better.

Only the Ensemble view carries a band, and only beside how often the buoy it is drawn for has fallen inside it. No chart shows a difference between the forecast and the red line.

### [charts-fc-wt] Forecast: the Wind and Tide charts

Hourly, over the same reach.

- **Wind**
  The National Weather Service's forecast wind at Coronado (the card's Local wind), with a dot for any gust and its direction under it. Beside the hours that have passed, the airfield's measured wind in red. In grey, GFS-Wave's own wind at the buoy, the one the model makes its wind sea from: hourly to five days and every third hour after, joined across the hours it does not give, never across a measured gap.
- **Shore direction**
  The local forecast's wind at the break whose tab is open, one row a day and one square an hour, so which mornings are offshore reads straight off it. An hour the forecast does not cover is an empty square.
- **Tide**
  The harmonic tide at the open coast with the measured departure added, as the card's is, and the gauge's measured level in red beside the hours that have passed.
- **Daily range**
  Each day's biggest swing between one predicted high or low and the next, starting that day: long bars are spring tides, short ones neaps. Measured between consecutive turns, never as the day's highest high less its lowest low, which would drop a low that crossed midnight and draw a neap that is not there.

The Shore direction “how often” bars and the Departure view are the “LIVE” tab's only. Counting how often over a week of forecast would throw away which day, and a measured departure has no future hours.

## [sources] Data sources and freshness

### [sources-list] Every source, and what it feeds

| Source | What | Feeds |
|---|---|---|
| NDBC buoy 46232, Point Loma South | Hourly directional spectrum, 64 bands; position from NDBC's metadata | “LIVE” swell and its Origin, every chart's buoy line, the red line |
| NDBC buoys 46047 and 46086, Tanner Banks and San Clemente Basin | Hourly directional spectra | Origin's direction (46047), the hurricane match (both) |
| KNZY, NAS North Island | Hourly airfield report (METAR) | “LIVE” wind, local chop, Shore direction |
| NOAA tide gauge 9410170, San Diego | 6-minute measured level, hourly prediction, predicted highs and lows | Tide card, breaking depth, departure |
| GFS-Wave (WAVEWATCH III), NOAA | The model's own directional spectrum and 10 m wind at the buoy, four runs a day | Forecast swell |
| GEFS-Wave, NOAA | 31-member ensemble at the buoy, height only | Ensemble chart |
| National Weather Service grid | Hourly forecast wind at the center break, 7 days | Forecast wind, offshore line |
| USGS CoNED, GMRT | Surveyed seabed and beach profiles (2016) | Refraction, friction, shoaling, breaking |
| NOAA electronic navigational charts | Coastline of Point Loma's tip, the islands, Baja and the break chords | The aperture |
| NOAA solar equations | Sunrise and sunset, computed | Night shading |

When GFS-Wave's directional spectrum is not available, the forecast is rebuilt from the model's separate swell trains instead, with an assumed directional spread, and the “standing on” block above says which was used and what spread was assumed.

### [sources-cadence] Cadence and lag

The observations are collected every 10 minutes and the page refetches them every 5. Every request carries a unique address, so no cache along the way can hand back an older copy. The model runs four times a day, and each run's numbers for the buoy appear about five and a half hours after its nominal time, so the newest forecast always starts a few hours in the past. [How a countdown is worked out](#swell-countdown).

### [sources-dark] When a source goes dark

Buoy 46232 went silent for 16 days in September 2026 and nobody knows why. When a source stops, its card's countdown runs out and turns red, its chart lines break, and nothing is filled in. No other buoy can stand in: 46232 is the only one in the array that sits inside Coronado's windows. If there is no current observation at all, the “LIVE” tab says so and points at the Forecast tab.

## [confidence] Confidence and verification

### [confidence-levels] The four levels

- **Geometry**
  Which bearings can reach each break: coordinates read off NOAA's charts. The firmest level.
- **Model**
  The Forecast tab's wave model, and the physics of the chain, both run on surveyed inputs.
- **Calibration**
  Adjusting the chain to fit what was observed at the beach. None yet: there is nothing to fit to.
- **Observation**
  Waves observed at the breaks. None yet.

The live blocks in [What each tab is standing on](#start-standing) show the current status of each.

### [confidence-physics] Why the physics is never called calibration

Refraction, diffraction, friction, shoaling and breaking are modelled from surveyed inputs and fitted to nothing. Calling them calibration would claim a level the project has not reached. That word is kept for fitting to beach observations, which is the one thing that can turn “physically derived” into something checked.

### [confidence-log] The beach observation log

The planned check is people at the beach. An observer writes down what they see at two or three of the breaks, about half an hour apart, on one tide, with the observer, time and method recorded. One person comparing breaks within half an hour cancels nearly everything that makes judging absolute height unreliable, and what is left, which break is bigger, is exactly what this forecast claims.

- The log is kept as its own record and is never blended into the forecast it judges.
- It never shows a forecast. An observer who has seen one is no longer an independent witness, so the observer's form and this page are kept apart, and this page does not link to it.
- It checks orderings and differences between breaks, not heights, until the step from significant height to face height has been fitted.

Until that record exists, no figure on the forecast page states how well it does, and none will without naming the observations it was compared against.

## [faq] Troubleshooting and questions

### [faq-messages] What a message means

- **“No current observation.”**
  The “LIVE” tab has nothing usable, and says why. Switch to Forecast for the modelled view.
- **“Update due.”**
  The next reading is expected and nothing is wrong yet: the source is at the slow end of its usual lag.
- **“Overdue by m:ss.” in red**
  Past the latest the source normally takes. The reading on screen is still the newest there is.
- **“not in yet”**
  The buoy's spectrum for that hour has not been collected yet. It usually lands 15–35 minutes after the hour.
- **“The calculation for this hour was not kept.”**
  A past forecast hour from a build that stored only its headline.
- **“Every hour in this forecast has passed.”**
  The newest model run has not arrived, so nothing on the Forecast tab is upcoming.
- **“Earlier hours are being rebuilt…”**
  The chain changed, and the archive is being rebuilt with it so that two versions are never drawn on one line.
- **“…or deeper” and a ≤ in the table**
  The waves were already breaking at the 5 m start point, so the break is further out and the height is an upper bound.

### [faq-questions] Common questions

- **Why is there no error bar?**
  An error bar has to be measured against observations of the thing forecast, and none exist at these breaks. A band fitted to something else would look reassuring and mean nothing.
- **Why is the buoy always bigger?**
  It is 29 km offshore with nothing in the way. Every break sits behind Point Loma, the islands and Baja.
- **Why does it disagree with other forecasts?**
  Most regional forecasts read one point offshore, or treat this stretch of coast as one beach. This one applies each break's own windows and seabed. Whether that does better is what the observation log is for.
- **Why is there a gap in a chart?**
  Nothing was measured or modelled for that hour, and a gap is never filled from the hour beside it.
- **Why does the number change for a past hour on “LIVE”?**
  The “LIVE” charts rebuild every hour with today's chain, so an improvement to the physics changes the past hours too. The Forecast tab is the opposite: a past hour shows what the page said at the time.

## [glossary] Glossary

- **Significant height (Hs)**
  Four times the square root of the total wave energy, close to the average of the highest third of waves, trough to crest. What buoys and models report, and what every number here is.
- **Face height**
  The height a surfer calls, measured on the wave's face. A different quantity from Hs, and the conversion has not been fitted.
- **Period**
  Seconds between wave crests. Longer-period swell travels faster, feels the seabed sooner and bends more.
- **Spectrum**
  How a sea's energy is spread over period and direction. The buoy reports it hourly, the model every hour of its run.
- **Swell train**
  One peak of the spectrum: a swell with its own height, period and direction.
- **Wind sea, chop**
  Short-period waves made by local wind.
- **Dispersion**
  A distant storm's swell sorting itself by period as it travels, longest first, because longer waves move faster. What Origin reads the distance from.
- **Forerunner**
  The first, longest-period waves of a swell to arrive.
- **Swell window**
  The range of bearings from which swell can reach a break in a straight line.
- **Aperture**
  All of a break's windows together, and the land that forms them.
- **Blocker**
  Land that casts a shadow: Point Loma, the two Coronado Island groups, the Baja coast.
- **Tangent vertex**
  The one charted point on a blocker that a break's line of sight just grazes, which forms a window edge.
- **Chord**
  The short stretch of shoreline that stands for a break.
- **Shore normal**
  The direction straight out to sea from a chord.
- **Refraction**
  Swell bending toward shallow water as it slows.
- **Diffraction**
  Swell spreading round an edge into its shadow.
- **Shoaling**
  Waves growing in height as the water shallows.
- **Bottom friction**
  Energy lost to the seabed in shallow water.
- **Fetch**
  The open water a wind blows over before it reaches the break.
- **Breaker index (γ)**
  The largest wave height a depth of water can hold, as a fraction of that depth.
- **MLLW, MSL**
  Mean lower low water, the tide card's zero, and mean sea level, which the seabed depths are measured from.
- **Harmonic prediction**
  The tide worked out from its astronomical constituents.
- **Departure**
  The gauge's measured level less its prediction.
- **GFS-Wave, GEFS-Wave**
  NOAA's global wave model, and the same model run as a 31-member ensemble.
- **ENC**
  NOAA's electronic navigational charts, the source of every coordinate in the aperture.
- **CoNED**
  The USGS Coastal National Elevation Database, a seamless survey of land and seabed.
- **46232, KNZY, 9410170**
  The buoy, the airfield and the tide gauge.

This page is built from the same files as the forecast page: the drawings from the geometry the forecast reads, and the “standing on” blocks from each tab's own file as the page loads. The worked hour is rebuilt from the archive by a test whenever the chain changes. Geometry only says which bearings can reach each break, not how big anything is; nothing on this page has been measured at the breaks.
