"""GFS-Wave's own directional spectrum and wind at a station.

Run: ``python -m collector.wavespec --cycle 2026-09-18T00`` — on Actions or a
session; the NOAA Open Data bucket is one of the few hosts not denied at
CONNECT (BRIEFING §8).

WAVEWATCH III publishes, per cycle, a spectral file for every station it
carries: a full ``nfreq × ndir`` energy grid at each forecast hour, plus the
10 m wind and the surface current in each record's header. That gives this
project two things the bulletin cannot:

* **Forecast wind**, with no second data source to wire up.
* **A measured directional spread**, which retires the assumed 20°/35° that
  BRIEFING §11 calls the least defensible number in the forecast chain.

**Nothing from here is archived.** Every cycle back to 2021-04 is still served
from the bucket — checked 2026-09-19 — so CLAUDE.md's rule applies: do not
write an "archive it now" job for history that is not actually unrecoverable.
The derived per-break numbers are what gets stored, in the forecast itself.

Cost, measured 2026-09-19: the whole tar is 1.73 GB, but 46232 is member 330
of 918, so streaming it and stopping at the right member needs **617 MB and
about ten seconds** — the remaining 1.1 GB is never pulled.

**Two direction conventions live in this one file, and they disagree.**
Measured against the same cycle's bulletin and against KNZY:

* the spectral grid's directions are **TOWARD** (4.5° when flipped against the
  bulletin's dominant partition, 175.5° as-is), so they are flipped once here;
* the header's wind direction is **FROM** (29.4° as-is against KNZY versus
  150.6° flipped, and 12.6° against the wind-sea partition versus 167.4°), so
  it is not touched.

Getting either backwards is the fault CLAUDE.md measures at 151°. Both are
pinned by tests.
"""

from __future__ import annotations

import argparse
import gzip
import io
import math
import sys
import tarfile
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone

from .ndbc import USER_AGENT

BASE_URL = "https://noaa-gfs-bdp-pds.s3.amazonaws.com"

#: Directions in the spectral grid are the direction waves travel TOWARD.
#: Everything else in this project is degrees FROM.
GRID_IS_TOWARD = True


class WaveSpecError(RuntimeError):
    pass


@dataclass
class SpecRecord:
    """One forecast hour: the grid, plus the wind that is driving it."""

    time: datetime
    #: Energy density E(f, θ) in m²/Hz/radian, indexed [direction][frequency].
    energy: list[list[float]]
    #: Degrees FROM, already flipped out of the file's TOWARD convention.
    directions: list[float]
    frequencies: list[float]
    depth_m: float
    wind_speed_ms: float
    #: Degrees FROM — the file's own convention, not flipped.
    wind_from_deg: float
    current_ms: float
    current_toward_deg: float

    @property
    def wind_kt(self) -> float:
        return self.wind_speed_ms * 1.94384


def spec_tar_url(cycle: datetime) -> str:
    day, hour = cycle.strftime("%Y%m%d"), f"{cycle.hour:02d}"
    return f"{BASE_URL}/gfs.{day}/{hour}/wave/station/gfswave.t{hour}z.spec_tar.gz"


class _Counting(io.RawIOBase):
    """Wraps the socket so the caller can report what the fetch actually cost."""

    def __init__(self, fh):
        self.fh, self.count = fh, 0

    def readable(self) -> bool:
        return True

    def readinto(self, buffer) -> int:
        chunk = self.fh.read(len(buffer))
        if not chunk:
            return 0
        self.count += len(chunk)
        buffer[: len(chunk)] = chunk
        return len(chunk)


def fetch_station_spec(
    station: str,
    cycle: datetime,
    *,
    timeout: float = 600.0,
    opener=urllib.request.urlopen,
) -> tuple[str, int]:
    """Pull one station's spectral file out of the cycle tar, stopping there.

    Returns (text, compressed bytes read). The tar is read as a gzip stream and
    abandoned as soon as the member is found; gzip has no random access, so
    "stop early" is the only saving available and it is a large one.
    """

    url = spec_tar_url(cycle)
    target = f"gfswave.{station}.spec"
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})

    try:
        with opener(request, timeout=timeout) as response:
            counter = _Counting(response)
            stream = gzip.GzipFile(fileobj=io.BufferedReader(counter, 1 << 20))
            with tarfile.open(fileobj=stream, mode="r|") as archive:
                for member in archive:
                    if member.name.lstrip("./") != target:
                        continue
                    handle = archive.extractfile(member)
                    if handle is None:
                        break
                    return handle.read().decode("utf-8", errors="replace"), counter.count
    except urllib.error.HTTPError as error:
        raise WaveSpecError(f"{url}: HTTP {error.code}") from error
    except (urllib.error.URLError, OSError, tarfile.TarError, EOFError) as error:
        raise WaveSpecError(f"{url}: {error}") from error

    raise WaveSpecError(f"{url}: no member {target}")


