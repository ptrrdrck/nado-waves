"""The production workflows run on plain Python, and nothing else checks it.

collect-beach-inputs.yml, forecast.yml and the other jobs that install nothing
run every `python -m` module on the runner's bare interpreter: no numpy, no
contourpy, no shapely. Only the precompute jobs (bathymetry*.yml) and the test
job install anything. That is the architecture, and until 2026-11-12 it was
held by habit alone: the tests run WITH numpy installed, so a module that
reached numpy from a production path passed every test and broke only on
Actions. On that day forecast.mapdata imported a helper from
forecast.seabedvector, which loads numpy, from inside a function. Every
publish failed for two hours -- the forecast build red, every collection's
publish green and silent -- and every LIVE card went overdue.

Two checks, one wide and one exact:

- every module the bare-Python workflows run, and everything it can import --
  top-level and function-level alike, because that day's import sat inside a
  function -- reaches no third-party module, except the few listed below, each
  with the reason it is safe;
- the collection's publish, run as Actions runs it, under `python -S` (no
  site-packages at all), on the repository's own data.
"""

import ast
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
WORKFLOWS = ROOT / ".github" / "workflows"
STDLIB = set(sys.stdlib_module_names)
OURS = ("forecast", "collector")

#: Third-party imports a production module may reach, each because it sits in
#: code no workflow runs. Add to this only with the reason; a new entry is a
#: claim that a bare-Python job never takes that path.
ALLOWED = {
    ("forecast.upstreamlag", "numpy"):
        "only in its report functions (ridge_section, _xcorr_arrays, _peak), run "
        "by `python -m forecast.upstreamlag` by hand; the Briefing reads its band "
        "constants and band_energy, which are pure Python",
}


def bare_python_modules() -> dict[str, list[str]]:
    """Every `python -m` module a workflow that installs nothing runs, and
    which workflows run it. Comment lines are not commands."""

    found: dict[str, list[str]] = {}
    for wf in sorted(WORKFLOWS.glob("*.yml")):
        lines = [ln for ln in wf.read_text(encoding="utf-8").splitlines()
                 if not ln.strip().startswith("#")]
        text = "\n".join(lines)
        if "pip install" in text:
            continue
        for module in re.findall(r"python3? -m ([A-Za-z_][\w.]*)", text):
            if module.split(".")[0] in OURS:
                found.setdefault(module, []).append(wf.name)
    return found


def _source(module: str) -> Path | None:
    base = ROOT.joinpath(*module.split("."))
    for path in (base.with_suffix(".py"), base / "__init__.py"):
        if path.exists():
            return path
    return None


def _imports(module: str):
    """(imported name, line) for every import statement in the module, at any
    depth: a function-level import is still a path the module can take."""

    path = _source(module)
    package = module if path.name == "__init__.py" else module.rsplit(".", 1)[0]
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield alias.name, node.lineno
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                parts = package.split(".")
                base = ".".join(parts[: len(parts) - node.level + 1])
                if node.module is None:
                    for alias in node.names:
                        yield f"{base}.{alias.name}", node.lineno
                else:
                    yield f"{base}.{node.module}", node.lineno
            else:
                yield node.module, node.lineno


def third_party_reached(start: str) -> dict[tuple[str, str], list[str]]:
    """{(our module, third-party package): [where]} over everything `start`
    can import."""

    seen, reached, todo = set(), {}, [start]
    while todo:
        module = todo.pop()
        if module in seen:
            continue
        seen.add(module)
        for name, line in _imports(module):
            top = name.split(".")[0]
            if top in OURS:
                # `from .x import f` names f; the module is x.
                target = name if _source(name) else name.rsplit(".", 1)[0]
                if _source(target):
                    todo.append(target)
            elif top not in STDLIB and top != "__future__":
                reached.setdefault((module, top), []).append(f"{module}:{line}")
    return reached


def test_the_checker_sees_a_function_level_import():
    """The control: seabedvector loads numpy at its top and shapely inside its
    functions; the checker must see both, or a clean result means nothing."""

    reached = {pkg for _, pkg in third_party_reached("forecast.seabedvector")}
    assert {"numpy", "shapely", "contourpy"} <= reached


def test_the_bare_python_workflows_are_found():
    modules = bare_python_modules()
    for module in ("forecast.publish", "forecast.now", "forecast.live", "forecast.briefing",
                   "forecast.fill", "forecast.buoys", "collector.spectra"):
        assert module in modules, module
    # The precompute jobs install numpy, so what they run is theirs to load.
    assert "forecast.seabedvector" not in modules
    assert "collector.bathymetry" not in modules


