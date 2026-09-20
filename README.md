# Coronado Forecast

A surf forecaster for three beaches on the Coronado peninsula — **Coronado
Central Beach**, **Breakers Beach (NASNI)** and **Gator Beach (NAB Coronado)**.

One offshore buoy, one blocking geometry, three different answers.

## Why these three beaches need their own forecaster

Point Loma sits directly across their swell window. Computed from coordinates:

| spot | west window | cuts off at | south window | island channel | coordinates |
|---|---|---|---|---|---|
| Coronado — north break | 41.6° | 242.2° | 164.7–187.4° | 192.6–198.6° | digitised |
| Coronado — center break | 47.7° | 250.3° | 166.4–189.1° | 194.4–200.5° | digitised |
| Coronado — south break | 54.7° | 259.9° | 168.5–191.1° | 196.8–203.0° | digitised |

Every edge in that table is formed by land. There used to be one window per
break, because `geometry.py` also reported a south-east arc the surface
deliberately withheld: it spans Imperial Beach, the Tijuana river mouth and
Rosarito at 11–41 km, and the Baja coast was not a blocker in `spots.json`, so
the raw arc claimed open water across a coastline you can see from the sand
(BRIEFING §12). On 2026-09-20 that coast was fetched from NOAA's ENC and
added, which closed the arc's lower edge on land and made it publishable —
and which matters, because 16.7% of the three-year 46232 archive arrives from
100–190° and nearly all of it is long-period south swell (BRIEFING §24).

The same fetch charted the Coronado Islands, which had been an estimate. They
are **two** islands with 6.1° of open channel between them, not one 13.5°
screen: modelling the group as a single blocker claimed that channel was land
and pushed its Fresnel number from ~1.6 to ~7, which silenced the diffraction
flag that BRIEFING §10 exists to raise.

The forecast and the app cover **these three breaks only**. Breakers (NASNI)
and Gator (NAB) are still in `spots.json` for the geometry, and out of
everything downstream: they are the two spots whose coordinates remain
estimated.

**Coronado is three rows because it is not one beach.** The west edge of the
window is the bearing to the Point Loma tip, and that bearing sweeps as you walk
the sand — 17° of it across 2.8 km. The spread between Coronado's own ends is a
third of the entire Breakers-to-Gator range.

At Breakers the shadow edge sits about **one degree** from the shore normal, so
a few degrees of incident-direction error moves the beach across the boundary
between "in the window" and "behind the peninsula". That is why a
general-purpose forecast is fragile here and reliable a few miles north.

What that sensitivity does **not** mean is that the shore normal drives the
answer. Measured: rotating a shoreline chord ±10° moves the swell-side window by
exactly zero, because both its edges are blocker-derived. Position moves it;
facing does not. `tests/test_geometry.py` pins the invariance and its control.

And in three years of archive, **3,257 hours of W–WNW and 3,771 hours of NW
swell fall in the blocked sector**, against 1,247 hours of S–SW in the open one.
The dominant San Diego swell regime is, for Coronado, geometrically blocked.

## The Coronado Islands are not a switch

Local surfers say the islands barely shadow anything. Measured, they are right,
and there is a mechanism (BRIEFING §10). The islands subtend **10.9°** where
Point Loma subtends **54.0°**, so against a swell with any realistic
directional spread they remove about **11%** of the energy and Point Loma
removes about **half** — and their Fresnel number runs 1.9–5.4 across surf
periods, low enough that diffraction fills part of even that 11%.

So the forecast **integrates the directional spectrum through the aperture**
rather than testing one dominant direction against a hard-edged sector. That
one change is what turns the islands from an on/off switch into a small energy
reduction. It also means digitising them is low value: they are 31 km out, and
a full kilometre of coordinate error moves an edge by under 2°, against
2.2–2.8° for 250 m at the Point Loma tip.

## Seeing it

    python -m forecast.live          # writes data/live/forecast.json
    python -m http.server            # then open /app/forecast.html

    python -m forecast.publish       # build the public bundle -> build/site/

**Live: https://ptrrdrck.github.io/nado-waves-forecast/** — this repository is
private, so the page is published to a public delivery repository, the same way
`nado-waves-log` serves the observer form. This repository stays the system of
record; nothing is edited on the far side.

The page states what it is standing on in four levels — geometry, model,
calibration, observation — and two of those currently read **none**.
`tests/test_app_surface.py` enforces that the page cannot use the vocabulary an
accuracy claim would need.

## The honest caveat, up front

**Nothing measures waves at these three beaches.** Until a verification series
exists, this produces a *physically derived* forecast, not an accurate one — and
no accuracy figure appears anywhere without naming what it was measured against.
See `CLAUDE.md` and `BRIEFING.md` §7.

The series it is waiting on is `data/beach_log/`, and it is **empty**. The log
that fills it is built (`docs/observation_log.md` explains why it is shaped the
way it is) and it verifies *differences between the breaks*, not heights — that
being the claim this project is actually making, and the one a human observer
can report reliably.

## Running it

```
python -m forecast.live                  # the forecast -> data/live/forecast.json
python -m forecast.transform             # energy through each aperture
python -m forecast.geometry              # which bearings reach each beach
python -m collector.spectra              # archive NDBC directional spectra
python -m collector.wind                 # KNZY    /  python -m collector.tide
python -m collector.probe_spectra        # are NDBC directional spectra reachable?
python -m collector.beachlog sweep -o me # log the three breaks in one trip
python -m forecast.beachverify           # does the log agree with the geometry?
python -m forecast.verify                # how wrong GFS-Wave is at the buoy
python -m forecast.residual --ceiling    # what an upstream observation could win
python -m forecast.forensics             # where a past swell was born
python -m collector.run                  # fetch and archive (needs NDBC reachable)
python -m collector.gfswave_backfill     # archive GFS-Wave bulletins
PYTHONPATH=. python -m pytest -q
```

## Layout

    app/forecast.html     the app surface, Coronado's three breaks  [built]
    collector/            NDBC archiving, revisions, station status, backfill,
                          GFS-Wave bulletin parsing, spectra, wind, tide
    forecast/live.py      the live forecast                          [built]
    forecast/transform.py spectrum -> energy through the aperture    [built]
    forecast/geometry.py  which bearings reach each beach            [built]
    forecast/spots.json   breaks and blockers     [Coronado digitised; others not]
    forecast/verify.py    bias, RMSE, scatter, calibration, band coverage
    forecast/residual.py  is the remaining error recoverable?
    forecast/beachverify.py  log vs geometry, with the control that could kill it
    collector/beachlog.py    the human observation log
    data/beach_log/          the verification series                    [EMPTY]
    forecast/forensics.py read a swell's origin off the buoy record
    data/historical/      3 years hourly, 15 stations — irreplaceable
    data/wave_forecasts/  1,095 GFS-Wave cycles/station, with swell partitions

Data files are tracked on purpose. NDBC's real-time feed retains 45 days;
anything not committed here is gone.

## Read first

`BRIEFING.md` — three years of measured findings, four falsified hypotheses and
several expensive mistakes, inherited from the project this grew out of. Most
questions worth asking have already been answered there, some the hard way.
