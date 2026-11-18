# Bottom friction before and after BRIEFING §57

Written by `python -m forecast.frictionshift --write`. Reports, never edits.
1476 archived 46232 hours with a measured tide within 30 min, 2026-09-17 to 2026-11-18. Before: the table's JONSWAP friction (`carry(friction="jonswap")`); after: Madsen's at the measured tide (what ships). Both into the surf zone at that tide; no local chop in either. A model's change, not an accuracy figure: nothing observed these heights.

## Breaking height, after ÷ before

Median [10th, 90th] and hours, by 46232's Hs (rows) and its swell's direction (energy-weighted mean of ≥ 8 s, `mopcheck.mean_from`).

### coronado_north

| 46232 Hs | S 150–205° | SSW-SW 205–235° | WSW-W 235–270° | W-WNW 270–295° | all |
|---|---|---|---|---|---|
| 0.0–1.0 m | 0.94 [0.91, 0.96] n=44 | 0.93 [0.90, 0.95] n=174 | 0.93 [0.92, 0.95] n=15 | – | 0.93 [0.90, 0.95] n=233 |
| 1.0–1.5 m | 0.93 [0.89, 0.95] n=107 | 0.91 [0.88, 0.94] n=473 | 0.92 [0.88, 0.94] n=206 | 0.92 [0.88, 0.94] n=34 | 0.91 [0.88, 0.95] n=820 |
| 1.5–2.0 m | 0.90 [0.87, 0.93] n=25 | 0.89 [0.87, 0.93] n=95 | 0.91 [0.88, 0.94] n=84 | 0.90 [0.87, 0.94] n=95 | 0.90 [0.87, 0.93] n=299 |
| 2.0–2.5 m | 0.91 [0.91, 0.91] n=1 | 0.88 [0.87, 0.89] n=8 | 0.89 [0.84, 0.91] n=22 | 0.88 [0.84, 0.92] n=25 | 0.89 [0.86, 0.92] n=56 |
| ≥ 2.5 m | 0.93 [0.90, 0.93] n=5 | 0.87 [0.87, 0.90] n=2 | 0.83 [0.83, 0.90] n=3 | 0.88 [0.85, 0.91] n=58 | 0.88 [0.85, 0.91] n=68 |

Median breaking Hs over every hour: before 1.05 m, after 0.95 m.

### coronado_center

| 46232 Hs | S 150–205° | SSW-SW 205–235° | WSW-W 235–270° | W-WNW 270–295° | all |
|---|---|---|---|---|---|
| 0.0–1.0 m | 0.95 [0.93, 0.97] n=44 | 0.95 [0.92, 0.96] n=174 | 0.95 [0.92, 0.96] n=15 | – | 0.95 [0.92, 0.97] n=233 |
| 1.0–1.5 m | 0.94 [0.92, 0.97] n=107 | 0.93 [0.90, 0.96] n=473 | 0.92 [0.88, 0.95] n=206 | 0.89 [0.88, 0.92] n=34 | 0.93 [0.89, 0.96] n=820 |
| 1.5–2.0 m | 0.93 [0.91, 0.96] n=25 | 0.92 [0.90, 0.94] n=95 | 0.90 [0.87, 0.93] n=84 | 0.88 [0.86, 0.91] n=95 | 0.90 [0.87, 0.93] n=299 |
| 2.0–2.5 m | 0.94 [0.94, 0.94] n=1 | 0.92 [0.86, 0.92] n=8 | 0.87 [0.84, 0.90] n=22 | 0.86 [0.80, 0.90] n=25 | 0.87 [0.81, 0.91] n=56 |
| ≥ 2.5 m | 0.93 [0.86, 0.93] n=5 | 0.90 [0.90, 0.92] n=2 | 0.76 [0.73, 0.87] n=3 | 0.84 [0.78, 0.88] n=58 | 0.85 [0.78, 0.89] n=68 |

Median breaking Hs over every hour: before 1.01 m, after 0.93 m.

### coronado_south

| 46232 Hs | S 150–205° | SSW-SW 205–235° | WSW-W 235–270° | W-WNW 270–295° | all |
|---|---|---|---|---|---|
| 0.0–1.0 m | 0.96 [0.94, 0.98] n=44 | 0.96 [0.93, 0.97] n=174 | 0.95 [0.93, 0.97] n=15 | – | 0.96 [0.94, 0.97] n=233 |
| 1.0–1.5 m | 0.95 [0.93, 0.97] n=107 | 0.94 [0.91, 0.97] n=473 | 0.93 [0.90, 0.95] n=206 | 0.91 [0.88, 0.93] n=34 | 0.94 [0.90, 0.97] n=820 |
| 1.5–2.0 m | 0.93 [0.92, 0.96] n=25 | 0.93 [0.89, 0.96] n=95 | 0.91 [0.87, 0.94] n=84 | 0.90 [0.87, 0.92] n=95 | 0.91 [0.88, 0.95] n=299 |
| 2.0–2.5 m | 0.93 [0.93, 0.93] n=1 | 0.88 [0.87, 0.89] n=8 | 0.88 [0.85, 0.90] n=22 | 0.85 [0.82, 0.91] n=25 | 0.87 [0.83, 0.91] n=56 |
| ≥ 2.5 m | 0.91 [0.88, 0.93] n=5 | 0.86 [0.86, 0.87] n=2 | 0.83 [0.80, 0.86] n=3 | 0.84 [0.81, 0.87] n=58 | 0.84 [0.81, 0.89] n=68 |

Median breaking Hs over every hour: before 0.96 m, after 0.89 m.

## Hours still flagged `outside_start` after Madsen

The sea already breaking where the surf-zone profile starts (`surfzone.START_GAIN`): the headline there is a ceiling, not a break point. After (before), of the hours in the band.

| 46232 Hs | coronado_north | coronado_center | coronado_south |
|---|---|---|---|
| 0.0–1.0 m | 0 (0) of 233 | 0 (0) of 233 | 0 (0) of 233 |
| 1.0–1.5 m | 0 (0) of 820 | 0 (0) of 820 | 0 (0) of 820 |
| 1.5–2.0 m | 0 (0) of 299 | 1 (3) of 299 | 0 (3) of 299 |
| 2.0–2.5 m | 0 (0) of 56 | 1 (13) of 56 | 4 (20) of 56 |
| ≥ 2.5 m | 0 (0) of 68 | 11 (41) of 68 | 32 (56) of 68 |
