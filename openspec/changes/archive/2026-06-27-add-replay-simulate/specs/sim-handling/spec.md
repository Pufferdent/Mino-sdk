# Simulation Handling

## ADDED Requirements

### Requirement: Handling model
The system SHALL provide a handling state machine that consumes `InputEvent` press/release events over frames and, using a `Handling` configuration (`das`, `arr`, `sdf`, `dcd`), reports the discrete horizontal cell movement and soft-drop applied on each frame.

#### Scenario: A tap moves one cell
- **WHEN** a left press and release occur within the DAS window
- **THEN** the handling reports exactly one cell of leftward movement

#### Scenario: A held key auto-shifts after DAS
- **WHEN** a left press is held beyond the DAS window
- **THEN** after DAS the handling reports repeated leftward movement at the ARR rate

#### Scenario: ARR zero shifts to the wall instantly
- **WHEN** a direction is held past DAS with `arr == 0`
- **THEN** the handling reports movement to the furthest reachable cell in a single frame

#### Scenario: Soft drop uses SDF
- **WHEN** soft drop is held
- **THEN** the handling reports downward movement scaled by `sdf` (an effectively infinite `sdf` drops to the resting row)
