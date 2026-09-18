"""Offshore directional spectrum at 46232 → energy that survives each aperture.

Run: ``python -m forecast.transform --spectra data/spectra/46232``

This is build-order item 3. It takes the buoy's directional spectrum E(f, θ)
and reports, per break, how much of that energy is aimed through the break's
open window — the quantity `forecast.geometry` could only answer yes/no about.

**Why a spectrum and not a direction.** BRIEFING §10: testing a single `MWD`
value against a hard-edged sector made the Coronado Islands look like an on/off
switch, when integrating the same geometry over a real directional spectrum
shows them removing about 11% of the energy and Point Loma about half. The
binary verdict was an artifact of collapsing the spectrum to one number. Nothing
here special-cases the islands; using the whole spectrum is what fixes it.

**What this is NOT.** It resolves the buoy's own spectrum into a sector. It does
not propagate anything to the beach: no shoaling, no refraction, no depth
limiting, no bottom friction, no wind sea generated inside the window. So
`hs_in_window_m` is *the offshore energy aimed at this break*, and it is not the
wave height at the beach and must never be shown as one. Face height and Hs are
different quantities and the transfer between them is unfitted — the same rule
`forecast.beachverify` runs under.

Conventions, because this is where they get confused: frequencies in Hz,
directions in degrees FROM which waves come (NDBC `MWD`, `alpha1`, `alpha2`),
matching `forecast.geometry` and NOT the GFS-Wave bulletin convention that
`collector.gfswave` flips on the way in. CLAUDE.md measured that at 29° of error
with the flip and 151° without.
"""

from __future__ import annotations

import argparse
import csv
import math
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from .geometry import (
    HIGH,
    LOW,
    Blocker,
    Spot,
    blocked_sector,
    load,
)
from .swell import great_circle_km

#: Integration step over direction, in degrees. The narrowest thing being
#: resolved is the islands' 10.9° notch, so a 1° step puts ~11 samples across
#: it. Finer buys nothing: the underlying D(f, θ) is a two-term Fourier fit and
#: carries no structure below about 20°.
STEP_DEG = 1.0

#: Below this Fresnel number a blocker's geometric shadow is not trustworthy —
#: diffraction fills it. F = W²/(λL). Point Loma runs 10.8–30.1 across surf
#: periods; the Coronado Islands run 1.9–5.4 and fall with period (BRIEFING
#: §10). The threshold is a reporting trigger, not a correction: nothing here
#: fits a diffraction model, because nothing has verified one.
FRESNEL_SHARP = 8.0

GRAVITY = 9.81

#: Attribution label for energy arriving from behind the beach.
SEAWARD_CLIP = "behind the beach"


@dataclass(frozen=True)
class Spectrum:
    """One timestamped directional spectrum at the buoy.

    Five NDBC files, one record. `c11` is energy density in m²/Hz; `a1`/`a2`
    are degrees FROM; `r1`/`r2` are dimensionless and already normalised to
    [0, 1] for the real-time product (BRIEFING §7 settled that — do not rescale
    by 100 without re-checking the historical files, which were not tested).
    """

    time: datetime
    frequencies: list[float]
    c11: list[float]
    a1: list[float]
    a2: list[float]
    r1: list[float]
    r2: list[float]

    def __post_init__(self) -> None:
        n = len(self.frequencies)
        for name in ("c11", "a1", "a2", "r1", "r2"):
            if len(getattr(self, name)) != n:
                raise ValueError(
                    f"{name} has {len(getattr(self, name))} values against "
                    f"{n} frequencies — the five files disagree, which is the "
                    f"one thing that must never be papered over"
                )

    def bin_width(self, index: int) -> float:
        f = self.frequencies
        if len(f) < 2:
            return 1.0
        if index == 0:
            return f[1] - f[0]
        if index == len(f) - 1:
            return f[-1] - f[-2]
        return (f[index + 1] - f[index - 1]) / 2.0

    def density(self, index: int, theta: float) -> float:
        """E(f, θ) at one frequency bin, in m²/Hz/radian.

        The NDBC reconstruction is
        ``D(f, θ) = (1/π)[0.5 + r1 cos(θ − α1) + r2 cos(2(θ − α2))]``.
        A two-term Fourier fit is not guaranteed non-negative, and a negative
        energy density is not a small numerical wrinkle — summed over a sector
        it silently *subtracts* energy and can make a windowed total exceed the
        unwindowed one. Clamped at zero, which is the standard treatment.
        """

        t = math.radians(theta)
        d = (1.0 / math.pi) * (
            0.5
            + self.r1[index] * math.cos(t - math.radians(self.a1[index]))
            + self.r2[index] * math.cos(2.0 * (t - math.radians(self.a2[index])))
        )
        return max(0.0, self.c11[index] * d)


