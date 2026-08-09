# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Run the test suite (always pass the tests/ dir — the repo root also contains
# archive/native_solver/ tests for deleted code that will fail)
.venv/bin/python -m pytest tests -q

# Run a single test file / test
.venv/bin/python -m pytest tests/test_opener.py -q
.venv/bin/python -m pytest tests/test_pc.py -k pattern -q

# One-time setup (Homebrew Python is externally managed, so use the venv)
python3 -m venv .venv && .venv/bin/pip install pytest lzstring
```

There is no linter or build step. Java must be on PATH for anything that shells out to `reference/sfinder.jar` (set `SFINDER_JAR` or pass `jar_path`).

## Hard rule: no native solving of perfect clears

Genuine perfect-clear search is delegated to knewjade's `sfinder.jar` (`reference/sfinder.jar`) via the thin subprocess wrapper in `mino_sdk/pc/sfinder.py`; a native Python PC solver was tried, was ~100x slower, and was removed (its corpse and failing tests live in `archive/native_solver/` — do not resurrect it or run its tests). The rule applies **only to perfect clears**: other search problems — opener lines, region tilings, reachability, queue coverage — are solved natively (see `mino_sdk/opener/tiles.py`), and sfinder's PC encoding is provably wrong for opener lines.

## Architecture

`mino_sdk/` is a layered library; everything below builds on the core:

- **Core** — `types` (Cell), `board` (10-wide Board), `pieces` (PieceType, SRS / SRS+ kick tables), `engine` (BFS `reachable`, spin classification via the immobile rule, `instant=True` mode where soft drop teleports), `events` (lock classification, `B2BRule` incl. S2 all-spin).
- **`fumen/`** — encoder/decoder/parser for fumen strings (the interchange format used everywhere; boards are routinely round-tripped through fumens).
- **`replay/`** — TETR.IO (`.ttr`) and Jstris replay decoding plus `simulate` to re-play inputs through the engine.
- **`sim/`** — game-loop pieces: platform RNGs, queue/hold, gravity profiles, handling (DAS/ARR), sim engine.
- **`pc/`** — perfect-clear tooling: `sfinder` wrapper, `leftover` (PC-number/bag arithmetic), `queue_pattern`, `segment` (split a replay fumen into per-PC snapshots), `saves`.
- **`opener/`** — the opener-research layer (see below).
- **`solver/`** — `compute_topological_orderings`: all placement orders consistent with gravity for a set of operations.

### The opener package and the Solver seam

`opener/` describes opener diagrams as data; the search algorithm is deliberately absent:

- `Node` — a graph key: canonical (color-normalized) fumen + remaining queue. Queue spans at most 2 bags; multiplicity encodes the bag split. Hold is modeled as "the held piece is queue index 0; placing index 1 *is* holding".
- `Bridge` — one line between two nodes across a whole bag. Clear count comes free from the mino tally (`(start + 4·pieces − end) / 10`; non-integer ⇒ impossible). A bridge reduces to a PC problem (complement-of-end field) for sfinder, then orderings are replayed in the real frame with `engine.reachable`.
- `constraints.py` — `Constraint` protocol (`allows` on finished routes, `prune` on prefixes): `KeepB2B`, `Spin`, `Saves`, `NoGravityWait`, `Clears`. Prune implementations are what keep search tractable.
- `hold.py` — which *queues* (not orderings) can produce a route; coverage counts queues. Forks: `any_odds`/`any_chance` (in `bridge.py`) give the union chance that at least one of several same-leftover bridges is playable.
- `diagram.py` — `Diagram.board()/.line()/.chances()` for linear chains, plus the graph optimizer for forked diagrams: `optimize(start, score)` maximizes expected user-defined score under optimal per-queue play (scorer SPI: any callable judging a `Route`); `chance_to(start, target)` is the probability special case; `explain()` breaks down every `(board, leftover)` state. Saves are grouped per `(score, saved)`, DAG only.
- `solver.py` — the `Solver` protocol (`solve(bridge, cap) -> list[Route]`). The shipped implementation is `tiles.TileSolver`, used by default when no solver is passed.
- `tiles.py` — the shipped solver: *lifted exact cover proposes, real-frame replay disposes*. Supporting modules: `lifted.py` (re-insert cleared rows so a mid-clear line becomes a static region; every placement of the cleared rows is a "frame"), `tiling.py` (exact cover of the region, including **stretched** footprints for pieces that straddle an already-cleared row — required for exactness), `fastreach.py` (bitboard BFS reachability with kicks, tucks, spins, and 180s when the system has them; `test_fastreach.py` pins it to `engine.reachable` under both SRS and SRS+). The rotation system defaults to TETR.IO's SRS+ and is configurable per `Bridge`/`Diagram` (`system=SRS()`). A full-bag bridge evaluates in about a second.

**Read `OPENER_SEARCH_NOTES.md` before touching opener/solver work.** The top section describes the shipped solver and its verification; below it are hard-won, easy-to-rederive-wrongly results: the mino tally, why the complement-as-garbage encoding is wrong when few lines clear, why sfinder's raw solution counts over-report (disconnected pieces / fake mid-clears), the even-T checkerboard parity theorem and exactly where it stops holding, and performance measurements showing unrestricted forward search doesn't scale.

### Conventions worth knowing

- Canonical piece order is `T I L J S Z O` (PCReview's ordering) — used for sorting pools, saves, and patterns.
- Two row conventions exist: fumen rows (top-down) vs board rows; `coords.py` converts. `get_piece_cells` takes a `coord_system` argument.
- Execution cost model: with instant soft drop, tucks and spins are free; the only expensive placement is a `gravity_wait` (piece must be halted partway down).
- sfinder pattern syntax appears throughout (`*p7`, `[TILO]p4`); `Node.pattern()` and `Bridge.pattern()` generate it.

## OpenSpec workflow

The repo uses OpenSpec (`openspec/specs/` holds per-capability specs; changes go through proposals). Use the `openspec-propose` / `openspec-apply-change` / `openspec-archive-change` / `openspec-sync-specs` / `openspec-explore` skills for spec-driven changes.
