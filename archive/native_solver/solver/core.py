from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from mino_sdk.board import Board, board_from_string, ROWS, COLS
from mino_sdk.engine import reachable
from mino_sdk.pieces import PieceType, SRS, RotationSystem, get_piece_cells
from mino_sdk.types import Cell

if TYPE_CHECKING:
    pass

_ROW_MASK = (1 << COLS) - 1
_MAX_ROWS = 40

_PIECE_OFFSETS: dict[tuple[PieceType, int], list[tuple[int, int]]] = {}
for _pt in PieceType:
    for _rot in range(4):
        cells = get_piece_cells(_pt, _rot, 0, 0, coord_system="sdk")
        min_row = min(r for r, _ in cells)
        offsets = [(r - min_row, c) for r, c in cells]
        _PIECE_OFFSETS[(_pt, _rot)] = offsets


def _column_heights(bb: int) -> list[int]:
    heights = [0] * COLS
    temp = bb
    while temp:
        lsb = temp & -temp
        pos = lsb.bit_length() - 1
        r = pos // COLS
        c = pos % COLS
        if r + 1 > heights[c]:
            heights[c] = r + 1
        temp ^= lsb
    return heights


def _piece_mask_from_heights(
    piece_type: PieceType, rotation: int, col: int, heights: list[int],
) -> int:
    offsets = _PIECE_OFFSETS[(piece_type, rotation)]
    row = 0
    for dr, dc in offsets:
        c = col + dc
        if 0 <= c < COLS:
            base = heights[c]
            candidate_row = base - dr
            if candidate_row > row:
                row = candidate_row
    mask = 0
    for dr, dc in offsets:
        cr = row + dr
        cc = col + dc
        if 0 <= cr < _MAX_ROWS and 0 <= cc < COLS:
            mask |= 1 << (cr * COLS + cc)
    return mask


@dataclass
class Solution:
    piece_order: list[str]
    board_states: list[Board]
    operations: list[tuple[PieceType, int, int, int]]
    unused_pieces: list[PieceType] = field(default_factory=list)
    topological_orderings: list[list[tuple[PieceType, int, int, int]]] = field(
        default_factory=list
    )


def _board_to_int(board: Board) -> int:
    bb = 0
    for r in range(ROWS):
        for c in range(COLS):
            if board.get_cell(r, c) != Cell.EMPTY:
                bb |= 1 << (r * COLS + c)
    return bb


def _int_to_board(bb: int) -> Board:
    b = Board()
    for r in range(ROWS):
        for c in range(COLS):
            if (bb >> (r * COLS + c)) & 1:
                b.set_cell(r, c, Cell.GARBAGE)
    return b


def _bb_clear_lines(bb: int) -> int:
    rows = []
    for r in range(_MAX_ROWS):
        row_val = (bb >> (r * COLS)) & _ROW_MASK
        if row_val != _ROW_MASK:
            rows.append(row_val)
    while len(rows) < _MAX_ROWS:
        rows.append(0)
    result = 0
    for r, row_val in enumerate(rows):
        result |= row_val << (r * COLS)
    return result


def _bb_max_filled_row(bb: int) -> int:
    for r in range(_MAX_ROWS - 1, -1, -1):
        if (bb >> (r * COLS)) & _ROW_MASK:
            return r
    return -1


def _make_mask(piece_type: PieceType, rotation: int, col: int, row: int) -> int:
    mask = 0
    for cr, cc in get_piece_cells(piece_type, rotation, col, row, coord_system="sdk"):
        if 0 <= cr < _MAX_ROWS and 0 <= cc < COLS:
            mask |= 1 << (cr * COLS + cc)
    return mask


