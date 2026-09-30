#!/usr/bin/env python3
"""One HTML page to audition every cut before signing off.

    review_page.py <edl.json> --original SRC --edited CUT [--out review.html] [--self-test]

Shows the source timeline (kept = green, cut = red), a table of every cut with
its reason, and both videos. Clicking a cut plays the source from 1 s before to
1 s after the cut, so you hear exactly what was removed; the matching join in the
edited video is one click away. Open the page from a local server or directly
(file://) with the videos next to it; paths are written relative to the page.
"""
import html, json, os, sys


def edited_time(src_t, keeps):
    off = 0.0
    for a, b in keeps:
        if src_t <= b:
            return off + max(0.0, src_t - a)
        off += b - a
    return off


def build(e, original, edited, out):
    rel = lambda p: os.path.relpath(os.path.abspath(p), os.path.dirname(os.path.abspath(out)))
    dur = e["source_duration"]
    bars = "".join(
        f'<div class="seg cut" style="left:{d[0] / dur * 100:.3f}%;width:{max((d[1] - d[0]) / dur * 100, .15):.3f}%" '
        f'title="{d[0]:.2f}-{d[1]:.2f}" onclick="play({d[0]:.3f},{d[1]:.3f},{edited_time(d[0], e["keep"]):.3f})"></div>'
        for d in e["delete"])
    rows = "".join(
        f'<tr onclick="play({d[0]:.3f},{d[1]:.3f},{edited_time(d[0], e["keep"]):.3f})"><td>{i}</td><td>{d[0]:.2f}</td>'
        f'<td>{d[1]:.2f}</td><td>{d[1] - d[0]:.2f}s</td><td>{html.escape(str(d[2]) if len(d) > 2 else "")}</td></tr>'
        for i, d in enumerate(e["delete"]))
    removed = dur - e["edited_duration"]
    page = f"""<!doctype html><html><head><meta charset="utf-8"><title>Cut review</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>
:root{{--bg:#fafaf8;--fg:#1b1b1b;--muted:#6b6b6b;--keep:#3c9a5f;--cut:#d2453b;--line:#e2e2de}}
@media (prefers-color-scheme:dark){{:root{{--bg:#151515;--fg:#eee;--muted:#999;--line:#333}}}}
body{{background:var(--bg);color:var(--fg);font:15px/1.45 system-ui,sans-serif;margin:0;padding:16px;max-width:1200px;margin:auto}}
.tl{{position:relative;height:28px;background:var(--keep);border-radius:4px;margin:12px 0 20px}}
.seg{{position:absolute;top:0;bottom:0;background:var(--cut);cursor:pointer}}
.vids{{display:grid;grid-template-columns:1fr 1fr;gap:12px}} video{{width:100%;max-height:60vh;background:#000}}
table{{border-collapse:collapse;width:100%;margin-top:16px}} td,th{{border-bottom:1px solid var(--line);padding:6px;text-align:left}}
tr:hover{{background:rgba(127,127,127,.12);cursor:pointer}} small{{color:var(--muted)}}
@media (max-width:700px){{.vids{{grid-template-columns:1fr}}}}
</style></head><body>
<h1>Cut review</h1>
<p>{html.escape(os.path.basename(e["source"]))}: {dur:.2f}s &rarr; {e["edited_duration"]:.2f}s,
removed {removed:.2f}s ({removed / dur:.1%}) in {len(e["delete"])} cuts. <small>Click a red block or a row to hear it.</small></p>
<div class="tl">{bars}</div>
<div class="vids"><div><b>Source</b><video id="o" src="{html.escape(rel(original))}" controls preload="metadata"></video></div>
<div><b>Edited</b> <small id="j"></small><video id="e" src="{html.escape(rel(edited))}" controls preload="metadata"></video></div></div>
<table><tr><th>#</th><th>from</th><th>to</th><th>length</th><th>reason</th></tr>{rows}</table>
<script>
const o=document.getElementById('o'),v=document.getElementById('e');let stop=null;
function play(a,b,j){{o.currentTime=Math.max(0,a-1);stop=b+1;o.play();v.pause();v.currentTime=Math.max(0,j-1);
document.getElementById('j').textContent='join at '+j.toFixed(2)+'s';}}
o.addEventListener('timeupdate',()=>{{if(stop!==null&&o.currentTime>=stop){{o.pause();stop=null;}}}});
</script></body></html>"""
    open(out, "w").write(page)
    return out


def self_test():
    e = {"source": "a.mp4", "source_duration": 10, "keep": [[0, 2], [3, 10]], "delete": [[2, 3, "pause 1.0s"]],
         "edited_duration": 9}
    assert edited_time(3.0, e["keep"]) == 2.0 and edited_time(5.0, e["keep"]) == 4.0
    import tempfile
    p = build(e, "a.mp4", "b.mp4", os.path.join(tempfile.mkdtemp(), "r.html"))
    s = open(p).read()
    assert "play(2.000,3.000,2.000)" in s and "pause 1.0s" in s
    print("review_page.py self-test ok")


def main(argv):
    if "--self-test" in argv:
        return self_test()
    opt = lambda k, d=None: argv[argv.index(k) + 1] if k in argv else d
    if not argv or not opt("--original") or not opt("--edited"):
        sys.exit(__doc__)
    e = json.load(open(argv[0]))
    out = opt("--out", os.path.splitext(argv[0])[0] + ".review.html")
    print(build(e, opt("--original"), opt("--edited"), out))


if __name__ == "__main__":
    main(sys.argv[1:])
