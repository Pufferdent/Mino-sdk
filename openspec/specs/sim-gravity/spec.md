# Simulation Gravity

## Purpose

Resolve a mode's downward behavior, which replays do not store and which differs
by game mode. Provides the `GravityProfile` value, a registry keyed by
`(platform, gamemode)` with a `gravity_for` lookup, and the application rules for
gravity, 20G, and lock delay.

## Requirements

### Requirement: Gravity profile
The system SHALL provide a `GravityProfile` value describing a mode's downward behavior: cell gravity `g` (cells per frame, or a level→g ramp), a time ramp (`gincrease` in G per second and `gmargin` in frames — past `gmargin`, effective gravity grows by `gincrease/60` per frame, matching the TETR.IO client), `lock_delay` (frames before a grounded piece locks), `lock_resets` (maximum lock-delay resets from movement/rotation), and an `is_20g` flag (the piece reaches the bottom immediately). Effective gravity SHALL be computable via `gravity_at(lines, frame)` and SHALL be capped at 20G.

#### Scenario: Profile exposes gravity and lock behavior
- **WHEN** a `GravityProfile` is constructed
- **THEN** it exposes `g`, `gincrease`, `gmargin`, `lock_delay`, `lock_resets`, and `is_20g`

#### Scenario: Time ramp starts after the margin
- **WHEN** `gravity_at` is queried for a profile with `gincrease > 0` at frames at, before, and one second past `gmargin`
- **THEN** gravity equals `g` up to `gmargin` and `g + gincrease` one second (60 frames) past it

#### Scenario: Ramped gravity caps at 20G
- **WHEN** the time ramp would exceed 20 cells/frame
- **THEN** `gravity_at` returns exactly 20

### Requirement: Per-mode gravity registry
The system SHALL provide a registry of gravity profiles keyed by `(platform, gamemode)` and a `gravity_for(meta)` lookup, since gravity is not stored uniformly in replays and differs by mode. The registry SHALL include at least TETR.IO `40l` (constant 0.02G — confirmed from the official client bundle), TETR.IO `blitz` (level ramp), TETR.IO `league` (`0.02 + 0.0035/s` after 7200 frames), TETR.IO `zenith` (`0.02 + 0.0005/s`, no margin), and a Jstris sprint profile. `gravity_for` SHALL fall back to a documented default when a mode is unknown, SHALL overlay gravity drivers present in the replay's own options (`g`, `gincrease`, `gmargin`, `locktime`, `lockresets`) over the resolved profile, and a caller SHALL be able to override the result with an explicit `GravityProfile`.

#### Scenario: Known mode resolves to its profile
- **WHEN** `gravity_for` is called with a `ReplayMeta` whose platform is TETR.IO and gamemode is `40l`
- **THEN** the registered Sprint profile is returned

#### Scenario: Unknown mode falls back and signals
- **WHEN** `gravity_for` is called with an unregistered `(platform, gamemode)`
- **THEN** a documented default profile is returned and the fallback is signalled

#### Scenario: Replay options override the profile
- **WHEN** the replay's raw options carry numeric `gincrease` and `locktime`
- **THEN** the returned profile uses those values while unspecified fields keep the registry profile's values

#### Scenario: Explicit override is honored
- **WHEN** the simulator is given an explicit `GravityProfile`
- **THEN** that profile is used instead of the registry lookup

### Requirement: Zenith floor data
The system SHALL export the TETR.IO Quick Play floor model as data transcribed from the client: `ZENITH_FLOOR_DISTANCE` (altitude boundaries for floors 1–10), `ZENITH_GRAVITY_BUMPS` and `ZENITH_G_LOCK_DELAY` (gravity-mod per-floor gravity increments and lock delays), `ZENITH_GR_LOCK_DELAY` (freefall-mod per-floor lock delays), and `zenith_floor(altitude)` mirroring the client's `GetFloorLevel`. Unmodded Zenith gravity SHALL NOT vary by floor.

#### Scenario: Floor from altitude
- **WHEN** `zenith_floor` is called with altitudes 0, 50, and 1404.75
- **THEN** it returns floors 1, 2, and 9 respectively

#### Scenario: Mod tables cover all floors
- **WHEN** the mod tables are inspected
- **THEN** each has 11 entries (index 0 padding + floors 1–10) matching the client values

### Requirement: Gravity application and locking
Applied gravity SHALL move the active piece downward by `g` cells per frame (snapping to the resting row when `is_20g`), and a grounded piece SHALL lock after `lock_delay` frames, with the lock timer reset up to `lock_resets` times by successful movement or rotation.

#### Scenario: 20G snaps to the bottom
- **WHEN** a piece is spawned or moved under a `is_20g` profile
- **THEN** it rests on the stack/floor in the same frame

#### Scenario: Lock delay defers locking
- **WHEN** a piece becomes grounded under a non-20G profile with a positive `lock_delay`
- **THEN** it does not lock until `lock_delay` frames pass without a successful reset