def parse_spec(text: str, *, limit_hours: int | None = None) -> list[SpecRecord]:
    """Parse a WAVEWATCH III station spectral file.

    Layout: a header naming `nfreq`, `ndir` and the point count; the frequency
    axis then the direction axis, both run together across lines; then, per
    time, a date line, a station line carrying depth/wind/current, and the
    energy grid written **direction-major** — `ndir` blocks of `nfreq`.

    The grid ordering is not documented in the file and is easy to get
    backwards, which silently produces a plausible spectrum with the wrong
    shape. It was settled by measurement: direction-major reproduces the same
    cycle's bulletin `Hst` to 0.800 m against 0.80 m, where frequency-major
    gives 0.876 m.
    """

    lines = [ln for ln in text.splitlines() if ln.strip()]
    if not lines or "WAVEWATCH" not in lines[0]:
        raise WaveSpecError("not a WAVEWATCH III spectral file")

    try:
        counts = lines[0].split("'")[2].split()
        n_freq, n_dir = int(counts[0]), int(counts[1])
    except (IndexError, ValueError) as exc:
        raise WaveSpecError(f"cannot read the header counts: {exc}") from None

    axis: list[float] = []
    index = 1
    while len(axis) < n_freq + n_dir and index < len(lines):
        axis += [float(v) for v in lines[index].split()]
        index += 1
    if len(axis) < n_freq + n_dir:
        raise WaveSpecError("frequency and direction axes are incomplete")

    frequencies = axis[:n_freq]
    # Flipped out of TOWARD into the degrees-FROM convention everything else
    # in this project uses. See the module docstring for the measurement.
    directions = [
        (math.degrees(value) + (180.0 if GRID_IS_TOWARD else 0.0)) % 360.0
        for value in axis[n_freq:n_freq + n_dir]
    ]

    records: list[SpecRecord] = []
    first: datetime | None = None
    while index < len(lines):
        head = lines[index].split()
        if len(head) != 2 or not head[0].isdigit():
            index += 1
            continue
        stamp = datetime.strptime(head[0] + head[1], "%Y%m%d%H%M%S").replace(
            tzinfo=timezone.utc
        )
        first = first or stamp
        if limit_hours is not None and (stamp - first).total_seconds() / 3600.0 > limit_hours:
            break
        index += 1

        # Latitude and longitude run together ("32.52-117.43"), so the trailing
        # fields are counted from the right.
        fields = lines[index].split("'")[2].split()
        depth, u10, udir, curr, cdir = (float(v) for v in fields[-5:])
        index += 1

        flat: list[float] = []
        while len(flat) < n_freq * n_dir and index < len(lines):
            flat += [float(v) for v in lines[index].split()]
            index += 1
        if len(flat) < n_freq * n_dir:
            raise WaveSpecError(f"grid for {stamp} is short: {len(flat)}/{n_freq*n_dir}")

        records.append(SpecRecord(
            time=stamp,
            energy=[flat[d * n_freq:(d + 1) * n_freq] for d in range(n_dir)],
            directions=directions,
            frequencies=frequencies,
            depth_m=depth,
            wind_speed_ms=u10,
            wind_from_deg=udir % 360.0,
            current_ms=curr,
            current_toward_deg=cdir % 360.0,
        ))

    return records


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--station", default="46232")
    parser.add_argument("--cycle", required=True, help="YYYY-MM-DDTHH")
    parser.add_argument("--hours", type=int, default=24)
    args = parser.parse_args(argv)

    cycle = datetime.strptime(args.cycle, "%Y-%m-%dT%H").replace(tzinfo=timezone.utc)
    try:
        text, read = fetch_station_spec(args.station, cycle)
    except WaveSpecError as exc:
        print(f"Not fetched: {exc}")
        return 1

    records = parse_spec(text, limit_hours=args.hours)
    print(f"{args.station} cycle {cycle:%Y-%m-%d %HZ}: {len(records)} records, "
          f"{read/1e6:.0f} MB read of a 1730 MB tar")
    print(f"  {len(records[0].frequencies)} frequencies x {len(records[0].directions)} directions")
    print(f"\n{'valid':>17s} {'wind':>16s} {'depth':>8s}")
    for record in records[:8]:
        print(f"{record.time:%Y-%m-%dT%H:%MZ} {record.wind_from_deg:8.0f}° "
              f"{record.wind_kt:5.0f} kt {record.depth_m:7.1f}m")
    return 0


if __name__ == "__main__":
    sys.exit(main())