def test_no_bare_python_workflow_can_reach_a_third_party_module():
    problems = []
    for module, where in sorted(bare_python_modules().items()):
        for (importer, package), lines in third_party_reached(module).items():
            if (importer, package) not in ALLOWED:
                problems.append(f"{module} ({', '.join(sorted(set(where)))}) reaches "
                                f"{package} at {', '.join(lines)}")
    assert not problems, (
        "These run on Actions with nothing installed:\n  " + "\n  ".join(problems))


def test_every_allowance_is_still_needed():
    """An allowance nothing needs any more is a hole left open."""

    used = set()
    for module in bare_python_modules():
        used |= set(third_party_reached(module))
    assert set(ALLOWED) <= used, set(ALLOWED) - used


def test_the_collections_publish_runs_with_nothing_installed(tmp_path):
    """The collection's own publish, as Actions runs it: `python -S` loads no
    site-packages, so numpy, contourpy and shapely are not there to find.
    The repository's data, with a now.json of its own (data/live is not
    tracked)."""

    bare = subprocess.run([sys.executable, "-S", "-c", "import numpy"], capture_output=True)
    assert bare.returncode != 0, "python -S still finds numpy: this test would prove nothing"

    data = tmp_path / "data"
    (data / "live").mkdir(parents=True)
    for entry in (ROOT / "data").iterdir():
        if entry.name != "live":
            (data / entry.name).symlink_to(entry)
    (data / "live" / "now.json").write_text(json.dumps({"observed_utc": "2026-11-12T20:00:00Z"}))
    out = tmp_path / "out"
    run = subprocess.run([sys.executable, "-S", "-m", "forecast.publish", "--only-now",
                          "--data-dir", str(data), "--out", str(out)],
                         cwd=ROOT, capture_output=True, text=True)
    assert run.returncode == 0, run.stderr[-3000:]
    for name in ("index.html", "docs.html", "now.json", "map.json"):
        assert (out / name).exists(), name
    assert json.loads((out / "map.json").read_text())["paths"]


def _step(workflow: str, name: str) -> str:
    """One step's text, from its `- name:` line to the next step's."""

    text = (WORKFLOWS / workflow).read_text(encoding="utf-8")
    start = text.index(f"      - name: {name}\n")
    ends = [i for i in (text.find("\n      - ", start + 1), text.find("\n      #", start + 1)) if i > 0]
    return text[start:min(ends) if ends else None]


def test_a_collection_that_did_not_publish_goes_red():
    """The forecast job's publish always failed its run; the collection's hid
    behind continue-on-error, and on 2026-11-12 two hours of failed publishes
    stayed green. Nothing expected fails there (now.json is written even when
    46232 is dark; no token exits 0), so a failure is a failure."""

    publish = _step("collect-beach-inputs.yml", "Publish the observed reading")
    assert "continue-on-error" not in publish
    assert "::error title=Page not published::" in publish
    assert "continue-on-error" not in _step("forecast.yml", "Publish the page")


def test_a_dark_46232_does_not_stop_the_wind_and_tide_charts():
    """forecast.now exits 1 when 46232 is dark, after writing now.json. Under
    set -e that skipped everything after it in the step, the wind and tide
    charts included, which read nothing of 46232. The step still ends with
    now's status, so the archive check that keys on it is unchanged."""

    step = _step("collect-beach-inputs.yml", "Rebuild the observed reading")
    assert "python -m forecast.now || now_status=$?" in step
    assert step.rstrip().endswith('exit "${now_status}"')
    for later in ("forecast.measured", "forecast.windtide", "forecast.originhistory --live"):
        assert step.index(later) > step.index("forecast.now ||"), later


def test_a_queued_archive_run_builds_on_the_newest_tip():
    """Three of 25 archive runs (10-12 Nov) rebuilt on the commit that
    triggered them, from before the run queued ahead of them pushed, and
    their rebase conflicted on that run's rebuild of the same file."""

    text = (WORKFLOWS / "series-archive.yml").read_text(encoding="utf-8")
    assert "concurrency:\n  group: series-archive" in text
    assert "- uses: actions/checkout@v5\n        with:\n          ref: ${{ github.ref_name }}" in text
