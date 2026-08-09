# Events

## ADDED Requirements

### Requirement: Event kinds
The system SHALL provide an `EventKind` enum with members `PLACEMENT` (a lock that cleared no lines and was not a spin), `SPIN` (a spin that cleared no lines), and `CLEAR` (a lock that cleared one or more lines). Each lock SHALL produce exactly one event whose kind is determined by `(lines, spin)`: `lines == 0 and spin == NONE` → `PLACEMENT`; `lines == 0 and spin != NONE` → `SPIN`; `lines >= 1` → `CLEAR`.

#### Scenario: A non-clearing, non-spin lock is a PLACEMENT
- **WHEN** a lock clears 0 lines with `spin == NONE`
- **THEN** the event kind is `PLACEMENT`

#### Scenario: A spin that clears nothing is a SPIN event
- **WHEN** a lock clears 0 lines with a non-NONE spin
- **THEN** the event kind is `SPIN`

#### Scenario: Any line clear is a CLEAR event
- **WHEN** a lock clears one or more lines (with or without a spin)
- **THEN** the event kind is `CLEAR`

### Requirement: Event value type
The system SHALL provide an immutable, hashable `Event` value type carrying: `kind` (EventKind), `piece` (PieceType), `spin` (SpinType), `lines` (int 0–4), `name` (str, derived), `difficult` (bool), `back_to_back` (bool), `b2b` (int running chain length), `combo` (int running combo), and `perfect_clear` (bool).

#### Scenario: Event is hashable and complete
- **WHEN** an `Event` is produced for a lock
- **THEN** it exposes all listed fields, and two events with identical fields compare and hash equal

### Requirement: Event classification and naming
The system SHALL provide a pure classification of `(piece, spin, lines)` into `(kind, name)` without reference to running state. Names SHALL be: `Placement` for a placement; `T-Spin`/`T-Spin Mini`/`<Piece>-Spin` for spin-0 events; `Single`/`Double`/`Triple`/`Quad` for plain line clears by count; `T-Spin Single`/`T-Spin Double`/`T-Spin Triple` for T full-spin clears; `T-Spin Mini Single`/`T-Spin Mini Double` for T mini-spin clears; `<Piece>-Spin <Lines>` for non-T spin clears. A 4-line clear SHALL be named `Quad`.

#### Scenario: Four-line clears are named Quad
- **WHEN** a no-spin 4-line clear is classified
- **THEN** the name is `Quad`

#### Scenario: Plain clears are named by count
- **WHEN** a no-spin clear of 1, 2, or 3 lines is classified
- **THEN** the names are `Single`, `Double`, `Triple` respectively

#### Scenario: T-spin clears are named
- **WHEN** `(T, FULL, 2)` is classified
- **THEN** the name is `T-Spin Double`

#### Scenario: Non-T spin clears are named by piece
- **WHEN** `(S, FULL, 1)` is classified
- **THEN** the name is `S-Spin Single`

#### Scenario: Spin-0 events are named without a line count
- **WHEN** `(T, MINI, 0)` is classified
- **THEN** the name is `T-Spin Mini` and the kind is `SPIN`

### Requirement: Back-to-back rule modes
The system SHALL provide a `B2BRule` enum with members `S1` and `S2` and a difficulty predicate over `(piece, spin, lines, rule)`. A clear of 0 lines SHALL never be difficult. A 4-line clear (Quad) SHALL be difficult under both rules. Under `S1`, a sub-4 clear SHALL be difficult iff the piece is `T` and `spin != NONE`. Under `S2`, a sub-4 clear SHALL be difficult iff `spin != NONE` (any piece).

#### Scenario: Quad is difficult under both rules
- **WHEN** the predicate is evaluated for a 4-line clear under `S1` and under `S2`
- **THEN** both return difficult

#### Scenario: S1 excludes non-T spins
- **WHEN** the predicate is evaluated for an `S`-piece spin single under `S1`
- **THEN** it is NOT difficult

#### Scenario: S2 includes non-T spins
- **WHEN** the predicate is evaluated for an `S`-piece spin single under `S2`
- **THEN** it is difficult

#### Scenario: T-spin clears are difficult under both rules
- **WHEN** the predicate is evaluated for a `T` full-spin double under `S1` and under `S2`
- **THEN** both return difficult

### Requirement: Back-to-back tracking
The board SHALL maintain a running back-to-back chain length and update it on each lock using the active `B2BRule`: a non-clearing lock (PLACEMENT or SPIN) SHALL preserve the chain; a difficult clear SHALL set `back_to_back` true only when a chain was already active and SHALL increment the chain length; a non-difficult clear SHALL reset the chain length to zero and `back_to_back` to false.

#### Scenario: First difficult clear starts but is not yet back-to-back
- **WHEN** a difficult clear occurs with no active chain
- **THEN** the event's `back_to_back` is false and the running `b2b` becomes 1

#### Scenario: Consecutive difficult clears are back-to-back
- **WHEN** a difficult clear occurs while a chain is active
- **THEN** the event's `back_to_back` is true and `b2b` increments

#### Scenario: A non-difficult clear breaks the chain
- **WHEN** a plain Single/Double/Triple occurs while a chain is active
- **THEN** the event's `back_to_back` is false and the running `b2b` resets to 0

#### Scenario: A spin-0 preserves the chain
- **WHEN** a spin that clears 0 lines occurs while a chain is active
- **THEN** the running `b2b` is unchanged and a subsequent difficult clear is back-to-back

### Requirement: Combo tracking
The board SHALL maintain a running combo counter: incremented on each line-clearing lock (CLEAR) and reset to zero on any non-clearing lock (PLACEMENT or SPIN). The combo count after the lock SHALL appear on the event.

#### Scenario: Combo increments across consecutive clears
- **WHEN** two CLEAR locks occur in a row
- **THEN** the combo is 1 after the first and 2 after the second

#### Scenario: A spin-0 resets combo
- **WHEN** a spin that clears 0 lines is locked
- **THEN** the combo is 0 afterward

### Requirement: Perfect clear detection
An event SHALL report `perfect_clear` true if and only if the board contains no filled cells after the lock's line clears.

#### Scenario: Emptying the board is a perfect clear
- **WHEN** a lock clears the only remaining filled rows, leaving the board empty
- **THEN** the event's `perfect_clear` is true

#### Scenario: Residual blocks are not a perfect clear
- **WHEN** a lock clears lines but leaves at least one filled cell
- **THEN** the event's `perfect_clear` is false
