# Replay Simulate

## Purpose

The driver that reconstructs gameplay from a decoded `Replay`: it runs the replay
through the simulation stack (seeded RNG → queue/hold, handling, gravity, frame
engine) and produces a `ReplaySim` with placements, per-lock events, board
snapshots, and a validation report against the replay's own recorded results.

## Requirements

### Requirement: Replay reconstruction
The system SHALL provide `simulate(replay, *, gravity=None, engine="native")` that runs a decoded `Replay` through the frame engine — building the piece sequence from `meta.seed`, applying `meta.handling`, and resolving gravity via the registry (or an explicit `gravity` override) — and produces a `ReplaySim` containing the ordered reconstructed placements, the per-lock `Event`s, and board snapshots. The `engine` selector SHALL choose the native engine by default and allow a `"teto"` fallback boundary for TETR.IO without changing the driver interface.

#### Scenario: Simulating a replay yields ordered placements and events
- **WHEN** `simulate` is called on a decoded replay
- **THEN** it returns a `ReplaySim` whose placements and `Event`s are ordered by lock

#### Scenario: Explicit gravity override is used
- **WHEN** `simulate` is called with an explicit `gravity` profile
- **THEN** that profile is used instead of the registry lookup

### Requirement: Validation against replay results
When `meta.results` is present, `simulate` SHALL produce a validation report comparing reconstructed aggregates — pieces placed, lines cleared, back-to-back, T-spins, and perfect clears — against the replay's recorded results.

#### Scenario: Reconstruction matches recorded stats
- **WHEN** a TETR.IO Sprint replay with `results` is simulated
- **THEN** the validation report reports the reconstructed pieces-placed and lines equal to the recorded values

#### Scenario: Mismatch is reported per field
- **WHEN** a reconstruction diverges from the recorded results
- **THEN** the validation report identifies which aggregate fields differ
