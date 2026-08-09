# Opener search — working notes

## 2026-08-09 — the blocker is resolved: `TileSolver`

`mino_sdk/opener/tiles.py` now ships a solver, used by default by
`Bridge.routes()` / `Diagram.chances()`. It is exact and evaluates a
full-bag bridge (routes + hold coverage) in about a second: the three-bag
example's heaviest line (3 clears) takes 1.0 s from a cold process, and the
whole example runs in ~2.1 s.

The shape: **lifted exact cover proposes, real-frame replay disposes.**

1. Put the cleared rows back (`lifted.frames` tries every placement of them)
   and the line has a static region again: `lifted(end) − start`.
2. Exact-cover the region per pool (`tiling.tile`, anchor-cell search). The
   step that makes this *exact* rather than a lower bound: a piece placed
   after a clear that straddles the vanished row appears **stretched** — with
   a gap at that row — in the lifted frame, so stretched footprints are tiled
   too (`tiling._variants`). This is also why some of sfinder's
   "disconnected piece" solutions (item 3 below) were genuine after all.
3. Replay each tiling in the real frame: rows clear the moment they fill,
   placements count only if `fastreach.reach` (bitboard BFS with SRS kicks —
   tucks and spins found, not assumed) can produce them, gravity waits come
   from the instant-drop diff, constraints prune mid-route. A stretched
   footprint maps to a disconnected cell set until its straddled rows are
   gone, so ordering legality falls out of the reach check.

Why it is fast where §Performance reality below was not: replay candidates
come from the tiling (a handful, not every resting position — the 350x), the
dead-state memo is keyed on the *remaining tiling entries* (all tilings of a
frame partition the same region, so that determines the whole state and the
work is shared across tilings), and `reach` is cached per (stack, piece)
with pure-bitmask collision tests.

Verified: `fastreach` ≡ engine on random stacks (`test_fastreach.py`);
solver coverage ≡ the independent per-queue `playable()` forward search on a
mid-clear line (720/5040 both ways; 0.03 s vs 19.8 s); the impossible cases
(§3) report 0; a route that *requires* a straddling piece is found, and its
illegal reverse order is not (`test_tile_solver.py`).

Forks are supported at both levels. `any_odds([bridge_a, bridge_b, ...])` /
`any_chance(...)` give the chance that **at least one** of several lines
from the same start (same leftover, each under its own constraints) is
playable — a true union over queues, not a sum, so overlapping
alternatives are not double-counted.

Whole forked diagrams are evaluated by `Diagram.optimize(start, score)`:
you write a scoring function over a `Route` (the entire interface), and
every queue is attributed to the playable option with the highest score
plus expected future — optimal play, per-bag knowledge, bags independent.
Routes are grouped by `(score, saved)`, so choosing a route also chooses
the leftover the next line starts from; states are `(board, leftover)`
pairs, valued leaves-first with plain loops. `Diagram.chance_to(start,
target)` is the probability special case; `explain()` shows every state's
choices; `on_fail` prices queues with no playable line (a dead end — a
state whose lines have no routes — is `on_fail`, not a success); cycles
raise (loop analysis is a later feature). Caveat, inherited from the
leftover model: saves re-enter in canonical order, not the real queue's
relative order.

