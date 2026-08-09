# Piece System

## MODIFIED Requirements

### Requirement: SRS rotation system
The system SHALL provide an `SRS` class inheriting from `RotationSystem` that implements the guideline Super Rotation System. `SRS.rotations()` SHALL return 4 rotation states per piece type, each containing 4 `(row, col)` offset tuples representing the cells occupied relative to the piece origin. The I-piece SHALL have 4 distinct rotation states incorporating SRS origin offset adjustments. `SRS.kicks()` SHALL return the standard SRS wall kick offsets for all 8 rotation transitions.

Kick offsets SHALL be expressed as `(drow, dcol)` deltas in the SDK's native row-increasing-upward frame — the same convention as `Piece.cells` — so that applying a kick is `(row + drow, col + dcol)`. The first test SHALL be `(0, 0)`. (This corrects the previously stored values, which were transcribed as `(x, y)` y-up numbers under a `(row, col)` label and were never applied; correctness SHALL be confirmed by decoding a known T-spin fumen to a `Board` and verifying a rotation into the slot succeeds via the expected kick.) `SRS` SHALL return an empty kick list for all O-piece transitions and for all 180 transitions.

#### Scenario: SRS T-piece has 4 rotation states
- **WHEN** `SRS().rotations(PieceType.T)` is accessed
- **THEN** a list of length 4 is returned, each element being a list of 4 cell offset tuples

#### Scenario: SRS I-piece has 4 distinct rotation states
- **WHEN** `SRS().rotations(PieceType.I)` is accessed
- **THEN** a list of length 4 is returned, and all four states contain different cell offsets

#### Scenario: SRS O-piece has 4 identical rotation states
- **WHEN** `SRS().rotations(PieceType.O)` is accessed
- **THEN** a list of length 4 is returned, and all four states contain the same cell offsets

#### Scenario: SRS kicks are (drow, dcol) deltas applicable to a piece
- **WHEN** an `SRS` kick offset `(drow, dcol)` for a transition is added to a piece's `(row, col)` origin
- **THEN** the resulting position is the kicked candidate in the same frame as `Piece.cells`, and the first offset tested is `(0, 0)`

#### Scenario: SRS kick correctness against a known fumen
- **WHEN** a board decoded from a known T-spin-single fumen has a T rotated into its slot using `SRS` kicks
- **THEN** the rotation succeeds at the kick offset that places the T in the slot, confirming the `(drow, dcol)` convention

#### Scenario: SRS I-piece has distinct kick table
- **WHEN** `SRS().kicks(PieceType.I, 0, 1)` is compared to `SRS().kicks(PieceType.T, 0, 1)`
- **THEN** the offset lists are different

#### Scenario: SRS O-piece has empty kicks
- **WHEN** `SRS().kicks(PieceType.O, 0, 1)` is called
- **THEN** an empty list is returned

#### Scenario: SRS has no 180 kicks
- **WHEN** `SRS().kicks(PieceType.T, 0, 2)` is called
- **THEN** an empty list is returned

## ADDED Requirements

### Requirement: SRS+ rotation system
The system SHALL provide an `SRSPlus` class inheriting from `RotationSystem` that implements TETR.IO's SRS+ rotation system. `SRSPlus` SHALL share `SRS`'s rotation shapes. Its kick tables SHALL be defined relative to the corrected `SRS` kick tables, in the same `(drow, dcol)` row-up convention:

- JLSTZ 90° transitions SHALL be identical to `SRS`.
- I-piece 90° transitions SHALL be the SRS+ symmetric variant (the `SRS` I-piece kicks reflected along the column axis).
- All four 180 transitions `(0,2)`, `(2,0)`, `(1,3)`, `(3,1)` SHALL be populated for JLSTZ/T and I (O SHALL remain empty), using the SRS+ 180 kick data.

The 180 kick data SHALL be verified by decoding a known 180/TST setup fumen to a `Board` and confirming the 180 rotation succeeds via the expected kick.

#### Scenario: SRS+ shares SRS rotation shapes
- **WHEN** `SRSPlus().rotations(PieceType.T)` is compared to `SRS().rotations(PieceType.T)`
- **THEN** the rotation states are identical

#### Scenario: SRS+ JLSTZ 90 kicks match SRS
- **WHEN** `SRSPlus().kicks(PieceType.L, 0, 1)` is compared to `SRS().kicks(PieceType.L, 0, 1)`
- **THEN** the offset lists are identical

#### Scenario: SRS+ I-piece 90 kicks are the symmetric variant
- **WHEN** `SRSPlus().kicks(PieceType.I, 0, 1)` is compared to `SRS().kicks(PieceType.I, 0, 1)`
- **THEN** the offsets are the SRS I-piece kicks reflected along the column axis (not identical)

#### Scenario: SRS+ defines 180 kicks
- **WHEN** `SRSPlus().kicks(PieceType.T, 0, 2)` is called
- **THEN** a non-empty list of `(drow, dcol)` offsets is returned

#### Scenario: SRS+ O-piece has no kicks
- **WHEN** `SRSPlus().kicks(PieceType.O, 0, 2)` is called
- **THEN** an empty list is returned

#### Scenario: SRS+ 180 kick correctness against a known fumen
- **WHEN** a board decoded from a known 180-spin fumen has a piece rotated 180 into its slot using `SRSPlus` kicks
- **THEN** the rotation succeeds at the expected kick offset, confirming the 180 data and convention
