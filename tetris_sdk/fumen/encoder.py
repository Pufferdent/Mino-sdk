from tetris_sdk.board import Board
from tetris_sdk.fumen.decoder import (
    FUMEN_TABLE,
    FUMEN_VISIBLE_ROWS,
    FUMEN_COLS,
    FUMEN_TO_CELL,
    decode_fumen,
)
from tetris_sdk.types import Cell

FUMEN_DATA_ROWS = FUMEN_VISIBLE_ROWS - 1
FIELD_SIZE = FUMEN_VISIBLE_ROWS * FUMEN_COLS

CELL_TO_FUMEN: dict[Cell, int] = {
    Cell.EMPTY: 0,
    Cell.T: 5,
    Cell.I: 1,
    Cell.L: 2,
    Cell.J: 6,
    Cell.S: 7,
    Cell.Z: 4,
    Cell.O: 3,
    Cell.GARBAGE: 8,
    Cell.SOLID: 8,
}
for k, v in CELL_TO_FUMEN.items():
    fumen_cell = FUMEN_TO_CELL[v]
    if k == Cell.SOLID:
        assert fumen_cell == Cell.GARBAGE.value, f"CELL_TO_FUMEN mapping mismatch for {k}"
    else:
        assert fumen_cell == k.value, f"CELL_TO_FUMEN mapping mismatch for {k}"


def _board_to_field(board: Board) -> list[int]:
    field = [0] * FIELD_SIZE
    for fumen_row in range(FUMEN_DATA_ROWS):
        board_row = FUMEN_DATA_ROWS - 1 - fumen_row
        for col in range(FUMEN_COLS):
            cell = board.get_cell(board_row, col)
            fumen_val = CELL_TO_FUMEN.get(cell, 8)
            field[fumen_row * FUMEN_COLS + col] = fumen_val
    return field


def _encode_field(field: list[int], prev: list[int]) -> list[int]:
    """Encode ``field`` as a run-length delta against the previous page's field.

    Every page after the first is a diff from the page before it, not from an
    empty board — see ``FieldEncoder(prevField, ...)`` in the reference decoder.
    A run covering the whole field with no change is the format's "unchanged"
    sentinel and must be followed by a repeat count.
    """
    indices: list[int] = []
    current = list(prev)
    j = 0
    while j < FIELD_SIZE:
        target = field[j]
        if target != current[j]:
            delta = target - current[j]
            count = 1
            while j + count < FIELD_SIZE:
                if field[j + count] != current[j + count] + delta:
                    break
                count += 1
        else:
            delta = 0
            count = 1
            while j + count < FIELD_SIZE and field[j + count] == current[j + count]:
                count += 1

        cell_delta = delta + 8
        run_len = count - 1
        v = cell_delta * FIELD_SIZE + run_len

        indices.append(v % 64)
        indices.append(v // 64)
        if v == 9 * FIELD_SIZE - 1:
            # Whole field unchanged: the sentinel takes a repeat count. Zero
            # means no further pages share this field.
            indices.append(0)

        for i in range(count):
            current[j + i] += delta
        j += count

    return indices


def _encode_piece(
    fumen_piece_type: int = 0,
    rotation: int = 0,
    position: int = 0,
    rise: bool = False,
    mirror: bool = False,
    color: bool = False,
    comment_flag: bool = False,
    lock: bool = False,
) -> list[int]:
    v = fumen_piece_type
    v += rotation * 8
    v += position * 32
    v += int(rise) * (32 * FIELD_SIZE)
    v += int(mirror) * (2 * 32 * FIELD_SIZE)
    v += int(color) * (4 * 32 * FIELD_SIZE)
    v += int(comment_flag) * (8 * 32 * FIELD_SIZE)
    v += int(lock) * (16 * 32 * FIELD_SIZE)

    return [v % 64, (v // 64) % 64, (v // 4096) % 64]


_ASCII_TABLE = ' !"#$%&\'()*+,-./0123456789:;<=>?@ABCDEFGHIJKLMNOPQRSTUVWXYZ[\\]^_`abcdefghijklmnopqrstuvwxyz{|}~'
_ASCII_TO_INDEX: dict[str, int] = {c: i for i, c in enumerate(_ASCII_TABLE)}


# Characters fumen leaves unescaped. This is deliberately *narrower* than
# _ASCII_TABLE: the comment table says which characters can be stored, this says
# which survive escaping. A conformant decoder rejects any other raw character,
# so escaping against the wrong set produces comments other tools cannot read.
_UNESCAPED = frozenset(
    "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789 @*_+-./"
)

_MAX_COMMENT = 4095


def _encode_escaped(s: str) -> str:
    result: list[str] = []
    for ch in s:
        if ch in _UNESCAPED:
            result.append(ch)
        elif ord(ch) < 256:
            result.append(f"%{ord(ch):02X}")
        else:
            result.append(f"%u{ord(ch):04X}")
    return "".join(result)


def _encode_comment(comment: str) -> list[int]:
    escaped = _encode_escaped(comment)[:_MAX_COMMENT]
    length = len(escaped)
    indices = [length % 64, (length // 64) % 64]

    encoded: list[int] = []
    for ch in escaped:
        if ch in _ASCII_TO_INDEX:
            encoded.append(_ASCII_TO_INDEX[ch])
        else:
            encoded.append(0)

    i = 0
    while i < len(encoded):
        v = 0
        for k in range(4):
            if i + k < len(encoded):
                v += encoded[i + k] * (96 ** k)
        indices.append(v % 64)
        indices.append((v // 64) % 64)
        indices.append((v // 4096) % 64)
        indices.append((v // 262144) % 64)
        indices.append((v // 16777216) % 64)
        i += 4

    return indices


def _encode_base64(indices: list[int]) -> str:
    return "".join(FUMEN_TABLE[idx] for idx in indices)


def encode_fumen(pages: list[tuple[Board, str]]) -> str:
    all_indices: list[int] = []

    prev_field = [0] * FIELD_SIZE

    for page_index, (board, comment) in enumerate(pages):
        field = _board_to_field(board)
        all_indices.extend(_encode_field(field, prev_field))
        # No piece is written and lock is false, so the reference decoder
        # neither locks a mino nor clears lines: the field carries over as-is.
        prev_field = field

        has_comment = len(comment) > 0
        all_indices.extend(_encode_piece(
            color=(page_index == 0),
            comment_flag=has_comment,
        ))

        if has_comment:
            all_indices.extend(_encode_comment(comment))

    encoded = _encode_base64(all_indices)

    return f"v115@{encoded}"
