# Rotation Kick Tables — SRS+ reference (+ deferred systems)

Reference data for the rotation systems the SDK ships. **Current scope: `SRS` (plain) and `SRSPlus` only.** `SRSX` and `Jstris180` are recorded here but **deferred** — pure data additions for later.

Kicks are stored in the SDK's native **`(drow, dcol)` row-up** convention (same as `Piece.cells`). The source data below uses other conventions; conversion + verification notes follow each.

> Implementation approach (see `openspec/changes/add-move-engine`): SRS+ is defined as a **diff from corrected `SRS`** — JLSTZ 90° reused exactly, I-piece 90° by column-axis reflection, 180s added — then pinned by a TST/180 fumen test. The raw `[x,y]` tables below are reference, not transcription targets.

## Provenance & status

| System | Source | Status |
|--------|--------|--------|
| **SRS** (plain) | existing `pieces.py` (needs convention correction) | ✅ shipped, being corrected |
| **SRS+** (TETR.IO default) | `@haelp/teto` engine source (`triangle`) | ✅ extracted, full table below |
| **SRS-X** (TETR.IO "powerful 180") | `@haelp/teto` engine source | ⏸ deferred |
| **jstris180** | `PCReview v2/kicks/jstris180.properties` (@metallicLurker) | ⏸ deferred |

## SRS+ full table (verbatim from teto engine)

`[x, y]`, TETR.IO **y-down**, tried after an implicit `[0, 0]`. SDK import: `(x, y) → (drow = −y, dcol = x)` with `(0,0)` prepended — **but verify the sign with a fumen** (JLSTZ 90° must reproduce the corrected SRS values exactly; if not, the convention is off).

```
JLSTZ/T  01 [-1,0][-1,-1][0,2][-1,2]      10 [1,0][1,1][0,-2][1,-2]
         12 [1,0][1,1][0,-2][1,-2]        21 [-1,0][-1,-1][0,2][-1,2]
         23 [1,0][1,-1][0,2][1,2]         32 [-1,0][-1,1][0,-2][-1,-2]
         30 [-1,0][-1,1][0,-2][-1,-2]     03 [1,0][1,-1][0,2][1,2]
  180:   02 [0,-1][1,-1][-1,-1][1,0][-1,0]   20 [0,1][-1,1][1,1][-1,0][1,0]
         13 [1,0][1,-2][1,-1][0,-2][0,-1]    31 [-1,0][-1,-2][-1,-1][0,-2][0,-1]

I        01 [1,0][-2,0][-2,1][1,-2]       10 [-1,0][2,0][-1,2][2,-1]
         12 [-1,0][2,0][-1,-2][2,1]       21 [-2,0][1,0][-2,-1][1,2]
         23 [2,0][-1,0][2,-1][-1,2]       32 [1,0][-2,0][1,-2][-2,1]
         30 [1,0][-2,0][1,2][-2,-1]       03 [-1,0][2,0][2,1][-1,-2]
  180:   02 [0,-1]   13 [1,0]   20 [0,1]   31 [-1,0]
O        (none)
```
Note: SRS+ I-piece 90° kicks are **symmetric about the y-axis** (left side mirrored) — the difference from plain SRS that makes SRS+ "true TETR.IO" rather than "SRS + 180".

---

## Deferred (recorded for later, not shipped)

### jstris180 — 180 transitions only (sfinder properties, verbatim)
sfinder format `(x, y)` y-up; `N`=0 `E`=1 `S`=2 `W`=3; `@` flags a T-spin-mini kick.

> The examined `sfinder.jar` build (2023) bundles **only** the built-in `srs` table (no-180, `MinoRotationNo180Impl`). It does **not** ship an SRS+ or jstris built-in — those are loaded from external `kicks/*.properties` files via `FileMinoRotationFactory`. So "within sfinder" means *usable by sfinder as a properties file*, not embedded in the jar.

## ⚠️ Coordinate conventions differ between sources

- **sfinder `.properties`** (jstris180): offsets are **`(x, y)` with y-up**. Rotation states are letters: **N**=spawn(0), **E**=right(1), **S**=reverse(2), **W**=left(3). So `T.NS` = 0→2 (the 180), `T.SN` = 2→0. The `@` marker (e.g. `(@-1,-2)`) flags a kick that should be treated as a **T-spin mini** for spin detection.
- **TETR.IO engine** (SRS+/SRS-X): offsets are **`[x, y]`** arrays; transitions keyed `"02"` (0→2) and `"20"` (2→0).
- **This SDK** uses **`(row, col)` with row-up**. To import: **`(x, y)` → `(row=y, col=x)`**. Verify y-axis sign on first integration with a known fumen test.

---

## jstris180 (sfinder properties, verbatim)

Only the **180 transitions** (NS / SN / EW / WE) are reproduced here; the file also redefines all 90° kicks (standard SRS values). `&L.NS` means "alias to the L definition."

```
# 180 kicks — format (x,y), y-up.  N=0 E=1 S=2 W=3
L.NS=(0,0)(0,+1)     # 0->2
L.SN=(0,0)(0,-1)     # 2->0
L.EW=(0,0)(+1,0)     # 1->3
L.WE=(0,0)(-1,0)     # 3->1

J,S,Z,T : same as L   (J.NS=&L.NS, ... T.NS=&L.NS, etc.)

I.NS=(+1,-1)(+1,0)   # 0->2
I.SN=(-1,+1)(-1,0)   # 2->0
I.EW=(-1,-1)(0,-1)   # 1->3
I.WE=(+1,+1)(0,+1)   # 3->1

O.NS=(+1,+1)         # O has single-cell 180 offsets
O.EW=(+1,-1)
O.SN=(-1,-1)
O.WE=(-1,+1)
```

**Note:** jstris 180 for JLSTZ is only **2 tests** — `(0,0)` then a single sideways nudge. Minimal, by design.

### SRS-X (TETR.IO "powerful 180", NullpoMino/Heboris-style) — 180 transitions

Same `[x, y]` format; **11 candidates** per 180 transition — this is the "powerful 180" that lands TSTs/twists base SRS+ can't.

```
"02" (0->2): [1,0] [2,0] [1,1] [2,1] [-1,0] [-2,0] [-1,1] [-2,1] [0,-1] [3,0] [-3,0]
"20" (2->0): [-1,0] [-2,0] [-1,-1] [-2,-1] [1,0] [2,0] [1,-1] [2,-1] [0,1] [-3,0] [3,0]
```
I-piece uses an analogous expanded set. SRS-X is opt-in per room/solo in TETR.IO.

---

## Implications for the SDK rotation-system design

- The `RotationSystem.kicks(type, from, to)` abstraction already accommodates 180s — they're just extra `(0,2)/(2,0)/(1,3)/(3,1)` entries. No interface change; pure data (the Techmino "rotation-as-data" pattern).
- **Shipping now:** `SRS` (corrected) and `SRSPlus`. **Deferred:** `SRSX`, `Jstris180` (data above). `allow_flip` in `reachable()` auto-enables only under systems that define 180 kicks.
- The jstris `@` mini-flag and SRS+'s symmetric-I detail mean kick *identity* can carry spin meaning. Our move engine uses the *immobile* convention instead (independent of which kick fired), so `@` is ignored for classification — but keep it in mind if a kick-based T-spin convention is ever added as a pluggable `classify_spin`.
- **Action before trusting any table:** validate against a known fumen (TST/180 setup) on first import, because of the `(x,y)`↔`(drow,dcol)` and y-sign conventions. For SRS+, the JLSTZ 90° kicks must reproduce the corrected SRS values exactly — that's the built-in cross-check.
