import pytest
from tetris_sdk import Board, Cell, PieceType, Piece
from tetris_sdk.fumen.encoder import encode_fumen
from tetris_sdk.fumen.decoder import decode_fumen
from tetris_sdk.fumen.multi_fumen import MultiFumenPage
from tetris_sdk.fumen.parser import parse_fumen


def _board_cells_match(a: Board, b: Board) -> bool:
    for row in range(40):
        for col in range(10):
            if a.get_cell(row, col) != b.get_cell(row, col):
                return False
    return True


class TestEncodeFumenSingle:
    def test_empty_board_round_trip(self):
        board = Board()
        fumen = encode_fumen([(board, "")])
        decoded_pages = decode_fumen(fumen)
        assert len(decoded_pages) == 1
        assert set(decoded_pages[0]["field"]) == {0}

    def test_empty_board_via_parse_fumen(self):
        board = Board()
        fumen = encode_fumen([(board, "")])
        boards = parse_fumen(fumen)
        assert len(boards) == 1
        assert _board_cells_match(boards[0], board)

    def test_single_cell_round_trip(self):
        board = Board()
        board.set_cell(0, 5, Cell.T)
        fumen = encode_fumen([(board, "")])
        boards = parse_fumen(fumen)
        assert boards[0].get_cell(0, 5) == Cell.T

    def test_multiple_cell_types(self):
        board = Board()
        board.set_cell(0, 0, Cell.I)
        board.set_cell(1, 2, Cell.L)
        board.set_cell(2, 4, Cell.O)
        board.set_cell(3, 6, Cell.GARBAGE)
        fumen = encode_fumen([(board, "")])
        boards = parse_fumen(fumen)
        assert boards[0].get_cell(0, 0) == Cell.I
        assert boards[0].get_cell(1, 2) == Cell.L
        assert boards[0].get_cell(2, 4) == Cell.O
        assert boards[0].get_cell(3, 6) == Cell.GARBAGE

    def test_garbage_cell(self):
        board = Board()
        board.set_cell(3, 9, Cell.GARBAGE)
        fumen = encode_fumen([(board, "")])
        boards = parse_fumen(fumen)
        assert boards[0].get_cell(3, 9) == Cell.GARBAGE

    def test_solid_cell_maps_to_garbage(self):
        board = Board()
        board.set_cell(3, 0, Cell.SOLID)
        fumen = encode_fumen([(board, "")])
        boards = parse_fumen(fumen)
        assert boards[0].get_cell(3, 0) == Cell.GARBAGE

    def test_all_piece_types(self):
        board = Board()
        pieces = [PieceType.T, PieceType.I, PieceType.L, PieceType.J,
                   PieceType.S, PieceType.Z, PieceType.O]
        for i, pt in enumerate(pieces):
            board.set_cell(1, i, pt.cell)
        fumen = encode_fumen([(board, "")])
        boards = parse_fumen(fumen)
        for i, pt in enumerate(pieces):
            assert boards[0].get_cell(1, i) == pt.cell

    def test_comment_empty(self):
        board = Board()
        fumen = encode_fumen([(board, "")])
        mf = MultiFumenPage.from_string(fumen)
        assert mf.pages[0].comment == ""

    def test_version_prefix(self):
        board = Board()
        fumen = encode_fumen([(board, "")])
        assert fumen.startswith("v115@")


class TestEncodeFumenMulti:
    def test_two_pages_distinct_boards(self):
        board1 = Board()
        board1.set_cell(0, 0, Cell.T)
        board2 = Board()
        board2.set_cell(0, 1, Cell.I)
        fumen = encode_fumen([(board1, ""), (board2, "")])
        boards = parse_fumen(fumen)
        assert len(boards) == 2
        assert boards[0].get_cell(0, 0) == Cell.T
        assert boards[1].get_cell(0, 1) == Cell.I

    def test_three_pages(self):
        boards_in = [Board() for _ in range(3)]
        boards_in[0].set_cell(0, 0, Cell.T)
        boards_in[1].set_cell(0, 1, Cell.I)
        boards_in[2].set_cell(0, 2, Cell.O)
        fumen = encode_fumen([(b, "") for b in boards_in])
        boards_out = parse_fumen(fumen)
        assert len(boards_out) == 3


