#!/usr/bin/env python3
"""Stage 2a: propose mistake cuts. Proposes only. A human or the agent decides.

    find_mistakes.py <words.json> --out-dir DIR [--self-test]

Input: the transcript that matches the video you will cut (normally the
*.pauses.words.json from stage 1).

Candidate kinds
    retake    a sentence said again soon after; keep the LAST take, cut the earlier one(s)
    restart   a phrase abandoned and started over ("we built a- we built the whole thing")
    repeat    the same word twice in a row ("the the")
    filler    um / uh / äh / ähm / erm

Each candidate has cut [start, end], the text removed, what follows, context,
confidence 0-1 and a default verdict (cut | review | keep). Emphasis doubles
("very very", "never, never", "sehr sehr") are flagged keep.

Writes <stem>.mistakes.json and <stem>.mistakes.md. Turn the ones you approve
into {"cuts": [{"start", "end", "reason"}]} and run apply_cuts.py.
"""
import difflib, json, os, re, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import edl  # noqa: E402

FILLERS = {"um", "uh", "uhm", "erm", "hmm", "äh", "ähm", "öh", "eh", "ehm", "mhm"}
EMPHASIS = {"very", "really", "so", "never", "no", "yes", "sehr", "ganz", "nie", "nein", "ja",
            "viel", "much", "more", "mehr", "go", "bye", "tschüss", "danke", "thanks"}
SENT_END = re.compile(r"[.!?…]$")


def norm(t):
    return re.sub(r"[^\w]", "", t.lower())


def sentences(words, gap=0.7):
    """Split on sentence punctuation or long silence. Returns [[i0, i1), ...]."""
    out, start = [], 0
    for i, w in enumerate(words):
        nxt = words[i + 1] if i + 1 < len(words) else None
        if SENT_END.search(w["text"]) or nxt is None or nxt["start"] - w["end"] > gap:
            out.append((start, i + 1))
            start = i + 1
    return out


def ctx(words, a, b, n=6):
    before = " ".join(w["text"] for w in words[max(0, a - n):a])
    removed = " ".join(w["text"] for w in words[a:b])
    after = " ".join(w["text"] for w in words[b:b + n])
    return before, removed, after


def cand(words, a, b, kind, conf, verdict, why):
    before, removed, after = ctx(words, a, b)
    end = words[b]["start"] if b < len(words) else words[b - 1]["end"]
    return {"kind": kind, "start": round(words[a]["start"], 3), "end": round(end, 3),
            "confidence": round(conf, 2), "verdict": verdict, "why": why,
            "removes": removed, "then": after, "context": f"…{before} [{removed}] {after}…",
            "word_range": [a, b]}


def find(words):
    n = [norm(w["text"]) for w in words]
    found = []
    # retakes: sentence-level near duplicates within the next three sentences
    sents = [s for s in sentences(words) if s[1] - s[0] >= 3]
    for x, (a0, a1) in enumerate(sents):
        for (b0, b1) in sents[x + 1:x + 4]:
            r = difflib.SequenceMatcher(None, n[a0:a1], n[b0:b1]).ratio()
            if r >= 0.6:
                verdict = "cut" if r >= 0.8 else "review"
                found.append(cand(words, a0, b0, "retake", r, verdict,
                                  f"sentence repeated {words[b0]['start'] - words[a0]['start']:.1f}s later "
                                  f"(similarity {r:.2f}); keeping the later take"))
                break
    # restarts: two+ words that reappear within 12 words, with the first attempt abandoned
    for j in range(2, len(n) - 1):
        for i in range(max(0, j - 12), j - 1):
            if n[i] and n[i] == n[j] and n[i + 1] == n[j + 1]:
                k = 0
                while j + k < len(n) and i + k < j and n[i + k] == n[j + k]:
                    k += 1
                if i + k == j:
                    continue  # an exact repeat of the whole span is a retake/phrase, handled elsewhere
                if re.search(r"[,;:.!?…]$", words[j - 1]["text"]):
                    continue  # "one for X, one for Y": a list, not an abandoned phrase
                found.append(cand(words, i, j, "restart", 0.7, "review",
                                  f"'{words[i]['text']} {words[i + 1]['text']}' restarted after {j - i} words"))
                break
    # word repeats and fillers
    for i in range(len(n) - 1):
        if n[i] and n[i] == n[i + 1] and words[i + 1]["start"] - words[i]["end"] < 0.6:
            emph = n[i] in EMPHASIS
            found.append(cand(words, i, i + 1, "repeat", 0.4 if emph else 0.85,
                              "keep" if emph else "cut",
                              "likely emphasis" if emph else "stutter / doubled word"))
    for i, t in enumerate(n):
        if t in FILLERS:
            found.append(cand(words, i, i + 1, "filler", 0.6, "review", "filler word"))
    # overlapping proposals: keep the widest
    found.sort(key=lambda c: (c["start"], -(c["end"] - c["start"])))
    out = []
    for c in found:
        if out and c["start"] < out[-1]["end"] - 1e-3:
            continue
        out.append(c)
    return out


