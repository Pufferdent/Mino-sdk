from mino_sdk.board import Board
from mino_sdk.types import Cell
from mino_sdk.fumen.decoder import decode_fumen, FUMEN_VISIBLE_ROWS, FUMEN_COLS, FUMEN_TO_CELL

BOARD_ROWS = 40
FUMEN_DATA_ROWS = FUMEN_VISIBLE_ROWS - 1


def parse_fumen(fumen_str: str) -> list[Board]:
    pages = decode_fumen(fumen_str)
    boards: list[Board] = []

    for page in pages:
        board = Board()

        field = page["field"]

        for fumen_row in range(FUMEN_DATA_ROWS):
            board_row = FUMEN_DATA_ROWS - 1 - fumen_row
            for col in range(FUMEN_COLS):
                fumen_val = field[fumen_row * FUMEN_COLS + col]
                if fumen_val > 8:
                    fumen_val = 8
                cell_val = FUMEN_TO_CELL[fumen_val]
                board.set_cell(board_row, col, Cell(cell_val))

        boards.append(board)

    return boards