#: An unverified blocker only downgrades confidence once it is taking a
#: material share of the energy. Set from measurement, not taste: BRIEFING §10
#: puts the Coronado Islands at ~11% of energy with five times less angular
#: leverage than Point Loma, so a rule that downgrades on any unverified edge
#: would mark every Coronado window "low" on the strength of a blocker that
#: barely moves the answer — and would then have nothing left to say when a
#: blocker that DOES move it is in doubt.
MATERIAL_SHARE = 0.20


@dataclass
class Removed:
    """How much of the buoy's energy one blocker took, and whether to believe it."""

    blocker: str
    share: float
    verified: bool
    #: Fresnel number at the surviving energy's mean period. Below
    #: `FRESNEL_SHARP` the hard-edged shadow is doubtful — diffraction fills it.
    fresnel: float

    @property
    def sharp(self) -> bool:
        return self.fresnel >= FRESNEL_SHARP


@dataclass
class Survives:
    """What one break gets, out of what the buoy saw."""

    spot_id: str
    spot_name: str
    time: datetime
    #: Zeroth moment inside the window and in total, m².
    m0_in: float
    m0_total: float
    #: Energy-weighted mean period and direction of the SURVIVING energy.
    peak_period_s: float
    mean_direction_deg: float
    confidence: str
    #: Per-blocker attribution of the energy that did not make it.
    removed: list[Removed] = field(default_factory=list)
    #: Blockers whose geometric shadow is not trustworthy at this period.
    diffraction_suspect: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    @property
    def dominant_blocker(self) -> str | None:
        """The blocker taking the most energy — what to name on a surface."""

        material = [r for r in self.removed if r.share > 0]
        return max(material, key=lambda r: r.share).blocker if material else None

    @property
    def fraction(self) -> float:
        return self.m0_in / self.m0_total if self.m0_total > 0 else float("nan")

    @property
    def hs_in_window_m(self) -> float:
        """4√m0 of the surviving energy.

        Offshore energy aimed at this break. NOT a wave height at the beach.
        """

        return 4.0 * math.sqrt(max(0.0, self.m0_in))

    @property
    def hs_total_m(self) -> float:
        return 4.0 * math.sqrt(max(0.0, self.m0_total))


def wavelength(period_s: float) -> float:
    """Deep-water wavelength. The buoy is in 200+ m; these are deep-water waves."""

    return GRAVITY * period_s * period_s / (2.0 * math.pi)


def fresnel_number(spot: Spot, blocker: Blocker, period_s: float) -> float:
    """F = W²/(λL) — how sharp this blocker's shadow is at this period.

    W is the blocker's own span and L its distance from the beach. Large F is a
    clean geometric shadow; F near 1 means the shadow is substantially filled by
    diffraction and the hard edge is fiction. See BRIEFING §10 for the measured
    values and for why this is reported rather than corrected for.
    """

    w = great_circle_km(blocker.a, blocker.b) * 1000.0
    length = min(
        great_circle_km(spot.position, blocker.a),
        great_circle_km(spot.position, blocker.b),
    ) * 1000.0
    lam = wavelength(period_s)
    if lam <= 0 or length <= 0:
        return float("inf")
    return w * w / (lam * length)


