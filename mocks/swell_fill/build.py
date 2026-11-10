"""Build the swell-fill mock: the published page with its data built in.

    python -m mocks.swell_fill.build BUNDLE OUT.html [--fragment]

BUNDLE is a checkout of the public delivery repository (nado-waves-forecast):
its index.html and every *.json beside it are built into one file, served to
the page by a fetch stand-in, so the mock opens anywhere with no server, as
the swell-map mock does. The fill itself is `fill.py`'s, rebuilt from the
archived 46232 spectrum at that now.json's own moment, never typed.
`--fragment` drops the document's own doctype, html, head and body tags, for
a host that supplies its own.

A MOCK. Nothing here is published: forecast.publish ships app/ only.
"""
import argparse
import json
import re
from pathlib import Path

from .fill import build as fill

HERE = Path(__file__).resolve().parent


def esc(s: str) -> str:
    return s.replace("</", "<\\/")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("bundle", type=Path)
    ap.add_argument("out", type=Path)
    ap.add_argument("--fragment", action="store_true")
    a = ap.parse_args()
    html = (a.bundle / "index.html").read_text(encoding="utf-8")
    data = {p.name: json.loads(p.read_text(encoding="utf-8")) for p in sorted(a.bundle.glob("*.json"))}
    shim = ("<script>window.__MOCK_DATA__=" + esc(json.dumps(data, separators=(",", ":"))) + ";"
            "(function(){var real=window.fetch.bind(window);window.fetch=function(u,o){"
            "var n=String(u).split('?')[0].split('/').pop();var d=window.__MOCK_DATA__[n];"
            "if(d)return Promise.resolve(new Response(JSON.stringify(d),{headers:{'Content-Type':'application/json'}}));"
            "return real(u,o);};})();</script>\n")
    tail = ("<style>" + (HERE / "swellfill.css").read_text() + "</style>\n"
            "<script>window.__SWELLFILL__=" + esc(json.dumps(fill(a.bundle / "now.json"),
                                                          separators=(",", ":"))) + ";</script>\n"
            "<script>" + esc((HERE / "swellfill.js").read_text()) + "</script>\n")
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
