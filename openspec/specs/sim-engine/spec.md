# Simulation Frame Engine

## Purpose

The per-frame live-play loop that integrates queue, hold, handling, gravity,
rotation, and locking. It holds the mutable `GameState` and advances play one
frame at a time, reusing the move engine's kick-aware rotation and the board's
locking/event accounting.

## Requirements

### Requirement: Game state
The system SHALL provide a `GameState` holding the `Board`, the `Queue`, the `Hold`, the active `Piece`, and the current frame, representing a single-player game in progress.

#### Scenario: Game state is constructible from queue and board
- **WHEN** a `GameState` is created with a board, queue, and hold
- **THEN** it spawns the first piece from the queue as the active piece

### Requirement: Frame stepping
The system SHALL provide a frame-stepping function that, given a `GameState`, the frame's handling-derived motion, and a `GravityProfile`, applies movement, rotation (via the move engine's kick-aware `rotate`), hold, soft drop, gravity, and locking, advancing the active piece and queue. Locking SHALL use `Board.lock(piece, spin)` where the spin is computed via `classify_spin` from whether the last successful action was a rotation, producing an `Event`. Top-out SHALL be detected when a newly spawned piece cannot be placed.

#### Scenario: Hard drop locks and yields an event
- **WHEN** a frame applies a hard drop to the active piece
- **THEN** the piece locks at its resting position and an `Event` is produced

#### Scenario: A rotation into a spin is classified at lock
- **WHEN** the last successful action before a lock is a rotation that leaves a T immobile with three corners
- **THEN** the produced `Event` reflects a T-spin

#### Scenario: Spawning into a full board tops out
- **WHEN** the next piece cannot be placed at spawn
- **THEN** the engine reports a top-out
