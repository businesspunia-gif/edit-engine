#!/usr/bin/env python3
"""Word-level transcript in one normalized shape, whatever the provider.

    transcribe.py <media> <out.json> [--lang auto|en|de|...] [--model PATH]
    transcribe.py --normalize <provider.json> <out.json>     # convert an existing transcript
    transcribe.py --self-test

Output shape (every other script in this skill reads it):
    {"words": [{"text": "Hello", "start": 0.42, "end": 0.71}, ...],
     "duration": 104.0, "language": "en", "source": "<media path>"}

Default engine: whisper.cpp (`whisper-cli`) running locally, nothing is uploaded.
Model: --model, else $WHISPER_MODEL, else ~/.cache/whisper-cpp/ggml-large-v3-turbo.bin.
Falls back to the Python `whisper` CLI when whisper-cli is missing.

--normalize accepts: whisper.cpp full JSON (-ojf), openai-whisper JSON with
word_timestamps, ElevenLabs Scribe ({"words": [{"text","start","end","type"}]}),
or any list/obj of {"text"|"word", "start", "end"}. Cloud providers are optional;
if you use one, export its JSON and normalize it here.
"""
import json, os, re, shutil, subprocess, sys, tempfile

WORDISH = re.compile(r"\w", re.UNICODE)


def media_duration(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                          "-of", "csv=p=0", path], capture_output=True, text=True).stdout
    try:
        return round(float(out.strip()), 3)
    except ValueError:
        return None


def from_whisper_cpp(d):
    """whisper.cpp tokens are sub-word pieces; a leading space opens a new word."""
    words = []
    for seg in d.get("transcription", []):
        for t in seg.get("tokens", []):
            raw = t.get("text", "")
            if raw.startswith("[") or raw.startswith("<"):
                continue  # [_BEG_], <|endoftext|> and similar control tokens
            s, e = t["offsets"]["from"] / 1000, t["offsets"]["to"] / 1000
            if raw.startswith(" ") or not words:
                if raw.strip():
                    words.append({"text": raw.strip(), "start": s, "end": e})
            else:
                words[-1]["text"] += raw
                words[-1]["end"] = e
    return words


def from_generic(d):
    if isinstance(d, dict) and "transcription" in d:
        return from_whisper_cpp(d)
    items = []
    if isinstance(d, list):
        items = d
    elif isinstance(d, dict) and "words" in d:
        items = d["words"]
    elif isinstance(d, dict) and "segments" in d:  # openai-whisper --word_timestamps True
        for seg in d["segments"]:
            items.extend(seg.get("words", []))
    words = []
    for w in items:
        if w.get("type") in ("spacing", "audio_event"):
            continue
        text = (w.get("text") or w.get("word") or "").strip()
        if text and "start" in w and "end" in w:
            words.append({"text": text, "start": float(w["start"]), "end": float(w["end"])})
    return words


def clean(words):
    out = []
    for w in words:
        if not WORDISH.search(w["text"]):
            continue  # punctuation-only pieces
        w = {"text": w["text"], "start": round(w["start"], 3), "end": round(max(w["end"], w["start"]), 3)}
        if out and w["start"] < out[-1]["start"]:
            continue  # out-of-order token, drop rather than break monotonic time
        out.append(w)
    return out


def run_whisper_cpp(media, lang, model, tmp):
    wav = os.path.join(tmp, "a.wav")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", media, "-ac", "1", "-ar", "16000", wav],
                   check=True, stdin=subprocess.DEVNULL)
    cmd = ["whisper-cli", "-m", model, "-l", lang, "-f", wav, "-ojf", "-sow",
           "-of", os.path.join(tmp, "full"), "-np"]
    if "large-v3-turbo" in os.path.basename(model):
        cmd += ["-dtw", "large.v3.turbo"]  # token-level alignment = tighter word times
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    d = json.load(open(os.path.join(tmp, "full.json")))
    detected = d.get("result", {}).get("language", lang)
    return from_whisper_cpp(d), detected


