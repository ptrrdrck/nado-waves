# Coronado Forecast

A surf forecaster for three beaches on the Coronado peninsula — **Coronado
Central Beach**, **Breakers Beach (NASNI)** and **Gator Beach (NAB Coronado)**.

One offshore buoy, one blocking geometry, three different answers.

## Why these three beaches need their own forecaster

Point Loma sits directly across their swell window. Computed from coordinates:

| spot | open swell window | cuts off at | coordinates |
|---|---|---|---|
| Breakers (NASNI) | 27° | 223° | estimated |
| Coronado — north break | 42.8° | 242.2° | digitised |
| Coronado — centre break | 49.1° | 250.3° | digitised |
| Coronado — south break | 56.3° | 259.9° | digitised |
| Gator (NAB) | 64° | 270° | estimated |

Gator holds west swell to 270°; Breakers dies at 223°. On a W/WNW swell Gator
works and Breakers is dead.

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

## The honest caveat, up front

**Nothing measures waves at these three beaches.** Until a verification series
exists, this produces a *physically derived* forecast, not an accurate one — and
no accuracy figure appears anywhere without naming what it was measured against.
See `CLAUDE.md` and `BRIEFING.md` §7.

## Running it

```
python -m forecast.geometry              # which bearings reach each beach
python -m collector.probe_spectra        # are NDBC directional spectra reachable?
python -m forecast.verify                # how wrong GFS-Wave is at the buoy
python -m forecast.residual --ceiling    # what an upstream observation could win
python -m forecast.forensics             # where a past swell was born
python -m collector.run                  # fetch and archive (needs NDBC reachable)
python -m collector.gfswave_backfill     # archive GFS-Wave bulletins
PYTHONPATH=. python -m pytest -q
```

## Layout

    collector/            NDBC archiving, revisions, station status, backfill,
                          GFS-Wave bulletin parsing
    forecast/geometry.py  which bearings reach each beach            [built]
    forecast/spots.json   breaks and blockers     [Coronado digitised; others not]
    forecast/verify.py    bias, RMSE, scatter, calibration, band coverage
    forecast/residual.py  is the remaining error recoverable?
    forecast/forensics.py read a swell's origin off the buoy record
    data/historical/      3 years hourly, 15 stations — irreplaceable
    data/wave_forecasts/  1,095 GFS-Wave cycles/station, with swell partitions

Data files are tracked on purpose. NDBC's real-time feed retains 45 days;
anything not committed here is gone.

## Read first

`BRIEFING.md` — three years of measured findings, four falsified hypotheses and
several expensive mistakes, inherited from the project this grew out of. Most
questions worth asking have already been answered there, some the hard way.
