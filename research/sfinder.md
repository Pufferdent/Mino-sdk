# Analysis: solution-finder (sfinder.jar)

**What it is:** A Java command-line tool by knewjade for analyzing Tetris fields — the de-facto standard engine for Perfect Clear (PC) theory, setup-finding, and percent calculations. The `sfinder.jar` examined here is the standard distribution (`Main-Class: Main`, built 2022–2023).

## Purpose

sfinder answers questions like:
- *Can this field be Perfect Cleared with this piece sequence?* (`percent`)
- *What placements lead to a PC?* (`path`)
- *Which setups cover the most bag permutations?* (`cover`, `util fig`)
- *Does this field allow a T-Spin / specific spin?* (`spin`)
- *How long a Ren/combo is achievable?* (`ren`)

It is a **brute-force + smart-pruning solver** over piece placements, not an AI. It exhaustively explores reachable fields under SRS movement constraints and filters by goal predicates.

## Architecture (from JAR package structure)

```
Main ─┬─ entry/EntryPointMain        ← CLI dispatch
      │
      ├─ entry/{percent,path,cover,   ← one subpackage per command
      │         spin,ren,setup,verify,
      │         util,common}
      │
      ├─ core/                        ← the engine
      │   ├─ field/   Large/Middle/SmallField   ← bitboard field reps
      │   │           BitOperators, ColumnOperators, KeyOperators
      │   ├─ mino/    Mino, Piece, MinoShifter,  ← piece geometry
      │   │           MinoFactory, MinoTransform
      │   ├─ srs/     SRS rotation + kick tables
      │   ├─ action/  reachable-placement movement
      │   └─ neighbor/column_field/
      │
      ├─ searcher/                    ← the solvers
      │   ├─ pack/      cover/PC packing (mino_field, solutions,
      │   │             calculator, memento, connections)
      │   ├─ spins/     T-spin / spin detection (largest subtree)
      │   ├─ checker/   PC feasibility checks (Hold / NoHold)
      │   ├─ checkmate/ full placement enumeration
      │   └─ ren/       combo search (RenUsingHold, RenNoHold)
      │
      ├─ common/  datastore, tetfu (fumen), order, pattern,
      │           comparator, tree, parser, generator
      ├─ concurrent/  parallel checker/checkmate (multi-threaded)
      └─ org/apache/  Commons CLI (arg parsing)
```

### Key design points

- **Bitboard fields.** Fields are `SmallField` (≤6 rows, one `long`), `MiddleField`, `LargeField` (up to 24 rows, multiple longs). Line clears, collision, and merges are bit operations — this is what makes exhaustive search tractable.
- **MinoShifter / MinoTransform** canonicalize piece orientations (e.g. S/Z/I have only 2 distinct rotation states) to prune duplicate states.
- **Reachability via `core/action` + `core/srs`.** A placement only counts if SRS movement (including kicks, optional soft-drop/180/hold) can actually reach it — distinguishes "fits" from "placeable."
- **Pattern language** (`common/pattern`): piece-sequence specs like `*p7`, `[^T]!`, `SZ,*,[LJ]p2` drive percent/path over all matching bags.
- **Fumen I/O** (`common/tetfu`): reads/writes fumen codes (`v115@…`) for field input and solution output — the interop format with the rest of the Tetris tooling ecosystem.
- **Concurrency:** `concurrent/` provides multi-threaded checker/checkmate for large searches.

## Commands (entry points)

| Command   | Question answered |
|-----------|-------------------|
| `percent` | % of sequences that achieve a PC from a field |
| `path`    | enumerate the actual solution placements (fumen output) |
| `cover`   | fraction of bags a set of setups/solutions covers |
| `setup`   | find setups matching a field/margin template |
| `spin`    | detect T-spins / arbitrary spins, by clear count |
| `ren`     | maximize combo length |
| `verify`  | sanity-check a solution against rules |
| `util fig`| render fields/solutions to images/GIFs |

## Relevance to this SDK

sfinder is the **gold-standard reference engine** for PC-mode correctness. For the Tetris SDK:

- **Fumen format** is the shared interchange — the SDK already has a `fumen/` parser; sfinder both consumes and emits the same codes, so it's the natural ground-truth for round-trip testing.
- **SRS + reachability semantics** in `core/srs` and `core/action` define exactly what "a legal placement" means. Any SDK board/movement model should match sfinder's behavior to be trusted by the PC community.
- **Bitboard field design** is a proven performance pattern if the SDK ever needs fast search.
- It is a **subprocess oracle**, not a library to embed (Java CLI, no clean public API). The likely integration is: SDK shells out to `java -jar sfinder.jar <cmd>`, passing fumen, parsing stdout/CSV/fumen results — exactly what the surrounding `PCReview` / `pc-saves-get` / `pc-nn` tooling in this repo tree already does.

**Limitations:** SRS-only (no other rotation systems), single-player field analysis only (no live game, garbage, or opponent model), JVM startup cost per invocation, output parsing is brittle (text/CSV/fumen).
