#!/usr/bin/env python3
"""Tempo, beat phase and a frame-exact beat sheet, from music or from a reference's cuts.

    beat_grid.py <audio-or-video> [--bpm-range 70-180] [--fps 30] [--beats]
                 [--length 15 --chapters "Intro:4, Build:8, Drop:4, Flurry:4, End:rest"]
    beat_grid.py --from-cuts report.json [--window 13-16]  # silent reference: tempo from its cut times
    beat_grid.py --bpm 128 --phase 0.08 --fps 30 --length 15 --chapters "..."   # sheet only
    beat_grid.py --self-test

Tempo: onset envelope (log-energy rise, ~86 frames/s), autocorrelation with a mild
preference for 90-150 BPM, then a fine search of BPM and phase that maximises the
envelope sampled on the grid. Phase is measured twice, on the kick band (<150 Hz)
and full band; hi-hats can pull full band half a beat late, so the kick phase is
the one to use and the script warns when they disagree.

--beats prints low-band energy per beat: a jump of ~10 dB marks a drop, a dip
before it marks the pre-drop gap. Cut there.

--from-cuts fits a grid to measured cut times (from analyze_reference.py) and
reports how many cuts land within 2 frames of a beat or half beat. It needs 6+
cuts to be meaningful and cannot tell 2x tempo apart from 1x on its own. Use
--window to keep only the cut-to-music stretch (a screen recording adds its own
start/stop cuts; single flash frames also add noise).
"""
import cmath, json, math, struct, subprocess, sys

SR, HOP = 11025, 128
FR = SR / HOP  # envelope frames per second


def envelope(path, lowpass=None):
    af = ["-af", f"lowpass=f={lowpass},lowpass=f={lowpass}"] if lowpass else []
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-vn", *af, "-f", "s16le", "-ac", "1",
                          "-ar", str(SR), "-"], capture_output=True, check=True).stdout
    n = len(raw) // 2
    pcm = struct.unpack(f"<{n}h", raw[:n * 2])
    energy = [10 * math.log10(sum(x * x for x in pcm[i:i + HOP]) / HOP + 1) for i in range(0, n - HOP, HOP)]
    return onset_strength(energy), energy


def onset_strength(energy):
    on = [0.0] + [max(0.0, energy[i] - energy[i - 1]) for i in range(1, len(energy))]
    m = sum(on) / len(on) if on else 0
    return [x - m if x > m else 0.0 for x in on]


def grid_score(env, period_f, phase_f):
    s, k, n = 0.0, 0, len(env)
    t = phase_f
    while t < n - 1:
        i = int(t)
        s += env[i] * (1 - (t - i)) + env[i + 1] * (t - i)
        k += 1
        t += period_f
    return s / k if k else 0


def best_phase(env, period_f, steps=64):
    return max((grid_score(env, period_f, period_f * j / steps), period_f * j / steps) for j in range(steps))


def tempo(env, lo=70, hi=180):
    n = len(env)
    best = None
    for bpm10 in range(lo * 10, hi * 10 + 1, 5):   # coarse: 0.5 BPM
        bpm = bpm10 / 10
        lag = FR * 60 / bpm
        li = int(lag)
        if li + 1 >= n:
            continue
        ac = sum(env[i] * (env[i + li] * (1 - (lag - li)) + env[i + li + 1] * (lag - li)) for i in range(0, n - li - 1, 2))
        prior = math.exp(-0.5 * (math.log2(bpm / 120) / 0.6) ** 2)
        if best is None or ac * prior > best[0]:
            best = (ac * prior, bpm)
    coarse = best[1]
    fine = max((best_phase(env, FR * 60 / (coarse + d / 20), 32)[0], coarse + d / 20) for d in range(-20, 21))
    return round(fine[1], 2)


def phase_seconds(env, bpm):
    return round(best_phase(env, FR * 60 / bpm, 128)[1] / FR, 4)


def per_beat_db(energy, bpm, phase, count):
    p = FR * 60 / bpm
    out = []
    for b in range(count):
        a = int((phase * FR) + b * p)
        seg = energy[a:int(a + p)]
        if not seg:
            break
        out.append(round(10 * math.log10(sum(10 ** (e / 10) for e in seg) / len(seg)), 1))
    return out


def fit_cuts(times, lo=70, hi=180, fps=60):
    """Grid that puts the most cuts on beats or half beats. Returns candidates, best first."""
    cands = []
    for bpm10 in range(lo * 10, hi * 10 + 1):
        bpm = bpm10 / 10
        half = 60 / bpm / 2
        z = sum(cmath.exp(2j * math.pi * t / half) for t in times) / len(times)
        cands.append((abs(z), bpm, (cmath.phase(z) / (2 * math.pi)) * half % half))
    top = max(c[0] for c in cands)
    near = [c for c in cands if c[0] >= 0.97 * top]
    r, bpm, ph = min(near, key=lambda c: c[1])  # slowest tempo that fits as well as the best
    half = 60 / bpm / 2
    on = sum(1 for t in times if abs(((t - ph) / half) - round((t - ph) / half)) * half <= 2 / fps)
    return {"bpm": bpm, "phase": round(ph, 4), "fit": round(r, 3), "cuts_on_grid": on, "cuts": len(times),
            "others": sorted({round(c[1]) for c in sorted(cands, reverse=True)[:40]})[:8]}


