# Fumen Pipeline

## Purpose

The Fumen Pipeline extends the core fumen decoder with multi-page parsing, board-to-string conversion, piece shape computation, fumen encoding, coordinate system utilities, piece type mappings, and color-mode decoding support. These capabilities form the interchange layer between the Mino SDK and external tools (PC-NN pipelines, fumen viewers, sfinder output).

## Requirements

### Requirement: Multi-page fumen parsing
The system SHALL provide a `MultiFumenPage` class that parses a v115 fumen string into a sequence of pages, each containing a `Board` and optional comment. Pages SHALL faithfully represent the raw fumen data without imposing a sequential interpretation.

#### Scenario: Parse a single-page fumen
- **WHEN** `MultiFumenPage.from_string("v115@...")` is called with a valid single-page fumen
- **THEN** the result contains one page with a `Board` reflecting the fumen field and an empty comment

#### Scenario: Parse a multi-page fumen
- **WHEN** `MultiFumenPage.from_string("v115@...")` is called with a 3-page fumen
- **THEN** the result contains 3 pages, each with its own `Board` and comment

#### Scenario: Pages preserve comments
- **WHEN** a fumen page includes an encoded comment
- **THEN** the corresponding page's `comment` attribute contains the decoded comment string

#### Scenario: Invalid fumen string
- **WHEN** `MultiFumenPage.from_string` is given a string without a valid version prefix
- **THEN** it raises a `ValueError`

#### Scenario: Unsupported fumen version
- **WHEN** `MultiFumenPage.from_string` is given a version other than `v115`
- **THEN** it raises a `ValueError`

### Requirement: Board string round-trip
The system SHALL provide `board_from_string()` and `board_to_string()` functions that convert between `Board` objects and the canonical 40-character PC board string format.

#### Scenario: Convert board to string
- **WHEN** `board_to_string(board)` is called with a board containing a T-piece and some garbage cells
- **THEN** the returned 40-character string uses 'N' for empty, 'X' for garbage/solid, and piece letters for colored cells

#### Scenario: Convert string to board
- **WHEN** `board_from_string("XXXXXXNNNXNNNXXNNNNXNNXXNNNNNXNNNXXNNNNX")` is called
- **THEN** the returned `Board` has cells matching the string's top-to-bottom, row-0-is-bottom convention

#### Scenario: Round-trip consistency
- **WHEN** a string is converted to a board and back to a string
- **THEN** the final string is identical to the original string

#### Scenario: PC board string coordinate convention
- **WHEN** `board_from_string` parses a string
- **THEN** the first 10 characters of the string map to board rows 3-3 (inclusive, descending) and the last 10 characters map to board row 0

### Requirement: Piece shape computation
The system SHALL provide a `get_piece_cells()` function that returns the list of (row, col) cells a piece occupies given its type, rotation, and pivot position.

#### Scenario: T-piece spawn at (5, 2) in SDK coordinates
- **WHEN** `get_piece_cells(PieceType.T, Rotation.SPAWN, x=5, y=2)` is called
- **THEN** the returned list contains exactly the 4 cells a T-piece occupies at that position, in (row, col) format, with (2,5), (2,6), (2,7), (3,6) for the bottom 3 cells and center cell

#### Scenario: O-piece at (0, 0)
- **WHEN** `get_piece_cells(PieceType.O, Rotation.SPAWN, x=0, y=0)` is called
- **THEN** the returned list is `[(0,0), (0,1), (1,0), (1,1)]`

#### Scenario: I-piece rotated right at (3, 4)
- **WHEN** `get_piece_cells(PieceType.I, Rotation.RIGHT, x=4, y=3)` is called
- **THEN** a 4-cell vertical column shape is returned centered at (4, 3)

#### Scenario: Fumen coordinate system
- **WHEN** `get_piece_cells` is called with `coord_system='fumen'`
- **THEN** the returned coordinates use (x, y) tuple format where y=0 is the bottom row

#### Scenario: Invalid rotation index
- **WHEN** `get_piece_cells` is called with a rotation index outside 0-3
- **THEN** it raises a `ValueError`

### Requirement: Fumen encoding
The system SHALL provide an `encode_fumen()` function that encodes a list of pages (each with a `Board` and optional comment) into a valid v115 fumen string.

#### Scenario: Encode a single board
- **WHEN** `encode_fumen([(board, "")])` is called with a board containing no cells
- **THEN** the returned string starts with `v115@` and decodes back to an empty board

#### Scenario: Encode with comments
- **WHEN** `encode_fumen([(board, "hello")])` is called
- **THEN** the encoded fumen, when decoded, yields a page with comment "hello"

#### Scenario: Encode and decode round-trip
- **WHEN** a board with mixed piece types and garbage is encoded and then decoded
- **THEN** the decoded board is visually identical to the original

#### Scenario: Encode multi-page fumen
- **WHEN** `encode_fumen` is given 3 pages
- **THEN** the resulting fumen decodes to 3 pages with matching board states and comments

### Requirement: Coordinate system documentation and utilities
The system SHALL document all coordinate system conventions used within the SDK and provide conversion utilities between SDK board coordinates, fumen field coordinates, and fumen piece-pivot coordinates.

#### Scenario: SDK to fumen field column conversion
- **WHEN** converting SDK board column `c` to fumen field column
- **THEN** the result is `c` (columns are identical between systems)

#### Scenario: SDK to fumen field row conversion
- **WHEN** converting SDK board row `r` (where r=0 is bottom) to fumen field row
- **THEN** the result is `FUMEN_VISIBLE_ROWS - 1 - r` (fumen row 0 is top)

#### Scenario: Fumen piece pivot to SDK row conversion
- **WHEN** converting fumen piece pivot `(x, y)` where y=0 is the top of the visible field to SDK board row
- **THEN** the result is `FUMEN_VISIBLE_ROWS - 1 - y`

### Requirement: Piece type mapping tables
The system SHALL expose mapping tables between fumen piece type indices and SDK `PieceType` / `Cell` enums.

#### Scenario: Fumen index to PieceType
- **WHEN** converting fumen piece index 0 (I in fumen convention)
- **THEN** the result is `PieceType.I`

#### Scenario: Fumen index to Cell
- **WHEN** converting fumen field cell index 1 (I in fumen convention)
- **THEN** the result is `Cell.I`

#### Scenario: PieceType to fumen index
- **WHEN** converting `PieceType.T` to fumen piece index
- **THEN** the result is 4

### Requirement: Color-mode fumen field decoding
The system SHALL correctly decode fumen pages where the `color` flag is `True`, mapping non-piece fill values (8+) to `Cell.GARBAGE` or a documented sentinel.

#### Scenario: Color-mode page with fill value 8
- **WHEN** a fumen page has `color: True` and a field cell value of 8
- **THEN** the decoded `Board` cell is `Cell.GARBAGE`

#### Scenario: Color-mode page with standard piece values
- **WHEN** a fumen page has `color: True` and a field cell value of 0 (empty in fumen)
- **THEN** the decoded `Board` cell is `Cell.EMPTY`

#### Scenario: Non-color-mode page unchanged
- **WHEN** a fumen page has `color: False`
- **THEN** field cell values are decoded per the standard `FUMEN_TO_CELL` mapping with the existing >8 clamp
