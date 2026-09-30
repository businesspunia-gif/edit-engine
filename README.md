# edit-engine

A Claude Code skill that turns raw footage into finished videos. The scripts measure and cut, Claude makes the editorial calls, and every render is checked on what it actually shows before it is called done.

| Mode | What it does |
|---|---|
| Long-form edit | Talking-head recording in, pauses and flubs out, graphics that support the speaker |
| Shorts cut | 9:16, tight pacing, hook, cut-out speaker, captions |
| Style from reference | Measures a reel or edit you like (cuts, motion, colours, beats) and turns it into a reusable style skill |
| Promo spot | Beat-cut product or brand video |
| Verification | Black and freeze detection, loudness, frame strips at every join, word-sync drift |

## Install

As a Claude Code plugin:

```
/plugin marketplace add businesspunia-gif/edit-engine
/plugin install edit-engine@edit-engine
```

Or copy the skill folder by hand:

```bash
git clone https://github.com/businesspunia-gif/edit-engine /tmp/edit-engine
cp -r /tmp/edit-engine/skills/edit-engine ~/.claude/skills/
```

## Requirements

- Python 3 (standard library only) and `ffmpeg`
- Local transcription: [whisper.cpp](https://github.com/ggml-org/whisper.cpp) or `openai-whisper`
- Graphics and rendering: the official [HyperFrames](https://github.com/heygen-com/hyperframes) skills (`npx hyperframes skills update`)
- Optional: macOS 14+ for the speaker cut-out (Apple Vision)

Every script prints its usage without arguments and has a `--self-test`.

## Use

Ask Claude, for example: *"cut the pauses and mistakes out of this recording"*, *"turn this into a short"*, *"analyze this reel and build a style from it"*, *"check my render"*. The original file is never touched; work happens in `projects/<slug>/`.

MIT licensed, see `LICENSE`.
