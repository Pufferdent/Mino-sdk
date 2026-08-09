from mino_sdk.pieces import PieceType

FUMEN_TABLE = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"

FUMEN_VISIBLE_ROWS = 24
FUMEN_COLS = 10

FUMEN_TO_CELL: list[int] = [0, 2, 3, 7, 6, 1, 4, 5, 8]

FUMEN_PIECE_TO_TYPE: dict[int, PieceType] = {
    0: PieceType.I,
    1: PieceType.L,
    2: PieceType.O,
    3: PieceType.Z,
    4: PieceType.T,
    5: PieceType.J,
    6: PieceType.S,
}
TYPE_TO_FUMEN_PIECE: dict[PieceType, int] = {v: k for k, v in FUMEN_PIECE_TO_TYPE.items()}


def _decode_base64(data: str) -> list[int]:
    indices = []
    for ch in data:
        idx = FUMEN_TABLE.index(ch)
        indices.append(idx)
    return indices


def _read_field(
    indices: list[int], offset: int, field_size: int, prev: list[int] | None = None
) -> tuple[list[int], int, int]:
    """Read one page's field as a delta applied to the previous page's field."""
    field = list(prev) if prev is not None else [0] * field_size
    fldrepcnt = 0

    j = 0
    while j < field_size:
        v = indices[offset] + indices[offset + 1] * 64
        offset += 2

        run_len = v % field_size
        cell_delta = (v // field_size) % 17

        for _ in range(run_len + 1):
            field[j] = (field[j] + cell_delta - 8) & 0xFF
            j += 1

        if cell_delta * field_size + run_len == 9 * field_size - 1:
            fldrepcnt = indices[offset]
            offset += 1

    return field, offset, fldrepcnt


def _read_piece(indices: list[int], offset: int, field_size: int, is_first: bool) -> tuple[dict, int]:
    v = indices[offset] + indices[offset + 1] * 64 + indices[offset + 2] * 4096
    offset += 3

    piece_type = v % 8
    v //= 8
    rotation = v % 4
    v //= 4
    position = v % field_size
    v //= field_size
    rise = v % 2
    v //= 2
    mirror = v % 2
    v //= 2
    # The color bit is encoded on every page (matching the encoder and the
    # reference fumen.js), not just the first; consuming it only on page 0 used
    # to mis-align comment_flag/lock on later pages of multi-page fumens.
    color = v % 2
    v //= 2
    comment_flag = v % 2
    v //= 2
    lock = v % 2

    return {
        "type": piece_type,
        "rotation": rotation,
        "position": position,
        "rise": bool(rise),
        "mirror": bool(mirror),
        "color": bool(color),
        "comment_flag": bool(comment_flag),
        "lock": bool(lock),
    }, offset


def _read_comment(indices: list[int], offset: int) -> tuple[str, int]:
    v = indices[offset] + indices[offset + 1] * 64
    offset += 2
    length = v % 4096

    ascii_table = ' !"#$%&\'()*+,-./0123456789:;<=>?@ABCDEFGHIJKLMNOPQRSTUVWXYZ[\\]^_`abcdefghijklmnopqrstuvwxyz{|}~'

    chars = []
    i = 0
    while i < length:
        v = (indices[offset] + indices[offset + 1] * 64 +
             indices[offset + 2] * 4096 + indices[offset + 3] * 262144 +
             indices[offset + 4] * 16777216)
        offset += 5
        for _ in range(4):
            if i < length:
                chars.append(ascii_table[v % 96])
                i += 1
            v //= 96

    comment = "".join(chars)
    comment = _decode_escaped(comment)
    return comment, offset


def _decode_escaped(s: str) -> str:
    """Reverse fumen's escaping: ``%XX`` for latin-1, ``%uXXXX`` beyond it."""
    result = []
    i = 0
    while i < len(s):
        if s[i] == "%" and s[i + 1:i + 2] == "u" and i + 6 <= len(s):
            try:
                result.append(chr(int(s[i + 2:i + 6], 16)))
                i += 6
                continue
            except ValueError:
                pass
        if s[i] == "%" and i + 3 <= len(s):
            try:
                result.append(chr(int(s[i + 1:i + 3], 16)))
                i += 3
                continue
            except ValueError:
                pass
        result.append(s[i])
        i += 1
    return "".join(result)


def decode_fumen(fumen_str: str) -> list[dict]:
    at_idx = fumen_str.find("@")
    if at_idx < 0:
        raise ValueError("Invalid fumen string: missing '@' separator")

    version = fumen_str[:at_idx]
    if version != "v115":
        raise ValueError(f"Unsupported fumen version: {version}. Only v115 is supported.")

    data_part = fumen_str[at_idx + 1:]

    data_part = data_part.replace("?", "")

    indices = _decode_base64(data_part)

    field_size = FUMEN_VISIBLE_ROWS * FUMEN_COLS
    offset = 0
    pages = []
    page_index = 0

    fldrepcnt = 0
    prev_field = [0] * field_size

    while offset < len(indices):
        if fldrepcnt < 1:
            field, offset, fldrepcnt = _read_field(
                indices, offset, field_size, prev_field
            )
        else:
            fldrepcnt -= 1
            field = prev_field.copy()
        prev_field = field.copy()

        piece, offset = _read_piece(indices, offset, field_size, page_index == 0)
        comment = ""
        if piece["comment_flag"]:
            comment, offset = _read_comment(indices, offset)

        pages.append({
            "field": field,
            "piece": piece,
            "comment": comment,
        })
        page_index += 1

    return pages
