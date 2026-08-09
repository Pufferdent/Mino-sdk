## 1. Value types

- [x] 1.1 Create `tetris_sdk/engine.py` with a `Move(Enum)` — `LEFT, RIGHT, SOFT_DROP, CW, CCW, FLIP, HARD_DROP` — and a helper identifying `CW/CCW/FLIP` as rotation moves
- [x] 1.2 Add `SpinType(Enum)` — `NONE, MINI, FULL` — with a defined rank ordering (FULL > MINI > NONE)
- [x] 1.3 Add a frozen, hashable `Placement` dataclass: `type, rotation, row, col, spin, lines_cleared, path: tuple[Move, ...]`

## 2. Kick convention correction & rotation systems (pieces.py)

- [x] 2.1 Establish the kick convention: tuples are `(drow, dcol)` in the row-up frame, first test `(0, 0)`; document on `RotationSystem.kicks`
- [x] 2.2 Audit and correct the stored `_JLSTZ_KICKS` and `_I_KICKS` in `pieces.py` to true `(drow, dcol)` (they were transcribed as `(x, y)` y-up); confirm against a decoded T-spin fumen
- [x] 2.3 Implement `SRSPlus(RotationSystem)` sharing `SRS` rotation shapes; JLSTZ 90° reused from corrected `SRS`; I-piece 90° as the SRS+ symmetric variant (reflect SRS I kicks along the column axis)
- [x] 2.4 Add SRS+ 180 kick tables for transitions `(0,2),(2,0),(1,3),(3,1)` for JLSTZ/T and I (O empty), translated into `(drow, dcol)` from `research/rotation-kick-tables-180.md`
- [x] 2.5 Export `SRSPlus` from `tetris_sdk/__init__.py`

## 3. Movement primitives

- [x] 3.1 Implement `translate(board, piece, drow, dcol) -> Piece | None` — returns a moved `piece.copy(...)` if `can_place`, else `None`; original unchanged
- [x] 3.2 Implement `soft_drop(board, piece) -> Piece` — repeatedly translate down by 1 until blocked; return the resting piece
- [x] 3.3 Implement `rotate(board, piece, direction) -> tuple[Piece, bool] | None` — compute target rotation, try `system.kicks(type, from, to)` `(drow, dcol)` offsets in order, first valid wins; return `(rotated_piece, kick_used)` or `None`. FLIP uses the 180 transition kicks

## 4. Spin primitives

- [x] 4.1 Implement `immobile(board, piece) -> bool` — true iff all four unit translations (up/down/left/right) are blocked or out of bounds
- [x] 4.2 Implement `t_corners_filled(board, piece) -> int` — derive the T center (the T cell adjacent to the other three), count the four diagonal positions that are out-of-bounds or non-EMPTY
- [x] 4.3 Implement `classify_spin(board, piece, last_action_was_rotation) -> SpinType` per the rules: NONE if no preceding rotation; T → MINI on 3 corners, FULL on 3 corners + immobile, else NONE; non-T → FULL if immobile else NONE

## 5. Reachability enumeration

- [x] 5.1 Define the default spawn table (rotation 0, guideline column/row per piece) in `engine.py`; allow caller override via `spawn`; ensure every piece spawns valid and soft-droppable on an empty board
- [x] 5.2 Implement BFS over `(rotation, row, col)` states with a `visited` set; transitions = LEFT, RIGHT, SOFT_DROP, CW, CCW, and FLIP when enabled; record the producing `Move` for path reconstruction
- [x] 5.3 Implement `allow_flip=None` auto-detection: enable FLIP when the active system defines any 180 kick (`kicks(t, 0, 2)` non-empty), else disable; explicit `True/False` overrides
- [x] 5.4 Emit a candidate `Placement` when `translate(down)` from a state is blocked (resting); compute `spin` via `classify_spin` using whether the producing move was a rotation
- [x] 5.5 Compute `lines_cleared` for each candidate from the locked field (without mutating the input board)
- [x] 5.6 Deduplicate candidates by absolute locked-cell set; on collision keep the highest-ranked `SpinType`
- [x] 5.7 Implement `reachable(board, piece_type, system=None, *, allow_flip=None, spawn=None) -> list[Placement]` tying the above together

## 6. Public API

- [x] 6.1 Export `Move`, `SpinType`, `Placement`, and `reachable` (plus `rotate`, `soft_drop`, `immobile`, `classify_spin`) from `tetris_sdk/__init__.py` and add to `__all__`

## 7. Tests

- [x] 7.1 `tests/test_engine.py` — `Move` rotation classification; `SpinType` ordering; `Placement` hashability/equality
- [x] 7.2 `tests/test_pieces.py` — corrected `SRS` kicks: `(0,0)` first; rotation into a T-spin slot from a decoded fumen succeeds at the expected kick; SRS has no 180 kicks
- [x] 7.3 `tests/test_pieces.py` — `SRSPlus`: shares SRS shapes; JLSTZ 90° identical to SRS; I 90° is the column-reflected variant; 180 transitions non-empty (O empty); a known 180/TST fumen rotates correctly
- [x] 7.4 `tests/test_engine.py` — `translate`: valid move, blocked by wall, blocked by occupied cell, original unchanged
- [x] 7.5 `tests/test_engine.py` — `soft_drop`: rests on floor, rests on a stack
- [x] 7.6 `tests/test_engine.py` — `rotate`: open-space (no kick), kick applied against obstruction, impossible rotation fails, O-piece in-place success
- [x] 7.7 `tests/test_engine.py` — `immobile`: mobile floating piece false; enclosed piece true (build from a fumen field)
- [x] 7.8 `tests/test_engine.py` — `t_corners_filled`: open T low count, out-of-bounds corners counted as filled
- [x] 7.9 `tests/test_engine.py` — `classify_spin`: no-rotation → NONE; T mini (3 corners, mobile); T full (3 corners, immobile); T <3 corners → NONE; non-T immobile → FULL; non-T mobile → NONE
- [x] 7.10 `tests/test_engine.py` — `reachable`: non-empty on empty board with valid paths; dedupe by locked cells (S/Z/I overlap); a known TSS/TST slot from a fumen yields a placement with expected spin; best-spin retained on collision; a fits-but-unreachable position is excluded; `allow_flip` auto-enables under `SRSPlus` and not under `SRS`
