## Context

The Mino SDK currently provides fumen *decoding* only via `decode_fumen` / `parse_fumen`, with no encoding path. The `parse_fumen` function throws away piece operation data that `decode_fumen` already parses. Consumers (PC-NN pipeline) currently rely on `py_fumen_py` for encoding and cumulative board states, and on `sfinder.jar` (Java subprocess) for PC solving. The goal is to bring these capabilities into the SDK as a native Python pipeline.

## Goals / Non-Goals

**Goals:**
- Faithful multi-page fumen representation (`MultiFumenPage`) that preserves raw page data without imposing sequence semantics
- Board-to-string round-trip in the PC 40-char format
- Standalone piece shape computation for any type/rotation/position
- Fumen encoding (Board → v115 string)
- Native Python PC solver with hold support, topological ordering, and structured output
- Wanted-saves expression parser and evaluator (from PC-Saves-Get)

**Non-Goals:**
- Changing the existing `parse_fumen` return type (it stays `list[Board]`)
- Full game simulation engine (already exists in `sim/`)
- Scoring system
- TETR.IO-specific gravity/line-clear timing

## Decisions

### Decision 1: MultiFumenPage is a new class, not a parse_fumen change

`MultiFumenPage` lives alongside `parse_fumen` — it does not replace it. Existing code depending on `parse_fumen` returning `list[Board]` continues to work. `MultiFumenPage.from_string()` is the entry point for multi-page fumen parsing.

**Alternatives considered:**
- Adding `cumulative=True` parameter to `parse_fumen` — rejected because it changes return type conditionally (list[Board] vs list[FumenPage]), which is confusing.
- Always returning richer objects — rejected because it's a breaking change.

### Decision 2: Module layout

```
mino_sdk/
├── fumen/
│   ├── decoder.py          # unchanged
│   ├── parser.py           # unchanged: parse_fumen
│   ├── multi_fumen.py      # NEW: MultiFumenPage class
│   └── encoder.py          # NEW: encode_fumen
├── board.py                # ADD: board_from_string, board_to_string
├── pieces.py               # ADD: get_piece_cells, piece type mappings
├── coords.py               # NEW: coordinate conversion utilities
└── solver/                 # NEW: entire solver subsystem
    ├── __init__.py
    ├── core.py             # solve_pc, DFS/backtrack algorithm
    ├── expressions.py      # Wanted-saves expression parser & AST
    ├── saves.py            # Save analysis, percentage computation
    └── queue_validator.py  # is_placement_order_valid, enumerate_placement_orders
```

**Rationale:** The fumen encoding and multi-page parsing are closely related to the existing fumen decoder — they share encoding tables and field structures. The solver is an entirely new subsystem with no existing dependencies in the SDK (except consuming Board, Piece, and engine primitives).

### Decision 3: MultiFumenPage structure

```python
@dataclass
class Page:
    board: Board
    comment: str

class MultiFumenPage:
    pages: list[Page]

    @classmethod
    def from_string(cls, fumen_str: str) -> "MultiFumenPage": ...
```

Pages carry board state (as decoded from the fumen field) and the comment. No `operation` field — the operation concept only applies to a specific interpretation (placement sequence), not to general-purpose fumen pages. Users who need cumulative board states can build that on top of `MultiFumenPage` themselves.

### Decision 4: Board string format

The 40-char string represents the bottom 4 rows (rows 0-3) of the board, encoded top-to-bottom: characters 0-9 = row 3, 10-19 = row 2, 20-29 = row 1, 30-39 = row 0. Glyphs: `N` = EMPTY, `X` = GARBAGE/SOLID, piece letters for colored cells.

### Decision 5: Solver algorithm

The solver uses DFS with memoization:
1. For the current board state and remaining queue prefix, enumerate reachable placements via `engine.reachable()`
2. For each placement, lock the piece, clear lines, recurse
3. Memoize `(board_hash, queue_position, hold_state)` → `list[solutions]` to avoid redundant search
4. Solutions track the piece order, boards, operations, and unused pieces
5. Topological orderings are computed post-solve using piece physics (no cell overlap, support constraints)

**Alternatives considered:**
- Porting sfinder-cpp's algorithm directly — rejected because it's in C++ and optimizes for different constraints; the SDK solver can leverage existing `reachable()`, `Board.lock()`, and rotation system.
- Using Zobrist hashing for board state — deferred to optimization phase; initial implementation uses tuple-of-tuples hashing which is sufficient for correctness.

### Decision 6: Wanted-saves expression parser

Recursive descent parser with precedence: OR < AND < NOT/AVOID < atomic. Produces an AST that is evaluated against a list of save strings. Same tokenizer approach as PC-Saves-Get (regex-based tokenizer → recursive descent parser → AST → evaluator).

## Risks / Trade-offs

- **Solver performance**: The naive DFS may be slow for complex setups (large boards, long queues). Mitigation: board-state memoization from the start. Further optimizations (Zobrist hashing, pattern precomputation) can follow.
- **Fumen encoding correctness**: The fumen binary format has edge cases (field repeat count, color mode, rise/mirror flags). Mitigation: round-trip tests (encode → decode → compare).
- **Coordinate confusion**: The SDK, fumen, and PC board string all use different conventions. Mitigation: explicit `coords.py` utility module with documented conversion functions — no implicit conversions.
- **Expression language scope**: The wanted-saves language from PC-Saves-Get has some features (# labels, !(T&&S)||L precedence subtleties) that may have edge cases. Mitigation: port the existing test suite alongside the parser.

## Open Questions

- Should `solve_pc` accept the board as a `Board` object, a 40-char string, or both? Both with auto-detection minimizes friction for consumers.
- Should the solver expose progress callbacks for long-running solves? Deferred — can be added later without API changes.
- Does fumen encoding need `lzstring` for the `?` compression suffix? The decoder strips `?` characters — research needed on whether encoding requires LZ compression.
