# Sound

Voice first, then sound effects that belong to things happening on screen, then
music underneath. Sound goes on last, after the picture timing is final.

## Voice

- Remove low rumble (high-pass around 80 Hz), even out level (gentle compression),
  and normalize before mixing. The official `hyperframes-audio` skill has the
  filters and the mix recipes.
- Every cut already gets a short fade (8 ms) from the scripts in this skill, so
  joins should not click. If one does, the cut landed inside a word. Move it.

## Sound effects are events

- Plan SFX from a list of visual events, not from the script: `{time, type}` where
  the type is what happens (pop-in, card slide, click, impact, whoosh on a fast
  move, riser into a reveal, success tone). Each type maps to one sound, so the
  same event always sounds the same.
- Align the **audible peak** of the sample with the visual landing (within ~2
  frames). Many samples start with silence, so trim it or offset by it.
- Hierarchy: one strong hit per section at most, lighter sounds for secondary
  events, and nothing on events the viewer does not notice.
- Never put a sound on every word or every cut. Some cuts should be silent.
- A short dip in the music right before a big hit makes the hit land without
  making it louder.

## Music

- Use tracks you own, licensed ones, or generated ones with recorded provenance
  (source, license, date) saved next to the file the moment you add it.
- Under speech, the bed usually sits about 15-20 dB below the voice and ducks
  further while someone talks. If someone says the music is too loud, lower the
  bed relative to the voice and measure the difference. Turning the whole master
  down fixes nothing.
- Never time-stretch music together with a sped-up video. Mix it at its own tempo
  under the final cut.
- Promo cut to music: the music is the clock. See `promo-spot.md`.

## Targets (measure with `verify_render.py`)

| Format | Integrated | True peak |
|---|---|---|
| Talking head / tutorial | about -16 LUFS | ≤ -1 dBTP |
| Short / promo | about -14 LUFS | ≤ -1 dBTP |
