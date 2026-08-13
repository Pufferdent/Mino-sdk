import pytest
from mino_sdk import parse_fumen, Board, Cell


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
        from mino_sdk.fumen.decoder import decode_fumen
        pages = decode_fumen(SAMPLE_FUMEN)
        assert len(pages) == 1
        page = pages[0]
        assert "field" in page
        assert "piece" in page
        assert len(page["field"]) == 240



class TestMultiPageFieldLineage:
    """Each page is a delta on the field the *previous page settled into*.

    A page that locks leaves behind a field with its mino stamped in and any
    full rows gone. Decoding a later page against the unsettled field instead
    puts cell values outside the legal 0-8, and because every page after it is
    a delta on that, one missed clear corrupts the whole rest of the fumen.
    """

    def _fixture_fumens(self):
        import os
        path = os.path.join(os.path.dirname(__file__), "pc_replay_fixture.fumen")
        with open(path) as handle:
            return [line.strip() for line in handle if line.strip().startswith("v115@")]

    def test_lock_is_set_for_pages_that_place_a_mino(self):
        from mino_sdk.fumen.decoder import decode_fumen

        # The lock bit is inverted on the wire, so reading it straight reports
        # False for exactly the pages that do lock.
        locking = 0
        for fumen in self._fixture_fumens():
            for page in decode_fumen(fumen):
                if page["piece"]["type"]:
                    assert page["piece"]["lock"] is True
                    locking += 1
        assert locking > 0, "fixture should contain pages that place a piece"

    def test_every_page_decodes_to_legal_cell_values(self):
        from mino_sdk.fumen.decoder import decode_fumen

        for fumen in self._fixture_fumens():
            for index, page in enumerate(decode_fumen(fumen)):
                out_of_range = sorted({v for v in page["field"] if not 0 <= v <= 8})
                assert not out_of_range, (
                    f"page {index} decoded cells {out_of_range}; a value outside "
                    f"0-8 means the field lineage desynced"
                )

    def test_clear_lines_drops_full_rows_and_keeps_the_garbage_row(self):
        from mino_sdk.fumen.decoder import _clear_lines, FUMEN_COLS, FUMEN_VISIBLE_ROWS

        size = FUMEN_VISIBLE_ROWS * FUMEN_COLS
        field = [0] * size
        bottom = FUMEN_VISIBLE_ROWS - 2          # last playfield row
        for col in range(FUMEN_COLS):
            field[bottom * FUMEN_COLS + col] = 8         # a full row: clears
            field[(bottom - 1) * FUMEN_COLS + col] = 8   # one gap: survives
        field[(bottom - 1) * FUMEN_COLS] = 0
        for col in range(FUMEN_COLS):
            field[(FUMEN_VISIBLE_ROWS - 1) * FUMEN_COLS + col] = 8  # garbage row

        out = _clear_lines(field, size)
        rows = [out[r * FUMEN_COLS:(r + 1) * FUMEN_COLS] for r in range(FUMEN_VISIBLE_ROWS)]
        assert rows[bottom] == [0] + [8] * (FUMEN_COLS - 1), "gapped row should drop"
        assert rows[FUMEN_VISIBLE_ROWS - 1] == [8] * FUMEN_COLS, "garbage row never clears"
        assert rows[0] == [0] * FUMEN_COLS, "an empty row should be shifted in on top"
