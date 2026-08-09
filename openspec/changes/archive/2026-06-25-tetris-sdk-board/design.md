## Context

The Tetris SDK is a greenfield Python project. The first building blocks are the Board model and the ability to import board states from fumen strings — a community-standard format for sharing Tetris board configurations (used by tools like fumen.zui.jp). Modern (guideline) Tetris uses a 40-row × 10-column playfield. Implementation is pure Python with no external dependencies.

## Goals / Non-Goals

**Goals:**
- Board class representing a 40×10 grid with cell state management and line clear logic
- Local fumen v115 decoder that produces Board objects from fumen strings
- Clean, testable API suitable for downstream consumers (AI, tools, analysis)

**Non-Goals:**
- Piece generation (randomizer, bag system) — future capability
- Game loop, scoring, or gravity simulation — future capabilities
- Fumen encoding (output) — decode only for now
- Version negotiation/upgrades for non-v115 fumen formats

## Decisions

### Board representation: 2D list of integer-backed Cell enum

Use a 2D list (list of lists) of `Cell` enum values, mapping each cell to one of 10 states that encode both occupancy and piece color:

| Value | Name | Meaning |
|---|---|---|
| 0 | EMPTY | Unfilled cell |
| 1 | T | T-piece lock color |
| 2 | I | I-piece lock color |
| 3 | L | L-piece lock color |
| 4 | J | J-piece lock color |
| 5 | S | S-piece lock color |
| 6 | Z | Z-piece lock color |
| 7 | O | O-piece lock color |
| 8 | GARBAGE | Garbage row cell (clearable when row is full) |
| 9 | SOLID | Permanent solid cell (never clears, stays through line clears) |

Row 0 is the bottom (visible playfield), row 39 is the top (hidden rows above the skyline). This is conventional for Tetris implementations and maps naturally to visual rendering.

**Alternatives considered**: 1D flat list, bitboard, numpy array. 2D list is simplest and most readable for the initial SDK. Bitboard would be faster for line clear checks but adds complexity not justified yet. Can migrate later if needed.

### Fumen format: v115, decode-only

Fumen v115 is the current standard. The format encodes one or more "pages" where each page contains a board state. The relevant decoding steps:

1. Strip `v115@` prefix
2. Base64-decode the remaining string (URL-safe variant with custom alphabet if needed)
3. Decompress the result with zlib (deflate)
4. Parse the binary structure: each page has field data using run-length encoding (counts of consecutive cells, bottom-to-top, alternating empty/filled) and piece/comment metadata

**Alternatives considered**: Requesting fumen as a web service API, using a third-party library. Local decoding avoids network dependency, keeps the SDK self-contained, and the format is well-documented. Only stdlib modules needed (`base64`, `zlib`, `struct`).

### Package layout

```
tetris_sdk/
├── __init__.py
├── board.py          # Board class, Row, Cell enum
├── types.py          # Shared types (Cell enum, etc.)
└── fumen/
    ├── __init__.py
    ├── parser.py     # parse_fumen(str) -> list[Board]
    └── decoder.py    # Low-level binary decoding helpers
```

Keeps fumen parsing isolated from core board logic. `types.py` holds shared enums/constants so `board.py` and `fumen/` both depend on it.

## Risks / Trade-offs

- **Fumen format changes**: v115 is stable, but upstream could change. → Pin to v115 explicitly; validate version prefix on parse.
- **Run-length decoding precision**: Off-by-one in the RLE decoding produces subtly wrong boards. → Comprehensive test suite with known fumen strings and expected board states.
- **Memory for 40×10 board**: Negligible (~400 cells), no concern.

## Open Questions

- None at this stage — scope is well-bounded.
