import pytest
from tetris_sdk.solver.saves import compute_save_percentage, filter_solves
from tetris_sdk.solver.expressions import parse_expression


class TestComputeSavePercentage:
    def test_basic_percentage(self):
        solves = [["TI", "SZ"], ["TI", "SZ"], ["TI", "SZ"], ["LJ"]]
        result = compute_save_percentage(solves, "T")
        assert result == 75.0

    def test_full_match(self):
        solves = [["TI"], ["TI"], ["TI"]]
        result = compute_save_percentage(solves, "T")
        assert result == 100.0

    def test_no_match(self):
        solves = [["LI"], ["SZ"], ["OJ"]]
        result = compute_save_percentage(solves, "T")
        assert result == 0.0

    def test_empty_solves(self):
        result = compute_save_percentage([], "T")
        assert result == 0.0

    def test_with_ast_node(self):
        ast = parse_expression("T&&S")
        solves = [["TI", "SZ"], ["LI", "SZ"]]
        result = compute_save_percentage(solves, ast)
        assert result == 50.0

    def test_over_solves_mode(self):
        solves = [["TI", "SZ"], ["LI", "SZ"], [], []]
        result = compute_save_percentage(solves, "T", over_solves=True)
        assert result == 50.0

    def test_over_solves_all_empty(self):
        result = compute_save_percentage([[], []], "T", over_solves=True)
        assert result == 0.0

    def test_complex_expression_percentage(self):
        solves = [
            ["TI", "LZ"],
            ["TS", "SZ"],
            ["LI", "OJ"],
            ["TI", "SZ"],
        ]
        result = compute_save_percentage(solves, "T||S")
        assert result == 75.0


class TestFilterSolves:
    def test_filter_basic(self):
        solves = [["TI", "SZ"], ["LI", "SZ"], ["TI", "LJ"]]
        result = filter_solves(solves, "T")
        assert result == [["TI", "SZ"], ["TI", "LJ"]]

    def test_filter_no_match(self):
        solves = [["LI", "SZ"], ["OJ"]]
        result = filter_solves(solves, "T")
        assert result == []

    def test_filter_all_match(self):
        solves = [["TI"], ["TJ"], ["TS"]]
        result = filter_solves(solves, "T")
        assert result == solves

    def test_filter_with_ast(self):
        ast = parse_expression("T&&S")
        solves = [["TI", "SZ"], ["TI", "LJ"], ["TS", "SZ"]]
        result = filter_solves(solves, ast)
        assert result == [["TI", "SZ"], ["TS", "SZ"]]
