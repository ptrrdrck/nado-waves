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

A swell forecaster for the three breaks on Coronado Central Beach: North, Center and South. All three read the same offshore buoy, CDIP 191 off Point Loma, and they get three different answers. The reason is geometric. Point Loma, the Coronado Islands and the Baja coast block most of the ocean from these beaches, and the gaps they leave open, the *swell windows*, point a different way from each spot on the sand. Walking from North to South moves the west edge of the window by about {{geo:west-sweep}}.

The premise is that a forecast that respects that geometry can say something a regional forecast cannot: which of the three breaks is holding more of today's swell.

### [start-claims] What it claims, and what it does not

**Nothing has ever measured a wave at these three breaks.** This is **physically derived**, not an accurate forecast, and it carries no error bar because there is nothing to compute one against. What it claims is which break holds more of today's swell — not how big it is.

Each break's number is the buoy's swell carried by physics to where it **breaks**: through the windows the coast leaves open, bent over the seabed and slowed by its friction, diffracted round every window edge, lifted by shoaling into 5 m of water with local wind chop added, then carried in over the surveyed beach profile at the tide of the moment until it breaks. It is still not a wave height at the beach as a surfer would call it: a significant height, not a face height, and the step from one to the other has not been fitted; the beach profile is a 2016 survey rather than this season's sandbars; and nothing has checked it against the sand.

### [start-minute] The page in one minute

From the top of the forecast page down. The figures are a real hour, noon on Monday 28 September 2026, at the North break.

[annotated card, row by row:]
- “LIVE” / Forecast
- North / Center / South / Buoy
- 3.5 ft (1.07 m) breaking height ▾
- the window drawing, and the swell trains under it
- CDIP 191 | 15 min ago | **Update in 59:12**
- **Charts** ▴
- **Wind** 9 mph (8 kt) from the west, cross-shore at this break · **Tide** 6.2 ft (1.89 m)

