import pytest

from tetris_sdk import Board, Cell, Piece, PieceType, RotationSystem, SRS, SRSPlus


ALL_TYPES = [
    PieceType.T, PieceType.I, PieceType.L, PieceType.J,
    PieceType.S, PieceType.Z, PieceType.O,
]


class TestPieceType:
    def test_values(self):
        assert PieceType.T == 1
        assert PieceType.I == 2
        assert PieceType.L == 3
        assert PieceType.J == 4
        assert PieceType.S == 5
        assert PieceType.Z == 6
        assert PieceType.O == 7

    def test_cell_mapping(self):
        assert PieceType.T.cell == Cell.T
        assert PieceType.I.cell == Cell.I
        assert PieceType.L.cell == Cell.L
        assert PieceType.J.cell == Cell.J
        assert PieceType.S.cell == Cell.S
        assert PieceType.Z.cell == Cell.Z
        assert PieceType.O.cell == Cell.O

    def test_cell_value_matches_piece_value(self):
        for pt in ALL_TYPES:
            assert pt.cell.value == pt.value


class TestSRSRotationShapes:
    def test_four_states_four_cells_each(self):
        srs = SRS()
        for pt in ALL_TYPES:
            states = srs.rotations(pt)
            assert len(states) == 4
            for state in states:
                assert len(state) == 4
                for offset in state:
                    assert len(offset) == 2

    def test_offsets_non_negative(self):
        srs = SRS()
        for pt in ALL_TYPES:
            for state in srs.rotations(pt):
                for dr, dc in state:
                    assert dr >= 0 and dc >= 0

    def test_i_piece_states_all_distinct(self):
        states = SRS().rotations(PieceType.I)
        sets = [frozenset(s) for s in states]
        assert len(set(sets)) == 4

    def test_o_piece_states_all_identical(self):
        states = SRS().rotations(PieceType.O)
        sets = [frozenset(s) for s in states]
        assert len(set(sets)) == 1

    def test_i_piece_known_shapes(self):
        # Guideline SRS: spawn on the upper row of the 4x4 box; a clockwise turn
        # (index 1, "R") puts the vertical I in column 2, index 3 ("L") in
        # column 1.
        states = SRS().rotations(PieceType.I)
        assert set(states[0]) == {(2, 0), (2, 1), (2, 2), (2, 3)}
        assert set(states[1]) == {(0, 2), (1, 2), (2, 2), (3, 2)}
        assert set(states[2]) == {(1, 0), (1, 1), (1, 2), (1, 3)}
        assert set(states[3]) == {(0, 1), (1, 1), (2, 1), (3, 1)}


class TestSRSKickTables:
    def test_jlstz_0_to_1(self):
        # Corrected to (drow, dcol) row-up convention (was the (x, y) values).
        kicks = SRS().kicks(PieceType.T, 0, 1)
        assert kicks == [(0, 0), (0, -1), (1, -1), (-2, 0), (-2, -1)]

    def test_jlstz_1_to_0(self):
        kicks = SRS().kicks(PieceType.T, 1, 0)
        assert kicks == [(0, 0), (0, 1), (-1, 1), (2, 0), (2, 1)]

    def test_jlstz_shared_across_types(self):
        srs = SRS()
        for pt in [PieceType.L, PieceType.J, PieceType.S, PieceType.Z]:
            assert srs.kicks(pt, 0, 1) == srs.kicks(PieceType.T, 0, 1)

    def test_i_piece_distinct_from_jlstz(self):
        srs = SRS()
        assert srs.kicks(PieceType.I, 0, 1) != srs.kicks(PieceType.T, 0, 1)

    def test_i_piece_0_to_1(self):
        kicks = SRS().kicks(PieceType.I, 0, 1)
        assert kicks == [(0, 0), (0, -2), (0, 1), (-1, -2), (2, 1)]

    def test_o_piece_empty(self):
        srs = SRS()
        for transition in [(0, 1), (1, 0), (1, 2), (2, 1),
                           (2, 3), (3, 2), (3, 0), (0, 3)]:
            assert srs.kicks(PieceType.O, *transition) == []

    def test_all_jlstz_transitions_five_tests(self):
        srs = SRS()
        for transition in [(0, 1), (1, 0), (1, 2), (2, 1),
                           (2, 3), (3, 2), (3, 0), (0, 3)]:
            assert len(srs.kicks(PieceType.T, *transition)) == 5
            assert len(srs.kicks(PieceType.I, *transition)) == 5


