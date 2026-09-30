#!/usr/bin/env python3
"""Evidence for VERIFY.md: measure the encoded file, never the source code.

    verify_render.py <render.mp4> <out-dir> [--edl final.edl.json] [--at 3.2,7.9]
                     [--words final.words.json] [--lang de] [--expect-duration 89.4]
    verify_render.py --self-test

Checks
    streams      duration, fps, resolution, audio present
    black        intervals >= 0.1 s that are (almost) black
    freeze       stretches >= 1.5 s with no picture change (fine for a held title, bad elsewhere)
    loudness     integrated LUFS and true peak (targets: talking head -16 LUFS / -1 dBTP,
                 promo -14 LUFS / -1 dBTP)
    strips       10 contiguous frames around every join (--edl) and every --at time,
                 tiled 5x2 into strip_<t>.jpg. Look at them: a one-frame pop, ghost layer
                 or black flash only shows up here
    word sync    with --words: re-transcribes the render and compares each word's start
                 with the transcript the graphics were timed to (median / p95 / max drift).
                 The fresh transcript is saved as fresh.words.json. It was made from the
                 finished audio, so when drift is large, retime captions and graphics to it

Writes verify.json and verify.md (paste into VERIFY.md, then add what you looked at
and listened to yourself, and what you could not check).
"""
import difflib, json, os, re, statistics, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import edl  # noqa: E402


def ff_log(path, vf=None, af=None):
    cmd = ["ffmpeg", "-hide_banner", "-nostats", "-i", path]
    cmd += ["-vf", vf] if vf else ["-vn"]
    cmd += ["-af", af] if af else ["-an"]
    cmd += ["-f", "null", "-"]
    return subprocess.run(cmd, capture_output=True, text=True).stderr


def black(path):
    log = ff_log(path, vf="blackdetect=d=0.1:pix_th=0.10")
    return [[float(a), float(b)] for a, b in re.findall(r"black_start:([\d.]+) black_end:([\d.]+)", log)]


def freezes(path):
    log = ff_log(path, vf="freezedetect=n=0.003:d=1.5")
    starts = [float(x) for x in re.findall(r"freeze_start: ([\d.]+)", log)]
    ends = [float(x) for x in re.findall(r"freeze_end: ([\d.]+)", log)]
    return [[s, e] for s, e in zip(starts, ends + [None] * (len(starts) - len(ends)))]


def loudness(path):
    log = ff_log(path, af="ebur128=peak=true")
    summ = log[log.rfind("Summary:"):]
    i = re.search(r"I:\s+(-?[\d.]+) LUFS", summ)
    tp = re.search(r"Peak:\s+(-?[\d.]+) dBFS", summ)
    return {"lufs": float(i.group(1)) if i else None, "true_peak_db": float(tp.group(1)) if tp else None}


def joins(e):
    t, out = 0.0, []
    for a, b in e["keep"][:-1]:
        t += b - a
        out.append(round(t, 3))
    return out


def strip(path, t, fps, out_dir):
    n0 = max(0, round(t * fps) - 5)
    out = os.path.join(out_dir, f"strip_{t:07.2f}.jpg")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", path, "-vf",
                    f"select='between(n\\,{n0}\\,{n0 + 9})',scale=384:-2,tile=5x2:padding=4",
                    "-frames:v", "1", "-fps_mode", "passthrough", "-q:v", "4", out], check=True)
    return out


def norm(t):
    return re.sub(r"[^\w]", "", t.lower())


def word_sync(render, words_path, lang, out_dir):
    fresh_path = os.path.join(out_dir, "fresh.words.json")
    subprocess.run([sys.executable, os.path.join(HERE, "transcribe.py"), render, fresh_path, "--lang", lang],
                   check=True, stdout=subprocess.DEVNULL)
    return compare_words(edl.load_words(words_path)[0], edl.load_words(fresh_path)[0])


def compare_words(expected, fresh):
    a, b = [norm(w["text"]) for w in expected], [norm(w["text"]) for w in fresh]
    drift = []
    for blk in difflib.SequenceMatcher(None, a, b, autojunk=False).get_matching_blocks():
        for k in range(blk.size):
            drift.append(fresh[blk.b + k]["start"] - expected[blk.a + k]["start"])
    if not drift:
        return {"matched": 0, "expected": len(a)}
    ad = sorted(abs(d) for d in drift)
    return {"matched": len(drift), "expected": len(a), "fresh": len(b),
            "median_ms": round(statistics.median(drift) * 1000), "p95_abs_ms": round(ad[int(len(ad) * 0.95) - 1 if len(ad) > 1 else 0] * 1000),
            "max_abs_ms": round(ad[-1] * 1000)}


