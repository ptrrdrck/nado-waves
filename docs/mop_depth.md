# The chain's own rays from MOP's points

Generated 2026-11-18 17:31 UTC by `python -m forecast.mopdepth` (precompute-side, numpy; not run by any workflow). **A model against a model**: MOP is a cross-check, not a verification series; nothing here is fitted or shipped (BRIEFING §56b).

Each start is a transfer table built by `raytrace.table` itself (same frequencies, 0.5° headings, islands and diffracting edges as shipped; no Madsen), carried hour by hour through the archived 46232 spectra (maximum entropy). Every figure is deep-water-equivalent Hs over 46232's Hs, before friction: `eq` with diffraction (`hs_equivalent`), `hard` with hard edges (`hs_hard`). MOP is de-shoaled at its own Tp from 10 m (as `mopcheck`) and, in brackets in the ratio tables, from 10.77 m (10 m NAVD88 on MSL).

Starts: `break_5m` the shipped table; `normal_mop` the break's normal out to the seabed's depth at the MOP point; `mop` at the MOP point (both half-fans).

## How to read it

- chain-at-MOP / MOP near 1 would put the 5 m excess between 10 m and 5 m (the place); above 1 puts it in the tables over the same water. `5 m / chain-at-MOP` is what the leg from MOP's point to the break adds.
- `normal_mop` is the break's own normal out to the MOP point's depth. At South it is beside the MOP point; at Center and North the ~11 m contour on the normal is 3 km out, on the open shelf, so there it is a third place, not the 10 m → 5 m leg.
- The frequency table sets the chain's energy up to a cut against MOP's WHOLE Hs. Near 1 at ≤ 0.1 Hz says the chain's swell alone is as big as all of MOP; it does not say the swell agrees. Which band MOP is short in needs MOP's own spectrum.
- Fourier against maximum entropy is the buoy's directional reading alone: the same tables, a different spread.

## Controls

- coronado_north: `break_5m` against the committed table: 0 of 23040 rows differ.
- coronado_center: `break_5m` against the committed table: 0 of 23040 rows differ.
- coronado_south: `break_5m` against the committed table: 0 of 23040 rows differ.

## coronado_north — shown, not read (§29)

MOP D0181: seabed 10.77 m below MSL there; starts: `break_5m` 5.05 m at 32.68472, -117.195172; `normal_mop` 10.79 m at 32.65737, -117.203203; `mop` 10.77 m at 32.673562, -117.191205. 2154 matched hours.

| 46232 from | n | MOP | break_5m eq | normal_mop eq | mop eq | mop hard |
|---|---:|---|---|---|---|---|
| S (150–205°) | 653 | 0.47 [0.36, 0.56] | 0.61 [0.48, 0.81] | 0.77 [0.67, 0.86] | 0.59 [0.50, 0.69] | 0.57 [0.47, 0.67] |
| SSW-SW (205–235°) | 961 | 0.56 [0.46, 0.68] | 0.70 [0.54, 0.92] | 0.84 [0.75, 0.96] | 0.69 [0.59, 0.82] | 0.67 [0.56, 0.80] |
| WSW-W (235–270°) | 335 | 0.56 [0.48, 0.66] | 0.57 [0.46, 0.75] | 0.88 [0.79, 0.96] | 0.73 [0.64, 0.84] | 0.70 [0.61, 0.81] |
| W-WNW (270–295°) | 205 | 0.52 [0.45, 0.61] | 0.45 [0.34, 0.55] | 0.91 [0.82, 0.98] | 0.73 [0.63, 0.84] | 0.69 [0.59, 0.78] |
| all (0–360°) | 2154 | 0.53 [0.42, 0.65] | 0.63 [0.46, 0.85] | 0.83 [0.72, 0.95] | 0.67 [0.55, 0.81] | 0.65 [0.52, 0.78] |

Ratios, hour by hour, median [10th, 90th] (MOP from 10.77 m in brackets):

