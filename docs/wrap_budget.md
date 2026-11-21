# The wrap round Point Loma on big westerly hours: budget, rays, robustness

Written by `python -m forecast.wrapbudget --write` (handoff item 27b). Reports, never edits. The chain as it ships (MEM, Madsen at the measured tide, surf zone from `SURF_START_M`), no local chop (27a: it adds nothing on these hours). 108 hours with 46232 ≥ 2 m and swell (≥ 8 s) from 270–295°, plus 17 Nov (109 in all, with a measured tide). **Nothing here is observed**: a model's anatomy, never a score.

## Controls

- `raytrace.table(dir_step=0.5)` against the committed tables: North 0 of 23040 rows differ; Center 0 of 23040 rows differ; South 0 of 23040 rows differ.
- The per-ray sum against `carry`'s 5 m height: worst |Δ| 0.0000%.
- Straight-line windows relative to each break's normal (°): North -30.2…-6.7, -1.5…+4.3, +6.2…+47.9; Center -48.3…-24.9, -19.5…-13.6, -11.7…+36.3; South -53.4…-29.9, -24.1…-18.1, -16.1…+39.2. West of the last arc is `wrap`.

## 1. Budget

Share of the 5 m energy (after Madsen) by where each ray's offshore heading sits in the straight-line view from the break; median [10th, 90th]. **headline without the wrap** breaks the 5 m sea with the wrap's energy taken out, period and heading held: an indication of its weight, not a decomposition (breaking is not linear).

| break | hours | direct | wrap | islands | baja | fill | headline, m | without the wrap ÷ headline |
|---|---|---|---|---|---|---|---|---|
| North | 108 | 0.54 [0.42, 0.64] | 0.30 [0.22, 0.38] | 0.02 [0.01, 0.03] | 0.00 [0.00, 0.01] | 0.12 [0.08, 0.21] | 1.10 [0.83, 1.35] | 0.87 [0.83, 0.90] |
| Center | 108 | 0.19 [0.10, 0.29] | 0.71 [0.62, 0.80] | 0.00 [0.00, 0.00] | 0.00 [0.00, 0.00] | 0.07 [0.05, 0.15] | 1.70 [1.17, 1.98] | 0.61 [0.52, 0.68] |
| South | 108 | 0.13 [0.08, 0.21] | 0.70 [0.59, 0.81] | 0.00 [0.00, 0.00] | 0.00 [0.00, 0.00] | 0.14 [0.08, 0.25] | 1.89 [1.40, 2.23] | 0.63 [0.53, 0.70] |

## 2. Concentration

Share of the 5 m energy in the top 1, 3 and 10 rays, and how many rays carry half of it, at the shipped 0.5° comb and the finest; median [10th, 90th].

| break | top 1 | top 3 | top 10 | rays for half (of all carrying) | top 3 at 0.125° | wrap share at 0.125° |
|---|---|---|---|---|---|---|
| North | 0.03 [0.02, 0.09] | 0.07 [0.04, 0.15] | 0.15 [0.09, 0.25] | 135 (5307) | 0.07 [0.04, 0.18] | 0.40 [0.32, 0.49] |
| Center | 0.06 [0.03, 0.12] | 0.13 [0.08, 0.24] | 0.27 [0.17, 0.40] | 50 (5455) | 0.06 [0.03, 0.14] | 0.74 [0.65, 0.83] |
| South | 0.05 [0.03, 0.13] | 0.12 [0.06, 0.25] | 0.23 [0.14, 0.41] | 59 (5280) | 0.05 [0.03, 0.10] | 0.79 [0.71, 0.86] |

## 3. Robustness: does the wrap survive a smoothed input and a finer comb?

Each over the shipped chain, median [10th, 90th]. Smoothed: the MEM density convolved in direction (Gaussian σ), through the shipped chain. Finer: the 5 m height with the rows' JONSWAP friction, fine ÷ 0.5°, and the headline when the shipped Madsen 5 m height is scaled by it.

| break | 5 m: σ 5° | σ 10° | 0.25° | 0.125° | 0.125° before friction | headline: σ 5° | σ 10° | 0.25° | 0.125° |
|---|---|---|---|---|---|---|---|---|---|
| North | 1.02 [0.96, 1.07] | 1.07 [1.00, 1.16] | 1.06 [0.97, 1.14] | 1.08 [0.98, 1.22] | 1.07 [0.97, 1.18] | 1.02 [0.97, 1.05] | 1.06 [1.00, 1.13] | 1.05 [0.98, 1.12] | 1.06 [0.98, 1.18] |
| Center | 1.02 [0.97, 1.09] | 1.04 [0.97, 1.12] | 0.96 [0.86, 1.03] | 1.00 [0.90, 1.07] | 1.00 [0.90, 1.07] | 1.02 [0.98, 1.07] | 1.03 [0.98, 1.10] | 0.97 [0.90, 1.03] | 1.00 [0.92, 1.05] |
| South | 1.01 [0.95, 1.08] | 1.01 [0.96, 1.10] | 0.99 [0.93, 1.12] | 0.97 [0.90, 1.06] | 0.97 [0.90, 1.05] | 1.01 [0.96, 1.07] | 1.01 [0.97, 1.09] | 0.99 [0.94, 1.10] | 0.98 [0.92, 1.05] |

