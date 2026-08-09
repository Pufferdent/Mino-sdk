## Why

After the move engine, the SDK can enumerate placements and classify spins, but it cannot yet *advance a game* and report **what happened**. The high-value output for research is not points (scoring is postponed) but a classified **event** per lock: a line clear (`Quad`, `T-Spin Double`, `S-Spin Single`, …), a plain block placement, or a *spin-0* (a spin that cleared no lines) — plus back-to-back continuity.

This change adds **one mutable board** that locks a piece and returns an **`Event`**, where line clears, block placements, and spin-0s are all kinds of event. Back-to-back is configurable between TETR.IO's **S1** and **S2** rules. Queue, hold, scoring, and attack are out of scope.

## What Changes

- Introduce an **`Event`** value type with an **`EventKind`** — `PLACEMENT` (a lock that cleared no lines and was not a spin), `SPIN` (a spin that cleared no lines, "spin-0"), and `CLEAR` (a lock that cleared ≥1 line). Every lock produces exactly one `Event`.
- Introduce **event classification** — pure `(piece, spin, lines) → (kind, name)` mapping. Line-clear names use **`Quad`** for 4 lines (not the legacy four-line-clear name): `Single`/`Double`/`Triple`/`Quad`; `T-Spin [Mini] Single/Double/Triple`; `<Piece>-Spin <Lines>` for non-T spins. Spin-0 names: `T-Spin`/`T-Spin Mini`/`<Piece>-Spin`. Placement: `Placement`.
- Introduce **`B2BRule`** with two modes:
  - **`S1`** (TETR.IO Season 1): a clear is back-to-back-eligible iff it is a **Quad** or a **T-spin that cleared lines**. Non-T spins do *not* count.
  - **`S2`** (TETR.IO Season 2): a clear is eligible iff it is a **Quad** or **any spin that cleared lines** (all-spin).
- Extend the **Board** into "one proper board": add running `b2b` and `combo` state plus a configurable `b2b_rule`, and a `lock(piece, spin=NONE) -> Event` that places the piece, clears lines, updates running state, and returns the classified `Event`.
- Define **back-to-back tracking** (difficulty per `b2b_rule`; chain preserved across non-clearing locks, broken by a non-difficult clear) and **combo** (consecutive line-clearing locks; reset on any non-clearing lock, including spin-0).

## Capabilities

### New Capabilities
- `events`: the `Event` / `EventKind` value types, the pure `(piece, spin, lines) → (kind, name)` classifier (with quads), the `B2BRule` modes (S1/S2) and their difficulty predicate, back-to-back and combo tracking, and perfect-clear detection.

### Modified Capabilities
- `board`: the Board gains running `b2b`/`combo` state, a configurable `b2b_rule`, and a `lock(piece, spin)` method returning an `Event`. Existing `place`, `can_place`, `clear_lines`, and the grid model are unchanged.

## Impact

- **New module**: `mino_sdk/events.py` — `Event`, `EventKind`, `B2BRule`, `classify_lock(piece, spin, lines, rule)`.
- **Modified**: `mino_sdk/board.py` — `b2b`/`combo`/`b2b_rule`; `lock(piece, spin=SpinType.NONE) -> Event`.
- **Depends on**: `add-move-engine` for `SpinType` (the spin is supplied by the caller, typically a move-engine `Placement.spin`; the board does not recompute it).
- **Public API** (`__init__.py`): export `Event`, `EventKind`, `B2BRule`.
- **Tests**: new `tests/test_events.py`; Board lock/B2B tests under both rules.
- **Non-goals (deferred)**: point values, attack/garbage tables, queue, hold, immutable state-trees, gravity/lock-delay timing.