| 46232 from | chain-at-MOP / MOP, eq | hard | 5 m / chain-at-MOP | 5 m / normal 10 m | normal 10 m / chain-at-MOP |
|---|---|---|---|---|---|
| S | 1.27 [1.09, 1.50] (1.25) | 1.22 [1.04, 1.44] | 1.04 [0.88, 1.30] | 0.80 [0.69, 0.97] | 1.30 [1.17, 1.44] |
| SSW-SW | 1.24 [1.08, 1.42] (1.22) | 1.20 [1.04, 1.37] | 1.00 [0.85, 1.23] | 0.83 [0.69, 0.99] | 1.21 [1.10, 1.36] |
| WSW-W | 1.29 [1.12, 1.52] (1.27) | 1.24 [1.07, 1.45] | 0.80 [0.65, 0.96] | 0.67 [0.54, 0.84] | 1.19 [1.08, 1.33] |
| W-WNW | 1.40 [1.17, 1.67] (1.38) | 1.30 [1.10, 1.56] | 0.61 [0.47, 0.72] | 0.50 [0.40, 0.58] | 1.23 [1.10, 1.40] |
| all | 1.26 [1.09, 1.49] (1.24) | 1.21 [1.05, 1.43] | 0.96 [0.68, 1.22] | 0.79 [0.56, 0.96] | 1.24 [1.10, 1.39] |

chain-at-MOP / MOP (eq) by 46232's swell peak period:

| 46232 from | 8–11 s | 11–14 s | 14–17 s | 17–26 s |
|---|---|---|---|---|
| S | 1.39 (n 39) | 1.30 (n 258) | 1.23 (n 315) | 1.26 (n 41) |
| SSW-SW | 1.29 (n 22) | 1.22 (n 190) | 1.24 (n 665) | 1.29 (n 84) |
| WSW-W | 1.24 (n 38) | 1.29 (n 139) | 1.29 (n 145) | 1.39 (n 13) |
| W-WNW | 1.30 (n 6) | 1.38 (n 66) | 1.41 (n 118) | 1.39 (n 15) |
| all | 1.33 (n 105) | 1.28 (n 653) | 1.25 (n 1243) | 1.29 (n 153) |

chain-at-MOP (eq, maximum entropy) with only its energy up to a frequency, over MOP's whole Hs; and with the whole spectrum read by Fourier instead:

| 46232 from | ≤ 0.1 Hz | ≤ 0.125 Hz | ≤ 0.15 Hz | ≤ 0.2 Hz | ≤ 0.25 Hz | ≤ 0.58 Hz | Fourier, all |
|---|---|---|---|---|---|---|---|
| S | 0.99 | 1.08 | 1.15 | 1.21 | 1.24 | 1.27 | 1.53 |
| SSW-SW | 0.99 | 1.06 | 1.13 | 1.19 | 1.22 | 1.24 | 1.42 |
| WSW-W | 1.04 | 1.15 | 1.21 | 1.26 | 1.27 | 1.29 | 1.46 |
| W-WNW | 1.25 | 1.32 | 1.36 | 1.38 | 1.39 | 1.40 | 1.70 |
| all | 1.01 | 1.10 | 1.16 | 1.22 | 1.24 | 1.26 | 1.48 |

Peak period over the same water (MOP's Tp; chain-at-MOP's densest bin), by 46232's overall peak:

| 46232 peak | n | MOP Tp | chain-at-MOP peak | hours MOP Tp < 9 s | hours chain peak < 9 s |
|---|---:|---|---|---:|---:|
| < 9 s | 53 | 16.67 [14.29, 18.18] | 15.38 [11.11, 18.18] | 2 | 4 |
| 9–12 s | 294 | 15.38 [12.30, 18.18] | 11.76 [10.53, 16.67] | 1 | 1 |
| ≥ 12 s | 1807 | 15.38 [13.33, 18.18] | 15.38 [12.50, 18.18] | 0 | 8 |

Share of chain-at-MOP's diffracted energy by kind of ray (sector totals), and chain-at-MOP / MOP with only the clear rays:

| 46232 from | clear | island fill | Point Loma fill | Baja fill | clear only / MOP |
|---|---|---|---|---|---|
| S | 91.1% | 4.6% | 4.1% | 0.1% | 1.21 [1.04, 1.43] |
| SSW-SW | 92.7% | 2.3% | 4.9% | 0.0% | 1.19 [1.04, 1.36] |
| WSW-W | 90.5% | 0.9% | 8.6% | 0.0% | 1.23 [1.06, 1.44] |
| W-WNW | 87.8% | 0.4% | 11.8% | 0.0% | 1.31 [1.10, 1.57] |
| all | 90.7% | 1.9% | 7.3% | 0.0% | 1.21 [1.05, 1.42] |

