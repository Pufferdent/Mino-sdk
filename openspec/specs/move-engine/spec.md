# Move Engine

## Purpose

The Move Engine module turns the static Board/Piece model into reachable play. It applies the active rotation system's wall kicks, performs soft/hard drops and unit translations, detects whether a resting piece is immobile, classifies spins (none/mini/full) under the immobile convention, and enumerates every placement a player could reach from spawn for a given piece type. It is the foundation for placement search, bot action spaces, and spin-stacking analysis. It consumes only the existing public surfaces of Board, Piece, and RotationSystem and adds no new dependencies.

## Requirements

### Requirement: Move enumeration
The system SHALL provide a `Move` enum with members `LEFT`, `RIGHT`, `SOFT_DROP`, `CW`, `CCW`, `FLIP`, and `HARD_DROP`. `CW`, `CCW`, and `FLIP` SHALL be classified as rotation moves.

#### Scenario: Rotation moves are identifiable
- **WHEN** a consumer checks whether `Move.CW`, `Move.CCW`, or `Move.FLIP` is a rotation move
- **THEN** each is reported as a rotation move, and `Move.LEFT`, `Move.RIGHT`, `Move.SOFT_DROP`, `Move.HARD_DROP` are not

### Requirement: SpinType enumeration
The system SHALL provide a `SpinType` enum with members `NONE`, `MINI`, and `FULL`, ordered such that `FULL` outranks `MINI` outranks `NONE`.

#### Scenario: Spin types are ordered
- **WHEN** the relative rank of `SpinType.FULL`, `SpinType.MINI`, and `SpinType.NONE` is compared
- **THEN** `FULL` is the highest rank and `NONE` is the lowest

### Requirement: Placement value type
The system SHALL provide a `Placement` value type that is immutable and hashable, carrying `type` (PieceType), `rotation` (int), `row` (int), `col` (int), `spin` (SpinType), `lines_cleared` (int), and `path` (a tuple of `Move`).

#### Scenario: Placement is hashable
- **WHEN** two `Placement` values with identical field values are created
- **THEN** they compare equal and hash equal, and can be used as set or dict keys

### Requirement: Unit translation
The system SHALL provide a translation operation that, given a Board, a Piece, and a row/column delta, returns a new Piece at the translated position if every cell it would occupy is in-bounds and EMPTY, or a sentinel indicating the translation is blocked otherwise. The original Piece SHALL be unchanged.

#### Scenario: Valid translation returns a moved piece
- **WHEN** a piece on an empty board is translated one column right
- **THEN** a new piece is returned whose column is one greater and whose other attributes are unchanged

#### Scenario: Blocked translation is reported
- **WHEN** a piece is translated into a wall or an occupied cell
- **THEN** the operation reports the move as blocked and returns no moved piece

### Requirement: Soft drop
The system SHALL provide a soft-drop operation that, given a Board and a Piece, returns a Piece moved straight down to its resting position — the lowest position reachable by repeated downward unit translation, where a further downward translation would be blocked.

#### Scenario: Soft drop rests on the floor
- **WHEN** a piece on an empty board is soft-dropped
- **THEN** the returned piece sits on the bottom of the board and cannot translate down further

#### Scenario: Soft drop rests on existing blocks
- **WHEN** a piece is soft-dropped above a stack of filled cells
- **THEN** the returned piece rests directly on top of the highest blocking cell in its columns

### Requirement: Kick-aware rotation
The system SHALL provide a rotation operation that, given a Board, a Piece, and a direction (`CW`, `CCW`, or `FLIP`), computes the target rotation index and tries the active rotation system's kick test offsets for that transition in order. The first offset that yields a placement satisfying `can_place` SHALL be applied; the operation SHALL report whether a non-`(0, 0)` kick offset was used. If no offset yields a valid placement, the rotation SHALL be reported as failed and the piece SHALL be unchanged.

#### Scenario: Rotation in open space uses no kick
- **WHEN** a piece on an empty board is rotated CW with room to rotate
- **THEN** a rotated piece is returned and no kick is reported as used

#### Scenario: Rotation against an obstruction applies a kick
- **WHEN** a piece is rotated such that the in-place rotation is blocked but a later kick offset fits
- **THEN** the rotated, kicked piece is returned and a kick is reported as used

#### Scenario: Impossible rotation fails
- **WHEN** a piece is rotated such that no kick offset yields a valid placement
- **THEN** the rotation is reported as failed and no rotated piece is returned

#### Scenario: O-piece rotates in place
- **WHEN** an O-piece is rotated in any direction on an empty board
- **THEN** the rotation succeeds with no kick used (the O-piece kick list is empty)

### Requirement: Immobility test
The system SHALL provide an immobility test that returns true if and only if a Piece, at its current position, cannot be moved by one cell in any of the four directions — up (row + 1), down (row − 1), left (col − 1), or right (col + 1) — because each such translation would be blocked or out of bounds.

