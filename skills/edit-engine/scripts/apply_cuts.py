#!/usr/bin/env python3
"""Stage 2b: apply approved cuts (mistakes, manual trims) and render once.

    apply_cuts.py <words.json> --cuts approved.json --out-dir DIR
                  [--base-edl <stem>.pauses.edl.json] [--video input.mp4] [--render]

approved.json:  {"cuts": [{"start": 75.5, "end": 81.32, "reason": "retake"}]}
Times are on the timeline of <words.json> (usually the pause-cut timeline).
Widen a range freely, e.g. from the start of a botched take to the clean restart.

--base-edl  (recommended) maps the cuts back onto the ORIGINAL recording and
            writes one combined EDL, so the final video is encoded once from the
            source instead of re-encoding an already cut file.
--video     without --base-edl: cut this file (must match <words.json>).

Writes <stem>.final.edl.json, <stem>.final.words.json (retimed, cut words removed),
<stem>.final.md, and <stem>.final.mp4 with --render. An empty cuts list is valid.
"""
import json, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import edl  # noqa: E402


def to_source(t, keeps):
    """Edited-timeline second -> source second, via a keep list."""
    off = 0.0
    for a, b in keeps:
        if t <= off + (b - a) + 1e-9:
            return a + (t - off)
        off += b - a
    return keeps[-1][1]


def combine(base, cuts):
    """Deletes of the base EDL plus the approved cuts mapped onto the source timeline."""
    dels = [list(d) for d in base["delete"]]
    for c in cuts:
        dels.append([to_source(c["start"], base["keep"]), to_source(c["end"], base["keep"]), c.get("reason", "cut")])
    return edl.merge(dels)


def self_test():
    keeps = [[1.0, 3.0], [4.0, 10.0]]            # edited timeline: 0-2 -> 1-3, 2-8 -> 4-10
    assert to_source(0.5, keeps) == 1.5 and to_source(2.5, keeps) == 4.5
    base = {"keep": keeps, "delete": [[0, 1, "lead"], [3, 4, "pause"]], "source_duration": 10}
    d = combine(base, [{"start": 1.5, "end": 3.0, "reason": "retake"}])  # spans the old pause
    assert d == [[0, 1, "lead"], [2.5, 5.0, "retake; pause"]], d
    assert edl.keeps_from_deletes(d, 10) == [[1, 2.5], [5.0, 10]]
    print("apply_cuts.py self-test ok")


def main(argv):
    if "--self-test" in argv:
        return self_test()
    opt = lambda k, d=None: argv[argv.index(k) + 1] if k in argv else d
    pos = [a for i, a in enumerate(argv) if not a.startswith("--") and (i == 0 or not argv[i - 1].startswith("--") or argv[i - 1] == "--render")]
    if not pos or not opt("--cuts"):
        sys.exit(__doc__)
    words, meta = edl.load_words(pos[0])
    cuts = json.load(open(opt("--cuts")))["cuts"]
    out_dir = opt("--out-dir", os.path.dirname(os.path.abspath(pos[0])))
    os.makedirs(out_dir, exist_ok=True)
    stem = os.path.join(out_dir, os.path.basename(pos[0]).split(".")[0])

    base = json.load(open(opt("--base-edl"))) if opt("--base-edl") else None
    if base:
        in_dur = base["edited_duration"]
        src, src_dur, fps = base["source"], base["source_duration"], base["fps"]
    else:
        src = opt("--video") or sys.exit("need --base-edl or --video")
        src_dur, fps, _ = edl.probe(src)
        in_dur = src_dur
    for c in cuts:
        if not (0 <= c["start"] < c["end"] <= in_dur + 0.05):
            sys.exit(f"cut out of bounds for a {in_dur:.2f}s timeline: {c}")

    local_keeps = edl.keeps_from_deletes([[c["start"], c["end"], c.get("reason", "")] for c in cuts], in_dur, fps)
    new_words = edl.retime(words, local_keeps, drop_cut=True)
    if base:
        deletes = combine(base, cuts)
    else:
        deletes = [[c["start"], c["end"], c.get("reason", "cut")] for c in cuts]
    keeps = edl.keeps_from_deletes(deletes, src_dur, fps)
    doc = edl.edl_doc(src, src_dur, fps, keeps, deletes, stage="final", approved_cuts=cuts)
    json.dump(doc, open(stem + ".final.edl.json", "w"), ensure_ascii=False, indent=1)
    json.dump({"words": new_words, "duration": doc["edited_duration"], "source": src},
              open(stem + ".final.words.json", "w"), ensure_ascii=False, indent=1)
    lines = [f"# Final cut: {os.path.basename(src)}", "",
             f"- source {src_dur:.2f}s -> final {doc['edited_duration']:.2f}s, {len(cuts)} approved cuts, "
             f"{len(words) - len(new_words)} words removed", "", "| from | to | reason |", "|---|---|---|"]
    lines += [f"| {c['start']:.2f} | {c['end']:.2f} | {c.get('reason', '')} |" for c in cuts]
    open(stem + ".final.md", "w").write("\n".join(lines) + "\n")
    res = {"source_s": round(src_dur, 2), "final_s": doc["edited_duration"], "cuts": len(cuts),
           "words_in": len(words), "words_out": len(new_words),
           "transcript_end_s": new_words[-1]["end"] if new_words else 0}
    if "--render" in argv:
        res["render"] = edl.render(src, keeps, stem + ".final.mp4")
        res["render_s"] = round(edl.probe(res["render"])[0], 3)
    print(json.dumps(res))


if __name__ == "__main__":
    main(sys.argv[1:])