def transmission(spot: Spot, blockers: list[Blocker], theta: float) -> float:
    """Fraction of energy arriving from `theta` that reaches the beach.

    Geometric: 1 outside every shadow, 0 inside any of them. Deliberately not
    tapered. A diffraction taper would be a fitted model with nothing to fit it
    against, and BRIEFING §10's own hypothesis about island transmission is
    explicitly marked untested. The honest move is a transmission this simple
    plus a loud flag on the blockers where it is doubtful.
    """

    from .geometry import _relative

    offset = _relative(theta, spot.normal)
    if abs(offset) > 90.0:
        return 0.0
    for blocker in blockers:
        sector = blocked_sector(spot, blocker)
        if sector and sector[0] <= offset <= sector[1]:
            return 0.0
    return 1.0


def through(
    spectrum: Spectrum,
    spot: Spot,
    blockers: list[Blocker],
    *,
    step: float = STEP_DEG,
) -> Survives:
    """Integrate E(f, θ)·T(θ) over the whole circle for one break."""

    steps = max(int(round(360.0 / step)), 1)
    d_theta = 360.0 / steps
    radians_step = math.radians(d_theta)

    trans = [transmission(spot, blockers, (n + 0.5) * d_theta) for n in range(steps)]

    # Which blocker is responsible for each blocked direction. A direction
    # inside two shadows is attributed to the first, so the shares sum to the
    # blocked total exactly rather than double-counting an overlap.
    from .geometry import _relative

    culprit: list[str | None] = []
    for n in range(steps):
        theta = (n + 0.5) * d_theta
        offset = _relative(theta, spot.normal)
        who: str | None = None
        if abs(offset) > 90.0:
            who = SEAWARD_CLIP
        else:
            for blocker in blockers:
                sector = blocked_sector(spot, blocker)
                if sector and sector[0] <= offset <= sector[1]:
                    who = blocker.name
                    break
        culprit.append(who)

    m0_in = m0_total = 0.0
    taken: dict[str, float] = {}
    # Energy-weighted accumulators for the SURVIVING energy only.
    weighted_period = 0.0
    sin_sum = cos_sum = 0.0

    for index, freq in enumerate(spectrum.frequencies):
        density = spectrum.c11[index]
        if density <= 0.0 or math.isnan(density):
            continue
        width = spectrum.bin_width(index)
        period = 1.0 / freq if freq > 0 else 0.0
        for n in range(steps):
            theta = (n + 0.5) * d_theta
            energy = spectrum.density(index, theta) * radians_step * width
            if energy <= 0.0:
                continue
            m0_total += energy
            if trans[n] > 0.0:
                surviving = energy * trans[n]
                m0_in += surviving
                weighted_period += surviving * period
                sin_sum += surviving * math.sin(math.radians(theta))
                cos_sum += surviving * math.cos(math.radians(theta))
            else:
                who = culprit[n]
                if who:
                    taken[who] = taken.get(who, 0.0) + energy

    mean_period = weighted_period / m0_in if m0_in > 0 else float("nan")
    mean_dir = math.degrees(math.atan2(sin_sum, cos_sum)) % 360.0 if m0_in > 0 else float("nan")

    by_name = {b.name: b for b in blockers}
    removed: list[Removed] = []
    for name, energy in sorted(taken.items(), key=lambda kv: -kv[1]):
        if name == SEAWARD_CLIP:
            continue
        blocker = by_name[name]
        f = (
            fresnel_number(spot, blocker, mean_period)
            if mean_period and not math.isnan(mean_period)
            else float("inf")
        )
        removed.append(
            Removed(
                blocker=name,
                share=energy / m0_total if m0_total > 0 else float("nan"),
                verified=blocker.tip_verified and spot.position_verified,
                fresnel=f,
            )
        )

    # Confidence follows the energy, not the edge count. A break is a
    # high-confidence answer when its own position is digitised and every
    # blocker taking a material share of the energy is digitised too.
    doubtful = [r for r in removed if not r.verified and r.share >= MATERIAL_SHARE]
    confidence = HIGH if spot.position_verified and not doubtful else LOW

    suspect = [r.blocker for r in removed if not r.sharp and r.share > 0]

    return Survives(
        spot_id=spot.id,
        spot_name=spot.name,
        time=spectrum.time,
        m0_in=m0_in,
        m0_total=m0_total,
        peak_period_s=mean_period,
        mean_direction_deg=mean_dir,
        confidence=confidence,
        removed=removed,
        diffraction_suspect=suspect,
    )


