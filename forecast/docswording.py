"""The documentation page's wording as one Markdown file, for editing.

    python -m forecast.docswording            # rewrite app/docs_wording.md
    python -m forecast.docswording --check    # exit 1 if it is out of date

`app/docs.html` is the page and stays the system of record. This writes its
prose, section by section, into `app/docs_wording.md`, keyed by each section's
id, so the owner can edit wording in an editor and push it, and the edits can
be carried back into the page by section. Headings, paragraphs, lists, term
lists, the math blocks, the model-choice boxes and the static tables come
through; anything the page draws or fills in at load (the vertex drawings, the
live standing-on blocks, the geometry tables, the worked hour's table) is
named in [brackets] and not reproduced, and a number the page reads from the
geometry is {{geo:its-key}}.

`tests/test_docs.py` pins that the file is this export of the page, so the two
cannot drift: change the page, run this, commit both. Pure Python, standard
library only.
"""

from __future__ import annotations

import argparse
import re
import sys
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PAGE = ROOT / "app" / "docs.html"
WORDING = ROOT / "app" / "docs_wording.md"

VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta",
        "source", "track", "wbr"}

HEADER = """\
# Nado Waves documentation: wording

This file is generated from `app/docs.html` by `python -m forecast.docswording`.
The page is the system of record; this is its prose, for editing.

How to edit:

- Edit wording in place. Keep every `## [section-id]` and `### [section-id]`
  line: the id in brackets is how an edit finds its way back to the page. The
  title after it is editable.
- Work on a branch (any name), push it, and say which branch. The test that
  keeps this file in step with the page fails on your push until the edits
  are carried into the page; that is expected.
- `{{geo:...}}` is a number the page reads from the geometry. Leave it as is,
  or change the words around it.
- `[bracketed notes]` are things the page draws or fills in itself: drawings,
  live blocks, the geometry tables. Their wording is not here.
- Fenced blocks are the math. Edit them like any other text.
- A line starting `>>` is a note to Claude, not page text. Use it for
  anything that is not a wording change, where it applies:
  `>> move this section after [calc-table]`, `>> delete this section`,
  `>> new section here: ### [new-id] Title`, `>> add a drawing of the tip`.
  Notes are removed when they are carried out.
"""


class _Node:
    __slots__ = ("tag", "attrs", "children", "parent")

    def __init__(self, tag, attrs, parent):
        self.tag, self.attrs, self.children, self.parent = tag, dict(attrs), [], parent

    def classes(self):
        return set((self.attrs.get("class") or "").split())

    def find(self, pred):
        for c in self.children:
            if isinstance(c, _Node):
                if pred(c):
                    return c
                hit = c.find(pred)
                if hit:
                    return hit
        return None

    def text(self):
        return "".join(c if isinstance(c, str) else c.text() for c in self.children)


