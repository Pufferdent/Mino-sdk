from __future__ import annotations

from typing import TYPE_CHECKING

from tetris_sdk.types import Cell

if TYPE_CHECKING:
    from tetris_sdk.pieces import Piece
    from tetris_sdk.engine import SpinType
    from tetris_sdk.events import Event, B2BRule

ROWS = 40
COLS = 10
PC_STRING_ROWS = 4

_CELL_TO_CHAR: dict[Cell, str] = {
    Cell.EMPTY: "N",
    Cell.T: "T",
    Cell.I: "I",
    Cell.L: "L",
    Cell.J: "J",
    Cell.S: "S",
    Cell.Z: "Z",
    Cell.O: "O",
    Cell.GARBAGE: "X",
    Cell.SOLID: "X",
}

_CHAR_TO_CELL: dict[str, Cell] = {
    "N": Cell.EMPTY,
    "T": Cell.T,
    "I": Cell.I,
    "L": Cell.L,
    "J": Cell.J,
    "S": Cell.S,
    "Z": Cell.Z,
    "O": Cell.O,
    "X": Cell.GARBAGE,
}


def board_to_string(board: Board) -> str:
    chars: list[str] = []
    for pc_row in range(PC_STRING_ROWS):
        board_row = PC_STRING_ROWS - 1 - pc_row
        for col in range(COLS):
            chars.append(_CELL_TO_CHAR[board.get_cell(board_row, col)])
    return "".join(chars)


def board_from_string(s: str) -> Board:
    if len(s) != PC_STRING_ROWS * COLS:
        raise ValueError(
            f"Board string must be {PC_STRING_ROWS * COLS} characters, got {len(s)}"
        )
    board = Board()
    for pc_row in range(PC_STRING_ROWS):
        board_row = PC_STRING_ROWS - 1 - pc_row
        for col in range(COLS):
            ch = s[pc_row * COLS + col]
            if ch not in _CHAR_TO_CELL:
                raise ValueError(f"Invalid board string character: {ch!r}")
            board.set_cell(board_row, col, _CHAR_TO_CELL[ch])
    return board


class Board:
    def __init__(self, b2b_rule: "B2BRule | None" = None) -> None:
        self._grid: list[list[Cell]] = [
            [Cell.EMPTY for _ in range(COLS)] for _ in range(ROWS)
        ]
        if b2b_rule is None:
            from tetris_sdk.events import B2BRule
            b2b_rule = B2BRule.S2
        self.b2b_rule: "B2BRule" = b2b_rule
        self.b2b: int = 0
        self.combo: int = 0

    @classmethod
    def from_fumen(cls, fumen_str: str) -> "Board":
        from tetris_sdk.fumen.parser import parse_fumen
        boards = parse_fumen(fumen_str)
        if not boards:
            raise ValueError("Fumen string produced no boards")
        return boards[0]

    @property
    def rows(self) -> int:
        return ROWS

    @property
    def cols(self) -> int:
        return COLS

    def get_cell(self, row: int, col: int) -> Cell:
        if not (0 <= row < ROWS and 0 <= col < COLS):
            raise IndexError(f"Cell position ({row}, {col}) out of bounds")
        return self._grid[row][col]

    def set_cell(self, row: int, col: int, value: Cell) -> None:
        if not (0 <= row < ROWS and 0 <= col < COLS):
            raise IndexError(f"Cell position ({row}, {col}) out of bounds")
        self._grid[row][col] = value

    def can_place(self, piece: "Piece") -> bool:
        """True iff every cell the piece occupies is in-bounds and EMPTY."""
        for row, col in piece.cells:
            if not (0 <= row < ROWS and 0 <= col < COLS):
                return False
            if self._grid[row][col] != Cell.EMPTY:
                return False
        return True

    def place(self, piece: "Piece") -> None:
        """Lock the piece onto the board, setting each cell to its color.

        Raises ``ValueError`` if the placement is invalid.
        """
        if not self.can_place(piece):
            raise ValueError(f"Cannot place piece {piece.type.name} at "
                             f"({piece.row}, {piece.col}) rotation {piece.rotation}")
        value = piece.type.cell
        for row, col in piece.cells:
            self._grid[row][col] = value

    def lock(self, piece: "Piece", spin: "SpinType | None" = None) -> "Event":
        """Lock ``piece``, clear lines, and return the classified ``Event``.

        Updates the running ``b2b``/``combo`` state using the board's
        ``b2b_rule``. The spin is taken from the argument (defaulting to no
        spin) and is never recomputed — the board has no move history. Raises
        ``ValueError`` (leaving running state unchanged) on an invalid
        placement.
        """
        from tetris_sdk.engine import SpinType
        from tetris_sdk.events import (
            Event, EventKind, classify_lock, is_difficult,
        )

        if spin is None:
            spin = SpinType.NONE
        self.place(piece)  # raises before mutating if invalid
        lines = self.clear_lines()
        kind, name = classify_lock(piece.type, spin, lines)
        difficult = is_difficult(piece.type, spin, lines, self.b2b_rule)

        if lines == 0:
            self.combo = 0
            back_to_back = False
        else:
            self.combo += 1
            if difficult:
                back_to_back = self.b2b > 0
                self.b2b += 1
            else:
                self.b2b = 0
                back_to_back = False

        perfect_clear = not any(
            cell != Cell.EMPTY for row in self._grid for cell in row
        )
        return Event(
            kind=kind,
            piece=piece.type,
            spin=spin,
            lines=lines,
            name=name,
            difficult=difficult,
            back_to_back=back_to_back,
            b2b=self.b2b,
            combo=self.combo,
            perfect_clear=perfect_clear,
        )

    def is_row_full(self, row: int) -> bool:
        return all(cell != Cell.EMPTY for cell in self._grid[row])

    def clear_lines(self) -> int:
        new_grid: list[list[Cell]] = []
        cleared = 0
        for row in self._grid:
            if all(cell != Cell.EMPTY for cell in row) and Cell.SOLID not in row:
                cleared += 1
            else:
                new_grid.append(row)
        while len(new_grid) < ROWS:
            new_grid.append([Cell.EMPTY for _ in range(COLS)])
        self._grid = new_grid
        return cleared

    def __str__(self) -> str:
        glyphs = {Cell.EMPTY: ".", Cell.T: "T", Cell.I: "I", Cell.L: "L",
                   Cell.J: "J", Cell.S: "S", Cell.Z: "Z", Cell.O: "O",
                   Cell.GARBAGE: "G", Cell.SOLID: "X"}
        lines = ["".join(glyphs[c] for c in row) for row in reversed(self._grid)]
        return "\n".join(lines)

    def __repr__(self) -> str:
        return self.__str__()