#### Scenario: Floating piece is mobile
- **WHEN** the immobility test is applied to a piece in open space on an empty board
- **THEN** the result is false

#### Scenario: Fully enclosed piece is immobile
- **WHEN** the immobility test is applied to a piece whose every one-cell translation is blocked
- **THEN** the result is true

### Requirement: T-corner count
The system SHALL provide a T-corner count that, for a T-piece, determines the T's center cell (the T cell adjacent to the other three) and counts how many of the four diagonal positions `(center_row ± 1, center_col ± 1)` are filled, where a position counts as filled if it is out of board bounds OR occupied by a non-EMPTY cell.

#### Scenario: T in open space has zero filled corners
- **WHEN** the T-corner count is taken for a T-piece resting on an empty board floor with no adjacent blocks above
- **THEN** the count reflects only out-of-bounds positions, if any, and unfilled in-bounds corners are not counted

#### Scenario: Out-of-bounds corners count as filled
- **WHEN** the T-corner count is taken for a T-piece positioned so that diagonal corners fall outside the board
- **THEN** those out-of-bounds corners are counted as filled

### Requirement: Spin classification
The system SHALL classify the spin of a Piece at its resting position given whether the last action before resting was a rotation, returning a `SpinType`:

- If the last action was NOT a rotation, the result SHALL be `NONE`.
- For a T-piece whose last action was a rotation: if at least 3 of its 4 diagonal corners are filled, the result SHALL be `FULL` when the piece is immobile and `MINI` otherwise; if fewer than 3 corners are filled, the result SHALL be `NONE`.
- For any non-T piece whose last action was a rotation: the result SHALL be `FULL` when the piece is immobile and `NONE` otherwise.

#### Scenario: No spin without a preceding rotation
- **WHEN** a piece reaches its resting position and the last action was a translation or drop
- **THEN** the classification is `NONE` regardless of corners or immobility

#### Scenario: T-spin mini from three corners
- **WHEN** a T-piece's last action is a rotation, at least 3 corners are filled, and the piece is NOT immobile
- **THEN** the classification is `MINI`

#### Scenario: T-spin full from three corners and immobility
- **WHEN** a T-piece's last action is a rotation, at least 3 corners are filled, and the piece IS immobile
- **THEN** the classification is `FULL`

#### Scenario: T with fewer than three corners is not a spin
- **WHEN** a T-piece's last action is a rotation but fewer than 3 corners are filled
- **THEN** the classification is `NONE`

#### Scenario: Non-T spin requires only immobility
- **WHEN** a non-T piece's last action is a rotation and the piece is immobile
- **THEN** the classification is `FULL`

#### Scenario: Mobile non-T rotation is not a spin
- **WHEN** a non-T piece's last action is a rotation but the piece is NOT immobile
- **THEN** the classification is `NONE`

### Requirement: Reachable placement enumeration
The system SHALL provide a `reachable(board, piece_type, system=None, *, allow_flip=False, spawn=None)` operation that returns every distinct resting placement reachable from the spawn state by a breadth-first exploration of translations, soft drops, and rotations. Exploration SHALL track visited `(rotation, row, col)` states to terminate. `FLIP` transitions SHALL be explored only when `allow_flip` is true. A reached state SHALL be emitted as a candidate placement when a downward translation from it is blocked (it is resting). Each emitted placement SHALL carry the spin classification computed from whether the move that produced that resting state was a rotation, and a `path` of moves from spawn that reaches it. Results SHALL be deduplicated by the absolute set of locked cells; when duplicates differ in spin, the highest-ranked `SpinType` SHALL be retained. Each placement's `lines_cleared` SHALL equal the number of lines that would clear if the piece were locked.

#### Scenario: Enumerate placements on an empty board
- **WHEN** `reachable` is called for any piece type on an empty board
- **THEN** a non-empty list of `Placement` values is returned, each resting on the floor, and every placement is reachable via its recorded `path`

#### Scenario: Distinct placements are deduplicated by locked cells
- **WHEN** `reachable` enumerates a piece whose different rotation/origin states occupy the same absolute cells
- **THEN** those states yield a single `Placement`, not duplicates

#### Scenario: A spin placement is discovered with its classification
- **WHEN** `reachable` is run on a board containing a T-slot reachable only by rotating into it
- **THEN** the placement filling that slot is present with `spin` equal to `MINI` or `FULL` per the classification rules

#### Scenario: Spin classification reflects the best reaching path
- **WHEN** a resting placement is reachable both by a plain drop and by a qualifying rotation
- **THEN** the single deduplicated placement carries the higher-ranked `SpinType`

#### Scenario: Unreachable positions are excluded
- **WHEN** a position fits the piece (cells empty) but no sequence of moves from spawn can maneuver the piece into it
- **THEN** that position does NOT appear in the returned placements
