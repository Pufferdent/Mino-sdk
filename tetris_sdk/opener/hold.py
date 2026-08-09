"""What a hold slot can and cannot reorder.

A line's routes are placement *orders*, but a player does not get to choose an
order — they get a queue and one hold slot. From a queue the only pieces in
reach are the front one and whatever is held, so most orders are unplayable.
Treating every permutation as available overstates a line's chance, sometimes
badly.

The model is the one :class:`~tetris_sdk.opener.node.Node` already uses: put the
held piece at the front of the queue, and placing is consuming index 0 or
index 1. Consuming index 1 leaves index 0 in front — that *is* holding.

:func:`producible` asks whether a queue can produce any of a set of orders,
walking both against a trie so the shared prefixes are only explored once.
"""

from __future__ import annotations

from itertools import permutations

from tetris_sdk.pieces import PieceType

_END = None


def trie(orders) -> dict:
    """Index placement orders by shared prefix."""
    root: dict = {}
    for order in orders:
        node = root
        for piece in order:
            node = node.setdefault(piece, {})
        node[_END] = True
    return root


def producible(queue: tuple, root: dict, count: int) -> bool:
    """Can ``queue`` place ``count`` pieces in some order the trie holds?

    ``queue`` is the effective queue: any held piece first, then upcoming.
    """
    seen: set = set()

    def walk(available: tuple, node: dict, placed: int) -> bool:
        if placed == count:
            return _END in node
        key = (available, id(node))
        if key in seen:
            return False
        seen.add(key)
        for index in (0, 1):
            if index >= len(available):
                break
            nxt = node.get(available[index])
            if nxt is None:
                continue
            rest = available[:index] + available[index + 1:]
            if walk(rest, nxt, placed + 1):
                return True
        return False

    return walk(tuple(queue), root, 0)


def queues(bag: tuple, leftover: tuple = ()) -> list:
    """Every queue a line can face: each bag order, behind the held leftover."""
    return [tuple(leftover) + order for order in permutations(bag)]


def coverage(orders, bag: tuple, count: int, leftover: tuple = ()) -> tuple[int, int]:
    """``(playable, total)`` queues — the numerator and denominator of a chance."""
    if not orders:
        return 0, len(queues(bag, leftover))
    root = trie(orders)
    every = queues(bag, leftover)
    hits = sum(1 for q in every if producible(q, root, count))
    return hits, len(every)


def coverage_any(groups, bag: tuple, leftover: tuple = ()) -> tuple[int, int]:
    """``(playable, total)`` queues able to produce at least one group's order.

    ``groups`` is an iterable of ``(orders, count)`` — one entry per
    alternative line. A queue counts once however many alternatives accept
    it, which is what makes this a union rather than a sum: alternatives
    overlap, and adding their coverages would double-count the overlap.
    """
    tries = [(trie(orders), count) for orders, count in groups if orders]
    every = queues(bag, leftover)
    hits = sum(1 for q in every
               if any(producible(q, root, count) for root, count in tries))
    return hits, len(every)