The rotation system is a parameter and defaults to **TETR.IO's SRS+**
(180 kicks enable the flip move, matching the engine's rule). Pass
`Bridge(..., system=SRS())` / `Diagram(system=SRS())` for guideline SRS, or
any other `RotationSystem`; `fastreach` is engine-verified under both.
Routes needing a gravity wait still count unless `NoGravityWait` is passed.
Everything below this section is the history that led here.

Goal: find a **looping opener** — reaches a perfect clear after 14 lines, and
preserves S2 back-to-back at 100% (every queue, guaranteed).

14 lines = 140 cells = 35 pieces = exactly 5 bags. So the target query is
"5 bags from empty, 14 lines cleared, board empty at the end, no clear ever
breaks B2B".

## State of the code (2026-08-08)

Working and tested (267 tests pass):

- `Node` — canonical **uncolored** fumen + queue. Colour is normalised in
  `__post_init__` (cached), so every entry point auto-uncolors.
- `engine.reachable(..., instant=True)` — restricted BFS where soft drop
  teleports to rest. Diffing against the normal BFS is what identifies a
  **gravity wait**, which is the only real execution cost (tucks and spins are
  free with instant soft drop).
- `constraints.py` — `Constraint` protocol (`allows` + `prune`), with
  `KeepB2B`, `Spin`, `Saves`, `NoGravityWait`, `Clears`.
- `hold.py` — hold automaton and trie membership; coverage counts **queues**,
  not orderings.
- `diagram.py` — `Diagram.board()/.line()/.chances()`.
- `tiling.py` — exact cover over a static region.
- `Bridge.playable(queue)` — per-queue forward search in the real frame.

## What is settled, and was hard-won

1. **The mino tally gives the clear count for free.**
   `cleared = (start_cells + 4*pieces - end_cells) / 10`. Non-integer → the
   line is impossible, with no search at all.

2. **The complement-as-garbage PC encoding is wrong for most lines.** It
   declares every cell outside the region solid. When a line clears few lines
   the complement is large and open, and the fiction walls off columns pieces
   really fall through. Bag 1 of the user's diagram is a *verified* 7-piece
   tiling (each colour group checked to be a real tetromino) yet sfinder
   reported `0/5040` on that encoding.

3. **sfinder's solution count over-reports.** It allows the fake complement
   rows to clear mid-sequence. For one example it returned 9 "tilings"; exact
   cover found 4, and 5 of sfinder's had **disconnected pieces** (a Z split
   across rows 0 and 2). Any number derived from that base was inflated —
   including the 1772 routes and 453 TSDs quoted earlier in the session.

4. **When rows clear mid-bag, the placements do not tile a static region.**
   Later pieces land in shifted coordinates. So neither the PC encoding nor
   exact cover models such a line. Exact cover is exact and instant only when
   `cleared_lines == 0` (bag 1: 1 tiling, correct, <0.01 s).

5. **Tucks and spins are not execution difficulty.** With soft drop set to
   instant, only a *gravity wait* costs the player anything.

## The blocker

The forward real-frame search is correct but too slow in pure Python. Measured:
`_placements` is not the problem (34 placements, 1.7 ms first call, 0.1 µs
cached). It is raw state count — fanout 34 per piece over 7 pieces, and the
height cap (`len(target) + clears_remaining`) does not bite until depth ~4.
A single queue did not finish in 10 minutes.

Prunes currently in place:
- clear budget from the tally
- height ≤ `len(target) + clears_remaining` (every row either survives into the
  end state or clears)
- once the budget is spent: stack must fit inside the target, and the cell
  deficit must equal `4 * pieces_remaining`

Missing prune worth trying: rows that are not a subset of any target row must
number ≤ clears remaining (each such row is obliged to clear).

## Decision

Heavy search goes to `sfinder.jar` — the standing project rule, and it applies
here. Use it for the PC/tiling half, and use this module only for B2B and
gravity-wait verification of candidates. See `MEMORY.md` →
`sfinder-over-native-solver`.

## Results on the 14-line loop (2026-08-08, post-revival)

A PC loop is a chain of PC *segments*; each starts and ends on an empty board.
A segment clearing `n` lines uses `2.5n` pieces, so **`n` must be even**. The
whole loop is 14 lines / 35 pieces / 5 bags, and 35 pieces for 140 cells is
exactly 2.5 per line — **zero slack**, no piece may be parked.

### 1. An all-quad loop is impossible

14 is not divisible by 4. Every 14-line B2B loop must contain at least one
**spin** clear. Minimum-spin shape is 3 quads + 2 lines of spin clears.

### 2. Quads cannot carry a guaranteed loop — ceiling 42.9%

A 4-line PC that clears as a *single quad* has a forced shape: no row may
complete early, so the closing piece must be a vertical I completing all four
rows at once, and the other nine pieces tile the 4×10 region minus the I's
column.

Colour that region like a checkerboard: 18 black, 18 white. I, L, J, S, Z and O
each cover 2 and 2; **only T is unbalanced** (3–1). So the body needs an **even
number of T pieces**. With one bag plus extras that forces exactly two T, i.e.
a T must arrive early in the second bag.

Measured: only **15 of 35** first-three-of-bag-2 combinations admit an even-T
body — **42.9%**, exactly 3/7. A single-quad 4-line PC can never be guaranteed,
so no quad-based loop reaches 100%.

