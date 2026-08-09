from __future__ import annotations

from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from mino_sdk.pieces import PieceType


def is_placement_order_valid(
    draw_queue: list["PieceType"],
    placement_order: list["PieceType"],
    hold_rule: str = "standard",
) -> bool:
    """Return True if *placement_order* is reachable from *draw_queue* with the
    given *hold_rule* (``"standard"``, ``"sfinder"``, or ``"none"``).
    """
    if hold_rule not in ("standard", "sfinder", "none"):
        raise ValueError(f"Unknown hold_rule: {hold_rule!r}")

    memo: set[tuple[tuple, object, bool, int]] = set()
    target_count = len(placement_order)

    def can_hold_fn(prev_can_hold: bool) -> bool:
        if hold_rule == "none":
            return False
        if hold_rule == "sfinder":
            return True
        return prev_can_hold

    def dfs(
        remaining: tuple["PieceType", ...],
        hold: "PieceType | None",
        can_hold: bool,
        order_idx: int,
    ) -> bool:
        if order_idx == target_count:
            return True

        key = (remaining, hold, can_hold, order_idx)
        if key in memo:
            return False
        memo.add(key)

        target = placement_order[order_idx]

        # 1. Place from queue
        if remaining and remaining[0] == target:
            if dfs(remaining[1:], hold, True, order_idx + 1):
                return True

        # 2. Place from hold
        if hold is not None and hold == target:
            if dfs(remaining, None, True, order_idx + 1):
                return True

        # 3. Hold
        hok = can_hold_fn(can_hold)
        if hok and remaining:
            if hold is None:
                if dfs(remaining[1:], remaining[0], False, order_idx):
                    return True
            else:
                new_remaining = (hold,) + remaining[1:]
                if dfs(new_remaining, remaining[0], False, order_idx):
                    return True

        return False

    return dfs(tuple(draw_queue), None, True, 0)


def enumerate_placement_orders(
    draw_queue: list["PieceType"],
    hold_rule: str = "standard",
) -> list[list["PieceType"]]:
    """Return all reachable placement orders (prefixes) under *hold_rule*."""
    if hold_rule not in ("standard", "sfinder", "none"):
        raise ValueError(f"Unknown hold_rule: {hold_rule!r}")

    results: list[list["PieceType"]] = []
    visited: set[tuple[tuple, object, bool]] = set()

    def can_hold_fn(prev_can_hold: bool) -> bool:
        if hold_rule == "none":
            return False
        if hold_rule == "sfinder":
            return True
        return prev_can_hold

    def dfs(
        remaining: tuple["PieceType", ...],
        hold: "PieceType | None",
        can_hold: bool,
        current: list["PieceType"],
    ) -> None:
        if current:
            results.append(list(current))

        key_state = (remaining, hold, can_hold)
        if key_state in visited:
            return
        visited.add(key_state)

        # 1. Place from queue
        if remaining:
            current.append(remaining[0])
            dfs(remaining[1:], hold, True, current)
            current.pop()

        # 2. Place from hold
        if hold is not None:
            current.append(hold)
            dfs(remaining, None, True, current)
            current.pop()

        # 3. Hold
        hok = can_hold_fn(can_hold)
        if hok and remaining:
            if hold is None:
                dfs(remaining[1:], remaining[0], False, current)
            else:
                dfs((hold,) + remaining[1:], remaining[0], False, current)

    results.append([])
    dfs(tuple(draw_queue), None, True, [])
    return results