def verify(render, out_dir, e=None, at=(), words=None, lang="auto", expect=None):
    os.makedirs(out_dir, exist_ok=True)
    dur, fps, has_audio = edl.probe(render)
    rep = {"file": render, "duration": round(dur, 3), "fps": fps, "audio": has_audio,
           "black": black(render), "freeze": freezes(render)}
    if expect:
        rep["duration_delta_ms"] = round((dur - expect) * 1000)
    if has_audio:
        rep["loudness"] = loudness(render)
    times = sorted(set((joins(e) if e else []) + list(at)))
    rep["strips"] = [strip(render, t, fps, out_dir) for t in times]
    if words:
        rep["word_sync"] = word_sync(render, words, lang, out_dir)
    json.dump(rep, open(os.path.join(out_dir, "verify.json"), "w"), indent=1)
    L = [f"## Measured: {os.path.basename(render)}", "",
         f"- {rep['duration']}s, {fps:.3f} fps, audio: {has_audio}"
         + (f", duration vs expected: {rep['duration_delta_ms']:+d} ms" if expect else ""),
         f"- black >= 0.1 s: {rep['black'] or 'none'}",
         f"- frozen >= 1.5 s: {rep['freeze'] or 'none'}"]
    if has_audio:
        L.append(f"- loudness: {rep['loudness']['lufs']} LUFS integrated, true peak {rep['loudness']['true_peak_db']} dBTP")
    if words:
        L.append(f"- word sync vs fresh transcript: {rep['word_sync']}")
    L.append(f"- {len(times)} frame strips written (joins + requested times); inspect every one")
    open(os.path.join(out_dir, "verify.md"), "w").write("\n".join(L) + "\n")
    return rep


def self_test():
    d = tempfile.mkdtemp()
    v = os.path.join(d, "t.mp4")
    subprocess.run(["ffmpeg", "-v", "error", "-y",
                    "-f", "lavfi", "-i", "testsrc2=s=320x180:r=30:d=2",
                    "-f", "lavfi", "-i", "color=c=black:s=320x180:r=30:d=0.5",
                    "-f", "lavfi", "-i", "testsrc2=s=320x180:r=30:d=1.5",
                    "-f", "lavfi", "-i", "sine=f=500:d=4",
                    "-filter_complex", "[0:v][1:v][2:v]concat=n=3:v=1:a=0[v]", "-map", "[v]", "-map", "3:a",
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", "-shortest", v], check=True)
    r = verify(v, os.path.join(d, "o"), e={"keep": [[0, 2], [5, 7]]}, at=[3.0], expect=4.0)
    assert r["black"] and abs(r["black"][0][0] - 2.0) < 0.05, r["black"]
    assert len(r["strips"]) == 2 and all(os.path.exists(s) for s in r["strips"])
    assert r["loudness"]["lufs"] is not None
    exp = [{"text": "a", "start": 1.0, "end": 1.2}, {"text": "b", "start": 2.0, "end": 2.2}]
    fr = [{"text": "A", "start": 1.05, "end": 1.2}, {"text": "b.", "start": 1.98, "end": 2.2}]
    c = compare_words(exp, fr)
    assert c["matched"] == 2 and c["max_abs_ms"] == 50, c
    print("verify_render.py self-test ok")


def main(argv):
    if "--self-test" in argv:
        return self_test()
    opt = lambda k, dflt=None: argv[argv.index(k) + 1] if k in argv else dflt
    pos = [a for i, a in enumerate(argv) if not a.startswith("--") and (i == 0 or not argv[i - 1].startswith("--"))]
    if len(pos) < 2:
        sys.exit(__doc__)
    e = json.load(open(opt("--edl"))) if opt("--edl") else None
    at = [float(x) for x in opt("--at").split(",")] if opt("--at") else []
    r = verify(pos[0], pos[1], e, at, opt("--words"), opt("--lang", "auto"),
               float(opt("--expect-duration")) if opt("--expect-duration") else None)
    r["strips"] = len(r["strips"])
    print(json.dumps(r))


if __name__ == "__main__":
    main(sys.argv[1:])
