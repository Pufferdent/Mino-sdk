# Board

## Purpose

The Board module provides a standard modern Tetris playfield representation — a 40-row × 10-column grid with per-cell piece color tracking, row inspection, and line clear logic.

## Requirements

### Requirement: Board dimensions
The Board SHALL represent a modern Tetris playfield with 40 rows and 10 columns. Row 0 SHALL be the bottom of the visible playfield and row 39 SHALL be the top.

#### Scenario: Board created with correct dimensions
- **WHEN** a Board is instantiated with default parameters
- **THEN** the board has 40 rows and 10 columns

#### Scenario: All cells initialized as empty
- **WHEN** a Board is instantiated with default parameters
- **THEN** every cell on the board is EMPTY

### Requirement: Cell states
The Board SHALL support ten cell states representing piece color and cell type:

| Value | Name | Description |
|---|---|---|
| 0 | EMPTY | Unfilled cell |
| 1 | T | Locked T-piece cell |
| 2 | I | Locked I-piece cell |
| 3 | L | Locked L-piece cell |
| 4 | J | Locked J-piece cell |
| 5 | S | Locked S-piece cell |
| 6 | Z | Locked Z-piece cell |
| 7 | O | Locked O-piece cell |
| 8 | GARBAGE | Clearable garbage cell |
| 9 | SOLID | Permanent solid cell that survives line clears |

#### Scenario: Get cell value
- **WHEN** `get_cell(row, col)` is called at a valid position
- **THEN** the current cell state (integer 0-9) is returned

#### Scenario: Set cell value
- **WHEN** `set_cell(row, col, T)` is called at a valid position
- **THEN** the cell at that position is updated to T (1)

#### Scenario: Set cell with out-of-bounds position raises error
- **WHEN** `set_cell(row, col, value)` is called with row or col outside valid range
- **THEN** an IndexError or ValueError is raised

### Requirement: Row queries
The Board SHALL provide methods to inspect individual rows.

#### Scenario: Row is full
- **WHEN** `is_row_full(row)` is called on a row where all 10 cells are non-EMPTY (values 1-9)
- **THEN** the method returns True

#### Scenario: Row is not full
- **WHEN** `is_row_full(row)` is called on a row where at least one cell is EMPTY (0)
- **THEN** the method returns False

### Requirement: Line clear
The Board SHALL support clearing full rows by removing them and shifting rows above downward. A row that contains any SOLID cell SHALL never be cleared, even if all 10 cells are non-EMPTY.

#### Scenario: Clear a single full row
- **WHEN** `clear_lines()` is called and row 5 is full (all cells non-EMPTY) with no SOLID cells
- **THEN** row 5 is removed, rows 6 through 39 shift down by one, and row 39 becomes a new empty row

#### Scenario: Clear multiple full rows simultaneously
- **WHEN** `clear_lines()` is called and rows 3 and 7 are full with no SOLID cells
- **THEN** both rows are removed, rows above each shift down, and two new empty rows are added at the top

#### Scenario: No rows to clear
- **WHEN** `clear_lines()` is called and no row is full
- **THEN** the board is unchanged

#### Scenario: Row with SOLID cell is never cleared
- **WHEN** `clear_lines()` is called and row 4 is full (all 10 cells non-EMPTY) but contains at least one SOLID cell
- **THEN** row 4 is NOT cleared and remains on the board unchanged

### Requirement: Board string representation
The Board SHALL provide a string representation for debugging, showing the board from top (row 39) to bottom (row 0) with distinct characters per cell type.

#### Scenario: Debug string shows board state
- **WHEN** `str(board)` or `repr(board)` is called
- **THEN** a human-readable ASCII representation of the board is returned using a distinct glyph per Cell value (0-9)

### Requirement: Board running event state
The `Board` SHALL maintain mutable running state for event detection: `b2b` (int, back-to-back chain length, 0 when no chain), `combo` (int, consecutive line-clearing locks, 0 when none), and `b2b_rule` (B2BRule, configurable, default `S2`). A freshly constructed `Board` and a `Board` created via `from_fumen` SHALL start with `b2b == 0`, `combo == 0`, and the default rule.

#### Scenario: New board starts with no active chain or combo
- **WHEN** a `Board` is constructed without arguments
- **THEN** `board.b2b == 0`, `board.combo == 0`, and `board.b2b_rule == B2BRule.S2`

#### Scenario: B2B rule is configurable
- **WHEN** a `Board` is constructed with `b2b_rule=B2BRule.S1`
- **THEN** `board.b2b_rule == B2BRule.S1`

### Requirement: Board lock returns an Event
The `Board` SHALL provide a `lock(piece, spin=SpinType.NONE) -> Event` method that places the piece (as `place` does, raising `ValueError` on an invalid placement), removes any full rows, updates the running `b2b` and `combo` state using the board's `b2b_rule`, and returns an `Event` describing the outcome (kind, piece, spin, lines, derived name, difficulty, back-to-back flag, running b2b and combo, and perfect-clear flag). The spin SHALL be taken from the argument and SHALL NOT be recomputed from board state.

#### Scenario: Locking a piece that clears lines returns a CLEAR event
- **WHEN** `board.lock(piece, spin)` is called and the placement completes one or more rows
- **THEN** those rows are removed, the event kind is `CLEAR`, and `lines` equals the number of removed rows

#### Scenario: Lock uses the supplied spin verbatim
- **WHEN** `board.lock(piece, SpinType.FULL)` is called for a T-piece completing 2 rows
- **THEN** the event has `spin == FULL` and `name == "T-Spin Double"`, regardless of board geometry

#### Scenario: A spin that clears nothing yields a SPIN event
- **WHEN** `board.lock(piece, SpinType.MINI)` is called and no rows complete
- **THEN** the event kind is `SPIN`, `lines == 0`, and `difficult` is false

#### Scenario: Locking an invalid placement raises
- **WHEN** `board.lock(piece)` is called with a piece that cannot be placed
- **THEN** a `ValueError` is raised and the running `b2b`/`combo` state is unchanged

#### Scenario: Rule selection changes difficulty
- **WHEN** an `S`-piece spin single is locked on a board with `b2b_rule=S1` versus one with `b2b_rule=S2`
- **THEN** the event is non-difficult (breaks B2B) under `S1` and difficult under `S2`