1. **Two tabs.** “LIVE” is built only from measurements, Forecast only from a model. [Two tabs, two chains](#chains).
2. **One tab per break**, ranked by how much swell each one's windows let in, with the buoy itself always last. [Break tabs](#swell-tabs).
3. **The headline**: the height where the waves break, and the depth they break in. The caret at its end folds out the calculation behind it. [Reading the table](#calc-table).
4. **The windows**, drawn facing the way the break faces, and the wave trains that make up the number. [The window drawing](#swell-drawing).
5. **Where it came from, and when the next one is due.** [Countdowns](#swell-countdown).
6. **Charts**, closed until opened, the last line of every card. [Charts](#charts).
7. **Wind and Tide**, cards of their own because one station feeds all three breaks. [Wind](#wind), [Tide](#tide).

### [start-wide] On a wider screen

The page above is a phone's. Wider than a phone, the same cards are laid out to use the room; what they say does not change.

- **A tablet held upright** (700 to 949 px wide) keeps the tabs, with Wind and Tide side by side under the Swell card.
- **From 950 px**, the three breaks sit side by side: North, Center, South, in the order they sit on the sand, never ranked, so a column's place is its break's. Each column's headline, calculation rows, trains and drawing sit level with the same ones beside it, and one caret opens all three calculations. The buoys get a card of their own, three across. [Origin](#swell-origin) becomes one block for the beach. The swell's charts get a card of their own too, with the break or the buoys picked above the plot. The Wind card gives every break's offshore, cross-shore or onshore line, and the Sun card every break's sunset, each under its break's name.
- **From 1280 px**, what the whole beach shares sits in a column at the left: the tabs, the Briefing, then Wind, Tide and Sun. The breaks, the buoys and the charts sit beside it.

On a wide screen the [Briefing](#briefing) is always open. Its green dot then marks an update you have not been at the page for, and goes at your next touch, click, key or scroll anywhere on it. And every chart has a button beside its menu that opens it full screen; the same button, or Escape, closes it.

### [start-standing] What each tab is standing on, right now

Each tab's file says which of the four confidence levels (geometry, model, calibration, observation) it has reached. These blocks are read from those files as the page loads, so they say what the forecast page is standing on at this moment. A level that reads none is one the project has not reached. [The four levels](#confidence-levels).

[live block: What “LIVE” is standing on]

[live block: What Forecast is standing on]

## [chains] Two tabs, two chains

The two tabs are not two views of one forecast. They are two separate *evidence chains* that share the geometry and nothing else, and the page never mixes a number from one into the other.

### [chains-live] “LIVE”: measurements only

Built from what was measured: CDIP 191's directional spectrum, the wind reported at the airfield on North Island (KNZY), and the water level at the San Diego Bay tide gauge (NOAA 9410170). The quotation marks are deliberate. The feeds update, but a reading is always some minutes old, and each card's countdown says exactly how old.

It carries exactly one modelled number, the tide's next high or low, and that is labelled *predicted* wherever it appears. [Why that one](#tide-turn).

Its Buoys tab also shows two more buoys, NDBC 46086 at San Clemente Basin and NDBC 46047 at Tanner Banks, measured the same way, and a [rose](#swell-roses) under each buoy. Nothing on any other tab is computed from either. [Why they are there](#swell-tabs).

Above its cards, the [Briefing](#briefing) folds out a short read of the swell, the conditions and the day's tides, from the same measurements and North Island's weather reports.

### [chains-forecast] Forecast: the model only

Built from the GFS-Wave model run by NOAA (WAVEWATCH III), read at the buoy's position and carried in through the same windows, seabed and surf zone. Its wind is the National Weather Service's forecast at Coronado and its tide is the harmonic prediction. It shows every third hour, from 48 hours back to the end of the newest run.

Above its cards, the National Weather Service's coast and ocean alerts over the hour shown, a line each. [The alerts](#briefing-alerts).

### [chains-apart] Why they are never mixed

So that you always know which chain a number belongs to. A forecast hour that has gone by gets a blue line under it that comes from the measured chain, and that line is labelled “Observed at” with its hour, never blended into the forecast figure above it. [The blue line](#time-observed).

A refresh keeps the tab you chose. A new visit always opens on “LIVE”.

## [briefing] The Briefing

Above the “LIVE” cards, a **Briefing** line folds out a short read of the beaches, so the cards need not be put together by hand. Closed, it says only “Briefing” and when it last updated, with a green dot while that update is one you have not opened on this device; opening it removes the dot. Nothing about the conditions shows until it is opened. On a wide screen it is always open, and the dot goes at your next touch, click, key or scroll on the page ([On a wider screen](#start-wide)).

### [briefing-stories] What it says

When the National Weather Service has a coast or ocean alert in force, it comes first, a line each ([below](#briefing-alerts)). Then three blocks, always in the same order:

- **Swell**: two sources, never matched to each other. First the beach, from CDIP 191: the breaking height at the three breaks as one range in whole feet, the lowest rounded down and the highest rounded up: the cards' own numbers, a significant height, not a face height. It is set as a headline, beside it a line of the biggest breaking height each hour over the last 24 hours, broken where an hour is missing. Under it, a line for each swell train at any of the three breaks at least half the height of the biggest one anywhere, biggest first. Each break sees only the part of a swell its windows let in, so one swell can read a few degrees and a second apart at two breaks: W at 9.1 s at one and WSW at 9.9 s at another. Each break's train is therefore matched to the train at CDIP 191 it belongs to, the one holding its peak period (and where the buoy split a band by direction, the side holding its heading), and trains that are one train at the buoy are one line, the biggest's. Two swells only a second or two apart, or from directions the buoy cannot part, can still read as one. Wind sea and local chop never are listed. Each says where it comes from and its period, as its row on the card does: offshore, not the direction it arrives from in 5 m of water. Then its status, read at CDIP 191 in that train's band: the periods it holds, from the offshore directions that hold nine tenths of what it carries to the break. That band's energy, averaged over three hours, is *building* when up a quarter or more on three hours before, *fading* when down a quarter or more, *peaking* when the day's highest came in the last three hours, and *holding* otherwise. Nothing follows a train from one spectrum to the next, so this is the band's energy, measured at the buoy before the windows, not the train's at the break. Then each west or north-west swell Tanner Banks holds, a line each opening on its compass point, with how it is doing there (“building offshore”) and when it is due here, while some of it is still to arrive ([below](#briefing-upstream)). A small grey mark in the margin, a dot sending two arcs, points the way that swell is travelling. If CDIP 191 is dark it says so and nothing else.
- **Tides**: today's tide as a curve, from midnight to midnight at Coronado, never past it: the harmonic prediction at the open coast with the gauge's departure, as the Tide card carries it. Each high and low tide has its height by its dot and its time on the axis under it. The hours already gone, and their turns, are grey; an open dot marks where the tide is now, a ring rippling out of it every few seconds; nights are faintly shaded, and the day's sunrise and sunset are above the shading, at its edges, each a small sun on the horizon with an arrow up or down beside its time, grey once passed. Those are the times the sun crosses the sea horizon at the center break: through most of the year it drops behind Point Loma from the beach a few minutes earlier ([the Sun card](#sun)). Tap it to see that it is predicted, from which gauge, and the departure it carries.
- **Conditions**: the water temperature off Coronado, from the receiver on one of the city's shark-monitoring buoys, which the lifeguards keep and the Shark Lab at California State University, Long Beach runs, about 3–7 ft (1–2 m) down: Center's buoy, else South's. The lab loads each day's readings the following night, so it is normally yesterday's water, and a tapped row says so; a receiver lying on its side on land is never read. Its thermometer is part of the receiver, not a sensor of its own: over the 60 days to 29 October 2026 it read 1.1 °F (0.6 °C) warmer on average than the lab's own water sensors on the same buoys (19,129 pairs), and off Coronado 0.7 °F (0.4 °C) cooler than CDIP 191 through September and October. When neither buoy has a reading from the last 48 hours, the row is CDIP 191's. The two are never mixed: the row, its arrowhead and its line are one source's. Then the air temperature, humidity and pressure in North Island's newest weather report (KNZY). Rain only when some fell: the last hour's and the last 24 hours', both shown when either is above zero. Each row's arrowhead says whether it is up, down or the same (a dash) against an earlier reading: water and air three hours back, because from one reading to the next they are usually the same; humidity and pressure the report before. Beside it, a line of its recent readings, broken where one is missing: water over 14 days, air and humidity over 24 hours, pressure over 3 days, and rain a bar a day for a week. Tap a row to see when it was read, by which station, and the reading it is compared with.

### [briefing-words] When it updates

It is rebuilt with every collection, but it *updates* only when what it says about the alerts, the swell or the tides changes, as printed: a change too small to show is no update. The conditions refresh with each collection without counting as one. Each update is kept in the repository's record of briefings, words and numbers, with the conditions of that moment.

It never uses the model. GFS-Wave and its ensemble belong to the Forecast tab; the Briefing is the “LIVE” chain and North Island's reports. Its wording, every case it can take, is in `docs/briefing_wording.md`.

### [briefing-alerts] NWS alerts

The National Weather Service's own alerts for the coast and the ocean here, a line each while one is in force: “Coastal Flood Warning until 2 PM Sun”, or “in effect” when it gives no end. The name links to the Weather Service's page for it, the grey *NWS* tag says whose it is, and a tap shows its own headline. Every alert for the coastal waters off Coronado (zone PZZ750) is shown, and from the land zone (San Diego County Coastal Areas, CAZ043) its coastal flood, high surf, rip current, beach hazards, tsunami and storm surge alerts — never heat, fire weather or wind on land. They are the Weather Service's words, not this page's, and nothing here checks them.

The times are the alert's: from the hazard's start, never before the alert was issued, until its end. A newer alert that replaces it takes over from when that one was issued, and one that cancels it ends it then. An alert that starts, moves its end or ends is a Briefing update; the same alert sent again in the same words is not.

On the Forecast tab the same alerts sit above the Swell card, over the hours they cover: each one in force at some moment from the hour shown to the next one the picker offers, saying “from” when it starts after the hour shown. A past hour shows the alert as it stood then. The alerts are collected with every collection and each is kept as the Weather Service published it. One issued and ended between two collections is never seen; that is a gap, and nothing fills it.

### [briefing-upstream] Swell seen first at Tanner Banks

NDBC 46047 sits 198 km west of CDIP 191, in open water, so west and north-west swell passes it first. A swell is found by its rise: its energy from the west (250–280°) or north-west (280–330°) up threefold in a period band (8–10, 10–12, 12–14 or 14–17 s) in the last three days. A swell's long periods arrive first, so its bands are the newest rise and each longer band that rose before it, within a day. The line names the band due next, “10–12 s”, and says when it is due at CDIP 191: the distance along its direction of travel at deep-water speed, *gT*/4π, about 3.5 to 6 hours. Then when it is due at the breaks, computed along the refracted rays from CDIP 191 to each break: 25 to 60 minutes. Once that band's time at the breaks has passed, the line moves on to the swell's next band, and once the last has passed it goes: from then on the swell is for the headline above to show, if it reaches the beach at all. It also goes sooner if Tanner Banks stops holding it, when its energy from that direction falls below a third of its peak. Over the two months to 24 October a line like this showed on about one hour in five.

Each ends on how the swell is doing at Tanner Banks now, not at the beach: *building* while its energy is up a quarter or more on three hours before, *fading* once it is under half of its peak, and *peaking* otherwise.

Checked against two months of both buoys' spectra, three ways. On average the archive agrees: north-west swell reaches CDIP 191 3.5 to 6 hours after Tanner Banks, and south swell much sooner, as the geometry says it should. One swell cannot be timed, though: at the shadowed buoy a single swell's arrival is too mixed with what is already there. So the due time is computed, never a measured arrival, and it never says how big, since how much gets past the Channel Islands is for CDIP 191 to show. The 8–10 s band was added after that check, which covered 10 to 17 s.

### [briefing-gate] Wave observer

The Observer switch at the foot of the page, after Docs. On a phone where it is on, the page opens on a quiet question, “Logging the beach today?”, and shows nothing else until today's log is done or you say you are not logging today. It comes back at midnight. Someone who has seen a forecast is no longer an independent witness, and the log is what will one day check this page, so the log comes first. That question is the one place the page links to the log. Turning it on after you have already looked starts it tomorrow.

### [settings] Units and theme

The last two settings at the foot of the page. Each is kept on your phone, as Observer is.

**Units** shows what it is set to, and each tap moves it on: *Both*, the default, gives every number in feet, miles per hour, miles, °F and inches with the metric figure in parentheses, “3.5 ft (1.07 m)”; *Imperial* gives the first alone; *Metric* gives the parenthesised figure alone, “1.07 m”, in metres, knots, kilometres, °C, hectopascals and millimetres. A metric number is never rounded again: it is the same figure Both shows in parentheses. The chart axes and the rose's rings step in metres and knots on Metric. Wind stays in knots, as the buoys and the forecast models publish it. This page keeps both units throughout, because its worked numbers are checked against one another.

**The theme** is the half-lit circle at the end of the line. A tap gives the other theme, light or dark; switch back to whichever your phone is set to and the page forgets the choice and follows the phone again. This page follows the same choice.

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

CDIP 191 publishes its spectrum every hour: for each of 64 frequency bands, the energy in that band and four numbers that describe which directions it came from. Height comes from the total energy:

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

On the “LIVE” tab the wind is KNZY's; on the Forecast tab it is the National Weather Service's forecast at Coronado. An hour with neither has no local chop: the model's wind at the buoy is out at sea, too strong for Point Loma's lee and blind to the wind near the shore.

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

If the waves are already breaking at the start point, the true break is further out than the profile begins. The Wave break row then says “at 16 ft (5.0 m) depth or deeper”, and its height is marked ≤ as an upper bound. Without a measured tide no breaking height is computed at all, and the card shows the 5 m figure, labelled with its depth. That is why no hour before 17 September 2026 has one.

### [calc-table] Reading the calculation table

The caret at the end of a card's headline folds out the table. Each row is one step above. **Change** is what that step added or took away, **%** is that change as a share of the row before, and **Hs** is the height after it. Read down, the last row is the headline. A step whose row is missing was not in the build that made that hour.

The Local chop row names the chop's period and the fetch it grew over: behind land, the water to the land upwind; over open water, the reach between the buoy and the break. The last row is the breaking height at the tide of that hour.

### [calc-not] What the number is not

- **Not a face height.** It is a *significant height*: the average of the biggest third of waves, trough to crest, the way buoys and wave models measure height. A surfer's call is different again, and the conversion between the two has never been fitted, because nothing has observed these breaks.
- **Not this season's sand.** The beach profile is the 2016 CoNED survey. A sandbar would move where and how the waves break, and nothing here knows where this season's bars are. On a profile without bars the tide changes *where* the waves break far more than *how big* they are.
- **Not checked.** Every step is physics and none has been compared against the sand. [Confidence and verification](#confidence).

## [swell] The Swell card

### [swell-tabs] Break tabs and the Buoys tab

One tab per break, ranked by how much of the buoy's energy its windows let through, with the Buoys tab always last. It shows the swell at CDIP 191, 29 km offshore, with nothing in the way, so it is always the biggest number, and it is the one the breaks are measured from. On a wide screen there are no break tabs: the breaks sit side by side, North to South, and the buoys are a card of their own ([On a wider screen](#start-wide)).

On “LIVE”, each buoy's provenance is one line of joined pills, each growing out of the one before it: the station, with a dot, then how long ago its spectrum was taken, then the countdown to the next. The Wind and Tide cards' provenance is the same line: “METAR KNZY”, the age and the countdown; “NOAA 9410170”, the age and the countdown. On a narrow phone, where the pills do not all fit, one wraps to start the next row and stands on its own. Point Loma South's station reads “CDIP 191”: Scripps' Coastal Data Information Program runs the buoy, and its spectra reach this page through NDBC, which lists it as 46232. Tanner Banks' reads “NDBC 46047” and San Clemente Basin's “NDBC 46086”, as NDBC runs those buoys itself. This page names every buoy that way, in its charts and here. CDIP 191's line sits under every swell tab, the break tabs included, because every break's numbers come from its spectrum. The dot is green while that buoy's spectra arrive on time, fades in and out once the next one is due, and turns red once it is overdue. It changes exactly when the [countdown](#swell-countdown) beside it says “Update due” and “Overdue”, from the same two instants. With reduced motion on, a due dot holds at half strength instead of fading.

On Forecast, every card's provenance is the same line of joined pills, with no dot and no countdown, because a model run is not a feed arriving on a clock. The swell, and the model's wind at the buoy: the buoy the model is read at, “CDIP 191”, then “GFS-Wave”, then the run and how far ahead of the hour it was made, as in “Oct 15 at 5:00 AM, 9 h ahead”. The local wind: “NWS”, the forecast grid cell, then when the National Weather Service last updated that grid, which under a past hour is the update the build that showed it read. The tide: “NOAA 9410170”, “Harmonic”, then the gauge's measured departure from the prediction over the last 3 days that the hour carries, or “No departure”. The hour itself is the one in the bar above the cards.

On “LIVE” the Buoys tab also shows NDBC 46086 at San Clemente Basin, 81 km west-south-west. It is read the same way as 46232: the combined height of its directional spectrum, and its [swell trains](#swell-trains), with a train fed from two directions naming both. It is not open ocean: it sits inside the south break's window, the only buoy besides CDIP 191 that does, and outside North's and Center's. It is still not carried to any break, because a buoy 81 km out is not the sea at the beach and CDIP 191 has no stand-in, and no number on any other tab comes from it. Its spectra are stamped every half hour, at :20 and :50, so it has its own observed time and its own [countdown](#swell-countdown), measured on its own readings.

Under it is NDBC 46047 at Tanner Banks, 222 km west, the buoy in the array that the islands shadow least, read the same way. It is open ocean outside every break's windows, so it too is not carried to any break. It is there so the swell before the Channel Islands and the Bight can be read beside the swell at CDIP 191. It too stamps at :20 and :50, with its own observed time and its own countdown. The Forecast tab's Buoys tab shows CDIP 191 only, because the model run is read at CDIP 191 alone.

Each buoy's headline folds out, as a break's does: tap it, or the caret at its end, and what sits between it and the buoy's provenance opens beneath it — its swell trains, and on “LIVE” its rose and one sentence under it: the station, linked to its public page (CDIP's for CDIP 191, and NDBC's for the other two), how far offshore it is and its bearing from Center break, both worked out from NDBC's position for the buoy, then what is read from it and what it is for here. It is closed until opened, except CDIP 191's, which opens whenever the Buoys tab is selected. Each buoy opens on its own, and the page keeps them as the reader left them across a refresh. On the Forecast tab it folds CDIP 191's trains; the observed line under a past hour stays out of it, as it does on a break's tab.

### [swell-headline] The headline

The breaking height, in feet with metres in parentheses: “3.5 ft (1.07 m) breaking height”, or in one of the two by [the Units setting](#settings). The depth it breaks in is the last row of [the calculation](#calc-table), under Wave break: “at 8 ft (2.3 m) depth”. When there is no tide to break it at, the headline is the height in 5 m of water and says so. The caret at its end opens the calculation.

### [swell-drawing] The window drawing

The break's windows, drawn facing the way the break faces: open water above the shore, the grey shadows of the land either side, and an arrow for each swell train, two for a train arriving from two directions. Tap a shadow for the land casting it and the share of this swell it takes; tap a window for the land either side and its width; tap an arrow for that train. Tapping a train in the list above the drawing picks its arrows the same way, and the train's row stays highlighted while it is picked. Tap it again, or the sand below the shoreline, to return. A mouse previews on hover, and the keyboard reaches every part with Tab.

A picked train also gets an arrowhead at the break, pointing in along the direction it arrives from in 5 m of water, after the seabed has turned it, and its caption gives that heading on a second line. [The next section](#swell-bend) says how it is worked out.

### [swell-bend] Which way a swell arrives in 5 m of water

Every arrow from the rim of the drawing is the direction a train's energy came from offshore, the frame the windows are drawn in. On its way in, a swell slows over the shallowing seabed and turns toward the shallows ([step 3](#calc-refraction)), so by 5 m of water it comes from much nearer straight out to sea. The arrowhead at the break is that heading: where each ray carrying the train's energy arrives from at the start point, averaged by the energy each carries. It is worked out for every train from the spectrum of the hour, at each break.

The table is the same calculation for one narrow swell at a time: 14.3 s, spread ±10° about each offshore heading, through the soft window edges and bottom friction as a train is. A dash means less than a tenth of that heading's energy reaches 5 m, too little for its direction to tell you anything.

[table the page fills in: bendtable]

At 10 s and 18.2 s instead of 14.3 s, the heading in 5 m moves by 3° at the median and 9° at most, over the 30 cells all three periods give.

Read down a column and a wide spread of offshore directions arrives inside a narrow one. By 5 m of water, the direction a swell came from offshore is mostly gone: from anywhere the windows let in, it arrives within about 20° of straight in.

Most of that turning happens well out to sea, not at the beach. Each break sits behind a wide, shallow shelf, 8 to 15 m deep for 3 to 5 km, and a swell is turned crossing it. The shelf is uneven, so neighbouring rays are turned by different amounts and cross each other: about half of them swap order between deep water and 5 m. That is how a swell can end up on the far side of straight in: at Center, one from 230°, west of the 214° normal, arrives from 205°, south of it. The seabed close to each break faces the way its beach does; it is the shelf further out that does this.

So the offshore direction decides how much swell gets in, through the windows; near the sand it says much less about the direction the waves come from. And where rays cross, the ray method is at its limit: read each heading as a few degrees either way, not to the degree.

It stops at 5 m. The last few metres turn a swell further still, and nothing here observes either. Physics on the surveyed seabed, fitted to nothing; generated by python -m forecast.bending --write from the same tables the cards use.

### [swell-trains] Swell trains

The number is rarely one swell. The spectrum is split into separate trains, each with its height, period and direction, and the local chop is listed as its own train, tagged. The trains add up, in energy, to the number above them.

The split happens in two steps. First by period: the energy is followed from long periods to short, and cut wherever it dips between two peaks. A dip counts only if it is deeper than the buoy's own sampling noise could make it, so a single swell is not cut in two by the wobble between neighbouring bands. Then by direction: where one of those pieces gets its energy from two directions, each carrying a fifth of it or more, it is divided heading by heading, and each direction becomes its own train with its own height, and its own period, read from its own energy. A south swell at 14 s and a west-north-west swell at 12 s that share a stretch of periods are two lines, not one line with two directions.

The biggest train at the buoy need not be the biggest at a break, because the windows take whichever trains point at the blocked sectors. In the worked hour the buoy's lead was 11.8 s from 219°, and North's was 12.5 s from 206°.

What the buoy cannot tell apart, no split can. A buoy reports four numbers about direction for each band, and from those one swell 20° wide and two narrow swells 30° apart look the same. Read by maximum entropy, a single swell 20–35° wide even comes back as two equal peaks 32–60° apart. So two equal directions closer than 60° are kept as one swell. Two swells of the same period are told apart only when they are far apart in direction, and two from the same direction only when a real dip separates their periods.

Rarely, a single train still carries two directions it could not be divided by, and then both are given, “WSW 258° & S 180°”, with an arrow from each on the drawing. Every train keeps to one line, giving as much as fits beside its height and period: the degrees when there is room, the compass points alone when there is not.

This replaced, on 8 October 2026, a split by period alone, which labelled a quarter of swell trains with two directions at one period and one height — and the two directions’ own peaks sat a second or more apart on most of them.

### [swell-roses] The roses on the Buoys tab

On “LIVE”, under each buoy's reading on the Buoys tab, a rose drawn from that buoy's spectrum. Each petal points where its energy comes from, one petal for each of the sixteen compass points, 22.5° wide. A new rose is drawn for every spectrum: hourly at CDIP 191, every half hour at NDBC 46047 and NDBC 46086. Each rose opens paused on the newest, the spectrum its headline reads, whenever it comes into view; the play button runs the last six hours of them in a loop, then the newest holds. One clock drives every rose, so all of them always show the same moment. The line under each rose is those six hours, with a tick for every spectrum that buoy sent; a missing spectrum is a missing tick, and while the loop passes it the rose says so rather than showing the one before. Tap the line to go to a moment, or step it with the arrow keys; the button to its left plays and pauses the loop, and the two at its right switch the view: **ft** for Height, **s** for Period. The Period legend's row stays empty on Height, so switching never moves the page.

**Height** gives each sector's energy as a height. Heights combine in energy, so the petals do not add up to the combined height above them; the square root of the sum of their squares does, exactly. **Period** gives each sector's share of the spectrum's energy, split into five bands by the period of the energy, the shortest palest and the longest in ink. Each buoy's rose has its own scale for each view, given in the one line under it, beside the frame's time and combined height (or share of the energy): evenly spaced rings, at most five, the outermost being the largest petal in its six hours rounded up to the next ring (the next whole foot, until the petals pass 5 ft and the rings go every 2 ft), so no petal passes it. That ring is the drawing's edge, with N, E, S and W just inside it. The scale holds through the loop, so a petal that grows from one frame to the next really grew. The buoys' scales differ, so compare them by their rings, not by the size of the petals.

Tap a swell train above a rose to light its period range on it: the frequencies that train holds in the newest spectrum, in ink, over the whole rose dimmed. Where one band of periods came from two directions and is listed as two trains, each lights its own side of the rose, and the range names its directions too. The light stays through the loop, and the line under the rose names the range and what it holds in that frame. It is the same range in every frame, not the same swell: nothing follows a train from one spectrum to the next, so in an older frame the range may hold part of another. Tap the row again to clear it; a new spectrum clears it too, since its trains are new.

A petal is the height of one compass point's energy alone, so a swell spread over several points shows petals well under the combined height: on 7 October CDIP 191 read 3 ft combined, spread over seven to ten points, its largest petal 1.8 ft.

A rose is the direction-reading method's picture of four numbers per frequency, not a measurement at each bearing, and it is the same reading the trains above it come from. NDBC 46047's spread reads broader than CDIP 191's, so its petals spread over more compass points. The two buoys can also point one swell different ways for a real reason: CDIP 191 sits behind the Channel Islands, NDBC 46047 in the open ocean before them. Neither rose is carried to a break.

### [swell-origin] Origin: where the swell was born

On a wide screen, where the breaks sit side by side, Origin is one block for the beach under them: each arrival once, under the names of the breaks it reaches. An arrival that reads differently at two breaks, another train or another period, is listed for each, in its own words. The rest of this section describes one break's.

On “LIVE”, the **Origin** line folds out, like the charts, from its own line right above “Charts”. The number in parentheses beside its title counts the origins arriving at that tab now, named hurricanes and readings alike, and is not there when nothing is arriving; a last readable arrival is not counted. Under it, each train that came from a distant storm says where that storm was: a sea, about how far away and in which direction, and when the swell left it. It is read backwards off the buoy's own spectrum. It is not a forecast, and nothing observes the storm.

Long-period waves travel faster than short ones. In deep water a wave group moves at *gT*/4π, so a 20-second swell outruns a 14-second one. A storm makes every period at once, and by the time the energy has crossed an ocean the long periods have pulled ahead. At the buoy they arrive in order, longest first, and the frequency rises in a straight line with time:

```
f(t) = g·(t − t₀) / (4π·R)          f = 1/T, the frequency of the train's peak
R  = g / (4π · slope)                the distance to the storm
t₀ = where the line reaches f = 0    when it blew
```

Every hour, each peak in the buoy's spectrum between 10 and 29 seconds is found and followed from hour to hour. A peak that moves steadily to shorter periods for at least 12 hours, starting at 13 seconds or longer, on a line straight enough to read (R² of 0.8 or more), is a readable arrival.

The direction is read where the sea is open: at NDBC 46047, Tanner Banks. Never at CDIP 191 itself: on a north-west swell it reads two directions at once, a westerly one held near 270° and the south's, and their average falls 50 to 74° too far south. Nor at NDBC 46086 in the San Clemente Basin, which is open to the south but holds a north-west swell near 279° whatever its real direction. And not at NDBC 46047 either when its energy at that period comes from two directions, each at least 15% of it: which one is the arrival's is not known, and their average would point between them. An arrival with no direction read gets a distance and a date and no place.

An origin belongs to a train, so a break shows only the arrivals that are one of its own trains, and the buoy's tab only those among the buoy's.

Every origin is written the same way, a head and one paragraph, whatever kind it is, and each is the same run of parts in the same order: a part with nothing to say is left out, and nothing is reworded. The head says what it is: a hurricane or tropical storm by name, the name linking to the National Hurricane Center's page for it, with its track and map; a sea; or an **unplaced storm**, either because NDBC 46047 has the train from several directions at once or because NDBC 46047 does not have the train at all. The paragraph opens with one sentence: the train, the day it was sent, and how far away the storm was. A reading's day is “about”, because it is fitted off the swell like the distance; a named storm's is the time of NHC's position. The next sentence says where the direction comes from. For a named storm it is NHC: where NHC had it, by bearing in degrees and compass point, and its winds and central pressure at that time, when it sent the train, which may not be what they are now. For a reading it names NDBC 46047 and says what it holds: the train from one bearing; the train from every one of several, so no place is given; or not the train at all, so no place is given. Then, for a named storm, how long its swell has been arriving, by its track, at the buoy where it has been arriving longest. How well that track agrees with the swell is what names the storm (described below), and is not repeated on the card; for a reading, how long the swell it is read from has been arriving, because a reading can still move while the train is arriving. Either way it reads “Arriving for … h so far.” When no readable swell is arriving, the last readable arrival at that tab in the last three weeks is shown after a line saying so: whichever ended later of the last swell read backwards there, with the train it was at its busiest hour, and the last storm named there, as it was last named, its paragraph ending with the day that train arrived, with no hours. A named storm's name is followed by its symbol, the eye open for a tropical storm and filled for a hurricane. No sources are listed under the entries: every train is read off CDIP 191's spectrum, a named storm's too; a reading's storm is then read backwards from it, with its direction from NDBC 46047; a named storm's position, winds and pressure are NHC's best track, an analysis; and each is described in this section.

How far the distance can be taken. The same storm read independently at two buoys gives distances about a fifth apart at the median: 18% between six Southern California buoys and buoys 1,000 to 4,000 km up the swell's path (2023–2025), and 25% between CDIP 191 and NDBC 46047, NDBC 46086 and NDBC 46258 (August to October 2026). So the card rounds to the nearest 500 miles and 500 km, says “about”, and names a sea rather than a point. A storm is an area that moves, and one running toward the coast while it blows reads nearer than it was. The version this grew out of also said which buoys upstream had seen the swell pass; measured, that check could not tell a storm 4,000 km away from one 6,000 km away, so it is not shown.

Checked against the hurricanes the National Hurricane Center tracked in the eastern and central Pacific, August to September 2026, run forward: where and when each one's swell had to arrive, against the energy the buoys measured from its direction, with the same storm moved days earlier and later, and turned 45°, as controls. Hurricane Marie's swell is found that way at two buoys independently. None of the readings this card made that season survives it: four that read as “Tropical Pacific” due south to south-south-west had no hurricane near at all, and the two that agree with a tracked storm in timing and direction (Polo, Nolo) agree no more often than shuffled directions do. A reading of a nearby tropical storm on this card has been, so far, more often wrong than right. Readings of the Southern Ocean and the north-west storm track cannot be checked this way.

**Swell from a hurricane.** What can be shown is the converse: a hurricane the National Hurricane Center is tracking, with how well its track matches what the buoys measured. Each position on its track at hurricane strength, and each after it while NHC still classes the storm a tropical storm, with open water to the buoy, says when each period of its swell must arrive: a hurricane that weakens goes on sending swell, and stays named for it; a storm that never reached hurricane strength is not. Positions whose path crosses the Baja peninsula or the mainland are dropped. As of the newest spectrum, the energy NDBC 46047 or NDBC 46086 measured from the storm's direction on that schedule is set against the same storm's schedule moved back in time, every 12 hours up to 30 days, when its swell was not arriving. The **match** is the share of those earlier moments it beats on both counts: more energy on schedule than usual for each period, and more from the storm's direction than from 45° to either side. It is stated only when the swell on schedule is livelier than usual on both counts and there are at least 20 earlier moments to beat. It is a count, not a probability, and it says where a train came from, never how big it is.

Under Origin, “Hurricane …” appears when the match is 50% or more, or “Tropical Storm …” for a train the storm sent after it had weakened: it is named for what it was when it sent that train, as its winds are. The card names the storm and says how long its swell has been arriving; it shows neither the match nor the counts behind it. Read against the control below, a match is **strong** from 90%, **partial** from 70% and **weak** from 50%. Beating a copy moved earlier means the swell on the real schedule had more energy, and more of it from the storm's direction, than the swell on the copy's schedule. The control below says how often a track moved to where its swell was not gets as far. It shows on a break only when one of that break's own trains is the storm's, and a train is the storm's only when four things hold. Its period is on the storm's schedule. It reaches the break from within 45° of the storm; refraction turns a swell here by at most about 30°, so a train further round is another swell with the same period. Tanner Banks or San Clemente Basin, whichever the storm is matched at, has that period coming from the storm, half as much again as from 45° to either side, the match's own test asked of one train. And Origin is not reading it from more than three times the storm's distance, or less than a third of it: those are two sources sharing a period and a side, and the train stays Origin's on every tab. Of the trains that pass, the storm's is the one its track has arriving closest to now, not the biggest, so every break ranks them the same way. Neighbouring trains that are one band of the storm's energy at that buoy are one swell the break's own reading cut in two, and are named together: “The 10.5 and 11.1 s trains”. One storm is never named on two separate trains: nothing measured here, nor found published, shows a storm sending two. Where the storm was, its winds and its central pressure are NHC's, from the position that sent that train, the distance rounded to 100 miles and 100 km, and the sources say so: a best track is an analysis, not a measurement.

What the words are worth. Asked every six hours from August to 10 October 2026 as of each moment, counting each storm's tropical storm days after it had been a hurricane, the card would have named Marie (4 to 10 September; strong at NDBC 46086 by the 6th, partial at best at NDBC 46047, 80%), Polo (27 to 30 September, partial at best, 78%), Odalys (26 to 29 September, partial at best, 82%) and Rachel (5 to 10 October; strong at NDBC 46086, partial at best at NDBC 46047, 79%). The same question asked of every track moved 8 to 24 days later, where its swell was not, named 17 of 74 such tracks at some moment: 15 reached partial and 7 strong. By moment, 3% of a misplaced track's are named against 13% of a real one's. The two strong ones in the first count, on 3 October, sat on another swell from the same direction: the test cannot tell two sources on one bearing apart, and a storm due west shares its bearing with the North Pacific's own storms. So a weak match is no more than misplaced tracks manage, partial is what about one misplaced track in five reached, and strong, reached by about one in ten, is the rarest by chance but not rare. WAVEWATCH III's own hindcast at the buoys is checked alongside on this page's reports, never on the card: a model.

### [swell-countdown] Countdowns: when the next reading is due

Each “LIVE” card counts down to when its next reading should be on screen. The countdown is three real events on the clock, not an interval added to the reading:

1. when the source next **publishes** a reading;
2. plus how long that source typically takes to become fetchable;
3. rounded up to the next **collection**, which runs every 10 minutes at :05, :15, :25, :35, :45 and :55;

then the page adds its own refresh, every 5 minutes.

| Source | Publishes | Typical lag | Late after | Reading at 12:00 PM, next due |
|---|---|---|---|---|
| Swell, CDIP 191 | hourly, stamped :00 |  |  | 1:15 PM, red after 1:45 PM |
| Swell, NDBC 46086 (Buoys tab) | half-hourly, stamped :20 and :50 |  |  | (12:20 PM reading) 1:15 PM, red after 2:45 PM |
| Swell, NDBC 46047 (Buoys tab) | half-hourly, stamped :20 and :50 |  |  | (12:20 PM reading) 1:15 PM, red after 2:15 PM |
| Wind, KNZY | hourly at :52 |  |  | (11:52 AM reading) 12:55 PM, red after 1:05 PM |
| Tide, 9410170 | every 6 min |  |  | 12:15 PM, red after 12:25 PM |

It reads “Update in m:ss”, then “Update due” once the typical time has passed. Only past the late time does it turn red and say “Overdue m:ss”, and not until 5 minutes after it plus the page's refresh: a collection takes a few minutes to publish what it fetched, and the update is due, not late, while it does. The publishing lag varies from hour to hour, so one deadline would either cry wolf on every slow hour or promise a time that almost never applies. Hence two figures.

Three hours after a reading, if no newer one has come, the numbers made from it turn grey: each break's height and trains and its drawing's leading arrow on 46232's reading, each buoy's on its own, the Wind card's on KNZY's and the Tide card's height on the gauge's. They return to their usual colours when a newer reading lands. The calculation table, Origin, the provenance and the tide's predicted turn keep their colours. On a rose, a frame is grey, its petals and the line under it, only if it went more than three hours without a newer spectrum: the newest frame once it is past three hours, and a frame left that long before a gap. A frame replaced in time stays in its usual colours however old it grows in the loop.

## [wind] The Wind card

### [wind-three] Three winds

- **KNZY**
  The airfield at Naval Air Station North Island, a few kilometres from the breaks. Its routine report lands at :52 each hour. This is the “LIVE” tab's wind.
- **Local**
  The National Weather Service's forecast grid at the center break, hourly for 7 days. On the Forecast tab it is the wind on the sand, and the offshore/onshore line comes from it. An hour the grid does not cover says so: KNZY's report never stands in on the Forecast tab, because it is an observation, not a forecast.
- **GFS-Wave**
  The wave model's own wind at the buoy, 29 km offshore. Kept on the Forecast card because it is the wind the model grows its wind sea from, never used for the offshore/onshore line.

### [wind-sense] Offshore, cross-shore, onshore or light

Whether a wind is offshore depends on which way the beach faces, and the three breaks face {{geo:normals}}. So the line is per break, shown for the break whose tab is open and hidden on the buoy's tab. On a wide screen, with no tabs, every break's line is shown, each naming its break.

```
offshore component = −cos(wind from − shore normal)     +1 straight off the land, −1 straight off the sea
  > +0.3   offshore          within 72.5° of straight off the land
  < −0.3   onshore           within 72.5° of straight off the sea
  between  cross-shore
  ≤ 3 kt   light offshore, light cross-shore or light onshore
  0 kt     no wind, so no side set        the headline reads Calm
  VRB      no direction, so no side set   a reported wind with no direction; the headline reads Variable

worked hour: 8 kt from 270°
North   normal 194.1°   −cos(75.9°) = −0.24   cross-shore
Center  normal 213.9°   −cos(56.1°) = −0.56   onshore
South   normal 220.9°   −cos(49.1°) = −0.66   onshore
```

[drawing: near] Caption: Each break's chord, with its shore normal drawn out to sea from the midpoint. One wind, three answers.

A wind of 3 kt or less, the Beaufort scale's light air, is “light”: the card still names its side, “light offshore” and so on, but the Shore direction charts count it as light or variable, because a direction that faint barely matters and a forecast gives it one anyway. A wind of 0 kt is “Calm”: the airfield reports a calm as 0° at 0 kt, which is no wind, not a north wind. A calm or a variable wind has no side at any break, so the break's line says why, “no wind” or “no direction”, rather than repeating the headline. The rule lives in one place on the page, so the card and both Shore direction charts change together.

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

On both tabs the card's numbers are the open coast's, carried from NOAA 9410170, and the provenance names that gauge. On “LIVE” the countdown keeps the gauge's own time.

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

### [tide-phase] The tide's phase

Under the card's provenance, a line reads *Phase*. On “LIVE” it is tagged *predicted*. Opened, it gives three paragraphs, each under a heading: the day (*Today*), the next spring or neap (*Around 17 Oct*) and the one after (*Late October*), set apart by a dot as Origin's entries are. The first says where the tide is in its cycles: spring tides, neap tides, building toward springs or easing toward neaps. On “LIVE” the day is the reader's day at Coronado. On Forecast it is the picked hour's day, and a past hour has none. No provenance follows the paragraphs: what they stand on is set out here.

Three cycles shape the tide here. Spring and neap, every 14.8 days, is the moon's and the sun's twice-daily tides falling into and out of step. The Moon's declination, every 13.7 days, makes one tide of the day much bigger than the other when the Moon is far north or south, and evens them out over the equator. Perigee and apogee, every 27.6 days, make a spring bigger or a neap smaller. San Diego's tide is mixed, mainly twice a day: the ratio of its once-daily to its twice-daily constituents is 0.72.

Spring and neap, the 14-hour lag and whether the extremes after next are larger or smaller than this week's are all read off NOAA's harmonic constants for San Diego (9410170), from NOAA's 2017–2021 analysis, fetched from NOAA and never typed, so they carry the station's own timing: springs fall about 3 hours before new or full moon. The Moon's declination is read 14 hours early, because the tide here feels it that late. The Moon's phase, distance and declination are computed, not fetched, from Meeus's lunar theory, and agree with an independent ephemeris within minutes. The highs and lows quoted as evidence, and the day's pair in the first paragraph, are the card's own turns: CO-OPS's high and low water for the gauge, carried to the open coast with the measured departure as the card's are.

```
form factor  (K1 + O1) / (M2 + S2) = (0.337 + 0.214) / (0.542 + 0.225) = 0.72
spring lag   (S2 − M2 Greenwich phase) / (S2 − M2 speed) = −2.9 h
declination  (K1 − O1 Greenwich phase) / (K1 − O1 speed) = +14.4 h
```

> **Model choice · every threshold measured**
> Each threshold was measured over 19 years of the station's own tide (2017–2035, a whole 18.6-year cycle of the Moon's orbit), rebuilt from the same constants. A part of the summary is shown only where it was right at least 85% of the times it would have been said. The Moon counts as near the equator within 4°, and as far north or south past 26°, which happens only in years like these, near a major lunar standstill. The phase line itself always says something, so it uses the window that agrees best with which days have the fortnight's biggest and smallest swings: 72 hours either side of a spring or neap.

> **Model choice · the two tides, not the two highs**
> Here the Moon's declination shows more in the day's two lows than in its two highs, so the summary speaks of the day's two tides and quotes whichever pair differs more.

None of this is a statement about waves. On these beach profiles the whole tide range moves where the waves break by tens of metres and their height by under 2%.

## [sun] The Sun card

### [sun-point-loma] The Point Loma sunset

Every published sunset is the moment the top of the sun meets a level sea horizon. From Coronado's sand the Point Loma peninsula stands between the breaks and that horizon for most of the year: its ridge is 4.5–8 km away and 90–130 m high, about 1° above the horizon. The sun goes behind it some 5–8 minutes before the published time. The card's headline is that sunset, at the open break: *behind Point Loma* and how many minutes before the sea-horizon time. On the Buoys tab there is no beach, so the headline is the sea-horizon time. On a wide screen every break's sunset is shown, each under its name, then the sea horizon's.

Each break has its own skyline, traced from the break over the same USGS CoNED survey the seabed comes from: it is a topographic and bathymetric survey, so Point Loma's land is in it beside the seabed. Along each bearing, the highest angle any land stands above the eye, an eye 3 m above sea level, is the skyline there. The Earth's curvature lowers a distant hill and refraction lifts it back a little. The sunset is the last moment any of the sun's disc stands above whatever is in front of it, land or sea, with each part of the disc refracted at its own height.

```
skyline angle = atan((land − eye) / distance) − distance × (1 − 0.13) / 2R
sunset        = last moment any of the disc is above max(skyline, sea horizon)

16 Oct 2026, center break: sea horizon 6:14 PM, behind Point Loma 6:07 PM
```

The sun is computed, not fetched, from Meeus's solar theory. It agrees with an independent ephemeris to within 0.03°, about seven seconds of sunset. Refraction is Bennett's standard formula. Sunrise is the sea-level time only, the same at every break: the city and mountains east of the breaks are not in the survey. On “LIVE” the card is tagged *computed*, and each time is the next one: once the sunset or the sunrise has passed, it gives tomorrow's and says so. On Forecast both are the picked hour's day.

### [sun-season] In the sea, left of the point

Through the winter the sun sets far enough south to go down in the sea, left of Point Loma's tip as you look out from the beach. How much of the winter that lasts depends on the break, because the bearing to the tip sweeps 18° along 2.8 km of sand, as the swell window's west edge does. The card says when the break's next run of sea sunsets is, or, while the sun is setting in the sea, until when, on the one line:

| Break | The tip, from the break | Sun sets in the sea |
|---|---|---|
| North | 242.0° | Never. Closest around 19–23 Dec, still 1 min early |
| Center | 250.3° | About 9 Nov to 1 Feb |
| South | 260.1° | About 15 Oct to 25 Feb |

Computed for each winter from 2025–26 to 2029–30, the dates move by a day at most. The tip's bearing as the survey sees it agrees with the charted tangent that carries the swell window's west edge to within 0.1°: two independent sources for one edge. On the days either side of a season the sun goes down partly in the sea, its last sliver hidden by the tip's low slope. Those days count as behind Point Loma, by a minute or less.

### [sun-limits] What it cannot see

The survey is bare earth. The trees along the ridge, the lighthouse and the buildings on Point Loma are not in it, so the real skyline can only be higher and the sun can only go behind it earlier. Refraction near the horizon swings with the marine layer, a minute either way on a real evening. Two metres more or less of eye height move the sunset about six seconds.

## [time] Moving through time

### [time-picker] The hour picker

On the Forecast tab, the arrows step through the hours three at a time, and tapping the hour beside them opens the full list. It opens on the first hour not yet passed, never one that has.

### [time-past] Past hours: what the page showed then

The Forecast tab reaches 48 hours back. For each hour that has gone by, the forecast figure is what this page showed for that hour: the newest run that had been published before it, which is not always the run on screen now. A past hour is drawn as it was published, with the drawing and the calculation, from that build's own record. When an older build kept only the headline, the card says “The calculation for this hour was not kept” rather than borrowing another build's detail.

### [time-observed] The blue “Observed at” line

The blue line under it is what CDIP 191 measured at that hour, carried in by the same chain the “LIVE” tab uses: the same windows, seabed and surf zone, with the airfield's wind and the gauge's water level from that hour. It is labelled “Observed at 8:00 AM” with its hour, and the tide's reads “Measured at”. The airfield's wind sits under the Local forecast, the forecast for the same sand, not under GFS-Wave's wind at the buoy. An hour with no buoy spectrum is shown as a gap. It is never filled from the hour beside it, and the newest hour reads “not in yet” until a later spectrum has passed it.

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

CDIP 191's own spectrum at every hour, carried in by the same chain as the reading above them. They open on the last day; zoom and pan them to go back to the start of the buoy's archive (4 August 2026). Every hour is rebuilt with today's windows, seabed and surf zone, so an earlier hour shows what the current chain makes of it, not what this page said at the time: the last week on every collection, the rest once a day. When the older hours no longer match today's chain they are not shown until they have been rebuilt, so two versions of the chain are never drawn on one line.

An hour with no buoy spectrum is a gap: a pale band with no line through it, at every zoom, never filled from the hour beside it. A break has no breaking height for an hour whose water level was not measured, which is every hour before 17 September 2026. Each tab draws its own line, in ink; only Height draws anything beside it.

- **Height**
  The break's breaking height, with the other two breaks' in lighter lines under it, the more southern of the two dashed, so the three can be compared at a glance on one axis. On the buoy's tab, the buoy's own height, and under it in a lighter line NDBC 46047's, Tanner Banks, and in a lighter dashed one NDBC 46086's, San Clemente Basin, each at its own readings: they measure at :20 and :50 past the hour, so each is drawn where it was taken and read out with its own time, never moved onto CDIP 191's hour. A missing reading is a gap in its line. NDBC 46047 is the open ocean before the Channel Islands, NDBC 46086 sits in the south break's window, and neither is carried to a break.
- **Window**
  A break's height through its windows as a share of the buoy's, before the seabed: the [Windows row](#calc-windows). Under it, a dot for each hour marks where the buoy's peak came from, over the break's open windows shaded. The share is the whole spectrum through the windows, so it moves with how widely the swell is spread as well as with where its peak sits. A dot is never “inside” or “outside”: a single bearing tested against a window is the yes-or-no the model refuses.
- **Origins**
  Where the swell arriving at the tab came from, over time, on every break's tab and the buoy's. A black dot every six hours is a hurricane, or one since weakened to a tropical storm, that the card would have named then (see [Origin](#swell-origin)), at the distance of NHC's position that sent the train; its name sits by its first dot in view. A grey bar is an arrival read off the swell itself with no storm named for it, at its dispersion distance, over the hours it was arriving. The readout names each as the Origin fold does: a storm by name, a sea, or an unplaced storm with no bearing. Distance runs on a log scale, 500 to 10,000 miles. Each mark is on a tab only where it was one of that tab's own trains, as on the card; and an arrival is drawn as the storm, not as a bar, where the storm's train at that tab is the arrival's own and Origin read it from within 45° of the storm. Under it, the bearing each came from, as seen from the buoy, never tested against the windows. A moment with no CDIP 191 spectrum, such as the outage of 1 to 17 September, places a named storm on no tab, so Marie's swell, which arrived then, is not on this chart. Rebuilt with today's chain like the rest: the whole archive once a day, the newest hours with every collection.
- **North vs. South**
  North's less South's. Where it crosses zero, which of the two is bigger has flipped.

[drawing: whole] Caption: The windows the Window chart's direction strip shades, here as they sit on the map.

### [charts-live-wt] “LIVE”: the Wind and Tide charts

On the same hours and the same window as the Swell charts. Both are read straight from the collected records rather than rebuilt, so nothing done to the chain can change an earlier hour. They reach back a month, or to where the records begin (18 September 2026 for the wind, 17 September for the tide).

- **Wind**
  The airfield's report taken in the hour up to each hour: its speed, a dot for any gust, and under it the direction it blows from, which a calm or a variable wind does not have. A report is never carried into the next hour. An hour with no report is a gap. The newest report is on the chart as soon as it is on the card, under the coming hour it stands for.
- **Shore direction**
  How often the airfield's wind has been offshore, cross-shore, onshore or light at the break whose tab is open (on a wide screen, the break picked above the swell's charts), one bar for each hour of the day on your clock. Each bar is that hour on every day counted, one reading a day, by the [same rule](#wind-sense) as the card. The readout says “over N days”, because a bar is many days' readings, not one hour's.
- **Tide**
  The gauge's sample at each hour exactly, carried to the open coast as the card's is. Past the present, the next 24 hours of harmonic prediction, dashed, with the measured departure added: the one modelled line on this tab, as the card's next turn is its one modelled number.
- **Departure**
  The gauge's measured level less its prediction at each hour, on the open coast, with the 3-day mean of it that the forecast's tide carries.

Night, from sunset to sunrise at the center break, is shaded behind the tide on both tabs, so a low tide in the dark reads apart from one at dawn. Sunrise and sunset are worked out from the sun's position with NOAA's solar equations, not measured.

### [charts-fc-swell] Forecast: the Swell charts

Drawn from the model, every 3 hours, from 48 hours back to the end of the run. They open on three days with the present a quarter of the way in. A break's line is its breaking height only; an hour whose figure was at 5 m of water, or that no run covered, is a gap.

- **Forecast + Observed**
  The newest GFS-Wave run's line over what each of the last eight runs said for the same hours, as the page showed them, and beside the hours that have passed, CDIP 191 carried in by the same chain, in blue. Where the run lines bunch, the runs agree; where they fan out, the model has been changing its mind. Runs agreeing is not the same as being right, and the spread between them is not a range the swell will fall in.
- **Swell trains**
  Each train the chain carries in, a dot at its period, larger for a bigger train, with the heading it comes from under it. A new swell arrives long-period first, so it shows as dots stepping down in period. Trains are split hour by hour, so a dot is not the same train as the one beside it, and they are kept only for the runs whose hours were kept in full.
- **North vs. South**
  North's forecast breaking height less South's.
- **Ensemble**
  On the buoy's tab only. GEFS-Wave is the same wave model run 31 times from slightly different weather. The dashed line is the mean of its members at the buoy and the shading one standard deviation either side, beside the newest GFS-Wave run and the blue line. It is total height at the buoy with no direction, so it cannot be carried through a break's windows and says nothing about the beach. The chart states how often CDIP 191 has fallen inside the shading, per lead time, over which dates and how many hours. So far that is far less often than a range that size would imply, because the members agree with each other more closely than any of them agrees with the sea, and their mean runs above the buoy. Nothing has been removed from it or added to it to make it look better.

Only the Ensemble view carries a band, and only beside how often the buoy it is drawn for has fallen inside it. No chart shows a difference between the forecast and the blue line.

### [charts-fc-wt] Forecast: the Wind and Tide charts

Hourly, over the same reach.

- **Wind**
  The National Weather Service's forecast wind at Coronado (the card's Local wind), with a dot for any gust and its direction under it. Beside the hours that have passed, the airfield's measured wind in blue. In grey, GFS-Wave's own wind at the buoy, the one the model makes its wind sea from: hourly to five days and every third hour after, joined across the hours it does not give, never across a measured gap.
- **Shore direction**
  The local forecast's wind at the break whose tab is open (on a wide screen, the break picked above the swell's charts), one row a day and one square an hour, so which mornings are offshore reads straight off it. An hour the forecast does not cover is an empty square.
- **Tide**
  The harmonic tide at the open coast with the measured departure added, as the card's is, and the gauge's measured level in blue beside the hours that have passed.
- **Daily range**
  Each day's biggest swing between one predicted high or low and the next, starting that day: long bars are spring tides, short ones neaps. Measured between consecutive turns, never as the day's highest high less its lowest low, which would drop a low that crossed midnight and draw a neap that is not there.

The Shore direction “how often” bars and the Departure view are the “LIVE” tab's only. Counting how often over a week of forecast would throw away which day, and a measured departure has no future hours.

## [sources] Data sources and freshness

### [sources-list] Every source, and what it feeds

| Source | What | Feeds |
|---|---|---|
| CDIP 191, Point Loma South (served by NDBC as 46232) | Hourly directional spectrum, 64 bands; position from NDBC's metadata | “LIVE” swell and its Origin, every chart's buoy line, the blue line |
| NDBC 46047 and NDBC 46086, Tanner Banks and San Clemente Basin | Hourly directional spectra | Origin's direction (NDBC 46047), the hurricane match (both) |
| KNZY, NAS North Island | Hourly airfield report (METAR) | “LIVE” wind, local chop, Shore direction |
| NOAA tide gauge 9410170, San Diego | 6-minute measured level, hourly prediction, predicted highs and lows, harmonic constants | Tide card and its phase, breaking depth, departure |
| GFS-Wave (WAVEWATCH III), NOAA | The model's own directional spectrum and 10 m wind at the buoy, four runs a day | Forecast swell |
| GEFS-Wave, NOAA | 31-member ensemble at the buoy, height only | Ensemble chart |
| National Weather Service grid | Hourly forecast wind at the center break, 7 days | Forecast wind, offshore line |
| USGS CoNED, GMRT | Surveyed seabed, beach profiles and Point Loma's land (2016) | Refraction, friction, shoaling, breaking, the Sun card's skyline |
| NOAA electronic navigational charts | Coastline of Point Loma's tip, the islands, Baja and the break chords | The aperture |
| NOAA solar equations | Sunrise and sunset, computed | Night shading |
| Meeus's solar theory | The sun's position, computed | The Sun card |
| Meeus's lunar theory | The Moon's phase, distance and declination, computed | The tide's phase |

When GFS-Wave's directional spectrum is not available, the forecast is rebuilt from the model's separate swell trains instead, with an assumed directional spread, and the “standing on” block above says which was used and what spread was assumed.

### [sources-cadence] Cadence and lag

The observations are collected every 10 minutes and the page refetches them every 5. Every request carries a unique address, so no cache along the way can hand back an older copy. The model runs four times a day, and each run's numbers for the buoy appear about five and a half hours after its nominal time, so the newest forecast always starts a few hours in the past. [How a countdown is worked out](#swell-countdown).

### [sources-dark] When a source goes dark

CDIP 191 went silent for 16 days in September 2026 and nobody knows why. When a source stops, its card's countdown runs out and turns red, its chart lines break, and nothing is filled in. No other buoy can stand in: CDIP 191 is the only one in the array that sits inside Coronado's windows. If there is no current observation at all, the “LIVE” tab says so and points at the Forecast tab.

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
- **“Overdue m:ss” in red**
  Past the latest the source normally takes. The reading on screen is still the newest there is.
- **Grey numbers on a card**
  The reading they were made from is more than three hours old. They return to their usual colours when a newer one lands.
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
- **Spring and neap tides**
  The days of the biggest and the smallest twice-daily swings, every 14.8 days.
- **Declination**
  How far north or south of the equator the Moon is.
- **Perigee, apogee**
  The Moon nearest the Earth, and farthest from it.
- **GFS-Wave, GEFS-Wave**
  NOAA's global wave model, and the same model run as a 31-member ensemble.
- **ENC**
  NOAA's electronic navigational charts, the source of every coordinate in the aperture.
- **CoNED**
  The USGS Coastal National Elevation Database, a seamless survey of land and seabed.
- **CDIP 191, KNZY, 9410170**
  The buoy, the airfield and the tide gauge. CDIP 191 is the buoy NDBC lists as 46232; NDBC 46047 and NDBC 46086 are the Buoys tab's other two.

This page is built from the same files as the forecast page: the drawings from the geometry the forecast reads, and the “standing on” blocks from each tab's own file as the page loads. The worked hour is rebuilt from the archive by a test whenever the chain changes. Geometry only says which bearings can reach each break, not how big anything is; nothing on this page has been measured at the breaks.