Bodies do exist for all six viable pools when the I closes in column 0; fewer
as the I moves inward (column 4: only `TL`, `TJ`).

### 3. A 2-line PC segment is impossible — proved twice

`Bridge.odds()` returned **0/5040** for a 2-line PC (5 pieces, from empty), and
exhaustive tiling of the 2×10 strip over every 5-subset of a bag agrees: no
pool tiles it.

Reason: in a two-row strip S and Z always orphan a cell at the edge, and T is
barred by the same parity argument. That leaves I, O, L, J — four types, one
each from a bag, so at most 16 of the 20 cells.

**Consequence: 4+4+4+2 is dead**, and so is any decomposition containing a
2-line segment. Surviving decompositions of 14 into even segments ≥ 4:
`4+4+6`, `4+6+4`, `6+4+4`, `4+10`, `10+4`, `6+8`, `8+6`, `14`.

### 4. The even-T parity theorem, and exactly how far it reaches

For a PC segment in which **no row clears until the end**, the pieces tile a
static `n×10` rectangle. Checkerboard it: `5n` black, `5n` white. I, L, J, S, Z
and O each cover 2 and 2; only T is unbalanced (3–1). So such a segment needs
an **even number of T pieces**.

Verified exhaustively on the 4-line case: of the 35 possible 10-piece pools,
**15/15 even-T pools tile 4×10 and 0/20 odd-T pools do** — the parity bound is
exactly tight, not merely necessary.

**Where it stops.** It does *not* extend to segments with intermediate clears.
When a row clears, everything above shifts down one row, which **flips the
checkerboard colour of every cell above it**, so the invariant does not survive.
Column-parity colouring survives row shifts but is not piece-invariant (a
vertical I is 4-of-one-colour, a horizontal I is 2–2), so it yields no theorem
either.

I briefly thought this proved the whole goal impossible — 5 bags carry 5 T's,
odd, versus a sum of even per-segment counts. **That argument is wrong**, for
exactly the reason above: it silently assumes no segment clears a row early.
Recording it so it does not get re-derived and believed.

### 4b. Correction — the 42.9% ceiling is narrower than it first looks

The quad result above is about a 4-line **PC** that clears as a single quad
(board empty afterwards). It says nothing about quads in general: a mid-game
quad just clears four rows of a taller stack, which is ordinary play and
carries no such ceiling.

Related and more important: the goal says a perfect clear **after 14 lines**,
not a chain of PCs. The board need not be empty in between. So this is one
35-piece span ending in a PC, not `4+4+6`-style segments — the decomposition
work above only applies if intermediate PCs are *chosen*, and it should not be
treated as a constraint on the goal.

Under that reading the target looks like a **B2B opener that happens to PC at
14 lines**: e.g. 3 quads (12 lines) + one spin double, or seven spin doubles,
or any composition of 14 from quads and spin clears. Seven T-spin doubles is
out on its own — that needs 7 T pieces and 5 bags carry only 5 — but under S2
all-spin the spins need not be T, so that is not binding.

### 5. Where that leaves the goal

Quads are capped at 42.9%, so a 100% loop must clear almost everything with
**spins**. Under S2 all-spin any piece locking immobile counts, not just T,
which is far more permissive and is the promising direction — dense PC stacks
produce immobile locks often. `Step.spin` already records this for every
placement, so the machinery to check it exists.

### Performance reality

`Bridge.odds()` on the *smallest possible* segment (5 pieces, height capped at
2) took 169 s for 5040 queues — ~33 ms per queue. A 10-piece segment is far
worse. Full queue coverage on real segments needs sfinder to propose and this
module only to verify, not a pure-Python forward search.

## Next steps

1. Baseline: `sfinder percent -c 14 -p *p7,*p7,*p7,*p7,*p7` from empty — how
   often is a 14-line PC even available across 5 bags?
2. Enumerate 14-line PC solutions, then filter for B2B: every clear must be a
   quad or a spin under S2.
3. A loop needs the *end* state to equal the *start* state. A PC returns to
   empty, so any 14-line PC opener is trivially a loop by construction — the
   real constraint is the 100% B2B and the bag alignment (35 pieces = 5 bags,
   so the loop restarts on a bag boundary, which is what makes it repeatable).