def load_spectra(directory: Path, *, limit: int | None = None) -> list[Spectrum]:
    """Read archived spectra written by `collector.spectra`.

    One CSV per component, wide: `time_utc` then one column per frequency. The
    five are joined on timestamp, and a timestamp missing from any one of them
    is DROPPED rather than filled. CLAUDE.md: never infer, interpolate or
    substitute a missing observation — a partial spectrum is a gap, and a
    silently half-filled D(f, θ) is exactly the confident-wrong-answer failure
    BRIEFING §8 lists.
    """

    parts: dict[str, dict[datetime, list[float]]] = {}
    freqs: list[float] = []
    for kind in ("c11", "a1", "a2", "r1", "r2"):
        path = directory / f"{kind}.csv"
        if not path.exists():
            raise FileNotFoundError(f"{path} — all five components are required")
        rows: dict[datetime, list[float]] = {}
        with path.open(newline="", encoding="utf-8") as fh:
            reader = csv.reader(fh)
            header = next(reader)
            these = [float(h) for h in header[1:]]
            if freqs and these != freqs:
                raise ValueError(
                    f"{path} frequency bins disagree with the other components"
                )
            freqs = these
            for row in reader:
                if not row or not row[0]:
                    continue
                stamp = datetime.fromisoformat(row[0].replace("Z", "+00:00"))
                rows[stamp] = [float(v) if v else float("nan") for v in row[1:]]
        parts[kind] = rows

    shared = sorted(set.intersection(*(set(p) for p in parts.values())))
    if limit is not None:
        shared = shared[-limit:]
    return [
        Spectrum(
            time=t,
            frequencies=freqs,
            c11=parts["c11"][t],
            a1=parts["a1"][t],
            a2=parts["a2"][t],
            r1=parts["r1"][t],
            r2=parts["r2"][t],
        )
        for t in shared
    ]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spectra", type=Path, default=Path("data/spectra/46232"))
    parser.add_argument("--spots-file", type=Path, default=None)
    args = parser.parse_args(argv)

    spots, blockers = load(args.spots_file) if args.spots_file else load()
    coronado = [s for s in spots if s.id.startswith("coronado")]

    try:
        spectra = load_spectra(args.spectra, limit=1)
    except FileNotFoundError as exc:
        print(f"No archived spectra: {exc}")
        print("Run the `Collect NDBC spectra` workflow — www.ndbc.noaa.gov is")
        print("denied at CONNECT from a Claude session (BRIEFING §8).")
        return 2

    if not spectra:
        print("No spectra with all five components present.")
        return 2

    spectrum = spectra[-1]
    print(f"46232 directional spectrum  {spectrum.time:%Y-%m-%d %H:%MZ}")
    print(f"  {len(spectrum.frequencies)} bins, "
          f"{spectrum.frequencies[0]:.4f}–{spectrum.frequencies[-1]:.4f} Hz\n")
    print(f"{'break':24s} {'window Hs':>10s} {'buoy Hs':>9s} {'survives':>9s} "
          f"{'mean T':>7s} {'mean dir':>9s}  confidence")
    for spot in coronado:
        got = through(spectrum, spot, blockers)
        print(
            f"{spot.name[:24]:24s} {got.hs_in_window_m:9.2f}m {got.hs_total_m:8.2f}m "
            f"{100*got.fraction:8.1f}% {got.peak_period_s:6.1f}s "
            f"{got.mean_direction_deg:8.0f}°  {got.confidence}"
        )
    print("\nWindow Hs is offshore energy aimed at the break. It is NOT a wave")
    print("height at the beach: no shoaling, no refraction, nothing propagated.")
    return 0