# --- comment escaping -------------------------------------------------------

def test_escaping_matches_the_fumen_unescaped_set():
    """Only A-Za-z0-9, space and ``@*_+-./`` survive raw; the rest are %-escaped.

    A conformant decoder throws on any other raw character, so escaping against
    the wider comment table produced comments other tools could not read.
    """
    from tetris_sdk.fumen.encoder import _encode_escaped
    assert _encode_escaped("PCO 1/7 a-b.c") == "PCO 1/7 a-b.c"
    assert _encode_escaped("a,b") == "a%2Cb"
    assert _encode_escaped("(hi!)") == "%28hi%21%29"
    assert _encode_escaped("50%") == "50%25"


def test_non_latin1_uses_the_u_form():
    from tetris_sdk.fumen.encoder import _encode_escaped
    assert _encode_escaped("あ") == "%u3042"


def test_comments_round_trip_through_encode_and_decode():
    from tetris_sdk.board import Board
    from tetris_sdk.fumen.encoder import encode_fumen
    from tetris_sdk.fumen.decoder import decode_fumen
    for comment in ["", "PCO", "01/20 JILOZST 1/7", "a,b (c)! 50%", "T-Spin: 100%", "あ"]:
        pages = decode_fumen(encode_fumen([(Board(), comment)]))
        assert pages[0]["comment"] == comment, comment


def test_an_overlong_comment_is_truncated_not_wrapped():
    from tetris_sdk.board import Board
    from tetris_sdk.fumen.encoder import encode_fumen
    from tetris_sdk.fumen.decoder import decode_fumen
    pages = decode_fumen(encode_fumen([(Board(), "x" * 5000)]))
    assert pages[0]["comment"] == "x" * 4095


# --- multi-page field deltas ------------------------------------------------

def test_empty_board_matches_the_canonical_fumen():
    """The all-blank field is the format's "unchanged" sentinel plus a repeat count."""
    from tetris_sdk.board import Board
    from tetris_sdk.fumen.encoder import encode_fumen
    assert encode_fumen([(Board(), "")]) == "v115@vhAAgH"


def test_pages_encode_as_deltas_from_the_previous_page():
    """Page N diffs against page N-1, not against an empty board."""
    from tetris_sdk.board import Board
    from tetris_sdk.fumen.encoder import encode_fumen
    from tetris_sdk.types import Cell

    def row(n):
        b = Board()
        for c in range(n):
            b.set_cell(0, c, Cell.GARBAGE)
        return b

    one = encode_fumen([(row(3), "")])
    two = encode_fumen([(row(3), ""), (row(3), "")])
    # An unchanged second page costs the sentinel, not a whole second field.
    assert two.startswith(one[: len(one) - 3])
    assert len(two) < 2 * len(one)


def test_an_unchanged_page_round_trips():
    from tetris_sdk.board import Board
    from tetris_sdk.fumen.encoder import encode_fumen
    from tetris_sdk.fumen.parser import parse_fumen
    from tetris_sdk.types import Cell

    def row(n):
        b = Board()
        for c in range(n):
            b.set_cell(0, c, Cell.GARBAGE)
        return b

    boards = [row(n) for n in (1, 3, 3, 7, 10)]
    back = parse_fumen(encode_fumen([(b, "") for b in boards]))
    counts = [
        sum(1 for c in range(10) if bd.get_cell(0, c) != Cell.EMPTY) for bd in back
    ]
    assert counts == [1, 3, 3, 7, 10]


def test_multi_page_round_trips_with_comments():
    from tetris_sdk.board import Board
    from tetris_sdk.fumen.encoder import encode_fumen
    from tetris_sdk.fumen.decoder import decode_fumen
    from tetris_sdk.types import Cell

    pages = []
    for n in range(1, 6):
        b = Board()
        for c in range(n):
            b.set_cell(0, c, Cell.GARBAGE)
        pages.append((b, f"page {n}/5"))
    got = decode_fumen(encode_fumen(pages))
    assert [p["comment"] for p in got] == [f"page {n}/5" for n in range(1, 6)]
