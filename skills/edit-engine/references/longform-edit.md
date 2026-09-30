# Long-form talking-head edit

Goal: a tight, watchable version of a long recording that still sounds like the
speaker, with graphics that carry structure the voice alone cannot.

## Steps

1. **Probe and set up.** `ffprobe` the file (duration, resolution, fps, audio).
   Create `projects/<slug>/`, note the source path in `projects/<slug>/NOTES.md`.
2. **Transcribe.** `python3 $S/transcribe.py raw.mov projects/<slug>/raw.words.json --lang <code>`.
   Check the words-per-second figure: ~2-3 is normal speech. Far lower usually means
   long silences, music, or a wrong language setting.
3. **Remove dead air.**
   `python3 $S/cut_pauses.py raw.mov raw.words.json --out-dir projects/<slug> --preset long --render`
   Read `raw.pauses.md`. The long preset removes 5-15 % of a normal take. More than
   ~25 % means the threshold is catching quiet speech, so raise `--min-pause` or pass
   `--threshold` a few dB lower. Words listed as clamped are ones the transcriber
   placed inside a cut. Listen to those joins.
4. **Find mistakes.** `python3 $S/find_mistakes.py raw.pauses.words.json --out-dir projects/<slug>`.
   Read every row of `raw.mistakes.md` in context:
   - *retake*: keep the last complete take unless an earlier one is clearly better
     delivered. Widen the cut to include the lead-in breath of the bad take.
   - *restart*: usually cut, unless the restart is a deliberate self-correction the
     audience should hear.
   - *repeat*: cut stutters and keep emphasis ("very, very").
   - *filler*: cut only where it breaks rhythm. Removing every "um" makes speech robotic.
   Also skim the full transcript yourself. The detector misses retakes that were
   reworded, and zero candidates does not mean zero mistakes.
   Present the list with a recommendation per row and get approval (or follow a
   standing instruction to decide yourself). Write `approved.json`.
5. **Apply and render once.**
   `python3 $S/apply_cuts.py raw.pauses.words.json --cuts approved.json --base-edl raw.pauses.edl.json --out-dir projects/<slug> --render`
6. **Audition.** `python3 $S/review_page.py raw.final.edl.json --original raw.mov --edited raw.final.mp4`,
   open it and listen to the biggest cuts and every mistake cut.
7. **Fresh transcript.** `python3 $S/verify_render.py raw.final.mp4 qa --edl raw.final.edl.json --words raw.final.words.json`
   gives `qa/fresh.words.json`, the timing source for everything visual.
8. **Graphics plan, then build, then verify.** See below, `scene-craft.md` and `verification.md`.

## Hiding jump cuts

A pause or mistake cut inside one continuous camera angle jumps the head. Hide the
cuts that matter, in this order of preference:
- a **punch-in**: scale the speaker 1.0 → 1.12 (or back) exactly on the join,
  alternating so the frame does not creep in forever
- a **graphic that starts on the join** (lower third, full-screen card)
- a **B-roll insert** spanning the join
Small jumps at sentence boundaries can stay. Viewers of talking-head content accept them.

## Graphics plan (write `SCENES.md` before any HTML)

One row per beat: spoken anchor (exact words), time from the fresh transcript, the
job of the graphic, type, duration.

The job must be one of these: name the topic, give structure (steps, list,
comparison), show a number or proof, translate a term, or mark a section change.
If none applies, the beat gets no graphic.

| Type | When | Rules |
|---|---|---|
| Overlay card (speaker stays visible) | explanations, labels, short lists, definitions | stays clear of the face and mouth, sits in the lower or side third, 3-8 s |
| Full-screen card | section markers, a key number, a thesis line, a quote | short (2-6 s), sparse text, returns to the speaker on a clean join |
| B-roll / screen recording | when showing is faster than telling | real footage of the actual thing, long enough to read the action |

Pacing check: in a talking-head video, stretches longer than ~20-30 s with no
visual change are where viewers drift. Look at those first. Do not fill them
with decoration.

Timing: a graphic lands on or up to 0.15 s before its anchor word, never after.
`verify_render.py --words` measures whether the cut audio still matches.