if __name__ == "__main__":
    sys.exit(main())


# ---------------------------------------------------------------------------
# Partitions
#
# GFS-Wave publishes swell partitions, not spectra: each is one wave train with
# a height, a peak period and a direction. A partition IS a wave train, so each
# one is integrated through the aperture on its own and the survivors are
# recombined by energy. Nothing here fabricates a joint spectrum — stitching
# partitions into one D(f, θ) would invent structure between them that the
# bulletin never claimed.
# ---------------------------------------------------------------------------

#: Directional spread assumed for a partition, in degrees, when the source does
#: not publish one — and GFS-Wave bulletins do not.
#:
#: **This is an assumption, not a measurement, and it is the least defensible
#: number in this module.** Swell narrows as it propagates, so a long-period
#: train from the Southern Hemisphere is narrower than a local wind sea; the
#: two defaults below are conventional values, not fitted ones. `live.py`
#: reports the sensitivity rather than hiding it, and once `collector.spectra`
#: has a series the real r1/r2 replace this entirely — that is the whole reason
#: the spectral path exists.
SWELL_SPREAD_DEG = 20.0
WIND_SEA_SPREAD_DEG = 35.0

#: The period below which a partition is treated as wind sea for spread
#: purposes when the bulletin does not flag it.
WIND_SEA_PERIOD_S = 8.0


def spread_for(period_s: float, wind_sea: bool) -> float:
    """The assumed directional spread for one partition. See SWELL_SPREAD_DEG."""

    if wind_sea or (period_s and period_s < WIND_SEA_PERIOD_S):
        return WIND_SEA_SPREAD_DEG
    return SWELL_SPREAD_DEG


def moments_for_spread(spread_deg: float) -> tuple[float, float]:
    """(r1, r2) for a wrapped-normal directional distribution of this spread.

    r1 = exp(-σ²/2) and r2 = exp(-2σ²) are the exact circular moments, rather
    than the small-angle 1 − σ²/2 expansion: at a 35° wind-sea spread the two
    differ by about 5%, and the expansion can go negative at wider spreads,
    which would put energy where there is none.
    """

    sigma = math.radians(spread_deg)
    return math.exp(-0.5 * sigma * sigma), math.exp(-2.0 * sigma * sigma)


def directional_fraction(
    spot: Spot,
    blockers: list[Blocker],
    from_deg: float,
    spread_deg: float,
    *,
    step: float = STEP_DEG,
) -> float:
    """Fraction of one wave train's energy that gets through the aperture."""

    r1, r2 = moments_for_spread(spread_deg)
    steps = max(int(round(360.0 / step)), 1)
    d_theta = 360.0 / steps

    total = inside = 0.0
    for n in range(steps):
        theta = (n + 0.5) * d_theta
        t = math.radians(theta)
        density = (1.0 / math.pi) * (
            0.5
            + r1 * math.cos(t - math.radians(from_deg))
            + r2 * math.cos(2.0 * (t - math.radians(from_deg)))
        )
        density = max(0.0, density)
        total += density
        if transmission(spot, blockers, theta) > 0.0:
            inside += density
    return inside / total if total > 0 else float("nan")


@dataclass
class PartitionThrough:
    """One wave train, before and after the aperture."""

    hs_offshore_m: float
    tp_s: float
    from_deg: float
    wind_sea: bool
    spread_deg: float
    fraction: float

    @property
    def hs_in_window_m(self) -> float:
        return self.hs_offshore_m * math.sqrt(max(0.0, self.fraction))


