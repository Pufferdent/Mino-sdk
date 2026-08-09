import pytest
from mino_sdk import Board, board_from_string, board_to_string, Cell, Piece, PieceType


class TestBoardToString:
    def test_empty_board(self):
        s = board_to_string(Board())
        assert s == "N" * 40

    def test_garbage_in_bottom_row(self):
        board = Board()
        board.set_cell(0, 0, Cell.GARBAGE)
        s = board_to_string(board)
        assert s[30] == "X"

    def test_garbage_in_top_of_window(self):
        board = Board()
        board.set_cell(3, 0, Cell.GARBAGE)
        s = board_to_string(board)
        assert s[0] == "X"

    def test_piece_colors(self):
        board = Board()
        board.set_cell(2, 5, Cell.T)
        board.set_cell(1, 3, Cell.L)
        s = board_to_string(board)
        assert s[15] == "T"
        assert s[23] == "L"

    def test_solid_maps_to_x(self):
        board = Board()
        board.set_cell(0, 9, Cell.SOLID)
        s = board_to_string(board)
        assert s[39] == "X"


class TestBoardFromString:
    def test_empty_string(self):
        board = board_from_string("N" * 40)
        for row in range(4):
            for col in range(10):
                assert board.get_cell(row, col) == Cell.EMPTY

    def test_garbage_everywhere(self):
        board = board_from_string("X" * 40)
        for row in range(4):
            for col in range(10):
                assert board.get_cell(row, col) == Cell.GARBAGE

    def test_coordinate_mapping(self):
        s = (
            "XXXXXXXXXX"
            "NNNNNNNNNN"
            "NNNNNNNNNN"
            "NNNNNNNNNN"
        )
        board = board_from_string(s)
        assert board.get_cell(3, 0) == Cell.GARBAGE
        assert board.get_cell(2, 0) == Cell.EMPTY

    def test_invalid_length_raises(self):
        with pytest.raises(ValueError, match="40"):
            board_from_string("NN")

    def test_invalid_character_raises(self):
        with pytest.raises(ValueError, match="Invalid"):
            board_from_string("Q" * 40)


class TestBoardStringRoundTrip:
    def test_round_trip_empty(self):
        s = "N" * 40
        assert board_to_string(board_from_string(s)) == s

    def test_round_trip_with_pieces(self):
        s = "XXXXXXNNNXNNNXXNNNNXNNXXNNNNNXNNNXXNNNNX"
        assert board_to_string(board_from_string(s)) == s

    def test_all_piece_types(self):
        board = Board()
        for i, pt in enumerate([PieceType.T, PieceType.I, PieceType.L,
                                 PieceType.J, PieceType.S, PieceType.Z,
                                 PieceType.O]):
            board.set_cell(1, i, pt.cell)
        s = board_to_string(board)
        assert board_to_string(board_from_string(s)) == s
