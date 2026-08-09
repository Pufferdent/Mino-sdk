"""Build an sfinder pattern string from a player's queue at a setup state.

The sfinder solver takes a 7-piece "next bag" lookahead. Given the full piece
deal order, how many pieces are already placed, and the visible queue (which
starts with the hold piece when one is held), :func:`queue_to_pattern` produces
the pattern that describes exactly the 7 pieces available from this state:

* known pieces remaining in the current bag collapse to ``[ABC]pN`` (or ``*pN``
  when all 7 types are present),
* a piece held over from the *previous* bag leads the pattern as ``[X]p1``,
* anything past the bag window is a free wildcard ``*pN``.

The total always sums to 7, matching sfinder's one-bag lookahead.
"""

from __future__ import annotations

ALL_PIECES = "TILJSZO"


def queue_to_pattern(
    full_sequence: str,
    placed_blocks: int,
    queue_str: str,
) -> str | None:
    """Return the sfinder pattern for the pieces available at this state.

    ``full_sequence`` is the entire deal order (piece letters). ``placed_blocks``
    is how many pieces have been placed when this state is reached.
    ``queue_str`` is the Jstris-style visible queue; a length of 7 means a piece
    is held (``queue_str[0]``).

    Returns ``None`` when the deal position runs past the known sequence.
    """
    if not queue_str:
        return None
    has_hold = len(queue_str) == 7
    deal_pos = placed_blocks + (1 if has_hold else 0)
    if deal_pos >= len(full_sequence):
        return None

    bag_start = (deal_pos // 7) * 7
    bag_end = bag_start + 7
    upcoming = list(full_sequence[deal_pos:min(bag_end, len(full_sequence))])

    held = queue_str[0] if has_hold else None
    held_in_bag = held is not None and held in full_sequence[bag_start:deal_pos]
    cur_bag = upcoming + [held] if held_in_bag else list(upcoming)

    parts: list[str] = []
    need = 7
    if held and not held_in_bag:  # leftover from the previous bag
        parts.append(f"[{held}]p1")
        need -= 1

    k = min(len(cur_bag), need)
    if k > 0:
        if len(set(cur_bag)) == 7:
            parts.append(f"*p{k}")
        else:
            parts.append(f"[{''.join(cur_bag)}]p{k}")
        need -= k

    if need > 0:
        parts.append(f"*p{need}")

    return ",".join(parts) if parts else None