def run_openai_whisper(media, lang, tmp):
    cmd = ["whisper", media, "--word_timestamps", "True", "--output_format", "json",
           "--output_dir", tmp]
    if lang != "auto":
        cmd += ["--language", lang]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL)
    stem = os.path.splitext(os.path.basename(media))[0]
    d = json.load(open(os.path.join(tmp, stem + ".json")))
    return from_generic(d), d.get("language", lang)


def self_test():
    fake = {"transcription": [{"tokens": [
        {"text": "[_BEG_]", "offsets": {"from": 0, "to": 0}},
        {"text": " Hel", "offsets": {"from": 100, "to": 300}},
        {"text": "lo", "offsets": {"from": 300, "to": 450}},
        {"text": " world", "offsets": {"from": 500, "to": 900}},
        {"text": ".", "offsets": {"from": 900, "to": 950}},
        {"text": " ,", "offsets": {"from": 960, "to": 970}}]}]}
    w = clean(from_whisper_cpp(fake))
    assert [x["text"] for x in w] == ["Hello", "world."], w
    assert w[0]["start"] == 0.1 and w[0]["end"] == 0.45, w
    eleven = {"words": [{"text": "Hi", "start": 0, "end": .2, "type": "word"},
                        {"text": " ", "start": .2, "end": .3, "type": "spacing"},
                        {"text": "there", "start": .3, "end": .6, "type": "word"}]}
    assert [x["text"] for x in clean(from_generic(eleven))] == ["Hi", "there"]
    oa = {"segments": [{"words": [{"word": " yes", "start": 1, "end": 1.2}]}]}
    assert clean(from_generic(oa))[0]["text"] == "yes"
    print("transcribe.py self-test ok")


def main(argv):
    if "--self-test" in argv:
        return self_test()
    opt = lambda k, d=None: argv[argv.index(k) + 1] if k in argv else d
    if "--normalize" in argv:
        i = argv.index("--normalize")
        src, dst = argv[i + 1], argv[i + 2]
        words = clean(from_generic(json.load(open(src))))
        doc = {"words": words, "duration": words[-1]["end"] if words else 0,
               "language": None, "source": src}
    else:
        pos = [a for i, a in enumerate(argv) if not a.startswith("--") and (i == 0 or not argv[i - 1] in ("--lang", "--model"))]
        if len(pos) < 2:
            sys.exit(__doc__)
        media, dst = pos[0], pos[1]
        lang = opt("--lang", "auto")
        model = opt("--model") or os.environ.get("WHISPER_MODEL") or \
            os.path.expanduser("~/.cache/whisper-cpp/ggml-large-v3-turbo.bin")
        with tempfile.TemporaryDirectory() as tmp:
            if shutil.which("whisper-cli"):
                if not os.path.exists(model):
                    sys.exit(f"whisper.cpp model not found: {model} (pass --model or set WHISPER_MODEL)")
                words, detected = run_whisper_cpp(media, lang, model, tmp)
            elif shutil.which("whisper"):
                words, detected = run_openai_whisper(media, lang, tmp)
            else:
                sys.exit("No local transcriber found. Install whisper.cpp (whisper-cli) or openai-whisper, "
                         "or transcribe elsewhere and use --normalize.")
        words = clean(words)
        doc = {"words": words, "duration": media_duration(media), "language": detected, "source": media}
    json.dump(doc, open(dst, "w"), ensure_ascii=False, indent=1)
    span = doc["words"][-1]["end"] - doc["words"][0]["start"] if doc["words"] else 0
    rate = len(doc["words"]) / span if span else 0
    print(json.dumps({"words": len(doc["words"]), "duration": doc["duration"],
                      "language": doc["language"], "words_per_sec": round(rate, 2), "out": dst}))


if __name__ == "__main__":
    main(sys.argv[1:])
