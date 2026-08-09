# Analysis: Techmino (26f-studio/Techmino)

**What it is:** An open-source, cross-platform block-puzzle game ("方块研究所" / "Block Institute") that aggregates many modern stacker rule-sets into one engine. Written in **Lua on the LÖVE 2D framework**, LGPL-3.0, very actively developed (5,000+ commits, 36+ releases). Targets Windows, macOS, Linux (AppImage), Android, and iOS.

## Why it's interesting as a reference

Techmino is a **full, faithful re-implementation of guideline-and-beyond stacker mechanics in readable scripting code**. Unlike a binary client (TETR.IO) or a search tool (sfinder), the *entire game logic is open Lua source* — making it a primary reference for *how a complete modern stacker is actually built*, including the parts an SDK usually has to reverse-engineer.

## Architecture (LÖVE / Lua)

```
main.lua / conf.lua        ← LÖVE entry + config
Zframework/                ← custom engine layer (scenes, input,
                             rendering, tweening, widgets, net)
parts/                     ← game logic + systems
  ├─ RSlist.lua    (42KB)  ← rotation systems + kick tables (multiple!)
  ├─ gameFuncs.lua (41KB)  ← core gameplay: spawn, lock, clear,
  │                          gravity, attack, scoring
  ├─ gameTables.lua(22KB)  ← constants/data tables (delays, scores)
  ├─ modes.lua     (11KB)  ← game-mode definitions
  ├─ net.lua/netPlayer.lua ← multiplayer / netcode
  ├─ bot/                  ← built-in AI/bot
  ├─ eventsets/            ← scripted event/rule configurations
  ├─ modes/, player/, scenes/, shaders/, language/
  └─ virtualKey, theme, skin, data, discordRPC, ...
```

### Standout: `RSlist.lua` (rotation systems)
A single large table-driven module defining **multiple rotation systems** (SRS, plus variants/alternatives), each with its own kick tables. This is the opposite of sfinder's SRS-only hardcoding — Techmino treats the rotation system as *data*, swappable per mode. Strong reference for designing a `RotationSystem` abstraction.

### `gameFuncs.lua` — the engine core
Holds the per-frame simulation: piece spawning (bag/RNG), gravity & soft/hard drop, lock delay, line clear detection, spin detection, attack/garbage computation, combo/B2B, and scoring. This is the equivalent of sfinder's `core/` but covering *live play* rather than static analysis.

### Mode/event system
`modes.lua` + `eventsets/` + `parts/modes/` make game rules **declarative and scriptable** — Sprint, Marathon, Blitz, challenge/puzzle modes, etc., are configurations layered over the same engine. This is effectively a modding surface.

## Relevance to this SDK

- **Reference for live-game mechanics** the SDK's static board model doesn't yet cover: gravity, lock delay, DAS/ARR input timing, garbage/attack tables, B2B/combo scoring, spin bonus rules.
- **Rotation-system-as-data** (`RSlist.lua`) validates designing `RotationSystem` (already in `mino_sdk/pieces.py`) as a pluggable table rather than hardcoded SRS — and gives concrete kick tables for systems beyond SRS.
- **Mode/eventset pattern** is a model for declaratively defining rule variants if the SDK grows beyond a single ruleset.
- **License caveat:** LGPL-3.0 — fine to *study* and re-derive mechanics, but copying Lua source/data tables verbatim into the SDK carries copyleft obligations. Use as a *specification reference*, not a source to vendor.

**Limitations as a reference:** Lua-specific idioms and tight coupling to LÖVE rendering/scene code mean logic must be extracted by reading, not imported. No formal spec — the source *is* the spec. Some mechanics are bespoke to Techmino rather than guideline-standard, so cross-check against TETR.IO/sfinder behavior before treating any detail as canonical.
