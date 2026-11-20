# The chain's own rays from MOP's points

Generated 2026-11-20 01:46 UTC by `python -m forecast.mopdepth` (precompute-side, numpy; not run by any workflow). **A model against a model**: MOP is a cross-check, not a verification series; nothing here is fitted or shipped (BRIEFING §56b).

Each start is a transfer table built by `raytrace.table` itself (same frequencies, 0.5° headings, islands and diffracting edges as shipped; no Madsen), carried hour by hour through the archived 46232 spectra (maximum entropy). Every figure is deep-water-equivalent Hs over 46232's Hs, before friction: `eq` with diffraction (`hs_equivalent`), `hard` with hard edges (`hs_hard`). MOP is de-shoaled at its own Tp from 10 m (as `mopcheck`) and, in brackets in the ratio tables, from 10.77 m (10 m NAVD88 on MSL).

Starts: `break_5m` the shipped table; `normal_mop` the break's normal out to the seabed's depth at the MOP point; `mop` at the MOP point (both half-fans).

## How to read it

- chain-at-MOP / MOP near 1 would put the 5 m excess between 10 m and 5 m (the place); above 1 puts it in the tables over the same water. `5 m / chain-at-MOP` is what the leg from MOP's point to the break adds.
- `normal_mop` is the break's own normal out to the MOP point's depth. At South it is beside the MOP point; at Center and North the ~11 m contour on the normal is 3 km out, on the open shelf, so there it is a third place, not the 10 m → 5 m leg.
- The frequency table sets the chain's energy up to a cut against MOP's WHOLE Hs. Near 1 at ≤ 0.1 Hz says the chain's swell alone is as big as all of MOP; it does not say the swell agrees. Which band MOP is short in is the per-band section under each break, from MOP's own spectrum.
- Per band, both sides are deep-water-equivalent before friction: MOP de-shoaled band by band at each band's own frequency, chain-at-MOP as carried. `MOP / chain-at-MOP` over 46232 in the same band says which side moves: MOP taking less of the buoy's band, or the chain taking more.
- Fourier against maximum entropy is the buoy's directional reading alone: the same tables, a different spread.

## Controls

- coronado_north: `break_5m` against the committed table: 0 of 23040 rows differ.
- coronado_center: `break_5m` against the committed table: 0 of 23040 rows differ.
- coronado_south: `break_5m` against the committed table: 0 of 23040 rows differ.
- The point path (`point_spot`, the normal held), given Center's MOP point and Center's normal, against Center's `mop` table: 0 of 23040 rows differ.

## Exposed against shadowed (handoff 24b)

