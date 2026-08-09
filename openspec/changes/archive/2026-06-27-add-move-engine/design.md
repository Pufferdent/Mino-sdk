## Context

The move engine is layer **L2** in the SDK architecture: it sits above the core state model (Board, Piece, RotationSystem — already built) and below every research surface (PC solver, bot environment, LST/spin scorer — not yet built). Its job is to turn the static "does this piece *fit* here?" (`Board.can_place`) into the dynamic "can a player *reach* this placement, and is it a spin?"

This change deliberately stays **pure-Python and correctness-first**, matching the project's "Python-first, seam for later" decision. The functions are written against the existing `Board`/`Piece` public API so that a faster bitboard/native backend can later implement the same operations without changing this engine's signatures.

**Reference implementations:** kick application and reachability semantics follow sfinder's `core/action` (the "placeable vs fits" distinction); spin rules follow the modern *immobile / all-spin* convention used by TETR.IO and configurable in Techmino, specialized here to the rules the user specified.

## Goals / Non-Goals

**Goals**
- Kick-aware rotation that applies `RotationSystem.kicks` test offsets in order.
- Soft drop, hard drop, and the four unit translations.
- Immobility test and T-corner test as reusable primitives.
- `SpinType` classification with the exact rules below.
- `reachable(board, piece_type, system)` → all distinct resting placements with spin + input path.
- `Move` enum and `Placement` dataclass as the value vocabulary.
- Two rotation systems shipped: `SRS` (corrected) and `SRSPlus` (true TETR.IO SRS+ — symmetric I 90° kicks + 180 kicks), with `allow_flip` auto-detecting 180 support.
- Correcting and fumen-verifying the kick coordinate convention (first code to apply kicks).

**Non-Goals**
- Hold, queue, 7-bag/RNG (a placement is enumerated for a *single* active piece; hold-aware enumeration is a queue-layer concern).
- Gravity, lock delay, DAS/ARR/SDF timing (this engine is frame-agnostic; it answers "what is reachable", not "in how many frames").
- Scoring, B2B, combo, attack, garbage.
- The PC solver and bot environment (separate later changes that consume `reachable`).
- Rotation systems beyond `SRS` and `SRSPlus` — `SRSX` and `Jstris180` are deferred (the engine is system-agnostic, so they are pure data additions later).

## Decisions

### Value types

```python
class Move(Enum):
    LEFT; RIGHT; SOFT_DROP; CW; CCW; FLIP; HARD_DROP   # HOLD deferred to queue layer

class SpinType(Enum):
    NONE; MINI; FULL

@dataclass(frozen=True)
class Placement:
    type: PieceType
    rotation: int
    row: int
    col: int
    spin: SpinType
    lines_cleared: int          # lines this placement would clear if locked
    path: tuple[Move, ...]      # an input sequence from spawn that reaches it
```

`Placement` is frozen/hashable so enumeration results can go straight into sets/dicts. `path` is *an* input sequence (not necessarily the shortest); consumers that don't need it can ignore it.

### Movement primitives

Each primitive returns a **new** `Piece` (or `None` if blocked); pieces are treated as immutable for engine purposes (`piece.copy(...)`). Collision is `Board.can_place`.

```python
def translate(board, piece, drow, dcol) -> Piece | None     # None if blocked
def soft_drop(board, piece) -> Piece                         # step down until resting
def rotate(board, piece, direction) -> tuple[Piece, bool] | None
        # direction ∈ {CW, CCW, FLIP}; returns (rotated_piece, kick_used) or None
```

**Rotation with kicks.** `rotate` computes the target rotation index, then iterates `system.kicks(type, from_rot, to_rot)` test offsets *in order*; the first offset whose resulting placement satisfies `can_place` wins. `kick_used` is `True` when the winning offset is not `(0, 0)`. If no offset succeeds, the rotation fails (`None`). O-piece kicks are empty, so O only rotates in place (which it always can). FLIP relies on the system providing 180 kicks: plain `SRS` returns `[]` for 180 transitions (so SRS FLIP only succeeds when the in-place 180 fits), while `SRSPlus` defines 180 kicks (so SRS+ FLIP can twist). See the **kick coordinate convention** decision below — this change is the first code to *apply* the kick tables, so it must settle how their tuples are interpreted.

### Spin classification (the core rule of this change)

A `SpinType` is computed for a piece **at its resting position**, given whether the last action that produced that resting state was a rotation.

```
classify(board, piece, last_action_was_rotation) -> SpinType:
    if not last_action_was_rotation:
        return NONE                      # last-move-rotation rule
    if piece.type == T:
        if t_corners_filled(board, piece) >= 3:
            return FULL if immobile(board, piece) else MINI
        return NONE
    else:                                # I, L, J, S, Z, O
        return FULL if immobile(board, piece) else NONE
```

