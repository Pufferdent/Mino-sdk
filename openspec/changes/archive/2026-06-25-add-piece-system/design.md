## Context

The Tetris SDK currently has Board representation and fumen import but no concept of tetromino pieces. The target audience is Tetris strategy researchers who need to analyze placements, evaluate board states, and generate possible moves across different rotation systems (SRS, Arika, Classic, etc.).

The SDK already defines a `Cell` enum with values for each piece color (T=1, I=2, L=3, J=4, S=5, Z=6, O=7). This change builds directly on that foundation.

**Data source:** Rotation shapes and kick tables are verified against Techmino's `RSlist.lua` and `gameTables.lua` — the most comprehensive open-source reference implementation of Tetris rotation systems.

## Goals / Non-Goals

**Goals:**
- `PieceType` enum with cell mapping
- `RotationSystem` abstraction — a protocol for pluggable rotation systems
- `SRS` — the guideline rotation system, with shapes and wall kick tables
- `Piece` class — an active piece positioned on a Board, carrying its RotationSystem
- `Board.can_place(piece)` and `Board.place(piece)`
- Architecture that supports adding `ArikaSRS`, `Classic`, `N64`, etc. later

**Non-Goals:**
- Multiple rotation systems beyond SRS in this change (just the abstraction + SRS)
- Wall kick *application* logic (the kick data is provided, the step-through-kicks algorithm is deferred)
- Ghost piece, lock delay, gravity, randomizer, game loop, scoring

## Decisions

### RotationSystem abstraction

Rotation shapes and kick data live on a `RotationSystem` class, not on `PieceType`. `PieceType` stays lightweight — just identity and cell mapping.

```python
class RotationSystem:
    name: str
    def rotations(self, piece_type: PieceType) -> list[list[tuple[int, int]]]
    def kicks(self, piece_type: PieceType, from_rot: int, to_rot: int) -> list[tuple[int, int]]

class SRS(RotationSystem):
    name = "SRS"
    # JLSTZ kick table (shared by T, L, J, S, Z)
    # I-piece kick table
    # O-piece: empty kicks
```

**Alternatives considered:** Putting rotation data on PieceType directly. Rejected — that couples piece identity with a specific rotation system and makes multi-system support impossible without changing the data model.

### Rotation shapes: cell offset tuples with origin shift

Each rotation state is a list of 4 `(row, col)` offset tuples from the piece's position origin. The offsets incorporate the SRS center/offset adjustment, so all 4 states are distinct even for the I-piece.

The shapes are derived from Techmino's boolean matrices (e.g. I-piece = `[[1,1,1,1]]`) rotated clockwise 3 times, then adjusted by the SRS origin offsets per state. This ensures correct absolute cell positions without consumers needing to understand rotation centers.

```
I-piece SRS shapes (origin-relative offsets):
State 0: [(1,0), (1,1), (1,2), (1,3)]  — horizontal, centered in 4×4 box
State 1: [(0,2), (1,2), (2,2), (3,2)]  — vertical, right column
State 2: [(2,0), (2,1), (2,2), (2,3)]  — horizontal, bottom row (distinct from state 0)
State 3: [(0,1), (1,1), (2,1), (3,1)]  — vertical, left-of-center (distinct from state 1)
```

**Alternatives considered:** Separating boolean matrix from center offset (like Techmino does internally). This is more correct but adds conceptual overhead. Pre-computing absolute offsets at the rotation system level keeps the Piece class dead simple.

### `Piece` carries its `RotationSystem`

```python
class Piece:
    type: PieceType
    rotation: int  # 0-3
    row: int       # bottom-left origin
    col: int
    system: RotationSystem  # default SRS

    @property
    def cells(self) -> list[tuple[int, int]]:
        offsets = self.system.rotations(self.type)[self.rotation]
        return [(self.row + dr, self.col + dc) for dr, dc in offsets]
```

Board methods (`can_place`, `place`) use `piece.cells` — they don't need to know about rotation systems.

**Alternatives considered:** Making `cells` take a system parameter instead of storing it on Piece. Rejected — it's more ergonomic to let the piece carry its system, and researchers comparing systems can create pieces with different system references.

### SRS kick data structure

Kick tables map `(from_rotation, to_rotation)` → list of `(row_offset, col_offset)` test positions. Three distinct tables:

**JLSTZ kicks** (used by T, L, J, S, Z):
```
0→1: [(0,0), (-1,0), (-1,+1), (0,-2), (-1,-2)]
1→0: [(0,0), (+1,0), (+1,-1), (0,+2), (+1,+2)]
 ... (8 transitions total, clockwise and counter-clockwise)
```

**I-piece kicks** (distinct from JLSTZ):
```
0→1: [(0,0), (-2,0), (+1,0), (-2,-1), (+1,+2)]
 ... 
```

**O-piece** — empty dict (no kicks needed).

180° kicks (e.g. 0→2) are excluded from SRS but available in `SRS_plus`.

### Package layout

```
tetris_sdk/
├── __init__.py        # Exports PieceType, RotationSystem, SRS, Piece, Cell, Board, parse_fumen
├── types.py           # Cell enum (unchanged)
├── board.py           # Board + can_place, place (modified)
└── pieces.py          # PieceType, RotationSystem, SRS, Piece (new)
```

`pieces.py` imports from `types.py` (Cell). `board.py` imports from `pieces.py` (Piece). No circular dependencies.

## Risks / Trade-offs

- **SRS shape correctness**: Incorrect offsets would produce wrong placements. → Shapes and kick tables verified against Techmino's data; tested against known board states from fumen strings.
- **Rotation count assumption**: All pieces expose 4 states even though O-piece has 1 distinct shape. → This is how SRS works and simplifies consumer code (always index 0-3). The rotation system abstraction allows future systems to define different state counts if needed.
- **Origin semantics**: The origin (row, col) of a Piece is the bottom-left corner of the bounding box. → Documented clearly on the Piece class.
- **Scalability**: Adding 16+ rotation systems means a lot of data. → Each system stores only tetromino data (indices 1-7), not the full 29-piece set Techmino uses. This keeps data manageable.

## Open Questions

- Should wall kick *application* (trying offsets in sequence) be part of this change? Decision: no — this change provides data, the algorithm comes with the game engine.
