#!/usr/bin/env python3
"""Shared edit-list helpers: ranges, retiming, ffmpeg rendering.

An EDL here is plain JSON:
    {"source": "raw.mp4", "source_duration": 104.0, "fps": 25,
     "keep": [[0.0, 3.2], [3.9, 10.4], ...],      # seconds on the SOURCE timeline
     "delete": [[3.2, 3.9, "pause 0.9s"], ...],
     "edited_duration": 96.1}

Every stage (pauses, mistakes, manual cuts) reads a transcript that matches its
input video and writes (a) an EDL and (b) a retimed transcript that matches its
output video. Never time graphics against a transcript from an earlier stage.

    edl.py --self-test
"""
import json, os, subprocess, sys


def load_words(path):
    d = json.load(open(path))
    words = d["words"] if isinstance(d, dict) else d
    meta = d if isinstance(d, dict) else {}
    return [dict(w) for w in words], meta


def probe(path):
    """duration, fps, has_audio for a media file."""
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                          "format=duration:stream=codec_type,r_frame_rate", "-of", "json", path],
                         capture_output=True, text=True, check=True).stdout
    d = json.loads(out)
    fps = None
    for s in d.get("streams", []):
        if s["codec_type"] == "video" and fps is None:
            n, den = s["r_frame_rate"].split("/")
            fps = float(n) / float(den) if float(den) else None
    has_audio = any(s["codec_type"] == "audio" for s in d.get("streams", []))
    return float(d["format"]["duration"]), fps, has_audio


def merge(ranges, min_len=0.0):
    """Sort + merge overlapping [a, b, *extra] ranges. Extra fields of merged ranges are joined."""
    rs = sorted([list(r) for r in ranges if r[1] - r[0] > min_len], key=lambda r: r[0])
    out = []
    for r in rs:
        if out and r[0] <= out[-1][1] + 1e-6:
            out[-1][1] = max(out[-1][1], r[1])
            if len(r) > 2:
                out[-1][2:] = ["; ".join(str(x) for x in (out[-1][2:] + r[2:]) if x)]
        else:
            out.append(r)
    return out


def snap(t, fps):
    return round(round(t * fps) / fps, 6) if fps else t


def keeps_from_deletes(deletes, duration, fps=None, min_keep=0.04):
    """Complement of the delete ranges, snapped to frame boundaries."""
    keeps, cur = [], 0.0
    for d in merge(deletes):
        a, b = max(0.0, d[0]), min(duration, d[1])
        if a > cur:
            keeps.append([cur, a])
        cur = max(cur, b)
    if cur < duration:
        keeps.append([cur, duration])
    keeps = [[snap(a, fps), snap(b, fps)] for a, b in keeps]
    return [k for k in keeps if k[1] - k[0] >= min_keep]


def retime(words, keeps, drop_cut=True):
    """Map source-time words onto the edited timeline.

    drop_cut=True  (mistake cuts): words whose midpoint was cut are removed.
    drop_cut=False (pause cuts): ASR word edges are fuzzy, so a word that seems to
    sit in a cut is clamped onto the nearest kept edge instead of being lost."""
    out, offset, ki = [], 0.0, 0
    offsets = []
    for a, b in keeps:
        offsets.append(offset)
        offset += b - a
    for w in words:
        mid = (w["start"] + w["end"]) / 2
        while ki < len(keeps) and keeps[ki][1] < mid:
            ki += 1
        if ki == len(keeps) or mid < keeps[ki][0]:
            if drop_cut:
                continue
            ki2 = min(ki, len(keeps) - 1)
            a, b = keeps[ki2]
            t = offsets[ki2] + (0 if ki < len(keeps) and mid < a else b - a)
            out.append(dict(w, start=round(t, 3), end=round(t, 3), clamped=True,
                            source_start=w.get("source_start", w["start"]), source_end=w.get("source_end", w["end"])))
            continue
        a, b = keeps[ki]
        s = offsets[ki] + max(w["start"], a) - a
        e = offsets[ki] + min(w["end"], b) - a
        nw = dict(w, start=round(s, 3), end=round(max(e, s), 3),
                  source_start=w.get("source_start", w["start"]), source_end=w.get("source_end", w["end"]))
        out.append(nw)
    return out


