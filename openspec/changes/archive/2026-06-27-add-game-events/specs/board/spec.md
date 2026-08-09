# Board

## ADDED Requirements

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
