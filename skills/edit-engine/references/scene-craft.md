# Scene craft

What separates graphics that look produced from graphics that look generated.
It applies to every mode.

## Five ways a video looks cheap

1. **Loose timing.** Graphics arrive after the words, or scenes drift from the
   plan. Timing is the skeleton: plan in absolute seconds from the fresh
   transcript, and verify against the plan.
2. **Naked elements.** A lone rectangle or bare text on an empty background.
   Give content a container that means something: a window with chrome, a phone,
   a terminal, a card with depth, a sheet of paper, a dashboard.
3. **Dead holds.** A frame that looks the same as the frame two seconds later.
   Something should always be moving: a slow push, a counter, a cursor, drifting
   light, secondary motion after the main entrance lands.
4. **Flat art.** One shape, one color, no depth. Build each visual from three or
   more layers: background, subject, detail, light or shadow.
5. **A slow start.** See `shorts-cut.md`. The opening is designed separately.

## Rules that travel

- **Each graphic has a job** (topic, structure, proof, translation, section
  change). No job, no graphic.
- **Show, don't repeat.** Captions carry the words. Graphics should show the
  example, the relationship or the result, not a third copy of the sentence.
- **One thing to look at.** At any moment one element is clearly the brightest,
  largest or moving. Everything else steps back.
- **Things do something.** Prefer an action with a visible result (a checklist
  ticks, a stack assembles, a number counts up to its value, a window opens onto
  the answer) over a title that appears and sits.
- **Vary the mechanism.** If two neighbouring scenes are the same reveal with
  different words, redesign one. Choose transitions for their meaning, not in
  rotation.
- **Callbacks.** An object planted early returns later in a changed or completed
  state. That turns separate cards into one story.
- **Fit the topic.** A terminal topic gets terminal chrome, a design topic a
  canvas, a business topic a dashboard. Reuse the design language between videos,
  not the scenes.
- **Legible at phone size.** Check hero frames at full size and scaled down to
  phone width. Dense UI must be enlarged, cropped to the action or held longer.
- **Real things only.** Official logos and real product captures, with sources
  recorded. A generated likeness is never presented as a real photo of a real person.

## Build discipline

- Plan (`SCENES.md`: time, anchor words, job, visual, motion, exit) before HTML.
- Build and render one scene end to end first, and check it before building the rest.
- Deterministic only: seeded randomness, no wall-clock time. Every timed layer
  must cover its full duration, or it vanishes early (black flash).
- Keep editable sources, the plan and the timing transcript in the project, so any
  later cut change can rebuild captions, graphics and sound from the same map.
