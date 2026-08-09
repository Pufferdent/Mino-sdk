## Context

This change turns the board into "one proper board" — a single mutable object you commit placements to, that reports a classified **event** for each lock and maintains back-to-back continuity. It is the smallest useful slice of L3 game logic: it answers *"what just happened, and is it back-to-back?"* without queue, hold, scoring, or multi-state search.

It builds on `add-move-engine`: a `Placement` already carries the piece position, its `SpinType`, and `lines_cleared`. This change consumes the spin (the board has no move history and cannot derive it) and owns the *event* classification plus the *running* B2B/combo state that a single `Placement` cannot express.

## Goals / Non-Goals

**Goals**
- An `Event` value type with an `EventKind` (PLACEMENT / SPIN / CLEAR); one event per lock.
- A pure classifier `(piece, spin, lines) → (kind, name)`, using `Quad` for 4-line clears.
- `B2BRule` modes S1 and S2 and their difficulty predicate.
- `Board.lock(piece, spin) -> Event` mutating the board and updating running state.
- Back-to-back and combo tracking; perfect-clear detection.

**Non-Goals**
- Scoring / points / attack / garbage (later `add-scoring-attack`; consumes `Event`).
- Queue, hold, randomizer (later `add-queue`).
- Immutable state-trees (later, if a solver needs them).
- Gravity, lock delay, DAS/ARR timing.
- Recomputing spin — spin is an input.

## Decisions

### Events are the output vocabulary

Every lock produces exactly one `Event`. Its `kind` is determined by `(lines, spin)`:

```
lines == 0 and spin == NONE   -> EventKind.PLACEMENT   ("block placement")
lines == 0 and spin != NONE   -> EventKind.SPIN        ("spin-0": a spin that cleared nothing)
lines >= 1                    -> EventKind.CLEAR       (a line clear; may also be a spin)
```

This taxonomy is mutually exclusive and total. `CLEAR` carries the spin in its `spin` field, so a T-spin double is `kind=CLEAR, spin=FULL, lines=2, name="T-Spin Double"`. Making events the output (rather than a clear-only result) means bots, replay logs, and the future scoring layer all consume one uniform type — and spin-0s and placements are first-class, not dropped on the floor.

```python
class EventKind(Enum):
    PLACEMENT; SPIN; CLEAR

@dataclass(frozen=True)
class Event:
    kind: EventKind
    piece: PieceType
    spin: SpinType
    lines: int            # 0..4
    name: str             # derived: "Placement", "T-Spin", "Quad", "T-Spin Double", ...
    difficult: bool       # B2B-eligible under the active rule (CLEAR only)
    back_to_back: bool    # continued an existing chain
    b2b: int              # running chain length after this lock
    combo: int            # running combo after this lock
    perfect_clear: bool   # board fully empty after the lock
```

Frozen/hashable so events can be logged, compared, and used as test fixtures / replay records.

### Naming (quads)

| Input | `name` |
|-------|--------|
| `lines==0, spin==NONE` | `Placement` |
| `lines==0, spin` (spin-0) | `T-Spin` / `T-Spin Mini` / `<Piece>-Spin` |
| `spin==NONE`, lines 1/2/3/4 | `Single` / `Double` / `Triple` / **`Quad`** |
| T, FULL, lines 1/2/3 | `T-Spin Single` / `T-Spin Double` / `T-Spin Triple` |
| T, MINI, lines 1/2 | `T-Spin Mini Single` / `T-Spin Mini Double` |
| non-T, FULL, lines n | `<Piece>-Spin <Lines>` (e.g. `S-Spin Single`) |

4-line clears are **`Quad`**, never the legacy four-line-clear name. The structured fields (`kind`, `spin`, `lines`) are the source of truth; `name` is a derived convenience.

### B2B rule modes (S1 / S2)

Difficulty is **not** a fixed function — it depends on the configured rule:

```python
class B2BRule(Enum):
    S1   # TETR.IO Season 1
    S2   # TETR.IO Season 2

def is_difficult(piece, spin, lines, rule) -> bool:
    if lines == 0:
        return False                      # only line clears can be difficult
    if lines == 4:
        return True                       # a quad is always B2B-eligible
    if rule == B2BRule.S1:
        return piece == PieceType.T and spin != SpinType.NONE   # T-spins-with-lines only
    else:  # S2
        return spin != SpinType.NONE       # any spin-with-lines (all-spin)
```