Where chain-at-MOP's energy comes from offshore (diffracted, sector totals, share by 10° of offshore heading; ≥ 3% shown) beside `break_5m`'s:

- **S** — MOP point: 170°s 7%, 180°s 4%, 190°s 3%, 210°s 9%, 220°s 20%, 230°s 14%, 240°s 8%, 250°s 8%, 260°s 7%, 270°s 7%, 280°s 4%; break 5 m: 170°s 6%, 180°s 8%, 190°s 11%, 200°s 17%, 210°s 25%, 220°s 14%, 230°s 9%, 240°s 5%
- **SSW-SW** — MOP point: 210°s 9%, 220°s 21%, 230°s 16%, 240°s 9%, 250°s 10%, 260°s 8%, 270°s 8%, 280°s 6%; break 5 m: 180°s 4%, 190°s 9%, 200°s 19%, 210°s 26%, 220°s 15%, 230°s 12%, 240°s 6%
- **WSW-W** — MOP point: 210°s 4%, 220°s 12%, 230°s 12%, 240°s 7%, 250°s 10%, 260°s 13%, 270°s 21%, 280°s 11%, 290°s 4%; break 5 m: 190°s 4%, 200°s 12%, 210°s 24%, 220°s 15%, 230°s 14%, 240°s 9%, 250°s 4%, 260°s 7%, 270°s 4%
- **W-WNW** — MOP point: 220°s 6%, 230°s 6%, 240°s 5%, 250°s 7%, 260°s 10%, 270°s 28%, 280°s 23%, 290°s 8%; break 5 m: 200°s 8%, 210°s 15%, 220°s 11%, 230°s 13%, 240°s 10%, 250°s 6%, 260°s 11%, 270°s 8%, 280°s 11%

Direction over the same water: MOP's peak direction (Dp) against the heading chain-at-MOP's energy arrives on in the 46232 bin nearest MOP's Tp:

| 46232 from | MOP Dp | chain-at-MOP | chain − MOP |
|---|---|---|---|
| S | 198.70 [195.75, 200.37] | 198.17 [192.85, 205.33] | -0.33 [-4.64, 6.02] |
| SSW-SW | 199.33 [195.76, 203.20] | 198.98 [194.56, 210.19] | 0.06 [-4.16, 7.97] |
| WSW-W | 202.01 [198.66, 213.43] | 205.56 [197.32, 224.19] | 2.91 [-2.70, 13.01] |
| W-WNW | 214.12 [209.62, 215.97] | 222.68 [214.64, 229.10] | 9.02 [1.65, 15.47] |
| all | 199.55 [196.26, 212.02] | 199.70 [194.60, 220.54] | 0.67 [-3.90, 10.48] |

Acceptance per offshore degree at 14.3 s (Σ width·diff_gain/Ks² per radian, 10° bins; planar-beach Kr² ≤ 1), by start:

| offshore from | break_5m | normal_mop | mop |
|---|---|---|---|
| 150–160° | 0.00 | 0.14 | 0.00 |
| 160–170° | 0.00 | 0.67 | 0.08 |
| 170–180° | 0.33 | 0.39 | 0.15 |
| 180–190° | 0.18 | 0.42 | 0.28 |
| 190–200° | 0.15 | 0.23 | 0.00 |
| 200–210° | 2.53 | 1.47 | 0.00 |
| 210–220° | 1.82 | 2.82 | 0.64 |
| 220–230° | 1.61 | 2.90 | 2.48 |
| 230–240° | 1.96 | 0.32 | 2.77 |
| 240–250° | 2.06 | 1.14 | 1.49 |
| 250–260° | 0.00 | 1.47 | 1.34 |
| 260–270° | 0.59 | 0.80 | 0.48 |
| 270–280° | 0.00 | 0.89 | 2.09 |
| 280–290° | 0.00 | 1.10 | 0.50 |
| 290–300° | 0.00 | 0.84 | 0.30 |
| 300–310° | 0.00 | 0.26 | 0.34 |
| 310–320° | 0.00 | 0.12 | 0.00 |