def edl_doc(source, duration, fps, keeps, deletes, **extra):
    return dict({"source": source, "source_duration": round(duration, 3), "fps": fps,
                 "keep": [[round(a, 3), round(b, 3)] for a, b in keeps],
                 "delete": [[round(d[0], 3), round(d[1], 3)] + list(d[2:]) for d in merge(deletes)],
                 "edited_duration": round(sum(b - a for a, b in keeps), 3)}, **extra)


def filter_script(keeps, has_audio, fade=0.008):
    """trim/atrim + concat graph. Short audio fades at every join kill clicks."""
    lines, labels = [], []
    for i, (a, b) in enumerate(keeps):
        lines.append(f"[0:v]trim=start={a:.6f}:end={b:.6f},setpts=PTS-STARTPTS[v{i}];")
        if has_audio:
            ln = b - a
            f = min(fade, ln / 4)
            lines.append(f"[0:a]atrim=start={a:.6f}:end={b:.6f},asetpts=PTS-STARTPTS,"
                         f"afade=t=in:d={f:.4f},afade=t=out:st={ln - f:.6f}:d={f:.4f}[a{i}];")
            labels.append(f"[v{i}][a{i}]")
        else:
            labels.append(f"[v{i}]")
    lines.append("".join(labels) + f"concat=n={len(keeps)}:v=1:a={1 if has_audio else 0}"
                 + ("[outv][outa]" if has_audio else "[outv]"))
    return "\n".join(lines)


def render(video, keeps, out_path, crf=18):
    _, _, has_audio = probe(video)
    graph = out_path + ".filter.txt"
    open(graph, "w").write(filter_script(keeps, has_audio))
    cmd = ["ffmpeg", "-v", "error", "-y", "-i", video, "-/filter_complex", graph, "-map", "[outv]"]
    if has_audio:
        cmd += ["-map", "[outa]", "-c:a", "aac", "-b:a", "192k"]
    cmd += ["-c:v", "libx264", "-crf", str(crf), "-preset", "medium", "-pix_fmt", "yuv420p",
            "-movflags", "+faststart", out_path]
    subprocess.run(cmd, check=True, stdin=subprocess.DEVNULL)
    return out_path


def self_test():
    assert merge([[5, 6], [1, 2], [1.5, 3]]) == [[1, 3], [5, 6]]
    k = keeps_from_deletes([[1, 2], [4, 5]], 10)
    assert k == [[0, 1], [2, 4], [5, 10]], k
    k25 = keeps_from_deletes([[1.013, 2.017]], 3, fps=25)
    assert k25 == [[0, 1.0], [2.0, 3]], k25
    w = [{"text": "a", "start": 0.2, "end": 0.5}, {"text": "cut", "start": 1.2, "end": 1.6},
         {"text": "b", "start": 2.5, "end": 2.9}, {"text": "c", "start": 5.5, "end": 6.0}]
    r = retime(w, k)
    assert [x["text"] for x in r] == ["a", "b", "c"], r
    assert r[1]["start"] == 1.5 and r[2]["start"] == 3.5, r
    assert r[2]["source_start"] == 5.5
    r2 = retime(w, k, drop_cut=False)
    assert len(r2) == 4 and r2[1]["clamped"] and r2[1]["start"] == 1.0, r2
    g = filter_script([[0, 1], [2, 3]], True)
    assert "concat=n=2:v=1:a=1" in g and g.count("afade=t=in") == 2
    print("edl.py self-test ok")


if __name__ == "__main__":
    if "--self-test" in sys.argv:
        self_test()
    else:
        print(__doc__)
