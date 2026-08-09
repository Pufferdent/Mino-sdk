import pytest

from mino_sdk import (
    Board,
    Cell,
    Piece,
    PieceType,
    SRS,
    SRSPlus,
    Move,
    SpinType,
    Placement,
    translate,
    soft_drop,
    rotate,
    immobile,
    t_corners_filled,
    classify_spin,
    reachable,
)

ALL_TYPES = [
    PieceType.T, PieceType.I, PieceType.L, PieceType.J,
    PieceType.S, PieceType.Z, PieceType.O,
]


class TestMoveAndSpinTypes:
    def test_rotation_moves(self):
        assert Move.CW.is_rotation
        assert Move.CCW.is_rotation
        assert Move.FLIP.is_rotation
        for m in (Move.LEFT, Move.RIGHT, Move.SOFT_DROP, Move.HARD_DROP):
            assert not m.is_rotation

    def test_spintype_order(self):
        assert SpinType.FULL.rank > SpinType.MINI.rank > SpinType.NONE.rank

    def test_placement_hashable(self):
        a = Placement(PieceType.T, 0, 1, 2, SpinType.FULL, 2, (Move.CW,))
        b = Placement(PieceType.T, 0, 1, 2, SpinType.FULL, 2, (Move.CW,))
        assert a == b and hash(a) == hash(b)
        assert {a, b} == {a}


class TestTranslate:
    def test_valid_move(self):
        board = Board()
        p = Piece(PieceType.O, row=5, col=5)
        moved = translate(board, p, 0, 1)
        assert moved is not None and moved.col == 6 and moved.row == 5
        assert p.col == 5  # original unchanged

    def test_blocked_by_wall(self):
        board = Board()
        p = Piece(PieceType.O, row=5, col=0)
        assert translate(board, p, 0, -1) is None

    def test_blocked_by_cell(self):
        board = Board()
        board.set_cell(5, 7, Cell.GARBAGE)
        p = Piece(PieceType.O, row=5, col=5)
        assert translate(board, p, 0, 1) is None


class TestSoftDrop:
    def test_rests_on_floor(self):
        board = Board()
        p = Piece(PieceType.O, row=20, col=4)
        dropped = soft_drop(board, p)
        assert dropped.row == 0
        assert translate(board, dropped, -1, 0) is None

    def test_rests_on_stack(self):
        board = Board()
        for c in range(10):
            board.set_cell(0, c, Cell.GARBAGE)
            board.set_cell(1, c, Cell.GARBAGE)
        p = Piece(PieceType.O, row=20, col=4)
        dropped = soft_drop(board, p)
        assert dropped.row == 2  # sits on top of the two filled rows


class TestRotate:
    def test_open_space_no_kick(self):
        board = Board()
        p = Piece(PieceType.T, row=10, col=4)
        result = rotate(board, p, Move.CW)
        assert result is not None
        rotated, kick_used = result
        assert rotated.rotation == 1 and not kick_used

    def test_kick_applied_against_obstruction(self):
        # T at rot0 origin (10,5). CW -> rot1. Block the (0,0) candidate's
        # cell (10,6) so the first kick (0,-1) fires, landing at col 4.
        board = Board()
        board.set_cell(10, 6, Cell.GARBAGE)
        p = Piece(PieceType.T, row=10, col=5)
        result = rotate(board, p, Move.CW)
        assert result is not None
        rotated, kick_used = result
        assert kick_used
        assert (rotated.row, rotated.col) == (10, 4)

    def test_impossible_rotation_fails(self):
        # Fully surround so no kick offset fits.
        board = Board()
        for r in range(8, 14):
            for c in range(2, 9):
                board.set_cell(r, c, Cell.GARBAGE)
        # carve exactly a rot0 T and nothing else
        cells = Piece(PieceType.T, row=10, col=5).cells
        for (r, c) in cells:
            board.set_cell(r, c, Cell.EMPTY)
        p = Piece(PieceType.T, row=10, col=5)
        assert rotate(board, p, Move.CW) is None

    def test_o_piece_rotates_in_place(self):
        board = Board()
        p = Piece(PieceType.O, row=10, col=4)
        for direction in (Move.CW, Move.CCW, Move.FLIP):
            result = rotate(board, p, direction)
            assert result is not None
            _, kick_used = result
            assert not kick_used


def _filled_rows_except(board, row, keep_empty_cols):
    for c in range(board.cols):
        if c not in keep_empty_cols:
            board.set_cell(row, c, Cell.GARBAGE)