## coronado_center

MOP D0179: seabed 10.98 m below MSL there; starts: `break_5m` 5.03 m at 32.680946, -117.186314; `normal_mop` 10.99 m at 32.655488, -117.20646; `mop` 11.0 m at 32.673935, -117.188472. 2154 matched hours.

| 46232 from | n | MOP | break_5m eq | normal_mop eq | mop eq | mop hard |
|---|---:|---|---|---|---|---|
| S (150–205°) | 653 | 0.43 [0.32, 0.49] | 0.50 [0.43, 0.59] | 0.84 [0.74, 0.95] | 0.54 [0.45, 0.61] | 0.52 [0.44, 0.60] |
| SSW-SW (205–235°) | 961 | 0.51 [0.42, 0.61] | 0.59 [0.49, 0.71] | 0.89 [0.79, 0.99] | 0.62 [0.54, 0.73] | 0.61 [0.53, 0.72] |
| WSW-W (235–270°) | 335 | 0.54 [0.45, 0.65] | 0.66 [0.56, 0.78] | 0.89 [0.81, 0.97] | 0.70 [0.60, 0.83] | 0.68 [0.58, 0.82] |
| W-WNW (270–295°) | 205 | 0.53 [0.45, 0.63] | 0.72 [0.59, 0.83] | 0.95 [0.87, 1.06] | 0.75 [0.64, 0.87] | 0.74 [0.62, 0.86] |
| all (0–360°) | 2154 | 0.49 [0.38, 0.60] | 0.58 [0.47, 0.74] | 0.88 [0.77, 0.99] | 0.61 [0.50, 0.77] | 0.60 [0.49, 0.76] |

Ratios, hour by hour, median [10th, 90th] (MOP from 10.77 m in brackets):

| 46232 from | chain-at-MOP / MOP, eq | hard | 5 m / chain-at-MOP | 5 m / normal 10 m | normal 10 m / chain-at-MOP |
|---|---|---|---|---|---|
| S | 1.29 [1.10, 1.53] (1.27) | 1.25 [1.07, 1.48] | 0.94 [0.88, 1.03] | 0.61 [0.52, 0.69] | 1.54 [1.39, 1.85] |
| SSW-SW | 1.24 [1.09, 1.44] (1.23) | 1.21 [1.06, 1.40] | 0.95 [0.88, 1.01] | 0.67 [0.58, 0.78] | 1.40 [1.22, 1.63] |
| WSW-W | 1.29 [1.13, 1.53] (1.28) | 1.27 [1.11, 1.50] | 0.94 [0.88, 0.99] | 0.74 [0.64, 0.85] | 1.27 [1.12, 1.46] |
| W-WNW | 1.40 [1.18, 1.74] (1.38) | 1.37 [1.15, 1.70] | 0.95 [0.85, 1.06] | 0.74 [0.65, 0.85] | 1.29 [1.10, 1.48] |
| all | 1.27 [1.10, 1.51] (1.25) | 1.24 [1.07, 1.47] | 0.94 [0.88, 1.01] | 0.67 [0.56, 0.80] | 1.42 [1.19, 1.68] |

chain-at-MOP / MOP (eq) by 46232's swell peak period:

| 46232 from | 8–11 s | 11–14 s | 14–17 s | 17–26 s |
|---|---|---|---|---|
| S | 1.37 (n 39) | 1.31 (n 258) | 1.25 (n 315) | 1.30 (n 41) |
| SSW-SW | 1.31 (n 22) | 1.20 (n 190) | 1.24 (n 665) | 1.37 (n 84) |
| WSW-W | 1.24 (n 38) | 1.31 (n 139) | 1.29 (n 145) | 1.38 (n 13) |
| W-WNW | 1.33 (n 6) | 1.38 (n 66) | 1.43 (n 118) | 1.29 (n 15) |
| all | 1.34 (n 105) | 1.29 (n 653) | 1.26 (n 1243) | 1.35 (n 153) |

chain-at-MOP (eq, maximum entropy) with only its energy up to a frequency, over MOP's whole Hs; and with the whole spectrum read by Fourier instead:

