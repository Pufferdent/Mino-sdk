"""Save-percentage math for PC mode.

A "save" is the probability that a wanted piece survives into the next PC's
leftover *and* the current PC still solves. Two effects combine:

* the **queued** window (the 7 pieces sfinder sees) — measured directly from an
  ``sfinder path`` enumeration as the fraction of solvable queues that leave the
  piece unused;
* the **non-queued** leftover — pieces beyond that window, which are leftover no
  matter what the solver does (see :func:`tetris_sdk.pc.leftover.nonqueued`).

The headline formula::

    save = solve_rate * (path_save + (100 - path_save) * nonqueued/7) / 100
"""

from __future__ import annotations

from tetris_sdk.pc.leftover import nonqueued
from tetris_sdk.pc.sfinder import PathResult

# sfinder path -k pattern CSV column headers
COL_QUEUE = "ツモ"
COL_FIELDS = "対応地形数"
COL_USED = "使用ミノ"
COL_UNUSED = "未使用ミノ"


def path_save_percent(result: PathResult, piece: str,
                      *, unused_col: str = COL_UNUSED) -> float:
    """Percent of solvable queues in ``result`` that leave ``piece`` unused.

    Each row is one queue; its unused column may list several alternative
    unused-sets (one per solving field) separated by ``;``. A queue counts as
    saving the piece if *any* of its solutions leaves the piece unused.
    """
    solvable = 0
    saving = 0
    for row in result.rows:
        unused = row.get(unused_col, "") or ""
        if not unused.strip():
            continue  # no solution for this queue
        solvable += 1
        alts = [a for a in unused.split(";") if a.strip()]
        if any(piece in a for a in alts):
            saving += 1
    return 100.0 * saving / solvable if solvable else 0.0


def combine_save(solve_rate: float, path_save: float,
                 rank: int, pieces_needed: int) -> float:
    """Combine the queued save fraction with the non-queued leftover.

    ``solve_rate`` and ``path_save`` are percentages (0-100). Returns the overall
    save percentage that the wanted piece survives into the next PC's leftover.
    """
    nq = nonqueued(rank, pieces_needed)
    return solve_rate * (path_save + (100.0 - path_save) * nq / 7.0) / 100.0
