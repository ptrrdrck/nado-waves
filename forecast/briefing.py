"""The LIVE tab's Briefing: what has happened since sunset, what is arriving.

    python -m forecast.briefing        # data/live/briefing.json

Owner's request, 2026-10-16: a lifeguard's morning read, so the cards need
not be put together by hand. It sits above the LIVE cards in its own fold.
Every number in it is already on the page or measured from what the page
reads; what it adds is the comparison across time and across cards, each
story over its own clock:

- **Standing on**: each feed's stamp, anything overdue, any hour since
  sunset 46232 has no spectrum for. 46232 dark stands every break story down.
- **Since sunset**: each break's breaking height at the last sunset and now,
  rose / dropped / little change, which break leads then and now, each
  break's biggest train then and now, and the leading break's biggest
  calculation step.
- **Arriving**: Origin's arrivals at the breaks (current, and ended since
  sunset), each running ridge's period projected `PERIOD_AHEAD_H` ahead; the
  hurricanes NHC tracks, due at the breaks by deep-water speed from their
  fixes (best track, then NHC's forecast, each named as such) until their
  last open-water fix's swell has passed; and 46047's west or north-west
  sector risen since sunset, due at 46232 and the breaks by deep-water speed
  (`forecast.upstreamlag`, BRIEFING §42).
- **Wind**: the KNZY reading each hour since sunset, per break by the card's
  verdict, and the newest; local chop now.
- **Tide**: the card's next turns (predicted), the departure, the phase.
- **Buoys and season**: 46047's and 46086's trains now, two directions at
  once where a buoy holds them, and how the leading break's height ranks in
  the archive.

**Never the model.** GFS-Wave and its ensemble are the Forecast tab's; the
briefing is the LIVE chain plus NHC's fixes, the one input the owner allowed
(2026-10-16) because the hurricane gate is already checking it.

**Every word that judges is measured** (`forecast.briefingreport`,
`docs/briefing_thresholds.md`): a slot is said only where it is right ≥ 85%
of the times it fires. The wind's onshore habit failed and is not carried.

Units stay metres and knots here; the page converts and words it
(`app/forecast.html`, `docs/briefing_wording.md`). This module is its own
file and its own step: a context buoy never enters `now.json` or the chain.
"""

from __future__ import annotations

#: Rose / dropped: the 3-hour medians at sunset and now differ by at least
#: this share (measured: the smallest step right ≥ 85% on every break and
#: span 6–24 h; 10% held from 12 h but north reached only 83% over 6 h).
CHANGE_SHARE = 0.15

#: Spans shorter than this were not measured; the story then gives the two
#: readings with no word between them.
MIN_SPAN_H = 6

#: A break leads when its 3-hour median is ahead of the next by this share
#: (measured: 3% is the smallest right ≥ 85%, 86.3%; 5% so the two heights
#: differ on screen at 0.1 ft).
LEAD_MARGIN = 0.05

#: A running ridge's period is projected this far ahead, in whole seconds
#: (measured: within 1 s on 9 of 9 at 12 h; 4 of 5 at 24 h).
PERIOD_AHEAD_H = 12