| 46232 from | ≤ 0.1 Hz | ≤ 0.125 Hz | ≤ 0.15 Hz | ≤ 0.2 Hz | ≤ 0.25 Hz | ≤ 0.58 Hz | Fourier, all |
|---|---|---|---|---|---|---|---|
| S | 0.97 | 1.07 | 1.15 | 1.21 | 1.25 | 1.29 | 1.57 |
| SSW-SW | 0.97 | 1.04 | 1.12 | 1.18 | 1.21 | 1.24 | 1.44 |
| WSW-W | 1.05 | 1.15 | 1.20 | 1.25 | 1.27 | 1.29 | 1.47 |
| W-WNW | 1.26 | 1.33 | 1.37 | 1.39 | 1.40 | 1.40 | 1.63 |
| all | 1.01 | 1.09 | 1.15 | 1.21 | 1.24 | 1.27 | 1.50 |

Peak period over the same water (MOP's Tp; chain-at-MOP's densest bin), by 46232's overall peak:

| 46232 peak | n | MOP Tp | chain-at-MOP peak | hours MOP Tp < 9 s | hours chain peak < 9 s |
|---|---:|---|---|---:|---:|
| < 9 s | 53 | 16.67 [14.29, 18.18] | 15.38 [9.90, 18.18] | 0 | 5 |
| 9–12 s | 294 | 14.29 [11.11, 18.18] | 11.76 [10.53, 16.67] | 0 | 1 |
| ≥ 12 s | 1807 | 15.38 [13.33, 18.18] | 14.29 [12.50, 18.18] | 0 | 16 |

Share of chain-at-MOP's diffracted energy by kind of ray (sector totals), and chain-at-MOP / MOP with only the clear rays:

| 46232 from | clear | island fill | Point Loma fill | Baja fill | clear only / MOP |
|---|---|---|---|---|---|
| S | 93.1% | 3.3% | 3.4% | 0.1% | 1.24 [1.06, 1.46] |
| SSW-SW | 94.3% | 2.0% | 3.6% | 0.1% | 1.20 [1.05, 1.39] |
| WSW-W | 96.0% | 0.6% | 3.3% | 0.0% | 1.27 [1.10, 1.49] |
| W-WNW | 96.4% | 0.3% | 3.3% | 0.0% | 1.38 [1.15, 1.71] |
| all | 95.1% | 1.4% | 3.4% | 0.1% | 1.23 [1.07, 1.47] |

Where chain-at-MOP's energy comes from offshore (diffracted, sector totals, share by 10° of offshore heading; ≥ 3% shown) beside `break_5m`'s:

- **S** — MOP point: 170°s 4%, 180°s 6%, 190°s 4%, 200°s 4%, 210°s 6%, 220°s 11%, 230°s 18%, 240°s 12%, 250°s 9%, 260°s 7%, 270°s 8%, 280°s 4%; break 5 m: 160°s 4%, 170°s 9%, 180°s 5%, 210°s 8%, 220°s 15%, 230°s 16%, 240°s 11%, 250°s 9%, 260°s 6%, 270°s 7%
- **SSW-SW** — MOP point: 200°s 4%, 210°s 7%, 220°s 11%, 230°s 20%, 240°s 13%, 250°s 10%, 260°s 9%, 270°s 11%, 280°s 5%; break 5 m: 210°s 8%, 220°s 16%, 230°s 18%, 240°s 13%, 250°s 11%, 260°s 8%, 270°s 10%, 280°s 4%
- **WSW-W** — MOP point: 220°s 5%, 230°s 13%, 240°s 10%, 250°s 9%, 260°s 13%, 270°s 25%, 280°s 13%; break 5 m: 210°s 3%, 220°s 8%, 230°s 12%, 240°s 10%, 250°s 11%, 260°s 13%, 270°s 24%, 280°s 12%
- **W-WNW** — MOP point: 230°s 6%, 240°s 6%, 250°s 6%, 260°s 9%, 270°s 31%, 280°s 28%, 290°s 5%, 300°s 3%; break 5 m: 220°s 3%, 230°s 6%, 240°s 6%, 250°s 7%, 260°s 10%, 270°s 28%, 280°s 31%, 290°s 5%

Direction over the same water: MOP's peak direction (Dp) against the heading chain-at-MOP's energy arrives on in the 46232 bin nearest MOP's Tp:

