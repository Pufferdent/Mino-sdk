import pytest
from tetris_sdk import parse_fumen, Board, Cell


SAMPLE_FUMEN = "v115@AhBtDewhBeBtEewhCeR4De0hR4CewhJeAgH"


class TestVersionValidation:
    def test_missing_at_raises_error(self):
        with pytest.raises(ValueError, match="missing '@'"):
            parse_fumen("v115invalid")

    def test_unsupported_version_raises_error(self):
        with pytest.raises(ValueError, match="Unsupported fumen version"):
            parse_fumen("v110@AAAA")

    def test_valid_v115_accepted(self):
        boards = parse_fumen(SAMPLE_FUMEN)
        assert len(boards) == 1


class TestParseFumen:
    def test_parse_returns_list_of_boards(self):
        boards = parse_fumen(SAMPLE_FUMEN)
        assert isinstance(boards, list)
        assert len(boards) == 1
        assert isinstance(boards[0], Board)

    def test_parsed_boards_have_correct_dimensions(self):
        boards = parse_fumen(SAMPLE_FUMEN)
        assert boards[0].rows == 40
        assert boards[0].cols == 10


class TestFieldDecoding:
    def test_sample_fumen_has_piece_colors(self):
        boards = parse_fumen(SAMPLE_FUMEN)
        board = boards[0]

        found_pieces = set()
        for row in range(40):
            for col in range(10):
                c = board.get_cell(row, col)
                if c != Cell.EMPTY:
                    found_pieces.add(c)

        assert Cell.I in found_pieces
        assert Cell.S in found_pieces
        assert Cell.Z in found_pieces

    def test_sample_fumen_top_rows_are_empty(self):
        boards = parse_fumen(SAMPLE_FUMEN)
        board = boards[0]
        for row in range(24, 40):
            for col in range(10):
                assert board.get_cell(row, col) == Cell.EMPTY

    def test_empty_board_fumen(self):
        boards = parse_fumen("v115@vhAAgH")
        board = boards[0]
        for row in range(40):
            for col in range(10):
                assert board.get_cell(row, col) == Cell.EMPTY


class TestDecodeFumenStructure:
    def test_decode_returns_page_with_field_and_piece(self):
        from tetris_sdk.fumen.decoder import decode_fumen
        pages = decode_fumen(SAMPLE_FUMEN)
        assert len(pages) == 1
        page = pages[0]
        assert "field" in page
        assert "piece" in page
        assert len(page["field"]) == 240

