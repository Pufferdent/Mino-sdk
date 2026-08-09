# TETR.IO gravity, per mode

Status of reverse-engineering TETR.IO's gravity model for `add-replay-simulate`.
For built-in modes, gravity is supplied by the mode at runtime; some modes write
the driving parameters into `replay.options`, others leave it implicit. Engine
runs at **60 fps**; gravity in **G** (1G = 1 cell/tick, cap 20G). Default lock:
`locktime = 30` frames (= 500 ms), `lockresets = 15`.

**2026-07-03: everything below is now SOLVED from the official client bundle**
`https://tetr.io/js/tetrio.js` (~2.5MB; fetches directly with a browser UA).
Despite the earlier "obfuscated, don't reverse" note, the mode configs are plain
text inside it: a `gameModes:{"40l":…,blitz:…}` block, the engine `OptionsList`
defaults (`g=0.02, gincrease=0, gmargin=0, gravitymay20g=true, locktime=30,
lockresets=15`), embedded room-preset strings, and the Zenith class's static
tables. The vendored triangle.js (`mino_sdk/replay/teto/…/splice.js`) uses
the same source. **Exact ramp semantics** (from the per-frame update): each
frame with `frame > gmargin`, `g += gincrease/60` — i.e. `gincrease` is G
gained per second, starting after `gmargin` frames.

Implemented in `mino_sdk/sim/gravity.py` (profiles, time ramp, Zenith
tables); `gravity_for()` additionally overlays `g/gincrease/gmargin/locktime/
lockresets` when a replay's own options carry them.

## Status table

