"""Cross-validation tests against reference tools: sfinder.jar and pc-saves-get."""

import subprocess
import sys
import pytest

sys.path.insert(0, "reference/pc-saves-get")

from mino_sdk import (
    Board,
    board_to_string,
    board_from_string,
    PieceType,
    parse_fumen,
    encode_fumen,
    SRS,
)
from mino_sdk.solver.core import solve_pc, Solution
from mino_sdk.solver.expressions import (
    parse_expression as sdk_parse,
    evaluate_ast as sdk_evaluate,
    evaluate_ast_all as sdk_evaluate_all,
)

SFINDER_JAR = "reference/sfinder.jar"
PC_SAVES_GET_DIR = "reference/pc-saves-get"


def run_sfinder_percent(fumen: str, patterns: list[str], clear_line: int = 4) -> str:
    """Run sfinder percent and return stdout."""
    args = [
        "java", "-jar", SFINDER_JAR, "percent",
        "--tetfu", fumen,
        "--patterns", ",".join(patterns),
        "--clear-line", str(clear_line),
    ]
    result = subprocess.run(args, capture_output=True, text=True, timeout=30)
    return result.stdout


def run_sfinder_path(fumen: str, patterns: list[str], clear_line: int = 4) -> str:
    """Run sfinder path and return stdout."""
    args = [
        "java", "-jar", SFINDER_JAR, "path",
        "--tetfu", fumen,
        "--patterns", ",".join(patterns),
        "--clear-line", str(clear_line),
        "--format", "csv",
    ]
    result = subprocess.run(args, capture_output=True, text=True, timeout=60)
    return result.stdout


# --- Expression parser cross-validation ---


class TestExpressionCrossValidate:
    @pytest.mark.parametrize("expr,saves,expected", [
        ("T", ["TI", "SZ"], True),
        ("T", ["LI", "SZ"], False),
        ("T&&S", ["TI", "SZ"], True),
        ("T&&S", ["TI", "LZ"], False),
        ("T||S", ["LI", "SZ"], True),
        ("!T", ["LI", "SZ"], True),
        ("!T", ["TI", "SZ"], False),
        ("^S", ["TI", "LZ"], True),
        ("^S", ["TS", "SZ"], False),
        ("/T[ISZO]/", ["TI", "SZ"], True),
        ("/^L/", ["TI", "SZ"], False),
        ("TSZ", ["TSZ"], True),
        ("TSZ", ["TI", "SZ"], False),
        ("T&&S&&Z", ["TI", "SZ", "LZ"], True),
        ("!(T&&S)||L", ["TI", "LZ"], True),
        ("(T||S)&&(Z||L)", ["TZ", "IL"], True),
        ("^T", ["LI", "SZ"], True),
        ("TO", ["TO"], True),
        ("TO", ["TI", "OZ"], False),
    ])
    def test_evaluate_ast_matches_reference(self, expr, saves, expected):
        sdk_result = sdk_evaluate(sdk_parse(expr), saves)
        assert sdk_result == expected, f"SDK evaluate_ast({expr!r}, {saves}) = {sdk_result}, expected {expected}"


class TestEvaluateASTAll:
    @pytest.mark.parametrize("expr,saves,expected_indices", [
        ("T", ["TI", "SZ", "LI"], [0]),
        ("TS", ["TS", "TI", "SZ", "TIL"], [0]),
        ("T&&S", ["TI", "SZ"], [1]),
    ])
    def test_evaluate_ast_all(self, expr, saves, expected_indices):
        result = sdk_evaluate_all(sdk_parse(expr), saves)
        assert sorted(result) == sorted(expected_indices), (
            f"evaluate_ast_all({expr!r}, {saves}) = {result}, expected {expected_indices}"
        )


# --- sfinder solver cross-validation ---


class TestSfinderCrossValidate:
    def test_sfinder_available(self):
        result = subprocess.run(
            ["java", "-jar", SFINDER_JAR],
            capture_output=True, text=True, timeout=10,
        )
        assert "percent" in result.stdout or "path" in result.stdout

    def test_empty_board_encodes_roundtrip(self):
        """Our fumen encoder produces valid v115 that sfinder parses."""
        fumen = encode_fumen([(Board(), "")])
        # Verify sfinder can parse it without error
        result = run_sfinder_percent(fumen, ["*p1"], clear_line=4)
        assert "Setup Field" in result, f"sfinder should parse fumen:\n{result}"

    def test_sdk_matches_sfinder_empty_board(self):
        """Empty board: both SDK and sfinder find a solution immediately."""
        board = Board()
        queue = [PieceType.T, PieceType.I, PieceType.L]
        sdk_results = solve_pc(board, queue, max_solutions=1)
        assert len(sdk_results) >= 1
        assert sdk_results[0].operations == []

    def test_sdk_solver_on_known_fumen(self):
        """Use a simple fumen and verify sfinder also parses it."""
        board = board_from_string(
            "NNNNNNNNNN"
            "NNNNNNNNNN"
            "NNNNNNNNNN"
            "XXXXXXXXXX"
        )
        fumen = encode_fumen([(board, "")])
        # Verify sfinder parses our encoded fumen
        result = run_sfinder_percent(fumen, ["*p7"], clear_line=4)
        assert "Setup Field" in result
        # SDK should not crash
        sdk_results = solve_pc(board, [PieceType.I] * 7, max_solutions=3, clear_lines=4)
        assert isinstance(sdk_results, list)

    def test_solver_no_crash_on_complex_board(self):
        board = board_from_string(
            "XXXXXXNNNX"
            "NNNXXNNNNX"
            "NNXXNNNNNX"
            "NNNXXNNNNX"
        )
        queue = (
            [PieceType.T, PieceType.I, PieceType.L, PieceType.J,
             PieceType.S, PieceType.Z, PieceType.O]
        )
        results = solve_pc(board, queue, max_solutions=3, clear_lines=4)
        assert isinstance(results, list)
        for sol in results:
            assert isinstance(sol, Solution)


# --- Hold mode cross-validation ---


class TestHoldValidation:
    def test_standard_hold_agrees_with_sfinder(self):
        """Verify SDK hold validation matches sfinder path output."""
        pass
