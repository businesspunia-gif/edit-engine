#!/usr/bin/env python3
"""Measure a reference video (or your own render) so a style can be rebuilt from numbers.

    analyze_reference.py <video> <out-dir> [--sheet-fps 4] [--cut 0.35] [--bpm 128 --phase 0.0]
    analyze_reference.py --self-test

Writes to <out-dir>:
    report.json / report.md   shot list (start, length, brightness, 3 dominant colors,
                              motion), cut rhythm stats, brightness + motion every 0.5 s,
                              audio loudness every 0.25 s and onsets (if the file has audio),
                              and with --bpm: each cut's distance to the nearest beat/half beat
    sheet_NN.jpg              contact sheets, 4x4 tiles at --sheet-fps
    shots.jpg                 one mid-frame per shot, in order: the fastest way to read an edit

Cut detection: mean absolute luma difference between consecutive 64x36 frames.
A frame is a cut when its difference is above max(cut x 90, 5 x median difference)
AND at least 2.5x the median of its 6 neighbours (so particle storms and fast
continuous moves are not counted). Flash frames still register as cuts, and
dissolves do not; read shots.jpg before trusting a number.
Needs ffmpeg + ffprobe.
"""
import json, math, os, statistics, struct, subprocess, sys

W, H = 64, 36


def probe(path):
    d = json.loads(subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                                   "format=duration:stream=codec_type,width,height,r_frame_rate",
                                   "-of", "json", path], capture_output=True, text=True, check=True).stdout)
    v = next(s for s in d["streams"] if s["codec_type"] == "video")
    n, den = v["r_frame_rate"].split("/")
    return {"duration": float(d["format"]["duration"]), "fps": float(n) / float(den),
            "width": v["width"], "height": v["height"],
            "has_audio": any(s["codec_type"] == "audio" for s in d["streams"])}


def frames_rgb(path):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-vf", f"scale={W}:{H}:flags=area",
                          "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True, check=True).stdout
    size = W * H * 3
    return [raw[i:i + size] for i in range(0, len(raw) - size + 1, size)]


def luma(fr):
    return [0.299 * fr[i] + 0.587 * fr[i + 1] + 0.114 * fr[i + 2] for i in range(0, len(fr), 3)]


def detect_cuts(diffs, frac):
    med = statistics.median(diffs[1:]) if len(diffs) > 2 else 0
    thr = max(frac * 255 * 0.35, 5 * med)
    cuts = []
    for i, d in enumerate(diffs):
        if not i or d <= thr or (cuts and i - cuts[-1] < 2):
            continue
        # a cut is a spike: fast continuous motion (particles, waves) keeps its neighbours high too
        around = [x for x in diffs[max(1, i - 3):i] + diffs[i + 1:i + 4]]
        if around and d < 2.5 * statistics.median(around):
            continue
        cuts.append(i)
    return cuts, thr


def dominant(fr, k=3):
    bins = {}
    for i in range(0, len(fr), 3):
        key = (fr[i] >> 5, fr[i + 1] >> 5, fr[i + 2] >> 5)
        bins[key] = bins.get(key, 0) + 1
    top = sorted(bins.items(), key=lambda x: -x[1])[:k]
    return ["#%02x%02x%02x" % tuple((c << 5) + 16 for c in key) for key, _ in top]


def audio_profile(path, sr=22050):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-vn", "-f", "s16le", "-ac", "1",
                          "-ar", str(sr), "-"], capture_output=True, check=True).stdout
    n = len(raw) // 2
    pcm = struct.unpack(f"<{n}h", raw[:n * 2])
    hop = 512
    env = []
    for i in range(0, n - hop, hop):
        seg = pcm[i:i + hop]
        env.append(math.sqrt(sum(x * x for x in seg) / hop) / 32768)
    q = int(0.25 * sr / hop)
    rms = [round(20 * math.log10(max(sum(e * e for e in env[i:i + q]) / max(1, len(env[i:i + q])), 1e-12) ** 0.5), 1)
           for i in range(0, len(env), q)]
    flux = [max(0.0, env[i] - env[i - 1]) for i in range(1, len(env))]
    thr = statistics.mean(flux) + 2 * statistics.pstdev(flux) if flux else 1
    onsets, last = [], -1
    for i in range(1, len(flux) - 1):
        if flux[i] > thr and flux[i] >= flux[i - 1] and flux[i] >= flux[i + 1] and i - last > 4:
            onsets.append(round((i + 1) * hop / sr, 3))
            last = i
    return rms, onsets


