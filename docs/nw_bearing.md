# 46232's north-west bearing

`python -m forecast.nwbearing` (full, ~10 min) or `--quick` (sections 1–3
and 6). BRIEFING §38 carries the reading; this is the output it was read
from, run 2026-10-04 on the archive to 2026-10-04 06Z, with the Channel
Islands charted the same day (`shoreline.yml`, regions
`channel_islands_south` and `channel_islands_north`, approach band).

What it asks, in one line each:

1. Is 46232's −52 to −74° north-west gap the buoy, or the average? (mean
   heading against its own westerly lobe)
2. Is it the hull? (the same at 46258, a Waverider, and 46086, an NDBC hull)
3. Is it the Channel Islands' edges? (every island's edges from each buoy)
4. Does it reach the beach? (each break's 5 m height with the lobe turned or
   removed, and where the breaks' westerly rays leave deep water)
5. Does it reach the page? (shown train headings against their own lobes)
6. Would a finer coast change a hurricane's land-path verdict?

It reports and never edits. Nothing measures the breaks: section 4 is the
chain's sensitivity to its input, not an error at the beach.

```
1-2. The westerly lobe at each shadowed buoy, against 46047's north-west lobe
   245 north-west hours at 46047 on 15 days (08-23, 09-11, 09-12, 09-13, 09-14, 09-16, 09-19, 09-23, 09-24, 09-25, 09-26, 09-29, 09-30, 10-01, 10-02)
   46232: 210 h on 8 days | westerly lobe median 270° (IQR 253-278) | slope on 46047's -0.17 | lobe − 46047 -39° | mean heading − 46047 -77°
   46258: 212 h on 10 days | westerly lobe median 286° (IQR 280-292) | slope on 46047's +0.15 | lobe − 46047 -24° | mean heading − 46047 -71°
   46086: 100 h on 8 days | westerly lobe median 279° (IQR 261-286) | slope on 46047's -0.19 | lobe − 46047 -31° | mean heading − 46047 -61°

3. The charted Channel Islands' edges, as seen from each buoy
   8 islands from enc_approach_88 (Anacapa, San Clemente, San Miguel, San Nicolas, Santa Barbara I., Santa Catalina, Santa Cruz, Santa Rosa)
   46047: Anacapa 2.7-5.3; Santa Barbara I. 20.9-21.8; Santa Catalina 36.0-48.9; San Clemente 51.2-67.9; San Miguel 334.8-338.4; Santa Rosa 339.4-346.8; Santa Cruz 348.7-0.4; San Nicolas 357.6-6.0
      lobe 310°: 25.3° anticlockwise of San Miguel's nearest edge
   46232: San Clemente 288.8-298.4; San Nicolas 292.5-294.1; San Miguel 301.7-303.2; Santa Rosa 302.1-305.5; Santa Barbara I. 305.2-306.3; Santa Cruz 306.2-311.5; Anacapa 312.1-313.4; Santa Catalina 313.1-318.6
      lobe 270°: 18.3° anticlockwise of San Clemente's nearest edge
   46258: San Clemente 274.0-287.8; San Nicolas 286.2-288.1; San Miguel 298.2-299.8; Santa Rosa 298.3-301.9; Santa Barbara I. 299.3-300.5; Santa Cruz 302.4-307.9; Santa Catalina 305.8-312.5; Anacapa 308.5-309.8
      lobe 286°: 0.3° clockwise of San Nicolas's nearest edge, INSIDE its arc
   46086: San Nicolas 300.2-302.4; San Miguel 307.6-309.6; Santa Rosa 308.9-312.8; San Clemente 311.3-319.7; Santa Cruz 314.2-321.2; Santa Barbara I. 318.5-319.9; Anacapa 322.3-324.1; Santa Catalina 333.7-344.3
      lobe 279°: 21.2° anticlockwise of San Nicolas's nearest edge

4. What 46232's westerly lobe carries into each break, on the same hours (energy at 5 m)
   coronado_north (n=231)
      share from 255-345° offshore, 10-25 s: median +6.2% (10th +3.2, 90th +11.9)
      Hs with that lobe absent: median -3.1% (10th -6.1, 90th -1.6)
      Hs with the lobe turned -9°: median +2.4% (10th +0.6, 90th +5.3)
      Hs with the lobe turned +9°: median -0.9% (10th -3.2, 90th +0.1)
      Hs with the lobe turned +18°: median -2.3% (10th -5.5, 90th -0.8)
   coronado_center (n=231)
      share from 255-345° offshore, 10-25 s: median +24.2% (10th +13.8, 90th +35.8)
      Hs with that lobe absent: median -12.9% (10th -19.9, 90th -7.1)
      Hs with the lobe turned -9°: median +4.3% (10th +1.9, 90th +8.3)
      Hs with the lobe turned +9°: median -3.8% (10th -7.4, 90th -1.6)
      Hs with the lobe turned +18°: median -6.5% (10th -10.9, 90th -3.4)
   coronado_south (n=231)
      share from 255-345° offshore, 10-25 s: median +36.1% (10th +23.0, 90th +45.2)
      Hs with that lobe absent: median -20.1% (10th -26.0, 90th -12.2)
      Hs with the lobe turned -9°: median +1.0% (10th -1.9, 90th +5.7)
      Hs with the lobe turned +9°: median -4.0% (10th -7.3, 90th -1.2)
      Hs with the lobe turned +18°: median -7.1% (10th -11.6, 90th -3.6)
   coronado_north: 241 westerly rays (10-20 s) leave deep water a median 26 km from 46232 and 25 km from 46258
   coronado_center: 458 westerly rays (10-20 s) leave deep water a median 25 km from 46232 and 25 km from 46258
   coronado_south: 627 westerly rays (10-20 s) leave deep water a median 25 km from 46232 and 25 km from 46258

5. Shown train headings against their own energy's lobes (1081 spectra at 46232)
   buoy              1968 swell trains | heading > 20° from every lobe holding 20%: 455 (23.1%) on 424 hours | two lobes or more: 475 (24.1%)
   coronado_north    2601 swell trains | heading > 20° from every lobe holding 20%: 111 (4.3%) on 107 hours | two lobes or more: 175 (6.7%)
   coronado_center   2701 swell trains | heading > 20° from every lobe holding 20%: 266 (9.8%) on 234 hours | two lobes or more: 555 (20.5%)
   coronado_south    2505 swell trains | heading > 20° from every lobe holding 20%: 1160 (46.3%) on 743 hours | two lobes or more: 1392 (55.6%)
   peak strip (a1 of 46232's peak bin): > 20° from every lobe on 85 of 1081 hours (7.9%)

6. Hurricane paths and the coast's resolution (forecast.landpath, Natural Earth 1:10m on 0.05°)
   708 fix-to-buoy paths (>= 64 kt). Verdicts that change with the coast moved:
      seaward 5 km: 3 (0.4%)
      landward 5 km: 3 (0.4%)
      seaward 10 km: 4 (0.6%)
      landward 10 km: 8 (1.1%)
   which: Genevieve 07-26 00Z->46086, Genevieve 07-26 12Z->46232, Polo 09-25 00Z->46047, Polo 09-25 18Z->46086, Polo 09-26 00Z->46232, Polo 09-26 06Z->46232, Polo 09-28 18Z->46232, Polo 09-29 00Z->46047, Rachel 10-02 06Z->46086, Rachel 10-02 12Z->46086, Rachel 10-02 18Z->46232, Rachel 10-03 00Z->46232
```