def solve_pc(
    board: Board | str,
    queue: list[PieceType | str],
    *,
    hold: str = "standard",
    head_hold: PieceType | str | None = None,
    max_solutions: int | None = None,
    clear_lines: int = 4,
    system: RotationSystem | None = None,
) -> list[Solution]:
    if isinstance(board, str):
        board = board_from_string(board)

    if system is None:
        system = SRS()

    queue = [
        PieceType[p] if isinstance(p, str) else p for p in queue
    ]
    if head_hold is not None and isinstance(head_hold, str):
        head_hold = PieceType[head_hold]

    if hold not in ("standard", "sfinder", "none"):
        raise ValueError(f"Unknown hold mode: {hold!r}")

    solutions: list[Solution] = []
    memo: dict[tuple, list[Solution]] = {}
    reachable_cache: dict[tuple[int, PieceType], list[tuple[int, int, int, int]]] = {}

    init_bb = _board_to_int(board)

    def _solve(
        bb: int,
        remaining: list[PieceType],
        hold_piece: PieceType | None,
        piece_order: list[str],
        operations: list[tuple[PieceType, int, int, int]],
    ) -> list[Solution]:
        nonlocal solutions

        if max_solutions is not None and len(solutions) >= max_solutions:
            return []

        if bb == 0:
            sol = Solution(
                piece_order=list(piece_order),
                board_states=[_int_to_board(bb)],
                operations=list(operations),
                unused_pieces=list(remaining),
            )
            solutions.append(sol)
            return [sol]

        max_row = _bb_max_filled_row(bb)
        if max_row >= clear_lines + 12:
            return []

        key = (bb, tuple(remaining), hold_piece)
        if key in memo:
            return list(memo[key])

        memo[key] = []
        local_solutions: list[Solution] = []

        heights = _column_heights(bb)

        def try_placements(
            piece_type: PieceType,
            new_remaining: list[PieceType],
            new_hold: PieceType | None,
        ) -> None:
            nonlocal local_solutions
            for rotation in range(4):
                offsets = _PIECE_OFFSETS[(piece_type, rotation)]
                min_dc = min(dc for _, dc in offsets)
                max_dc = max(dc for _, dc in offsets)
                for col in range(-min_dc, COLS - max_dc):
                    row = 0
                    rests_on = False
                    for dr, dc in offsets:
                        c = col + dc
                        if 0 <= c < COLS:
                            h = heights[c]
                            if h - dr > row:
                                row = h - dr
                            if row + dr == h and h > 0:
                                rests_on = True
                    mask = 0
                    for dr, dc in offsets:
                        cr = row + dr
                        cc = col + dc
                        if 0 <= cr < _MAX_ROWS and 0 <= cc < COLS:
                            mask |= 1 << (cr * COLS + cc)
                    if mask == 0 or (mask & bb) != 0:
                        continue
                    if row > clear_lines + 4:
                        continue
                    if bb != 0 and not rests_on and not (mask & _ROW_MASK):
                        continue
                    new_bb = bb | mask
                    new_bb = _bb_clear_lines(new_bb)
                    if new_bb == bb:
                        continue
                    new_order = piece_order + [piece_type.name]
                    new_ops = operations + [
                        (piece_type, rotation, col, row)
                    ]
                    sub = _solve(
                        new_bb, list(new_remaining), new_hold,
                        new_order, new_ops,
                    )
                    local_solutions.extend(sub)

        if hold == "none":
            if remaining:
                try_placements(remaining[0], remaining[1:], None)
        else:
            if remaining:
                piece1 = hold_piece if hold_piece is not None else remaining[0]
                if hold_piece is not None:
                    try_placements(piece1, list(remaining), None)
                else:
                    try_placements(piece1, remaining[1:], None)

                if hold_piece is not None:
                    try_placements(hold_piece, remaining[1:], remaining[0])
                elif len(remaining) >= 2:
                    try_placements(remaining[1], remaining[2:], remaining[0])

                if hold == "sfinder":
                    new_hold = remaining[0]
                    new_remaining = remaining[1:]
                    if hold_piece is not None:
                        new_remaining = [hold_piece] + new_remaining
                    sub = _solve(
                        bb, new_remaining, new_hold,
                        piece_order, operations,
                    )
                    local_solutions.extend(sub)

        memo[key] = local_solutions
        return local_solutions

    init_hold: PieceType | None = head_hold
    _solve(init_bb, queue, init_hold, [], [])

    for sol in solutions:
        sol.topological_orderings = _compute_topological_orderings(sol.operations)

    return solutions


def _compute_topological_orderings(
    operations: list[tuple[PieceType, int, int, int]],
) -> list[list[tuple[PieceType, int, int, int]]]:
    n = len(operations)
    if n <= 1:
        return [list(operations)]

    piece_cells: list[list[tuple[int, int]]] = []
    for ptype, rot, col, row in operations:
        cells = get_piece_cells(ptype, rot, col, row, coord_system="sdk")
        piece_cells.append(cells)

    adj: list[list[int]] = [[] for _ in range(n)]
    indegree: list[int] = [0] * n

    for i in range(n):
        cells_i = piece_cells[i]
        cols_i = {c for _, c in cells_i}
        for j in range(n):
            if i == j:
                continue
            cells_j = piece_cells[j]
            common_cols = cols_i & {c for _, c in cells_j}
            for c in common_cols:
                min_row_i = min(r for r, col_ in cells_i if col_ == c)
                min_row_j = min(r for r, col_ in cells_j if col_ == c)
                if min_row_i < min_row_j:
                    # i is below j in this column → i must be placed before j
                    adj[i].append(j)
                    indegree[j] += 1
                    break

    all_orders: list[list[tuple[PieceType, int, int, int]]] = []

    def backtrack(
        order: list[int], visited: list[bool], indeg: list[int]
    ) -> None:
        if len(order) == n:
            all_orders.append([operations[idx] for idx in order])
            return

        for i in range(n):
            if not visited[i] and indeg[i] == 0:
                visited[i] = True
                order.append(i)
                for nb in adj[i]:
                    indeg[nb] -= 1
                backtrack(order, visited, indeg)
                order.pop()
                visited[i] = False
                for nb in adj[i]:
                    indeg[nb] += 1

    backtrack([], [False] * n, list(indegree))
    if not all_orders:
        all_orders.append(list(operations))
    return all_orders
