# Coronado Forecast

A surf forecaster for three beaches on the Coronado peninsula — **Coronado
Central Beach**, **Breakers Beach (NASNI)** and **Gator Beach (NAB Coronado)**.

One offshore buoy, one blocking geometry, three different answers.

## Why these three beaches need their own forecaster

Point Loma sits directly across their swell window. Computed from coordinates:

| beach | faces | open swell window | shadow edge from shore normal |
|---|---|---|---|
| Breakers (NASNI) | 223° | 196–222° — just 26° | 1° |
| Coronado Central | 251° | 201–249° — 48° | 1° |
| Gator (NAB) | 240° | 206–270° — 65° | 30° |

Gator holds west swell to 270°; Coronado cuts off at 249°; Breakers at 222°. On
a W/WNW swell Gator works and Breakers is dead.

At Coronado and Breakers the shadow edge sits about **one degree** from the
shore normal, so a few degrees of incident-direction error moves the beach
across the boundary between "in the window" and "behind the peninsula". That is
why a general-purpose forecast is fragile here and reliable a few miles north.

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
    forecast/spots.json   the three beaches                [COORDINATES UNVERIFIED]
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
