---
name: edit-engine
description: Edit real footage into finished videos with Claude Code, ffmpeg and HyperFrames. Five modes - long-form talking-head edit (remove pauses and flubs, add graphics that support the speaker), short-form cut (9:16, tight pacing, hook, cut-out speaker, captions), style-from-reference (measure a motion reel or edit you like and turn it into a reusable style skill), promo spot (beat-cut product or brand video), and a verification loop that proves a render is right before it is called done. Use when someone says "edit my video", "cut the pauses", "remove the mistakes / retakes / stutters", "turn this into a short / reel", "make it look like this reference", "analyze this reel", "build a style from this video", "promo video", "sizzle reel", "check my render". Scripts are Python 3 standard library plus ffmpeg; transcription runs locally with Whisper.
---

# edit-engine

Raw recording or reference in, verified MP4 out. The scripts do the measuring and
the mechanical cutting. You make the editorial calls, and the render is judged on
what it actually shows, not on what the code intended.

`S=<this skill>/scripts`. Every script prints its usage with no arguments and has
a `--self-test`.

## 1. Pick the mode

| The user has... | Mode | Read |
|---|---|---|
| A long talking-head recording (YouTube, course, webinar) | Long-form edit | `references/longform-edit.md` |
| A vertical recording, or wants a Short/Reel/TikTok | Shorts cut | `references/shorts-cut.md` |
| A video they like and want to reuse the look of | Style from reference | `references/style-from-reference.md` |
| A product, launch, brand or community hype video to make | Promo spot | `references/promo-spot.md` |
| A finished render to check | Verification only | `references/verification.md` |

Every mode ends in the verification loop. Graphics work in every mode follows
`references/scene-craft.md`, and all audio decisions follow `references/sound.md`.

If a request is only "make a video from this URL / text / music" with no footage,
hand over to the official `/hyperframes` entry skill; it routes to its own
product-launch, music-to-video and general workflows. This skill adds what those
do not do: cutting real recordings, and turning a reference into numbers and a style.

## 2. Ground rules (all modes)

1. **Never touch the original.** Work in `projects/<slug>/`, reference the source
   by path or copy it into `assets/`. Every output gets a new file name.
2. **One timeline at a time.** Each cutting stage reads a transcript that matches
   its input and writes a retimed transcript that matches its output. Time
   graphics only against the transcript of the video they sit on. After the final
   cut, the fresh transcript of the finished audio (`verify_render.py --words`) wins.
3. **Render once from the source.** Stack edits as EDLs and encode the final cut
   from the original recording (`apply_cuts.py --base-edl`). Re-encoding cut files
   again and again loses quality and makes timing drift.
4. **Cut the words last and by judgment.** Pause removal is mechanical. Mistake
   removal is a proposal that someone approves. Emphasis, lists and rhetorical
   repeats look like mistakes to a detector.
5. **Local first.** Whisper runs locally by default. Cloud transcription, voice or
   generation services (ElevenLabs, kie.ai and the like) are optional. Name the
   cost and what gets uploaded, and get a yes before the first paid call.
6. **Evidence before "done".** Nothing is finished until `verify_render.py` has
   run on the encoded file, the strips have been looked at, and `VERIFY.md` says
   what was checked and what could not be.
7. **Real marks only.** Use logos and product visuals from the owner or official
   sources, never a redrawn look-alike. Never present generated footage as proof
   of a real result.

## 3. The pipeline at a glance

```
recording ─ transcribe.py ─ cut_pauses.py ─ find_mistakes.py ─(approve)─ apply_cuts.py ─┐
                                                     review_page.py  ◄───────────────────┤
reference ─ analyze_reference.py ─ beat_grid.py ─ STYLE.md ─ style skill                 │
                                                                                         ▼
                           plan (SCENES.md) ─ HyperFrames build ─ render ─ verify_render.py ─ VERIFY.md
speaker cut-out (macOS): make_cutout.sh ──────────┘
```

| Script | Does |
|---|---|
| `transcribe.py` | Local word-level transcript (whisper.cpp or openai-whisper), or `--normalize` any provider's JSON into one shape |
| `cut_pauses.py` | Finds silence on the audio, keeps a natural breath (longer after a sentence), writes EDL + retimed words, `--render` |
| `find_mistakes.py` | Proposes retakes, restarts, doubled words, fillers with context and a default verdict |
| `apply_cuts.py` | Applies approved cuts, merges them with the pause EDL, renders the final cut once from the source |
| `review_page.py` | HTML page: every cut on a timeline, one click plays the removed audio in context |
| `analyze_reference.py` | Shot list, cut rhythm, brightness and motion curves, dominant colors, audio onsets, contact sheets |
| `beat_grid.py` | Tempo and kick phase from music (or from a reference's cuts), frame-exact beat and chapter sheet |
| `make_cutout.sh` | Speaker cut-out with alpha (Apple Vision, macOS 14+) for layouts where the person breaks out of a frame |
| `verify_render.py` | Black/freeze detection, loudness, frame strips at every join, word-sync drift against a fresh transcript |

## 4. Working with HyperFrames

Graphics, captions, overlays and whole compositions are HyperFrames projects.
Load `/hyperframes` (entry) and `hyperframes-core` (the composition contract) before
writing composition HTML. Related official skills: `talking-head-recut` for dressing
a recording with timed cards, `embedded-captions` for caption styling, and
`hyperframes-audio` for mixing. This skill supplies the cut, the timing source, the
style numbers and the verification. Those skills supply the rendering rules.
Where they state a rule about composition structure, theirs wins.

## 5. Delivery

Give the user the absolute path of the final MP4, plus `VERIFY.md` and the edit
decisions (EDL + approved cuts) in the project folder. Also say plainly what was
not checked, for example "listened only to the joins, not the full video". Label
drafts as drafts. Publishing or posting is a separate step that needs the user's
explicit go.