def beat_offsets(times, bpm, phase):
    p = 60 / bpm
    out = []
    for t in times:
        b = (t - phase) / p
        ob = (b - round(b)) * p
        oh = (b * 2 - round(b * 2)) * p / 2
        out.append({"t": t, "beat": round(b, 2), "off_beat_ms": round(ob * 1000), "off_half_ms": round(oh * 1000)})
    return out


def sheets(path, out, fps_sheet, shot_mids, fps):
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", path, "-vf",
                    f"fps={fps_sheet},scale=480:-2,tile=4x4:padding=4", "-q:v", "4",
                    os.path.join(out, "sheet_%02d.jpg")], check=True)
    if shot_mids:
        sel = "+".join(f"eq(n\\,{m})" for m in shot_mids)
        cols = min(6, len(shot_mids))
        rows = math.ceil(len(shot_mids) / cols)
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", path, "-vf",
                        f"select='{sel}',scale=320:-2,tile={cols}x{rows}:padding=4",
                        "-frames:v", "1", "-fps_mode", "passthrough", "-q:v", "4",
                        os.path.join(out, "shots.jpg")], check=True)


def analyze(path, out, sheet_fps=4, frac=0.35, bpm=None, phase=0.0):
    os.makedirs(out, exist_ok=True)
    info = probe(path)
    fps = info["fps"]
    frs = frames_rgb(path)
    lum = [statistics.fmean(luma(f)) for f in frs]
    diffs = [0.0]
    prev = luma(frs[0]) if frs else []
    for f in frs[1:]:
        cur = luma(f)
        diffs.append(sum(abs(a - b) for a, b in zip(cur, prev)) / len(cur))
        prev = cur
    cuts, thr = detect_cuts(diffs, frac)
    bounds = [0] + cuts + [len(frs)]
    shots = []
    for s, e in zip(bounds, bounds[1:]):
        mid = (s + e) // 2
        shots.append({"start": round(s / fps, 3), "length": round((e - s) / fps, 3), "frames": e - s,
                      "luma": round(statistics.fmean(lum[s:e])), "motion": round(statistics.fmean(diffs[s + 1:e] or [0]), 1),
                      "colors": dominant(frs[mid]), "mid_frame": mid})
    half = max(1, round(fps / 2))
    lengths = [s["length"] for s in shots]
    rep = {"file": os.path.basename(path), **info, "frames": len(frs), "cut_threshold": round(thr, 1),
           "shots": shots, "cut_times": [round(c / fps, 3) for c in cuts],
           "stats": {"shots": len(shots), "cuts_per_sec": round(len(cuts) / info["duration"], 2),
                     "shot_len_mean": round(statistics.fmean(lengths), 2),
                     "shot_len_median": round(statistics.median(lengths), 2),
                     "shot_len_min": min(lengths), "shot_len_max": max(lengths),
                     "shots_under_0_5s": sum(1 for x in lengths if x < 0.5)},
           "luma_every_0_5s": [round(statistics.fmean(lum[i:i + half])) for i in range(0, len(lum), half)],
           "motion_every_0_5s": [round(statistics.fmean(diffs[i:i + half]), 1) for i in range(0, len(diffs), half)]}
    if info["has_audio"]:
        rep["audio_rms_db_every_0_25s"], rep["audio_onsets"] = audio_profile(path)
    if bpm:
        rep["cuts_vs_beat"] = beat_offsets(rep["cut_times"], bpm, phase)
    json.dump(rep, open(os.path.join(out, "report.json"), "w"), indent=1)
    sheets(path, out, sheet_fps, [s["mid_frame"] for s in shots][:60], fps)
    md = [f"# Reference: {rep['file']}", "",
          f"{info['width']}x{info['height']}, {fps:.2f} fps, {info['duration']:.2f}s, audio: {info['has_audio']}", "",
          "| shots | cuts/s | mean | median | min | max | <0.5s |", "|---|---|---|---|---|---|---|",
          "| {shots} | {cuts_per_sec} | {shot_len_mean}s | {shot_len_median}s | {shot_len_min}s | {shot_len_max}s | {shots_under_0_5s} |".format(**rep["stats"]),
          "", "| # | start | length | luma | motion | colors |", "|---|---|---|---|---|---|"]
    md += [f"| {i} | {s['start']:.2f} | {s['length']:.2f} | {s['luma']} | {s['motion']} | {' '.join(s['colors'])} |"
           for i, s in enumerate(shots)]
    md += ["", "Brightness every 0.5 s: " + " ".join(map(str, rep["luma_every_0_5s"])),
           "", "Motion every 0.5 s: " + " ".join(map(str, rep["motion_every_0_5s"]))]
    if "audio_onsets" in rep:
        md += ["", f"Audio onsets ({len(rep['audio_onsets'])}): " + " ".join(map(str, rep["audio_onsets"][:80]))]
    if bpm:
        md += ["", f"Cuts vs {bpm} BPM grid (phase {phase}s): " +
               ", ".join(f"{c['t']}s {c['off_beat_ms']:+d}ms/{c['off_half_ms']:+d}ms" for c in rep["cuts_vs_beat"])]
    open(os.path.join(out, "report.md"), "w").write("\n".join(md) + "\n")
    return rep