**Immobility test** — a piece is *immobile* iff it cannot move by one cell in any of the four directions:

```
immobile(board, piece):
    return all(board.can_place(translate-by d) is invalid
               for d in [up(+1 row), down(-1 row), left(-1 col), right(+1 col)])
```

(Board convention: row increases upward, so "up" = row+1.)

**T-corner test** — the T's *center* is the single T cell adjacent to the other three (rotation-agnostic; the engine derives it rather than hardcoding per rotation). The four diagonal corners are `(center_row ± 1, center_col ± 1)`. A corner counts as filled if it is **out of bounds OR non-EMPTY**. `t_corners_filled` returns how many of the four are filled; `>= 3` satisfies the T condition.

> This is intentionally the *immobile* spin convention, not the SRS front/back-corner convention. Per the user's rule: T uses 3-corner for MINI and 3-corner + immobile for FULL; every other piece is immobile-only. There is no separate "kick exception" promotion (e.g. TST-twist auto-full); a T is FULL only when it is genuinely immobile. This keeps the rule total and easy to test, and matches all-spin scoring environments.

### Reachability enumeration

```python
def reachable(board, piece_type, system=None, *, allow_flip=None,
              spawn=None) -> list[Placement]
# allow_flip=None -> auto-enable when `system` defines 180 kicks
```

BFS over the state space `(rotation, row, col)`:

- **Start state**: spawn position/rotation (caller may override `spawn`; default is a top-of-board spawn for the piece).
- **Transitions** from each state: LEFT, RIGHT, SOFT_DROP (one cell), CW, CCW, and FLIP when `allow_flip`. Each transition that yields a valid piece enqueues the new state (with the producing `Move` recorded for path reconstruction). A `visited` set on `(rotation, row, col)` prevents revisiting.
- **Emit**: whenever a reached state is **resting** (`translate down` is invalid), it is a candidate placement. The candidate's `SpinType` is computed via `classify(...)` using whether the `Move` that produced this state was a rotation (CW/CCW/FLIP).
- **Dedupe**: candidates are keyed by their resulting **locked cell set** (the absolute filled cells), so two states that lock the same cells are one placement. When duplicates differ in spin, the **highest** classification is kept (FULL > MINI > NONE) — i.e. a placement counts as a spin if *any* reaching path ends in a qualifying rotation. `lines_cleared` is computed from the locked field.

**Why cell-set dedupe rather than (rotation,row,col) dedupe for output:** S/Z/I/T have rotation states that occupy identical cells from different origins; researchers want one placement per physical outcome. (The BFS `visited` set still uses `(rotation,row,col)` to terminate.)

**`allow_flip` defaulting.** Rather than a hard default, `reachable` enables FLIP transitions automatically when the active rotation system defines any 180 kick entry (i.e. `system.kicks(t, 0, 2)` is non-empty for some piece), and disables them otherwise. An explicit `allow_flip: bool | None = None` lets callers force it on/off; `None` (default) means auto-detect. Consequence: SRS enumerations are unaffected (no 180 data), SRS+ enumerations include twists, and researchers don't need to know whether their chosen system supports 180.

### Kick coordinate convention (resolves the load-bearing problem)

This change is the **first code that applies kick tables** — the existing `SRS` kick tuples in `pieces.py` have only ever been *stored*, never used, so their interpretation is latent and untested. The move engine must settle it, and `SRSPlus` must follow the same convention.

**Decision:** kick offset tuples are interpreted as **`(drow, dcol)` in the SDK's native row-up frame**, consistent with `Piece.cells` and every other offset in the codebase. A rotation test adds `(drow, dcol)` to the piece origin and checks `can_place`. There is one offset convention in the SDK; kicks are not special.

**Consequence for the data:** the values currently in `_JLSTZ_KICKS` / `_I_KICKS` were transcribed as canonical SRS `(x, y)` y-up numbers under a `(row, col)` label — so applying them as-is would be wrong. The implementing task MUST validate the *existing* SRS tables against a known fumen (e.g. a TSS/TST setup decoded to a `Board`) and correct the stored tuples to true `(drow, dcol)` if they disagree. This is a correction to data, not to the `RotationSystem` interface.

**`SRSPlus` is defined as a diff from corrected `SRS`, not imported from teto's axes:**

