"""Perfect-clear bag/leftover arithmetic.

A 7-bag PC game places 10 pieces per PC, so each PC spans 1.43 bags and the PC
"rank" (1st-7th) cycles every 35 pieces (5 bags). These helpers compute the rank
from a cumulative piece count and the leftover-size formulas that govern how many
pieces a PC inherits from the previous bag and leaves for the next PC.

Conventions match PC-Saves-Get / sfinder tooling:

* ``leaves(rank)``    pieces left over for the NEXT PC  -> ``(rank*4) % 7 or 7``
* ``receives(rank)``  pieces inherited from the prev bag -> ``((rank*4)+2) % 7 + 1``
"""

from __future__ import annotations

# cumulative-pieces-mod-35 -> rank (1st..7th)
_MOD_TO_RANK = {0: 1, 10: 2, 20: 3, 30: 4, 5: 5, 15: 6, 25: 7}


def pc_number(cumulative_pieces: int) -> int | None:
    """Rank (1-7) of the PC that *starts* after ``cumulative_pieces`` placements.

    Returns ``None`` if the count is not on a PC boundary (e.g. a mixed
    2-line/4-line game can land off the 10-piece grid).
    """
    return _MOD_TO_RANK.get(cumulative_pieces % 35)


def leaves(rank: int) -> int:
    """Number of pieces this PC leaves over for the NEXT PC."""
    _check_rank(rank)
    return (rank * 4) % 7 or 7


def receives(rank: int) -> int:
    """Number of pieces this PC inherits from the PREVIOUS bag."""
    _check_rank(rank)
    return ((rank * 4) + 2) % 7 + 1


def nonqueued(rank: int, pieces_needed: int) -> int:
    """Leftover pieces that lie *beyond* the 7-piece queue window.

    The sfinder pattern only sees the next 7 pieces (one bag of lookahead). The
    full leftover for the next PC also includes pieces from later bags not yet in
    that window — those are leftover no matter what the solver does::

        total_leftover  = leaves(rank)
        unused_from_queue = 7 - pieces_needed
        nonqueued       = total_leftover - unused_from_queue
    """
    return leaves(rank) - (7 - pieces_needed)


def _check_rank(rank: int) -> None:
    if not isinstance(rank, int) or not (1 <= rank <= 7):
        raise ValueError(f"rank must be 1-7, got {rank!r}")
