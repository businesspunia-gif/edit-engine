# Verification loop

"Done" means the encoded file was measured and looked at. Code that should work,
a clean lint and an existing file are not evidence.

## Loop

1. **Before rendering:** `npx hyperframes lint`, then look at the Studio preview
   (or `npx hyperframes snapshot --at <times>`) at every scene midpoint and just
   before and after every transition.
2. **Draft render**, low quality, then measure:
   ```sh
   python3 $S/verify_render.py draft.mp4 qa/draft --edl final.edl.json \
     --at <scene starts, transitions> --words final.words.json --lang <code> --expect-duration <s>
   ```
3. **Look at every strip** (`qa/draft/strip_*.jpg`, 10 consecutive frames). Look
   for a black or white flash, a one-frame pop, a layer that stays when it should
   have left (ghost), a frozen frame, a face or mouth covered by text, text outside
   the safe area, or a visible jump cut that should have been hidden.
4. **Listen** at every join and at the first and last second. Check for a clipped
   consonant, a click, a breath cut in half, or music drowning the voice. If you
   cannot listen (no audio review available), say so in `VERIFY.md`. A waveform is
   not listening.
5. **Fix, then re-check what the fix touched** plus its neighbours. One round of
   fixes is normal. If a second round finds structural problems (missing beats,
   desync), fix the plan, not just the frames.
6. **Final render**, then run `verify_render.py` again on the final file. Numbers
   from the draft do not carry over.

## Reading the numbers

| Measure | Pass | Act when |
|---|---|---|
| duration vs expected | within one frame | off by more: stale file, missing tail, wrong cut list |
| black ≥ 0.1 s | none, or intended fades only | any unplanned interval, usually a clip whose timeline ends early |
| frozen ≥ 1.5 s | only intended holds (end card) | a freeze under moving speech means a stalled video layer |
| loudness | talking head about -16 LUFS, promo about -14 LUFS, true peak ≤ -1 dBTP | peak above 0 dBTP: limit it. Re-encoding AAC can push peaks up, so measure after the final encode |
| word sync | median within ±50 ms, p95 under ~150 ms | large drift at the start or at one spot: the first transcript was wrong there, so retime graphics to `fresh.words.json`. Drift growing over time: wrong fps or speed |
| beat offsets (promo) | hard cuts within ~35 ms of beat or half beat | re-derive times from the grid, not by hand |

## `VERIFY.md`

```
# VERIFY: <project>, <date>
Final: <absolute path>, <duration>, <sha256>
Measured: (paste qa/final/verify.md)
Looked at: <which strips / frames, what was found, what was fixed>
Listened to: <which joins / whole video / nothing, and why>
Not checked: <honest list>
Open issues: <anything the user should decide>
```

Get the hash with `shasum -a 256 final.mp4`. A report without "Not checked" is
not finished.