- **S1**: only quads and T-spins that cleared lines extend B2B; an S-spin single does **not**.
- **S2**: quads and *any* line-clearing spin (T, S, Z, L, J, I) extend B2B.

T-spin **mini** clears are difficult under both rules (they are T-spins that cleared lines). The rule lives on the board (`b2b_rule`), default **`S2`** (current TETR.IO); see open questions.

### Running state lives on the one board

`Board` gains `b2b: int`, `combo: int`, and `b2b_rule: B2BRule`, plus `lock`. This honors "one proper board": the canonical game object is a single mutable `Board`.

**Safe given the move engine:** `reachable()` enumerates over *copies* and never calls `lock()`; it uses `can_place`/`cells` only. The counters never change during search and only advance on a real `lock()`. A fresh `Board()` and `from_fumen` start with `b2b == 0`, `combo == 0` and the default rule.

> Alternative considered: a separate `Game`/`Field` wrapper keeping `Board` a pure value. Deferred — "maintain one proper board" is the stated framing, and the counters can later move to a wrapper without changing `Event`/`classify_lock`.

### `lock` takes the spin; it does not recompute it

```python
def lock(self, piece: Piece, spin: SpinType = SpinType.NONE) -> Event
```

The board has no record of the moves that placed the piece, so it cannot know whether the last action was a rotation, and cannot compute the spin. The spin is supplied, normally from `Placement.spin`. **The move engine classifies spins; the board classifies events.** A convenience overload may accept a `Placement` and forward `placement.spin`.

`lock` sequence: validate (reuse `place`, raise `ValueError` if invalid) → write cells → remove full rows (`lines`) → `kind, name = classify_lock(...)` → update `b2b`/`combo` per the rules below → compute `perfect_clear` → return `Event`.

### Back-to-back and combo update

```
on lock producing (piece, spin, lines):
    if lines == 0:                       # PLACEMENT or SPIN (spin-0)
        combo = 0                        # a non-clearing lock ends a combo
        back_to_back = False             # b2b PRESERVED (chain survives)
        difficult = False
    else:                                # CLEAR
        combo += 1
        difficult = is_difficult(piece, spin, lines, b2b_rule)
        if difficult:
            back_to_back = (b2b > 0)     # True only if a chain was already active
            b2b += 1                     # start (1) or extend
        else:
            b2b = 0                      # a non-difficult clear breaks the chain
            back_to_back = False
```

So `b2b` is the chain length (0 = none, 1 = first difficult clear, 2+ = genuine back-to-back); `Event.back_to_back` is the boolean "this clear continued the chain." A spin-0 or plain placement keeps the chain alive but resets combo — matching guideline/TETR.IO behavior where setup pieces don't reset B2B.

### Module layout

```
mino_sdk/
├── events.py    # NEW: Event, EventKind, B2BRule, classify_lock, is_difficult
├── board.py     # MODIFIED: b2b/combo/b2b_rule attrs, lock(piece, spin) -> Event
├── engine.py    # unchanged (provides SpinType, Placement)
└── __init__.py  # export Event, EventKind, B2BRule
```

`events.py` imports `PieceType`, `SpinType`. `board.py` imports `events`. No circular import.

## Risks / Trade-offs

- **Counters on a value-ish Board.** Adds mutable state to a grid type. → Search uses copies and never locks; counters default inactive and are ignorable; documented escape hatch to a wrapper.
- **Spin must be supplied correctly.** Wrong spin → wrong event. → By design it comes from a verified `Placement.spin`; documented on `lock`.
- **Naming is a convention.** Communities differ. → Structured fields are the source of truth; `name` is remappable.
- **Rule default.** Picking S2 vs S1 as default affects reproducibility. → Default S2 (current TETR.IO) and always explicit on the `Event`'s computed `difficult`; callers pin the rule per experiment.

## Open Questions

- **Default `b2b_rule`** — S2 (current) chosen; confirm. Trivial to change, but it is the reproducibility default.
- **Should spin-0 events feed combo/B2B at all?** Current design: no (0 lines → combo reset, b2b preserved). Matches TETR.IO. Revisit only if a target ruleset differs.
- **Further rules** (e.g. a future "S3", or custom difficulty sets) — `B2BRule` is an enum now; if it needs to become a pluggable predicate (like `RotationSystem`), that's a later, additive change.
- **Combo offset** (0 vs −1 start) — deferred to scoring; raw counter tracked here.
