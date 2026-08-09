# Proposal: update-gravity-model

## Why

TETR.IO's per-mode gravity was fully pinned from the official client bundle
(`tetr.io/js/tetrio.js`; see `research/tetrio-gravity.md`): 40L is a confirmed
constant 0.02G, Tetra League and Quick Play (Zenith) use a time ramp
(`g += gincrease/60` per frame past `gmargin`), Zenith's per-floor tables
belong to the gravity/freefall mods only, and replays may carry the gravity
drivers in their own options. The sim's gravity model predated these findings —
no time ramp, no league/zenith profiles, no floor tables — leaving non-sprint
TETR.IO replays simulated under a wrong (flat default) gravity.

## What Changes

- `GravityProfile` gains the client-exact time ramp: `gincrease` (G per
  second) and `gmargin` (frames), applied on top of constant or level-ramp
  gravity; `gravity_at` becomes frame-aware and the frame engine passes the
  current frame.
- New registry profiles: TETR.IO `league` (`0.02 + 0.0035/s` after 7200f) and
  `zenith` (`0.02 + 0.0005/s`, no margin).
- Zenith floor data exported: `ZENITH_FLOOR_DISTANCE` (floor ← altitude),
  `ZENITH_GRAVITY_BUMPS` / `ZENITH_G_LOCK_DELAY` (gravity mod),
  `ZENITH_GR_LOCK_DELAY` (freefall mod), and `zenith_floor(altitude)`
  mirroring the client's `GetFloorLevel`.
- `gravity_for` overlays gravity drivers present in a replay's own options
  (`g`, `gincrease`, `gmargin`, `locktime`, `lockresets`) over the resolved
  profile — the client's own precedence.
- 40L documentation corrected from "low constant heuristic" to confirmed
  official value.

## Capabilities

### New Capabilities

_None._

### Modified Capabilities

- `sim-gravity`: profile grows time-ramp fields and frame-aware gravity;
  registry gains league/zenith profiles and Zenith floor/mod data; lookup
  gains replay-options overlay.

## Impact

- `tetris_sdk/sim/gravity.py` (model, registry, lookup), `tetris_sdk/sim/engine.py`
  (frame-aware gravity call), `tetris_sdk/sim/__init__.py` (exports),
  `tests/test_sim_gravity.py`.
- Behavior change: TETR.IO league/zenith replays (and any replay carrying
  gravity options) now simulate under correct ramping gravity instead of the
  flat default. All 235 tests pass, including replay-simulate oracles.
