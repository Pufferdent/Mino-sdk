import pytest
from mino_sdk import Board, Cell


class TestBoardDimensions:
    def test_default_board_has_40_rows(self):
        board = Board()
        assert board.rows == 40

    def test_default_board_has_10_cols(self):
        board = Board()
        assert board.cols == 10

    def test_all_cells_initialized_empty(self):
        board = Board()
        for row in range(40):
            for col in range(10):
                assert board.get_cell(row, col) == Cell.EMPTY


class TestCellGetSet:
    def test_get_cell_returns_cell_value(self):
        board = Board()
        assert board.get_cell(0, 0) == Cell.EMPTY

    def test_set_cell_updates_value(self):
        board = Board()
        board.set_cell(0, 0, Cell.T)
        assert board.get_cell(0, 0) == Cell.T

    @pytest.mark.parametrize("cell_type", [
        Cell.EMPTY, Cell.T, Cell.I, Cell.L, Cell.J,
        Cell.S, Cell.Z, Cell.O, Cell.GARBAGE, Cell.SOLID,
    ])
    def test_set_and_get_all_cell_types(self, cell_type):
        board = Board()
        board.set_cell(5, 5, cell_type)
        assert board.get_cell(5, 5) == cell_type

    def test_set_cell_out_of_bounds_row_raises_error(self):
        board = Board()
        with pytest.raises(IndexError):
            board.set_cell(40, 0, Cell.T)

    def test_set_cell_out_of_bounds_col_raises_error(self):
        board = Board()
        with pytest.raises(IndexError):
            board.set_cell(0, 10, Cell.T)

    def test_set_cell_negative_row_raises_error(self):
        board = Board()
        with pytest.raises(IndexError):
            board.set_cell(-1, 0, Cell.T)

    def test_set_cell_negative_col_raises_error(self):
        board = Board()
        with pytest.raises(IndexError):
            board.set_cell(0, -1, Cell.T)

    def test_get_cell_out_of_bounds_raises_error(self):
        board = Board()
        with pytest.raises(IndexError):
            board.get_cell(40, 0)


class TestIsRowFull:
    def test_empty_row_not_full(self):
        board = Board()
        assert not board.is_row_full(0)

    def test_fully_filled_row_is_full(self):
        board = Board()
        for col in range(10):
            board.set_cell(0, col, Cell.T)
        assert board.is_row_full(0)

    def test_partially_filled_row_not_full(self):
        board = Board()
        for col in range(9):
            board.set_cell(0, col, Cell.T)
        assert not board.is_row_full(0)

    def test_row_with_garbage_is_full(self):
        board = Board()
        for col in range(10):
            board.set_cell(0, col, Cell.GARBAGE)
        assert board.is_row_full(0)

    def test_row_with_solid_is_full(self):
        board = Board()
        for col in range(10):
            board.set_cell(0, col, Cell.SOLID)
        assert board.is_row_full(0)

    def test_row_with_mixed_types_is_full(self):
        board = Board()
        for col in range(5):
            board.set_cell(0, col, Cell.T)
        for col in range(5, 10):
            board.set_cell(0, col, Cell.GARBAGE)
        assert board.is_row_full(0)


class TestClearLines:
    def test_clear_single_full_row(self):
        board = Board()
        for col in range(10):
            board.set_cell(5, col, Cell.T)
        cleared = board.clear_lines()
        assert cleared == 1
        assert all(board.get_cell(5, col) != Cell.T for col in range(10))
        for col in range(10):
            assert board.get_cell(39, col) == Cell.EMPTY

    def test_clear_multiple_full_rows(self):
        board = Board()
        for col in range(10):
            board.set_cell(3, col, Cell.T)
            board.set_cell(7, col, Cell.I)
        cleared = board.clear_lines()
        assert cleared == 2

    def test_no_rows_to_clear(self):
        board = Board()
        cleared = board.clear_lines()
        assert cleared == 0

    def test_row_with_solid_cell_not_cleared(self):
        board = Board()
        for col in range(10):
            board.set_cell(4, col, Cell.T)
        board.set_cell(4, 5, Cell.SOLID)
        cleared = board.clear_lines()
        assert cleared == 0
        assert board.get_cell(4, 0) == Cell.T

    def test_solid_row_prevents_clear_but_other_full_rows_still_clear(self):
        board = Board()
        for col in range(10):
            board.set_cell(3, col, Cell.O)
            board.set_cell(4, col, Cell.T)
        board.set_cell(4, 5, Cell.SOLID)
        cleared = board.clear_lines()
        assert cleared == 1


class TestStrRepr:
    def test_str_contains_rows_top_to_bottom(self):
        board = Board()
        board.set_cell(0, 0, Cell.T)
        output = str(board)
        lines = output.split("\n")
        assert len(lines) == 40

    def test_repr_equals_str(self):
        board = Board()
        assert repr(board) == str(board)

    def test_str_shows_piece_colors(self):
        board = Board()
        board.set_cell(0, 0, Cell.T)
        board.set_cell(0, 1, Cell.I)
        board.set_cell(0, 2, Cell.GARBAGE)
        board.set_cell(0, 3, Cell.SOLID)
        output = str(board)
        last_line = output.split("\n")[-1]
        assert last_line.startswith("TIGX")