@dataclass
class PartitionsThrough:
    """Every wave train at one valid time, recombined after the aperture."""

    spot_id: str
    parts: list[PartitionThrough] = field(default_factory=list)

    @property
    def hs_offshore_m(self) -> float:
        return math.sqrt(sum(p.hs_offshore_m ** 2 for p in self.parts))

    @property
    def hs_in_window_m(self) -> float:
        """Recombined in ENERGY, not height. Adding heights would overstate a
        two-swell day by up to 40%; partitions are independent trains and their
        variances add, which is the same reason Hs = 4√m0 in the first place."""

        return math.sqrt(sum(p.hs_in_window_m ** 2 for p in self.parts))

    @property
    def fraction(self) -> float:
        total = sum(p.hs_offshore_m ** 2 for p in self.parts)
        return (self.hs_in_window_m ** 2 / total) if total > 0 else float("nan")

    @property
    def dominant(self) -> PartitionThrough | None:
        """The train contributing most energy AT THE BREAK, not offshore.

        These differ, and the difference is the entire point of the project: on
        a west swell the biggest offshore train can be the one Point Loma takes,
        leaving a smaller south train to define what is actually breaking.
        """

        surviving = [p for p in self.parts if p.hs_in_window_m > 0]
        return max(surviving, key=lambda p: p.hs_in_window_m) if surviving else None


def through_partitions(
    spot: Spot,
    blockers: list[Blocker],
    partitions: list[tuple[float, float, float, bool]],
    *,
    spread_override: float | None = None,
    step: float = STEP_DEG,
) -> PartitionsThrough:
    """Run (hs_m, tp_s, from_deg, wind_sea) tuples through one break's aperture.

    `from_deg` is degrees FROM. `collector.gfswave` stores partitions as
    `toward_deg` and flips once on the way into the archive; if you are reading
    a `Partition` object rather than an archive row, flip it yourself and do it
    exactly once (CLAUDE.md: 29° of error with the flip, 151° without).
    """

    out = PartitionsThrough(spot_id=spot.id)
    for hs, tp, from_deg, wind_sea in partitions:
        spread = spread_override if spread_override is not None else spread_for(tp, wind_sea)
        out.parts.append(
            PartitionThrough(
                hs_offshore_m=hs,
                tp_s=tp,
                from_deg=from_deg,
                wind_sea=wind_sea,
                spread_deg=spread,
                fraction=directional_fraction(spot, blockers, from_deg, spread, step=step),
            )
        )
    return out


def attribution(
    spot: Spot,
    blockers: list[Blocker],
    from_deg: float,
    spread_deg: float,
    *,
    step: float = STEP_DEG,
) -> dict[str, float]:
    """Which blocker takes which share of one wave train's energy.

    Shares are of the train's TOTAL energy, so they sum with the surviving
    fraction to 1. Energy from behind the beach is filed under `SEAWARD_CLIP`
    rather than dropped, because a surface that shows "62% gets through" and
    two blockers accounting for 20% invites the reader to wonder where the rest
    went — and the answer, that a fifth of a broad spectrum was always pointed
    at the wrong half of the world, is worth saying.
    """

    r1, r2 = moments_for_spread(spread_deg)
    steps = max(int(round(360.0 / step)), 1)
    d_theta = 360.0 / steps

    from .geometry import _relative

    total = 0.0
    taken: dict[str, float] = {}
    for n in range(steps):
        theta = (n + 0.5) * d_theta
        t = math.radians(theta)
        density = max(0.0, (1.0 / math.pi) * (
            0.5
            + r1 * math.cos(t - math.radians(from_deg))
            + r2 * math.cos(2.0 * (t - math.radians(from_deg)))
        ))
        if density <= 0.0:
            continue
        total += density

        offset = _relative(theta, spot.normal)
        who: str | None = None
        if abs(offset) > 90.0:
            who = SEAWARD_CLIP
        else:
            for blocker in blockers:
                sector = blocked_sector(spot, blocker)
                if sector and sector[0] <= offset <= sector[1]:
                    who = blocker.name
                    break
        if who:
            taken[who] = taken.get(who, 0.0) + density

    if total <= 0:
        return {}
    return {name: value / total for name, value in taken.items()}
