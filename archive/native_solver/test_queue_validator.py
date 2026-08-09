import pytest
from mino_sdk import PieceType
from mino_sdk.solver.queue_validator import (
    is_placement_order_valid,
    enumerate_placement_orders,
)

T = PieceType.T
I = PieceType.I
L = PieceType.L
J = PieceType.J
S = PieceType.S
Z = PieceType.Z
O = PieceType.O

_dq = PieceType  # alias for type annotations in tests


def make_queue(s: str) -> list[_dq]:
    return [PieceType[ch] for ch in s]


class TestIsPlacementOrderValid:
    def test_no_hold_simple(self):
        assert is_placement_order_valid(
            make_queue("TILJSZO"), make_queue("TILJSZO"), hold_rule="none"
        )

    def test_no_hold_wrong_order(self):
        assert not is_placement_order_valid(
            make_queue("TILJSZO"), make_queue("ITLJSZO"), hold_rule="none"
        )

    def test_standard_reachable_with_hold(self):
        assert is_placement_order_valid(
            make_queue("JIZLOSI"),
            make_queue("IJZOLS"),
            hold_rule="standard",
        )

    def test_standard_unreachable_double_hold(self):
        assert not is_placement_order_valid(
            make_queue("JIZL"),
            make_queue("ZI"),
            hold_rule="standard",
        )

    def test_standard_empty(self):
        assert is_placement_order_valid(
            make_queue("TIL"), [], hold_rule="standard"
        )

    def test_standard_hold_place_hold(self):
        assert is_placement_order_valid(
            make_queue("TIL"),
            make_queue("IT"),
            hold_rule="standard",
        )

    def test_sfinder_unlimited_swap(self):
        assert is_placement_order_valid(
            make_queue("JIZL"),
            make_queue("IZJL"),
            hold_rule="sfinder",
        )

    def test_non_existent_piece(self):
        assert not is_placement_order_valid(
            make_queue("TIL"),
            make_queue("TIS"),
            hold_rule="standard",
        )

    def test_invalid_hold_rule(self):
        with pytest.raises(ValueError, match="Unknown hold_rule"):
            is_placement_order_valid(make_queue("T"), make_queue("T"), hold_rule="bad")

    def test_standard_swap_with_existing_hold(self):
        assert is_placement_order_valid(
            make_queue("JIT"),
            make_queue("JI"),
            hold_rule="standard",
        )

    def test_hold_then_place_old_hold(self):
        assert is_placement_order_valid(
            make_queue("JIT"),
            make_queue("I"),
            hold_rule="standard",
        )


class TestEnumeratePlacementOrders:
    def test_standard_small_queue(self):
        orders = enumerate_placement_orders(make_queue("JI"), hold_rule="standard")
        tuples = [tuple(o) for o in orders]
        assert () in tuples
        assert tuple(make_queue("J")) in tuples
        assert tuple(make_queue("I")) in tuples
        assert tuple(make_queue("JI")) in tuples
        assert tuple(make_queue("IJ")) in tuples
        assert tuple(make_queue("IJ")) in [tuple(o) for o in orders]

    def test_all_respect_standard_rules(self):
        orders = enumerate_placement_orders(make_queue("JIZ"), hold_rule="standard")
        for order in orders:
            assert is_placement_order_valid(
                make_queue("JIZ"), order, hold_rule="standard"
            )

    def test_none_mode(self):
        orders = enumerate_placement_orders(make_queue("TIL"), hold_rule="none")
        assert tuple(make_queue("T")) in [tuple(o) for o in orders]
        assert tuple(make_queue("TI")) in [tuple(o) for o in orders]
        assert tuple(make_queue("TIL")) in [tuple(o) for o in orders]
        assert tuple(make_queue("I")) not in [tuple(o) for o in orders]

    def test_invalid_hold_rule(self):
        with pytest.raises(ValueError, match="Unknown hold_rule"):
            enumerate_placement_orders(make_queue("T"), hold_rule="bad")

    def test_empty_queue(self):
        orders = enumerate_placement_orders([], hold_rule="standard")
        assert orders == [[]]

    def test_sfinder_unlimited(self):
        orders = enumerate_placement_orders(make_queue("JIZ"), hold_rule="sfinder")
        for order in orders:
            assert is_placement_order_valid(
                make_queue("JIZ"), order, hold_rule="sfinder"
            )
