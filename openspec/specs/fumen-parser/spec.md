# Fumen Parser

## Purpose

The Fumen Parser decodes fumen v115 strings (a community-standard format for sharing Tetris board configurations) into Board objects, enabling local import of board states without external services.

## Requirements

### Requirement: Parse fumen v115 string
The system SHALL parse a fumen v115 string and return a list of Board objects, one per page encoded in the fumen data.

#### Scenario: Parse a valid fumen string with one page
- **WHEN** `parse_fumen("v115@AhBtDewhBeBtEewhCeR4De0hR4CewhJeAgH")` is called
- **THEN** a list with one Board object is returned representing the decoded board state

#### Scenario: Parse returns multiple boards for multi-page fumen
- **WHEN** `parse_fumen(...)` is called with a fumen string containing two pages
- **THEN** a list with two Board objects is returned

### Requirement: Version validation
The parser SHALL validate the fumen string's version prefix and reject unsupported versions.

#### Scenario: Valid v115 prefix accepted
- **WHEN** the fumen string starts with `v115@`
- **THEN** parsing proceeds normally

#### Scenario: Unsupported version raises error
- **WHEN** the fumen string starts with `v110@` or any version other than `v115@`
- **THEN** a ValueError is raised indicating unsupported version

#### Scenario: Missing version prefix raises error
- **WHEN** the fumen string does not contain `@`
- **THEN** a ValueError is raised

### Requirement: Field data reconstruction
The parser SHALL decode the fumen-encoded field data to reconstruct board cell states using differential run-length encoding. The fumen's 24 encoded rows SHALL be mapped to the bottom 23 rows of the Board — the fumen's bottom row (row 23) is always unused and SHALL be discarded.

#### Scenario: Fumen bottom row discarded
- **WHEN** a fumen string with a block at the bottom meaningful row (fumen row 22) is parsed
- **THEN** that block appears at Board row 0 (the very bottom)

#### Scenario: Empty board round-trips correctly
- **WHEN** a fumen string representing an empty board is parsed
- **THEN** the resulting Board has all cells EMPTY

#### Scenario: Board with single filled cell
- **WHEN** a fumen string representing a board with one T-piece cell at a known position is parsed
- **THEN** the resulting Board has exactly that cell as T (1) and all others EMPTY

### Requirement: Cell type preservation
The parser SHALL preserve piece colors (T/I/L/J/S/Z/O), GARBAGE, and SOLID cells when decoding fumen data, matching the original cell types encoded in the fumen string.

#### Scenario: Piece colors preserved after parsing
- **WHEN** a fumen string representing a board with cells of different piece types is parsed
- **THEN** the corresponding cells in the Board retain their exact piece color (1-7)

#### Scenario: GARBAGE cells preserved after parsing
- **WHEN** a fumen string representing a board with GARBAGE cells is parsed
- **THEN** the corresponding cells in the Board are GARBAGE (8), not a piece color

#### Scenario: SOLID cells preserved after parsing
- **WHEN** a fumen string representing a board with SOLID cells is parsed
- **THEN** the corresponding cells in the Board are SOLID (9)