def self_test():
    def W(text, t0=0.0, step=0.3):
        return [{"text": t, "start": round(t0 + i * step, 2), "end": round(t0 + i * step + 0.25, 2)}
                for i, t in enumerate(text.split())]
    words = (W("Hello and welcome.", 0) + W("We built the the app in one day.", 1.2)
             + W("All of it connected and ready.", 4) + W("All of it connected and ready.", 6.5)
             + W("It is very very fast.", 9) + W("We made a- we made the whole thing.", 11)
             + W("One for plans, one for tests.", 14))
    c = find(words)
    kinds = {}
    for x in c:
        kinds.setdefault(x["kind"], x)
    assert kinds["retake"]["start"] == 4.0 and kinds["retake"]["end"] == 6.5, kinds["retake"]
    assert kinds["repeat"]["removes"] == "the" and kinds["repeat"]["verdict"] == "cut", c
    very = [x for x in c if x["removes"] == "very"]
    assert very and very[0]["verdict"] == "keep", c
    assert kinds["restart"]["removes"] == "We made a-", kinds["restart"]
    assert not [x for x in c if x["removes"].startswith("One for")], c  # list parallelism is not a restart
    print("find_mistakes.py self-test ok")


def main(argv):
    if "--self-test" in argv:
        return self_test()
    pos = [a for i, a in enumerate(argv) if not a.startswith("--") and (i == 0 or argv[i - 1] != "--out-dir")]
    if not pos:
        sys.exit(__doc__)
    words, _ = edl.load_words(pos[0])
    out_dir = argv[argv.index("--out-dir") + 1] if "--out-dir" in argv else os.path.dirname(os.path.abspath(pos[0]))
    os.makedirs(out_dir, exist_ok=True)
    stem = os.path.join(out_dir, os.path.basename(pos[0]).split(".")[0])
    c = find(words)
    json.dump({"source_transcript": pos[0], "candidates": c}, open(stem + ".mistakes.json", "w"),
              ensure_ascii=False, indent=1)
    md = [f"# Mistake candidates: {os.path.basename(pos[0])}", "",
          "Read every row in context. Emphasis and rhetorical doubling look like stutters.", "",
          "| # | kind | from | to | verdict | conf | removes | then | why |", "|---|---|---|---|---|---|---|---|---|"]
    for i, x in enumerate(c):
        md.append(f"| {i} | {x['kind']} | {x['start']:.2f} | {x['end']:.2f} | {x['verdict']} | {x['confidence']} "
                  f"| {x['removes']} | {x['then']} | {x['why']} |")
    md += ["", "Approved cuts file shape:", "", '```json',
           json.dumps({"cuts": [{"start": x["start"], "end": x["end"], "reason": x["kind"]}
                                for x in c if x["verdict"] == "cut"]}, ensure_ascii=False, indent=1), "```"]
    open(stem + ".mistakes.md", "w").write("\n".join(md) + "\n")
    by = {}
    for x in c:
        by[x["kind"]] = by.get(x["kind"], 0) + 1
    print(json.dumps({"candidates": len(c), "by_kind": by,
                      "default_cut": sum(1 for x in c if x["verdict"] == "cut"),
                      "out": stem + ".mistakes.md"}, ensure_ascii=False))


if __name__ == "__main__":
    main(sys.argv[1:])
