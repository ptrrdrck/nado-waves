"""Build the swell-fill mock: the swell-map mock with a picked train's rays on it.

    python -m mocks.swell_fill.build BUNDLE LEAFLET_DIST ROTATE_DIST OUT.html \\
        [--rays RAYS.json] [--fragment]

BUNDLE is a checkout of the public delivery repository (nado-waves-forecast):
every *.json in it is built into one file, served to the page by a fetch
stand-in, as the swell-map mock does. The page is this branch's
app/forecast.html, wrapped as forecast.publish wraps it. LEAFLET_DIST is
Leaflet 1.9.4's dist/ folder and ROTATE_DIST leaflet-rotate 0.2.8's
(npm install leaflet@1.9.4 leaflet-rotate@0.2.8). The map is
mocks/swell_map's, with class names and hooks added (a base map, its
attribution, the view kept across the page's redraws, zoom buttons that stop
at their limits); the rays are `rays.py`'s for that bundle's now.json (or a
saved `--rays` file of it: the trace takes a few minutes); the outer seabed is
`context.py`'s, from `collector.bathymetry`'s GMRT context grid once
bathymetry-context.yml has fetched it, and absent until then; the buoys
marked beside 46232 (46086 and 46047) are NDBC's fetched coordinates
(`forecast.siting.load_coordinates`), never typed. `--fragment` drops the
document's own doctype, html, head and body tags, for a host that supplies
its own.

The map's base is the seabed, not the satellite imagery (owner's choice,
2026-11-10). The mock opens on the map rather than the drawing on a device
that has never chosen, because the fill is the map's. A MOCK: nothing here is published.
"""
import argparse
import json
import re
from pathlib import Path

from forecast.geomviz import build as geometry

HERE = Path(__file__).resolve().parent
MAP = HERE.parent / "swell_map"


def esc(s: str) -> str:
    return s.replace("</", "<\\/")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("bundle", type=Path)
    ap.add_argument("leaflet", type=Path)
    ap.add_argument("rotate", type=Path)
    ap.add_argument("out", type=Path)
    ap.add_argument("--rays", type=Path)
    ap.add_argument("--fragment", action="store_true")
    a = ap.parse_args()
    if a.rays:
        rays = json.loads(a.rays.read_text(encoding="utf-8"))
    else:
        from .rays import build as build_rays
        rays = build_rays(a.bundle / "now.json")
    from forecast.siting import load_coordinates
    from .context import build as build_context
    rays["context"] = build_context()
    where = load_coordinates()
    rays["buoys"] = {b: list(where[b]) for b in ("46086", "46047")}
    print("context seabed:", "GMRT context grid" if rays["context"] else "none yet (bathymetry-context.yml)")
    # The page as this branch would publish it (forecast.publish's own
    # wrapping), not the delivery repo's: the mock shows this branch's page.
    from forecast.publish import PAGE_SOURCE, repoint, wrap
    html = wrap(repoint(PAGE_SOURCE.read_text(encoding="utf-8")), app_title="Nado Waves")
    data = {p.name: json.loads(p.read_text(encoding="utf-8")) for p in sorted(a.bundle.glob("*.json"))}
    shim = ("<script>window.__MOCK_DATA__=" + esc(json.dumps(data, separators=(",", ":"))) + ";"
            "(function(){var real=window.fetch.bind(window);window.fetch=function(u,o){"
            "var n=String(u).split('?')[0].split('/').pop();var d=window.__MOCK_DATA__[n];"
            "if(d)return Promise.resolve(new Response(JSON.stringify(d),{headers:{'Content-Type':'application/json'}}));"
            "return real(u,o);};})();"
            "try{if(localStorage.getItem('nado-sm-view')==null)localStorage.setItem('nado-sm-view','map')}catch(e){}"
            "</script>\n")
    tail = ("<style>" + (a.leaflet / "leaflet.css").read_text() + "</style>\n"
            "<style>" + (MAP / "swellmap.css").read_text() + "</style>\n"
            "<style>" + (HERE / "mapfill.css").read_text() + "</style>\n"
            "<script>" + esc((a.leaflet / "leaflet.js").read_text()) + "</script>\n"
            "<script>" + esc((a.rotate / "leaflet-rotate.js").read_text()) + "</script>\n"
            "<script>window.__SWELLRAYS__=" + esc(json.dumps(rays, separators=(",", ":"))) + ";</script>\n"
            "<script>" + esc((HERE / "mapfill.js").read_text()) + "</script>\n"
            "<script>window.__SWELLMAP_MODEL__=" + esc(json.dumps(geometry(), default=list)) + ";</script>\n"
            "<script>" + esc((MAP / "swellmap.js").read_text()) + "</script>\n")
    i = html.index("<script>")
    html = html[:i] + shim + html[i:]
    j = html.rindex("</body>")
    html = html[:j] + tail + html[j:]
    html = html.replace("<title>", "<title>MOCK swell fill · ", 1)
    if a.fragment:
        html = re.sub(r"<title>[^<]*</title>", "<title>Swell Fill Mock</title>", html, count=1)
        html = re.sub(r"(?is)<!doctype[^>]*>|</?html[^>]*>|</?head[^>]*>|</?body[^>]*>", "", html)
    a.out.write_text(html, encoding="utf-8")
    print(a.out, f"{a.out.stat().st_size / 1e6:.2f} MB")


if __name__ == "__main__":
    main()
