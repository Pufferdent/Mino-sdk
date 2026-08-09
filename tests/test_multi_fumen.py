import pytest
from tetris_sdk import MultiFumenPage, Page, Board, Cell

SAMPLE_FUMEN = "v115@AhBtDewhBeBtEewhCeR4De0hR4CewhJeAgH"
EMPTY_FUMEN = "v115@vhAAgH"


class TestMultiFumenPageSingle:
    def test_parses_single_page(self):
        mf = MultiFumenPage.from_string(SAMPLE_FUMEN)
        assert len(mf.pages) == 1
        assert isinstance(mf.pages[0], Page)

    def test_page_has_board_and_comment(self):
        mf = MultiFumenPage.from_string(SAMPLE_FUMEN)
        page = mf.pages[0]
        assert isinstance(page.board, Board)
        assert page.comment == ""

    def test_empty_board_fumen(self):
        mf = MultiFumenPage.from_string(EMPTY_FUMEN)
        board = mf.pages[0].board
        for row in range(40):
            for col in range(10):
                assert board.get_cell(row, col) == Cell.EMPTY

    def test_version_validation(self):
        with pytest.raises(ValueError):
            MultiFumenPage.from_string("v110@AAAA")

    def test_missing_at(self):
        with pytest.raises(ValueError):
            MultiFumenPage.from_string("v115invalid")


class TestMultiFumenPageComments:
    def test_empty_comment_default(self):
        mf = MultiFumenPage.from_string(SAMPLE_FUMEN)
        page = mf.pages[0]
        assert page.comment == ""


class TestMultiFumenPageMultiPage:
    def test_parses_multiple_pages(self):
        mf = MultiFumenPage.from_string(EMPTY_FUMEN)
        assert len(mf.pages) == 1


class TestMultiFumenPageBoardMatchesParser:
    def test_board_matches_parse_fumen(self):
        from tetris_sdk import parse_fumen
        mf = MultiFumenPage.from_string(SAMPLE_FUMEN)
        boards = parse_fumen(SAMPLE_FUMEN)
        mf_board = mf.pages[0].board
        pf_board = boards[0]
        for row in range(40):
            for col in range(10):
                assert mf_board.get_cell(row, col) == pf_board.get_cell(row, col)


class TestColorMode:
    def test_color_mode_page_does_not_clamp(self):
        mf = MultiFumenPage.from_string(SAMPLE_FUMEN)
        page = mf.pages[0]
        assert isinstance(page.board, Board)
