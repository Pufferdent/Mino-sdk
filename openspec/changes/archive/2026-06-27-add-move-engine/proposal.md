## Why

The SDK has a Board, Pieces, a pluggable RotationSystem (with SRS kick *data*), and fumen import — but no way to *move* a piece. The kick tables are present, yet nothing applies them; there is no soft/hard drop, no reachability, and no spin detection. Every downstream research goal — PC discovery, bot action spaces, LST/spin-stacking simulation — depends on one keystone capability: **given a board and a piece type, enumerate every placement a player could actually reach, and classify any spin.**

This change builds that keystone: the **move engine** (architecture layer L2). It is the single highest-leverage capability in the SDK, and it is shared by all three research personas.

## What Changes

- Introduce **movement primitives**: translate left/right/up/down with collision checks against the Board.
- Introduce **kick-aware rotation**: apply the active RotationSystem's kick tests in order, first valid wins, reporting whether a kick was used.
- Introduce **drop**: soft drop (step down to rest) and hard drop (rest position).
- Introduce **immobility** and **T-corner** tests as primitives.
- Introduce **spin classification** (`SpinType`): NONE / MINI / FULL, using the rules below.
- Introduce **reachability enumeration**: BFS over reachable states returning every distinct resting `Placement`, each annotated with its spin type and the input path that reaches it. `FLIP`/180 transitions auto-enable when the active rotation system defines 180 kicks.
- Introduce supporting value types: `Move` enum and a `Placement` dataclass.
- **Correct and fumen-verify the kick coordinate convention.** This is the first code to *apply* the `SRS` kick tables (until now they were only stored). The tuples must be interpreted as `(drow, dcol)` in the SDK's native row-up frame; the existing values were transcribed as `(x, y)` y-up under a `(row, col)` label and are corrected and pinned with a fumen test.
- **Add `SRSPlus`** (true TETR.IO SRS+): the symmetric I-piece 90° kicks plus the SRS+ 180 kick table, defined as a diff from corrected `SRS` (JLSTZ 90° reused exactly; I 90° by reflection; 180s new). Scope is exactly two rotation systems — `SRS` and `SRSPlus`; `SRSX`/`Jstris180` are deferred.

### Spin classification rules

- **T piece**: 3 of the 4 diagonal corners around the T's center filled (or out of bounds) ⇒ at least **MINI**. If additionally **immobile** ⇒ **FULL** (proper T-spin).
- **All other pieces** (I, L, J, S, Z, O): **immobile** ⇒ **FULL** spin; otherwise NONE. (No corner rule for non-T pieces.)
- A spin is only recognized when the **last successful action before locking was a rotation** (the standard last-move-rotation rule). A piece reaching its rest position by translation/drop alone is NONE regardless of corners or immobility.

## Capabilities

### New Capabilities
- `move-engine`: Movement primitives, kick-aware rotation, soft/hard drop, immobility and T-corner tests, spin classification (NONE/MINI/FULL), and reachable-placement enumeration over a Board for a given piece type and rotation system.

### Modified Capabilities
- `piece-system`: the SRS kick tables are corrected to the `(drow, dcol)` row-up convention (they are now actually applied), and a new `SRSPlus` rotation system is added (symmetric I 90° kicks + 180 kicks). Board and fumen-parser specs are unchanged.

## Impact

- **New module**: `tetris_sdk/engine.py` — `Move`, `SpinType`, `Placement`, movement/rotation/drop functions, immobility & corner tests, spin classification, `reachable(...)`.
- **Modified**: `tetris_sdk/pieces.py` — correct `SRS` kick tuples to `(drow, dcol)`; add `SRSPlus` (true TETR.IO SRS+).
- **Reuses unchanged**: `Board.can_place`, `Piece.cells`, the `RotationSystem` interface.
- **Public API** (`__init__.py`): export `Move`, `SpinType`, `Placement`, `SRSPlus`, and the engine entry points.
- **Tests**: new `tests/test_engine.py`; kick-convention + SRS+ fumen tests.
- **Data source**: SRS+ values recorded verbatim in `research/rotation-kick-tables-180.md` (from the `@haelp/teto` engine); applied as a diff from verified SRS.
- **Non-goals (deferred)**: 7-bag/RNG, hold, queue, gravity/lock-delay/DAS-ARR timing, scoring/B2B/combo, garbage, and the PC solver — all build *on top of* this engine in later changes.
