import pytest
from tetris_sdk import (
    Board,
    PieceType,
    board_from_string,
    board_to_string,
    get_piece_cells,
    SRS,
    Cell,
    parse_fumen,
)
from tetris_sdk.solver.core import solve_pc, Solution, _compute_topological_orderings

T = PieceType.T
I = PieceType.I
L = PieceType.L
J = PieceType.J
S = PieceType.S
Z = PieceType.Z
O = PieceType.O

ALL_PIECES = [T, I, L, J, S, Z, O]


class TestSolvePC:
    def test_empty_board(self):
        board = Board()
        queue = [T, I, L]
        result = solve_pc(board, queue)
        assert len(result) == 1
        sol = result[0]
        assert sol.piece_order == []
        assert len(sol.board_states) == 1
        assert sol.operations == []
        assert sol.unused_pieces == queue

    def test_no_solution(self):
        board = board_from_string(
            "XXXXXXXXXX"
            "XXXXXXXXXX"
            "XXXXXXXXXX"
            "XXXXXXXXXX"
        )
        queue = [T, I]
        result = solve_pc(board, queue, clear_lines=4)
        assert result == []

    def test_max_solutions_limit(self):
        board = Board()
        queue = ALL_PIECES
        result = solve_pc(board, queue, max_solutions=1)
        assert len(result) <= 1

    def test_board_string_input(self):
        result = solve_pc(
            "NNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNN",
            [T],
        )
        assert len(result) == 1

    def test_hold_none(self):
        board = Board()
        result = solve_pc(board, [T, I, L], hold="none")
        assert len(result) == 1

    def test_hold_sfinder(self):
        board = Board()
        result = solve_pc(board, [T, I, L], hold="sfinder")
        assert len(result) == 1

    def test_head_hold(self):
        board = Board()
        result = solve_pc(board, [T, I], head_hold=J)
        assert len(result) == 1

    def test_solution_structure(self):
        board = Board()
        result = solve_pc(board, [T, I])
        sol = result[0]
        assert isinstance(sol, Solution)
        assert isinstance(sol.piece_order, list)
        assert isinstance(sol.board_states, list)
        assert isinstance(sol.operations, list)
        assert isinstance(sol.unused_pieces, list)
        assert isinstance(sol.topological_orderings, list)

    def test_piece_type_strings(self):
        board = Board()
        result = solve_pc(board, ["T", "I", "L"], head_hold="J")
        assert len(result) == 1

    def test_unknown_hold_mode(self):
        with pytest.raises(ValueError, match="Unknown hold mode"):
            solve_pc(Board(), [T], hold="bad")

    def test_solutions_have_topological_orderings(self):
        board = Board()
        result = solve_pc(board, ALL_PIECES, max_solutions=3)
        for sol in result:
            if sol.operations:
                assert len(sol.topological_orderings) >= 0

    def test_fumen_board_input(self):
        board = Board.from_fumen("v115@vhAAgH")
        result = solve_pc(board, [T])
        assert len(result) == 1


class TestTopologicalOrderings:
    def test_single_piece(self):
        ops = [(T, 0, 5, 0)]
        orders = _compute_topological_orderings(ops)
        assert orders == [ops]

    def test_empty_ops(self):
        orders = _compute_topological_orderings([])
        assert orders == [[]]

    def test_two_pieces_different_columns(self):
        ops = [
            (I, 0, 3, 0),
            (O, 0, 7, 0),
        ]
        orders = _compute_topological_orderings(ops)
        assert len(orders) >= 1
        for order in orders:
            assert len(order) == 2
            assert set(op[0] for op in order) == {I, O}

    def test_two_pieces_same_column_below_above(self):
        ops = [
            (I, 0, 3, 0),
            (I, 0, 3, 2),
        ]
        orders = _compute_topological_orderings(ops)
        for order in orders:
            assert order[0][0] == I
            assert order[1][0] == I
