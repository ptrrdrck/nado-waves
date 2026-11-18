# Where the surf zone starts, before and after BRIEFING §58

Written by `python -m forecast.breakshift --write`. Reports, never edits.
1484 archived 46232 hours with a measured tide within 30 min, 2026-09-17 to 2026-11-18; the shipped chain (Madsen's friction at the measured tide) into the surf zone at that tide, no local chop. Before: the profile from the table's start point (5 m) in. After: the profile from 7 m (north), 10 m (center), 10 m (south). A model's change, not an accuracy figure: nothing observed these heights.

## coronado_north

| 46232 Hs | hours | breaking Hs, median: before → after | after ÷ before: median [10th] min | break depth, median: before → after [90th] max | break seaward of 5 m | flagged: before → after |
|---|---|---|---|---|---|---|
| 0.0–1.0 m | 233 | 0.82 → 0.82 m | 1.000 [1.000] 1.000 | 1.67 → 1.67 m [2.03] 2.66 m | 0 | 0 → 0 |
| 1.0–1.5 m | 820 | 0.95 → 0.95 m | 1.000 [1.000] 1.000 | 1.99 → 1.99 m [2.62] 3.47 m | 0 | 0 → 0 |
| 1.5–2.0 m | 305 | 1.00 → 1.00 m | 1.000 [1.000] 0.998 | 2.11 → 2.11 m [2.99] 3.45 m | 0 | 0 → 0 |
| 2.0–2.5 m | 58 | 1.14 → 1.14 m | 1.000 [1.000] 1.000 | 2.44 → 2.44 m [2.87] 3.16 m | 0 | 0 → 0 |
| ≥ 2.5 m | 68 | 1.26 → 1.26 m | 1.000 [1.000] 1.000 | 2.75 → 2.75 m [3.06] 3.38 m | 0 | 0 → 0 |

Hours not flagged before, by the share of waves already breaking at the table's start point with the old start (Qb): the breaking height after ÷ before − 1.

| Qb at 5 m, old start | hours | worst | 99th percentile of the size |
|---|---|---|---|
| none | 728 | +0.000% | 0.000% |
| 0 – 0.001 | 749 | -0.030% | 0.019% |
| 0.001 – 0.01 | 7 | -0.161% | 0.161% |
| 0.01 – 1 | 0 | – | – |

Flagged after: 0 of 1484 hours.

## coronado_center

| 46232 Hs | hours | breaking Hs, median: before → after | after ÷ before: median [10th] min | break depth, median: before → after [90th] max | break seaward of 5 m | flagged: before → after |
|---|---|---|---|---|---|---|
| 0.0–1.0 m | 233 | 0.72 → 0.72 m | 1.000 [1.000] 1.000 | 1.54 → 1.54 m [1.84] 2.23 m | 0 | 0 → 0 |
| 1.0–1.5 m | 820 | 0.89 → 0.89 m | 1.000 [1.000] 1.000 | 1.88 → 1.88 m [2.31] 3.08 m | 0 | 0 → 0 |
| 1.5–2.0 m | 305 | 1.15 → 1.15 m | 1.000 [1.000] 0.988 | 2.41 → 2.41 m [2.92] 4.09 m | 0 | 1 → 0 |
| 2.0–2.5 m | 58 | 1.48 → 1.48 m | 1.000 [0.995] 0.985 | 2.92 → 2.92 m [3.73] 4.43 m | 0 | 1 → 0 |
| ≥ 2.5 m | 68 | 1.85 → 1.84 m | 0.997 [0.979] 0.939 | 3.60 → 3.60 m [5.03] 5.96 m | 6 | 11 → 0 |

Hours not flagged before, by the share of waves already breaking at the table's start point with the old start (Qb): the breaking height after ÷ before − 1.

| Qb at 5 m, old start | hours | worst | 99th percentile of the size |
|---|---|---|---|
| none | 795 | +0.000% | 0.000% |
| 0 – 0.001 | 623 | -0.076% | 0.055% |
| 0.001 – 0.01 | 44 | -0.889% | 0.889% |
| 0.01 – 1 | 9 | -1.249% | 1.249% |

Flagged after: 0 of 1484 hours.

## coronado_south

| 46232 Hs | hours | breaking Hs, median: before → after | after ÷ before: median [10th] min | break depth, median: before → after [90th] max | break seaward of 5 m | flagged: before → after |
|---|---|---|---|---|---|---|
| 0.0–1.0 m | 233 | 0.64 → 0.64 m | 1.000 [1.000] 1.000 | 1.49 → 1.49 m [1.76] 2.02 m | 0 | 0 → 0 |
| 1.0–1.5 m | 820 | 0.84 → 0.84 m | 1.000 [1.000] 1.000 | 1.93 → 1.93 m [2.47] 3.54 m | 0 | 0 → 0 |
| 1.5–2.0 m | 305 | 1.17 → 1.17 m | 1.000 [1.000] 0.991 | 2.58 → 2.58 m [3.60] 4.31 m | 0 | 0 → 0 |
| 2.0–2.5 m | 58 | 1.64 → 1.64 m | 0.999 [0.991] 0.966 | 4.02 → 4.02 m [4.69] 5.13 m | 0 | 4 → 0 |
| ≥ 2.5 m | 68 | 2.09 → 2.06 m | 0.990 [0.951] 0.900 | 5.04 → 5.05 m [5.53] 6.73 m | 8 | 32 → 0 |

Hours not flagged before, by the share of waves already breaking at the table's start point with the old start (Qb): the breaking height after ÷ before − 1.

| Qb at 5 m, old start | hours | worst | 99th percentile of the size |
|---|---|---|---|
| none | 840 | +0.000% | 0.000% |
| 0 – 0.001 | 542 | -0.095% | 0.055% |
| 0.001 – 0.01 | 52 | -0.812% | 0.696% |
| 0.01 – 1 | 14 | -1.159% | 1.159% |

Flagged after: 0 of 1484 hours.