### Hour-to-hour jumps

Consecutive hours of the selection one hour apart. A **jump**: the headline moves by more than 15% (|Δ ln|) while 46232's Hs moves under 5%. |Δ ln headline|: median [90th]; jumps counted.

| break | pairs | shipped | σ 5° | σ 10° | 0.25° | 0.125° | jumps: shipped / σ 5° / σ 10° / 0.25° / 0.125° | top-3 share, jump hours vs the rest |
|---|---|---|---|---|---|---|---|---|
| North | 94 | 0.113 [0.235] | 0.106 [0.253] | 0.074 [0.211] | 0.095 [0.251] | 0.082 [0.218] | 21 / 15 / 10 / 14 / 10 | 0.09 [0.04, 0.17] vs 0.07 [0.04, 0.14] |
| Center | 94 | 0.061 [0.171] | 0.052 [0.137] | 0.049 [0.133] | 0.061 [0.141] | 0.056 [0.153] | 7 / 1 / 1 / 2 / 3 | 0.14 [0.10, 0.18] vs 0.13 [0.08, 0.25] |
| South | 94 | 0.074 [0.170] | 0.049 [0.123] | 0.046 [0.129] | 0.060 [0.148] | 0.057 [0.148] | 6 / 0 / 0 / 1 / 2 | 0.13 [0.10, 0.25] vs 0.12 [0.06, 0.27] |

### 17 Nov, hour by hour

Headline (m): shipped / σ 10° / 0.125°; the wrap's share of the 5 m energy; top-3 rays' share.

