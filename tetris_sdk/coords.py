from tetris_sdk.fumen.decoder import FUMEN_VISIBLE_ROWS, FUMEN_COLS


def fumen_row_to_board_row(fumen_row: int) -> int:
    return FUMEN_VISIBLE_ROWS - 1 - fumen_row


def board_row_to_fumen_row(board_row: int) -> int:
    return FUMEN_VISIBLE_ROWS - 1 - board_row


def fumen_position_to_row_col(position: int) -> tuple[int, int]:
    row = position // FUMEN_COLS
    col = position % FUMEN_COLS
    return row, col


def fumen_position_to_board_row_col(position: int) -> tuple[int, int]:
    fumen_row, col = fumen_position_to_row_col(position)
    board_row = fumen_row_to_board_row(fumen_row)
    return board_row, col
