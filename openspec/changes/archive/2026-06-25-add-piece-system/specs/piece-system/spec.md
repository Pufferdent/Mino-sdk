# Piece System

## Purpose

The Piece System module defines the seven standard guideline tetromino pieces, a pluggable rotation system abstraction, the SRS rotation system with shapes and wall kick data, and operations for positioning and placing pieces on a Board.

## ADDED Requirements

### Requirement: Piece type enumeration
The system SHALL provide a `PieceType` enum with the seven standard tetromino types: T (1), I (2), L (3), J (4), S (5), Z (6), O (7). Each member's integer value SHALL match the corresponding `Cell` enum value. `PieceType` SHALL expose a `cell` property mapping to the corresponding `Cell`.

#### Scenario: Access piece type values
- **WHEN** a consumer references `PieceType.T`
- **THEN** `PieceType.T.value` equals 1

#### Scenario: Map piece type to cell
- **WHEN** `PieceType.L.cell` is accessed
- **THEN** the result is `Cell.L`

### Requirement: Rotation system abstraction
The system SHALL provide a `RotationSystem` base class with methods `rotations(piece_type)` returning 4 rotation states as lists of `(row, col)` offset tuples, and `kicks(piece_type, from_rotation, to_rotation)` returning a list of `(row_offset, col_offset)` wall kick test positions.

#### Scenario: RotationSystem is subclassable
- **WHEN** a new class inherits from `RotationSystem` and implements `rotations` and `kicks`
- **THEN** it can be passed as the `system` parameter to `Piece` and used for placement

### Requirement: SRS rotation system
The system SHALL provide an `SRS` class inheriting from `RotationSystem` that implements the guideline Super Rotation System. `SRS.rotations()` SHALL return 4 rotation states per piece type, each containing 4 `(row, col)` offset tuples representing the cells occupied relative to the piece origin. The I-piece SHALL have 4 distinct rotation states incorporating SRS origin offset adjustments. `SRS.kicks()` SHALL return the standard SRS wall kick offsets for all 8 rotation transitions.

#### Scenario: SRS T-piece has 4 rotation states
- **WHEN** `SRS().rotations(PieceType.T)` is accessed
- **THEN** a list of length 4 is returned, each element being a list of 4 cell offset tuples

#### Scenario: SRS I-piece has 4 distinct rotation states
- **WHEN** `SRS().rotations(PieceType.I)` is accessed
- **THEN** a list of length 4 is returned, and all four states contain different cell offsets

#### Scenario: SRS O-piece has 4 identical rotation states
- **WHEN** `SRS().rotations(PieceType.O)` is accessed
- **THEN** a list of length 4 is returned, and all four states contain the same cell offsets

#### Scenario: SRS JLSTZ kick table
- **WHEN** `SRS().kicks(PieceType.T, 0, 1)` is called
- **THEN** a list of `(row, col)` offset tuples is returned, with at least `[(0, 0), (-1, 0), (-1, 1), (0, -2), (-1, -2)]`

#### Scenario: SRS I-piece has distinct kick table
- **WHEN** `SRS().kicks(PieceType.I, 0, 1)` is compared to `SRS().kicks(PieceType.T, 0, 1)`
- **THEN** the offset lists are different

#### Scenario: SRS O-piece has empty kicks
- **WHEN** `SRS().kicks(PieceType.O, 0, 1)` is called
- **THEN** an empty list is returned

### Requirement: Piece class
The system SHALL provide a `Piece` class with `type: PieceType`, `rotation: int` (0-3), `row: int`, `col: int`, and `system: RotationSystem` (default SRS) attributes. The origin (`row`, `col`) SHALL be the bottom-left corner of the piece's bounding box. The `system` attribute SHALL default to `SRS()`.

#### Scenario: Create a piece with defaults
- **WHEN** a `Piece` is constructed with `Piece(PieceType.T)`
- **THEN** `piece.type == PieceType.T`, `piece.rotation == 0`, `piece.row == 0`, `piece.col == 0`, and `piece.system` is an SRS instance

#### Scenario: Create a piece with explicit values
- **WHEN** `Piece(PieceType.I, rotation=1, row=18, col=4)` is constructed
- **THEN** the piece's type is I, rotation is 1, row is 18, and col is 4

### Requirement: Piece absolute cell positions
The `Piece` class SHALL provide a `cells` property returning a list of absolute `(row, col)` board positions occupied by the piece, computed by adding the piece's row/col position to the system's rotation shape offsets.

#### Scenario: T-piece at origin in rotation 0
- **WHEN** `Piece(PieceType.T, rotation=0, row=0, col=0, system=SRS()).cells` is accessed
- **THEN** a list of 4 `(row, col)` tuples is returned, representing the SRS T-piece shape at the board origin

#### Scenario: T-piece offset from origin
- **WHEN** `Piece(PieceType.T, rotation=0, row=5, col=3, system=SRS()).cells` is accessed
- **THEN** all returned positions have row >= 5 and col >= 3

### Requirement: Piece copy method
The `Piece` class SHALL provide a `copy(**overrides)` method returning a new `Piece` with optionally overridden attributes.

#### Scenario: Copy with rotation override
- **WHEN** `piece.copy(rotation=2)` is called on a piece with rotation 0
- **THEN** a new Piece is returned with rotation 2, and the original piece is unchanged

#### Scenario: Copy preserves system
- **WHEN** `piece.copy(col=5)` is called
- **THEN** the returned Piece has the same `system` as the original

### Requirement: Board placement validation
The `Board` class SHALL provide a `can_place(piece)` method returning `True` if and only if all cells occupied by the piece are within board bounds and are EMPTY.

#### Scenario: Valid placement on empty board
- **WHEN** `board.can_place(Piece(PieceType.O, row=0, col=0))` is called on an empty board
- **THEN** the method returns `True`

#### Scenario: Placement blocked by occupied cell
- **WHEN** `board.can_place(piece)` is called and at least one cell the piece would occupy is non-EMPTY
- **THEN** the method returns `False`

#### Scenario: Placement out of bounds
- **WHEN** `board.can_place(Piece(PieceType.T, row=0, col=-1))` is called
- **THEN** the method returns `False`

#### Scenario: Placement above top of board
- **WHEN** `board.can_place(piece)` is called where the piece extends above row 39
- **THEN** the method returns `False`

### Requirement: Board piece placement
The `Board` class SHALL provide a `place(piece)` method that locks the piece onto the board by setting each occupied cell to the piece type's corresponding `Cell` value. If placement is invalid, a `ValueError` SHALL be raised.

#### Scenario: Place a piece on an empty board
- **WHEN** `board.place(Piece(PieceType.L, row=0, col=0))` is called on an empty board
- **THEN** the 4 cells occupied by the L-piece are now `Cell.L`

#### Scenario: Place on invalid position raises error
- **WHEN** `board.place(piece)` is called with a piece that cannot be placed
- **THEN** a `ValueError` is raised

#### Scenario: Board cells are the correct Cell enum value
- **WHEN** `board.place(Piece(PieceType.S, row=5, col=2))` is called successfully
- **THEN** all occupied cells read as `Cell.S`
