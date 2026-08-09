# Replay Decode

## ADDED Requirements

### Requirement: Normalized replay model
The system SHALL provide a normalized, platform-agnostic replay model: a `Platform` enum (`TETRIO`, `JSTRIS`); a `ReplayInput` enum (`LEFT`, `RIGHT`, `SOFT_DROP`, `HARD_DROP`, `CW`, `CCW`, `FLIP`, `HOLD`); an immutable `InputEvent` carrying `frame` (int), `subframe` (float), `input` (ReplayInput), and `pressed` (bool); a `Handling` value with `das`, `arr`, `sdf`, `dcd`, and an `extras` mapping; a `ReplayMeta` carrying `platform`, `seed`, `gamemode`, `handling`, `allow180`, `spinbonuses`, `version`, `raw_options`, and optional `results`; and a `Replay` carrying `meta` and an ordered tuple of `InputEvent`s.

#### Scenario: Replay exposes meta and ordered inputs
- **WHEN** a `Replay` is produced by any decoder
- **THEN** it exposes a `ReplayMeta` and a tuple of `InputEvent`s ordered by `(frame, subframe)`

#### Scenario: Input events distinguish press and release
- **WHEN** a held key produces a keydown and a later keyup
- **THEN** two `InputEvent`s are produced with `pressed` True then False for the same `input`

### Requirement: TETR.IO decode
The system SHALL decode a TETR.IO `.ttr` JSON object into a `Replay`. Each `replay.events` entry of type `keydown` or `keyup` SHALL become an `InputEvent` whose `input` is the mapping of its `data.key` (`moveLeft→LEFT`, `moveRight→RIGHT`, `softDrop→SOFT_DROP`, `hardDrop→HARD_DROP`, `rotateCW→CW`, `rotateCCW→CCW`, `rotate180→FLIP`, `hold→HOLD`), whose `pressed` is true for `keydown`, and whose `frame`/`subframe` come from the event. `ReplayMeta` SHALL be populated from `replay.options` (seed, handling, allow180, spinbonuses, version), the top-level `gamemode`, and `replay.results` (as `results`). Non-input events SHALL NOT produce `InputEvent`s.

#### Scenario: TETR.IO keys map to normalized inputs
- **WHEN** a TETR.IO replay containing `moveLeft`, `hardDrop`, and `hold` keydowns is decoded
- **THEN** the corresponding `InputEvent`s have inputs `LEFT`, `HARD_DROP`, and `HOLD` with `pressed` true

#### Scenario: TETR.IO metadata is captured
- **WHEN** the TETR.IO fixture is decoded
- **THEN** `meta.platform` is `TETRIO`, `meta.gamemode` is `"40l"`, `meta.seed` is present, `meta.handling.das` matches the source, and `meta.results` is non-null

#### Scenario: Start and end events are not inputs
- **WHEN** a TETR.IO replay containing `start` and `end` events is decoded
- **THEN** no `InputEvent` is produced for those events

### Requirement: Jstris decode
The system SHALL decode a Jstris replay string by LZString-decompressing it to JSON, populating `ReplayMeta` from the `c` config (seed, das, version, mode flags, preserved as `raw_options`), and unpacking the `d` action bitstream into ordered `InputEvent`s.

#### Scenario: Jstris container is decompressed and read
- **WHEN** the Jstris fixture is decoded
- **THEN** `meta.platform` is `JSTRIS`, `meta.seed` equals the `c.seed` value, and `meta.handling.das` equals `c.das`

#### Scenario: Jstris inputs are produced from the action stream
- **WHEN** the Jstris fixture is decoded
- **THEN** a non-empty ordered tuple of `InputEvent`s is produced

### Requirement: Platform auto-detection
The system SHALL provide `decode_replay(data)` that accepts a path, `str`, or `bytes`, detects the platform (TETR.IO JSON with a `replay.events` shape, or a Jstris LZString blob), and dispatches to the matching decoder. Unrecognized input SHALL raise `ValueError`.

#### Scenario: TETR.IO content is auto-detected
- **WHEN** `decode_replay` is given the `.ttr` fixture
- **THEN** it returns a `Replay` with `meta.platform == TETRIO`

#### Scenario: Jstris content is auto-detected
- **WHEN** `decode_replay` is given the Jstris `.txt` fixture
- **THEN** it returns a `Replay` with `meta.platform == JSTRIS`

#### Scenario: Unknown content raises
- **WHEN** `decode_replay` is given data that is neither a TETR.IO replay nor a Jstris blob
- **THEN** a `ValueError` is raised