| 46232 from | MOP Dp | chain-at-MOP | chain − MOP |
|---|---|---|---|
| S | 201.32 [198.22, 204.20] | 200.85 [193.73, 207.51] | -0.48 [-7.74, 6.84] |
| SSW-SW | 202.11 [198.48, 207.07] | 202.27 [196.74, 210.49] | -0.24 [-5.83, 6.58] |
| WSW-W | 205.81 [201.86, 218.36] | 208.72 [199.57, 220.46] | 1.34 [-3.63, 7.10] |
| W-WNW | 216.75 [211.97, 219.85] | 219.59 [214.31, 222.72] | 2.54 [-2.15, 7.39] |
| all | 202.32 [198.93, 215.03] | 203.36 [196.27, 218.52] | 0.30 [-5.85, 6.86] |

Acceptance per offshore degree at 14.3 s (Σ width·diff_gain/Ks² per radian, 10° bins; planar-beach Kr² ≤ 1), by start:

| offshore from | break_5m | normal_mop | mop |
|---|---|---|---|
| 150–160° | 0.38 | 4.05 | 0.00 |
| 160–170° | 0.24 | 0.55 | 0.00 |
| 170–180° | 0.08 | 0.16 | 0.43 |
| 180–190° | 0.00 | 0.50 | 0.18 |
| 190–200° | 0.09 | 0.00 | 0.00 |
| 200–210° | 0.15 | 0.82 | 0.25 |
| 210–220° | 0.31 | 2.17 | 0.44 |
| 220–230° | 1.13 | 2.22 | 0.76 |
| 230–240° | 1.94 | 0.57 | 2.32 |
| 240–250° | 2.06 | 1.37 | 1.79 |
| 250–260° | 1.47 | 0.78 | 1.08 |
| 260–270° | 0.67 | 0.89 | 1.18 |
| 270–280° | 0.94 | 0.35 | 1.89 |
| 280–290° | 0.95 | 2.09 | 0.47 |
| 290–300° | 0.34 | 0.60 | 0.09 |
| 300–310° | 0.20 | 0.65 | 0.11 |
| 310–320° | 0.00 | 0.10 | 0.25 |

## coronado_south

MOP D0168: seabed 10.95 m below MSL there; starts: `break_5m` 5.03 m at 32.67354, -117.175819; `normal_mop` 10.96 m at 32.669484, -117.17996; `mop` 10.96 m at 32.668966, -117.178924. 2154 matched hours.

| 46232 from | n | MOP | break_5m eq | normal_mop eq | mop eq | mop hard |
|---|---:|---|---|---|---|---|
| S (150–205°) | 653 | 0.37 [0.29, 0.44] | 0.52 [0.46, 0.58] | 0.49 [0.42, 0.56] | 0.53 [0.43, 0.59] | 0.48 [0.40, 0.55] |
| SSW-SW (205–235°) | 961 | 0.44 [0.37, 0.55] | 0.57 [0.49, 0.65] | 0.56 [0.49, 0.64] | 0.58 [0.51, 0.64] | 0.55 [0.47, 0.61] |
| WSW-W (235–270°) | 335 | 0.54 [0.43, 0.65] | 0.68 [0.59, 0.84] | 0.66 [0.58, 0.75] | 0.65 [0.58, 0.72] | 0.62 [0.55, 0.69] |
| W-WNW (270–295°) | 205 | 0.55 [0.47, 0.66] | 0.81 [0.71, 0.90] | 0.71 [0.64, 0.77] | 0.70 [0.62, 0.78] | 0.65 [0.58, 0.72] |
| all (0–360°) | 2154 | 0.44 [0.34, 0.59] | 0.57 [0.48, 0.78] | 0.56 [0.46, 0.70] | 0.58 [0.49, 0.69] | 0.55 [0.45, 0.65] |

Ratios, hour by hour, median [10th, 90th] (MOP from 10.77 m in brackets):