chain-at-MOP / MOP in each band as heights (√ energy ratio, both deep-water-equivalent before friction, MOP de-shoaled band by band), median, on the 2175 hours every place below has a matched 46232 spectrum and a complete MOP spectrum for. Straight-line Point Loma edge at each MOP point in brackets (`geometry.open_windows`, MOP's own normal). A band-hour is compared when 46232 has ≥ 0.05 m in it. Whole spectrum: chain-at-MOP / MOP, MOP de-shoaled by band. `32 m seabed` is the grid control: the same MOP point traced with the 8 m `nearshore` grid left out, the seabed a point outside it (Imperial Beach) is traced on.

| 46232 from | place | n | whole | 16.7–26.7 s | 13.0–16.7 s | 10.0–13.0 s | 8.0–10.0 s | 6.7–8.0 s | 5.0–6.7 s | 4.0–5.0 s | 2.2–4.0 s |
|---|---|---:|---|---|---|---|---|---|---|---|---|
| S | coronado_north (Point Loma 258.8°) | 653 | 1.15 | 1.03 | 1.16 | 1.22 | 1.13 | 1.13 | 1.14 | 1.00 | 0.86 |
| S | coronado_center (Point Loma 258.9°) | 653 | 1.16 | 1.11 | 1.14 | 1.18 | 1.18 | 1.15 | 1.13 | 1.01 | 0.85 |
| S | coronado_south (Point Loma 265.8°) | 653 | 1.26 | 1.26 | 1.52 | 1.35 | 1.11 | 1.27 | 1.17 | 0.95 | 0.83 |
| S | coronado_center, 32 m seabed (Point Loma 258.9°) | 653 | 1.17 | 1.13 | 1.13 | 1.18 | 1.18 | 1.16 | 1.16 | 1.00 | 0.85 |
| S | imperial_beach (Point Loma 315.6°) | 653 | 1.37 | 1.42 | 1.78 | 1.88 | 1.45 | 1.10 | 1.02 | 0.95 | 0.82 |
| SSW-SW | coronado_north (Point Loma 258.8°) | 961 | 1.15 | 1.05 | 1.15 | 1.18 | 1.10 | 1.15 | 1.16 | 1.06 | 0.90 |
| SSW-SW | coronado_center (Point Loma 258.9°) | 961 | 1.15 | 1.11 | 1.14 | 1.15 | 1.17 | 1.17 | 1.15 | 1.06 | 0.90 |
| SSW-SW | coronado_south (Point Loma 265.8°) | 961 | 1.18 | 1.20 | 1.34 | 1.18 | 1.02 | 1.28 | 1.18 | 1.01 | 0.87 |
| SSW-SW | coronado_center, 32 m seabed (Point Loma 258.9°) | 961 | 1.15 | 1.13 | 1.14 | 1.12 | 1.16 | 1.20 | 1.17 | 1.06 | 0.90 |
| SSW-SW | imperial_beach (Point Loma 315.6°) | 961 | 1.25 | 1.33 | 1.48 | 1.50 | 1.21 | 1.08 | 1.06 | 0.98 | 0.85 |
| WSW-W | coronado_north (Point Loma 258.8°) | 335 | 1.19 | 1.08 | 1.20 | 1.26 | 1.11 | 1.08 | 1.13 | 1.03 | 0.87 |
| WSW-W | coronado_center (Point Loma 258.9°) | 335 | 1.20 | 1.12 | 1.20 | 1.24 | 1.16 | 1.11 | 1.12 | 1.03 | 0.86 |
| WSW-W | coronado_south (Point Loma 265.8°) | 335 | 1.11 | 1.04 | 1.20 | 1.09 | 1.04 | 1.20 | 1.18 | 0.98 | 0.84 |
| WSW-W | coronado_center, 32 m seabed (Point Loma 258.9°) | 335 | 1.18 | 1.12 | 1.17 | 1.18 | 1.17 | 1.13 | 1.15 | 1.03 | 0.86 |
| WSW-W | imperial_beach (Point Loma 315.6°) | 335 | 1.26 | 1.34 | 1.40 | 1.54 | 1.29 | 1.10 | 1.07 | 0.96 | 0.82 |
| W-WNW | coronado_north (Point Loma 258.8°) | 226 | 1.27 | 1.17 | 1.37 | 1.27 | 1.09 | 1.02 | 1.07 | 0.98 | 0.76 |
| W-WNW | coronado_center (Point Loma 258.9°) | 226 | 1.30 | 1.30 | 1.39 | 1.29 | 1.10 | 1.08 | 1.06 | 0.98 | 0.74 |
| W-WNW | coronado_south (Point Loma 265.8°) | 226 | 1.17 | 1.03 | 1.36 | 0.99 | 0.99 | 1.15 | 1.10 | 0.92 | 0.71 |
| W-WNW | coronado_center, 32 m seabed (Point Loma 258.9°) | 226 | 1.24 | 1.28 | 1.31 | 1.21 | 1.11 | 1.10 | 1.10 | 0.97 | 0.75 |
| W-WNW | imperial_beach (Point Loma 315.6°) | 226 | 1.49 | 1.80 | 1.75 | 1.64 | 1.28 | 1.12 | 1.02 | 0.92 | 0.72 |
| all | coronado_north (Point Loma 258.8°) | 2175 | 1.16 | 1.06 | 1.17 | 1.21 | 1.11 | 1.12 | 1.13 | 1.03 | 0.87 |
| all | coronado_center (Point Loma 258.9°) | 2175 | 1.17 | 1.13 | 1.16 | 1.18 | 1.16 | 1.14 | 1.13 | 1.03 | 0.86 |
| all | coronado_south (Point Loma 265.8°) | 2175 | 1.20 | 1.16 | 1.36 | 1.20 | 1.04 | 1.25 | 1.17 | 0.98 | 0.84 |
| all | coronado_center, 32 m seabed (Point Loma 258.9°) | 2175 | 1.17 | 1.13 | 1.16 | 1.16 | 1.16 | 1.17 | 1.15 | 1.03 | 0.87 |
| all | imperial_beach (Point Loma 315.6°) | 2175 | 1.31 | 1.41 | 1.58 | 1.63 | 1.30 | 1.10 | 1.05 | 0.96 | 0.83 |

## imperial_beach — a MOP point that is not a break (handoff 24b)

MOP D0052 at 32.57851, -117.1423, 216 m from the search target [32.5785, -117.14] (Imperial Beach, near the pier: outside Point Loma's shadow (handoff 24b)). MOP's `metaWaterDepth` 10.0; the seabed reads 10.46 m below MSL there, from the 32 m grid (the Coronado points sit in the 8 m one). Fan centred on MOP's own `metaShoreNormal`, 264.48°; `mop` starts 10.46 m at 32.578508, -117.142321, `mop_back` (the opposite half) 10.46 m. 2175 matched hours, cut to the 2565 of its 2592 MOP hours that every break's MOP series also has.

Open arcs there, straight lines to the charted blockers: 174.5° (seaward limit) – 203.7° (Coronado Islands (South group)); 213.7° (Coronado Islands (South group)) – 221.5° (Coronado Islands (North group)); 224.9° (Coronado Islands (North group)) – 315.6° (Point Loma peninsula).

| 46232 from | n | MOP (at Tp) | chain-at-MOP eq | chain-at-MOP / MOP, eq (at Tp) | hard / MOP | back half's share | Fourier / MOP |
|---|---:|---|---|---|---|---|---|
| S | 653 | 0.59 [0.42, 0.70] | 0.94 [0.85, 1.03] | 1.57 [1.33, 2.26] | 1.57 [1.32, 2.23] | 0.0% | 1.51 [1.30, 2.03] |
| SSW-SW | 961 | 0.66 [0.55, 0.76] | 0.92 [0.84, 1.02] | 1.41 [1.18, 1.73] | 1.40 [1.18, 1.73] | 0.0% | 1.38 [1.21, 1.64] |
| WSW-W | 335 | 0.64 [0.55, 0.76] | 0.93 [0.83, 1.08] | 1.43 [1.18, 1.89] | 1.43 [1.17, 1.90] | 0.0% | 1.41 [1.19, 1.66] |
| W-WNW | 226 | 0.54 [0.46, 0.63] | 0.88 [0.74, 1.04] | 1.62 [1.30, 2.06] | 1.62 [1.30, 2.07] | 0.0% | 1.68 [1.40, 2.01] |
| all | 2175 | 0.62 [0.50, 0.74] | 0.93 [0.83, 1.03] | 1.48 [1.22, 1.93] | 1.48 [1.21, 1.93] | 0.0% | 1.45 [1.23, 1.81] |

From past the seaward limit: the share of chain-at-MOP's energy arriving from offshore headings more than 90° off the normal (below 174.5° or above 354.5°, 5° bins by centre), median, and chain-at-MOP / MOP (MOP de-shoaled by band) with and without those rays:

| 46232 from | n | share past the limit | chain-at-MOP / MOP | without them |
|---|---:|---|---|---|
| S | 653 | 10.1% [4.2, 33.6] | 1.37 [1.19, 2.03] | 1.28 [1.12, 1.73] |
| SSW-SW | 961 | 4.4% [2.3, 9.1] | 1.25 [1.06, 1.57] | 1.22 [1.04, 1.52] |
| WSW-W | 335 | 2.5% [1.0, 5.1] | 1.26 [1.07, 1.74] | 1.24 [1.05, 1.71] |
| W-WNW | 226 | 1.2% [0.7, 2.4] | 1.49 [1.17, 1.88] | 1.47 [1.16, 1.88] |
| all | 2175 | 4.5% [1.4, 14.4] | 1.31 [1.10, 1.73] | 1.26 [1.07, 1.66] |

Share of chain-at-MOP's diffracted energy by kind of ray (sector totals), and chain-at-MOP / MOP (at Tp) with only the clear rays:

| 46232 from | clear | island fill | Point Loma fill | Baja fill | clear only / MOP |
|---|---|---|---|---|---|
| S | 96.0% | 3.4% | 0.1% | 0.5% | 1.55 [1.30, 2.20] |
| SSW-SW | 96.4% | 3.1% | 0.2% | 0.3% | 1.38 [1.16, 1.70] |
| WSW-W | 98.5% | 1.3% | 0.1% | 0.1% | 1.41 [1.17, 1.89] |
| W-WNW | 99.1% | 0.6% | 0.2% | 0.1% | 1.61 [1.29, 2.05] |
| all | 97.3% | 2.3% | 0.2% | 0.3% | 1.46 [1.20, 1.91] |

Acceptance per offshore degree at 14.3 s (Σ width·diff_gain/Ks² per radian, 10° bins, both half-fans), beside a beach of straight parallel contours at MOP's normal (264.48°) and the start's depth (10.46 m): Snell's Kr² and arrival off the normal. A reference, not a claim about this seabed:

| offshore from | chain | straight contours Kr² | their arrival off normal |
|---|---|---|---|
| 150–160° | 0.54 | 0.00 |  |
| 160–170° | 0.55 | 0.00 |  |
| 170–180° | 0.98 | 0.01 | -26° |
| 180–190° | 1.51 | 0.20 | -26° |
| 190–200° | 1.67 | 0.38 | -24° |
| 200–210° | 0.85 | 0.55 | -22° |
| 210–220° | 0.54 | 0.69 | -19° |
| 220–230° | 0.89 | 0.80 | -16° |
| 230–240° | 0.11 | 0.89 | -12° |
| 240–250° | 0.60 | 0.95 | -8° |
| 250–260° | 1.50 | 0.99 | -4° |
| 260–270° | 1.62 | 1.00 | +0° |
| 270–280° | 2.52 | 0.99 | +5° |
| 280–290° | 0.00 | 0.95 | +9° |
| 290–300° | 0.12 | 0.88 | +13° |
| 300–310° | 0.11 | 0.79 | +17° |
| 310–320° | 0.13 | 0.68 | +20° |
| 320–330° | 0.00 | 0.53 | +22° |
| 150–330°, Σ × 10° | 143° | 113° | |

### MOP's own spectrum, band by band

MOP's 20 bands, 0.0375–0.4500 Hz (edges from `waveFrequencyBounds`); read-back 4·sqrt(Σ E·df) / MOP's Hs median 1.0, worst 1.0 over 2592 hours. Common bands 0.0375–0.4500 Hz. 2175 matched hours with a complete MOP spectrum; a band-hour is compared when 46232 has ≥ 0.05 m in the band.

Whole spectrum, MOP de-shoaled band by band at each band's frequency (10.77 m in brackets) against at its Tp as above; MOP's spectrum summed over its own Hs at the point:

| 46232 from | n | MOP, by band | MOP, at Tp | chain-at-MOP / MOP, by band | at Tp | spectrum Hs / MOP Hs |
|---|---:|---|---|---|---|---|
| S | 653 | 0.68 [0.47, 0.78] | 0.59 [0.42, 0.70] | 1.37 [1.19, 2.03] (1.37) | 1.57 | 1.00 [1.00, 1.00] |
| SSW-SW | 961 | 0.74 [0.62, 0.84] | 0.66 [0.55, 0.76] | 1.25 [1.06, 1.57] (1.24) | 1.41 | 1.00 [1.00, 1.00] |
| WSW-W | 335 | 0.71 [0.60, 0.83] | 0.64 [0.55, 0.76] | 1.26 [1.07, 1.74] (1.25) | 1.43 | 1.00 [1.00, 1.00] |
| W-WNW | 226 | 0.59 [0.51, 0.69] | 0.54 [0.46, 0.63] | 1.49 [1.17, 1.88] (1.47) | 1.62 | 1.00 [1.00, 1.00] |
| all | 2175 | 0.70 [0.56, 0.82] | 0.62 [0.50, 0.74] | 1.31 [1.10, 1.73] (1.31) | 1.48 | 1.00 [1.00, 1.00] |

chain-at-MOP / MOP in each band, as heights (√ of the energy ratio, both deep-water-equivalent, before friction), median [10th, 90th] and hours:

| 46232 from | 16.7–26.7 s | 13.0–16.7 s | 10.0–13.0 s | 8.0–10.0 s | 6.7–8.0 s | 5.0–6.7 s | 4.0–5.0 s | 2.2–4.0 s |
|---|---|---|---|---|---|---|---|---|
| S | 1.42 [0.96, 2.21] n 653 | 1.78 [1.25, 2.60] n 653 | 1.88 [1.41, 3.37] n 653 | 1.45 [1.02, 2.38] n 652 | 1.10 [0.83, 1.50] n 621 | 1.02 [0.82, 1.27] n 628 | 0.95 [0.73, 1.16] n 616 | 0.82 [0.60, 1.04] n 569 |
| SSW-SW | 1.33 [0.90, 1.94] n 961 | 1.48 [1.03, 2.02] n 961 | 1.50 [1.18, 1.99] n 961 | 1.21 [0.91, 1.68] n 961 | 1.08 [0.84, 1.42] n 951 | 1.06 [0.87, 1.26] n 954 | 0.98 [0.77, 1.22] n 927 | 0.85 [0.56, 1.10] n 901 |
| WSW-W | 1.34 [0.85, 2.14] n 329 | 1.40 [0.97, 2.11] n 335 | 1.54 [1.18, 2.18] n 335 | 1.29 [0.98, 1.75] n 335 | 1.10 [0.86, 1.36] n 335 | 1.07 [0.89, 1.26] n 335 | 0.96 [0.77, 1.16] n 328 | 0.82 [0.55, 1.08] n 307 |
| W-WNW | 1.80 [1.28, 2.55] n 226 | 1.75 [1.21, 2.39] n 226 | 1.64 [1.19, 2.20] n 226 | 1.28 [0.98, 1.76] n 226 | 1.12 [0.92, 1.41] n 226 | 1.02 [0.81, 1.23] n 223 | 0.92 [0.66, 1.11] n 196 | 0.72 [0.45, 0.96] n 159 |
| all | 1.41 [0.93, 2.15] n 2169 | 1.58 [1.07, 2.27] n 2175 | 1.63 [1.21, 2.34] n 2175 | 1.30 [0.95, 1.88] n 2174 | 1.10 [0.85, 1.44] n 2133 | 1.05 [0.84, 1.26] n 2140 | 0.96 [0.75, 1.19] n 2067 | 0.83 [0.56, 1.08] n 1936 |

Each over 46232 in the same band, as heights (√ energy ratio), median: MOP / chain-at-MOP. Where MOP is lower than the chain, this says whether MOP takes less of the buoy's band or the chain takes more:

| 46232 from | 16.7–26.7 s | 13.0–16.7 s | 10.0–13.0 s | 8.0–10.0 s | 6.7–8.0 s | 5.0–6.7 s | 4.0–5.0 s | 2.2–4.0 s |
|---|---|---|---|---|---|---|---|---|
| S | 0.72 / 1.03 | 0.55 / 0.98 | 0.48 / 0.91 | 0.59 / 0.82 | 0.80 / 0.84 | 0.90 / 0.92 | 0.94 / 0.91 | 1.04 / 0.87 |
| SSW-SW | 0.75 / 1.02 | 0.66 / 0.97 | 0.60 / 0.92 | 0.68 / 0.82 | 0.78 / 0.84 | 0.85 / 0.90 | 0.89 / 0.89 | 0.96 / 0.83 |
| WSW-W | 0.72 / 0.99 | 0.67 / 0.95 | 0.59 / 0.94 | 0.67 / 0.87 | 0.82 / 0.88 | 0.86 / 0.92 | 0.91 / 0.90 | 0.98 / 0.84 |
| W-WNW | 0.53 / 0.99 | 0.49 / 0.87 | 0.50 / 0.82 | 0.64 / 0.84 | 0.79 / 0.90 | 0.88 / 0.90 | 0.93 / 0.86 | 1.01 / 0.76 |
| all | 0.71 / 1.01 | 0.60 / 0.97 | 0.55 / 0.91 | 0.65 / 0.83 | 0.79 / 0.85 | 0.87 / 0.91 | 0.91 / 0.89 | 0.99 / 0.84 |

Share of the deep-water-equivalent energy by band (sector totals): MOP / chain-at-MOP / 46232:

| 46232 from | 16.7–26.7 s | 13.0–16.7 s | 10.0–13.0 s | 8.0–10.0 s | 6.7–8.0 s | 5.0–6.7 s | 4.0–5.0 s | 2.2–4.0 s |
|---|---|---|---|---|---|---|---|---|
| S | 10 / 11 / 8% | 17 / 26 / 22% | 10 / 28 / 29% | 7 / 9 / 12% | 10 / 6 / 7% | 21 / 11 / 11% | 12 / 5 / 6% | 13 / 4 / 5% |
| SSW-SW | 9 / 13 / 10% | 22 / 31 / 28% | 10 / 15 / 15% | 9 / 9 / 10% | 11 / 9 / 10% | 18 / 13 / 14% | 10 / 6 / 8% | 10 / 5 / 6% |
| WSW-W | 4 / 7 / 5% | 19 / 27 / 25% | 16 / 25 / 23% | 14 / 14 / 15% | 13 / 9 / 10% | 17 / 11 / 12% | 9 / 5 / 5% | 8 / 3 / 4% |
| W-WNW | 7 / 14 / 12% | 21 / 33 / 33% | 15 / 21 / 22% | 15 / 12 / 13% | 14 / 8 / 8% | 15 / 7 / 7% | 7 / 3 / 3% | 6 / 1 / 2% |
| all | 8 / 11 / 9% | 21 / 30 / 27% | 12 / 21 / 21% | 10 / 10 / 12% | 12 / 8 / 9% | 18 / 11 / 11% | 10 / 5 / 6% | 9 / 3 / 5% |

MOP's own weighted input coverage per band (`waveModelBinInputCoverage`, overlap-weighted mean of its bands), median [10th, 90th]:

| 46232 from | 16.7–26.7 s | 13.0–16.7 s | 10.0–13.0 s | 8.0–10.0 s | 6.7–8.0 s | 5.0–6.7 s | 4.0–5.0 s | 2.2–4.0 s |
|---|---|---|---|---|---|---|---|---|
| S | 1.00 [1.00, 1.00] | 1.00 [1.00, 1.00] | 1.00 [1.00, 1.00] | 1.00 [1.00, 1.00] | 1.00 [1.00, 1.00] | 1.00 [1.00, 1.00] | 1.00 [1.00, 1.00] | 1.00 [1.00, 1.00] |
| SSW-SW | 1.00 [1.00, 1.00] | 1.00 [1.00, 1.00] | 1.00 [1.00, 1.00] | 1.00 [1.00, 1.00] | 1.00 [1.00, 1.00] | 1.00 [1.00, 1.00] | 1.00 [1.00, 1.00] | 1.00 [1.00, 1.00] |
| WSW-W | 1.00 [1.00, 1.00] | 1.00 [1.00, 1.00] | 1.00 [1.00, 1.00] | 1.00 [1.00, 1.00] | 1.00 [1.00, 1.00] | 1.00 [1.00, 1.00] | 1.00 [1.00, 1.00] | 1.00 [1.00, 1.00] |
| W-WNW | 1.00 [1.00, 1.00] | 1.00 [1.00, 1.00] | 1.00 [1.00, 1.00] | 1.00 [1.00, 1.00] | 1.00 [1.00, 1.00] | 1.00 [1.00, 1.00] | 1.00 [1.00, 1.00] | 1.00 [1.00, 1.00] |
| all | 1.00 [1.00, 1.00] | 1.00 [1.00, 1.00] | 1.00 [1.00, 1.00] | 1.00 [1.00, 1.00] | 1.00 [1.00, 1.00] | 1.00 [1.00, 1.00] | 1.00 [1.00, 1.00] | 1.00 [1.00, 1.00] |

By MOP's input sources (`waveModelInputSource` as written, trailing padding dropped; CDIP station ids): whole-spectrum chain-at-MOP / MOP (MOP de-shoaled by band), median [10th, 90th] and hours, by 46232's sector:

| inputs | S | SSW-SW | WSW-W | W-WNW | all |
|---|---|---|---|---|---|
| `191p1-067p1-071p1:191p1-220p1-100p1-045p1` | 1.37 [1.19, 2.03] n 653 | 1.25 [1.06, 1.57] n 961 | 1.26 [1.07, 1.74] n 335 | 1.49 [1.17, 1.88] n 226 | 1.31 [1.10, 1.73] n 2175 |

MOP's a1/b1 convention, read off its own Dp at its peak band (median |difference|): from, clockwise from north: atan2(b1, a1) 0.0°; toward, clockwise from north: atan2(b1, a1) + 180 180.0°; toward, counter-clockwise from east: 270 - atan2(b1, a1) 103.3°; from, counter-clockwise from east: 90 - atan2(b1, a1) 76.7°. Taken: **from, clockwise from north: atan2(b1, a1)**.

Direction by band: chain-at-MOP's arrival heading minus MOP's mean direction from (°), median [10th, 90th]; MOP's mean direction in brackets:

| 46232 from | 16.7–26.7 s | 13.0–16.7 s | 10.0–13.0 s | 8.0–10.0 s | 6.7–8.0 s | 5.0–6.7 s | 4.0–5.0 s | 2.2–4.0 s |
|---|---|---|---|---|---|---|---|---|
| S | -21.09 [-26.81, -14.16] (265°) | -18.90 [-25.20, -13.42] (261°) | -25.26 [-37.09, -14.46] (264°) | -25.59 [-46.37, -8.40] (273°) | -6.97 [-28.12, 0.26] (280°) | -1.74 [-8.22, 3.75] (280°) | -0.59 [-6.65, 5.82] (278°) | -0.02 [-8.36, 7.40] (272°) |
| SSW-SW | -19.03 [-24.74, -9.35] (265°) | -15.29 [-20.94, -10.19] (262°) | -12.87 [-24.98, -2.10] (266°) | -6.57 [-18.80, 0.37] (277°) | -0.99 [-8.95, 2.99] (280°) | 0.59 [-5.10, 4.90] (279°) | 0.51 [-6.90, 6.17] (275°) | 0.66 [-7.58, 7.19] (271°) |
| WSW-W | -10.56 [-21.27, 2.70] (267°) | -8.35 [-16.14, 2.79] (266°) | -1.94 [-15.32, 5.06] (271°) | -2.61 [-11.50, 3.25] (277°) | 0.12 [-4.37, 4.16] (279°) | 0.98 [-3.58, 5.22] (278°) | 0.50 [-5.23, 6.14] (273°) | 0.44 [-6.14, 7.32] (269°) |
| W-WNW | 2.10 [-7.89, 6.06] (273°) | 2.82 [-4.91, 7.25] (274°) | 2.61 [-1.66, 6.16] (275°) | 1.69 [-2.52, 4.48] (278°) | 1.78 [-2.16, 4.82] (279°) | 1.60 [-2.50, 5.11] (277°) | 1.13 [-4.72, 6.04] (275°) | 0.75 [-4.59, 8.31] (273°) |
| all | -18.25 [-25.03, 0.42] (265°) | -14.95 [-22.12, 0.57] (263°) | -13.61 [-29.88, 2.73] (266°) | -7.70 [-33.85, 1.81] (277°) | -1.64 [-13.13, 3.36] (280°) | 0.21 [-5.54, 4.75] (279°) | 0.26 [-6.53, 6.06] (275°) | 0.44 [-7.54, 7.44] (271°) |

## coronado_north — shown, not read (§29)

MOP D0181: seabed 10.77 m below MSL there; starts: `break_5m` 5.05 m at 32.68472, -117.195172; `normal_mop` 10.79 m at 32.65737, -117.203203; `mop` 10.77 m at 32.673562, -117.191205. 2175 matched hours.

| 46232 from | n | MOP | break_5m eq | normal_mop eq | mop eq | mop hard |
|---|---:|---|---|---|---|---|
| S (150–205°) | 653 | 0.47 [0.36, 0.56] | 0.61 [0.48, 0.81] | 0.77 [0.67, 0.86] | 0.59 [0.50, 0.69] | 0.57 [0.47, 0.67] |
| SSW-SW (205–235°) | 961 | 0.56 [0.46, 0.68] | 0.70 [0.54, 0.92] | 0.84 [0.75, 0.96] | 0.69 [0.59, 0.82] | 0.67 [0.56, 0.80] |
| WSW-W (235–270°) | 335 | 0.56 [0.48, 0.66] | 0.57 [0.46, 0.75] | 0.88 [0.79, 0.96] | 0.73 [0.64, 0.84] | 0.70 [0.61, 0.81] |
| W-WNW (270–295°) | 226 | 0.52 [0.45, 0.61] | 0.44 [0.34, 0.53] | 0.90 [0.80, 0.97] | 0.72 [0.61, 0.83] | 0.68 [0.58, 0.77] |
| all (0–360°) | 2175 | 0.53 [0.43, 0.64] | 0.63 [0.46, 0.85] | 0.83 [0.72, 0.95] | 0.67 [0.55, 0.81] | 0.64 [0.52, 0.78] |

Ratios, hour by hour, median [10th, 90th] (MOP from 10.77 m in brackets):

| 46232 from | chain-at-MOP / MOP, eq | hard | 5 m / chain-at-MOP | 5 m / normal 10 m | normal 10 m / chain-at-MOP |
|---|---|---|---|---|---|
| S | 1.27 [1.09, 1.50] (1.25) | 1.22 [1.04, 1.44] | 1.04 [0.88, 1.30] | 0.80 [0.69, 0.97] | 1.30 [1.17, 1.44] |
| SSW-SW | 1.24 [1.08, 1.42] (1.22) | 1.20 [1.04, 1.37] | 1.00 [0.85, 1.23] | 0.83 [0.69, 0.99] | 1.21 [1.10, 1.36] |
| WSW-W | 1.29 [1.12, 1.52] (1.27) | 1.24 [1.07, 1.45] | 0.80 [0.65, 0.96] | 0.67 [0.54, 0.84] | 1.19 [1.08, 1.33] |
| W-WNW | 1.38 [1.17, 1.65] (1.36) | 1.29 [1.10, 1.56] | 0.61 [0.47, 0.71] | 0.49 [0.40, 0.57] | 1.24 [1.10, 1.40] |
| all | 1.26 [1.09, 1.49] (1.24) | 1.21 [1.05, 1.43] | 0.96 [0.67, 1.22] | 0.78 [0.54, 0.96] | 1.24 [1.11, 1.39] |

chain-at-MOP / MOP (eq) by 46232's swell peak period:

| 46232 from | 8–11 s | 11–14 s | 14–17 s | 17–26 s |
|---|---|---|---|---|
| S | 1.39 (n 39) | 1.30 (n 258) | 1.23 (n 315) | 1.26 (n 41) |
| SSW-SW | 1.29 (n 22) | 1.22 (n 190) | 1.24 (n 665) | 1.29 (n 84) |
| WSW-W | 1.24 (n 38) | 1.29 (n 139) | 1.29 (n 145) | 1.39 (n 13) |
| W-WNW | 1.30 (n 7) | 1.36 (n 77) | 1.40 (n 127) | 1.39 (n 15) |
| all | 1.33 (n 106) | 1.28 (n 664) | 1.25 (n 1252) | 1.29 (n 153) |

chain-at-MOP (eq, maximum entropy) with only its energy up to a frequency, over MOP's whole Hs; and with the whole spectrum read by Fourier instead:

| 46232 from | ≤ 0.1 Hz | ≤ 0.125 Hz | ≤ 0.15 Hz | ≤ 0.2 Hz | ≤ 0.25 Hz | ≤ 0.58 Hz | Fourier, all |
|---|---|---|---|---|---|---|---|
| S | 0.99 | 1.08 | 1.15 | 1.21 | 1.24 | 1.27 | 1.53 |
| SSW-SW | 0.99 | 1.06 | 1.13 | 1.19 | 1.22 | 1.24 | 1.42 |
| WSW-W | 1.04 | 1.15 | 1.21 | 1.26 | 1.27 | 1.29 | 1.46 |
| W-WNW | 1.20 | 1.29 | 1.33 | 1.36 | 1.37 | 1.38 | 1.69 |
| all | 1.01 | 1.10 | 1.16 | 1.22 | 1.24 | 1.26 | 1.48 |

Peak period over the same water (MOP's Tp; chain-at-MOP's densest bin), by 46232's overall peak:

| 46232 peak | n | MOP Tp | chain-at-MOP peak | hours MOP Tp < 9 s | hours chain peak < 9 s |
|---|---:|---|---|---:|---:|
| < 9 s | 53 | 16.67 [14.29, 18.18] | 15.38 [11.11, 18.18] | 2 | 4 |
| 9–12 s | 296 | 15.38 [12.30, 18.18] | 11.76 [10.53, 16.67] | 1 | 1 |
| ≥ 12 s | 1826 | 15.38 [13.33, 18.18] | 15.38 [12.50, 18.18] | 0 | 8 |

Share of chain-at-MOP's diffracted energy by kind of ray (sector totals), and chain-at-MOP / MOP with only the clear rays:

| 46232 from | clear | island fill | Point Loma fill | Baja fill | clear only / MOP |
|---|---|---|---|---|---|
| S | 91.1% | 4.6% | 4.1% | 0.1% | 1.21 [1.04, 1.43] |
| SSW-SW | 92.7% | 2.3% | 4.9% | 0.0% | 1.19 [1.04, 1.36] |
| WSW-W | 90.5% | 0.9% | 8.6% | 0.0% | 1.23 [1.06, 1.44] |
| W-WNW | 87.9% | 0.4% | 11.7% | 0.0% | 1.29 [1.10, 1.55] |
| all | 90.7% | 1.9% | 7.4% | 0.0% | 1.21 [1.05, 1.42] |

Where chain-at-MOP's energy comes from offshore (diffracted, sector totals, share by 10° of offshore heading; ≥ 3% shown) beside `break_5m`'s:

- **S** — MOP point: 170°s 7%, 180°s 4%, 190°s 3%, 210°s 9%, 220°s 20%, 230°s 14%, 240°s 8%, 250°s 8%, 260°s 7%, 270°s 7%, 280°s 4%; break 5 m: 170°s 6%, 180°s 8%, 190°s 11%, 200°s 17%, 210°s 25%, 220°s 14%, 230°s 9%, 240°s 5%
- **SSW-SW** — MOP point: 210°s 9%, 220°s 21%, 230°s 16%, 240°s 9%, 250°s 10%, 260°s 8%, 270°s 8%, 280°s 6%; break 5 m: 180°s 4%, 190°s 9%, 200°s 19%, 210°s 26%, 220°s 15%, 230°s 12%, 240°s 6%
- **WSW-W** — MOP point: 210°s 4%, 220°s 12%, 230°s 12%, 240°s 7%, 250°s 10%, 260°s 13%, 270°s 21%, 280°s 11%, 290°s 4%; break 5 m: 190°s 4%, 200°s 12%, 210°s 24%, 220°s 15%, 230°s 14%, 240°s 9%, 250°s 4%, 260°s 7%, 270°s 4%
- **W-WNW** — MOP point: 220°s 6%, 230°s 7%, 240°s 5%, 250°s 7%, 260°s 10%, 270°s 27%, 280°s 23%, 290°s 8%; break 5 m: 200°s 8%, 210°s 15%, 220°s 11%, 230°s 13%, 240°s 10%, 250°s 6%, 260°s 11%, 270°s 7%, 280°s 11%

Direction over the same water: MOP's peak direction (Dp) against the heading chain-at-MOP's energy arrives on in the 46232 bin nearest MOP's Tp:

| 46232 from | MOP Dp | chain-at-MOP | chain − MOP |
|---|---|---|---|
| S | 198.70 [195.75, 200.37] | 198.17 [192.85, 205.33] | -0.33 [-4.64, 6.02] |
| SSW-SW | 199.33 [195.76, 203.20] | 198.98 [194.56, 210.19] | 0.06 [-4.16, 7.97] |
| WSW-W | 202.01 [198.66, 213.43] | 205.56 [197.32, 224.19] | 2.91 [-2.70, 13.01] |
| W-WNW | 214.38 [209.87, 216.10] | 223.18 [214.73, 229.10] | 9.04 [1.69, 15.31] |
| all | 199.56 [196.28, 212.65] | 199.74 [194.64, 221.07] | 0.71 [-3.84, 10.70] |

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


### MOP's own spectrum, band by band

MOP's 20 bands, 0.0375–0.4500 Hz (edges from `waveFrequencyBounds`); read-back 4·sqrt(Σ E·df) / MOP's Hs median 1.0, worst 1.0 over 2565 hours. Common bands 0.0375–0.4500 Hz. 2175 matched hours with a complete MOP spectrum; a band-hour is compared when 46232 has ≥ 0.05 m in the band.

Whole spectrum, MOP de-shoaled band by band at each band's frequency (10.77 m in brackets) against at its Tp as above; MOP's spectrum summed over its own Hs at the point:

| 46232 from | n | MOP, by band | MOP, at Tp | chain-at-MOP / MOP, by band | at Tp | spectrum Hs / MOP Hs |
|---|---:|---|---|---|---|---|
| S | 653 | 0.52 [0.39, 0.60] | 0.47 [0.36, 0.56] | 1.15 [1.01, 1.36] (1.14) | 1.27 | 1.00 [1.00, 1.00] |
| SSW-SW | 961 | 0.60 [0.51, 0.71] | 0.56 [0.46, 0.68] | 1.15 [1.01, 1.31] (1.14) | 1.24 | 1.00 [1.00, 1.00] |
| WSW-W | 335 | 0.61 [0.53, 0.71] | 0.56 [0.48, 0.66] | 1.19 [1.02, 1.41] (1.18) | 1.29 | 1.00 [1.00, 1.00] |
| W-WNW | 226 | 0.56 [0.50, 0.65] | 0.52 [0.45, 0.61] | 1.27 [1.08, 1.55] (1.25) | 1.38 | 1.00 [1.00, 1.00] |
| all | 2175 | 0.57 [0.47, 0.68] | 0.53 [0.43, 0.64] | 1.16 [1.02, 1.37] (1.15) | 1.26 | 1.00 [1.00, 1.00] |

chain-at-MOP / MOP in each band, as heights (√ of the energy ratio, both deep-water-equivalent, before friction), median [10th, 90th] and hours:

| 46232 from | 16.7–26.7 s | 13.0–16.7 s | 10.0–13.0 s | 8.0–10.0 s | 6.7–8.0 s | 5.0–6.7 s | 4.0–5.0 s | 2.2–4.0 s |
|---|---|---|---|---|---|---|---|---|
| S | 1.03 [0.81, 1.33] n 653 | 1.16 [0.92, 1.45] n 653 | 1.22 [0.98, 1.63] n 653 | 1.13 [0.90, 1.62] n 652 | 1.13 [0.91, 1.40] n 621 | 1.14 [0.95, 1.42] n 628 | 1.00 [0.80, 1.26] n 616 | 0.86 [0.59, 1.15] n 569 |
| SSW-SW | 1.05 [0.81, 1.35] n 961 | 1.15 [0.92, 1.41] n 961 | 1.18 [0.97, 1.47] n 961 | 1.10 [0.88, 1.39] n 961 | 1.15 [0.90, 1.44] n 951 | 1.16 [0.93, 1.39] n 954 | 1.06 [0.83, 1.32] n 927 | 0.90 [0.54, 1.17] n 901 |
| WSW-W | 1.08 [0.81, 1.41] n 329 | 1.20 [0.93, 1.61] n 335 | 1.26 [1.00, 1.58] n 335 | 1.11 [0.86, 1.47] n 335 | 1.08 [0.87, 1.34] n 335 | 1.13 [0.95, 1.33] n 335 | 1.03 [0.78, 1.28] n 328 | 0.87 [0.53, 1.16] n 307 |
| W-WNW | 1.17 [0.83, 1.63] n 226 | 1.37 [1.02, 1.81] n 226 | 1.27 [0.98, 1.66] n 226 | 1.09 [0.92, 1.39] n 226 | 1.02 [0.88, 1.27] n 226 | 1.07 [0.84, 1.27] n 223 | 0.98 [0.69, 1.17] n 196 | 0.76 [0.42, 0.96] n 159 |
| all | 1.06 [0.81, 1.39] n 2169 | 1.17 [0.93, 1.50] n 2175 | 1.21 [0.98, 1.56] n 2175 | 1.11 [0.88, 1.46] n 2174 | 1.12 [0.89, 1.40] n 2133 | 1.13 [0.93, 1.38] n 2140 | 1.03 [0.80, 1.28] n 2067 | 0.87 [0.54, 1.16] n 1936 |

Each over 46232 in the same band, as heights (√ energy ratio), median: MOP / chain-at-MOP. Where MOP is lower than the chain, this says whether MOP takes less of the buoy's band or the chain takes more:

| 46232 from | 16.7–26.7 s | 13.0–16.7 s | 10.0–13.0 s | 8.0–10.0 s | 6.7–8.0 s | 5.0–6.7 s | 4.0–5.0 s | 2.2–4.0 s |
|---|---|---|---|---|---|---|---|---|
| S | 0.77 / 0.81 | 0.58 / 0.66 | 0.50 / 0.59 | 0.53 / 0.60 | 0.54 / 0.61 | 0.47 / 0.54 | 0.43 / 0.42 | 0.56 / 0.48 |
| SSW-SW | 0.81 / 0.87 | 0.68 / 0.80 | 0.61 / 0.73 | 0.58 / 0.63 | 0.54 / 0.62 | 0.47 / 0.55 | 0.43 / 0.44 | 0.55 / 0.48 |
| WSW-W | 0.87 / 0.97 | 0.73 / 0.90 | 0.59 / 0.76 | 0.59 / 0.64 | 0.59 / 0.63 | 0.50 / 0.56 | 0.48 / 0.47 | 0.58 / 0.50 |
| W-WNW | 0.74 / 0.89 | 0.59 / 0.83 | 0.49 / 0.64 | 0.56 / 0.62 | 0.61 / 0.63 | 0.54 / 0.58 | 0.46 / 0.45 | 0.54 / 0.42 |
| all | 0.80 / 0.88 | 0.64 / 0.78 | 0.56 / 0.69 | 0.57 / 0.62 | 0.56 / 0.62 | 0.48 / 0.55 | 0.44 / 0.44 | 0.56 / 0.48 |

Share of the deep-water-equivalent energy by band (sector totals): MOP / chain-at-MOP / 46232:

| 46232 from | 16.7–26.7 s | 13.0–16.7 s | 10.0–13.0 s | 8.0–10.0 s | 6.7–8.0 s | 5.0–6.7 s | 4.0–5.0 s | 2.2–4.0 s |
|---|---|---|---|---|---|---|---|---|
| S | 17 / 14 / 8% | 29 / 29 / 22% | 17 / 21 / 29% | 9 / 11 / 12% | 8 / 8 / 7% | 10 / 10 / 11% | 4 / 3 / 6% | 6 / 3 / 5% |
| SSW-SW | 15 / 14 / 10% | 36 / 37 / 28% | 15 / 17 / 15% | 9 / 8 / 10% | 7 / 8 / 10% | 8 / 9 / 14% | 4 / 3 / 8% | 5 / 3 / 6% |
| WSW-W | 10 / 9 / 5% | 32 / 36 / 25% | 21 / 25 / 23% | 14 / 12 / 15% | 9 / 7 / 10% | 8 / 7 / 12% | 3 / 2 / 5% | 4 / 2 / 4% |
| W-WNW | 18 / 16 / 12% | 35 / 44 / 33% | 17 / 18 / 22% | 12 / 10 / 13% | 8 / 6 / 8% | 6 / 4 / 7% | 2 / 1 / 3% | 2 / 1 / 2% |
| all | 15 / 14 / 9% | 34 / 37 / 27% | 17 / 20 / 21% | 11 / 10 / 12% | 8 / 7 / 9% | 8 / 7 / 11% | 3 / 3 / 6% | 4 / 2 / 5% |

MOP's own weighted input coverage per band (`waveModelBinInputCoverage`, overlap-weighted mean of its bands), median [10th, 90th]:

| 46232 from | 16.7–26.7 s | 13.0–16.7 s | 10.0–13.0 s | 8.0–10.0 s | 6.7–8.0 s | 5.0–6.7 s | 4.0–5.0 s | 2.2–4.0 s |
|---|---|---|---|---|---|---|---|---|
| S | 1.00 [1.00, 1.00] | 1.00 [1.00, 1.00] | 1.00 [1.00, 1.00] | 1.00 [1.00, 1.00] | 1.00 [1.00, 1.00] | 1.00 [1.00, 1.00] | 1.00 [1.00, 1.00] | 1.00 [1.00, 1.00] |
| SSW-SW | 1.00 [1.00, 1.00] | 1.00 [1.00, 1.00] | 1.00 [1.00, 1.00] | 1.00 [1.00, 1.00] | 1.00 [1.00, 1.00] | 1.00 [1.00, 1.00] | 1.00 [1.00, 1.00] | 1.00 [1.00, 1.00] |
| WSW-W | 1.00 [1.00, 1.00] | 1.00 [1.00, 1.00] | 1.00 [1.00, 1.00] | 1.00 [1.00, 1.00] | 1.00 [1.00, 1.00] | 1.00 [1.00, 1.00] | 1.00 [1.00, 1.00] | 1.00 [1.00, 1.00] |
| W-WNW | 1.00 [1.00, 1.00] | 1.00 [1.00, 1.00] | 1.00 [1.00, 1.00] | 1.00 [1.00, 1.00] | 1.00 [1.00, 1.00] | 1.00 [1.00, 1.00] | 1.00 [1.00, 1.00] | 1.00 [1.00, 1.00] |
| all | 1.00 [1.00, 1.00] | 1.00 [1.00, 1.00] | 1.00 [1.00, 1.00] | 1.00 [1.00, 1.00] | 1.00 [1.00, 1.00] | 1.00 [1.00, 1.00] | 1.00 [1.00, 1.00] | 1.00 [1.00, 1.00] |

By MOP's input sources (`waveModelInputSource` as written, trailing padding dropped; CDIP station ids): whole-spectrum chain-at-MOP / MOP (MOP de-shoaled by band), median [10th, 90th] and hours, by 46232's sector:

| inputs | S | SSW-SW | WSW-W | W-WNW | all |
|---|---|---|---|---|---|
| `191p1-067p1-071p1:191p1-220p1-100p1-045p1` | 1.15 [1.01, 1.36] n 653 | 1.15 [1.01, 1.31] n 961 | 1.19 [1.02, 1.41] n 335 | 1.27 [1.08, 1.55] n 226 | 1.16 [1.02, 1.37] n 2175 |

MOP's a1/b1 convention, read off its own Dp at its peak band (median |difference|): from, clockwise from north: atan2(b1, a1) 0.0°; toward, clockwise from north: atan2(b1, a1) + 180 180.0°; toward, counter-clockwise from east: 270 - atan2(b1, a1) 128.9°; from, counter-clockwise from east: 90 - atan2(b1, a1) 51.1°. Taken: **from, clockwise from north: atan2(b1, a1)**.

Direction by band: chain-at-MOP's arrival heading minus MOP's mean direction from (°), median [10th, 90th]; MOP's mean direction in brackets:

| 46232 from | 16.7–26.7 s | 13.0–16.7 s | 10.0–13.0 s | 8.0–10.0 s | 6.7–8.0 s | 5.0–6.7 s | 4.0–5.0 s | 2.2–4.0 s |
|---|---|---|---|---|---|---|---|---|
| S | 0.99 [-2.21, 5.69] (200°) | -1.35 [-6.37, 2.49] (199°) | -2.65 [-9.97, 3.22] (203°) | -5.83 [-18.12, 2.94] (214°) | 5.44 [-3.80, 10.31] (221°) | 5.69 [-0.29, 10.20] (229°) | 2.88 [-1.35, 5.80] (235°) | 4.47 [-0.42, 7.66] (234°) |
| SSW-SW | 1.08 [-2.01, 6.64] (200°) | 0.11 [-3.46, 4.24] (199°) | 1.44 [-4.05, 7.85] (204°) | 2.92 [-4.50, 9.40] (219°) | 7.73 [2.41, 11.79] (224°) | 6.42 [1.77, 10.84] (229°) | 2.94 [-1.16, 6.02] (234°) | 3.91 [-1.43, 7.43] (233°) |
| WSW-W | 3.62 [-1.89, 11.43] (201°) | 3.14 [-1.39, 10.44] (203°) | 5.77 [-0.19, 11.14] (210°) | 4.37 [-1.39, 10.41] (220°) | 7.14 [2.70, 11.08] (225°) | 5.86 [1.70, 9.50] (229°) | 1.86 [-2.48, 5.04] (233°) | 3.34 [-2.64, 6.81] (232°) |
| W-WNW | 9.33 [4.11, 16.45] (212°) | 10.22 [4.80, 15.07] (213°) | 7.27 [3.47, 11.92] (215°) | 7.52 [2.41, 11.47] (221°) | 7.59 [4.02, 10.13] (226°) | 5.93 [1.59, 9.44] (229°) | 2.19 [-2.58, 5.60] (232°) | 3.25 [-2.88, 7.04] (232°) |
| all | 1.67 [-1.96, 9.41] (200°) | 0.42 [-3.94, 9.12] (200°) | 1.36 [-6.06, 9.08] (205°) | 1.89 [-9.83, 9.31] (218°) | 7.08 [0.73, 11.28] (224°) | 6.10 [1.34, 10.21] (229°) | 2.71 [-1.64, 5.73] (234°) | 3.96 [-1.51, 7.40] (233°) |

## coronado_center

MOP D0179: seabed 10.98 m below MSL there; starts: `break_5m` 5.03 m at 32.680946, -117.186314; `normal_mop` 10.99 m at 32.655488, -117.20646; `mop` 11.0 m at 32.673935, -117.188472. 2175 matched hours.

| 46232 from | n | MOP | break_5m eq | normal_mop eq | mop eq | mop hard |
|---|---:|---|---|---|---|---|
| S (150–205°) | 653 | 0.43 [0.32, 0.49] | 0.50 [0.43, 0.59] | 0.84 [0.74, 0.95] | 0.54 [0.45, 0.61] | 0.52 [0.44, 0.60] |
| SSW-SW (205–235°) | 961 | 0.51 [0.42, 0.61] | 0.59 [0.49, 0.71] | 0.89 [0.79, 0.99] | 0.62 [0.54, 0.73] | 0.61 [0.53, 0.72] |
| WSW-W (235–270°) | 335 | 0.54 [0.45, 0.65] | 0.66 [0.56, 0.78] | 0.89 [0.81, 0.97] | 0.70 [0.60, 0.83] | 0.68 [0.58, 0.82] |
| W-WNW (270–295°) | 226 | 0.52 [0.45, 0.63] | 0.71 [0.57, 0.82] | 0.95 [0.86, 1.06] | 0.73 [0.62, 0.86] | 0.72 [0.60, 0.85] |
| all (0–360°) | 2175 | 0.49 [0.39, 0.60] | 0.58 [0.47, 0.74] | 0.88 [0.78, 0.99] | 0.61 [0.50, 0.77] | 0.60 [0.49, 0.75] |

Ratios, hour by hour, median [10th, 90th] (MOP from 10.77 m in brackets):

| 46232 from | chain-at-MOP / MOP, eq | hard | 5 m / chain-at-MOP | 5 m / normal 10 m | normal 10 m / chain-at-MOP |
|---|---|---|---|---|---|
| S | 1.29 [1.10, 1.53] (1.27) | 1.25 [1.07, 1.48] | 0.94 [0.88, 1.03] | 0.61 [0.52, 0.69] | 1.54 [1.39, 1.85] |
| SSW-SW | 1.24 [1.09, 1.44] (1.23) | 1.21 [1.06, 1.40] | 0.95 [0.88, 1.01] | 0.67 [0.58, 0.78] | 1.40 [1.22, 1.63] |
| WSW-W | 1.29 [1.13, 1.53] (1.28) | 1.27 [1.11, 1.50] | 0.94 [0.88, 0.99] | 0.74 [0.64, 0.85] | 1.27 [1.12, 1.46] |
| W-WNW | 1.38 [1.17, 1.69] (1.36) | 1.36 [1.15, 1.68] | 0.95 [0.86, 1.04] | 0.73 [0.63, 0.85] | 1.31 [1.11, 1.48] |
| all | 1.27 [1.10, 1.51] (1.25) | 1.24 [1.07, 1.47] | 0.94 [0.88, 1.01] | 0.66 [0.56, 0.80] | 1.42 [1.20, 1.68] |

chain-at-MOP / MOP (eq) by 46232's swell peak period:

| 46232 from | 8–11 s | 11–14 s | 14–17 s | 17–26 s |
|---|---|---|---|---|
| S | 1.37 (n 39) | 1.31 (n 258) | 1.25 (n 315) | 1.30 (n 41) |
| SSW-SW | 1.31 (n 22) | 1.20 (n 190) | 1.24 (n 665) | 1.37 (n 84) |
| WSW-W | 1.24 (n 38) | 1.31 (n 139) | 1.29 (n 145) | 1.38 (n 13) |
| W-WNW | 1.35 (n 7) | 1.38 (n 77) | 1.40 (n 127) | 1.29 (n 15) |
| all | 1.34 (n 106) | 1.29 (n 664) | 1.26 (n 1252) | 1.35 (n 153) |

chain-at-MOP (eq, maximum entropy) with only its energy up to a frequency, over MOP's whole Hs; and with the whole spectrum read by Fourier instead:

| 46232 from | ≤ 0.1 Hz | ≤ 0.125 Hz | ≤ 0.15 Hz | ≤ 0.2 Hz | ≤ 0.25 Hz | ≤ 0.58 Hz | Fourier, all |
|---|---|---|---|---|---|---|---|
| S | 0.97 | 1.07 | 1.15 | 1.21 | 1.25 | 1.29 | 1.57 |
| SSW-SW | 0.97 | 1.04 | 1.12 | 1.18 | 1.21 | 1.24 | 1.44 |
| WSW-W | 1.05 | 1.15 | 1.20 | 1.25 | 1.27 | 1.29 | 1.47 |
| W-WNW | 1.24 | 1.30 | 1.35 | 1.37 | 1.38 | 1.38 | 1.62 |
| all | 1.01 | 1.09 | 1.16 | 1.22 | 1.24 | 1.27 | 1.50 |

Peak period over the same water (MOP's Tp; chain-at-MOP's densest bin), by 46232's overall peak:

| 46232 peak | n | MOP Tp | chain-at-MOP peak | hours MOP Tp < 9 s | hours chain peak < 9 s |
|---|---:|---|---|---:|---:|
| < 9 s | 53 | 16.67 [14.29, 18.18] | 15.38 [9.90, 18.18] | 0 | 5 |
| 9–12 s | 296 | 14.29 [11.11, 18.18] | 11.76 [10.53, 16.67] | 0 | 1 |
| ≥ 12 s | 1826 | 15.38 [13.33, 18.18] | 14.29 [12.50, 18.18] | 0 | 16 |

Share of chain-at-MOP's diffracted energy by kind of ray (sector totals), and chain-at-MOP / MOP with only the clear rays:

| 46232 from | clear | island fill | Point Loma fill | Baja fill | clear only / MOP |
|---|---|---|---|---|---|
| S | 93.1% | 3.3% | 3.4% | 0.1% | 1.24 [1.06, 1.46] |
| SSW-SW | 94.3% | 2.0% | 3.6% | 0.1% | 1.20 [1.05, 1.39] |
| WSW-W | 96.0% | 0.6% | 3.3% | 0.0% | 1.27 [1.10, 1.49] |
| W-WNW | 96.2% | 0.3% | 3.4% | 0.0% | 1.36 [1.14, 1.67] |
| all | 95.1% | 1.4% | 3.5% | 0.1% | 1.23 [1.07, 1.47] |

Where chain-at-MOP's energy comes from offshore (diffracted, sector totals, share by 10° of offshore heading; ≥ 3% shown) beside `break_5m`'s:

- **S** — MOP point: 170°s 4%, 180°s 6%, 190°s 4%, 200°s 4%, 210°s 6%, 220°s 11%, 230°s 18%, 240°s 12%, 250°s 9%, 260°s 7%, 270°s 8%, 280°s 4%; break 5 m: 160°s 4%, 170°s 9%, 180°s 5%, 210°s 8%, 220°s 15%, 230°s 16%, 240°s 11%, 250°s 9%, 260°s 6%, 270°s 7%
- **SSW-SW** — MOP point: 200°s 4%, 210°s 7%, 220°s 11%, 230°s 20%, 240°s 13%, 250°s 10%, 260°s 9%, 270°s 11%, 280°s 5%; break 5 m: 210°s 8%, 220°s 16%, 230°s 18%, 240°s 13%, 250°s 11%, 260°s 8%, 270°s 10%, 280°s 4%
- **WSW-W** — MOP point: 220°s 5%, 230°s 13%, 240°s 10%, 250°s 9%, 260°s 13%, 270°s 25%, 280°s 13%; break 5 m: 210°s 3%, 220°s 8%, 230°s 12%, 240°s 10%, 250°s 11%, 260°s 13%, 270°s 24%, 280°s 12%
- **W-WNW** — MOP point: 230°s 6%, 240°s 6%, 250°s 6%, 260°s 9%, 270°s 30%, 280°s 28%, 290°s 5%, 300°s 3%; break 5 m: 220°s 3%, 230°s 6%, 240°s 6%, 250°s 7%, 260°s 10%, 270°s 28%, 280°s 30%, 290°s 5%

Direction over the same water: MOP's peak direction (Dp) against the heading chain-at-MOP's energy arrives on in the 46232 bin nearest MOP's Tp:

| 46232 from | MOP Dp | chain-at-MOP | chain − MOP |
|---|---|---|---|
| S | 201.32 [198.22, 204.20] | 200.85 [193.73, 207.51] | -0.48 [-7.74, 6.84] |
| SSW-SW | 202.11 [198.48, 207.07] | 202.27 [196.74, 210.49] | -0.24 [-5.83, 6.58] |
| WSW-W | 205.81 [201.86, 218.36] | 208.72 [199.57, 220.46] | 1.34 [-3.63, 7.10] |
| W-WNW | 216.99 [212.42, 220.10] | 219.61 [214.33, 222.64] | 2.24 [-2.24, 7.07] |
| all | 202.34 [198.97, 215.52] | 203.43 [196.31, 218.86] | 0.31 [-5.84, 6.85] |

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


### MOP's own spectrum, band by band

MOP's 20 bands, 0.0375–0.4500 Hz (edges from `waveFrequencyBounds`); read-back 4·sqrt(Σ E·df) / MOP's Hs median 1.0, worst 1.0 over 2565 hours. Common bands 0.0375–0.4500 Hz. 2175 matched hours with a complete MOP spectrum; a band-hour is compared when 46232 has ≥ 0.05 m in the band.

Whole spectrum, MOP de-shoaled band by band at each band's frequency (10.77 m in brackets) against at its Tp as above; MOP's spectrum summed over its own Hs at the point:

| 46232 from | n | MOP, by band | MOP, at Tp | chain-at-MOP / MOP, by band | at Tp | spectrum Hs / MOP Hs |
|---|---:|---|---|---|---|---|
| S | 653 | 0.47 [0.36, 0.53] | 0.43 [0.32, 0.49] | 1.16 [1.02, 1.35] (1.15) | 1.29 | 1.00 [1.00, 1.00] |
| SSW-SW | 961 | 0.54 [0.47, 0.64] | 0.51 [0.42, 0.61] | 1.15 [1.03, 1.31] (1.14) | 1.24 | 1.00 [1.00, 1.00] |
| WSW-W | 335 | 0.58 [0.49, 0.68] | 0.54 [0.45, 0.65] | 1.20 [1.04, 1.42] (1.19) | 1.29 | 1.00 [1.00, 1.00] |
| W-WNW | 226 | 0.55 [0.49, 0.66] | 0.52 [0.45, 0.63] | 1.30 [1.08, 1.59] (1.28) | 1.38 | 1.00 [1.00, 1.00] |
| all | 2175 | 0.52 [0.43, 0.63] | 0.49 [0.39, 0.60] | 1.17 [1.03, 1.38] (1.16) | 1.27 | 1.00 [1.00, 1.00] |

chain-at-MOP / MOP in each band, as heights (√ of the energy ratio, both deep-water-equivalent, before friction), median [10th, 90th] and hours:

| 46232 from | 16.7–26.7 s | 13.0–16.7 s | 10.0–13.0 s | 8.0–10.0 s | 6.7–8.0 s | 5.0–6.7 s | 4.0–5.0 s | 2.2–4.0 s |
|---|---|---|---|---|---|---|---|---|
| S | 1.11 [0.85, 1.42] n 653 | 1.14 [0.93, 1.45] n 653 | 1.18 [0.95, 1.57] n 653 | 1.18 [0.93, 1.58] n 652 | 1.15 [0.95, 1.44] n 621 | 1.13 [0.94, 1.41] n 628 | 1.01 [0.79, 1.28] n 616 | 0.85 [0.57, 1.15] n 569 |
| SSW-SW | 1.11 [0.86, 1.43] n 961 | 1.14 [0.92, 1.39] n 961 | 1.15 [0.94, 1.41] n 961 | 1.17 [0.95, 1.45] n 961 | 1.17 [0.93, 1.43] n 951 | 1.15 [0.92, 1.36] n 954 | 1.06 [0.81, 1.35] n 927 | 0.90 [0.53, 1.16] n 901 |
| WSW-W | 1.12 [0.85, 1.45] n 329 | 1.20 [0.95, 1.55] n 335 | 1.24 [0.96, 1.66] n 335 | 1.16 [0.93, 1.51] n 335 | 1.11 [0.91, 1.40] n 335 | 1.12 [0.94, 1.31] n 335 | 1.03 [0.78, 1.28] n 328 | 0.86 [0.53, 1.14] n 307 |
| W-WNW | 1.30 [0.98, 1.70] n 226 | 1.39 [0.94, 1.81] n 226 | 1.29 [0.98, 1.62] n 226 | 1.10 [0.89, 1.38] n 226 | 1.08 [0.90, 1.32] n 226 | 1.06 [0.85, 1.24] n 223 | 0.98 [0.68, 1.19] n 196 | 0.74 [0.42, 0.96] n 159 |
| all | 1.13 [0.86, 1.47] n 2169 | 1.16 [0.93, 1.50] n 2175 | 1.18 [0.95, 1.54] n 2175 | 1.16 [0.93, 1.48] n 2174 | 1.14 [0.93, 1.43] n 2133 | 1.13 [0.92, 1.36] n 2140 | 1.03 [0.78, 1.30] n 2067 | 0.86 [0.53, 1.15] n 1936 |

Each over 46232 in the same band, as heights (√ energy ratio), median: MOP / chain-at-MOP. Where MOP is lower than the chain, this says whether MOP takes less of the buoy's band or the chain takes more:

| 46232 from | 16.7–26.7 s | 13.0–16.7 s | 10.0–13.0 s | 8.0–10.0 s | 6.7–8.0 s | 5.0–6.7 s | 4.0–5.0 s | 2.2–4.0 s |
|---|---|---|---|---|---|---|---|---|
| S | 0.62 / 0.71 | 0.49 / 0.56 | 0.49 / 0.55 | 0.47 / 0.55 | 0.50 / 0.57 | 0.46 / 0.52 | 0.43 / 0.42 | 0.56 / 0.48 |
| SSW-SW | 0.67 / 0.76 | 0.58 / 0.68 | 0.60 / 0.69 | 0.50 / 0.58 | 0.49 / 0.57 | 0.46 / 0.53 | 0.43 / 0.45 | 0.55 / 0.47 |
| WSW-W | 0.78 / 0.88 | 0.69 / 0.84 | 0.61 / 0.77 | 0.52 / 0.60 | 0.52 / 0.58 | 0.49 / 0.55 | 0.48 / 0.48 | 0.58 / 0.49 |
| W-WNW | 0.66 / 0.86 | 0.60 / 0.85 | 0.55 / 0.72 | 0.51 / 0.56 | 0.53 / 0.58 | 0.52 / 0.55 | 0.46 / 0.45 | 0.54 / 0.42 |
| all | 0.67 / 0.78 | 0.57 / 0.68 | 0.56 / 0.67 | 0.50 / 0.58 | 0.50 / 0.57 | 0.47 / 0.53 | 0.44 / 0.44 | 0.56 / 0.47 |

Share of the deep-water-equivalent energy by band (sector totals): MOP / chain-at-MOP / 46232:

| 46232 from | 16.7–26.7 s | 13.0–16.7 s | 10.0–13.0 s | 8.0–10.0 s | 6.7–8.0 s | 5.0–6.7 s | 4.0–5.0 s | 2.2–4.0 s |
|---|---|---|---|---|---|---|---|---|
| S | 12 / 13 / 8% | 27 / 26 / 22% | 20 / 23 / 29% | 9 / 10 / 12% | 8 / 8 / 7% | 12 / 11 / 11% | 5 / 4 / 6% | 7 / 4 / 5% |
| SSW-SW | 12 / 13 / 10% | 33 / 33 / 28% | 18 / 19 / 15% | 8 / 9 / 10% | 7 / 8 / 10% | 10 / 10 / 14% | 5 / 4 / 8% | 6 / 4 / 6% |
| WSW-W | 9 / 8 / 5% | 32 / 35 / 25% | 25 / 29 / 23% | 12 / 11 / 15% | 8 / 6 / 10% | 8 / 7 / 12% | 3 / 2 / 5% | 4 / 2 / 4% |
| W-WNW | 14 / 16 / 12% | 37 / 43 / 33% | 21 / 21 / 22% | 10 / 8 / 13% | 7 / 5 / 8% | 6 / 4 / 7% | 2 / 1 / 3% | 2 / 1 / 2% |
| all | 12 / 13 / 9% | 33 / 36 / 27% | 21 / 22 / 21% | 10 / 9 / 12% | 7 / 7 / 9% | 9 / 8 / 11% | 4 / 3 / 6% | 5 / 3 / 5% |

MOP's own weighted input coverage per band (`waveModelBinInputCoverage`, overlap-weighted mean of its bands), median [10th, 90th]:

| 46232 from | 16.7–26.7 s | 13.0–16.7 s | 10.0–13.0 s | 8.0–10.0 s | 6.7–8.0 s | 5.0–6.7 s | 4.0–5.0 s | 2.2–4.0 s |
|---|---|---|---|---|---|---|---|---|
| S | 1.00 [1.00, 1.00] | 1.00 [1.00, 1.00] | 1.00 [1.00, 1.00] | 1.00 [1.00, 1.00] | 1.00 [1.00, 1.00] | 1.00 [1.00, 1.00] | 1.00 [1.00, 1.00] | 1.00 [1.00, 1.00] |
| SSW-SW | 1.00 [1.00, 1.00] | 1.00 [1.00, 1.00] | 1.00 [1.00, 1.00] | 1.00 [1.00, 1.00] | 1.00 [1.00, 1.00] | 1.00 [1.00, 1.00] | 1.00 [1.00, 1.00] | 1.00 [1.00, 1.00] |
| WSW-W | 1.00 [1.00, 1.00] | 1.00 [1.00, 1.00] | 1.00 [1.00, 1.00] | 1.00 [1.00, 1.00] | 1.00 [1.00, 1.00] | 1.00 [1.00, 1.00] | 1.00 [1.00, 1.00] | 1.00 [1.00, 1.00] |
| W-WNW | 1.00 [1.00, 1.00] | 1.00 [1.00, 1.00] | 1.00 [1.00, 1.00] | 1.00 [1.00, 1.00] | 1.00 [1.00, 1.00] | 1.00 [1.00, 1.00] | 1.00 [1.00, 1.00] | 1.00 [1.00, 1.00] |
| all | 1.00 [1.00, 1.00] | 1.00 [1.00, 1.00] | 1.00 [1.00, 1.00] | 1.00 [1.00, 1.00] | 1.00 [1.00, 1.00] | 1.00 [1.00, 1.00] | 1.00 [1.00, 1.00] | 1.00 [1.00, 1.00] |

By MOP's input sources (`waveModelInputSource` as written, trailing padding dropped; CDIP station ids): whole-spectrum chain-at-MOP / MOP (MOP de-shoaled by band), median [10th, 90th] and hours, by 46232's sector:

| inputs | S | SSW-SW | WSW-W | W-WNW | all |
|---|---|---|---|---|---|
| `191p1-067p1-071p1:191p1-220p1-100p1-045p1` | 1.16 [1.02, 1.35] n 653 | 1.15 [1.03, 1.31] n 961 | 1.20 [1.04, 1.42] n 335 | 1.30 [1.08, 1.59] n 226 | 1.17 [1.03, 1.38] n 2175 |

MOP's a1/b1 convention, read off its own Dp at its peak band (median |difference|): from, clockwise from north: atan2(b1, a1) 0.0°; toward, clockwise from north: atan2(b1, a1) + 180 180.0°; toward, counter-clockwise from east: 270 - atan2(b1, a1) 134.5°; from, counter-clockwise from east: 90 - atan2(b1, a1) 45.5°. Taken: **from, clockwise from north: atan2(b1, a1)**.

Direction by band: chain-at-MOP's arrival heading minus MOP's mean direction from (°), median [10th, 90th]; MOP's mean direction in brackets:

| 46232 from | 16.7–26.7 s | 13.0–16.7 s | 10.0–13.0 s | 8.0–10.0 s | 6.7–8.0 s | 5.0–6.7 s | 4.0–5.0 s | 2.2–4.0 s |
|---|---|---|---|---|---|---|---|---|
| S | 0.85 [-2.90, 4.75] (202°) | -2.17 [-6.83, 1.82] (202°) | -5.34 [-11.43, -0.04] (206°) | -4.87 [-13.52, 2.34] (213°) | 2.97 [-6.40, 8.63] (221°) | 4.51 [-1.74, 7.85] (230°) | 1.51 [-2.72, 4.18] (236°) | 3.36 [-1.53, 6.32] (235°) |
| SSW-SW | 1.57 [-2.31, 5.47] (202°) | -0.85 [-4.24, 3.32] (202°) | -1.51 [-6.48, 4.16] (208°) | 2.14 [-3.94, 7.16] (217°) | 6.22 [0.53, 10.83] (223°) | 5.04 [0.51, 8.10] (230°) | 1.76 [-2.43, 4.75] (235°) | 2.79 [-2.38, 6.12] (234°) |
| WSW-W | 3.19 [-0.97, 7.79] (203°) | 1.02 [-2.87, 6.32] (205°) | 2.42 [-3.53, 7.09] (213°) | 2.83 [-1.53, 8.18] (219°) | 5.81 [1.91, 10.82] (224°) | 4.84 [1.19, 7.89] (230°) | 0.81 [-3.58, 3.92] (234°) | 2.39 [-3.40, 5.67] (233°) |
| W-WNW | 6.01 [2.72, 9.96] (210°) | 3.09 [-0.40, 6.56] (217°) | 3.84 [0.44, 6.94] (218°) | 5.30 [0.69, 8.92] (220°) | 6.51 [2.79, 9.80] (225°) | 4.77 [0.73, 7.65] (230°) | 1.25 [-4.35, 4.22] (233°) | 2.35 [-4.21, 5.67] (233°) |
| all | 1.94 [-2.14, 6.97] (202°) | -0.64 [-4.93, 4.22] (203°) | -1.57 [-8.18, 5.02] (208°) | 1.03 [-7.82, 6.99] (217°) | 5.42 [-0.99, 10.23] (223°) | 4.82 [0.16, 7.93] (230°) | 1.44 [-2.86, 4.43] (235°) | 2.86 [-2.59, 6.12] (234°) |

## coronado_south

MOP D0168: seabed 10.95 m below MSL there; starts: `break_5m` 5.03 m at 32.67354, -117.175819; `normal_mop` 10.96 m at 32.669484, -117.17996; `mop` 10.96 m at 32.668966, -117.178924. 2175 matched hours.

| 46232 from | n | MOP | break_5m eq | normal_mop eq | mop eq | mop hard |
|---|---:|---|---|---|---|---|
| S (150–205°) | 653 | 0.37 [0.29, 0.44] | 0.52 [0.46, 0.58] | 0.49 [0.42, 0.56] | 0.53 [0.43, 0.59] | 0.48 [0.40, 0.55] |
| SSW-SW (205–235°) | 961 | 0.44 [0.37, 0.55] | 0.57 [0.49, 0.65] | 0.56 [0.49, 0.64] | 0.58 [0.51, 0.64] | 0.55 [0.47, 0.61] |
| WSW-W (235–270°) | 335 | 0.54 [0.43, 0.65] | 0.68 [0.59, 0.84] | 0.66 [0.58, 0.75] | 0.65 [0.58, 0.72] | 0.62 [0.55, 0.69] |
| W-WNW (270–295°) | 226 | 0.54 [0.47, 0.65] | 0.80 [0.69, 0.89] | 0.70 [0.64, 0.76] | 0.69 [0.62, 0.78] | 0.65 [0.57, 0.71] |
| all (0–360°) | 2175 | 0.44 [0.34, 0.59] | 0.57 [0.48, 0.78] | 0.56 [0.46, 0.70] | 0.58 [0.49, 0.69] | 0.55 [0.45, 0.65] |

Ratios, hour by hour, median [10th, 90th] (MOP from 10.77 m in brackets):

| 46232 from | chain-at-MOP / MOP, eq | hard | 5 m / chain-at-MOP | 5 m / normal 10 m | normal 10 m / chain-at-MOP |
|---|---|---|---|---|---|
| S | 1.41 [1.18, 1.76] (1.39) | 1.30 [1.09, 1.56] | 0.98 [0.90, 1.14] | 1.05 [0.98, 1.16] | 0.95 [0.86, 1.03] |
| SSW-SW | 1.30 [1.09, 1.53] (1.28) | 1.22 [1.03, 1.44] | 0.99 [0.91, 1.08] | 1.01 [0.96, 1.09] | 0.98 [0.90, 1.05] |
| WSW-W | 1.19 [1.00, 1.46] (1.18) | 1.14 [0.96, 1.40] | 1.07 [0.97, 1.21] | 1.04 [0.97, 1.14] | 1.03 [0.95, 1.11] |
| W-WNW | 1.25 [1.04, 1.49] (1.24) | 1.17 [0.98, 1.38] | 1.15 [1.02, 1.29] | 1.13 [1.03, 1.26] | 1.02 [0.91, 1.10] |
| all | 1.31 [1.08, 1.59] (1.29) | 1.23 [1.02, 1.48] | 1.00 [0.91, 1.17] | 1.03 [0.97, 1.15] | 0.98 [0.89, 1.06] |

chain-at-MOP / MOP (eq) by 46232's swell peak period:

| 46232 from | 8–11 s | 11–14 s | 14–17 s | 17–26 s |
|---|---|---|---|---|
| S | 1.50 (n 39) | 1.38 (n 258) | 1.42 (n 315) | 1.45 (n 41) |
| SSW-SW | 1.31 (n 22) | 1.19 (n 190) | 1.31 (n 665) | 1.44 (n 84) |
| WSW-W | 1.09 (n 38) | 1.18 (n 139) | 1.22 (n 145) | 1.39 (n 13) |
| W-WNW | 1.27 (n 7) | 1.23 (n 77) | 1.28 (n 127) | 1.29 (n 15) |
| all | 1.31 (n 106) | 1.26 (n 664) | 1.33 (n 1252) | 1.44 (n 153) |

chain-at-MOP (eq, maximum entropy) with only its energy up to a frequency, over MOP's whole Hs; and with the whole spectrum read by Fourier instead:

| 46232 from | ≤ 0.1 Hz | ≤ 0.125 Hz | ≤ 0.15 Hz | ≤ 0.2 Hz | ≤ 0.25 Hz | ≤ 0.58 Hz | Fourier, all |
|---|---|---|---|---|---|---|---|
| S | 0.98 | 1.11 | 1.23 | 1.31 | 1.35 | 1.41 | 1.50 |
| SSW-SW | 0.86 | 0.97 | 1.13 | 1.22 | 1.27 | 1.30 | 1.39 |
| WSW-W | 0.87 | 1.00 | 1.10 | 1.15 | 1.17 | 1.19 | 1.27 |
| W-WNW | 1.07 | 1.16 | 1.22 | 1.24 | 1.25 | 1.25 | 1.41 |
| all | 0.93 | 1.04 | 1.16 | 1.24 | 1.28 | 1.31 | 1.41 |

Peak period over the same water (MOP's Tp; chain-at-MOP's densest bin), by 46232's overall peak:

| 46232 peak | n | MOP Tp | chain-at-MOP peak | hours MOP Tp < 9 s | hours chain peak < 9 s |
|---|---:|---|---|---:|---:|
| < 9 s | 53 | 14.29 [8.16, 18.18] | 7.69 [6.67, 15.38] | 13 | 36 |
| 9–12 s | 296 | 12.30 [10.00, 16.67] | 11.76 [9.09, 13.33] | 15 | 23 |
| ≥ 12 s | 1826 | 15.38 [12.30, 16.67] | 14.29 [11.76, 16.67] | 41 | 111 |

Share of chain-at-MOP's diffracted energy by kind of ray (sector totals), and chain-at-MOP / MOP with only the clear rays:

| 46232 from | clear | island fill | Point Loma fill | Baja fill | clear only / MOP |
|---|---|---|---|---|---|
| S | 82.4% | 13.4% | 3.7% | 0.5% | 1.29 [1.08, 1.55] |
| SSW-SW | 86.8% | 8.3% | 4.7% | 0.2% | 1.21 [1.02, 1.43] |
| WSW-W | 89.2% | 2.6% | 8.1% | 0.1% | 1.13 [0.96, 1.39] |
| W-WNW | 79.7% | 0.9% | 19.4% | 0.0% | 1.16 [0.97, 1.37] |
| all | 84.2% | 5.5% | 10.1% | 0.2% | 1.22 [1.02, 1.46] |

Where chain-at-MOP's energy comes from offshore (diffracted, sector totals, share by 10° of offshore heading; ≥ 3% shown) beside `break_5m`'s:

- **S** — MOP point: 170°s 7%, 180°s 11%, 190°s 12%, 200°s 5%, 230°s 4%, 240°s 9%, 250°s 13%, 260°s 9%, 270°s 12%, 280°s 5%; break 5 m: 170°s 14%, 180°s 14%, 190°s 8%, 220°s 3%, 230°s 3%, 240°s 7%, 250°s 11%, 260°s 11%, 270°s 12%, 280°s 4%
- **SSW-SW** — MOP point: 180°s 6%, 190°s 8%, 200°s 5%, 210°s 3%, 230°s 4%, 240°s 11%, 250°s 17%, 260°s 11%, 270°s 15%, 280°s 7%, 290°s 4%; break 5 m: 180°s 5%, 190°s 5%, 220°s 4%, 230°s 4%, 240°s 9%, 250°s 14%, 260°s 15%, 270°s 19%, 280°s 8%, 290°s 4%
- **WSW-W** — MOP point: 240°s 9%, 250°s 15%, 260°s 13%, 270°s 25%, 280°s 15%, 290°s 5%; break 5 m: 240°s 6%, 250°s 11%, 260°s 15%, 270°s 31%, 280°s 17%, 290°s 6%
- **W-WNW** — MOP point: 240°s 5%, 250°s 9%, 260°s 8%, 270°s 24%, 280°s 35%, 290°s 8%, 300°s 3%; break 5 m: 240°s 3%, 250°s 6%, 260°s 10%, 270°s 30%, 280°s 28%, 290°s 15%

Direction over the same water: MOP's peak direction (Dp) against the heading chain-at-MOP's energy arrives on in the 46232 bin nearest MOP's Tp:

| 46232 from | MOP Dp | chain-at-MOP | chain − MOP |
|---|---|---|---|
| S | 212.81 [210.57, 221.46] | 209.80 [205.57, 218.03] | -3.68 [-8.88, 0.49] |
| SSW-SW | 214.51 [210.96, 224.79] | 213.23 [207.76, 222.41] | -1.75 [-6.75, 2.64] |
| WSW-W | 219.02 [215.74, 228.04] | 221.59 [214.23, 229.66] | 0.27 [-5.02, 8.45] |
| W-WNW | 219.26 [217.58, 226.24] | 226.55 [223.05, 237.31] | 6.54 [-0.34, 18.83] |
| all | 215.56 [211.02, 225.76] | 213.99 [206.95, 227.42] | -1.61 [-7.01, 6.21] |

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


### MOP's own spectrum, band by band

MOP's 20 bands, 0.0375–0.4500 Hz (edges from `waveFrequencyBounds`); read-back 4·sqrt(Σ E·df) / MOP's Hs median 1.0, worst 1.0 over 2565 hours. Common bands 0.0375–0.4500 Hz. 2175 matched hours with a complete MOP spectrum; a band-hour is compared when 46232 has ≥ 0.05 m in the band.

Whole spectrum, MOP de-shoaled band by band at each band's frequency (10.77 m in brackets) against at its Tp as above; MOP's spectrum summed over its own Hs at the point:

| 46232 from | n | MOP, by band | MOP, at Tp | chain-at-MOP / MOP, by band | at Tp | spectrum Hs / MOP Hs |
|---|---:|---|---|---|---|---|
| S | 653 | 0.42 [0.31, 0.48] | 0.37 [0.29, 0.44] | 1.26 [1.11, 1.56] (1.26) | 1.41 | 1.00 [1.00, 1.00] |
| SSW-SW | 961 | 0.49 [0.41, 0.57] | 0.44 [0.37, 0.55] | 1.18 [1.04, 1.35] (1.18) | 1.30 | 1.00 [1.00, 1.00] |
| WSW-W | 335 | 0.58 [0.48, 0.68] | 0.54 [0.43, 0.65] | 1.11 [0.96, 1.33] (1.11) | 1.19 | 1.00 [1.00, 1.00] |
| W-WNW | 226 | 0.59 [0.52, 0.70] | 0.54 [0.47, 0.65] | 1.17 [0.97, 1.37] (1.15) | 1.25 | 1.00 [1.00, 1.00] |
| all | 2175 | 0.48 [0.38, 0.62] | 0.44 [0.34, 0.59] | 1.20 [1.03, 1.41] (1.19) | 1.31 | 1.00 [1.00, 1.00] |

chain-at-MOP / MOP in each band, as heights (√ of the energy ratio, both deep-water-equivalent, before friction), median [10th, 90th] and hours:

| 46232 from | 16.7–26.7 s | 13.0–16.7 s | 10.0–13.0 s | 8.0–10.0 s | 6.7–8.0 s | 5.0–6.7 s | 4.0–5.0 s | 2.2–4.0 s |
|---|---|---|---|---|---|---|---|---|
| S | 1.26 [0.93, 1.75] n 653 | 1.52 [1.18, 2.12] n 653 | 1.35 [1.06, 1.97] n 653 | 1.11 [0.86, 1.65] n 652 | 1.27 [1.00, 1.64] n 621 | 1.17 [0.97, 1.46] n 628 | 0.95 [0.74, 1.20] n 616 | 0.83 [0.56, 1.11] n 569 |
| SSW-SW | 1.20 [0.90, 1.60] n 961 | 1.34 [1.05, 1.66] n 961 | 1.18 [0.93, 1.50] n 961 | 1.02 [0.81, 1.31] n 961 | 1.28 [0.98, 1.67] n 951 | 1.18 [0.95, 1.42] n 954 | 1.01 [0.78, 1.25] n 927 | 0.87 [0.52, 1.12] n 901 |
| WSW-W | 1.04 [0.79, 1.37] n 329 | 1.20 [1.03, 1.51] n 335 | 1.09 [0.84, 1.38] n 335 | 1.04 [0.77, 1.35] n 335 | 1.20 [0.95, 1.58] n 335 | 1.18 [0.95, 1.39] n 335 | 0.98 [0.75, 1.20] n 328 | 0.84 [0.54, 1.09] n 307 |
| W-WNW | 1.03 [0.80, 1.35] n 226 | 1.36 [1.04, 1.76] n 226 | 0.99 [0.74, 1.32] n 226 | 0.99 [0.78, 1.28] n 226 | 1.15 [0.96, 1.42] n 226 | 1.10 [0.89, 1.30] n 223 | 0.92 [0.66, 1.10] n 196 | 0.71 [0.43, 0.94] n 159 |
| all | 1.16 [0.87, 1.59] n 2169 | 1.36 [1.07, 1.83] n 2175 | 1.20 [0.89, 1.59] n 2175 | 1.04 [0.80, 1.38] n 2174 | 1.25 [0.98, 1.62] n 2133 | 1.17 [0.95, 1.42] n 2140 | 0.98 [0.75, 1.22] n 2067 | 0.84 [0.53, 1.10] n 1936 |

Each over 46232 in the same band, as heights (√ energy ratio), median: MOP / chain-at-MOP. Where MOP is lower than the chain, this says whether MOP takes less of the buoy's band or the chain takes more:

| 46232 from | 16.7–26.7 s | 13.0–16.7 s | 10.0–13.0 s | 8.0–10.0 s | 6.7–8.0 s | 5.0–6.7 s | 4.0–5.0 s | 2.2–4.0 s |
|---|---|---|---|---|---|---|---|---|
| S | 0.38 / 0.48 | 0.32 / 0.51 | 0.38 / 0.52 | 0.52 / 0.57 | 0.53 / 0.68 | 0.46 / 0.54 | 0.51 / 0.48 | 0.66 / 0.55 |
| SSW-SW | 0.43 / 0.50 | 0.40 / 0.54 | 0.52 / 0.61 | 0.60 / 0.60 | 0.55 / 0.70 | 0.46 / 0.55 | 0.51 / 0.51 | 0.63 / 0.54 |
| WSW-W | 0.61 / 0.64 | 0.52 / 0.66 | 0.61 / 0.65 | 0.62 / 0.63 | 0.59 / 0.72 | 0.49 / 0.57 | 0.55 / 0.53 | 0.65 / 0.56 |
| W-WNW | 0.72 / 0.74 | 0.56 / 0.76 | 0.63 / 0.62 | 0.63 / 0.62 | 0.61 / 0.72 | 0.52 / 0.58 | 0.54 / 0.50 | 0.63 / 0.49 |
| all | 0.45 / 0.52 | 0.41 / 0.55 | 0.51 / 0.59 | 0.58 / 0.60 | 0.55 / 0.70 | 0.47 / 0.55 | 0.52 / 0.50 | 0.64 / 0.54 |

Share of the deep-water-equivalent energy by band (sector totals): MOP / chain-at-MOP / 46232:

| 46232 from | 16.7–26.7 s | 13.0–16.7 s | 10.0–13.0 s | 8.0–10.0 s | 6.7–8.0 s | 5.0–6.7 s | 4.0–5.0 s | 2.2–4.0 s |
|---|---|---|---|---|---|---|---|---|
| S | 6 / 7 / 8% | 15 / 23 / 22% | 17 / 21 / 29% | 13 / 12 / 12% | 12 / 12 / 7% | 15 / 13 / 11% | 10 / 6 / 6% | 13 / 6 / 5% |
| SSW-SW | 7 / 8 / 10% | 20 / 26 / 28% | 18 / 17 / 15% | 15 / 11 / 10% | 11 / 14 / 10% | 12 / 13 / 14% | 8 / 6 / 8% | 10 / 6 / 6% |
| WSW-W | 8 / 7 / 5% | 22 / 29 / 25% | 26 / 24 / 23% | 17 / 14 / 15% | 10 / 11 / 10% | 8 / 9 / 12% | 4 / 4 / 5% | 5 / 3 / 4% |
| W-WNW | 18 / 18 / 12% | 29 / 41 / 33% | 23 / 17 / 22% | 13 / 10 / 13% | 7 / 7 / 8% | 5 / 5 / 7% | 2 / 2 / 3% | 3 / 1 / 2% |
| all | 11 / 11 / 9% | 23 / 31 / 27% | 21 / 19 / 21% | 14 / 11 / 12% | 10 / 11 / 9% | 9 / 9 / 11% | 5 / 4 / 6% | 7 / 4 / 5% |

MOP's own weighted input coverage per band (`waveModelBinInputCoverage`, overlap-weighted mean of its bands), median [10th, 90th]:

| 46232 from | 16.7–26.7 s | 13.0–16.7 s | 10.0–13.0 s | 8.0–10.0 s | 6.7–8.0 s | 5.0–6.7 s | 4.0–5.0 s | 2.2–4.0 s |
|---|---|---|---|---|---|---|---|---|
| S | 0.99 [0.99, 0.99] | 1.00 [1.00, 1.00] | 1.00 [1.00, 1.00] | 1.00 [1.00, 1.00] | 1.00 [1.00, 1.00] | 1.00 [1.00, 1.00] | 1.00 [1.00, 1.00] | 1.00 [1.00, 1.00] |
| SSW-SW | 0.99 [0.99, 0.99] | 1.00 [1.00, 1.00] | 1.00 [1.00, 1.00] | 1.00 [1.00, 1.00] | 1.00 [1.00, 1.00] | 1.00 [1.00, 1.00] | 1.00 [1.00, 1.00] | 1.00 [1.00, 1.00] |
| WSW-W | 0.99 [0.99, 0.99] | 1.00 [1.00, 1.00] | 1.00 [1.00, 1.00] | 1.00 [1.00, 1.00] | 1.00 [1.00, 1.00] | 1.00 [1.00, 1.00] | 1.00 [1.00, 1.00] | 1.00 [1.00, 1.00] |
| W-WNW | 0.99 [0.99, 0.99] | 1.00 [1.00, 1.00] | 1.00 [1.00, 1.00] | 1.00 [1.00, 1.00] | 1.00 [1.00, 1.00] | 1.00 [1.00, 1.00] | 1.00 [1.00, 1.00] | 1.00 [1.00, 1.00] |
| all | 0.99 [0.99, 0.99] | 1.00 [1.00, 1.00] | 1.00 [1.00, 1.00] | 1.00 [1.00, 1.00] | 1.00 [1.00, 1.00] | 1.00 [1.00, 1.00] | 1.00 [1.00, 1.00] | 1.00 [1.00, 1.00] |

By MOP's input sources (`waveModelInputSource` as written, trailing padding dropped; CDIP station ids): whole-spectrum chain-at-MOP / MOP (MOP de-shoaled by band), median [10th, 90th] and hours, by 46232's sector:

| inputs | S | SSW-SW | WSW-W | W-WNW | all |
|---|---|---|---|---|---|
| `191p1-067p1-071p1:191p1-220p1-100p1-045p1` | 1.26 [1.11, 1.56] n 653 | 1.18 [1.04, 1.35] n 961 | 1.11 [0.96, 1.33] n 335 | 1.17 [0.97, 1.37] n 226 | 1.20 [1.03, 1.41] n 2175 |

MOP's a1/b1 convention, read off its own Dp at its peak band (median |difference|): from, clockwise from north: atan2(b1, a1) 0.0°; toward, clockwise from north: atan2(b1, a1) + 180 180.0°; toward, counter-clockwise from east: 270 - atan2(b1, a1) 159.3°; from, counter-clockwise from east: 90 - atan2(b1, a1) 20.7°. Taken: **from, clockwise from north: atan2(b1, a1)**.

Direction by band: chain-at-MOP's arrival heading minus MOP's mean direction from (°), median [10th, 90th]; MOP's mean direction in brackets:

| 46232 from | 16.7–26.7 s | 13.0–16.7 s | 10.0–13.0 s | 8.0–10.0 s | 6.7–8.0 s | 5.0–6.7 s | 4.0–5.0 s | 2.2–4.0 s |
|---|---|---|---|---|---|---|---|---|
| S | -1.29 [-4.47, 2.42] (214°) | -4.85 [-7.84, -1.85] (213°) | -6.72 [-11.42, -2.44] (218°) | -9.62 [-17.84, -2.32] (226°) | 2.78 [-6.72, 7.23] (231°) | 3.15 [-1.74, 6.19] (237°) | -0.14 [-3.91, 2.82] (245°) | 2.12 [-2.21, 5.65] (243°) |
| SSW-SW | -0.34 [-3.89, 3.03] (214°) | -2.76 [-6.07, 0.14] (213°) | -3.29 [-8.98, 0.18] (220°) | -2.38 [-7.87, 1.26] (230°) | 4.83 [0.05, 8.10] (233°) | 3.61 [0.10, 6.32] (236°) | 0.26 [-3.76, 3.08] (243°) | 1.50 [-3.53, 5.38] (241°) |
| WSW-W | 1.51 [-1.09, 8.24] (215°) | 0.26 [-3.06, 6.41] (216°) | -1.40 [-5.84, 1.55] (225°) | -1.61 [-5.41, 2.34] (230°) | 4.72 [1.54, 8.81] (233°) | 3.72 [1.10, 6.09] (236°) | -0.47 [-4.45, 2.43] (242°) | 0.98 [-4.55, 4.57] (240°) |
| W-WNW | 8.29 [2.43, 16.36] (218°) | 7.09 [3.37, 15.12] (220°) | -0.44 [-2.15, 2.06] (228°) | 0.73 [-1.74, 3.26] (230°) | 5.41 [1.70, 8.02] (233°) | 3.71 [0.87, 6.06] (236°) | -0.40 [-4.73, 3.15] (242°) | 1.09 [-4.48, 4.91] (242°) |
| all | 0.07 [-3.72, 6.74] (214°) | -2.63 [-6.68, 4.95] (214°) | -3.39 [-9.69, 0.54] (220°) | -3.01 [-12.52, 1.55] (229°) | 4.42 [-0.79, 8.01] (232°) | 3.56 [-0.27, 6.22] (236°) | -0.09 [-4.09, 2.95] (244°) | 1.54 [-3.60, 5.38] (241°) |

## What MOP's files say about themselves

Read from each file's DAS and from its small variables (`collector.mop`, Actions), verbatim. This is where MOP's depth datum, its method and the buoys that drive the nowcast are read; nothing in this section is inferred.

### Global attributes (D0181)

- `history`: "2026-11-18T21:09:10Z: dataset created; Net_model version 2.1. Runtime arguments: /project/f90_bin/net_model_gf -s 202611181300 -h 8 -c socal_alongshore_ref.nc -i socal_alongshore_nowcast.INPUT -z nowcast -e -S If date_modified is after date_created, contact CDIP for details of changes."
- `date_created`: "2026-11-18T21:09:10Z"
- `date_modified`: "2026-11-18T21:09:10Z"
- `title`: "Bulk wave parameters and directional wave spectra as predicted by the CDIP MOP version 1.1 model for the sites defined in D0181."
- `summary`: "The CDIP Monitoring and Prediction (MOP) System output of spectral wave predictions for the sites defined in D0181 from 04/01/2025 00:00 to 11/18/2026 20:00 UTC."
- `contributor_name`: "CDIP"
- `contributor_role`: "model design and implementation"
- `comment`: "Details on the MOP wave model are provided in OReilly, W.C. et al (2016). The California Coastal Wave Monitoring and Prediction System. Manuscript submitted to Coastal Engineering."
- `keywords`: "EARTH SCIENCE, OCEANS, OCEAN WAVES, GRAVITY WAVES, WIND WAVES, SIGNIFICANT WAVE HEIGHT, WAVE FREQUENCY, WAVE PERIOD, WAVE SPECTRA, OCEAN, PACIFIC OCEAN, EASTERN PACIFIC OCEAN"
- `id`: "MOPv1.1_D0181_2025040100-2026111820"
- `MOP_initialization_file`: "socal_alongshore_nowcast.INPUT"
- `MOP_output_site_definitions`: "D0181"
- `acknowledgment`: "CDIP is primarily supported by the U.S. Army Corps of Engineers (USACE)."
- `metadata_link`: "http://cdip.ucsd.edu/MOP_v1.1/"
- `infoUrl`: "http://cdip.ucsd.edu/MOP_v1.1/"
- `geospatial_lat_min`: 32.67358
- `geospatial_lat_max`: 32.67358
- `geospatial_lat_units`: "degrees_north"
- `geospatial_lat_resolution`: 0.0001
- `geospatial_lon_min`: -117.1912
- `geospatial_lon_max`: -117.1912
- `geospatial_lon_units`: "degrees_east"
- `geospatial_lon_resolution`: 0.0001
- `geospatial_vertical_min`: 0.0
- `geospatial_vertical_max`: 0.0
- `geospatial_vertical_units`: "meters"
- `geospatial_vertical_origin`: "sea surface"
- `geospatial_vertical_positive`: "up"
- `geospatial_vertical_resolution`: 1.0
- `time_coverage_start`: "2025-03-31T23:30:00Z"
- `time_coverage_end`: "2026-11-18T20:30:00Z"
- `time_coverage_duration`: "P596DT21H00M"
- `time_coverage_resolution`: "PT01H00M"
- `source`: "model output"
- `naming_authority`: "edu.ucsd.cdip"
- `keywords_vocabulary`: "Global Change Master Directory (GCMD) Earth Science Keywords"
- `date_issued`: "2026-11-18T21:09:10Z"
- `creator_name`: "Coastal Data Information Program, SIO/UCSD"
- `creator_url`: "http://cdip.ucsd.edu"
- `creator_email`: "www@cdip.ucsd.edu"
- `creator_institution`: "Scripps Institution of Oceanography, UCSD"
- `creator_country`: "USA"
- `creator_sector`: "academic"
- `publisher_name`: "Coastal Data Information Program, SIO/UCSD"
- `publisher_url`: "http://cdip.ucsd.edu"
- `publisher_email`: "www@cdip.ucsd.edu"
- `publisher_country`: "USA"
- `publisher_institution`: "Scripps Institution of Oceanography, UCSD"
- `institution`: "Scripps Institution of Oceanography, University of California San Diego"
- `project`: "Coastal Data Information Program (CDIP)"
- `processing_level`: "QA/QC information available at http://cdip.ucsd.edu/documentation"
- `standard_name_vocabulary`: "CF Standard Name Table v79"
- `Conventions`: "ACDD-1.3, CF-1.8, IOOS-1.2"
- `license`: "These data may be redistributed and used without restriction."
- `cdm_data_type`: "Station"
- `featureType`: "timeSeries"
- `ncei_template_version`: "NCEI_NetCDF_TimeSeries_Orthogonal_Template_v2.0"
- `references`: "http://cdip.ucsd.edu/documentation"
- `uuid`: "EB46E4C1-4F3C-4652-92FF-7195D82BF195"

Differing at D0179 (coronado_center):
- `history`: "2026-11-18T21:09:09Z: dataset created; Net_model version 2.1. Runtime arguments: /project/f90_bin/net_model_gf -s 202611181300 -h 8 -c socal_alongshore_ref.nc -i socal_alongshore_nowcast.INPUT -z nowcast -e -S If date_modified is after date_created, contact CDIP for details of changes."
- `date_created`: "2026-11-18T21:09:09Z"
- `date_modified`: "2026-11-18T21:09:09Z"
- `title`: "Bulk wave parameters and directional wave spectra as predicted by the CDIP MOP version 1.1 model for the sites defined in D0179."
- `summary`: "The CDIP Monitoring and Prediction (MOP) System output of spectral wave predictions for the sites defined in D0179 from 04/01/2025 00:00 to 11/18/2026 20:00 UTC."
- `id`: "MOPv1.1_D0179_2025040100-2026111820"
- `MOP_output_site_definitions`: "D0179"
- `geospatial_lat_min`: 32.67395
- `geospatial_lat_max`: 32.67395
- `geospatial_lon_min`: -117.18846
- `geospatial_lon_max`: -117.18846
- `date_issued`: "2026-11-18T21:09:09Z"
- `uuid`: "EB4714D1-5833-4E1E-9DEB-3838305D72CB"

Differing at D0168 (coronado_south):
- `history`: "2026-11-18T21:09:07Z: dataset created; Net_model version 2.1. Runtime arguments: /project/f90_bin/net_model_gf -s 202611181300 -h 8 -c socal_alongshore_ref.nc -i socal_alongshore_nowcast.INPUT -z nowcast -e -S If date_modified is after date_created, contact CDIP for details of changes."
- `date_created`: "2026-11-18T21:09:07Z"
- `date_modified`: "2026-11-18T21:09:07Z"
- `title`: "Bulk wave parameters and directional wave spectra as predicted by the CDIP MOP version 1.1 model for the sites defined in D0168."
- `summary`: "The CDIP Monitoring and Prediction (MOP) System output of spectral wave predictions for the sites defined in D0168 from 04/01/2025 00:00 to 11/18/2026 20:00 UTC."
- `id`: "MOPv1.1_D0168_2025040100-2026111820"
- `MOP_output_site_definitions`: "D0168"
- `geospatial_lat_min`: 32.66898
- `geospatial_lat_max`: 32.66898
- `geospatial_lon_min`: -117.17891
- `geospatial_lon_max`: -117.17891
- `date_issued`: "2026-11-18T21:09:07Z"
- `uuid`: "EA4749CA-5D2E-4C14-92D8-D159CBF6CF70"

Differing at D0052 (imperial_beach):
- `history`: "2026-11-20T00:07:50Z: dataset created; Net_model version 2.1. Runtime arguments: /project/f90_bin/net_model_gf -s 202611191600 -h 8 -c socal_alongshore_ref.nc -i socal_alongshore_nowcast.INPUT -z nowcast -e -S If date_modified is after date_created, contact CDIP for details of changes."
- `date_created`: "2026-11-20T00:07:50Z"
- `date_modified`: "2026-11-20T00:07:50Z"
- `title`: "Bulk wave parameters and directional wave spectra as predicted by the CDIP MOP version 1.1 model for the sites defined in D0052."
- `summary`: "The CDIP Monitoring and Prediction (MOP) System output of spectral wave predictions for the sites defined in D0052 from 04/01/2025 00:00 to 11/19/2026 23:00 UTC."
- `id`: "MOPv1.1_D0052_2025040100-2026111923"
- `MOP_output_site_definitions`: "D0052"
- `geospatial_lat_min`: 32.57851
- `geospatial_lat_max`: 32.57851
- `geospatial_lon_min`: -117.1423
- `geospatial_lon_max`: -117.1423
- `time_coverage_end`: "2026-11-19T23:30:00Z"
- `time_coverage_duration`: "P598DT00H00M"
- `date_issued`: "2026-11-20T00:07:50Z"
- `uuid`: "6AE3DDD2-5137-48EC-983F-3B49CEB6C7D4"

### Per point

**D0181** (coronado_north) — `metaWaterDepth` attributes: {"standard_name": "sea_floor_depth_below_sea_level", "long_name": "water depth", "units": "meter", "_FillValue": -999.99, "ncei_name": "DEPTH - BOTTOM", "coverage_content_type": "referenceInformation"}. Spectrum: read; variables declared: metaGridMapping, metaLatitude, metaLongitude, metaShoreNormal, metaSiteLabel, metaWaterDepth, waveA1Value, waveA2Value, waveB1Value, waveB2Value, waveBandwidth, waveDm, waveDp, waveEnergyDensity, waveFlagPrimary, waveFlagSecondary, waveFrequency, waveFrequencyBounds, waveFrequencyFlagPrimary, waveFrequencyFlagSecondary, waveHs, waveMeanDirection, waveModelBinInputCoverage, waveModelInputSource, waveSxx, waveSxy, waveTa, waveTime, waveTimeBounds, waveTp.

Small variables (off the time axis), as served:

```
waveFrequency[20]
0.04, 0.045, 0.05, 0.055, 0.06, 0.065, 0.07, 0.075, 0.0813, 0.09, 0.1, 0.11, 0.1225, 0.14, 0.16, 0.18, 0.2075, 0.25, 0.3125, 0.4

waveFrequencyBounds[20][2]
[0], 0.037499998, 0.0425
[1], 0.0425, 0.047500003
[2], 0.0475, 0.052500002
[3], 0.0525, 0.0575
[4], 0.057499997, 0.0625
[5], 0.062499996, 0.067499995
[6], 0.0675, 0.0725
[7], 0.072500005, 0.0775
[8], 0.07755, 0.085049994
[9], 0.085, 0.095000006
[10], 0.095, 0.105000004
[11], 0.105, 0.115
[12], 0.115, 0.13
[13], 0.13, 0.15
[14], 0.14999999, 0.17
[15], 0.17, 0.19000001
[16], 0.19125, 0.22375
[17], 0.225, 0.275
[18], 0.275, 0.35
[19], 0.35, 0.45000002

waveFrequencyFlagPrimary[20]
1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1

waveFrequencyFlagSecondary[20]
0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0

waveBandwidth[20]
0.005, 0.005, 0.005, 0.005, 0.005, 0.005, 0.005, 0.005, 0.0075, 0.01, 0.01, 0.01, 0.015, 0.02, 0.02, 0.02, 0.0325, 0.05, 0.075, 0.1

metaSiteLabel, "D0181"
metaLatitude, 32.67358
metaLongitude, -117.1912
metaWaterDepth, 10.0
metaShoreNormal, 217.42
metaGridMapping, "_"
```

**D0179** (coronado_center) — `metaWaterDepth` attributes: {"standard_name": "sea_floor_depth_below_sea_level", "long_name": "water depth", "units": "meter", "_FillValue": -999.99, "ncei_name": "DEPTH - BOTTOM", "coverage_content_type": "referenceInformation"}. Spectrum: read; variables declared: metaGridMapping, metaLatitude, metaLongitude, metaShoreNormal, metaSiteLabel, metaWaterDepth, waveA1Value, waveA2Value, waveB1Value, waveB2Value, waveBandwidth, waveDm, waveDp, waveEnergyDensity, waveFlagPrimary, waveFlagSecondary, waveFrequency, waveFrequencyBounds, waveFrequencyFlagPrimary, waveFrequencyFlagSecondary, waveHs, waveMeanDirection, waveModelBinInputCoverage, waveModelInputSource, waveSxx, waveSxy, waveTa, waveTime, waveTimeBounds, waveTp.

Small variables (off the time axis), as served:

```
waveFrequency[20]
0.04, 0.045, 0.05, 0.055, 0.06, 0.065, 0.07, 0.075, 0.0813, 0.09, 0.1, 0.11, 0.1225, 0.14, 0.16, 0.18, 0.2075, 0.25, 0.3125, 0.4

waveFrequencyBounds[20][2]
[0], 0.037499998, 0.0425
[1], 0.0425, 0.047500003
[2], 0.0475, 0.052500002
[3], 0.0525, 0.0575
[4], 0.057499997, 0.0625
[5], 0.062499996, 0.067499995
[6], 0.0675, 0.0725
[7], 0.072500005, 0.0775
[8], 0.07755, 0.085049994
[9], 0.085, 0.095000006
[10], 0.095, 0.105000004
[11], 0.105, 0.115
[12], 0.115, 0.13
[13], 0.13, 0.15
[14], 0.14999999, 0.17
[15], 0.17, 0.19000001
[16], 0.19125, 0.22375
[17], 0.225, 0.275
[18], 0.275, 0.35
[19], 0.35, 0.45000002

waveFrequencyFlagPrimary[20]
1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1

waveFrequencyFlagSecondary[20]
0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0

waveBandwidth[20]
0.005, 0.005, 0.005, 0.005, 0.005, 0.005, 0.005, 0.005, 0.0075, 0.01, 0.01, 0.01, 0.015, 0.02, 0.02, 0.02, 0.0325, 0.05, 0.075, 0.1

metaSiteLabel, "D0179"
metaLatitude, 32.67395
metaLongitude, -117.18846
metaWaterDepth, 10.0
metaShoreNormal, 218.97
metaGridMapping, "_"
```

**D0168** (coronado_south) — `metaWaterDepth` attributes: {"standard_name": "sea_floor_depth_below_sea_level", "long_name": "water depth", "units": "meter", "_FillValue": -999.99, "ncei_name": "DEPTH - BOTTOM", "coverage_content_type": "referenceInformation"}. Spectrum: read; variables declared: metaGridMapping, metaLatitude, metaLongitude, metaShoreNormal, metaSiteLabel, metaWaterDepth, waveA1Value, waveA2Value, waveB1Value, waveB2Value, waveBandwidth, waveDm, waveDp, waveEnergyDensity, waveFlagPrimary, waveFlagSecondary, waveFrequency, waveFrequencyBounds, waveFrequencyFlagPrimary, waveFrequencyFlagSecondary, waveHs, waveMeanDirection, waveModelBinInputCoverage, waveModelInputSource, waveSxx, waveSxy, waveTa, waveTime, waveTimeBounds, waveTp.

Small variables (off the time axis), as served:

```
waveFrequency[20]
0.04, 0.045, 0.05, 0.055, 0.06, 0.065, 0.07, 0.075, 0.0813, 0.09, 0.1, 0.11, 0.1225, 0.14, 0.16, 0.18, 0.2075, 0.25, 0.3125, 0.4

waveFrequencyBounds[20][2]
[0], 0.037499998, 0.0425
[1], 0.0425, 0.047500003
[2], 0.0475, 0.052500002
[3], 0.0525, 0.0575
[4], 0.057499997, 0.0625
[5], 0.062499996, 0.067499995
[6], 0.0675, 0.0725
[7], 0.072500005, 0.0775
[8], 0.07755, 0.085049994
[9], 0.085, 0.095000006
[10], 0.095, 0.105000004
[11], 0.105, 0.115
[12], 0.115, 0.13
[13], 0.13, 0.15
[14], 0.14999999, 0.17
[15], 0.17, 0.19000001
[16], 0.19125, 0.22375
[17], 0.225, 0.275
[18], 0.275, 0.35
[19], 0.35, 0.45000002

waveFrequencyFlagPrimary[20]
1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1

waveFrequencyFlagSecondary[20]
0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0

waveBandwidth[20]
0.005, 0.005, 0.005, 0.005, 0.005, 0.005, 0.005, 0.005, 0.0075, 0.01, 0.01, 0.01, 0.015, 0.02, 0.02, 0.02, 0.0325, 0.05, 0.075, 0.1

metaSiteLabel, "D0168"
metaLatitude, 32.66898
metaLongitude, -117.17891
metaWaterDepth, 10.0
metaShoreNormal, 221.99
metaGridMapping, "_"
```

**D0052** (imperial_beach) — `metaWaterDepth` attributes: {"standard_name": "sea_floor_depth_below_sea_level", "long_name": "water depth", "units": "meter", "_FillValue": -999.99, "ncei_name": "DEPTH - BOTTOM", "coverage_content_type": "referenceInformation"}. Spectrum: read; variables declared: metaGridMapping, metaLatitude, metaLongitude, metaShoreNormal, metaSiteLabel, metaWaterDepth, waveA1Value, waveA2Value, waveB1Value, waveB2Value, waveBandwidth, waveDm, waveDp, waveEnergyDensity, waveFlagPrimary, waveFlagSecondary, waveFrequency, waveFrequencyBounds, waveFrequencyFlagPrimary, waveFrequencyFlagSecondary, waveHs, waveMeanDirection, waveModelBinInputCoverage, waveModelInputSource, waveSxx, waveSxy, waveTa, waveTime, waveTimeBounds, waveTp.

Small variables (off the time axis), as served:

```
waveFrequency[20]
0.04, 0.045, 0.05, 0.055, 0.06, 0.065, 0.07, 0.075, 0.0813, 0.09, 0.1, 0.11, 0.1225, 0.14, 0.16, 0.18, 0.2075, 0.25, 0.3125, 0.4

waveFrequencyBounds[20][2]
[0], 0.037499998, 0.0425
[1], 0.0425, 0.047500003
[2], 0.0475, 0.052500002
[3], 0.0525, 0.0575
[4], 0.057499997, 0.0625
[5], 0.062499996, 0.067499995
[6], 0.0675, 0.0725
[7], 0.072500005, 0.0775
[8], 0.07755, 0.085049994
[9], 0.085, 0.095000006
[10], 0.095, 0.105000004
[11], 0.105, 0.115
[12], 0.115, 0.13
[13], 0.13, 0.15
[14], 0.14999999, 0.17
[15], 0.17, 0.19000001
[16], 0.19125, 0.22375
[17], 0.225, 0.275
[18], 0.275, 0.35
[19], 0.35, 0.45000002

waveFrequencyFlagPrimary[20]
1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1

waveFrequencyFlagSecondary[20]
0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0

waveBandwidth[20]
0.005, 0.005, 0.005, 0.005, 0.005, 0.005, 0.005, 0.005, 0.0075, 0.01, 0.01, 0.01, 0.015, 0.02, 0.02, 0.02, 0.0325, 0.05, 0.075, 0.1

metaSiteLabel, "D0052"
metaLatitude, 32.57851
metaLongitude, -117.1423
metaWaterDepth, 10.0
metaShoreNormal, 264.48
metaGridMapping, "_"
```
