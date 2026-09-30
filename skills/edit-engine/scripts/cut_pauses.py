#!/usr/bin/env python3
"""Stage 1: remove dead air. Leaves every spoken word alone.

    cut_pauses.py <video> <words.json> --out-dir DIR [--preset long|short]
                  [--min-pause S] [--breath S] [--sentence-breath S]
                  [--threshold DB] [--render] [--self-test]

Why audio AND transcript: local ASR stretches word ends across the silence that
follows them, so transcript gaps undercount pauses. Silence is measured on the
audio (10 ms RMS frames, threshold adapted to this recording's noise floor and
speech level); the transcript only says whether a pause ends a sentence, which
earns a slightly longer breath.

Presets
    long   min pause 0.45 s, breath 0.18 s, after a sentence 0.30 s  (YouTube talking head)
    short  min pause 0.25 s, breath 0.08 s, after a sentence 0.14 s  (Shorts/Reels, dense)

Writes to --out-dir:
    <stem>.pauses.edl.json     keep/delete ranges on the source timeline
    <stem>.pauses.words.json   transcript retimed to the cut (feed this to stage 2)
    <stem>.pauses.md           summary + the 10 longest pauses removed
    <stem>.pauses.mp4          with --render (re-encode, audio fades at each join)
"""
import json, math, os, struct, subprocess, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import edl  # noqa: E402

PRESETS = {"long": dict(min_pause=0.45, breath=0.18, sentence_breath=0.30, head=0.15, tail=0.35),
           "short": dict(min_pause=0.25, breath=0.08, sentence_breath=0.14, head=0.05, tail=0.20)}
HOP = 0.01


def rms_db(path, sr=16000):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-vn", "-f", "s16le", "-ac", "1",
                          "-ar", str(sr), "-"], capture_output=True, check=True).stdout
    n = len(raw) // 2
    pcm = struct.unpack(f"<{n}h", raw[:n * 2])
    win = int(sr * HOP)
    out = []
    for i in range(0, n - win + 1, win):
        seg = pcm[i:i + win]
        out.append(20 * math.log10(math.sqrt(sum(x * x for x in seg) / win) / 32768 + 1e-9))
    return out


def auto_threshold(db):
    s = sorted(db)
    floor, speech = s[int(len(s) * 0.10)], s[int(len(s) * 0.90)]
    return floor + (speech - floor) * 0.22, floor, speech  # low: soft word endings must survive


def silent_runs(db, thr, min_len, blip=0.06):
    """Runs of frames under thr, bridging voiced blips shorter than `blip` (clicks, breaths)."""
    quiet = [d < thr for d in db]
    runs, i, n = [], 0, len(quiet)
    while i < n:
        if not quiet[i]:
            i += 1
            continue
        j = i
        while j < n:
            if quiet[j]:
                j += 1
                continue
            k = j
            while k < n and not quiet[k]:
                k += 1
            if (k - j) * HOP < blip and k < n:
                j = k
            else:
                break
        if (j - i) * HOP >= min_len:
            runs.append([i * HOP, j * HOP])
        i = max(j, i + 1)
    return runs


def ends_sentence(words, t):
    prev = [w for w in words if w["start"] <= t + 0.05]
    return bool(prev) and prev[-1]["text"].rstrip()[-1:] in ".!?…"


def plan(db, words, duration, p, thr):
    runs = silent_runs(db, thr, p["min_pause"])
    deletes = []
    voiced = [i * HOP for i, d in enumerate(db) if d >= thr]
    first = voiced[0] if voiced else 0.0
    last = voiced[-1] + HOP if voiced else duration
    if first - p["head"] > 0:
        deletes.append([0.0, first - p["head"], "lead-in"])
    if last + p["tail"] < duration:
        deletes.append([last + p["tail"], duration, "tail"])
    for a, b in runs:
        if a <= first or b >= last:
            continue
        keep = p["sentence_breath"] if ends_sentence(words, a) else p["breath"]
        if b - a <= keep:
            continue
        ca, cb = a + keep * 0.55, b - keep * 0.45  # bias the breath toward the phrase that just ended
        deletes.append([round(ca, 3), round(cb, 3), f"pause {b - a:.2f}s"])
    return deletes