| Mode | Driver | Status |
|------|--------|--------|
| Tetra League (versus) | time (margin ramp) | **SOLVED** — `g=0.02, gincrease=0.0035, gmargin=7200` (bundle preset; the old `0.0025/3600` figures are the *default custom room* preset) |
| 40 LINES (Sprint) | constant | **SOLVED** — mode sets `g=0.02` only; defaults ⇒ no ramp, constant 0.02G |
| **Blitz** | **level ← line clears** | **SOLVED** (formula derived + validated; bundle confirms `levelspeed=.42, levelgbase=.65, gravitymay20g=false`) |
| Quick Play (Zenith), no mods | time ramp only | **SOLVED** — `g=0.02` (default) `+ 0.0005/s`, no margin; **no per-floor gravity** (the wiki's per-floor table is the gravity mod). Floor-up sets `glock=240`: gravity suppressed, easing back as `(1−glock/180)²·g` over the last 180 frames |
| Quick Play — gravity mod | floor ← altitude | **SOLVED** — on reaching floor a: `g += GravityBumps[a]`, `locktime = GLockDelay[a]` (tables below) |
| Quick Play — freefall mod (`gravity_reversed`) | floor ← altitude | **SOLVED** — `g=20`, `locktime = GRLockDelay[a]` |

Zenith class statics (bundle; index 0 unused, floors 1–10):

```
FloorDistance = [0,50,150,300,450,650,850,1100,1350,1650,∞]
GravityBumps  = [0,.48,.3,.3,.3,.3,.3,.3,.3,.3,.3]     (gravity mod only)
GLockDelay    = [0,30,29,28,27,26,24,22,20,18,16]      (gravity mod)
GRLockDelay   = [0,24,22,20,18,16,15,14,13,12,11]      (freefall mod)
```

Independent confirmation + climb-speed model (Propeller Levels, height release
10%/frame capped 10m): the CN community QP2 doc — GitHub user `MrZ626`, repo
`modern_<game>_cn_community`, file `io_qp2_rule/full.md`.

---

## Blitz — SOLVED

Replay `cf4f62a670db.ttr` (`gamemode: blitz`). Options carry the drivers:
`levelgbase = 0.65`, `levelspeed = 0.42`, `levels = true`, `gravitymay20g = false`.

**Level ← line clears.** Lines needed to advance level L→L+1 = `2L+1` (3, 5, 7,
9, …). Cumulative lines to *reach* level L = `L² − 1`. Documented anomaly: the
L11→L12 step costs +3 (24, not 23).
Cross-check vs replay: final `level=11`, `lines=126`, `level_lines=6`,
`level_lines_needed=24`. `reach(L11) = 11²−1 = 120`; `126 − 120 = 6` ✓ and the
24 anomaly ✓.

**Gravity ← level** (classic guideline marathon curve, parameterized):

    sec_per_row(L) = (levelgbase − (levelspeed/60)·(L−1)) ^ (L−1)
    G(L)           = min(20, 1 / (60 · sec_per_row(L)))

with `levelgbase = 0.65`, `levelspeed = 0.42` → per-level decrement
`levelspeed/60 = 0.007` (the classic guideline constant). Validated against the
full wiki level table, all 15 rows to 3 sig figs:

| L | sec/row | G | | L | sec/row | G |
|---|---------|-----|---|---|---------|-----|
| 1 | 1.0 | 0.0167 | | 9 | 0.0155 | 1.08 |
| 2 | 0.643 | 0.0259 | | 10 | 0.00827 | 2.01 |
| 3 | 0.404 | 0.0412 | | 11 | 0.00431 | 3.87 |
| 4 | 0.249 | 0.0670 | | 12 | 0.00219 | 7.62 |
| 5 | 0.150 | 0.111 | | 13 | 0.00108 | 15.4 |
| 6 | 0.0880 | 0.189 | | 14 | 0.00052 | 20 (cap) |
| 7 | 0.0505 | 0.330 | | 15 | 0.00024 | 20 (cap) |
| 8 | 0.0283 | 0.588 | | | | |

(`gravitymay20g=false` → the 20G cap applies, as seen at L14–15.)

---

## Quick Play (Zenith) — floor structure CONFIRMED (gravity since solved; see status table)

Replay `3e1f75007df9.ttr` (`gamemode: zenith`, `zenith_mods: []` → no mods).
Zenith does NOT use levels (`level` stays 1); gravity is driven by **floor**,
which is driven by **altitude** (you climb passively + on line sends).

Relevant options: `gincrease = 0.0005`, `garbagemargin = 720000000` (≈ off),
`TEMP_zenith_grace = [0, 3.8, 3.0, 2.3, 1.7, 1.2, 0.8, 0.5, 0.5, 0.5, 0.2]`
(11 entries, decreasing — a per-floor grace, exact meaning unconfirmed),
`fullinterval = 3324`, `fulloffset = 332`.

**Floor ← altitude (CONFIRMED against the replay).** The 10-floor / altitude
table:

| Floor | Name | Altitude |
|-------|------|----------|
| 1 | Hall of Beginnings | 0–50 m |
| 2 | The Hotel | 50–150 m |
| 3 | The Casino | 150–300 m |
| 4 | The Arena | 300–450 m |
| 5 | The Museum | 450–650 m |
| 6 | Abandoned Offices | 650–850 m |
| 7 | The Laboratory | 850–1100 m |
| 8 | The Core | 1100–1350 m |
| 9 | Corruption | 1350–1650 m |
| 10 | Platform of the Gods | 1650 m+ |

Replay `results.zenith`: `altitude = 1404.75 m`, `floor = 9` — and 1404.75 sits
in the floor-9 band (1350–1650) ✓. Per-floor reach times are in
`results.zenith.splits = [25983, 57633, 86583, 112917, 159883, 237767, 313805,
344333, 0]` ms (reached floor 9 at 344.3 s; died at `finaltime=364200`; floor 10
never reached → trailing 0).

**Gravity-per-floor: RESOLVED (2026-07-03).** The suspected conflation was
real: the "floor 1 = 0.48G, +0.30G/floor" wiki table is the **gravity mod**,
not normal Zenith. Unmodded Zenith gravity never depends on floor — it is the
plain time ramp `g + gincrease·t` (this replay's options: `gincrease=0.0005`),
plus the `glock=240` floor-up grace. `TEMP_zenith_grace` turned out to feed
`_targetingGrace` (garbage targeting), not gravity.

---

## Quick Play mods — SOLVED (tables in status section)

- **Gravity mod (`zenith_gravity`)**: on reaching floor a, `g +=
  GravityBumps[a]` and `locktime = GLockDelay[a]`.
- **Freefall mod (`gravity_reversed`)**: `g = 20`, `locktime = GRLockDelay[a]`.

---

## Tetra League (versus) — SOLVED

Bundle preset (verbatim in `tetr.io/js/tetrio.js`, both current and "season 1"
presets): `g=0.02`, `gincrease=0.0035/s`, `gmargin=7200f (2 min)`,
`locktime=30f`, `lockresets=15`. So `g(t) = 0.02 + 0.0035·max(0, (t−7200)/60)`.
The previously recorded `0.0025/3600` belongs to the **default custom room**
preset, not TL. (`locktime` 30f = 500 ms cross-checks the community wiki figure.)

## Remaining threads

1. The simulator does not yet model Zenith's `glock=240` floor-up gravity
   grace, or altitude/floor progression (needs the climb-speed model — see the
   CN QP2 doc linked above) — only relevant for mod replays or long
   low-interaction stretches.
2. A gravity-mod or freefall replay would let us validate the mod tables
   end-to-end against real inputs.