| 46232 from | chain-at-MOP / MOP, eq | hard | 5 m / chain-at-MOP | 5 m / normal 10 m | normal 10 m / chain-at-MOP |
|---|---|---|---|---|---|
| S | 1.41 [1.18, 1.76] (1.39) | 1.30 [1.09, 1.56] | 0.98 [0.90, 1.14] | 1.05 [0.98, 1.16] | 0.95 [0.86, 1.03] |
| SSW-SW | 1.30 [1.09, 1.53] (1.28) | 1.22 [1.03, 1.44] | 0.99 [0.91, 1.08] | 1.01 [0.96, 1.09] | 0.98 [0.90, 1.05] |
| WSW-W | 1.19 [1.00, 1.46] (1.18) | 1.14 [0.96, 1.40] | 1.07 [0.97, 1.21] | 1.04 [0.97, 1.14] | 1.03 [0.95, 1.11] |
| W-WNW | 1.27 [1.05, 1.49] (1.26) | 1.18 [0.97, 1.39] | 1.15 [1.02, 1.30] | 1.14 [1.04, 1.28] | 1.02 [0.91, 1.09] |
| all | 1.31 [1.09, 1.59] (1.30) | 1.23 [1.02, 1.48] | 1.00 [0.91, 1.16] | 1.03 [0.97, 1.15] | 0.98 [0.88, 1.06] |

chain-at-MOP / MOP (eq) by 46232's swell peak period:

| 46232 from | 8–11 s | 11–14 s | 14–17 s | 17–26 s |
|---|---|---|---|---|
| S | 1.50 (n 39) | 1.38 (n 258) | 1.42 (n 315) | 1.45 (n 41) |
| SSW-SW | 1.31 (n 22) | 1.19 (n 190) | 1.31 (n 665) | 1.44 (n 84) |
| WSW-W | 1.09 (n 38) | 1.18 (n 139) | 1.22 (n 145) | 1.39 (n 13) |
| W-WNW | 1.27 (n 6) | 1.24 (n 66) | 1.29 (n 118) | 1.29 (n 15) |
| all | 1.31 (n 105) | 1.26 (n 653) | 1.33 (n 1243) | 1.44 (n 153) |

chain-at-MOP (eq, maximum entropy) with only its energy up to a frequency, over MOP's whole Hs; and with the whole spectrum read by Fourier instead:

| 46232 from | ≤ 0.1 Hz | ≤ 0.125 Hz | ≤ 0.15 Hz | ≤ 0.2 Hz | ≤ 0.25 Hz | ≤ 0.58 Hz | Fourier, all |
|---|---|---|---|---|---|---|---|
| S | 0.98 | 1.11 | 1.23 | 1.31 | 1.35 | 1.41 | 1.50 |
| SSW-SW | 0.86 | 0.97 | 1.13 | 1.22 | 1.27 | 1.30 | 1.39 |
| WSW-W | 0.87 | 1.00 | 1.10 | 1.15 | 1.17 | 1.19 | 1.27 |
| W-WNW | 1.08 | 1.16 | 1.23 | 1.25 | 1.26 | 1.27 | 1.43 |
| all | 0.93 | 1.05 | 1.16 | 1.24 | 1.28 | 1.31 | 1.41 |

Peak period over the same water (MOP's Tp; chain-at-MOP's densest bin), by 46232's overall peak:

| 46232 peak | n | MOP Tp | chain-at-MOP peak | hours MOP Tp < 9 s | hours chain peak < 9 s |
|---|---:|---|---|---:|---:|
| < 9 s | 53 | 14.29 [8.16, 18.18] | 7.69 [6.67, 15.38] | 13 | 36 |
| 9–12 s | 294 | 12.30 [9.09, 16.67] | 11.76 [9.09, 13.33] | 15 | 23 |
| ≥ 12 s | 1807 | 15.38 [12.30, 16.67] | 14.29 [11.76, 16.67] | 41 | 111 |

Share of chain-at-MOP's diffracted energy by kind of ray (sector totals), and chain-at-MOP / MOP with only the clear rays:

| 46232 from | clear | island fill | Point Loma fill | Baja fill | clear only / MOP |
|---|---|---|---|---|---|
| S | 82.4% | 13.4% | 3.7% | 0.5% | 1.29 [1.08, 1.55] |
| SSW-SW | 86.8% | 8.3% | 4.7% | 0.2% | 1.21 [1.02, 1.43] |
| WSW-W | 89.2% | 2.6% | 8.1% | 0.1% | 1.13 [0.96, 1.39] |
| W-WNW | 79.6% | 0.9% | 19.4% | 0.0% | 1.17 [0.97, 1.37] |
| all | 84.3% | 5.7% | 9.8% | 0.2% | 1.22 [1.02, 1.47] |