def self_test():
    # 1 s speech, 0.8 s silence, 1 s speech, 0.2 s silence (kept: too short), 1 s speech, 1 s tail
    db = [-20] * 100 + [-60] * 80 + [-20] * 100 + [-60] * 20 + [-20] * 100 + [-60] * 100
    db[150] = -20  # 10 ms click inside the long pause must not split it
    thr, _, _ = auto_threshold(db)
    assert -60 < thr < -20
    words = [{"text": "One.", "start": 0.1, "end": 0.9}, {"text": "two", "start": 1.9, "end": 2.7},
             {"text": "three", "start": 3.1, "end": 3.9}]
    d = plan(db, words, 5.0, PRESETS["long"], thr)
    pauses = [x for x in d if x[2].startswith("pause")]
    assert len(pauses) == 1, d
    a, b, _ = pauses[0]
    assert abs((b - a) - (0.8 - 0.30)) < 0.02, pauses  # sentence end -> 0.30 s breath kept
    assert any(x[2] == "tail" for x in d)
    print("cut_pauses.py self-test ok")


def main(argv):
    if "--self-test" in argv:
        return self_test()
    opt = lambda k, d=None: argv[argv.index(k) + 1] if k in argv else d
    pos = [a for i, a in enumerate(argv) if not a.startswith("--") and (i == 0 or not argv[i - 1].startswith("--") or argv[i - 1] == "--render")]
    if len(pos) < 2:
        sys.exit(__doc__)
    video, words_path = pos[0], pos[1]
    out_dir = opt("--out-dir", os.path.dirname(os.path.abspath(words_path)))
    os.makedirs(out_dir, exist_ok=True)
    p = dict(PRESETS[opt("--preset", "long")])
    for k in ("min_pause", "breath", "sentence_breath"):
        if opt("--" + k.replace("_", "-")):
            p[k] = float(opt("--" + k.replace("_", "-")))
    words, _ = edl.load_words(words_path)
    duration, fps, _ = edl.probe(video)
    db = rms_db(video)
    thr, floor, speech = auto_threshold(db)
    if opt("--threshold"):
        thr = float(opt("--threshold"))
    deletes = plan(db, words, duration, p, thr)
    keeps = edl.keeps_from_deletes(deletes, duration, fps)
    stem = os.path.join(out_dir, os.path.splitext(os.path.basename(video))[0])
    doc = edl.edl_doc(video, duration, fps, keeps, deletes, stage="pauses", params=p,
                      threshold_db=round(thr, 1), noise_floor_db=round(floor, 1), speech_db=round(speech, 1))
    json.dump(doc, open(stem + ".pauses.edl.json", "w"), indent=1)
    new_words = edl.retime(words, keeps, drop_cut=False)
    json.dump({"words": new_words, "duration": doc["edited_duration"], "source": video},
              open(stem + ".pauses.words.json", "w"), ensure_ascii=False, indent=1)
    removed = duration - doc["edited_duration"]
    top = sorted(doc["delete"], key=lambda d: d[0] - d[1])[:10]
    md = [f"# Pause cut: {os.path.basename(video)}", "",
          f"- source {duration:.2f}s -> edited {doc['edited_duration']:.2f}s, removed {removed:.2f}s ({removed / duration:.1%})",
          f"- {len(doc['delete'])} cuts, {len(keeps)} kept segments, threshold {thr:.1f} dB "
          f"(floor {floor:.1f}, speech {speech:.1f})",
          f"- words in {len(words)}, words out {len(new_words)}, clamped {sum(1 for w in new_words if w.get('clamped'))}"
          " (clamped = ASR put the word inside a cut; spot-check those joins by ear)", "",
          "| from | to | removed | why |", "|---|---|---|---|"]
    md += [f"| {a:.2f} | {b:.2f} | {b - a:.2f}s | {w} |" for a, b, *r in top for w in [r[0] if r else ""]]
    open(stem + ".pauses.md", "w").write("\n".join(md) + "\n")
    result = {"source_s": round(duration, 2), "edited_s": doc["edited_duration"], "removed_s": round(removed, 2),
              "removed_pct": round(100 * removed / duration, 1), "cuts": len(doc["delete"]),
              "words_in": len(words), "words_out": len(new_words),
              "words_clamped": sum(1 for w in new_words if w.get("clamped")), "threshold_db": round(thr, 1)}
    if "--render" in argv:
        result["render"] = edl.render(video, keeps, stem + ".pauses.mp4")
        result["render_s"] = round(edl.probe(result["render"])[0], 3)
    print(json.dumps(result))


if __name__ == "__main__":
    main(sys.argv[1:])
