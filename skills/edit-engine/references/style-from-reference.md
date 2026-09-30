# Style from a reference video

Turn "make it look like this" into numbers, then into a small skill that can make
new videos in that style without the reference.

Only study references you are allowed to watch and learn from. Take the
**mechanisms** (rhythm, structure, type roles, transitions, color logic), never the
copy, logos, footage or characters.

## 1. Measure

```sh
python3 $S/analyze_reference.py ref.mp4 projects/<slug>/ref --sheet-fps 4
```

Outputs: `report.md` (shot list with start, length, brightness, motion, 3 dominant
colors; cut-rhythm stats; brightness and motion every 0.5 s; audio onsets),
`shots.jpg` (one frame per shot) and `sheet_NN.jpg` (contact sheets).

Then look at them, all of them. The numbers tell you where to look, and your eyes
tell you what happens there:
- `shots.jpg` first: is each tile a real shot, or a flash, or one step of a
  continuous transform? The detector counts flashes as cuts and cannot see
  transforms, match cuts or dissolves.
- For each transition that matters, pull 10 contiguous frames:
  `python3 $S/verify_render.py ref.mp4 projects/<slug>/ref/strips --at 4.17,9.89,13.65`
- A screen recording of a reference adds its own junk: black lead-in, browser
  frames at the end, dropped frames. Note the usable window and ignore the rest.

## 2. Find the grid

With audio:
`python3 $S/beat_grid.py ref.mp4 --beats` gives tempo, kick phase and energy per beat.
The drop is where low-band energy jumps ~10 dB, and a short dip just before it
is a pre-drop gap.

Without audio (screen recordings often have none):
`python3 $S/beat_grid.py --from-cuts projects/<slug>/ref/report.json --window A-B`
fits a tempo to the cut times inside the edited window. Trust it only if the fit
is ≥ 0.5 and most cuts land on the grid. It cannot tell double tempo from single,
so sanity-check against how fast the edit feels.

With a grid, re-run the analysis to get each cut's offset from the beat:
`analyze_reference.py ref.mp4 out --bpm 127.2 --phase 0.21`.

## 3. Write `STYLE.md`

Separate what you **measured** from what you **infer**. Sections:

| Section | Content |
|---|---|
| Format | resolution, fps, length, audio yes/no |
| Rhythm | shots, cuts/s, median and shortest shot, where it accelerates, where it holds; tempo and how tightly cuts sit on it |
| Structure | timeline table: time, chapter/section name, what happens, how it exits into the next |
| Value and color | brightness curve (does it flip dark/light per section?), palette with hex from `report.md` checked against frames, the role of each color, any color held back for the climax |
| Type | roles (display, accent, technical/mono), case, tracking, how type moves |
| Motion | typical eases, entrances, transforms vs hard cuts, secondary motion, texture (grain, blur, glow) |
| Persistent layers | HUD, frames, progress bars, watermarks |
| Sound | tempo, where hits land, silence before the big moment |
| Why it works | 3-6 inferred principles, each tied to a timestamp |
| Do not copy | brand names, logos, slogans, specific characters or footage |

## 4. Turn it into a style skill

Create a folder `<style-name>/` with:
- `SKILL.md`: when to use the style, the rules as a checklist, and a build order
  (grid first, then structure, then one section built and rendered end to end,
  then the rest)
- `STYLE.md` from step 3
- `tokens.css`: colors, fonts, easing curves, spacing as CSS variables
- optionally one proven HyperFrames composition as a starting point

Test the style skill by making something new with it on a different subject.
Compare the new render to the reference with `analyze_reference.py` on both, the
same way: cut rhythm, brightness curve, beat offsets. If the numbers and a
side-by-side of `shots.jpg` do not match, the style skill is missing a rule.
