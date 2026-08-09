import pytest

from tetris_sdk import (
    Board,
    Cell,
    Piece,
    PieceType,
    SpinType,
    Event,
    EventKind,
    B2BRule,
    classify_lock,
    is_difficult,
)


# --- helpers ---------------------------------------------------------------

def _setup_clear(board, piece):
    """Fill every row the piece touches except the piece's own cells, so that
    locking the piece clears exactly those rows. Returns the row count."""
    occ = set(piece.cells)
    rows = sorted({r for r, _ in occ})
    for r in rows:
        for c in range(board.cols):
            if (r, c) not in occ:
                board.set_cell(r, c, Cell.GARBAGE)
    return len(rows)


def _vertical_i():
    # cells (0,0),(1,0),(2,0),(3,0): a 4-row well filler -> Quad
    return Piece(PieceType.I, rotation=1, row=0, col=-2)


def _t_double():
    # cells (0,4),(1,3),(1,4),(1,5) -> 2 rows
    return Piece(PieceType.T, rotation=2, row=0, col=3)


def _horizontal_i_single():
    # cells (0,3),(0,4),(0,5),(0,6) -> 1 row
    return Piece(PieceType.I, rotation=0, row=-1, col=3)


def _s_double():
    # cells (1,3),(1,4),(2,4),(2,5) -> 2 rows
    return Piece(PieceType.S, rotation=0, row=0, col=3)


# --- pure classification ----------------------------------------------------

class TestClassifyLock:
    def test_kind_from_lines_and_spin(self):
        assert classify_lock(PieceType.O, SpinType.NONE, 0)[0] == EventKind.PLACEMENT
        assert classify_lock(PieceType.T, SpinType.MINI, 0)[0] == EventKind.SPIN
        assert classify_lock(PieceType.T, SpinType.FULL, 2)[0] == EventKind.CLEAR

    def test_quad_name(self):
        assert classify_lock(PieceType.I, SpinType.NONE, 4) == (EventKind.CLEAR, "Quad")

    def test_plain_clear_names(self):
        assert classify_lock(PieceType.L, SpinType.NONE, 1)[1] == "Single"
        assert classify_lock(PieceType.L, SpinType.NONE, 2)[1] == "Double"
        assert classify_lock(PieceType.L, SpinType.NONE, 3)[1] == "Triple"

    def test_t_spin_names(self):
        assert classify_lock(PieceType.T, SpinType.FULL, 2)[1] == "T-Spin Double"
        assert classify_lock(PieceType.T, SpinType.MINI, 1)[1] == "T-Spin Mini Single"

    def test_non_t_spin_name(self):
        assert classify_lock(PieceType.S, SpinType.FULL, 1)[1] == "S-Spin Single"

    def test_spin_zero_names(self):
        assert classify_lock(PieceType.T, SpinType.MINI, 0)[1] == "T-Spin Mini"
        assert classify_lock(PieceType.Z, SpinType.FULL, 0)[1] == "Z-Spin"
        assert classify_lock(PieceType.O, SpinType.NONE, 0)[1] == "Placement"


class TestIsDifficult:
    def test_zero_lines_never(self):
        for rule in (B2BRule.S1, B2BRule.S2):
            assert not is_difficult(PieceType.T, SpinType.FULL, 0, rule)

    def test_quad_both_rules(self):
        for rule in (B2BRule.S1, B2BRule.S2):
            assert is_difficult(PieceType.I, SpinType.NONE, 4, rule)

    def test_s1_excludes_non_t_spin(self):
        assert not is_difficult(PieceType.S, SpinType.FULL, 1, B2BRule.S1)

    def test_s2_includes_non_t_spin(self):
        assert is_difficult(PieceType.S, SpinType.FULL, 1, B2BRule.S2)

    def test_t_spin_difficult_both_rules(self):
        for rule in (B2BRule.S1, B2BRule.S2):
            assert is_difficult(PieceType.T, SpinType.FULL, 2, rule)
            assert is_difficult(PieceType.T, SpinType.MINI, 1, rule)


class TestEventValue:
    def test_hashable_and_complete(self):
        e = Event(EventKind.CLEAR, PieceType.T, SpinType.FULL, 2,
                  "T-Spin Double", True, False, 1, 1, False)
        f = Event(EventKind.CLEAR, PieceType.T, SpinType.FULL, 2,
                  "T-Spin Double", True, False, 1, 1, False)
        assert e == f and hash(e) == hash(f)
        assert {e, f} == {e}


# --- board lock -------------------------------------------------------------

class TestBoardState:
    def test_new_board_defaults(self):
        b = Board()
        assert b.b2b == 0 and b.combo == 0 and b.b2b_rule == B2BRule.S2

    def test_rule_configurable(self):
        assert Board(b2b_rule=B2BRule.S1).b2b_rule == B2BRule.S1

    def test_fumen_board_defaults(self):
        # an empty-field fumen page
        b = Board.from_fumen("v115@vhAAgH")
        assert b.b2b == 0 and b.combo == 0 and b.b2b_rule == B2BRule.S2


