"""Apply fumen piece operations to reconstruct cumulative board state.

The SDK's :func:`decode_fumen` returns each page's encoded *field* plus the piece
*operation*, but a replay fumen is an operation stream: every page reuses the
prior field and encodes only the piece placed, so the decoded fields are empty.
To recover the board after each placement we replay the operations here.

Geometry follows the canonical fumen definitions (matching ``tetris-fumen``):
piece block offsets are ``(x, y)`` with ``y`` pointing up, the action's encoded
rotation is ``0=reverse, 1=right, 2=spawn, 3=left``, and the position decodes to
``x = n % 10``, ``y = 22 - n // 10`` with small per-piece corrections for O/I/S/Z
in particular rotations.
"""

from __future__ import annotations

# Fumen operation piece-type encoding (same as the field cell encoding):
# 1=I 2=L 3=O 4=Z 5=T 6=J 7=S; 0 = none, 8 = gray. This is distinct from the
# decoder's FUMEN_PIECE_TO_TYPE table, which is a different (page-mino) ordering.
_OP_TYPE_TO_LETTER = {1: "I", 2: "L", 3: "O", 4: "Z", 5: "T", 6: "J", 7: "S"}

_COLS = 10
_FIELD_ROWS = 24            # 0 = top
_FIELD_SIZE = _FIELD_ROWS * _COLS
_FIELD_TOP = 23

# Spawn block offsets (x, y) with y up; index 0 is the rotation origin.
_SPAWN_BLOCKS = {
    "I": [(0, 0), (-1, 0), (1, 0), (2, 0)],
    "T": [(0, 0), (-1, 0), (1, 0), (0, 1)],
    "O": [(0, 0), (1, 0), (0, 1), (1, 1)],
    "L": [(0, 0), (-1, 0), (1, 0), (1, 1)],
    "J": [(0, 0), (-1, 0), (1, 0), (-1, 1)],
    "S": [(0, 0), (-1, 0), (0, 1), (1, 1)],
    "Z": [(0, 0), (1, 0), (0, 1), (-1, 1)],
}

# raw encoded rotation -> name
_ROT_REVERSE, _ROT_RIGHT, _ROT_SPAWN, _ROT_LEFT = 0, 1, 2, 3

def _rotate(blocks, rot):
    if rot == _ROT_SPAWN:
        return blocks
    if rot == _ROT_RIGHT:
        return [(y, -x) for x, y in blocks]
    if rot == _ROT_LEFT:
        return [(-y, x) for x, y in blocks]
    return [(-x, -y) for x, y in blocks]  # reverse


def operation_cells(piece_type_raw: int, rotation_raw: int, position: int):
    """Return ``[(fumen_row, col), ...]`` cells occupied by a fumen operation.

    ``piece_type_raw``/``rotation_raw``/``position`` are the raw fields from
    :func:`decode_fumen`. ``fumen_row`` is 0 at the top (matching the decoded
    field array layout). Returns ``None`` when the operation places no mino.
    """
    if piece_type_raw not in _OP_TYPE_TO_LETTER:
        return None
    letter = _OP_TYPE_TO_LETTER[piece_type_raw]

    x = position % _COLS
    origin_y = position // _COLS
    y = _FIELD_TOP - origin_y - 1

    # per-piece coordinate corrections (from fumen's decodeCoordinate)
    if letter == "O":
        if rotation_raw == _ROT_LEFT:
            x += 1; y -= 1
        elif rotation_raw == _ROT_REVERSE:
            x += 1
        elif rotation_raw == _ROT_SPAWN:
            y -= 1
    elif letter == "I":
        if rotation_raw == _ROT_REVERSE:
            x += 1
        elif rotation_raw == _ROT_LEFT:
            y -= 1
    elif letter == "S":
        if rotation_raw == _ROT_SPAWN:
            y -= 1
        elif rotation_raw == _ROT_RIGHT:
            x -= 1
    elif letter == "Z":
        if rotation_raw == _ROT_SPAWN:
            y -= 1
        elif rotation_raw == _ROT_LEFT:
            x += 1

    blocks = _rotate(_SPAWN_BLOCKS[letter], rotation_raw)
    cells = []
    for dx, dy in blocks:
        cx, cy = x + dx, y + dy
        cells.append((_FIELD_TOP - 1 - cy, cx))  # y-up -> fumen_row (0 = top)
    return cells


def apply_operation(field: list[int], piece_type_raw: int, rotation_raw: int,
                    position: int) -> int:
    """Lock an operation onto ``field`` (mutated) and clear full rows.

    Returns the number of rows cleared. ``field`` is a flat 24x10 list, row 0 at
    the top, values per the fumen field encoding.
    """
    count, _, _ = apply_operation_detailed(
        field, piece_type_raw, rotation_raw, position)
    return count


# The PC window is the bottom four fumen rows 19..22 (top -> bottom).
_WINDOW_TOP = 19


def apply_operation_detailed(field, piece_type_raw, rotation_raw, position):
    """Lock an operation and clear full rows, returning per-clear detail.

    Returns ``(cleared_count, pre_window, cleared_window_rows)`` where
    ``pre_window`` is the 40-cell bottom-4 window (raw values, row 0 = top)
    *after placing but before clearing*, and ``cleared_window_rows`` lists the
    window-row indices (0 top .. 3 bottom) that cleared. ``field`` is mutated to
    the settled state.
    """
    cells = operation_cells(piece_type_raw, rotation_raw, position)
    if cells is None:
        window = _window_values(field)
        return 0, window, []
    val = piece_type_raw  # operation type value == field cell value
    for frow, col in cells:
        if 0 <= frow < _FIELD_ROWS and 0 <= col < _COLS:
            field[frow * _COLS + col] = val

    pre_window = _window_values(field)  # after place, before clear

    cleared = 0
    cleared_window_rows = []
    kept_rows = []
    for frow in range(_FIELD_ROWS):
        row = field[frow * _COLS:(frow + 1) * _COLS]
        if all(v != 0 for v in row):
            cleared += 1
            if _WINDOW_TOP <= frow <= _WINDOW_TOP + 3:
                cleared_window_rows.append(frow - _WINDOW_TOP)
        else:
            kept_rows.append(row)
    empty = _FIELD_ROWS - len(kept_rows)
    new_rows = [[0] * _COLS for _ in range(empty)] + kept_rows
    field[:] = [v for row in new_rows for v in row]
    return cleared, pre_window, sorted(cleared_window_rows)


def _window_values(field):
    vals = []
    for wr in range(4):
        base = (_WINDOW_TOP + wr) * _COLS
        vals.extend(field[base:base + _COLS])
    return vals
