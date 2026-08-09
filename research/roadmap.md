# SDK Roadmap — sequencing after the move engine

Living plan for what to build, in what order, and why. Anchored to the layered architecture (see `research/` analyses). Status reflects OpenSpec changes.

## Where we are

| Layer | Capability | Status |
|-------|-----------|--------|
| L1 core | Board, Cell, fumen *reader* | ✅ shipped |
| L1 core | PieceType, RotationSystem, SRS | ✅ shipped |
| L2 engine | move engine: kick rotation, drop, immobile/T-corner, spin, `reachable()`; SRS kick correction + `SRSPlus` | 📝 specced (`add-move-engine`) |
| L3 logic | **one proper board: `lock()` → `Event` (placement/spin-0/clear), quad naming, B2B (S1/S2) + combo** | 📝 specced (`add-game-events`) ⬅ **next to build** |
| L3 logic | queue + hold + (optional) Game/State wrapper | later |
| L3 logic | scoring / attack tables (consumes `ClearResult`) | later (postponed) |
| L4 surfaces | PC solver · Bot env · LST scorer | later (diverge) |
| L5 interop | fumen *writer* · sfinder oracle · render | cheap, parallel |

## The dependency picture

```
        L1 core ─► L2 move engine ─► L3 Game/State ─┬─► PC solver
                          │                          ├─► Bot env (gym)
                          │                          └─► LST scorer
                          │
        fumen writer ◄────┘  (independent, unlocks sfinder oracle + sharing)
        scoring/attack ◄── Game/State events  (swappable rules layer)
```

The L3 logic layer is the **last shared substrate**. Above it, the three personas diverge. We are building it **bottom-up and narrow**: first "one proper board" that classifies clears and tracks B2B (`add-clear-detection`, specced), then queue/hold, then optionally an immutable state wrapper — rather than one big Game/State change. Scoring is postponed and will *consume* `ClearResult`.

---

## Now building: `add-game-events` (one proper board)

A single mutable `Board` you commit placements to. `lock(piece, spin) -> Event` places the piece, clears lines, and returns a classified **`Event`** — where **block placement**, **spin-0** (a spin clearing nothing), and **line clear** are all `EventKind`s. Clear names use **`Quad`** (not the legacy four-line-clear name): `Quad`, `T-Spin Double`, `S-Spin Single`, … Back-to-back is configurable: **`S1`** (TETR.IO Season 1 — only quads + T-spin-with-lines) vs **`S2`** (Season 2 — any line-clearing spin). Combo tracked alongside. No scoring/queue/hold; spin is supplied (from a move-engine `Placement`), not recomputed. See `openspec/changes/add-game-events`.

## Later: `add-game-state` (deferred — when queue/hold/search need it)

### Why now
Every goal operates on *sequences against an evolving state*: a bot steps a game, a solver explores a tree of states, an LST sim stacks piece after piece. None is expressible with single-piece `reachable()` alone. This change adds the object that holds board + queue + hold + active piece and advances it — deterministically.

### What it introduces
- **Queue** — a piece sequence driven by a **7-bag randomizer with a seedable RNG**. Deterministic from a seed ⇒ reproducible research and differential testing. Configurable preview length.
- **Hold** — single hold slot with the standard once-per-piece lock.
- **State / Game** — board + queue + hold + active piece, with:
  - `legal_moves()` → `reachable()` over the active piece **and** the held/next piece (hold-aware enumeration — the deferred item from the move-engine design lands here).
  - `apply(placement)` → places, clears lines, advances the queue/hold, spawns next; returns `(new_state, Events)`.
  - top-out / terminal detection (spawn blocked).
- **Events** — raw, rule-agnostic facts from a placement: `lines_cleared`, `spin: SpinType`, `was_b2b`, `combo`, `perfect_clear`, `topped_out`. *No scoring/attack numbers* — those come later and consume these events.

### Key design decisions to pin in its design.md
- **Immutable core `apply()` vs mutable `step()`.** Search wants cheap immutable states (branch a tree, no undo); bots want a mutable env. → Core is **immutable**: `apply(placement) -> (State, Events)`, `State` frozen/hashable. A thin mutable `Game` wrapper (holds a current `State`, exposes `step()`) serves the env persona without duplicating logic. One owns the truth; the other is ergonomics.
- **Scoring stays out.** `apply()` emits events, not points/attack. Keeps the state core rule-agnostic; the versus/bot math becomes a swappable `add-scoring-attack` change (TETR.IO vs guideline vs custom).
- **Hold-aware `legal_moves()`.** Merge `reachable(active)` with `reachable(hold-or-next)`, tagging each placement with whether it used hold. This is where the move-engine "should reachable include hold?" open question is answered — at the state layer, not the engine.
- **Garbage is deferred but designed-for.** Single-player state now; leave a seam (an incoming-garbage queue + a `receive_garbage` path) so versus/bot training can add it without reshaping `State`.
- **Determinism contract.** Same seed + same placement sequence ⇒ identical state stream. This is a *tested invariant*, not an aspiration — it's what makes the fast backend differentially testable later.

### Non-goals (separate later changes)
- Scoring, B2B/combo *point values*, attack tables, garbage exchange.
- Gravity / lock-delay / DAS-ARR *timing* (state is frame-agnostic; "what's reachable", not "in how many frames").
- The solver, env, and LST surfaces.

---

## Parallel / cheap wins (any time)

- **`add-fumen-writer`** — you decode fumen but can't emit it. Small, independent, and it unlocks (a) sharing results, (b) the **sfinder oracle** for correctness tests, (c) human-inspectable test fixtures. Highest value-per-effort item on the board; can land alongside `add-game-state`.

## After the substrate — the persona surfaces (sketch, not yet specced)

- **PC solver (`add-pc-solver`)** — DFS/BFS over `State` to a perfect clear; pattern DSL (`*p7`) for piece-set queries; **sfinder as the correctness oracle** via fumen while a native solver grows.
- **Bot env (`add-bot-env`)** — Gym-style `reset/step/observation/reward` over the mutable `Game`; feature extraction (heights, holes, bumpiness — cheap with the column-bitboard backend); vectorization for throughput.
- **LST / pattern scorer (`add-lst-scorer`)** — over `reachable()` + spin: enumerate stacking continuations, score efficiency (downstack/upstack, spin yield), detect named patterns.

## Open threads to revisit
- **Performance seam**: still pure-Python. The bot-env change is the one that will demand the bitboard/native backend — that's the natural moment to cash in the "seam for later" decision, validated against the RefEngine + Game-State determinism tests.
- **Scoring convention**: TETR.IO vs guideline vs custom — likely a pluggable table like `RotationSystem`, decided when `add-scoring-attack` is scoped.
