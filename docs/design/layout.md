_Read when you need to know what a module or data directory holds beyond CLAUDE.md's short map._

# Layout (full)

Moved verbatim from CLAUDE.md on 2026-11-14 (the context-reduction
restructure); CLAUDE.md keeps the one-line rule and points here.

## Layout

    collector/          data pipeline: NDBC archiving, revisions, station
                        status (stations.json is a COLLECTION list, not a
                        ranking — see forecast/siting.py), historical backfill,
                        GFS-Wave bulletins, localwind.py (the NWS forecast
                        grid's hourly wind at Coronado, fetched by the
                        forecast build, not archived), gefswave.py (GEFS-Wave's
                        31-member bulletin at 46232: mean and spread, no
                        direction — BRIEFING §35),
                        probe_spectra.py (are directional spectra reachable?),
                        spectra.py (archive them: 46232, 46047 and 46086
                        hourly (`--hourly`; HOURLY_STATIONS, held by a
                        test to the union of Origin's and the hurricane
                        gate's readers, so dropping a reader never drops a
                        collection) —
                        and 46258 from collect.yml; context for checks, read
                        by no height), wind.py (KNZY),
                        wavespec.py (WW3's own spectrum + wind, not archived),
                        tide.py (9410170 — measured, hourly predicted, and
                        CO-OPS's own hilo TURNS in a third file),
                        harcon.py (NOAA's harmonic constants for 9410170,
                        as served, monthly; the phase fold's — §41),
                        tidestations.py (every CO-OPS station near the breaks,
                        their offsets and datums, and a 30-day comparison
                        window — run on Actions; BRIEFING §32),
                        shoreline.py (NOAA's ENC coastline, by named REGION —
                        `coronado` carries the break chords, `baja` carries
                        the islands and the Mexican coast, `point_loma` the
                        tip, `channel_islands_south`/`_north` the eight
                        Channel Islands, read by no chain (§38) — run on
                        Actions),
                        enc_layers.py (what else the charts carry: the jetty,
                        the soundings, a finer coastline — BRIEFING §22),
                        beachlog.py + beachlog_import.py (the observation log),
                        stationdepth.py (each shown buoy's water depth,
                        read off NDBC's station page, monthly ->
                        data/station_depth.json; Actions only),
                        nwsalerts.py (NWS's alerts for CAZ043 and PZZ750,
                        each one's document byte for byte, once by its id
                        -> data/alerts/; Actions only),
                        sharklab.py + sharklab.json (the Coronado
                        shark-monitoring buoys' receiver temperatures from
                        CSULB Shark Lab's ERDDAP, a trailing 72 h at most
                        hourly (MIN_INTERVAL_MIN: the lab's data changes
                        nightly), or once from a date (the workflow's
                        sharklab_backfill_from), each reading once ->
                        data/sharklab/;
                        the registry holds hub and receiver IDs, never a
                        coordinate; plain http, Actions only),
                        probe_sharklab.py (what that ERDDAP serves; its
                        --hubs history and --temps comparison — BRIEFING §47),
                        beachwater.py + beachwater.json (the county's beach
                        water quality at each break's station, through the
                        site's OutSystems screen services: samples, the
                        posting report's advisories / closures / warnings,
                        and each station's status from the events in force
                        (the map's PriorityMax a cross-check), each kept once, every
                        collection -> data/beach_water/; the registry holds the
                        county's station codes and site ids, never a
                        coordinate; Actions only — BRIEFING §48),
                        probe_beachwater.py (how that site serves its data,
                        and Coronado's records through the collector's
                        client; a push to a claude/ branch that changes it
                        runs it),
                        nhcforecast.py (NHC's official forecast, the OFCL
                        lines of each live storm's a-deck, Actions only —
                        unverified against a live file until its first run),
                        bathymetry.py (USGS CoNED seabed, regional 32 m and
                        nearshore 8 m, NAVD88; the MSL offset is fetched from
                        CO-OPS on Actions — needs requirements-precompute.txt;
                        and GMRT's outer 90 m and `context` 400 m grids, the
                        latter the map's only, read by no chain, fetched by
                        bathymetry-context.yml)
    app/forecast.html   the app surface — Coronado's three breaks       [built]
    app/docs.html       the documentation, the live page's one link: every
                        card, chart and calculation; one contents pill built
                        from its own headings, with full-text search, its
                        panel growing out of it (at the bottom on a phone, at
                        the top on a wide screen; owner's design, 2026-10-29,
                        replacing the sidebar and drawer); the caveat, the cycle line and both chains'
                        standing-on blocks; the model-geometry drawing,
                        filled by `forecast.geomviz` from spots.json and never
                        hand-edited with coordinates; and ONE worked hour
                        through the chain that `tests/test_docs.py` rebuilds
                        from the archive. Shipped by `forecast.publish` in
                        BOTH bundles. Never links to the observation log.
                        Replaced info.html and geometry.html 2026-10-02
                        (owner's decision); `publish.RETIRED` deletes them
                        from the public site
    app/docs_wording.md the page's prose by section id, for the owner to edit
                        on a branch: generated by `python -m forecast.docswording`,
                        pinned to the page by a test. Edits are carried INTO
                        docs.html by hand and the file regenerated; `>>`
                        lines are notes to Claude, never page text
    app/vendor/         MapLibre GL JS 4.7.1 and its BSD-3 licence, for the
                        Swell card map; shipped beside the page
    app/beachlog.html   the phone form, owner build (shared store)
    app/beachlog-observer.html  same file, observer build — no sign-in, entries
                        stay on the phone and are handed back as text. The two
                        differ only in <title>; a test enforces it. The repo CSV
                        stays the system of record for both.
    forecast/
      geometry.py       which bearings reach each beach          [built]
      transform.py      spectrum -> energy through the aperture   [built]
      spreadmethod.py   Fourier vs maximum-entropy D(f, θ) from the same
                        four buoy moments, over the archive; reports,
                        never edits (BRIEFING §28)              [built]
      raytrace.py       PRECOMPUTE (numpy): backward rays from the 5 m
                        contour off each break to deep water over the seabed
                        grids — refraction and shoaling (S·c·cg invariant),
                        islands' shelves included; diffraction at the islands,
                        the Point Loma tip and the Baja tangent, hard and soft
                        per ray; bottom friction per ray; plus each break's
                        wind fetch and cross-shore profile.
                        Writes data/nearshore/; never imported by the
                        forecast                                  [built]
      nearshore.py      carries a spectrum through those tables, pure
                        Python; local fetch-limited chop, fresh over
                        closed fetches and grown on over the open water
                        between the buoy and the break; reports
                        against the aperture                        [built]
      bending.py        which way each offshore heading arrives in 5 m,
                        per break, into docs.html's swell-bend table [built]
      surfzone.py       5 m to the break on each profile at the tide,
                        Battjes–Janssen, pure Python                [built]
      tidesite.py       the bay gauge's level carried to the open coast
                        (x0.944, measured against La Jolla), and the
                        measured departure from the epoch prediction [built]
      live.py           the live forecast, Coronado only          [built]
      now.py            the OBSERVED reading, measurements only    [built]
      forecastlog.py    the permanent record of what each build said,
                        the 48 h of it the page reads back, and the
                        last eight runs' lines for the Runs chart  [built]
      measured.py       the observed chain rebuilt for each past hour:
                        exact-stamp spectrum, wind and tide as of then [built]
      series.py         the same, every hour for the last week, with the
                        south-less-north, window ratio and %K the Now
                        tab's chart draws; one rebuild feeds both files;
                        and `--archive`, every archived hour into
                        data/series/ (series-archive.yml only)      [built]
      windtide.py       the measured wind and tide each hour, and the
                        next day's predicted tide, for the Wind and Tide
                        cards' charts; read from the archives   [built]
      tidephase.py      the Tide card's phase fold: spring / neap and the
                        declination from NOAA's constants, the Moon's
                        events, the card's turns as evidence; pure Python;
                        never a turn or a height for the card     [built]
      tidephasereport.py its thresholds measured over 19 years; reports,
                        never edits (BRIEFING §41)                 [built]
      tidephasewording.py its wording, run from the page's own code into
                        docs/tide_phase_wording.md; --check         [built]
      moon.py           the Moon's phases, distance and declination
                        (Meeus ch. 47), pure Python                 [built]
      daylight.py       sunrise and sunset at the center break, for the
                        Tide charts' night shading; computed, not fetched [built]
      skyline.py        PRECOMPUTE (numpy): Point Loma's skyline from each
                        break off CoNED's land, into data/nearshore/ [built]
      sunset.py         the Sun card: sunrise, and each break's sunset
                        behind Point Loma or in the sea, and its season;
                        pure Python (Meeus ch. 25)                [built]
      modelbias.py      GFS-Wave's bias at 46232 through each break's
                        windows; reports, never edits              [built]
      ensemble.py       GEFS-Wave's mean and spread against 46232: how
                        often the buoy fell inside the spread, and the
                        page's Ensemble block; reports, never edits  [built]
      exposurebias.py   GFS-Wave's bias from the unshadowed 46047 to the
                        most shadowed buoy, and the model's shadow against
                        the measured one; reports, never edits     [built]
      publish.py        the public delivery bundle                 [built]
      units.py          ft/mph first, m/kt in parentheses -- display only
      tideturns.py      the next high/low, and why its direction is not
                        differenced from the measured level      [built]
      tiderate.py       the LIVE tide's measured rate: the gauge's last
                        30 min, slack under 0.10 m/h or across a predicted
                        turn; and its measurements (BRIEFING §50)  [built]
      trainsplit.py     how a spectrum is split into trains: a synthetic
                        control with a known answer (buoy noise, maximum
                        entropy, as the chain reads it) and the archive,
                        period-only vs 10° watershed vs shipped; reports,
                        never edits (BRIEFING §40)                [built]
      nwbearing.py      46232's north-west bearing: the mean against its
                        lobes, the hull control, the Channel Islands' edges,
                        what the lobe carries into each break, shown train
                        headings against their own lobes; reports, never
                        edits (BRIEFING §38)                      [built]
      shorenormal.py    surveyed shore normals vs the digitised chords,
                        swept over scale; reports, never edits    [built]
      blockeredge.py    a blocker's edges read off the charted coast, against
                        what spots.json claims; reports, never edits  [built]
      fill.py           the map's fill on LIVE: each train's 5 m energy
                        credited ray by ray, checked against the chain's
                        height, into data/live/fill.json            [built]
      seabedvector.py   PRECOMPUTE (numpy, contourpy, shapely): the Swell
                        card map's seabed as vectors from the bathymetry
                        grids, into data/seabed_vector/; `--check`  [built]
      mapdata.py        the map's map.json: geomviz's model, the other
                        buoys, the tile manifest                  [built]
      geomviz.py        draws the vertices the model uses, the ray to each
                        edge's vertex, and the distances between them, into
                        docs.html                                  [built]
      docswording.py    docs.html's prose as app/docs_wording.md, by
                        section id, for editing; --check            [built]
      siting.py         which BUOYS observe the swell that reaches it  [built]
      spots.json        breaks and blockers    [Coronado digitised; others not]
      swell.py          great circles, bearings, group velocity
      utm.py            lat/lon <-> UTM 11 metres, pure Python (the grids' CRS)
      stats.py          load_column, least_squares, rmse, circular means
      dispersion.py     the 1/T dispersion fit, and arrivals in a buoy's
                        dominant period (historical files only)
      forensics.py      a past swell's origin off the historical record;
                        "seen upstream" tests no distance (BRIEFING §37)
      buoys.py          the LIVE tab's Buoys tab below 46232: 46047 and
                        46086 at the buoy, not carried to any break, each its
                        own countdown and words                    [built]
      rose.py           one spectrum's height and period rose by compass
                        sector, for the Buoys tab's six-hour loop   [built]
      alerts.py         NWS's coast and ocean alerts: which are in force,
                        and over which hours; the Briefing's top line and
                        the Forecast tab's, alerts.json             [built]
      briefing.py       the LIVE tab's Briefing: built every collection,
                        updated when its alert, swell, tide or water quality
                        words change, each
                        update kept in data/briefings/             [built]
      trainmatch.py     a break's train to the buoy train it is, for the
                        Briefing's one line a swell; and the archive and
                        known-answer control that chose it; reports  [built]
      windsea.py        which trains are wind sea: wave age against KNZY's
                        AND 46086's measured wind on LIVE, GFS-Wave's own
                        wind (or its bulletin's flags) on Forecast; and the
                        measurement behind it; never a period (§51) [built]
      trainmerge.py     a break's row that is two buoy trains: how often,
                        and what dividing it at 20% / a third does, on the
                        archive and a known-answer control (BRIEFING §49);
                        and `--brackets`, which rows are one swell (§49b);
                        reports, never edits                       [built]
      briefingreport.py its thresholds, measured; reports, never edits
      briefingwording.py its wording, run from the page's own code into
                        docs/briefing_wording.md; --check           [built]
      stormdue.py       when a storm's swell is due at each break, from NHC's
                        best track and official forecast             [built]
      upstreamlag.py    46047 → 46232 → the breaks: deep-water lag, checked
                        against the archive; reports (BRIEFING §43)  [built]
      origin.py         the LIVE tab's Origin: each train's dispersion
                        ridge in 46232's spectrum, bearing at 46047
                        [built]
      originreport.py   the measurements behind it; reports, never edits
      originwording.py  every wording Origin can show, run from the page's own
                        code into docs/origin_wording.md; --check     [built]
      origintracks.py   readings against NHC's best tracks, by position
      originhistory.py  the Origins chart's marks: every arrival and every
                        named moment over the archive, and the page's
                        file from it each collection             [built]
      stormtrack.py     each hurricane run forward to the buoys, with
                        controls, backtest and GFS-Wave cross-check; and
                        `live`, the card's "Hurricane X" gate       [built]
      landpath.py       does a swell's great circle cross land?   [built]
      verify.py         bias, RMSE, scatter index, calibration, band coverage
      residual.py       is the remaining error recoverable? (it was not, before)
      beachverify.py    does the log agree with the geometry, and the control
    data/live/          forecast.json, now.json, measured.json, series.json,
                        series_all.json, windtide.json, origins.json,
                        buoys.json, briefing.json, alerts.json, fill.json
                        and map.json, what the app surface
                        reads (derived, gitignored)
    data/alerts/        YYYY/<oid>.json: every NWS alert the active listing
                        returned for CAZ043 and PZZ750, as NWS served it,
                        written once (collector.nwsalerts, its one writer)
    data/sharklab/      <receiver>/YYYY-MM.csv: each Coronado receiver's
                        ambient_temperature and tilt, once per device stamp,
                        with first_seen_utc (a backfill's rows carry the
                        backfill's: state.json lists those runs, to leave out
                        of any arrival lag); hubs.json, each hub's receiver
                        and the break its newest fix in the water serves;
                        state.json, the last fetch (collector.sharklab, its
                        one writer)
    data/beach_water/   samples/<station>.csv, each sample once by the
                        county's id (date and time Pacific, as given);
                        events.csv, the three stations' advisories, closures
                        and warnings, a moved lift time a new row;
                        status.csv, each status change as first seen;
                        state.json, the last read and each station's status
                        (collector.beachwater, its one writer)
    data/briefings/     YYYY-MM.jsonl: every Briefing update, as built and as
                        worded (18–22 Oct: the Morning / Midday issues).
                        PERMANENT, append-only, one writer ("Record the
                        briefing"); the page's briefing.json is each build
                        settled against its newest line
    data/series/        46232/YYYY-MM.csv: the observed chain for every
                        archived hour, and 46232_origins.json, the Origins
                        chart's marks, both rebuilt whole with today's chain
                        by series-archive.yml, its only writer. DERIVED but
                        tracked: rebuilding a year costs minutes a
                        collection cannot spend (see Infrastructure)
    data/forecast_log/  46232/YYYY-MM.csv: what every forecast build said,
                        3-hourly, one row per site (forecast.forecastlog).
                        PERMANENT and never published: the one input to the
                        bias report nothing can rebuild. 46232_shown/ is each
                        build's hours IN FULL for the 48 h after it was
                        published (JSONL, ~85 KB a build): what a past card is
                        drawn from; `seed-shown.yml` fills it for the first
                        builds from the delivery repo's published history,
                        headline-checked. 46232_recomputed/ is past cycles
                        rebuilt later (model-bias.yml), kept apart
    data/spectra/       NDBC directional spectra, five components per station
    data/wind/          KNZY       data/tide/  NOAA 9410170, three files:
                        _observed (measured), _predicted (hourly harmonic),
                        _turns (the harmonic model's own highs and lows),
                        and _harcon.json (NOAA's harmonic constants, as
                        served: the phase fold reads them)
    data/shoreline/     NOAA ENC coastline, one file per chart band AND
                        region. `_coronado` (harbour 904 pts, approach 689,
                        coastal 312) and `_baja` (harbour 2428, approach 3691,
                        coastal 1431 - the islands and the Mexican coast to
                        32.383, where NOAA's charts stop) and `_point_loma`
                        (harbour 2815, approach 1612, coastal 879 — the
                        harbour band is holed at the tip), and
                        `_channel_islands_south`/`_north` (the eight Channel
                        Islands; context, read by no chain). A CHART product,
                        generalised, not survey-grade MHW. Every file is
                        clipped by its own query envelope on all four edges,
                        which is why the region is in the filename.
    data/bathymetry/    CoNED seabed grids (.npz, decimetres NAVD88) + a JSON
                        sidecar each. Does NOT cover the Coronado Islands or
                        Baja (south of 32.49 N); those stay charted blockers.
    data/seabed_vector/ the Swell card map's seabed, <grid>.geojson and
                        manifest.json (forecast.seabedvector); derived but
                        tracked, redrawn by the bathymetry workflows
    data/nearshore/     per-break transfer tables from forecast.raytrace:
                        <break>.csv (one row per period x 0.5° heading at
                        5 m: hard-edged gain, diffracting gain and the heading
                        each reads, and the friction factor of each),
                        <break>.json (start point, datum, grids),
                        <break>_fetch.csv (open water upwind, per 1° of wind),
                        <break>_profile.csv (depth below MSL every 2 m from the
                        start point to dry sand, along the normal)
                        <break>_skyline.csv (the land's angle above the eye
                        every 0.02° of azimuth, 225–315°; forecast.skyline)
                        <break>_paths.json (every clearing ray's traced path
                        and minutes after 46232, 0.03–0.25 Hz, for the map's
                        fill; raytrace --paths-only)
    data/beach_log/     the verification series — human observation  [EMPTY]
    data/historical/    3 years hourly, 15 stations — irreplaceable
    data/ensemble_forecasts/ GEFS-Wave's bulletin at 46232, 00Z 2023–2025 (means
                        only) and every cycle from 2026 (with spread), leads
                        to +240 h; exceedance shares by COLUMN, not label
    data/wave_forecasts/ 1,096 archived GFS-Wave 00Z cycles/station, 2023–2025,
                        with partitions: 46047 (unshadowed, the reference)
                        and five shadowed buoys, 46086, 46258, 46232, 46224,
                        46222

`forecast/stats.py` was trimmed to the four helpers this project uses
(`load_column`, `angular_difference`, `least_squares`, `rmse`) when the
repository went public. The predecessor's scoring work — `assess`,
`contested_skill`, the feature-group fits and the CLI — is gone, along with
`collector/forecast.py` and its probes, which archived an Open-Meteo water
temperature forecast as a candidate scoring baseline. `LEAGUE_TZ` is now
`LOCAL_TZ`; it was always just America/Los_Angeles.
