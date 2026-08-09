from dataclasses import dataclass, field

from tetris_sdk.board import Board
from tetris_sdk.fumen.decoder import (
    decode_fumen,
    FUMEN_VISIBLE_ROWS,
    FUMEN_COLS,
    FUMEN_TO_CELL,
)
from tetris_sdk.types import Cell


FUMEN_DATA_ROWS = FUMEN_VISIBLE_ROWS - 1


def _field_to_board(field: list[int], color: bool) -> Board:
    board = Board()
    for fumen_row in range(FUMEN_DATA_ROWS):
        board_row = FUMEN_DATA_ROWS - 1 - fumen_row
        for col in range(FUMEN_COLS):
            fumen_val = field[fumen_row * FUMEN_COLS + col]
            if color:
                if fumen_val == 0:
                    cell_val = Cell.EMPTY
                elif fumen_val >= 8:
                    cell_val = Cell.GARBAGE
                else:
                    cell_val = FUMEN_TO_CELL[fumen_val]
            else:
                if fumen_val > 8:
                    fumen_val = 8
                cell_val = FUMEN_TO_CELL[fumen_val]
            board.set_cell(board_row, col, Cell(cell_val))
    return board


@dataclass
class Page:
    board: Board
    comment: str = ""


@dataclass
class MultiFumenPage:
    pages: list[Page] = field(default_factory=list)

    @classmethod
    def from_string(cls, fumen_str: str) -> "MultiFumenPage":
        raw_pages = decode_fumen(fumen_str)
        pages: list[Page] = []
        for raw in raw_pages:
            board = _field_to_board(raw["field"], raw["piece"]["color"])
            comment = raw["comment"]
            pages.append(Page(board=board, comment=comment))
        return cls(pages=pages)
