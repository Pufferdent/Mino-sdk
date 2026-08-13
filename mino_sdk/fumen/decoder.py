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
    """Read one page's field as a delta applied to the previous page's field.

    A page whose field is identical to the previous one is not written out as
    240 zero deltas: it is written as the single marker block ``cell_delta ==
    8, run_len == field_size - 1`` — a run covering the whole field at delta
    zero — and the *count of further pages that repeat it* follows the block
    as one more index. Reading that count as if it were field data desyncs
    every page after it, which is what a diagram of unchanged annotation
    pages hits immediately.
    """
    field = list(prev) if prev is not None else [0] * field_size
    changed = True

    j = 0
    while j < field_size:
        v = indices[offset] + indices[offset + 1] * 64
        offset += 2

        run_len = v % field_size
        # Not reduced mod 17: a legal delta is 0-16 (-8 to +8 once shifted),
        # and folding 17 back onto 0 turns an overflowing read into a
        # plausible-looking one instead of letting it surface.
        cell_delta = v // field_size

        if cell_delta == 8 and run_len == field_size - 1:
            changed = False

        for _ in range(run_len + 1):
            # Deliberately unmasked. Values are 0-8 and stay there when the
            # stream is read correctly; masking to a byte turns a decode error
            # into 248-255 garbage that silently poisons every later page.
            field[j] = field[j] + cell_delta - 8
            j += 1

    fldrepcnt = 0
    if not changed:
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
    # Inverted on the wire: the bit is *set* to suppress locking, so a page
    # that locks writes 0 here. Reading it straight makes every ordinary page
    # look like a no-lock page, and the line clears a lock triggers are then
    # never applied to the field the next page's delta builds on.
    lock = not (v % 2)

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


# Cell offsets from a piece's origin at spawn, in (x, y) with y pointing up.
_SPAWN_CELLS = {
    1: ((0, 0), (-1, 0), (1, 0), (2, 0)),    # I
    2: ((0, 0), (-1, 0), (1, 0), (1, 1)),    # L
    3: ((0, 0), (1, 0), (0, 1), (1, 1)),     # O
    4: ((0, 0), (1, 0), (0, 1), (-1, 1)),    # Z
    5: ((0, 0), (-1, 0), (1, 0), (0, 1)),    # T
    6: ((0, 0), (-1, 0), (1, 0), (-1, 1)),   # J
    7: ((0, 0), (-1, 0), (0, 1), (1, 1)),    # S
}

# Fumen numbers rotations in its own order, not the usual spawn-first one.
_REVERSE, _RIGHT, _SPAWN, _LEFT = 0, 1, 2, 3

# Where fumen's stored origin sits away from the piece's own, per shape and
# rotation. Only these combinations are offset; everything else is exact.
_ORIGIN_FIX = {
    (3, _LEFT): (1, -1), (3, _REVERSE): (1, 0), (3, _SPAWN): (0, -1),   # O
    (1, _REVERSE): (1, 0), (1, _LEFT): (0, -1),                          # I
    (7, _SPAWN): (0, -1), (7, _RIGHT): (-1, 0),                          # S
    (4, _SPAWN): (0, -1), (4, _LEFT): (1, 0),                            # Z
}


def _piece_cells(piece_type: int, rotation: int, position: int) -> list[tuple[int, int]]:
    """The four (x, y) cells a locked piece occupies, y counting up from 0."""
    cells = _SPAWN_CELLS[piece_type]
    if rotation == _RIGHT:
        cells = tuple((y, -x) for x, y in cells)
    elif rotation == _LEFT:
        cells = tuple((-y, x) for x, y in cells)
    elif rotation == _REVERSE:
        cells = tuple((-x, -y) for x, y in cells)

    x = position % FUMEN_COLS
    y = FUMEN_VISIBLE_ROWS - 1 - position // FUMEN_COLS - 1
    dx, dy = _ORIGIN_FIX.get((piece_type, rotation), (0, 0))
    x, y = x + dx, y + dy
    return [(x + cx, y + cy) for cx, cy in cells]


def _fill_piece(field: list[int], piece: dict) -> list[int]:
    """Stamp a locked mino into the field it settles on."""
    out = list(field)
    for x, y in _piece_cells(piece["type"], piece["rotation"], piece["position"]):
        row = FUMEN_VISIBLE_ROWS - 2 - y
        if 0 <= row < FUMEN_VISIBLE_ROWS and 0 <= x < FUMEN_COLS:
            out[row * FUMEN_COLS + x] = piece["type"]
    return out


def _clear_lines(field: list[int], field_size: int) -> list[int]:
    """The field a locking page leaves behind: full rows gone, stack dropped.

    The last row is fumen's garbage row, which sits below the playfield and
    never clears, so it is held out of the shift and put back underneath.
    """
    playfield = field[:field_size - FUMEN_COLS]
    garbage = field[field_size - FUMEN_COLS:]

    rows = [playfield[i:i + FUMEN_COLS] for i in range(0, len(playfield), FUMEN_COLS)]
    kept = [row for row in rows if any(cell == 0 for cell in row)]
    empty = [[0] * FUMEN_COLS for _ in range(len(rows) - len(kept))]

    out: list[int] = []
    for row in empty + kept:
        out.extend(row)
    return out + garbage


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

        # A locking page settles before the next page's delta is applied to it:
        # the mino is stamped, full rows vanish, and the stack drops. The page
        # itself still reports the field as drawn, so only what carries forward
        # is affected -- but every later page is a delta on this, so skipping it
        # silently corrupts the whole rest of the fumen rather than one page.
        if piece["lock"]:
            if piece["rise"] or piece["mirror"]:
                raise NotImplementedError(
                    "decoding a fumen that uses the rise or mirror flag is not "
                    "supported: both transform the field that carries forward"
                )
            settled = _fill_piece(field, piece) if piece["type"] else field
            prev_field = _clear_lines(settled, field_size)

    return pages