| hour | 46232 | North | Center | South |
|---|---|---|---|---|
| 00Z | 2.54 m, 272° | 1.51 / 1.56 / 1.53; wrap 0.20; top 3 0.08 | 1.93 / 2.08 / 1.93; wrap 0.59; top 3 0.12 | 1.87 / 2.06 / 2.04; wrap 0.70; top 3 0.17 |
| 01Z | 2.61 m, 273° | 1.10 / 1.20 / 1.29; wrap 0.28; top 3 0.09 | 1.57 / 1.77 / 1.70; wrap 0.80; top 3 0.18 | 1.82 / 1.95 / 1.89; wrap 0.80; top 3 0.23 |
| 02Z | 2.66 m, 272° | 1.25 / 1.25 / 1.23; wrap 0.62; top 3 0.42 | 2.09 / 1.93 / 1.50; wrap 0.69; top 3 0.27 | 2.10 / 2.12 / 2.26; wrap 0.86; top 3 0.27 |
| 03Z | 2.27 m, 274° | 0.94 / 1.06 / 0.99; wrap 0.22; top 3 0.05 | 1.77 / 1.69 / 1.53; wrap 0.64; top 3 0.17 | 1.81 / 1.81 / 1.75; wrap 0.79; top 3 0.20 |
| 04Z | 2.70 m, 268° | 1.51 / 1.52 / 1.58; wrap 0.32; top 3 0.13 | 2.05 / 1.97 / 1.99; wrap 0.77; top 3 0.09 | 2.15 / 2.16 / 2.11; wrap 0.76; top 3 0.10 |
| 05Z | 2.49 m, 274° | 1.09 / 1.19 / 1.22; wrap 0.36; top 3 0.09 | 1.75 / 1.78 / 1.64; wrap 0.81; top 3 0.10 | 2.00 / 1.99 / 1.93; wrap 0.73; top 3 0.09 |
| 06Z | 2.45 m, 276° | 1.02 / 1.13 / 1.14; wrap 0.34; top 3 0.06 | 1.81 / 1.72 / 1.56; wrap 0.68; top 3 0.16 | 1.92 / 1.90 / 1.82; wrap 0.70; top 3 0.15 |
| 07Z | 2.97 m, 272° | 1.37 / 1.43 / 1.41; wrap 0.37; top 3 0.09 | 1.91 / 1.93 / 1.88; wrap 0.71; top 3 0.10 | 2.10 / 2.12 / 2.09; wrap 0.65; top 3 0.08 |
| 08Z | 3.13 m, 277° | 1.17 / 1.25 / 1.21; wrap 0.38; top 3 0.07 | 1.76 / 1.83 / 1.72; wrap 0.72; top 3 0.09 | 1.98 / 2.04 / 2.03; wrap 0.74; top 3 0.07 |
| 09Z | 3.48 m, 274° | 1.26 / 1.33 / 1.35; wrap 0.34; top 3 0.10 | 1.84 / 1.90 / 1.75; wrap 0.74; top 3 0.11 | 2.07 / 2.16 / 2.13; wrap 0.69; top 3 0.09 |
| 10Z | 3.54 m, 280° | 1.13 / 1.27 / 1.25; wrap 0.30; top 3 0.08 | 1.63 / 1.87 / 1.81; wrap 0.71; top 3 0.13 | 1.83 / 2.14 / 2.12; wrap 0.66; top 3 0.05 |
| 11Z | 3.55 m, 283° | 1.31 / 1.40 / 1.39; wrap 0.37; top 3 0.07 | 1.90 / 1.94 / 1.87; wrap 0.68; top 3 0.05 | 2.12 / 2.16 / 2.11; wrap 0.68; top 3 0.05 |
| 12Z | 3.61 m, 282° | 1.37 / 1.39 / 1.42; wrap 0.26; top 3 0.09 | 1.90 / 1.92 / 1.80; wrap 0.69; top 3 0.10 | 2.07 / 2.05 / 2.03; wrap 0.63; top 3 0.08 |
| 13Z | 3.60 m, 282° | 1.19 / 1.26 / 1.31; wrap 0.33; top 3 0.05 | 1.88 / 1.92 / 1.81; wrap 0.71; top 3 0.12 | 2.12 / 2.13 / 2.11; wrap 0.68; top 3 0.11 |
| 14Z | 3.51 m, 281° | 1.26 / 1.29 / 1.28; wrap 0.29; top 3 0.12 | 1.77 / 1.83 / 1.66; wrap 0.62; top 3 0.12 | 1.81 / 1.92 / 1.99; wrap 0.61; top 3 0.10 |
| 15Z | 3.57 m, 283° | 1.19 / 1.25 / 1.25; wrap 0.33; top 3 0.07 | 1.72 / 1.76 / 1.71; wrap 0.76; top 3 0.11 | 2.02 / 2.06 / 2.05; wrap 0.70; top 3 0.05 |
| 16Z | 3.51 m, 284° | 1.12 / 1.16 / 1.23; wrap 0.24; top 3 0.05 | 1.66 / 1.75 / 1.65; wrap 0.66; top 3 0.11 | 2.20 / 1.98 / 1.75; wrap 0.58; top 3 0.20 |
| 17Z | 3.48 m, 289° | 1.15 / 1.18 / 1.12; wrap 0.29; top 3 0.11 | 1.62 / 1.71 / 1.71; wrap 0.70; top 3 0.14 | 1.83 / 1.97 / 1.94; wrap 0.70; top 3 0.13 |
| 18Z | 3.64 m, 283° | 1.29 / 1.34 / 1.40; wrap 0.21; top 3 0.05 | 1.81 / 1.86 / 1.84; wrap 0.68; top 3 0.15 | 2.09 / 2.13 / 2.01; wrap 0.62; top 3 0.06 |
| 19Z | 3.30 m, 288° | 1.10 / 1.05 / 1.05; wrap 0.29; top 3 0.12 | 1.61 / 1.70 / 1.72; wrap 0.76; top 3 0.21 | 2.52 / 1.97 / 1.93; wrap 0.36; top 3 0.15 |
| 20Z | 3.57 m, 284° | 1.12 / 1.18 / 1.30; wrap 0.35; top 3 0.08 | 1.75 / 1.81 / 1.74; wrap 0.74; top 3 0.18 | 2.01 / 2.08 / 1.98; wrap 0.62; top 3 0.06 |
| 21Z | 3.34 m, 284° | 1.09 / 1.17 / 1.30; wrap 0.31; top 3 0.04 | 1.69 / 1.81 / 1.75; wrap 0.73; top 3 0.14 | 1.91 / 2.05 / 1.99; wrap 0.71; top 3 0.11 |
| 22Z | 3.10 m, 284° | 1.05 / 1.10 / 1.12; wrap 0.30; top 3 0.06 | 1.75 / 1.72 / 1.62; wrap 0.75; top 3 0.34 | 1.95 / 1.94 / 1.83; wrap 0.76; top 3 0.27 |
| 23Z | 3.03 m, 283° | 0.94 / 1.02 / 1.04; wrap 0.31; top 3 0.05 | 1.71 / 1.66 / 1.63; wrap 0.70; top 3 0.19 | 1.90 / 1.87 / 1.73; wrap 0.70; top 3 0.14 |