def sheet(bpm, phase, fps, length, chapters):
    p = 60 / bpm
    rows, beat = [], 0
    total = int((length - phase) / p) + 1 if length else 0
    for name, n in chapters:
        n = total - beat if n == "rest" else int(n)
        s = phase + beat * p
        e = min(phase + (beat + n) * p, length) if length else phase + (beat + n) * p
        rows.append((name.strip(), beat, n, round(s, 3), round(s * fps), round(e, 3), round(e * fps)))
        beat += n
    return rows


def parse_chapters(txt):
    out = []
    for part in txt.split(","):
        name, _, n = part.strip().rpartition(":")
        out.append((name, n.strip()))
    return out


def self_test():
    # synthetic click track: 124 BPM, first beat at 0.2 s, clicks on every beat + softer off-beat hats
    bpm, ph = 124.0, 0.2
    energy = [0.0] * int(FR * 20)
    for b in range(40):
        i = int((ph + b * 60 / bpm) * FR)
        if i + 3 < len(energy):
            energy[i:i + 3] = [30, 20, 10]
        j = int((ph + (b + 0.5) * 60 / bpm) * FR)
        if j + 1 < len(energy):
            energy[j] = 12
    env = onset_strength(energy)
    est = tempo(env)
    assert abs(est - bpm) < 0.6, est
    assert abs(phase_seconds(env, est) - ph) < 0.03, phase_seconds(env, est)
    cuts = [ph + k * 60 / bpm for k in (4, 12, 16, 20, 22, 23)] + [ph + 23.5 * 60 / bpm]
    f = fit_cuts(cuts)
    assert abs(f["bpm"] - bpm) < 1.5 and f["cuts_on_grid"] == len(cuts), f
    rows = sheet(128, 0.0, 30, 15, parse_chapters("A:4, B:8, End:rest"))
    assert rows[1][3] == round(4 * 60 / 128, 3) and rows[-1][0] == "End"
    print("beat_grid.py self-test ok")


def main(argv):
    if "--self-test" in argv:
        return self_test()
    opt = lambda k, d=None: argv[argv.index(k) + 1] if k in argv else d
    fps = float(opt("--fps", 30))
    lo, hi = map(int, opt("--bpm-range", "70-180").split("-"))
    length = float(opt("--length", 0)) or None
    res = {}
    if opt("--from-cuts"):
        rep = json.load(open(opt("--from-cuts")))
        fps = float(opt("--fps", rep.get("fps", 60)))
        times = rep["cut_times"]
        if opt("--window"):  # ignore cuts outside the part that is actually edited to music
            a, b = map(float, opt("--window").split("-"))
            times = [t for t in times if a <= t <= b]
        res = fit_cuts(times, lo, hi, fps)
        bpm, phase = res["bpm"], res["phase"]
        length = length or rep.get("duration")
    elif opt("--bpm"):
        bpm, phase = float(opt("--bpm")), float(opt("--phase", 0))
    else:
        pos = [a for i, a in enumerate(argv) if not a.startswith("--") and (i == 0 or not argv[i - 1].startswith("--"))]
        if not pos:
            sys.exit(__doc__)
        env_low, energy_low = envelope(pos[0], lowpass=150)
        env_full, _ = envelope(pos[0])
        bpm = tempo(env_full, lo, hi)
        phase = phase_seconds(env_low, bpm)
        full_phase = phase_seconds(env_full, bpm)
        p = 60 / bpm
        diff = abs(((phase - full_phase) + p / 2) % p - p / 2)
        res = {"bpm": bpm, "period": round(p, 4), "phase_kick": phase, "phase_full": full_phase,
               "warning": "kick and full-band phase disagree; trust the kick phase" if diff > p / 4 else None}
        if "--beats" in argv:
            res["low_band_db_per_beat"] = per_beat_db(energy_low, bpm, phase, int(len(energy_low) / FR / p))
        length = length or len(energy_low) / FR
    res.update({"bpm": bpm, "phase": phase, "frame_per_beat": round(60 / bpm * fps, 2), "fps": fps})
    print(json.dumps(res))
    if opt("--chapters"):
        print("\n| chapter | first beat | beats | start s | start frame | end s | end frame |\n|---|---|---|---|---|---|---|")
        for r in sheet(bpm, phase, fps, length, parse_chapters(opt("--chapters"))):
            print("| " + " | ".join(map(str, r)) + " |")


if __name__ == "__main__":
    main(sys.argv[1:])
