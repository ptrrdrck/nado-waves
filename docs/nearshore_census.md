# Observed nearshore spectra: can the chain and MOP be scored?

Generated 2026-11-20T20:37:05+00:00 by `python -m collector.nearshore_census` on Actions (`mop-check.yml`, `points=census`). Report only: nothing the forecast uses reads it. The test it looks for: trace the chain to an observed nearshore buoy from 46232's spectra, take MOP's nearest point, and score both against what the buoy measured. That judges the deep-water-to-10 m leg the two models disagree on (BRIEFING §56a–§56d); it is not a verification series for any break.

46232 (the chain's input), years with all five NDBC spectral files: **NDBC's historical listings hold no spectral file for it**; its old spectra are in CDIP's archive (CDIP 191, below).

MOP products CDIP lists for San Diego county (datasets): `ecmwf_fc` 1210, `forecast` 1210, `hindcast` 1210, `nowcast` 1210

Every NDBC station inside the chain's seabed grids (nearshore, outer, regional), nearest Imperial Beach first. Directional years: all of density, mean and principal direction, r1 and r2 at NDBC. Overlap: those years shared with 46232's.

| NDBC | CDIP | name | stated depth | grids | km to IB / Center | directional years | overlap with 46232 | CDIP archive | reporting now | MOP point (m away, depth) | MOP nowcast | MOP hindcast |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 46235 | 155 | Imperial Beach Nearshore, CA (155) | 21 m | regional, outer | 2.9 / 12.6 | no NDBC files | — | 2006-12-19 – 2026-05-03 | no | D0043 (1871, 10.1 m) | 2025-03-31 – 2026-11-20 | 1999-12-31 – 2025-03-31 |
| 46232 (input) | 191 | Point Loma South, CA  (191) | 1049.8 m | outer | 27.6 / 29.0 | no NDBC files | — | 2007-10-03 – 2026-09-01 | yes | — | — | — |
| 46231 | 093 | Mission Bay, CA (093) | 201.17 m | regional, outer | 28.6 / 18.7 | no NDBC files | — | — | — | — | — | — |
| 46227 | 091 | Point Loma, CA (091) | 188 m | regional, outer | 29.1 / 24.9 | no NDBC files | — | — | — | — | — | — |
| 46254 | 201 | SCRIPPS Nearshore, CA (201) | 46 m | outer | 34.4 / 22.1 | no NDBC files | — | 2013-03-27 – 2026-10-21 | yes | D0512 (635, 10.0 m) | 2025-03-31 – 2026-11-20 | 1999-12-31 – 2025-03-31 |
| 46226 | 095 | Point La Jolla, CA (095) | 180 m | regional, outer | 36.0 / 24.2 | no NDBC files | — | — | — | — | — | — |
| 46258 | 220 | Mission Bay West, CA (220) | 562.7 m | regional, outer | 38.9 / 30.6 | no NDBC files | — | — | — | — | — | — |

CDIP requests spent: 54 of 90.

## What failed

- nothing
