# Shorts cut (9:16, 20-90 s)

A short lives or dies in its opening. The rest of the cut exists to deliver what
the opening promised, faster than the viewer expects.

## Steps

1. **Probe.** A vertical source (1080x1920) is ideal. A horizontal one needs a
   deliberate reframe per scene, not one centre crop for the whole video.
2. **Transcribe**, then **cut pauses with the short preset**:
   `python3 $S/cut_pauses.py in.mp4 in.words.json --out-dir P --preset short`
   (0.25 s minimum pause, 0.08-0.14 s breath). Expect 10-20 % removed.
3. **Mistakes and double takes.** Creators record a line several times, so shorts
   are full of retakes. Run `find_mistakes.py`, then read the whole transcript
   anyway: a take abandoned after two words, or a reworded retake, often escapes
   the detector. Keep the best-delivered take, which is usually the last.
   Some creators mark bad takes with a sound (a clap, a click). The transcriber
   does not see those. If the user has such a convention, find the marks by ear or
   in the waveform and add them to `approved.json` by hand.
4. **Apply once from the source** (`apply_cuts.py --base-edl`). If the user wants
   a speed-up (1.1-1.2x is common), apply it once as the very last video step,
   before transcribing for graphics. Never speed up an already sped-up file. Ask
   when unsure, because the speed cannot be read reliably from the file.
5. **Fresh transcript of the final audio.** It drives captions and every scene time.
6. **Plan, build, verify.** Plan in `SCENES.md` with absolute seconds, build in
   HyperFrames, then run the verification loop. Put SFX and music on last, once
   the picture timing is final.

## The opening (first 3 seconds)

- **Sentence one is short.** One claim, spoken in 2.5 s or less. If the script's
  first sentence is longer, trim it before recording or cut it tighter. Rewording
  it after the fact is a different video.
- **Say who it is for or what it is about by sentence two.**
- **Frame one already moves.** At least three layers in motion at t=0 (the speaker,
  a graphic, a background or text element). A static face on frame one loses people.
- **First hard cut by 3.0 s.**
- **Hook text is keywords, not a caption.** 2-4 words that name the payoff, not a
  transcript of the sentence.
- **The opening must still work with the sound off.** Check it muted.
- Make two or three different openings from the same speech when the stakes are
  high, compare them muted, and keep the one that makes the payoff most concrete.
  Never promise something the rest of the video does not deliver.

## Layouts

| Layout | What it looks like | Use |
|---|---|---|
| Visual | graphics or B-roll full frame, speaker hidden, voice continues | most of the runtime in graphics-heavy topics |
| Card | graphic on top, speaker in a rounded card in the lower part of the frame, head and shoulders breaking out over the card's top edge | hook and 2-3 key moments. It keeps the human in the video without giving up the frame |
| Face | speaker full frame, bold caption | one punchline or conviction beat, eyes on the lens |
| Split | 50/50 speaker and visual | comparisons, reactions |

Card layout recipe: the raw footage (including the room) plays inside the card, and
the cut-out from `make_cutout.sh` plays on top, aligned to the same pixels, with the
card's top edge as the line where the head leaves the card. Both videos come from
the same final cut, so they stay frame-locked. Make the cut-out once, after the cut
is final.

Budget speaker-on-screen time deliberately (for example ~10-15 s of a 60 s short)
rather than letting it happen by default. Switch layouts on hard cuts, roughly one
visual change per second overall, with small punch-ins on held shots.

## Captions

- Safe area for 1080x1920: keep text inside x 90-930, y 200-1600. The right edge and
  bottom are covered by platform UI.
- 1-4 words per group, timed to the fresh transcript, active word highlighted.
- Never cover the mouth. Move captions per layout.
- Use at most two caption styles per video (for example one on visuals, one on face shots).

## Script notes (if you write the script too)

Write for the mouth, not the page. Use short main clauses, no stacked appositions,
and numbers the way people say them ("about two hundred sixty thousand", not
"267,431"). Each claim gets its reason in the same breath. End walkthroughs on
the result, not a feature. Never invent a personal anecdote for the speaker. Ask
what they actually did.
