"""Build the swell-map mock: the published page with its data built in, plus the back.

    python -m mocks.swell_map.build BUNDLE LEAFLET_DIST ROTATE_DIST OUT.html

BUNDLE is a checkout of the public delivery repository (nado-waves-forecast):
its index.html and every *.json beside it are built into one file, served to
the page by a fetch stand-in, so the mock opens anywhere with no server.
LEAFLET_DIST is Leaflet 1.9.4's dist/ folder and ROTATE_DIST leaflet-rotate
0.2.8's (npm install leaflet@1.9.4 leaflet-rotate@0.2.8).
The geometry is forecast.geomviz's, built here from spots.json, never typed.

A MOCK. Nothing here is published: forecast.publish ships app/ only.
"""
import argparse
import json
from pathlib import Path

from forecast.geomviz import build as geometry

HERE = Path(__file__).resolve().parent


def esc(s: str) -> str:
    return s.replace("</", "<\\/")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("bundle", type=Path)
    ap.add_argument("leaflet", type=Path)
    ap.add_argument("rotate", type=Path, help="leaflet-rotate 0.2.8's dist/ folder")
    ap.add_argument("out", type=Path)
    a = ap.parse_args()
    html = (a.bundle / "index.html").read_text(encoding="utf-8")
    data = {p.name: json.loads(p.read_text(encoding="utf-8")) for p in sorted(a.bundle.glob("*.json"))}
    shim = ("<script>window.__MOCK_DATA__=" + esc(json.dumps(data, separators=(",", ":"))) + ";"
            "(function(){var real=window.fetch.bind(window);window.fetch=function(u,o){"
            "var n=String(u).split('?')[0].split('/').pop();var d=window.__MOCK_DATA__[n];"
            "if(d)return Promise.resolve(new Response(JSON.stringify(d),{headers:{'Content-Type':'application/json'}}));"
            "return real(u,o);};})();</script>\n")
    model = json.dumps(geometry(), default=list)
    tail = ("<style>" + (a.leaflet / "leaflet.css").read_text() + "</style>\n"
            "<style>" + (HERE / "swellmap.css").read_text() + "</style>\n"
            "<script>" + esc((a.leaflet / "leaflet.js").read_text()) + "</script>\n"
            "<script>" + esc((a.rotate / "leaflet-rotate.js").read_text()) + "</script>\n"
            "<script>window.__SWELLMAP_MODEL__=" + esc(model) + ";</script>\n"
            "<script>" + esc((HERE / "swellmap.js").read_text()) + "</script>\n")
    i = html.index("<script>")
    html = html[:i] + shim + html[i:]
    j = html.rindex("</body>")
    html = html[:j] + tail + html[j:]
    a.out.write_text(html.replace("<title>", "<title>MOCK swell map · ", 1), encoding="utf-8")
    print(a.out, f"{a.out.stat().st_size / 1e6:.2f} MB")


if __name__ == "__main__":
    main()
