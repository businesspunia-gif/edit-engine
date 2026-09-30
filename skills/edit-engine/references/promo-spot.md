# Promo spot (8-60 s: product, launch, brand, community hype)

A promo is a sequence of small, precise decisions set to music. The music grid
comes first, and the pictures are designed onto it.

If there is no footage and the user just wants a launch video from a URL or brief,
the official `product-launch-video` workflow (via `/hyperframes`) is the faster
route. Use this reference when the promo mixes real recordings or screen captures,
follows a measured reference style, or must be cut tightly to a specific track.

## 1. Brief (`BRIEF.md`)

- purpose, audience, length, aspect ratio(s), where it plays
- the one thing a viewer should remember
- real assets: logo files from the owner or the official press kit (record source +
  checksum), screen recordings of the real product, photos the user has rights to
- 3-5 facts worth putting on screen, each with its source and date
- style: an existing `STYLE.md` / style skill, or a short direction

## 2. Music and grid

Use a track the user owns or has licensed, or generate one if they approve the cost.
```sh
python3 $S/beat_grid.py music.mp3 --beats --fps 30 --length 20 \
  --chapters "Open:4, Problem:8, Product:8, Proof:8, Flurry:4, End:rest"
```
Use the kick phase. If the chapter table does not fit the track's own build and
drop, move the chapter lengths, not the music. Re-run `beat_grid.py` on the final
edited music bed: its phase should be within ~25 ms of your plan.

## 3. Structure

Write `STORYBOARD.md`: one row per chapter with beats, start frame, the object on
screen, how it enters, how it leaves, light/dark value, sound cue.

Patterns that hold up:
- **A recurring object.** One simple element from the brand (a dot, an icon, a
  shape from the logo) opens the piece, changes form through the sections and
  closes it inside the logo lockup.
- **Transform, don't just cut.** Inside the development part, the outgoing object
  becomes the incoming one. Save hard cuts for the fast climax.
- **Flip value per section.** Dark → light → saturated keeps the eye awake. Hold one
  accent color back for the climax.
- **Accelerate, then hold.** About three quarters development, a short burst of
  one-beat and half-beat cuts, then a calm lockup of 2+ seconds.
- **Show real product.** Actual UI in motion (scrolling, clicking, a result
  appearing) beats a generic mock-up. Never fake a result.
- **Density changes.** Alternate one object on an empty frame with a full frame.

## 4. Build

HyperFrames, one paused timeline, all times derived from the grid
(`beat(n) = phase + n * 60 / bpm`). Everything seek-safe: any value that changes
every frame (particles, noise, counters, HUD timecode) is computed from the
timeline time with seeded randomness, never `Math.random()` at draw time. Animate
transforms and opacity. Build one chapter end to end, render it, check it, then
build the rest against it. For composition rules, follow `hyperframes-core`.

## 5. Sound and verify

Mix per `sound.md` (promo: about -14 LUFS, -1 dBTP). Then run the verification loop
and add two promo-specific checks:
- `analyze_reference.py render.mp4 qa/ref --bpm <bpm> --phase <phase>`: every hard
  cut within ~35 ms of a beat or half beat
- brand check: pick 6 random frames and cover the logo. Each should still read as
  this brand through its colors, objects or type.
