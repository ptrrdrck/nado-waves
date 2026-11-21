# The chain and MOP against an observation: one year at Imperial Beach Nearshore

Generated 2026-11-21 00:21 UTC by `python -m forecast.nearshoretest` (precompute-side, numpy; not run by any workflow). Report only: nothing here is fitted or shipped.

**Verification series: CDIP 155, Imperial Beach Nearshore (NDBC 46235)**, a Datawell Waverider, primary QC flag 1 only, 2024-01-01 – 2025-01-01 (the year `collector.nearshore_test` chose by its rule: 12 consecutive calendar months inside one MOP product's coverage with the most clock hours on which both buoys have a record; ties to the latest). It judges the leg from deep water to ~21 m at Imperial Beach, outside Point Loma's shadow. It is not a break and not Coronado.

Input: CDIP 191 (46232), MEM as shipped. MOP: `hindcast` at D0043. 8782 hours with all three (both buoys flag 1, no gap, within 30 min of MOP's hour). No lag between 46232 and the buoy (~30 km, about an hour of swell travel): hour-to-hour scatter, not bias.

## Controls

- **The input is the input**: CDIP's 191, converted to NDBC's form, against this repository's NDBC archive of 46232 on the 671 records both hold at the same time (August 2026). Hs |Δ|/Hs median 0.0307, 99th 0.0826 (signed median +0.0305); energy density in bins ≥ 0.2 m²/Hz (8814), |Δ|/E median 0.0161, 99th 0.4462; α1 |Δ| median 1.01°, 99th 9.97° (r1 > 0.3); r1 |Δ| median 0.0026. CDIP over NDBC, Hs signed median [10th, 90th]: ≥ 8 s +0.009 [+0.005, +0.015]; < 8 s +0.066 [+0.028, +0.196]. NDBC's feed is quantised and its small bins read low; CDIP's archive is neither, and the year below is carried from CDIP's. Where the models disagree (≥ 8 s) the two are the same input to about 1%.
- **What NDBC's rounded feed does to the shipped chain at the buoy** (the shipped tables fed NDBC's archive of 46232 and CDIP's 191 on the same records, August 2026; no observation then, so a ratio of two carries, not a score): Hs NDBC-fed / CDIP-fed, median [10th, 90th], whole 0.965 [0.931, 0.983]; ≥ 8 s 0.991 [0.959, 1.025]; < 8 s 0.943 [0.837, 0.975] over 671 records. Production reads NDBC's feed; the year below is CDIP's.
- **Read-backs** (4·sqrt(Σ E·df) / Hs, median / worst): imperial_beach_nearshore 0.99994 / 0.98915; point_loma_south 1.0 / 1.00861; mop_D0043 1.0 / 1.0.
- **QC flags** at the buoy over the year: {'1': 17562}.
- **MOP's independence**: inputs {'191p1-067p1-071p1:191p1-220p1-100p1-045p1___________________________________________________________': 8750, '191p1-067p1-071p1:191p1-100p1-045p1_________________________________________________________________': 34}; driven by 155 on 0 hours.
- **Where the buoy is**: CDIP's extent over its deployments, 32.56960, -117.16897 (centre); seabed there 20.91 m MSL (the chain's grid; the station states 21 m). Traced again from the extent's corner (32.57099, -117.17072, seabed 21.85 m): Hs corner / centre 1.00 [0.97, 1.03].
- Starts: buoy 20.91 m, corner 21.85 m, D0043 10.63 m (its seabed 10.64 m; MOP states 10.08 m). Fans on D0043's `metaShoreNormal` 273.01°, both halves, so every heading.

## The score at the buoy (the chain, exactly; Hs over the observed Hs)

Hs is the whole spectrum, 0.025–0.58 Hz on both sides. Median [10th, 90th]; bias and RMS in metres (model − observed).

**The shipped chain** is the chain as it runs: Madsen's friction tabulated at this start (20.93 m) and carried by `nearshore.carry` itself, at MSL (no coast tide for 2024). `before friction` and `JONSWAP` are the same tables without it and with the table's old fixed-share friction. All three are fed CDIP's 191; NDBC's rounded feed, which production reads, is in the controls.

| 46232 from | n | observed Hs | 46232 Hs / observed | **shipped chain / observed** | bias, RMS (m) | before friction / observed | bias, RMS (m) | JONSWAP / observed | bias, RMS (m) |
|---|---:|---|---|---|---|---|---|---|---|
| S | 1628 | 0.73 [0.58, 0.93] | 1.34 [1.16, 1.60] | 1.05 [0.92, 1.24] | +0.05, 0.11 | 1.09 [0.95, 1.30] | +0.08, 0.14 | 1.06 [0.93, 1.26] | +0.06, 0.12 |
| SSW-SW | 2283 | 0.76 [0.59, 0.97] | 1.30 [1.13, 1.48] | 1.07 [0.92, 1.22] | +0.06, 0.11 | 1.10 [0.95, 1.27] | +0.08, 0.13 | 1.08 [0.93, 1.24] | +0.06, 0.12 |
| WSW-W | 3097 | 0.97 [0.71, 1.61] | 1.23 [1.07, 1.42] | 1.05 [0.91, 1.21] | +0.05, 0.14 | 1.09 [0.94, 1.25] | +0.09, 0.16 | 1.07 [0.93, 1.23] | +0.07, 0.14 |
| W-WNW | 1773 | 1.38 [0.96, 2.45] | 1.23 [1.06, 1.42] | 1.07 [0.93, 1.23] | +0.10, 0.21 | 1.11 [0.96, 1.28] | +0.16, 0.25 | 1.09 [0.95, 1.25] | +0.13, 0.23 |
| all | 8782 | 0.88 [0.63, 1.67] | 1.27 [1.09, 1.48] | 1.06 [0.92, 1.23] | +0.06, 0.14 | 1.09 [0.95, 1.27] | +0.10, 0.17 | 1.07 [0.93, 1.24] | +0.08, 0.15 |

By the observed Hs (all directions; W–WNW in brackets, where §56 found the headline high on big days). MOP and its column are deep-water-equivalent against the buoy de-shoaled, as below:

| observed Hs | n (W–WNW) | shipped chain / observed | bias (m) | before friction / observed | MOP / observed |
|---|---|---|---|---|---|
| 0–0.75 m | 2540 (21) | 1.08 [0.93, 1.25] (1.26) | +0.06 | 1.11 [0.96, 1.30] (1.30) | 0.96 [0.83, 1.09] (1.09) |
| 0.75–1 m | 3018 (221) | 1.06 [0.93, 1.23] (1.16) | +0.06 | 1.10 [0.96, 1.28] (1.19) | 0.99 [0.84, 1.15] (1.10) |
| 1–1.5 m | 2032 (761) | 1.05 [0.90, 1.20] (1.07) | +0.06 | 1.08 [0.93, 1.24] (1.10) | 1.01 [0.88, 1.16] (1.04) |
| 1.5–2 m | 694 (393) | 1.05 [0.92, 1.20] (1.07) | +0.09 | 1.08 [0.95, 1.23] (1.11) | 1.05 [0.94, 1.17] (1.05) |
| ≥ 2 m | 498 (377) | 1.02 [0.90, 1.15] (1.03) | +0.04 | 1.06 [0.94, 1.20] (1.07) | 1.03 [0.92, 1.17] (1.02) |

By band, the shipped chain / observed as heights at the buoy (√ energy ratio), median [10th, 90th]; a band-hour counts when the observed band holds ≥ 0.05 m:

| 46232 from | 16.7–26.7 s | 13.0–16.7 s | 10.0–13.0 s | 8.0–10.0 s | 6.7–8.0 s | 5.0–6.7 s | 4.0–5.0 s | 2.2–4.0 s |
|---|---|---|---|---|---|---|---|---|
| S | 1.23 [0.91, 1.69] | 1.19 [0.91, 1.56] | 0.96 [0.77, 1.19] | 0.96 [0.73, 1.19] | 1.00 [0.76, 1.29] | 1.04 [0.84, 1.29] | 1.06 [0.89, 1.27] | 1.04 [0.86, 1.25] |
| SSW-SW | 1.18 [0.88, 1.62] | 1.15 [0.90, 1.49] | 0.99 [0.79, 1.22] | 0.99 [0.75, 1.28] | 1.02 [0.78, 1.33] | 1.06 [0.87, 1.29] | 1.07 [0.88, 1.29] | 1.05 [0.85, 1.29] |
| WSW-W | 1.06 [0.77, 1.43] | 1.08 [0.84, 1.38] | 1.03 [0.82, 1.28] | 1.04 [0.83, 1.29] | 1.05 [0.84, 1.30] | 1.05 [0.87, 1.26] | 1.06 [0.87, 1.31] | 1.05 [0.83, 1.31] |
| W-WNW | 1.01 [0.78, 1.35] | 1.06 [0.84, 1.39] | 1.07 [0.86, 1.34] | 1.07 [0.87, 1.33] | 1.06 [0.86, 1.30] | 1.07 [0.91, 1.26] | 1.08 [0.90, 1.29] | 1.06 [0.86, 1.30] |
| all | 1.11 [0.81, 1.53] | 1.11 [0.87, 1.45] | 1.01 [0.81, 1.27] | 1.02 [0.79, 1.28] | 1.04 [0.81, 1.30] | 1.05 [0.87, 1.28] | 1.07 [0.88, 1.29] | 1.05 [0.85, 1.29] |

By band, the chain before friction / observed as heights at the buoy (√ energy ratio), median [10th, 90th]; a band-hour counts when the observed band holds ≥ 0.05 m:

| 46232 from | 16.7–26.7 s | 13.0–16.7 s | 10.0–13.0 s | 8.0–10.0 s | 6.7–8.0 s | 5.0–6.7 s | 4.0–5.0 s | 2.2–4.0 s |
|---|---|---|---|---|---|---|---|---|
| S | 1.33 [0.97, 1.86] | 1.28 [0.98, 1.70] | 1.04 [0.83, 1.29] | 0.99 [0.76, 1.23] | 1.01 [0.77, 1.31] | 1.04 [0.85, 1.30] | 1.06 [0.89, 1.28] | 1.04 [0.86, 1.25] |
| SSW-SW | 1.27 [0.94, 1.76] | 1.23 [0.96, 1.61] | 1.04 [0.83, 1.29] | 1.02 [0.77, 1.31] | 1.03 [0.79, 1.34] | 1.07 [0.87, 1.29] | 1.07 [0.89, 1.29] | 1.05 [0.85, 1.29] |
| WSW-W | 1.14 [0.83, 1.54] | 1.16 [0.90, 1.48] | 1.08 [0.86, 1.33] | 1.07 [0.85, 1.33] | 1.06 [0.85, 1.32] | 1.06 [0.88, 1.27] | 1.07 [0.87, 1.31] | 1.05 [0.83, 1.31] |
| W-WNW | 1.09 [0.83, 1.45] | 1.14 [0.89, 1.48] | 1.12 [0.89, 1.39] | 1.10 [0.90, 1.37] | 1.08 [0.87, 1.33] | 1.08 [0.92, 1.27] | 1.08 [0.90, 1.29] | 1.07 [0.86, 1.30] |
| all | 1.19 [0.87, 1.66] | 1.19 [0.92, 1.56] | 1.07 [0.85, 1.33] | 1.05 [0.82, 1.32] | 1.05 [0.83, 1.32] | 1.06 [0.87, 1.28] | 1.07 [0.88, 1.30] | 1.05 [0.85, 1.29] |

## Both models, deep-water-equivalent, against the buoy de-shoaled

MOP at D0043 and the chain traced from D0043, both de-shoaled band by band from their start; the buoy de-shoaled from its seabed depth. Like for like between the two models; against the observation it carries the 1.9 km between the places, which the last column estimates from the chain's own two tables. Whole = the coarse bands summed.

| 46232 from | n | MOP / observed | chain at MOP's point / observed | chain at the buoy / observed | chain at MOP's point / chain at the buoy |
|---|---:|---|---|---|---|
| S | 1628 | 0.90 [0.77, 1.05] | 1.16 [0.98, 1.44] | 1.09 [0.95, 1.30] | 1.05 [0.99, 1.16] |
| SSW-SW | 2283 | 0.96 [0.85, 1.08] | 1.16 [0.98, 1.36] | 1.10 [0.95, 1.27] | 1.05 [0.99, 1.12] |
| WSW-W | 3097 | 1.03 [0.90, 1.17] | 1.16 [0.99, 1.35] | 1.09 [0.95, 1.26] | 1.06 [0.99, 1.13] |
| W-WNW | 1773 | 1.05 [0.93, 1.21] | 1.20 [1.02, 1.41] | 1.11 [0.96, 1.28] | 1.08 [1.01, 1.16] |
| all | 8782 | 0.99 [0.85, 1.14] | 1.17 [0.99, 1.38] | 1.10 [0.95, 1.27] | 1.06 [1.00, 1.14] |

By band, MOP / observed, deep-water-equivalent as heights:

| 46232 from | 16.7–26.7 s | 13.0–16.7 s | 10.0–13.0 s | 8.0–10.0 s | 6.7–8.0 s | 5.0–6.7 s | 4.0–5.0 s | 2.2–4.0 s |
|---|---|---|---|---|---|---|---|---|
| S | 0.80 [0.58, 1.06] | 0.73 [0.54, 0.93] | 0.70 [0.49, 0.91] | 0.91 [0.70, 1.14] | 0.98 [0.81, 1.19] | 1.01 [0.86, 1.20] | 1.01 [0.87, 1.18] | 1.00 [0.83, 1.17] |
| SSW-SW | 0.87 [0.64, 1.16] | 0.86 [0.69, 1.15] | 0.88 [0.71, 1.07] | 0.98 [0.79, 1.19] | 1.01 [0.83, 1.21] | 1.01 [0.87, 1.17] | 1.01 [0.88, 1.16] | 1.00 [0.79, 1.18] |
| WSW-W | 1.00 [0.73, 1.44] | 1.06 [0.82, 1.37] | 0.99 [0.82, 1.18] | 1.03 [0.86, 1.23] | 1.04 [0.87, 1.22] | 0.99 [0.85, 1.14] | 1.00 [0.83, 1.16] | 0.99 [0.69, 1.20] |
| W-WNW | 1.07 [0.79, 1.48] | 1.12 [0.88, 1.48] | 1.01 [0.84, 1.22] | 1.05 [0.88, 1.23] | 1.05 [0.89, 1.23] | 1.01 [0.87, 1.14] | 1.02 [0.88, 1.16] | 1.01 [0.77, 1.20] |
| all | 0.94 [0.67, 1.35] | 0.96 [0.69, 1.32] | 0.93 [0.68, 1.15] | 1.00 [0.81, 1.21] | 1.02 [0.85, 1.21] | 1.00 [0.86, 1.16] | 1.01 [0.86, 1.16] | 1.00 [0.75, 1.19] |

By band, chain at MOP's point / observed, deep-water-equivalent as heights:

| 46232 from | 16.7–26.7 s | 13.0–16.7 s | 10.0–13.0 s | 8.0–10.0 s | 6.7–8.0 s | 5.0–6.7 s | 4.0–5.0 s | 2.2–4.0 s |
|---|---|---|---|---|---|---|---|---|
| S | 1.48 [1.03, 2.26] | 1.50 [1.13, 1.98] | 1.21 [0.94, 1.59] | 1.05 [0.80, 1.32] | 1.01 [0.74, 1.36] | 1.01 [0.81, 1.28] | 1.03 [0.86, 1.25] | 1.02 [0.84, 1.23] |
| SSW-SW | 1.37 [0.97, 2.11] | 1.37 [1.05, 1.82] | 1.19 [0.94, 1.51] | 1.09 [0.81, 1.45] | 1.04 [0.77, 1.41] | 1.04 [0.84, 1.27] | 1.04 [0.87, 1.26] | 1.02 [0.82, 1.25] |
| WSW-W | 1.20 [0.85, 1.73] | 1.25 [0.95, 1.63] | 1.22 [0.96, 1.54] | 1.16 [0.90, 1.47] | 1.08 [0.85, 1.37] | 1.03 [0.85, 1.25] | 1.03 [0.84, 1.28] | 1.02 [0.80, 1.27] |
| W-WNW | 1.17 [0.86, 1.61] | 1.27 [0.98, 1.70] | 1.30 [1.02, 1.65] | 1.22 [0.95, 1.53] | 1.11 [0.86, 1.39] | 1.04 [0.88, 1.25] | 1.04 [0.87, 1.25] | 1.03 [0.82, 1.26] |
| all | 1.27 [0.89, 1.92] | 1.32 [1.00, 1.79] | 1.23 [0.96, 1.57] | 1.13 [0.86, 1.46] | 1.07 [0.81, 1.38] | 1.03 [0.85, 1.26] | 1.04 [0.86, 1.27] | 1.02 [0.82, 1.26] |

## Direction by band

The buoy's mean direction FROM (median) and each model's minus it (median [10th, 90th]); band-hours with the observed band ≥ 0.05 m. The chain at the buoy; MOP at its point, 1.9 km inshore, where refraction has turned the swell further.

The last column is like for like between the models: the chain traced from MOP's own point, against MOP there.

| 46232 from | band | observed | chain − observed | MOP − observed | chain at MOP's point − MOP |
|---|---|---|---|---|---|
| S | 16.7–26.7 s | 236° | -1.49 [-9.97, 10.06] | 22.80 [13.89, 33.21] | -20.97 [-26.58, -15.77] |
| S | 13.0–16.7 s | 234° | -3.21 [-9.37, 2.85] | 24.25 [17.05, 31.77] | -26.64 [-33.99, -19.74] |
| S | 10.0–13.0 s | 235° | -6.84 [-15.43, 0.67] | 27.85 [15.14, 36.45] | -26.85 [-34.57, -19.40] |
| S | 8.0–10.0 s | 255° | -2.56 [-15.71, 9.17] | 16.40 [3.10, 31.49] | -16.28 [-29.37, -4.51] |
| S | 6.7–8.0 s | 273° | 0.44 [-9.06, 8.70] | 3.10 [-3.19, 10.85] | -3.65 [-11.29, 1.20] |
| S | 5.0–6.7 s | 275° | 0.24 [-7.67, 8.02] | 1.87 [-3.59, 7.70] | -2.52 [-7.23, 2.23] |
| S | 4.0–5.0 s | 272° | 1.52 [-7.42, 10.12] | 2.03 [-4.75, 9.18] | -1.66 [-8.12, 5.05] |
| S | 2.2–4.0 s | 266° | 3.57 [-7.11, 14.52] | 3.49 [-5.13, 15.72] | -2.21 [-9.82, 5.41] |
| SSW-SW | 16.7–26.7 s | 240° | -2.56 [-10.64, 7.67] | 19.32 [10.41, 29.43] | -19.09 [-24.57, -14.21] |
| SSW-SW | 13.0–16.7 s | 241° | -4.66 [-12.01, 2.28] | 19.32 [11.26, 27.68] | -22.83 [-29.68, -15.75] |
| SSW-SW | 10.0–13.0 s | 251° | -3.90 [-13.90, 4.52] | 16.81 [5.34, 28.96] | -18.27 [-27.88, -8.06] |
| SSW-SW | 8.0–10.0 s | 267° | 0.09 [-10.56, 7.70] | 5.48 [-0.53, 18.24] | -4.48 [-17.57, 0.74] |
| SSW-SW | 6.7–8.0 s | 273° | 1.46 [-6.71, 8.95] | 2.79 [-2.87, 9.31] | -2.30 [-8.29, 1.88] |
| SSW-SW | 5.0–6.7 s | 273° | 1.47 [-5.74, 8.96] | 2.83 [-2.42, 8.42] | -1.65 [-6.79, 2.64] |
| SSW-SW | 4.0–5.0 s | 269° | 2.76 [-5.52, 10.78] | 3.37 [-2.72, 9.84] | -1.19 [-7.69, 4.54] |
| SSW-SW | 2.2–4.0 s | 263° | 4.32 [-6.17, 15.59] | 4.30 [-4.47, 17.93] | -1.86 [-9.74, 5.64] |
| WSW-W | 16.7–26.7 s | 251° | -3.15 [-11.36, 5.63] | 12.44 [3.14, 24.88] | -15.29 [-23.00, -4.45] |
| WSW-W | 13.0–16.7 s | 256° | -3.98 [-11.43, 3.13] | 9.91 [2.07, 22.17] | -13.13 [-26.23, -4.21] |
| WSW-W | 10.0–13.0 s | 265° | -0.65 [-7.18, 5.52] | 5.50 [0.45, 13.60] | -4.76 [-13.46, -0.97] |
| WSW-W | 8.0–10.0 s | 269° | 0.86 [-4.98, 6.70] | 3.56 [-1.05, 9.43] | -1.60 [-5.66, 1.75] |
| WSW-W | 6.7–8.0 s | 268° | 1.86 [-5.11, 8.69] | 3.36 [-2.11, 10.29] | -1.54 [-6.37, 2.12] |
| WSW-W | 5.0–6.7 s | 267° | 2.08 [-5.82, 9.25] | 3.64 [-2.10, 10.76] | -1.39 [-6.76, 2.73] |
| WSW-W | 4.0–5.0 s | 264° | 3.41 [-7.05, 12.63] | 4.16 [-2.96, 14.22] | -1.31 [-9.69, 4.71] |
| WSW-W | 2.2–4.0 s | 259° | 4.49 [-7.81, 19.24] | 5.25 [-5.90, 33.08] | -2.28 [-15.94, 5.99] |
| W-WNW | 16.7–26.7 s | 260° | -1.95 [-8.61, 5.07] | 6.23 [1.29, 18.88] | -6.01 [-19.19, -1.58] |
| W-WNW | 13.0–16.7 s | 265° | -0.67 [-6.54, 4.35] | 3.90 [-0.34, 13.17] | -3.52 [-14.55, 0.53] |
| W-WNW | 10.0–13.0 s | 269° | 1.34 [-2.91, 5.83] | 3.17 [-0.19, 7.13] | -1.45 [-4.53, 1.75] |
| W-WNW | 8.0–10.0 s | 271° | 1.94 [-2.53, 6.67] | 2.59 [-1.15, 6.60] | 0.00 [-2.94, 2.87] |
| W-WNW | 6.7–8.0 s | 271° | 2.47 [-3.27, 8.90] | 2.17 [-2.34, 7.95] | -0.64 [-3.84, 2.72] |
| W-WNW | 5.0–6.7 s | 269° | 2.34 [-4.57, 9.24] | 2.70 [-2.26, 9.56] | -0.93 [-5.36, 3.04] |
| W-WNW | 4.0–5.0 s | 265° | 2.88 [-6.15, 13.02] | 3.37 [-3.57, 13.13] | -1.12 [-8.35, 4.68] |
| W-WNW | 2.2–4.0 s | 260° | 3.65 [-9.70, 18.29] | 4.01 [-7.21, 27.75] | -2.73 [-12.82, 5.44] |
| all | 16.7–26.7 s | 247° | -2.45 [-10.46, 6.90] | 15.60 [3.59, 28.46] | -17.28 [-24.14, -4.22] |
| all | 13.0–16.7 s | 250° | -3.22 [-10.56, 3.35] | 14.77 [2.12, 27.21] | -18.76 [-29.42, -2.86] |
| all | 10.0–13.0 s | 257° | -1.69 [-11.10, 5.01] | 8.37 [1.10, 29.42] | -8.47 [-28.21, -0.54] |
| all | 8.0–10.0 s | 266° | 0.70 [-8.06, 7.35] | 4.61 [-0.65, 19.60] | -2.51 [-18.46, 1.69] |
| all | 6.7–8.0 s | 271° | 1.70 [-6.00, 8.83] | 2.88 [-2.56, 9.71] | -1.76 [-7.50, 2.06] |
| all | 5.0–6.7 s | 271° | 1.70 [-6.04, 9.01] | 2.87 [-2.53, 9.40] | -1.53 [-6.61, 2.75] |
| all | 4.0–5.0 s | 267° | 2.73 [-6.46, 11.84] | 3.40 [-3.45, 11.42] | -1.27 [-8.48, 4.72] |
| all | 2.2–4.0 s | 262° | 4.11 [-7.51, 17.12] | 4.32 [-5.58, 23.28] | -2.22 [-11.92, 5.66] |