class TestSRSPlus:
    def test_shares_srs_shapes(self):
        srs, plus = SRS(), SRSPlus()
        for pt in ALL_TYPES:
            assert plus.rotations(pt) == srs.rotations(pt)

    def test_jlstz_90_matches_srs(self):
        srs, plus = SRS(), SRSPlus()
        for pt in [PieceType.T, PieceType.L, PieceType.J,
                   PieceType.S, PieceType.Z]:
            assert plus.kicks(pt, 0, 1) == srs.kicks(pt, 0, 1)

    def test_i_90_is_column_reflection(self):
        srs, plus = SRS(), SRSPlus()
        srs_i = srs.kicks(PieceType.I, 0, 1)
        plus_i = plus.kicks(PieceType.I, 0, 1)
        assert plus_i != srs_i
        assert plus_i == [(dr, -dc) for dr, dc in srs_i]

    def test_defines_180_kicks(self):
        plus = SRSPlus()
        for transition in [(0, 2), (2, 0), (1, 3), (3, 1)]:
            assert plus.kicks(PieceType.T, *transition)
            assert plus.kicks(PieceType.I, *transition)

    def test_srs_has_no_180(self):
        srs = SRS()
        for transition in [(0, 2), (2, 0), (1, 3), (3, 1)]:
            assert srs.kicks(PieceType.T, *transition) == []

    def test_o_piece_no_kicks(self):
        plus = SRSPlus()
        for transition in [(0, 1), (0, 2), (2, 0)]:
            assert plus.kicks(PieceType.O, *transition) == []


class TestPieceConstruction:
    def test_defaults(self):
        piece = Piece(PieceType.T)
        assert piece.type == PieceType.T
        assert piece.rotation == 0
        assert piece.row == 0
        assert piece.col == 0
        assert isinstance(piece.system, SRS)

    def test_explicit_values(self):
        piece = Piece(PieceType.I, rotation=1, row=18, col=4)
        assert piece.type == PieceType.I
        assert piece.rotation == 1
        assert piece.row == 18
        assert piece.col == 4

    def test_cells_at_origin(self):
        piece = Piece(PieceType.I, rotation=0, row=0, col=0, system=SRS())
        assert set(piece.cells) == {(2, 0), (2, 1), (2, 2), (2, 3)}

    def test_cells_offset(self):
        piece = Piece(PieceType.T, rotation=0, row=5, col=3, system=SRS())
        assert len(piece.cells) == 4
        for row, col in piece.cells:
            assert row >= 5 and col >= 3

    def test_cells_offset_matches_origin_shift(self):
        origin = Piece(PieceType.T, rotation=0, row=0, col=0).cells
        shifted = Piece(PieceType.T, rotation=0, row=5, col=3).cells
        assert set(shifted) == {(r + 5, c + 3) for r, c in origin}


class TestPieceCopy:
    def test_copy_with_override(self):
        piece = Piece(PieceType.T, rotation=0)
        new = piece.copy(rotation=2)
        assert new.rotation == 2
        assert piece.rotation == 0

    def test_copy_preserves_system(self):
        system = SRS()
        piece = Piece(PieceType.T, col=0, system=system)
        new = piece.copy(col=5)
        assert new.system is system
        assert new.col == 5
        assert piece.col == 0

    def test_copy_preserves_unspecified(self):
        piece = Piece(PieceType.L, rotation=1, row=7, col=2)
        new = piece.copy(row=9)
        assert new.type == PieceType.L
        assert new.rotation == 1
        assert new.row == 9
        assert new.col == 2


class TestBoardCanPlace:
    def test_valid_placement(self):
        board = Board()
        assert board.can_place(Piece(PieceType.O, row=0, col=0)) is True

    def test_blocked_by_occupied_cell(self):
        board = Board()
        piece = Piece(PieceType.O, row=0, col=0)
        occupied = piece.cells[0]
        board.set_cell(occupied[0], occupied[1], Cell.GARBAGE)
        assert board.can_place(piece) is False

    def test_out_of_bounds_left(self):
        board = Board()
        assert board.can_place(Piece(PieceType.T, row=0, col=-1)) is False

    def test_out_of_bounds_right(self):
        board = Board()
        assert board.can_place(Piece(PieceType.O, row=0, col=9)) is False

    def test_out_of_bounds_bottom(self):
        board = Board()
        # I-piece rotation 1 occupies rows 0-3 of its box; row=-1 pushes below 0
        assert board.can_place(Piece(PieceType.I, rotation=1, row=-1, col=0)) is False

    def test_out_of_bounds_top(self):
        board = Board()
        assert board.can_place(Piece(PieceType.O, row=39, col=0)) is False


class TestBoardPlace:
    def test_locks_each_type(self):
        for pt in ALL_TYPES:
            board = Board()
            piece = Piece(pt, row=5, col=2)
            board.place(piece)
            for row, col in piece.cells:
                assert board.get_cell(row, col) == pt.cell

    def test_raises_on_invalid(self):
        board = Board()
        with pytest.raises(ValueError):
            board.place(Piece(PieceType.T, row=0, col=-1))

    def test_correct_cell_value(self):
        board = Board()
        piece = Piece(PieceType.S, row=5, col=2)
        board.place(piece)
        for row, col in piece.cells:
            assert board.get_cell(row, col) == Cell.S


class TestRotationSystemSubclass:
    def test_subclass_usable_as_system(self):
        class Dummy(RotationSystem):
            name = "Dummy"

            def rotations(self, piece_type):
                return [[(0, 0), (0, 1), (1, 0), (1, 1)]] * 4

            def kicks(self, piece_type, from_rot, to_rot):
                return []

        board = Board()
        piece = Piece(PieceType.O, row=0, col=0, system=Dummy())
        assert board.can_place(piece) is True
        assert set(piece.cells) == {(0, 0), (0, 1), (1, 0), (1, 1)}