- **JLSTZ 90°** — identical to `SRS` (SRS+ shares these); reuse unchanged.
- **I-piece 90°** — the SRS+ *symmetric* variant: the same magnitudes as SRS I-kicks but mirrored along the column axis (TETR.IO mirrors the left side rather than the right). Derived by reflecting the corrected SRS I table, not by re-transcribing.
- **180 kicks (all pieces)** — new entries for transitions `(0,2),(2,0),(1,3),(3,1)`, expressed in the corrected `(drow, dcol)` frame. Source values (teto engine, verbatim) are recorded in `research/rotation-kick-tables-180.md`; they are translated into the SDK frame and then **pinned by a single round-tripped TST/180 fumen test**, which resolves all axis/sign questions at once.

> Why diff-from-SRS instead of converting teto's `[x,y]` directly: SRS+ and SRS provably share JLSTZ 90° kicks, so any conversion that doesn't reproduce the existing SRS values is wrong by construction. Defining SRS+ relative to a corrected, fumen-verified SRS makes the shared parts exact-by-reuse and isolates the genuinely new data (symmetric I, 180s) to one verifiable test.

### Default spawn table

`reachable` needs a concrete spawn `(rotation, row, col)` per piece type when `spawn` is not supplied. **Decision:** spawn rotation is `0` for all pieces; spawn column places the piece's bounding box left edge at column 3 (guideline spawn: pieces centred over columns 3–6, I over 3–6, O over 4–5); spawn row places the piece just above the visible playfield so its lowest cells sit at the top of the field. Exact origin values are derived from each piece's rotation-0 offsets so that, on an empty board, the spawned piece is in-bounds and immediately soft-droppable. The spawn table lives in `engine.py` as data and is tested on an empty board (every piece type spawns valid and reaches the floor).

### Module layout

```
mino_sdk/
├── engine.py    # NEW: Move, SpinType, Placement, translate, soft_drop,
│                #      rotate, immobile, t_corners_filled, classify_spin, reachable
├── board.py     # unchanged
├── pieces.py    # unchanged
└── __init__.py  # export Move, SpinType, Placement, reachable (+ primitives)
```

`engine.py` imports `Board`, `Piece`, `PieceType`, `RotationSystem`, `SRS` (and `SRSPlus`, see below). No new dependencies. No circular imports (engine depends on board+pieces; neither depends on engine).

`SRSPlus` (true TETR.IO SRS+) is added to `pieces.py` alongside `SRS`, since it is rotation-system *data*, not engine logic. Scope for now is exactly two systems: `SRS` and `SRSPlus`. `SRSX` and `Jstris180` are deferred (data recorded in `research/rotation-kick-tables-180.md`).

## Risks / Trade-offs

- **Performance**: pure-Python BFS over `(rot,row,col)` per piece is fine for analysis but not for high-throughput bot training. → Acceptable now; the function signatures are the seam where a bitboard/native backend later substitutes. Output semantics (the `Placement` set) must stay identical so a fast backend is differentially testable against this reference.
- **Spin convention is opinionated**: the immobile rule diverges from sfinder's SRS-corner T-spin classification and from "kick-based" full-spin promotion. → This is a deliberate, user-specified choice; documented here. If other conventions are needed later, `classify_spin` becomes pluggable (analogous to `RotationSystem`).
- **FLIP under SRS vs SRS+**: plain SRS has no 180 kick data, so FLIP rarely helps under SRS; SRS+ defines 180 kicks. → `allow_flip` auto-detects from the system's 180 data (see decision), so the right thing happens per system without caller knowledge.
- **Latent kick-convention bug**: the existing SRS kick tuples have never been applied and were stored as canonical `(x,y)` numbers under a `(row,col)` label. → This change corrects them to true `(drow, dcol)` and pins SRS *and* SRS+ with a fumen test; if left unaddressed, every rotation against an obstruction would be wrong. This is the highest-risk item.
- **SRS+ data provenance**: SRS+ values came from the teto engine source via web fetch, not a vendored file. → Mitigated by defining SRS+ as a diff from verified SRS (JLSTZ 90° exact-by-reuse, I 90° by reflection) and a TST/180 fumen test; only the genuinely new offsets are trusted, and they're checked.
- **Spawn definition**: an incorrect spawn makes some placements unreachable (a piece spawning into a filled board can't move). → Default spawn table defined in the decisions; `spawn` is overridable; tested on an empty board for every piece type.
- **Path is non-canonical**: `path` is *a* reaching sequence, not minimal or unique. → Documented; consumers needing optimal input sequences compute them separately.

## Open Questions

- Should `reachable` optionally include **hold** (try both current and held piece)? Deferred — belongs to the queue layer, which can call `reachable` twice and merge.
- Should soft-drop transitions allow **multi-cell** drops as a single move for speed? Deferred — single-cell keeps the BFS simple and correct; an optimization, not a semantic change.
- Do we need a **spin-immobile promotion exception** for known TST/STSD shapes? Not under the stated rule (immobile already captures these); revisit only if a target environment scores them differently.
