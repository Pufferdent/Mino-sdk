# Simulation Queue & RNG

## ADDED Requirements

### Requirement: Per-platform seeded RNG
The system SHALL provide an `Rng` protocol and two implementations, `TetrioRng` and `JstrisRng`, each constructed from a replay seed and producing a deterministic stream that reproduces its platform's piece order. Identical seeds SHALL produce identical streams.

#### Scenario: RNG is deterministic from a seed
- **WHEN** two `TetrioRng` instances are created with the same seed
- **THEN** they produce identical value streams

#### Scenario: Platforms use distinct generators
- **WHEN** `TetrioRng` and `JstrisRng` are created from comparable seeds
- **THEN** they are distinct types producing platform-appropriate sequences

### Requirement: Seven-bag piece sequence
The system SHALL provide a `Queue` that draws an infinite piece sequence as 7-bags shuffled by an `Rng`, exposes the next piece, and supports peeking a preview window.

#### Scenario: Each bag contains all seven pieces
- **WHEN** the first seven pieces are drawn from a `Queue`
- **THEN** they are a permutation of the seven `PieceType`s

#### Scenario: Preview reflects upcoming pieces
- **WHEN** `peek(n)` is called and then `n` pieces are drawn
- **THEN** the drawn pieces equal the previewed pieces in order

### Requirement: Hold slot
The system SHALL provide a `Hold` supporting a single held piece with once-per-piece swap semantics that reset after a lock.

#### Scenario: First hold stores the active piece
- **WHEN** hold is used while the slot is empty
- **THEN** the active piece is stored and the next queue piece becomes active

#### Scenario: Hold cannot be reused before a lock
- **WHEN** hold is used twice without a lock in between
- **THEN** the second use is rejected