def self_test():
    import tempfile
    d = tempfile.mkdtemp()
    src = os.path.join(d, "t.mp4")
    # three 1 s colour shots (red, white, blue) at 30 fps with a tone: cuts at 1.0 and 2.0
    subprocess.run(["ffmpeg", "-v", "error", "-y",
                    "-f", "lavfi", "-i", "color=c=red:s=320x180:r=30:d=1",
                    "-f", "lavfi", "-i", "color=c=white:s=320x180:r=30:d=1",
                    "-f", "lavfi", "-i", "color=c=blue:s=320x180:r=30:d=1",
                    "-f", "lavfi", "-i", "sine=f=440:d=3",
                    "-filter_complex", "[0:v][1:v][2:v]concat=n=3:v=1:a=0[v]", "-map", "[v]", "-map", "3:a",
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", "-shortest", src], check=True)
    r = analyze(src, os.path.join(d, "out"), bpm=120, phase=0)
    assert r["cut_times"] == [1.0, 2.0], r["cut_times"]
    assert r["shots"][1]["luma"] > 240 and r["shots"][0]["luma"] < 120, r["shots"]
    assert all(c["off_beat_ms"] == 0 for c in r["cuts_vs_beat"])
    assert os.path.exists(os.path.join(d, "out", "shots.jpg"))
    print("analyze_reference.py self-test ok")


def main(argv):
    if "--self-test" in argv:
        return self_test()
    opt = lambda k, dflt=None: argv[argv.index(k) + 1] if k in argv else dflt
    pos = [a for i, a in enumerate(argv) if not a.startswith("--") and (i == 0 or not argv[i - 1].startswith("--"))]
    if len(pos) < 2:
        sys.exit(__doc__)
    r = analyze(pos[0], pos[1], float(opt("--sheet-fps", 4)), float(opt("--cut", 0.35)),
                float(opt("--bpm")) if opt("--bpm") else None, float(opt("--phase", 0)))
    print(json.dumps({"duration": r["duration"], "fps": round(r["fps"], 3), **r["stats"],
                      "audio": r["has_audio"], "out": pos[1]}))


if __name__ == "__main__":
    main(sys.argv[1:])