class _Tree(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = _Node("#root", {}, None)
        self.cur = self.root

    def handle_starttag(self, tag, attrs):
        node = _Node(tag, attrs, self.cur)
        self.cur.children.append(node)
        if tag not in VOID:
            self.cur = node

    def handle_startendtag(self, tag, attrs):
        self.cur.children.append(_Node(tag, attrs, self.cur))

    def handle_endtag(self, tag):
        n = self.cur
        while n is not None and n.tag != tag:
            n = n.parent
        if n is not None and n.parent is not None:
            self.cur = n.parent

    def handle_data(self, data):
        self.cur.children.append(data)


def _sq(t: str) -> str:
    return re.sub(r"\s+", " ", t)


def _inline(n) -> str:
    if isinstance(n, str):
        return _sq(n)
    cls = n.classes()
    if n.tag in ("script", "style", "svg") or cls & {"anchor", "pin", "num"}:
        return ""
    if "data-geo" in n.attrs:
        return "{{geo:" + n.attrs["data-geo"] + "}}"
    if "tabs" in cls:
        return " / ".join(_sq(c.text()).strip() for c in n.children if isinstance(c, _Node))
    kids = "".join(_inline(c) for c in n.children)
    if n.tag in ("b", "strong"):
        return f"**{kids.strip()}**"
    if n.tag in ("em", "i"):
        return f"*{kids.strip()}*"
    if n.tag == "code":
        return f"`{n.text()}`"
    if n.tag == "a" and (n.attrs.get("href") or "").startswith("#"):
        return f"[{kids.strip()}]({n.attrs['href']})"
    if n.tag == "br":
        return "\n"
    return kids


def _line(n) -> str:
    return _inline(n).strip()


def _table(t) -> str:
    rows = []
    for tr in _walk(t, lambda x: x.tag == "tr"):
        rows.append("| " + " | ".join(_line(c) for c in tr.children
                                       if isinstance(c, _Node) and c.tag in ("td", "th")) + " |")
    if len(rows) > 1:
        rows.insert(1, "|" + "---|" * (rows[0].count(" | ") + 1))
    return "\n".join(rows)


def _walk(n, pred):
    for c in n.children:
        if isinstance(c, _Node):
            if pred(c):
                yield c
            yield from _walk(c, pred)


def _block(n, out: list[str]) -> None:
    if isinstance(n, str):
        if n.strip():
            out.append(_sq(n).strip())
        return
    cls = n.classes()
    if n.tag == "section" and n.attrs.get("id"):
        head = next((c for c in n.children if isinstance(c, _Node) and c.tag in ("h1", "h2", "h3")), None)
        level = "###" if head is not None and head.tag == "h3" else "##"
        out.append(f"{level} [{n.attrs['id']}] {_line(head) if head is not None else ''}".rstrip())
        for c in n.children:
            if c is not head:
                _block(c, out)
        return
    if cls & {"next", "mapbox", "status", "controls", "legend", "seg", "anchor"} or n.tag == "script":
        return
    if "card" in cls and n.find(lambda x: x.attrs.get("id") in ("standing-now", "standing-forecast")):
        label = n.find(lambda x: "lbl" in x.classes())
        out.append(f"[live block: {_line(label)}]")
        return
    if "tablebox" in cls or n.attrs.get("id") == "worked-table":
        table = n.find(lambda x: x.tag == "table")
        if table is not None and not table.attrs.get("id"):
            out.append(_table(table))
        else:
            out.append(f"[table the page fills in: {(table.attrs.get('id') if table is not None else None) or n.attrs.get('id')}]")
        return
    if "choice" in cls:
        out.append("\n".join((f"> **{_line(c)}**" if "lbl" in c.classes() else f"> {_line(c)}")
                             for c in n.children if isinstance(c, _Node)))
        return
    if "mock" in cls:
        out.append("[annotated card, row by row:]\n" + "\n".join(
            f"- {_line(c)}" for c in n.children if isinstance(c, _Node)))
        return
    if "chain" in cls:
        out.append(_line(n))
        return
    if n.tag in ("p", "span", "h4"):
        t = _line(n)
        if t:
            out.append(f"#### {t}" if n.tag == "h4" else t)
        return
    if n.tag == "pre":
        out.append("```\n" + n.text().rstrip() + "\n```")
        return
    if n.tag in ("ul", "ol"):
        items = [c for c in n.children if isinstance(c, _Node) and c.tag == "li"]
        out.append("\n".join(f"{i + 1}. {_line(li)}" if n.tag == "ol" else f"- {_line(li)}"
                             for i, li in enumerate(items)))
        return
    if n.tag == "dl":
        lines = []
        for c in n.children:
            if isinstance(c, _Node) and c.tag == "dt":
                lines.append(f"- **{_line(c)}**")
            elif isinstance(c, _Node) and c.tag == "dd":
                lines.append(f"  {_line(c)}")
        out.append("\n".join(lines))
        return
    if n.tag == "figure":
        view = n.find(lambda x: "data-view" in x.attrs)
        cap = n.find(lambda x: x.tag == "figcaption")
        out.append(f"[drawing: {view.attrs['data-view'] if view else ''}] "
                   f"Caption: {_line(cap) if cap is not None else ''}".rstrip())
        return
    if n.tag == "table":
        out.append(_table(n))
        return
    for c in n.children:
        _block(c, out)


def export(page: str) -> str:
    """The wording file for the page's source text."""

    tree = _Tree()
    tree.feed(page)
    article = tree.root.find(lambda x: x.tag == "article" and x.attrs.get("id") == "doc")
    if article is None:
        raise ValueError("no <article id=\"doc\"> in the page")
    out: list[str] = []
    for c in article.children:
        if isinstance(c, _Node) and c.tag == "section":
            _block(c, out)
    return HEADER + "\n" + "\n\n".join(out) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--check", action="store_true",
                        help="exit 1 if app/docs_wording.md is not the page's export")
    args = parser.parse_args(argv)
    text = export(PAGE.read_text(encoding="utf-8"))
    if args.check:
        current = WORDING.read_text(encoding="utf-8") if WORDING.exists() else ""
        if current != text:
            print(f"{WORDING.relative_to(ROOT)} is out of date: run python -m forecast.docswording")
            return 1
        print(f"{WORDING.relative_to(ROOT)} is current")
        return 0
    WORDING.write_text(text, encoding="utf-8")
    print(f"wrote {WORDING.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
