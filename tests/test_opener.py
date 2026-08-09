import pytest

from tetris_sdk.board import Board
from tetris_sdk.opener import Node
from tetris_sdk.pieces import PieceType
from tetris_sdk.types import Cell

T, I, L, J, S, Z, O = (
    PieceType.T, PieceType.I, PieceType.L,
    PieceType.J, PieceType.S, PieceType.Z, PieceType.O,
)


def board_with(cells, fill=Cell.GARBAGE) -> Board:
    board = Board()
    for row, col in cells:
        board.set_cell(row, col, fill)
    return board


# --- canonical fumen --------------------------------------------------------

def test_stacks_differing_only_in_colour_are_the_same_node():
    left = board_with([(0, 0), (0, 1)], Cell.S)
    right = board_with([(0, 0), (0, 1)], Cell.J)
    assert Node.at(left, (T,)) == Node.at(right, (T,))


def test_nodes_are_hashable_and_converge():
    a = Node.at(board_with([(0, 0)], Cell.L), (T, I))
    b = Node.at(board_with([(0, 0)], Cell.Z), (T, I))
    assert len({a, b}) == 1


def test_different_occupancy_is_a_different_node():
    a = Node.at(board_with([(0, 0)]), (T,))
    b = Node.at(board_with([(0, 1)]), (T,))
    assert a != b


def test_the_fumen_round_trips_to_the_same_occupancy():
    node = Node.at(board_with([(0, 0), (0, 9), (1, 4)]), (T,))
    board = node.board()
    filled = {
        (r, c)
        for r in range(board.rows)
        for c in range(board.cols)
        if board.get_cell(r, c) != Cell.EMPTY
    }
    assert filled == {(0, 0), (0, 9), (1, 4)}


# --- bag structure, recovered by counting -----------------------------------

def test_a_full_bag_is_one_set():
    node = Node.at(Board(), (T, I, L, J, S, Z, O))
    assert node.sets() == ((T, I, L, J, S, Z, O),)
    assert node.pattern() == "*p7"


def test_a_partial_bag_is_one_set():
    node = Node.at(Board(), (Z, O))
    assert node.sets() == ((Z, O),)
    assert node.pattern() == "[ZO]p2"


def test_a_duplicate_splits_the_queue_into_two_sets():
    node = Node.at(Board(), (T, T, O, I, L))
    assert node.sets() == ((T,), (T, I, L, O))
    assert node.pattern() == "[T]p1,[TILO]p4"


def test_sets_are_in_pcreview_canonical_order():
    node = Node.at(Board(), (O, Z, S, J, L, I, T))
    assert node.sets() == ((T, I, L, J, S, Z, O),)


def test_bag_structure_is_order_independent():
    a = Node.at(Board(), (T, T, O, I, L))
    b = Node.at(Board(), (O, T, L, I, T))
    assert a.sets() == b.sets() == ((T,), (T, I, L, O))


def test_a_queue_spanning_more_than_two_bags_is_rejected():
    with pytest.raises(ValueError):
        Node.at(Board(), (T, T, T))


# --- futures ----------------------------------------------------------------

def test_futures_enumerate_every_ordering():
    assert len(list(Node.at(Board(), (T, I, L)).futures())) == 6


def test_futures_do_not_repeat_orderings_of_a_duplicate():
    futures = list(Node.at(Board(), (T, T, I)).futures())
    assert len(futures) == len(set(futures)) == 3


# --- hold as the queue head -------------------------------------------------

def test_both_head_entries_are_placeable():
    assert Node.at(Board(), (T, I, L)).active == (T, I)


def test_a_repeated_head_deduplicates():
    assert Node.at(Board(), (T, T, L)).active == (T,)


def test_consuming_the_second_entry_holds_the_first():
    node = Node.at(Board(), (T, I, L))
    assert node.consume(1, Board()).queue == (T, L)


def test_consuming_the_head_plays_it():
    node = Node.at(Board(), (T, I, L))
    assert node.consume(0, Board()).queue == (I, L)


def test_a_revealed_piece_extends_the_queue():
    node = Node.at(Board(), (T, I))
    assert node.consume(0, Board(), drawn=L).queue == (I, L)


def test_only_the_first_two_entries_are_placeable():
    with pytest.raises(ValueError):
        Node.at(Board(), (T, I, L)).consume(2, Board())


def test_consuming_lands_on_the_new_board():
    node = Node.at(Board(), (T, I))
    assert node.consume(0, board_with([(0, 0)])).fumen != node.fumen


# --- board metrics ----------------------------------------------------------

def test_holes_counts_covered_cells():
    # (0,0) empty with (1,0) filled above it.
    node = Node.at(board_with([(1, 0), (0, 1)]), (T,))
    assert node.holes() == 1


def test_a_flat_stack_has_no_holes():
    assert Node.at(board_with([(0, 0), (0, 1)]), (T,)).holes() == 0


def test_mirroring_reflects_the_stack():
    node = Node.at(board_with([(0, 0)]), (T,))
    assert node.mirrored() == Node.at(board_with([(0, 9)]), (T,))


def test_mirroring_is_an_involution():
    node = Node.at(board_with([(0, 0), (1, 3)]), (T, I))
    assert node.mirrored().mirrored() == node


def test_mirroring_leaves_the_queue_alone():
    node = Node.at(board_with([(0, 0)]), (T, I))
    assert node.mirrored().queue == (T, I)
