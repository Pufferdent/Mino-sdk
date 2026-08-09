# Tasks: update-gravity-model

## 1. Profile model

- [x] 1.1 Add `gincrease`/`gmargin` fields to `GravityProfile` and make `gravity_at(lines, frame)` apply the closed-form time ramp with the 20G cap
- [x] 1.2 Pass the current frame from the engine's gravity step (`step_frame`)

## 2. Registry and lookup

- [x] 2.1 Add `league` and `zenith` profiles; correct the 40L documentation to the confirmed constant
- [x] 2.2 Overlay replay-option gravity drivers (`g/gincrease/gmargin/locktime/lockresets`, numeric-only) in `gravity_for`

## 3. Zenith data

- [x] 3.1 Export `ZENITH_FLOOR_DISTANCE`, `ZENITH_GRAVITY_BUMPS`, `ZENITH_G_LOCK_DELAY`, `ZENITH_GR_LOCK_DELAY`, and `zenith_floor()`; re-export from `tetris_sdk.sim`

## 4. Tests

- [x] 4.1 Tests for the time ramp (margin start, no-margin, cap), 40L constancy over time, floor-from-altitude, mod-table shape, and options-overlay behavior; full suite green