class TestLock:
    def test_clear_event_lines_and_name(self):
        board = Board()
        t = _t_double()
        _setup_clear(board, t)
        ev = board.lock(t, SpinType.FULL)
        assert ev.kind == EventKind.CLEAR
        assert ev.lines == 2
        assert ev.name == "T-Spin Double"
        assert ev.spin == SpinType.FULL

    def test_spin_zero_event(self):
        board = Board()
        ev = board.lock(Piece(PieceType.T, row=10, col=4), SpinType.MINI)
        assert ev.kind == EventKind.SPIN
        assert ev.lines == 0
        assert not ev.difficult

    def test_invalid_placement_raises_and_preserves_state(self):
        board = Board()
        board.b2b = 3
        board.combo = 2
        board.set_cell(0, 0, Cell.GARBAGE)
        with pytest.raises(ValueError):
            board.lock(Piece(PieceType.O, row=0, col=0))
        assert board.b2b == 3 and board.combo == 2


class TestBackToBack:
    def test_chain_progression(self):
        board = Board()
        # first quad: starts chain, not yet b2b
        i = _vertical_i(); _setup_clear(board, i)
        ev1 = board.lock(i)
        assert ev1.lines == 4 and not ev1.back_to_back and board.b2b == 1
        # second quad (board emptied by PC): now back-to-back
        i = _vertical_i(); _setup_clear(board, i)
        ev2 = board.lock(i)
        assert ev2.back_to_back and board.b2b == 2
        # a plain single breaks the chain
        s = _horizontal_i_single(); _setup_clear(board, s)
        ev3 = board.lock(s)
        assert not ev3.difficult and not ev3.back_to_back and board.b2b == 0

    def test_spin_zero_preserves_chain(self):
        board = Board()
        i = _vertical_i(); _setup_clear(board, i)
        board.lock(i)  # b2b -> 1
        board.lock(Piece(PieceType.T, row=10, col=4), SpinType.FULL)  # spin-0
        assert board.b2b == 1  # preserved
        i = _vertical_i(); _setup_clear(board, i)
        ev = board.lock(i)
        assert ev.back_to_back and board.b2b == 2

    def test_rule_selection_changes_difficulty(self):
        for rule, expected in [(B2BRule.S1, False), (B2BRule.S2, True)]:
            board = Board(b2b_rule=rule)
            s = _s_double(); _setup_clear(board, s)
            ev = board.lock(s, SpinType.FULL)
            assert ev.lines == 2
            assert ev.difficult is expected


class TestCombo:
    def test_combo_increments_and_resets(self):
        board = Board()
        i = _vertical_i(); _setup_clear(board, i)
        assert board.lock(i).combo == 1
        i = _vertical_i(); _setup_clear(board, i)
        assert board.lock(i).combo == 2
        # placement clears nothing -> combo resets
        ev = board.lock(Piece(PieceType.O, row=0, col=0))
        assert ev.kind == EventKind.PLACEMENT and ev.combo == 0


class TestPerfectClear:
    def test_perfect_clear_true(self):
        board = Board()
        i = _vertical_i(); _setup_clear(board, i)
        ev = board.lock(i)
        assert ev.perfect_clear

    def test_residual_blocks_not_perfect(self):
        board = Board()
        i = _vertical_i(); _setup_clear(board, i)
        board.set_cell(6, 5, Cell.GARBAGE)  # leftover block above the well
        ev = board.lock(i)
        assert not ev.perfect_clear


class TestS2Attack:
    def test_normal_clears_send_0124_spun_or_not(self):
        from tetris_sdk.events import attack
        for spin in (SpinType.NONE, SpinType.FULL, SpinType.MINI):
            for piece in (PieceType.S, PieceType.Z, PieceType.L, PieceType.I):
                assert attack(piece, spin, 1) == 0
                assert attack(piece, spin, 2) == 1
                assert attack(piece, spin, 3) == 2
                assert attack(piece, spin, 4) == 4

    def test_full_t_spins_send_246(self):
        from tetris_sdk.events import attack
        assert attack(PieceType.T, SpinType.FULL, 1) == 2
        assert attack(PieceType.T, SpinType.FULL, 2) == 4
        assert attack(PieceType.T, SpinType.FULL, 3) == 6
        # minis use the normal table
        assert attack(PieceType.T, SpinType.MINI, 1) == 0
        assert attack(PieceType.T, SpinType.MINI, 2) == 1

    def test_b2b_clear_adds_one(self):
        from tetris_sdk.events import attack
        assert attack(PieceType.I, SpinType.NONE, 4, b2b=True) == 5
        assert attack(PieceType.T, SpinType.FULL, 2, b2b=True) == 5
        assert attack(PieceType.S, SpinType.FULL, 2, b2b=True) == 2
        # non-difficult clears never get the bonus, and no clear means none
        assert attack(PieceType.I, SpinType.NONE, 2, b2b=True) == 1
        assert attack(PieceType.I, SpinType.NONE, 0, b2b=True) == 0

    def test_s1_is_not_implemented(self):
        import pytest
        from tetris_sdk.events import B2BRule, attack
        with pytest.raises(NotImplementedError):
            attack(PieceType.T, SpinType.FULL, 2, rule=B2BRule.S1)