class TestImmobileAndCorners:
    def test_floating_is_mobile(self):
        board = Board()
        p = Piece(PieceType.T, row=10, col=4)
        assert not immobile(board, p)

    def test_enclosed_is_immobile(self):
        # Build a TSD slot: T-down at origin (1,3) occupies
        # (1,4),(2,3),(2,4),(2,5); fill rows 1 and 2 around it plus an
        # overhang at (3,3).
        board = Board()
        _filled_rows_except(board, 1, {4})
        _filled_rows_except(board, 2, {3, 4, 5})
        board.set_cell(3, 3, Cell.GARBAGE)
        t = Piece(PieceType.T, rotation=2, row=1, col=3)
        assert set(t.cells) == {(1, 4), (2, 3), (2, 4), (2, 5)}
        assert immobile(board, t)
        assert t_corners_filled(board, t) >= 3

    def test_corners_out_of_bounds_count(self):
        board = Board()
        # T resting on the floor against the left wall.
        t = Piece(PieceType.T, rotation=0, row=0, col=-1)
        # center cell is at (1,0); corners (0,-1),(0,1),(2,-1),(2,1):
        # the two with col -1 are out of bounds -> filled.
        assert t_corners_filled(board, t) == 2


class TestClassifySpin:
    def _tsd_board(self):
        board = Board()
        _filled_rows_except(board, 1, {4})
        _filled_rows_except(board, 2, {3, 4, 5})
        board.set_cell(3, 3, Cell.GARBAGE)
        return board, Piece(PieceType.T, rotation=2, row=1, col=3)

    def test_no_rotation_is_none(self):
        board, t = self._tsd_board()
        assert classify_spin(board, t, False) == SpinType.NONE

    def test_t_full_from_corners_and_immobile(self):
        board, t = self._tsd_board()
        assert classify_spin(board, t, True) == SpinType.FULL

    def test_t_mini_three_corners_mobile(self):
        # 3 corners filled but the piece can still move (not immobile).
        board = Board()
        # T-down at (5,3): cells (5,4),(6,3),(6,4),(6,5). center (6,4).
        # corners (5,3),(5,5),(7,3),(7,5). Fill 3 corners but leave (5,3)
        # empty so the piece can still slide left -> mobile.
        board.set_cell(5, 5, Cell.GARBAGE)
        board.set_cell(7, 3, Cell.GARBAGE)
        board.set_cell(7, 5, Cell.GARBAGE)
        t = Piece(PieceType.T, rotation=2, row=5, col=3)
        assert t_corners_filled(board, t) >= 3
        assert not immobile(board, t)
        assert classify_spin(board, t, True) == SpinType.MINI

    def test_t_fewer_than_three_corners(self):
        board = Board()
        t = Piece(PieceType.T, rotation=2, row=10, col=3)
        assert t_corners_filled(board, t) < 3
        assert classify_spin(board, t, True) == SpinType.NONE

    def test_non_t_immobile_is_full(self):
        # Trap an O piece: fill everything around its 2x2 footprint.
        board = Board()
        for r in range(0, 4):
            for c in range(0, 4):
                board.set_cell(r, c, Cell.GARBAGE)
        for (r, c) in Piece(PieceType.O, row=1, col=1).cells:
            board.set_cell(r, c, Cell.EMPTY)
        o = Piece(PieceType.O, row=1, col=1)
        assert immobile(board, o)
        assert classify_spin(board, o, True) == SpinType.FULL

    def test_non_t_mobile_is_none(self):
        board = Board()
        s = Piece(PieceType.S, row=10, col=4)
        assert classify_spin(board, s, True) == SpinType.NONE


class TestReachable:
    def test_empty_board_nonempty_resting(self):
        board = Board()
        for pt in ALL_TYPES:
            placements = reachable(board, pt)
            assert placements
            for pl in placements:
                piece = Piece(pt, rotation=pl.rotation, row=pl.row, col=pl.col)
                assert translate(board, piece, -1, 0) is None  # resting

    def test_dedup_by_cells(self):
        # The number of placements never exceeds distinct cell-sets.
        board = Board()
        placements = reachable(board, PieceType.I)
        cellsets = {
            frozenset(Piece(PieceType.I, rotation=p.rotation,
                            row=p.row, col=p.col).cells)
            for p in placements
        }
        assert len(cellsets) == len(placements)

    def test_finds_tsd_spin(self):
        # Accessible TSD: rows 1 and 2 filled around the slot, overhang at
        # (3,3), and the column above the slot open so the T can tuck in.
        board = Board()
        _filled_rows_except(board, 1, {4})
        _filled_rows_except(board, 2, {3, 4, 5})
        board.set_cell(3, 3, Cell.GARBAGE)
        placements = reachable(board, PieceType.T)
        spins = [p for p in placements if p.spin == SpinType.FULL]
        assert any(p.lines_cleared == 2 for p in spins)

    def test_flip_auto_enables_under_srsplus_only(self):
        board = Board()
        srs_paths = reachable(board, PieceType.T, SRS())
        plus_paths = reachable(board, PieceType.T, SRSPlus())
        srs_has_flip = any(Move.FLIP in p.path for p in srs_paths)
        plus_has_flip = any(Move.FLIP in p.path for p in plus_paths)
        assert not srs_has_flip
        assert plus_has_flip
