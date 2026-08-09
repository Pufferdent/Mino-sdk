# Design: update-gravity-model

## Context

`research/tetrio-gravity.md` now documents, with sources, the complete TETR.IO
gravity model extracted from the official client bundle and independently
confirmed by the CN community QP2 doc. The sim previously modeled only
constant gravity and the Blitz level ramp. This change retrofits the model;
the implementation landed alongside the research (2026-07-03) and this change
formalizes it against the spec.

## Goals / Non-Goals

**Goals:**
- Client-exact time-ramp semantics: each frame with `frame > gmargin`,
  effective gravity grows by `gincrease/60`; expressed closed-form as
  `g + gincrease·max(0, frame − gmargin)/60`, capped at 20G.
- Correct profiles for `league` and `zenith`; Zenith mod tables available as
  data for future use.
- Replay options as the highest-precedence gravity source.

**Non-Goals:**
- Simulating Zenith altitude/floor progression (needs the climb-speed model;
  the tables and `zenith_floor` are exported for when that lands).
- The Zenith `glock=240` floor-up gravity grace (documented in research; not
  modeled — requires floor tracking).
- Lock-delay reset counting changes; versus garbage.

## Decisions

- **Closed-form ramp on `gravity_at`, not mutable per-frame state.** The
  client mutates `g` each frame; we compute the equivalent value from the
  frame number. Keeps `GravityProfile` frozen/stateless and the engine's
  single `gravity_at(lines, frame)` call site unchanged in shape.
- **Options overlay inside `gravity_for`, via `dataclasses.replace`.** Replays
  that carry `g/gincrease/gmargin/locktime/lockresets` (e.g. Zenith's
  `gincrease=0.0005`) override the registry profile field-by-field; booleans
  are excluded from the numeric check (JS options mix types). Alternative — a
  separate resolver layer — rejected as ceremony for five keys.
- **Floor tables as plain tuples with index-0 padding**, matching the client's
  arrays verbatim so future transcription errors are diffable against the
  bundle.

## Risks / Trade-offs

- [Ramp applied on top of Blitz's level ramp if misconfigured] → Blitz profile
  keeps `gincrease=0`; the ramp only composes when explicitly set.
- [Registry keys guess gamemode strings (`league`, `zenith`)] → validated
  against decoded fixtures for `zenith`; `league` awaits a TL replay fixture
  (options overlay covers drift, since TL replays carry their options in
  multiplayer configs).