Where chain-at-MOP's energy comes from offshore (diffracted, sector totals, share by 10° of offshore heading; ≥ 3% shown) beside `break_5m`'s:

- **S** — MOP point: 170°s 7%, 180°s 11%, 190°s 12%, 200°s 5%, 230°s 4%, 240°s 9%, 250°s 13%, 260°s 9%, 270°s 12%, 280°s 5%; break 5 m: 170°s 14%, 180°s 14%, 190°s 8%, 220°s 3%, 230°s 3%, 240°s 7%, 250°s 11%, 260°s 11%, 270°s 12%, 280°s 4%
- **SSW-SW** — MOP point: 180°s 6%, 190°s 8%, 200°s 5%, 210°s 3%, 230°s 4%, 240°s 11%, 250°s 17%, 260°s 11%, 270°s 15%, 280°s 7%, 290°s 4%; break 5 m: 180°s 5%, 190°s 5%, 220°s 4%, 230°s 4%, 240°s 9%, 250°s 14%, 260°s 15%, 270°s 19%, 280°s 8%, 290°s 4%
- **WSW-W** — MOP point: 240°s 9%, 250°s 15%, 260°s 13%, 270°s 25%, 280°s 15%, 290°s 5%; break 5 m: 240°s 6%, 250°s 11%, 260°s 15%, 270°s 31%, 280°s 17%, 290°s 6%
- **W-WNW** — MOP point: 240°s 5%, 250°s 9%, 260°s 8%, 270°s 24%, 280°s 36%, 290°s 8%, 300°s 3%; break 5 m: 250°s 6%, 260°s 10%, 270°s 31%, 280°s 28%, 290°s 15%

Direction over the same water: MOP's peak direction (Dp) against the heading chain-at-MOP's energy arrives on in the 46232 bin nearest MOP's Tp:

| 46232 from | MOP Dp | chain-at-MOP | chain − MOP |
|---|---|---|---|
| S | 212.81 [210.57, 221.46] | 209.80 [205.57, 218.03] | -3.68 [-8.88, 0.49] |
| SSW-SW | 214.51 [210.96, 224.79] | 213.23 [207.76, 222.41] | -1.75 [-6.75, 2.64] |
| WSW-W | 219.02 [215.74, 228.04] | 221.59 [214.23, 229.66] | 0.27 [-5.02, 8.45] |
| W-WNW | 219.35 [217.45, 226.10] | 226.24 [223.03, 236.75] | 6.37 [-0.30, 18.26] |
| all | 215.50 [211.01, 225.75] | 213.92 [206.92, 227.09] | -1.63 [-7.03, 5.85] |

Acceptance per offshore degree at 14.3 s (Σ width·diff_gain/Ks² per radian, 10° bins; planar-beach Kr² ≤ 1), by start:

| offshore from | break_5m | normal_mop | mop |
|---|---|---|---|
| 150–160° | 0.43 | 0.22 | 0.00 |
| 160–170° | 0.63 | 0.31 | 0.32 |
| 170–180° | 0.15 | 0.00 | 0.30 |
| 180–190° | 0.00 | 0.00 | 0.50 |
| 190–200° | 0.28 | 0.00 | 0.18 |
| 200–210° | 0.00 | 0.00 | 0.15 |
| 210–220° | 0.24 | 0.00 | 0.30 |
| 220–230° | 0.49 | 0.49 | 0.00 |
| 230–240° | 0.00 | 0.24 | 0.22 |
| 240–250° | 0.82 | 1.02 | 0.85 |
| 250–260° | 1.10 | 1.89 | 2.12 |
| 260–270° | 1.30 | 1.18 | 0.45 |
| 270–280° | 1.52 | 0.60 | 0.63 |
| 280–290° | 0.77 | 0.36 | 0.65 |
| 290–300° | 0.35 | 0.19 | 0.13 |
| 300–310° | 0.94 | 0.40 | 0.19 |
| 310–320° | 0.37 | 0.24 | 0.42 |
