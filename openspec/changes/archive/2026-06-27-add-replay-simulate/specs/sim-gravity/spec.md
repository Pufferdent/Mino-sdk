# Simulation Gravity

## ADDED Requirements

### Requirement: Gravity profile
The system SHALL provide a `GravityProfile` value describing a mode's downward behavior: cell gravity `g` (cells per frame, or a level→g ramp), `lock_delay` (frames before a grounded piece locks), `lock_resets` (maximum lock-delay resets from movement/rotation), and an `is_20g` flag (the piece reaches the bottom immediately).

#### Scenario: Profile exposes gravity and lock behavior
- **WHEN** a `GravityProfile` is constructed
- **THEN** it exposes `g`, `lock_delay`, `lock_resets`, and `is_20g`

### Requirement: Per-mode gravity registry
The system SHALL provide a registry of gravity profiles keyed by `(platform, gamemode)` and a `gravity_for(meta)` lookup, since gravity is not stored in replays and differs by mode. The registry SHALL include at least TETR.IO `40l` (Sprint) and a Jstris sprint profile. `gravity_for` SHALL fall back to a documented default and signal the fallback when a mode is unknown. A caller SHALL be able to override the looked-up profile with an explicit `GravityProfile`.

#### Scenario: Known mode resolves to its profile
- **WHEN** `gravity_for` is called with a `ReplayMeta` whose platform is TETR.IO and gamemode is `40l`
- **THEN** the registered Sprint profile is returned

#### Scenario: Unknown mode falls back and signals
- **WHEN** `gravity_for` is called with an unregistered `(platform, gamemode)`
- **THEN** a documented default profile is returned and the fallback is signalled

#### Scenario: Explicit override is honored
- **WHEN** the simulator is given an explicit `GravityProfile`
- **THEN** that profile is used instead of the registry lookup

### Requirement: Gravity application and locking
Applied gravity SHALL move the active piece downward by `g` cells per frame (snapping to the resting row when `is_20g`), and a grounded piece SHALL lock after `lock_delay` frames, with the lock timer reset up to `lock_resets` times by successful movement or rotation.

#### Scenario: 20G snaps to the bottom
- **WHEN** a piece is spawned or moved under a `is_20g` profile
- **THEN** it rests on the stack/floor in the same frame

#### Scenario: Lock delay defers locking
- **WHEN** a piece becomes grounded under a non-20G profile with a positive `lock_delay`
- **THEN** it does not lock until `lock_delay` frames pass without a successful reset
